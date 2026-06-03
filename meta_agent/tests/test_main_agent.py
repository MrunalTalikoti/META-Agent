"""
MetaAgent test suite
pytest tests/  (from meta_agent/ directory)

Run with:
    pytest tests/ -v --asyncio-mode=auto
"""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, User, Project, Task, TaskStatus, AgentType, UserTier
from app.core.task_decomposer import TaskDecomposer, DecomposedTask, AVAILABLE_AGENTS, MAX_TASKS
from app.core.orchestrator import MetaAgentOrchestrator, AGENT_REGISTRY
from app.agents.code_generator import CodeGeneratorAgent
from app.agents.api_designer import APIDesignerAgent
from app.agents.database_schema import DatabaseSchemaAgent
from app.agents.testing_agent import TestingAgent
from app.agents.documentation_agent import DocumentationAgent
from app.agents.frontend_generator import FrontendGeneratorAgent
from app.agents.devops_agent import DevOpsAgent
from app.agents.security_auditor import SecurityAuditorAgent
from app.agents.performance_optimizer import PerformanceOptimizerAgent
from app.services.llm_service import LLMService, LLMResponse, MockProvider
from app.utils.tier_limits import check_rate_limit
from app.services.validation import SyntaxValidator, QualityChecker, ValidationOrchestrator
from app.services.file_export import FileExportService
from fastapi import HTTPException
import datetime


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture
def user(db):
    u = User(
        email="test@example.com",
        hashed_password="hashed",
        tier=UserTier.FREE,
        requests_today=0,
        last_request_date=datetime.date.today(),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def project(db, user):
    p = Project(user_id=user.id, name="Test Project", description="A test project")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def task(db, project):
    t = Task(
        project_id=project.id,
        title="Test task",
        description="Test description",
        agent_type=AgentType.CODE_GENERATOR,
        status=TaskStatus.PENDING,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def make_llm_response(content: str, model: str = "mock") -> LLMResponse:
    return LLMResponse(
        content=content,
        prompt_tokens=100,
        completion_tokens=200,
        model=model,
        provider="mock",
    )


# ── LLM Service ───────────────────────────────────────────────────────────────

class TestLLMService:
    @pytest.mark.asyncio
    async def test_mock_provider_returns_response(self):
        provider = MockProvider()
        messages = [{"role": "user", "content": "Write hello world in Python"}]
        response = await provider.generate(messages)
        assert response.content
        assert response.total_tokens > 0
        assert response.provider == "mock"

    @pytest.mark.asyncio
    async def test_mock_provider_decomposer_path(self):
        provider = MockProvider()
        messages = [
            {"role": "system", "content": "You break down tasks. AVAILABLE AGENTS are listed."},
            {"role": "user", "content": "User request: build a login API"},
        ]
        response = await provider.generate(messages)
        # Should return a JSON array
        data = json.loads(response.content)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_llm_service_selects_mock_without_keys(self):
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            mock_settings.anthropic_api_key = ""
            svc = LLMService()
            assert isinstance(svc._provider, MockProvider)

    def test_cost_estimation_mock_is_zero(self):
        r = make_llm_response("hello", model="mock")
        assert r.estimated_cost_usd() == 0.0

    def test_cost_estimation_gpt4o(self):
        r = LLMResponse("hello", 1000, 500, "gpt-4o", "openai")
        cost = r.estimated_cost_usd()
        assert cost > 0
        assert cost < 0.01  # sanity check


# ── Task Decomposer ───────────────────────────────────────────────────────────

class TestTaskDecomposer:
    def test_parse_valid_json_array(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        raw = '[{"id": 1, "description": "test", "agent": "code_generator", "dependencies": [], "inputs": {}}]'
        tasks = decomposer._parse_response(raw)
        assert len(tasks) == 1
        assert tasks[0].agent == "code_generator"

    def test_parse_json_in_markdown_block(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        raw = '```json\n[{"id": 1, "description": "test", "agent": "code_generator", "dependencies": [], "inputs": {}}]\n```'
        tasks = decomposer._parse_response(raw)
        assert len(tasks) == 1

    def test_parse_invalid_raises(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        with pytest.raises(Exception):
            decomposer._parse_response("not json at all")

    def test_validate_unknown_agent_raises(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        tasks = [DecomposedTask(1, "test", "unknown_agent", [], {})]
        with pytest.raises(ValueError, match="Unknown agent"):
            decomposer._validate_tasks(tasks)

    def test_validate_missing_dependency_raises(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        tasks = [DecomposedTask(1, "test", "code_generator", [99], {})]
        with pytest.raises(ValueError, match="depends on task 99"):
            decomposer._validate_tasks(tasks)

    def test_validate_circular_dep_raises(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        tasks = [
            DecomposedTask(1, "task1", "code_generator", [2], {}),
            DecomposedTask(2, "task2", "api_designer", [1], {}),
        ]
        with pytest.raises(ValueError, match="[Cc]ircular"):
            decomposer._validate_tasks(tasks)

    # ── Iterative cycle detection (explicit-stack DFS) ────────────────────────

    @staticmethod
    def _task(i, deps):
        return DecomposedTask(i, f"task{i}", "code_generator", deps, {})

    def test_validate_valid_dag_passes(self):
        """A diamond DAG (1; 2→1; 3→1; 4→[2,3]) is acyclic and must pass."""
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        tasks = [
            self._task(1, []),
            self._task(2, [1]),
            self._task(3, [1]),
            self._task(4, [2, 3]),
        ]
        decomposer._validate_tasks(tasks)  # must not raise

    def test_validate_self_loop_raises(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        with pytest.raises(ValueError, match="[Cc]ircular.*task 1"):
            decomposer._validate_tasks([self._task(1, [1])])

    def test_validate_three_node_cycle_raises(self):
        """1→2→3→1 — exercises the explicit stack beyond a single frame."""
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        tasks = [self._task(1, [2]), self._task(2, [3]), self._task(3, [1])]
        with pytest.raises(ValueError, match="[Cc]ircular"):
            decomposer._validate_tasks(tasks)

    def test_check_circular_deep_chain_no_recursion_error(self):
        """A 2000-node linear chain would overflow Python's recursion limit under
        the old recursive DFS. The iterative version handles it (depth bounded by
        memory, not the call stack). Calls _check_circular directly to bypass the
        MAX_TASKS cap that _validate_tasks would otherwise apply first."""
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        chain = [self._task(1, [])] + [self._task(i, [i - 1]) for i in range(2, 2001)]
        decomposer._check_circular(chain)  # must not raise (acyclic) or RecursionError

    def test_check_circular_deep_chain_detects_cycle(self):
        """Same deep chain, but closed into a cycle (1 depends on the last node)."""
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        chain = [self._task(1, [2000])] + [self._task(i, [i - 1]) for i in range(2, 2001)]
        with pytest.raises(ValueError, match="[Cc]ircular"):
            decomposer._check_circular(chain)

    def test_validate_exceeds_max_tasks_raises(self):
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        tasks = [self._task(i, []) for i in range(1, MAX_TASKS + 2)]  # MAX_TASKS + 1
        with pytest.raises(ValueError, match="[Tt]oo many tasks"):
            decomposer._validate_tasks(tasks)

    def test_validate_at_max_tasks_passes(self):
        """Exactly MAX_TASKS valid tasks is allowed (boundary)."""
        decomposer = TaskDecomposer.__new__(TaskDecomposer)
        tasks = [self._task(i, []) for i in range(1, MAX_TASKS + 1)]
        decomposer._validate_tasks(tasks)  # must not raise

    def test_all_registry_agents_in_available_agents(self):
        """Critical: every agent in AGENT_REGISTRY must be in AVAILABLE_AGENTS."""
        from app.core.orchestrator import AGENT_REGISTRY
        for agent_name in AGENT_REGISTRY:
            assert agent_name in AVAILABLE_AGENTS, (
                f"Agent '{agent_name}' is in AGENT_REGISTRY but missing from AVAILABLE_AGENTS. "
                f"The decomposer will never route tasks to it."
            )

    @pytest.mark.asyncio
    async def test_decompose_returns_tasks(self):
        decomposer = TaskDecomposer()
        decomposer.llm = MagicMock()
        decomposer.llm.generate = AsyncMock(return_value=make_llm_response(
            '[{"id": 1, "description": "Generate code", "agent": "code_generator", "dependencies": [], "inputs": {}}]'
        ))
        tasks = await decomposer.decompose("Write a hello world function")
        assert len(tasks) == 1
        assert tasks[0].agent == "code_generator"


# ── Orchestrator ──────────────────────────────────────────────────────────────

class TestOrchestrator:
    def test_group_by_level_simple(self):
        orc = MetaAgentOrchestrator.__new__(MetaAgentOrchestrator)
        tasks = [
            DecomposedTask(1, "t1", "code_generator", [], {}),
            DecomposedTask(2, "t2", "testing_agent", [1], {}),
            DecomposedTask(3, "t3", "documentation_agent", [1], {}),
        ]
        levels = orc._group_by_level(tasks)
        assert len(levels) == 2
        assert len(levels[0]) == 1  # task 1
        assert len(levels[1]) == 2  # tasks 2 and 3 in parallel

    def test_group_by_level_circular_raises(self):
        orc = MetaAgentOrchestrator.__new__(MetaAgentOrchestrator)
        tasks = [
            DecomposedTask(1, "t1", "code_generator", [2], {}),
            DecomposedTask(2, "t2", "api_designer", [1], {}),
        ]
        with pytest.raises(ValueError, match="[Cc]ircular|Cannot resolve"):
            orc._group_by_level(tasks)

    @pytest.mark.asyncio
    async def test_process_creates_tasks_in_db(self, db, project):
        orc = MetaAgentOrchestrator()
        orc.decomposer = MagicMock()
        orc.decomposer.decompose = AsyncMock(return_value=[
            DecomposedTask(1, "Generate code", "code_generator", [], {}),
        ])

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"code": "print('hello')", "language": "python"}
        mock_result.error = None
        mock_result.to_dict = lambda: {"success": True, "output": mock_result.output}

        with patch.dict(AGENT_REGISTRY, {"code_generator": MagicMock(
            run=AsyncMock(return_value=mock_result)
        )}):
            result = await orc.process("Write hello world", project.id, db)

        assert result.total_tasks == 1
        assert result.completed_tasks == 1
        assert result.failed_tasks == 0


# ── Agent parse_output ────────────────────────────────────────────────────────

class TestAgentParsers:
    def test_code_generator_parses_code_block(self):
        agent = CodeGeneratorAgent()
        raw = '```python\ndef hello():\n    return "world"\n```\n\nThis function returns a greeting.'
        result = agent.parse_output(raw)
        assert result["code"] == 'def hello():\n    return "world"'
        assert result["language"] == "python"
        assert "This function" in result["explanation"]

    def test_code_generator_no_block_returns_raw(self):
        agent = CodeGeneratorAgent()
        result = agent.parse_output("No code here")
        assert result["code"] is None
        assert "raw_output" in result

    def test_api_designer_parses_valid_json(self):
        agent = APIDesignerAgent()
        data = {"endpoints": [{"path": "/users", "method": "GET"}], "authentication": "JWT", "base_url": "/api/v1"}
        result = agent.parse_output(json.dumps(data))
        assert result["endpoint_count"] == 1
        assert result["auth_method"] == "JWT"

    def test_api_designer_parses_json_in_markdown(self):
        agent = APIDesignerAgent()
        data = {"endpoints": [], "authentication": "None", "base_url": "/api/v1"}
        raw = f"```json\n{json.dumps(data)}\n```"
        result = agent.parse_output(raw)
        assert "api_design" in result

    def test_api_designer_missing_endpoints_returns_error(self):
        agent = APIDesignerAgent()
        result = agent.parse_output('{"authentication": "JWT"}')
        assert "error" in result

    def test_testing_agent_parses_code_block(self):
        agent = TestingAgent()
        raw = "```python\ndef test_hello_returns_world():\n    assert hello() == 'world'\n```"
        result = agent.parse_output(raw)
        assert result["test_code"] is not None
        assert result["test_count"] >= 1
        assert "test_hello_returns_world" in result["test_names"]

    def test_testing_agent_no_block_returns_error(self):
        agent = TestingAgent()
        result = agent.parse_output("No tests here")
        assert "error" in result

    def test_database_schema_parses_json(self):
        agent = DatabaseSchemaAgent()
        data = {
            "database_type": "PostgreSQL",
            "tables": [{"name": "users", "description": "User table", "columns": [
                {"name": "id", "type": "SERIAL", "primary_key": True, "nullable": False}
            ], "indexes": []}],
            "relationships": []
        }
        result = agent.parse_output(json.dumps(data))
        assert result["table_count"] == 1
        assert "CREATE TABLE" in result["sql_ddl"]

    def test_documentation_agent_returns_markdown(self):
        agent = DocumentationAgent()
        raw = "# My Project\n\n## Overview\nThis is a test.\n\n```python\nprint('hi')\n```"
        result = agent.parse_output(raw)
        assert result["format"] == "markdown"
        assert result["code_examples"] == 1
        assert "My Project" in result["sections"]

    # ── New agent categories: frontend / devops / security / performance ──────

    def test_frontend_generator_extracts_components_and_styles(self):
        agent = FrontendGeneratorAgent()
        result = agent.parse_output(MockProvider.MOCK_RESPONSES["frontend"])
        assert result["component_count"] >= 1
        assert "warning" not in result
        assert any("export default" in c for c in result["components"])
        assert result["styles"]  # css block captured

    def test_frontend_generator_no_components_warns(self):
        agent = FrontendGeneratorAgent()
        result = agent.parse_output("Just prose, no code blocks at all.")
        assert result["component_count"] == 0
        assert "warning" in result

    def test_devops_agent_classifies_files(self):
        agent = DevOpsAgent()
        result = agent.parse_output(MockProvider.MOCK_RESPONSES["devops"])
        assert result["file_count"] >= 1
        assert "warning" not in result
        assert "Dockerfile" in result["files"]
        assert "docker-compose.yml" in result["files"]
        assert ".github/workflows/ci.yml" in result["files"]
        assert ".env.example" in result["files"]

    def test_devops_agent_no_files_warns(self):
        agent = DevOpsAgent()
        result = agent.parse_output("No configuration here.")
        assert result["file_count"] == 0
        assert "warning" in result

    def test_security_auditor_parses_json(self):
        agent = SecurityAuditorAgent()
        result = agent.parse_output(MockProvider.MOCK_RESPONSES["security"])
        assert result["severity"] not in (None, "unknown")
        assert "raw" not in result
        assert len(result["issues"]) >= 1
        assert all({"type", "location", "fix"} <= set(i) for i in result["issues"])

    def test_security_auditor_invalid_json_falls_back(self):
        agent = SecurityAuditorAgent()
        result = agent.parse_output("not json")
        assert result["severity"] == "unknown"  # documents the fallback shape

    def test_performance_optimizer_parses_json(self):
        agent = PerformanceOptimizerAgent()
        result = agent.parse_output(MockProvider.MOCK_RESPONSES["performance"])
        assert "raw" not in result
        assert len(result["bottlenecks"]) >= 1
        assert result["bottlenecks"][0]["impact"] in ("high", "medium", "low")
        assert result["optimizations"]


# ── Mock Provider routing ─────────────────────────────────────────────────────

# Every agent in the registry, paired with a predicate that is True only when
# parse_output() produced a real, schema-correct result (i.e. NOT a fallback).
AGENT_SUCCESS_CHECKS = {
    "code_generator":        lambda o: o.get("code") and "raw_output" not in o,
    "api_designer":          lambda o: o.get("endpoint_count", 0) >= 1 and "error" not in o,
    "database_schema":       lambda o: o.get("table_count", 0) >= 1 and "CREATE TABLE" in o.get("sql_ddl", ""),
    "testing_agent":         lambda o: o.get("test_count", 0) >= 1 and "error" not in o,
    "documentation_agent":   lambda o: o.get("format") == "markdown" and o.get("section_count", 0) >= 1,
    "requirements_gatherer": lambda o: o.get("status") in ("needs_clarification", "ready"),
    "frontend_generator":    lambda o: o.get("component_count", 0) >= 1 and "warning" not in o,
    "devops":                lambda o: o.get("file_count", 0) >= 1 and "warning" not in o,
    "security_auditor":      lambda o: o.get("severity") not in (None, "unknown") and "raw" not in o,
    "performance_optimizer": lambda o: len(o.get("bottlenecks", [])) >= 1 and "raw" not in o,
}


class TestMockProviderRouting:
    """The MockProvider must hand every agent schema-correct content."""

    @pytest.mark.asyncio
    async def test_routes_frontend_by_system_prompt(self):
        provider = MockProvider()
        messages = [
            {"role": "system", "content": FrontendGeneratorAgent().get_system_prompt()},
            {"role": "user", "content": "Build the dashboard"},  # no routing keywords
        ]
        content = (await provider.generate(messages)).content
        assert "```tsx" in content

    @pytest.mark.asyncio
    async def test_routes_devops_by_system_prompt(self):
        provider = MockProvider()
        messages = [
            {"role": "system", "content": DevOpsAgent().get_system_prompt()},
            {"role": "user", "content": "Set up deployment"},
        ]
        content = (await provider.generate(messages)).content
        assert "Dockerfile" in content and "docker-compose" in content

    @pytest.mark.asyncio
    async def test_routes_security_by_system_prompt(self):
        provider = MockProvider()
        messages = [
            {"role": "system", "content": SecurityAuditorAgent().get_system_prompt()},
            {"role": "user", "content": "Review the code"},
        ]
        data = json.loads((await provider.generate(messages)).content)
        assert data["severity"] == "high" and data["issues"]

    @pytest.mark.asyncio
    async def test_routes_performance_by_system_prompt(self):
        provider = MockProvider()
        messages = [
            {"role": "system", "content": PerformanceOptimizerAgent().get_system_prompt()},
            {"role": "user", "content": "Make it faster"},
        ]
        data = json.loads((await provider.generate(messages)).content)
        assert data["bottlenecks"]

    @pytest.mark.asyncio
    async def test_system_prompt_beats_misleading_keywords(self):
        """A frontend task whose description mentions 'api'/'database' must still
        route by the frontend system prompt, not the keyword fallback."""
        provider = MockProvider()
        messages = [
            {"role": "system", "content": FrontendGeneratorAgent().get_system_prompt()},
            {"role": "user", "content": "Build a UI that calls the api and shows database tables"},
        ]
        content = (await provider.generate(messages)).content
        assert "```tsx" in content  # frontend wins despite 'api'/'database' keywords

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_name", list(AGENT_SUCCESS_CHECKS.keys()))
    async def test_no_agent_falls_back_to_default(self, agent_name):
        """Every registered agent must parse the MockProvider output into a real
        result — never the generic 'default' / warning / raw fallback."""
        from app.core.orchestrator import AGENT_REGISTRY

        agent = AGENT_REGISTRY[agent_name]
        messages = [
            {"role": "system", "content": agent.get_system_prompt()},
            {"role": "user", "content": "Build a user management feature"},
        ]
        response = await MockProvider().generate(messages)

        # The generic prose default must never be what an agent receives.
        assert response.content != MockProvider.MOCK_RESPONSES["default"]

        output = agent.parse_output(response.content)
        assert AGENT_SUCCESS_CHECKS[agent_name](output), (
            f"{agent_name} fell back instead of parsing mock output: {output}"
        )

    def test_every_registry_agent_has_a_success_check(self):
        """Guard: if a new agent is registered, this suite must cover it."""
        from app.core.orchestrator import AGENT_REGISTRY
        assert set(AGENT_REGISTRY) == set(AGENT_SUCCESS_CHECKS)


# ── Syntax Validator ──────────────────────────────────────────────────────────

class TestSyntaxValidator:
    def test_valid_python_passes(self):
        v = SyntaxValidator()
        result = v.validate("def hello():\n    return 'world'\n", "python")
        assert result.passed

    def test_invalid_python_fails(self):
        v = SyntaxValidator()
        result = v.validate("def hello(\n    broken syntax", "python")
        assert not result.passed
        assert any(i.severity == "error" for i in result.issues)

    def test_wildcard_import_warns(self):
        v = SyntaxValidator()
        result = v.validate("from os import *\nprint('hi')", "python")
        assert result.passed  # warns but doesn't fail
        assert any("wildcard" in i.message.lower() for i in result.issues)

    def test_valid_json_passes(self):
        v = SyntaxValidator()
        result = v.validate('{"key": "value"}', "json")
        assert result.passed

    def test_invalid_json_fails(self):
        v = SyntaxValidator()
        result = v.validate("{bad json}", "json")
        assert not result.passed

    def test_unknown_language_passes(self):
        v = SyntaxValidator()
        result = v.validate("anything", "brainfuck")
        assert result.passed


# ── Tier Limits ───────────────────────────────────────────────────────────────

class TestTierLimits:
    def test_free_user_within_limit_passes(self, db, user):
        user.requests_today = 5
        user.tier = UserTier.FREE
        db.commit()
        check_rate_limit(user, db)  # Should not raise
        assert user.requests_today == 6

    def test_free_user_at_limit_raises(self, db, user):
        user.requests_today = 10
        user.tier = UserTier.FREE
        user.last_request_date = datetime.date.today()
        db.commit()
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(user, db)
        assert exc_info.value.status_code == 429

    def test_counter_resets_on_new_day(self, db, user):
        user.requests_today = 9
        user.last_request_date = datetime.date(2000, 1, 1)  # Old date
        user.tier = UserTier.FREE
        db.commit()
        check_rate_limit(user, db)  # Should reset, then allow
        assert user.requests_today == 1

    def test_pro_user_unlimited(self, db, user):
        user.requests_today = 999
        user.tier = UserTier.PRO
        user.last_request_date = datetime.date.today()
        db.commit()
        check_rate_limit(user, db)  # Should not raise


# ── File Export ───────────────────────────────────────────────────────────────

class TestFileExport:
    def test_build_zip_returns_bytes(self, project, db):
        task = Task(
            project_id=project.id,
            title="Task 1: code_generator",
            description="Generate code",
            agent_type=AgentType.CODE_GENERATOR,
            status=TaskStatus.COMPLETED,
            output_data={"code": "print('hello')", "language": "python", "explanation": "Simple print"},
        )
        db.add(task)
        db.commit()

        result = FileExportService.build_zip(project, [task])
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_zip_contains_manifest(self, project, db):
        import zipfile, io
        task = Task(
            project_id=project.id,
            title="Task 1: documentation_agent",
            description="Write docs",
            agent_type=AgentType.DOCUMENTATION_AGENT,
            status=TaskStatus.COMPLETED,
            output_data={"documentation": "# README\nHello world"},
        )
        db.add(task)
        db.commit()

        zip_bytes = FileExportService.build_zip(project, [task])
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
        assert "MANIFEST.md" in names
        assert "README.md" in names