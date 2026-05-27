"""
Parser robustness tests using realistic LLM output samples.

Existing tests in test_main_agent.py use perfectly formatted synthetic inputs
that always match expected patterns.  Real LLM outputs vary in:
  - language tag spelling (js vs javascript vs react)
  - presence/absence of fenced code blocks
  - extra prose before/after/between code
  - markdown headings, bullets, and nested formatting
  - missing language tags entirely

These tests exercise the actual parse_output() methods against sampled
outputs to catch regex brittleness before it reaches production.

Run with:
    pytest tests/unit/test_parser_robustness.py -v
"""

from pathlib import Path

import pytest

from app.agents.code_generator import CodeGeneratorAgent
from app.agents.frontend_generator import FrontendGeneratorAgent
from app.agents.devops_agent import DevOpsAgent
from app.agents.testing_agent import TestingAgent

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "llm_outputs"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ── CodeGeneratorAgent ───────────────────────────────────────────────────────


class TestCodeGeneratorRealistic:
    def setup_method(self):
        self.agent = CodeGeneratorAgent()

    def test_gpt4o_long_response_with_heading(self):
        """GPT-4o often adds markdown headings before code."""
        raw = _load("code_generator_gpt4o.md")
        result = self.agent.parse_output(raw)

        assert result["code"] is not None
        assert "class AuthService" in result["code"]
        assert result["language"] == "python"
        assert result["line_count"] > 10

    def test_claude_minimal_no_language_tag(self):
        """Claude sometimes omits the language tag on short responses."""
        raw = _load("code_generator_claude_minimal.md")
        result = self.agent.parse_output(raw)

        assert result["code"] is not None
        assert "validate_email" in result["code"]

    def test_no_code_fences_returns_raw(self):
        """LLM responds with bare code — no backtick fences at all."""
        raw = _load("code_generator_no_fences.md")
        result = self.agent.parse_output(raw)

        # Parser should gracefully return raw_output
        assert result["code"] is None
        assert "raw_output" in result
        assert "calculate_shipping" in result["raw_output"]

    def test_javascript_language_tag(self):
        """LLM uses 'javascript' instead of 'js'."""
        raw = _load("code_generator_javascript.md")
        result = self.agent.parse_output(raw)

        assert result["code"] is not None
        assert result["language"] == "javascript"
        assert "apiLimiter" in result["code"]

    def test_inline_prose_before_code_block(self):
        """Ensure explanatory text before the code block doesn't break parsing."""
        raw = (
            "Great question! Here's what I'd suggest:\n\n"
            "```python\n"
            "def greet(name: str) -> str:\n"
            '    return f"Hello, {name}!"\n'
            "```\n\n"
            "This is a simple greeting function."
        )
        result = self.agent.parse_output(raw)

        assert result["code"] is not None
        assert "def greet" in result["code"]
        assert "simple greeting" in result["explanation"]

    def test_multiple_code_blocks_picks_first(self):
        """When LLM outputs multiple blocks, parser takes the first."""
        raw = (
            "```python\ndef main():\n    pass\n```\n\n"
            "And here's a helper:\n\n"
            "```python\ndef helper():\n    pass\n```"
        )
        result = self.agent.parse_output(raw)

        assert result["code"] is not None
        assert "def main" in result["code"]
        assert "def helper" not in result["code"]


# ── FrontendGeneratorAgent ───────────────────────────────────────────────────


class TestFrontendGeneratorRealistic:
    def setup_method(self):
        self.agent = FrontendGeneratorAgent()

    def test_typescript_tag_with_react(self):
        """Real React component with 'typescript' language tag."""
        raw = _load("frontend_react_typescript.md")
        result = self.agent.parse_output(raw)

        assert result["component_count"] >= 1
        assert any("ProfileCard" in c for c in result["components"])
        assert len(result["styles"]) >= 1

    def test_js_tag_with_vue_component(self):
        """Vue component using 'js' tag — old parser would miss this entirely."""
        raw = _load("frontend_vue_js_tag.md")
        result = self.agent.parse_output(raw)

        assert result["component_count"] >= 1
        assert any("NotificationToast" in c for c in result["components"])

    def test_scss_style_extraction(self):
        """SCSS blocks should be captured as styles."""
        raw = _load("frontend_vue_js_tag.md")
        result = self.agent.parse_output(raw)

        assert len(result["styles"]) >= 1
        assert any(".toast" in s for s in result["styles"])

    def test_no_language_tag_with_react_signals(self):
        """Code block has no language tag but contains React imports/hooks."""
        raw = _load("frontend_no_lang_tag.md")
        result = self.agent.parse_output(raw)

        assert result["component_count"] >= 1
        assert any("SearchBar" in c for c in result["components"])

    def test_pure_prose_returns_warning(self):
        """If LLM returns only text, parser should not silently succeed."""
        raw = "You should use React with Tailwind. Here's the general approach..."
        result = self.agent.parse_output(raw)

        assert result["component_count"] == 0
        assert "warning" in result
        assert "raw_output" in result

    def test_html_block_not_mistaken_for_component(self):
        """Plain HTML block without React/Vue signals should not be extracted."""
        raw = (
            "```html\n"
            "<div><p>Hello world</p></div>\n"
            "```"
        )
        result = self.agent.parse_output(raw)

        assert result["component_count"] == 0


# ── DevOpsAgent ──────────────────────────────────────────────────────────────


class TestDevOpsAgentRealistic:
    def setup_method(self):
        self.agent = DevOpsAgent()

    def test_github_actions_full_stack(self):
        """Real GPT-4o response with Dockerfile + compose + GH Actions + env."""
        raw = _load("devops_github_actions.md")
        result = self.agent.parse_output(raw)

        assert "Dockerfile" in result["files"]
        assert "docker-compose.yml" in result["files"]
        assert ".github/workflows/ci.yml" in result["files"]
        assert result["file_count"] >= 3

    def test_dockerfile_content_is_valid(self):
        """Dockerfile content should include FROM and not be a YAML block."""
        raw = _load("devops_github_actions.md")
        result = self.agent.parse_output(raw)

        dockerfile = result["files"].get("Dockerfile", "")
        assert "FROM" in dockerfile
        assert "EXPOSE" in dockerfile

    def test_gitlab_ci_detection(self):
        """YAML with stages: + script: should be classified as GitLab CI."""
        raw = _load("devops_gitlab_ci.md")
        result = self.agent.parse_output(raw)

        assert ".gitlab-ci.yml" in result["files"]
        assert "Dockerfile" in result["files"]

    def test_kubernetes_manifests(self):
        """YAML blocks with apiVersion + kind should map to k8s/ directory."""
        raw = _load("devops_kubernetes.md")
        result = self.agent.parse_output(raw)

        k8s_files = [f for f in result["files"] if f.startswith("k8s/")]
        assert len(k8s_files) >= 1
        assert any("deployment" in f for f in k8s_files)

    def test_no_yaml_blocks_returns_warning(self):
        """Response with no fenced code blocks should warn, not silently empty."""
        raw = _load("devops_no_yaml_blocks.md")
        result = self.agent.parse_output(raw)

        assert result["file_count"] == 0
        assert "warning" in result
        assert "raw_output" in result

    def test_compose_not_stolen_by_ci(self):
        """docker-compose and CI blocks should not be conflated."""
        raw = _load("devops_github_actions.md")
        result = self.agent.parse_output(raw)

        compose = result["files"].get("docker-compose.yml", "")
        ci = result["files"].get(".github/workflows/ci.yml", "")

        assert "services:" in compose
        assert "jobs:" in ci
        assert "jobs:" not in compose

    def test_env_block_extraction(self):
        """Blocks with 'env' language tag should be captured."""
        raw = _load("devops_github_actions.md")
        result = self.agent.parse_output(raw)

        assert ".env.example" in result["files"]
        assert "DATABASE_URL" in result["files"][".env.example"]


# ── TestingAgent ─────────────────────────────────────────────────────────────


class TestTestingAgentRealistic:
    def setup_method(self):
        self.agent = TestingAgent()

    def test_jest_tests_with_js_tag(self):
        """Jest tests using 'js' language tag — parser should still extract."""
        raw = _load("testing_agent_jest.md")
        result = self.agent.parse_output(raw)

        assert result.get("test_code") is not None
        assert result["test_count"] >= 1
        assert result["language"] == "js"

    def test_prose_heavy_response(self):
        """Real output with extensive explanation before the code block."""
        raw = _load("testing_agent_prose_heavy.md")
        result = self.agent.parse_output(raw)

        assert result.get("test_code") is not None
        assert result["test_count"] >= 3
        assert "test_create_order_with_valid_items" in result["test_names"]

    def test_no_code_block_returns_error(self):
        """Pure prose with no fenced code should return error, not crash."""
        raw = "You should write tests for the login flow using pytest."
        result = self.agent.parse_output(raw)

        assert "error" in result
        assert "raw_output" in result

    def test_multiple_blocks_takes_first(self):
        """If LLM outputs test code then example usage, take the test code."""
        raw = (
            "```python\n"
            "def test_add():\n"
            "    assert 1 + 1 == 2\n"
            "```\n\n"
            "Example usage:\n\n"
            "```python\n"
            "print(add(1, 1))\n"
            "```"
        )
        result = self.agent.parse_output(raw)

        assert "test_add" in result["test_names"]
        assert result["test_count"] == 1
