from datetime import datetime
from typing import Optional, Dict, List, Set
import asyncio

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent, AgentResult
from app.agents.code_generator import CodeGeneratorAgent
from app.agents.api_designer import APIDesignerAgent
from app.agents.database_schema import DatabaseSchemaAgent
from app.agents.testing_agent import TestingAgent
from app.agents.documentation_agent import DocumentationAgent
from app.core.task_decomposer import TaskDecomposer, DecomposedTask
from app.models.database import Task, TaskStatus, AgentType, Project
from app.utils.logger import logger


# ── Agent Registry ────────────────────────────────────────────────────────────
AGENT_REGISTRY: Dict[str, BaseAgent] = {
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
        results: Dict,  # task_id -> AgentResult
    ):
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
    ) -> OrchestratorResult:
        """
        Full pipeline with parallel execution:
        1. Decompose request into subtasks
        2. Persist subtasks to DB
        3. Execute in parallel where possible (respecting dependencies)
        4. Return aggregated results
        """
        logger.info(f"Orchestrator starting | project={project_id} | request='{user_request[:60]}'")

        # ── Step 1: Decompose ─────────────────────────────────────────────────
        subtasks = await self.decomposer.decompose(user_request)

        # ── Step 2: Persist to DB ─────────────────────────────────────────────
        task_db_map: Dict[int, Task] = {}

        for subtask in subtasks:
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
            db.flush()
            task_db_map[subtask.id] = db_task

        db.commit()

        # ── Step 3: Execute in parallel where possible ────────────────────────
        results: Dict[int, AgentResult] = {}
        completed_count = 0
        failed_count = 0

        # Group tasks by execution level (tasks with same dependencies can run together)
        execution_levels = self._group_by_level(subtasks)

        for level_tasks in execution_levels:
            # Run all tasks in this level in parallel
            level_results = await self._execute_level(level_tasks, task_db_map, results, db)
            
            for task_id, result in level_results.items():
                results[task_id] = result
                if result.success:
                    completed_count += 1
                else:
                    failed_count += 1

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
    
    def _group_by_level(self, tasks: List[DecomposedTask]) -> List[List[DecomposedTask]]:
        """
        Group tasks into execution levels.
        Tasks in the same level have no dependencies on each other and can run in parallel.
        """
        levels: List[List[DecomposedTask]] = []
        remaining = set(t.id for t in tasks)
        completed: Set[int] = set()

        while remaining:
            # Find all tasks whose dependencies are satisfied
            current_level = []
            for task in tasks:
                if task.id in remaining:
                    deps = set(task.dependencies)
                    if deps.issubset(completed):
                        current_level.append(task)
            
            if not current_level:
                # Circular dependency or error
                raise ValueError("Cannot resolve task dependencies (possible circular reference)")
            
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
        """Execute all tasks in a level concurrently"""
        
        async def execute_single(subtask: DecomposedTask):
            db_task = task_db_map[subtask.id]
            
            # Update status
            db_task.status = TaskStatus.IN_PROGRESS
            db_task.started_at = datetime.utcnow()
            db.commit()
            
            try:
                agent = AGENT_REGISTRY.get(subtask.agent)
                if not agent:
                    db_task.status = TaskStatus.FAILED
                    db_task.error_message = f"Agent '{subtask.agent}' not implemented"
                    db.commit()
                    return (subtask.id, AgentResult(
                        success=False,
                        output={},
                        agent_name=subtask.agent,
                        error=f"Agent not found: {subtask.agent}"
                    ))
                
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
                
                # Update DB
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
                
            except Exception as e:
                db_task.status = TaskStatus.FAILED
                db_task.error_message = str(e)
                db.commit()
                logger.error(f"✗ Task {subtask.id} ({subtask.agent}) crashed: {e}")
                return (subtask.id, AgentResult(
                    success=False,
                    output={},
                    agent_name=subtask.agent,
                    error=str(e)
                ))
        
        # Execute all tasks in this level concurrently
        level_results = await asyncio.gather(*[execute_single(task) for task in level_tasks])
        return dict(level_results)

    def _resolve_agent_type(self, agent_name: str) -> AgentType:
        mapping = {
            "code_generator": AgentType.CODE_GENERATOR,
            "api_designer": AgentType.API_DESIGNER,
            "database_schema": AgentType.DATABASE_SCHEMA,
            "testing_agent": AgentType.TESTING_AGENT,
            "documentation_agent": AgentType.DOCUMENTATION_AGENT,
        }
        return mapping.get(agent_name, AgentType.CODE_GENERATOR)