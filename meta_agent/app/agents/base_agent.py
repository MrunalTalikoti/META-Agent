import hashlib
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.database import AgentExecution, Task, TaskStatus
from app.services.llm_service import LLMService, LLMResponse
from app.core.cache import CacheService
from app.utils.logger import logger
from app.utils.cost_monitor import cost_monitor


class AgentResult:
    """Standardized output from every agent."""

    def __init__(
        self,
        success: bool,
        output: dict,
        agent_name: str,
        execution_time_ms: int = 0,
        error: str = None,
    ):
        self.success = success
        self.output = output
        self.agent_name = agent_name
        self.execution_time_ms = execution_time_ms
        self.error = error

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "agent": self.agent_name,
            "output": self.output,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


class BaseAgent(ABC):
    """
    All specialized agents inherit from this.
    
    Provides:
    - LLM access via self.llm
    - Automatic DB logging of every execution
    - LLM response caching (saves API costs on repeated prompts)
    - Standardized error handling
    - Execution timing
    """

    def __init__(self, name: str, use_cache: bool = True):
        self.name = name
        self.llm = LLMService()
        self.use_cache = use_cache

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Define your agent's personality and output format here.
        This is the most important method to get right.
        """
        pass

    @abstractmethod
    def parse_output(self, raw_content: str) -> dict:
        """
        Parse the LLM's raw string output into a structured dict.
        Override per agent based on expected output format.
        """
        pass

    def build_user_message(
        self,
        description: str,
        inputs: dict = None,
        dependency_results: dict = None,
    ) -> str:
        """
        Constructs the user message sent to the LLM.
        Injects dependency results so agents can build on each other.
        """
        parts = [f"Task: {description}"]

        if inputs:
            parts.append(f"\nAdditional inputs:\n{json.dumps(inputs, indent=2)}")

        if dependency_results:
            parts.append("\nResults from previous tasks (use these as context):")
            for task_id, result in dependency_results.items():
                output = result.get("output", {})
                parts.append(f"\nTask {task_id} output:\n{json.dumps(output, indent=2)}")

        return "\n".join(parts)

    def _make_cache_key(self, messages: list[dict]) -> str:
        """Deterministic cache key from messages content."""
        content = json.dumps(messages, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    async def run(
        self,
        description: str,
        task_db_record: Task,
        db: Session,
        inputs: dict = None,
        dependency_results: dict = None,
    ) -> AgentResult:
        """
        Main execution method. Called by the orchestrator.
        Handles timing, caching, DB logging, and error recovery.
        """
        start_ms = int(time.time() * 1000)
        logger.info(f"[{self.name}] Starting task {task_db_record.id}: {description[:60]}...")

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": self.build_user_message(description, inputs, dependency_results)},
        ]

        # ── Cache check ───────────────────────────────────────────────────────
        llm_response = None
        cache_key = self._make_cache_key(messages)

        if self.use_cache:
            cached = CacheService.get_llm_response(cache_key)
            if cached:
                logger.debug(f"[{self.name}] Cache HIT — skipping LLM call")
                # Reconstruct a fake LLMResponse from cache
                from app.services.llm_service import LLMResponse as LR
                llm_response = LR(
                    content=cached["content"],
                    prompt_tokens=cached["prompt_tokens"],
                    completion_tokens=cached["completion_tokens"],
                    model=cached["model"],
                    provider=cached["provider"],
                )

        # ── LLM call ─────────────────────────────────────────────────────────
        if llm_response is None:
            try:
                llm_response = await self.llm.generate(messages)
                if self.use_cache:
                    CacheService.cache_llm_response(cache_key, {
                        "content": llm_response.content,
                        "prompt_tokens": llm_response.prompt_tokens,
                        "completion_tokens": llm_response.completion_tokens,
                        "model": llm_response.model,
                        "provider": llm_response.provider,
                    })
            except Exception as e:
                error_msg = f"LLM call failed: {str(e)}"
                logger.error(f"[{self.name}] {error_msg}")
                self._log_execution(
                    db=db, task_id=task_db_record.id,
                    llm_response=None, execution_time_ms=int(time.time() * 1000) - start_ms,
                    success=False
                )
                return AgentResult(
                    success=False,
                    output={},
                    agent_name=self.name,
                    execution_time_ms=int(time.time() * 1000) - start_ms,
                    error=error_msg,
                )
            cost_usd = llm_response.estimated_cost_usd()
            cost_monitor.track(cost_usd)

        # ── Parse output ─────────────────────────────────────────────────────
        try:
            parsed_output = self.parse_output(llm_response.content)
        except Exception as e:
            logger.warning(f"[{self.name}] Output parsing failed: {e} — returning raw")
            parsed_output = {"raw_output": llm_response.content}

        execution_time_ms = int(time.time() * 1000) - start_ms

        # ── Log to DB ─────────────────────────────────────────────────────────
        self._log_execution(
            db=db,
            task_id=task_db_record.id,
            llm_response=llm_response,
            execution_time_ms=execution_time_ms,
            success=True,
        )

        logger.info(
            f"[{self.name}] Task {task_db_record.id} complete | "
            f"tokens={llm_response.total_tokens} | {execution_time_ms}ms"
        )

        return AgentResult(
            success=True,
            output=parsed_output,
            agent_name=self.name,
            execution_time_ms=execution_time_ms,
        )

    def _log_execution(
        self,
        db: Session,
        task_id: int,
        llm_response,
        execution_time_ms: int,
        success: bool,
    ):
        """Write execution record to DB for monitoring and cost tracking."""
        try:
            record = AgentExecution(
                task_id=task_id,
                agent_name=self.name,
                llm_provider=llm_response.provider if llm_response else "unknown",
                model_used=llm_response.model if llm_response else "unknown",
                prompt_tokens=llm_response.prompt_tokens if llm_response else 0,
                completion_tokens=llm_response.completion_tokens if llm_response else 0,
                total_tokens=llm_response.total_tokens if llm_response else 0,
                estimated_cost_usd=int(llm_response.estimated_cost_usd() * 1_000_000) if llm_response else 0,
                execution_time_ms=execution_time_ms,
                success=1 if success else 0,
            )
            db.add(record)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log execution to DB: {e}")