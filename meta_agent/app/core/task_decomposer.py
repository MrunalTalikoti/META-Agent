import json
import re

from app.services.llm_service import LLMService
from app.models.database import AgentType
from app.utils.logger import logger


# All agents that exist in the registry
AVAILABLE_AGENTS = {
    "code_generator":        "Writes production code in any language (Python, JS, Go, etc.)",
    "api_designer":          "Designs REST API endpoints, request/response schemas, auth flows",
    "database_schema":       "Designs database tables, columns, relationships, and generates SQL DDL",
    "testing_agent":         "Writes unit tests, integration tests, and test fixtures",
    "documentation_agent":   "Creates README files, API docs, user guides, and inline comments",
    "frontend_generator":    "Creates React/Vue/HTML frontend components with Tailwind CSS",
    "devops":                "Generates Dockerfile, docker-compose, GitHub Actions CI/CD configs",
    "security_auditor":      "Audits code for vulnerabilities: SQLi, XSS, auth flaws, secrets",
    "performance_optimizer": "Identifies bottlenecks, N+1 queries, caching opportunities",
    "requirements_gatherer": "Asks clarifying questions to gather complete project requirements",
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
        agent_descriptions = "\n".join(
            f"- {name}: {desc}" for name, desc in AVAILABLE_AGENTS.items()
        )

        system_prompt = f"""You are a professional project planning AI. Break down user requests into clear subtasks.

AVAILABLE AGENTS:
{agent_descriptions}

RULES:
1. Only use the agent names listed above (exact spelling)
2. If a task needs output from another task, list that task's ID in "dependencies"
3. Keep descriptions specific and actionable
4. Minimum 1 task, maximum 8 tasks
5. Return ONLY valid JSON — no markdown, no explanation
6. Always include a security_auditor task for any project that has user data, auth, or API endpoints
7. Include devops task for any project that needs deployment

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

        response = await self.llm.generate(messages, temperature=0.2)
        tasks = self._parse_response(response.content)

        try:
            self._validate_tasks(tasks)
        except ValueError as e:
            logger.error(f"Task decomposition validation failed: {e}")
            raise

        logger.info(f"Decomposed '{user_request[:50]}...' into {len(tasks)} tasks")
        for t in tasks:
            logger.debug(f"  {t}")

        return tasks

    def _parse_response(self, content: str) -> list[DecomposedTask]:
        json_match = re.search(r"```(?:json)?\n?(.*?)```", content, re.DOTALL)
        json_str = json_match.group(1) if json_match else content

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
        task_ids = {t.id for t in tasks}

        for task in tasks:
            if task.agent not in AVAILABLE_AGENTS:
                raise ValueError(
                    f"Unknown agent '{task.agent}' in task {task.id}. "
                    f"Valid agents: {list(AVAILABLE_AGENTS.keys())}"
                )
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    raise ValueError(
                        f"Task {task.id} depends on task {dep_id} which doesn't exist"
                    )

        # Detect circular dependencies via DFS
        self._check_circular(tasks)
        logger.debug("Task decomposition validation passed")

    def _check_circular(self, tasks: list[DecomposedTask]) -> None:
        graph = {t.id: set(t.dependencies) for t in tasks}
        visited, in_stack = set(), set()

        def dfs(node):
            visited.add(node)
            in_stack.add(node)
            for dep in graph.get(node, set()):
                if dep not in visited:
                    dfs(dep)
                elif dep in in_stack:
                    raise ValueError(
                        f"Circular dependency detected involving task {dep}"
                    )
            in_stack.remove(node)

        for task_id in graph:
            if task_id not in visited:
                dfs(task_id)