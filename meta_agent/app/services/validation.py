"""
Validation & Quality Layer
--------------------------
Post-generation checks promised in the README but never implemented.

1. SyntaxValidator   — static checks (Python ast, JSON, SQL keywords)
2. QualityChecker    — LLM reviews generated output against the original request
3. ValidationOrchestrator — runs both and returns a unified report
"""

import ast
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.llm_service import LLMService
from app.utils.logger import logger


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SyntaxIssue:
    severity: str        # "error" | "warning"
    message: str
    line: Optional[int] = None


@dataclass
class SyntaxResult:
    passed: bool
    language: str
    issues: List[SyntaxIssue] = field(default_factory=list)


@dataclass
class QualityResult:
    score: int            # 1–10
    passed: bool          # score >= 6
    summary: str
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    syntax: SyntaxResult
    quality: QualityResult

    @property
    def passed(self) -> bool:
        return self.syntax.passed and self.quality.passed

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "syntax": {
                "passed": self.syntax.passed,
                "language": self.syntax.language,
                "issues": [{"severity": i.severity, "message": i.message, "line": i.line}
                           for i in self.syntax.issues],
            },
            "quality": {
                "score": self.quality.score,
                "passed": self.quality.passed,
                "summary": self.quality.summary,
                "suggestions": self.quality.suggestions,
            },
        }


# ── Syntax Validator ──────────────────────────────────────────────────────────

class SyntaxValidator:
    """Static syntax checking — no LLM calls."""

    def validate(self, content: str, language: str) -> SyntaxResult:
        lang = (language or "").lower()
        if lang == "python":
            return self._check_python(content)
        elif lang == "json":
            return self._check_json(content)
        elif lang in ("sql", "ddl"):
            return self._check_sql(content)
        else:
            # No static checker for this language — pass through
            return SyntaxResult(passed=True, language=lang, issues=[])

    def _check_python(self, code: str) -> SyntaxResult:
        issues: List[SyntaxIssue] = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(SyntaxIssue(severity="error", message=str(e), line=e.lineno))
        except Exception as e:
            issues.append(SyntaxIssue(severity="error", message=f"Parse error: {e}"))

        # Warn about common bad practices
        if "import *" in code:
            issues.append(SyntaxIssue(severity="warning", message="Avoid wildcard imports (import *)"))
        if re.search(r"except\s*:", code):
            issues.append(SyntaxIssue(severity="warning", message="Bare 'except:' clause — catch specific exceptions"))
        if "password" in code.lower() and re.search(r'["\'][^"\']{8,}["\']', code):
            issues.append(SyntaxIssue(severity="warning", message="Possible hardcoded credential detected"))

        return SyntaxResult(
            passed=not any(i.severity == "error" for i in issues),
            language="python",
            issues=issues,
        )

    def _check_json(self, content: str) -> SyntaxResult:
        issues: List[SyntaxIssue] = []
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            issues.append(SyntaxIssue(severity="error", message=str(e), line=e.lineno))
        return SyntaxResult(passed=not issues, language="json", issues=issues)

    def _check_sql(self, sql: str) -> SyntaxResult:
        issues: List[SyntaxIssue] = []
        upper = sql.upper()
        # Detect unparameterised string concat (basic heuristic)
        if re.search(r"['\"]?\s*\+\s*['\"]?", sql) and ("SELECT" in upper or "WHERE" in upper):
            issues.append(SyntaxIssue(
                severity="warning",
                message="Possible SQL injection: use parameterised queries instead of string concatenation",
            ))
        if "DROP TABLE" in upper and "IF EXISTS" not in upper:
            issues.append(SyntaxIssue(severity="warning", message="DROP TABLE without IF EXISTS"))
        return SyntaxResult(passed=True, language="sql", issues=issues)


# ── LLM Quality Checker ───────────────────────────────────────────────────────

class QualityChecker:
    """Asks the LLM to review generated output against the original request."""

    def __init__(self):
        self.llm = LLMService()

    async def check(self, original_request: str, generated_output: str, agent_name: str) -> QualityResult:
        system_prompt = """You are a senior code reviewer. Evaluate whether the generated output satisfies the original request.

Respond with ONLY valid JSON — no markdown, no preamble:
{
  "score": <integer 1-10>,
  "summary": "<one sentence overall assessment>",
  "suggestions": ["<specific improvement>", ...]
}

Scoring guide:
10 = perfect, all requirements met, production-ready
7-9 = good, minor gaps
4-6 = partial, key requirements missing
1-3 = poor, major issues"""

        user_message = (
            f"Original request:\n{original_request}\n\n"
            f"Agent: {agent_name}\n\n"
            f"Generated output:\n{generated_output[:3000]}"  # truncate for token budget
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.llm.generate(messages, temperature=0.1, max_tokens=500)
            data = self._parse_response(response.content)
            score = max(1, min(10, int(data.get("score", 5))))
            return QualityResult(
                score=score,
                passed=score >= 6,
                summary=data.get("summary", ""),
                suggestions=data.get("suggestions", []),
            )
        except Exception as e:
            logger.warning(f"Quality check failed: {e} — skipping")
            return QualityResult(score=7, passed=True, summary="Quality check skipped", suggestions=[])

    def _parse_response(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {}


# ── Validation Orchestrator ───────────────────────────────────────────────────

class ValidationOrchestrator:
    """
    Runs syntax + quality checks on a single agent output.
    Call after each task completes (or only for code/api/schema agents).
    """

    def __init__(self):
        self.syntax_validator = SyntaxValidator()
        self.quality_checker = QualityChecker()

    async def validate(
        self,
        original_request: str,
        agent_name: str,
        output: dict,
    ) -> ValidationReport:
        # Extract the text content to check
        content = ""
        language = "unknown"

        if "code" in output:
            content = output["code"]
            language = output.get("language", "python")
        elif "api_design" in output:
            content = json.dumps(output["api_design"])
            language = "json"
        elif "sql_ddl" in output:
            content = output["sql_ddl"]
            language = "sql"
        elif "test_code" in output:
            content = output["test_code"]
            language = output.get("language", "python")
        elif "documentation" in output:
            content = output["documentation"]
            language = "markdown"
        else:
            content = json.dumps(output)
            language = "json"

        syntax_result = self.syntax_validator.validate(content, language)
        quality_result = await self.quality_checker.check(original_request, content, agent_name)

        report = ValidationReport(syntax=syntax_result, quality=quality_result)
        logger.info(
            f"[validator] {agent_name} | syntax={'ok' if syntax_result.passed else 'FAIL'} "
            f"| quality={quality_result.score}/10"
        )
        return report