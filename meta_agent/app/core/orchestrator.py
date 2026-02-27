from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent, AgentResult
from app.agents.code_generator import CodeGeneratorAgent
from app.core.task_decomposer import TaskDecomposer, DecomposedTask
from app.models.database import Task, TaskStatus, AgentType, Project
from app.utils.logger import logger

from app.agents.base_agent import BaseAgent, AgentResult
from app.agents.code_generator import CodeGeneratorAgent
from app.agents.api_designer import APIDesignerAgent
from app.agents.database_schema import DatabaseSchemaAgent
from app.agents.testing_agent import TestingAgent
from app.agents.documentation_agent import DocumentationAgent


# ── Agent Registry ────────────────────────────────────────────────────────────
# Add new agents here as you build them (Day 4+)
AGENT_REGISTRY: dict[str, BaseAgent] = {
    "code_generator": CodeGeneratorAgent(),
    "api_designer": APIDesignerAgent(),
    "database_schema": DatabaseSchemaAgent(),
    "testing_agent": TestingAgent(),
    "documentation_agent": DocumentationAgent(),
}


class OrchestratorResult:
    def __init__(
        self,
        project_id: int,
        user_request: str,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        results: dict,  # task_id -> AgentResult
    ):
        self.project_id = project_id
        self.user_request = user_request
        self.total_tasks = total_tasks
        self.completed_tasks = completed_tasks
        self.failed_tasks = failed_tasks
        self.results = results
        self.success = failed_tasks == 0

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "user_request": self.user_request,
            "success": self.success,
            "summary": {
                "total": self.total_tasks,
                "completed": self.completed_tasks,
                "failed": self.failed_tasks,
            },
            "results": {
                str(task_id): result.to_dict()
                for task_id, result in self.results.items()
            },
        }


class MetaAgentOrchestrator:
    def __init__(self):
        self.decomposer = TaskDecomposer()

    async def process(
        self,
        user_request: str,
        project_id: int,
        db: Session,
    ) -> OrchestratorResult:
        """
        Full pipeline:
        1. Decompose request into subtasks
        2. Persist subtasks to DB
        3. Execute in dependency order
        4. Return aggregated results
        """
        logger.info(f"Orchestrator starting | project={project_id} | request='{user_request[:60]}'")

        # ── Step 1: Decompose ─────────────────────────────────────────────────
        subtasks = await self.decomposer.decompose(user_request)

        # ── Step 2: Persist to DB ─────────────────────────────────────────────
        task_db_map: dict[int, Task] = {}

        for subtask in subtasks:
            # Map agent name string to AgentType enum
            agent_type = self._resolve_agent_type(subtask.agent)

            db_task = Task(
                project_id=project_id,
                title=f"Task {subtask.id}: {subtask.agent}",
                description=subtask.description,
                agent_type=agent_type,
                status=TaskStatus.PENDING,
                execution_order=subtask.id,
                dependency_ids=subtask.dependencies,
                input_data=subtask.inputs,
            )
            db.add(db_task)
            db.flush()  # Gets the DB-assigned ID without committing
            task_db_map[subtask.id] = db_task

        db.commit()

        # ── Step 3: Execute in order ──────────────────────────────────────────
        results: dict[int, AgentResult] = {}
        completed_count = 0
        failed_count = 0

        for subtask in self._execution_order(subtasks):
            db_task = task_db_map[subtask.id]

            # Check all dependencies completed successfully
            deps_ok = all(
                results.get(dep_id) and results[dep_id].success
                for dep_id in subtask.dependencies
            )

            if not deps_ok:
                logger.warning(f"Skipping task {subtask.id} — dependency failed")
                db_task.status = TaskStatus.SKIPPED
                db.commit()
                continue

            # Update DB status
            db_task.status = TaskStatus.IN_PROGRESS
            db_task.started_at = datetime.utcnow()
            db.commit()

            # Get agent
            agent = AGENT_REGISTRY.get(subtask.agent)
            if not agent:
                logger.error(f"No agent registered for '{subtask.agent}'")
                db_task.status = TaskStatus.FAILED
                db_task.error_message = f"Agent '{subtask.agent}' not implemented yet"
                db.commit()
                failed_count += 1
                continue

            # Build dependency context
            dependency_results = {
                dep_id: results[dep_id].to_dict()
                for dep_id in subtask.dependencies
                if dep_id in results
            }

            # Run agent
            result = await agent.run(
                description=subtask.description,
                task_db_record=db_task,
                db=db,
                inputs=subtask.inputs,
                dependency_results=dependency_results,
            )
            results[subtask.id] = result

            # Update DB with result
            if result.success:
                db_task.status = TaskStatus.COMPLETED
                db_task.output_data = result.output
                db_task.completed_at = datetime.utcnow()
                completed_count += 1
                logger.info(f"✓ Task {subtask.id} ({subtask.agent}) completed")
            else:
                db_task.status = TaskStatus.FAILED
                db_task.error_message = result.error
                failed_count += 1
                logger.error(f"✗ Task {subtask.id} ({subtask.agent}) failed: {result.error}")

            db.commit()

        logger.info(
            f"Orchestrator complete | "
            f"completed={completed_count}/{len(subtasks)} | "
            f"failed={failed_count}"
        )

        return OrchestratorResult(
            project_id=project_id,
            user_request=user_request,
            total_tasks=len(subtasks),
            completed_tasks=completed_count,
            failed_tasks=failed_count,
            results=results,
        )

    def _execution_order(self, tasks: list[DecomposedTask]) -> list[DecomposedTask]:
        """Topological sort — tasks with no dependencies execute first."""
        completed = set()
        ordered = []

        # Max iterations to prevent infinite loop on circular deps
        for _ in range(len(tasks) * 2):
            if len(ordered) == len(tasks):
                break
            for task in tasks:
                if task.id not in completed:
                    if all(dep in completed for dep in task.dependencies):
                        ordered.append(task)
                        completed.add(task.id)

        return ordered

    def _resolve_agent_type(self, agent_name: str) -> AgentType:
        mapping = {
            "code_generator": AgentType.CODE_GENERATOR,
            "api_designer": AgentType.API_DESIGNER,
            "database_schema": AgentType.DATABASE_SCHEMA,
            "testing_agent": AgentType.TESTING_AGENT,
            "documentation_agent": AgentType.DOCUMENTATION_AGENT,
        }
        return mapping.get(agent_name, AgentType.CODE_GENERATOR)