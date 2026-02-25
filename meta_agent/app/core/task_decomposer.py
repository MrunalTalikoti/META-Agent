import json
import re

from app.services.llm_service import LLMService
from app.models.database import AgentType
from app.utils.logger import logger


AVAILABLE_AGENTS = {
    "code_generator": "Writes code in any language (Python, JS, Go, etc.)",
    "api_designer": "Designs REST API endpoints, request/response schemas",
    "database_schema": "Designs database tables, columns, and relationships",
    "testing_agent": "Writes unit tests and integration tests",
    "documentation_agent": "Creates README files, API docs, and user guides",
}


class DecomposedTask:
    def __init__(self, id: int, description: str, agent: str, dependencies: list[int], inputs: dict):
        self.id = id
        self.description = description
        self.agent = agent
        self.dependencies = dependencies
        self.inputs = inputs

    def __repr__(self):
        return f"<Task {self.id} | {self.agent} | deps={self.dependencies}>"


class TaskDecomposer:
    def __init__(self):
        self.llm = LLMService()

    async def decompose(self, user_request: str, project_context: str = None) -> list[DecomposedTask]:
        """
        Breaks a user's request into ordered subtasks.
        Each subtask is assigned to one specialized agent.
        """
        agent_descriptions = "\n".join(
            f"- {name}: {desc}" for name, desc in AVAILABLE_AGENTS.items()
        )

        system_prompt = f"""You are a professional project planning AI. Break down user requests into clear subtasks.

AVAILABLE AGENTS:
{agent_descriptions}

RULES:
1. Only use the agent names listed above (exact spelling)
2. If a task needs output from another task, list that task's ID in "dependencies"
3. Keep descriptions specific and actionable (not vague)
4. Minimum 1 task, maximum 8 tasks
5. Return ONLY valid JSON — no markdown, no explanation
6. If you return anything other than a JSON array, the system will fail.

OUTPUT FORMAT (JSON array only):
[
  {{
    "id": 1,
    "description": "Specific description of what to do",
    "agent": "agent_name_from_list",
    "dependencies": [],
    "inputs": {{}}
  }}
]"""

        user_message = f"User request: {user_request}"
        if project_context:
            user_message += f"\n\nProject context: {project_context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self.llm.generate(messages, temperature=0.2)  # Low temp for consistent JSON

        tasks = self._parse_response(response.content)
        self._validate_tasks(tasks)

        logger.info(f"Decomposed '{user_request[:50]}...' into {len(tasks)} tasks")
        for t in tasks:
            logger.debug(f"  {t}")

        return tasks

    def _parse_response(self, content: str) -> list[DecomposedTask]:
        """Parse JSON from LLM response. Handles markdown-wrapped JSON too."""
        # Strip markdown code blocks if present
        json_match = re.search(r"```(?:json)?\n?(.*?)```", content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content

        # Find JSON array
        array_match = re.search(r"\[.*\]", json_str, re.DOTALL)
        if not array_match:
            raise ValueError(f"No JSON array found in decomposer response: {content[:200]}")

        raw_tasks = json.loads(array_match.group(0))

        return [
            DecomposedTask(
                id=t["id"],
                description=t["description"],
                agent=t["agent"],
                dependencies=t.get("dependencies", []),
                inputs=t.get("inputs", {}),
            )
            for t in raw_tasks
        ]

    def _validate_tasks(self, tasks: list[DecomposedTask]) -> None:
        """Ensure task list is valid before executing."""
        task_ids = {t.id for t in tasks}

        for task in tasks:
            # Check agent name is valid
            if task.agent not in AVAILABLE_AGENTS:
                raise ValueError(
                    f"Unknown agent '{task.agent}' in task {task.id}. "
                    f"Valid agents: {list(AVAILABLE_AGENTS.keys())}"
                )

            # Check dependencies reference valid task IDs
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    raise ValueError(
                        f"Task {task.id} depends on task {dep_id} which doesn't exist"
                    )

        logger.debug("Task decomposition validation passed")