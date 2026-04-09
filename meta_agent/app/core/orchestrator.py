import asyncio
from datetime import datetime
from typing import Optional, Dict, List, Set

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent, AgentResult
from app.agents.code_generator import CodeGeneratorAgent
from app.agents.api_designer import APIDesignerAgent
from app.agents.database_schema import DatabaseSchemaAgent
from app.agents.testing_agent import TestingAgent
from app.agents.documentation_agent import DocumentationAgent
from app.agents.requirements_gatherer import RequirementsGathererAgent
from app.agents.frontend_generator import FrontendGeneratorAgent
from app.agents.devops_agent import DevOpsAgent
from app.agents.security_auditor import SecurityAuditorAgent
from app.agents.performance_optimizer import PerformanceOptimizerAgent
from app.core.task_decomposer import TaskDecomposer, DecomposedTask
from app.models.database import Task, TaskStatus, AgentType, Project
from app.utils.logger import logger

TASK_TIMEOUT_SECONDS = 120  # Per-task LLM timeout

# ── Agent Registry (all 10 agents) ────────────────────────────────────────────
AGENT_REGISTRY: Dict[str, BaseAgent] = {
    "code_generator":        CodeGeneratorAgent(),
    "api_designer":          APIDesignerAgent(),
    "database_schema":       DatabaseSchemaAgent(),
    "testing_agent":         TestingAgent(),
    "documentation_agent":   DocumentationAgent(),
    "requirements_gatherer": RequirementsGathererAgent(),
    "frontend_generator":    FrontendGeneratorAgent(),
    "devops":                DevOpsAgent(),
    "security_auditor":      SecurityAuditorAgent(),
    "performance_optimizer": PerformanceOptimizerAgent(),
}

_AGENT_TYPE_MAP = {
    "code_generator":        AgentType.CODE_GENERATOR,
    "api_designer":          AgentType.API_DESIGNER,
    "database_schema":       AgentType.DATABASE_SCHEMA,
    "testing_agent":         AgentType.TESTING_AGENT,
    "documentation_agent":   AgentType.DOCUMENTATION_AGENT,
    "requirements_gatherer": AgentType.REQUIREMENTS_GATHERER,
    # These three reuse CODE_GENERATOR enum value as DB enum wasn't extended
    "frontend_generator":    AgentType.CODE_GENERATOR,
    "devops":                AgentType.CODE_GENERATOR,
    "security_auditor":      AgentType.CODE_GENERATOR,
    "performance_optimizer": AgentType.CODE_GENERATOR,
}


class OrchestratorResult:
    def __init__(self, project_id, user_request, total_tasks, completed_tasks, failed_tasks, results):
        self.project_id = project_id
        self.user_request = user_request
        self.total_tasks = total_tasks
        self.completed_tasks = completed_tasks
        self.failed_tasks = failed_tasks
        self.results = results
        self.success = failed_tasks == 0

    def to_dict(self) -> Dict:
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
        project_context: str = None,
    ) -> OrchestratorResult:
        logger.info(f"Orchestrator starting | project={project_id} | request='{user_request[:60]}'")

        # ── Decompose ─────────────────────────────────────────────────────────
        try:
            subtasks = await self.decomposer.decompose(user_request, project_context)
        except ValueError as e:
            logger.error(f"Decomposition failed: {e}")
            raise

        # ── Persist to DB ─────────────────────────────────────────────────────
        task_db_map: Dict[int, Task] = {}
        for subtask in subtasks:
            db_task = Task(
                project_id=project_id,
                title=f"Task {subtask.id}: {subtask.agent}",
                description=subtask.description,
                agent_type=_AGENT_TYPE_MAP.get(subtask.agent, AgentType.CODE_GENERATOR),
                status=TaskStatus.PENDING,
                execution_order=subtask.id,
                dependency_ids=subtask.dependencies,
                input_data=subtask.inputs,
            )
            db.add(db_task)
            db.flush()
            task_db_map[subtask.id] = db_task
        db.commit()

        # ── Execute by level ──────────────────────────────────────────────────
        results: Dict[int, AgentResult] = {}
        completed_count = 0
        failed_count = 0

        for level_tasks in self._group_by_level(subtasks):
            level_results = await self._execute_level(level_tasks, task_db_map, results, db)
            for task_id, result in level_results.items():
                results[task_id] = result
                if result.success:
                    completed_count += 1
                else:
                    failed_count += 1

        logger.info(
            f"Orchestrator complete | completed={completed_count}/{len(subtasks)} | failed={failed_count}"
        )

        return OrchestratorResult(
            project_id=project_id,
            user_request=user_request,
            total_tasks=len(subtasks),
            completed_tasks=completed_count,
            failed_tasks=failed_count,
            results=results,
        )

    def _group_by_level(self, tasks: List[DecomposedTask]) -> List[List[DecomposedTask]]:
        levels: List[List[DecomposedTask]] = []
        remaining = set(t.id for t in tasks)
        completed: Set[int] = set()

        while remaining:
            current_level = [
                task for task in tasks
                if task.id in remaining and set(task.dependencies).issubset(completed)
            ]
            if not current_level:
                raise ValueError("Cannot resolve task dependencies (circular reference or missing task)")

            levels.append(current_level)
            for task in current_level:
                remaining.remove(task.id)
                completed.add(task.id)

        return levels

    async def _execute_level(
        self,
        level_tasks: List[DecomposedTask],
        task_db_map: Dict[int, Task],
        results: Dict[int, AgentResult],
        db: Session,
    ) -> Dict[int, AgentResult]:

        async def execute_single(subtask: DecomposedTask):
            db_task = task_db_map[subtask.id]
            db_task.status = TaskStatus.IN_PROGRESS
            db_task.started_at = datetime.utcnow()
            db.commit()

            agent = AGENT_REGISTRY.get(subtask.agent)
            if not agent:
                err = f"Agent '{subtask.agent}' not found in registry"
                db_task.status = TaskStatus.FAILED
                db_task.error_message = err
                db.commit()
                logger.error(f"✗ Task {subtask.id}: {err}")
                return (subtask.id, AgentResult(success=False, output={}, agent_name=subtask.agent, error=err))

            dependency_results = {
                dep_id: results[dep_id].to_dict()
                for dep_id in subtask.dependencies
                if dep_id in results and results[dep_id].success
            }

            try:
                result = await asyncio.wait_for(
                    agent.run(
                        description=subtask.description,
                        task_db_record=db_task,
                        db=db,
                        inputs=subtask.inputs,
                        dependency_results=dependency_results,
                    ),
                    timeout=TASK_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                err = f"Task timed out after {TASK_TIMEOUT_SECONDS}s"
                db_task.status = TaskStatus.FAILED
                db_task.error_message = err
                db.commit()
                logger.error(f"✗ Task {subtask.id} ({subtask.agent}) timed out")
                return (subtask.id, AgentResult(success=False, output={}, agent_name=subtask.agent, error=err))
            except Exception as e:
                err = str(e)
                db_task.status = TaskStatus.FAILED
                db_task.error_message = err
                db.commit()
                logger.error(f"✗ Task {subtask.id} ({subtask.agent}) crashed: {e}")
                return (subtask.id, AgentResult(success=False, output={}, agent_name=subtask.agent, error=err))

            if result.success:
                db_task.status = TaskStatus.COMPLETED
                db_task.output_data = result.output
                db_task.completed_at = datetime.utcnow()
                logger.info(f"✓ Task {subtask.id} ({subtask.agent}) completed")
            else:
                db_task.status = TaskStatus.FAILED
                db_task.error_message = result.error
                logger.error(f"✗ Task {subtask.id} ({subtask.agent}) failed: {result.error}")

            db.commit()
            return (subtask.id, result)

        level_results = await asyncio.gather(*[execute_single(task) for task in level_tasks])
        return dict(level_results)