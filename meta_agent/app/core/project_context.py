"""
Per-execution shared context that accumulates as agents complete.

Each agent gets a read-only snapshot of what prior agents produced,
regardless of whether the decomposer wired explicit dependencies.
Summaries are compact interface descriptions, not full outputs.
"""

import json
from typing import Dict, Optional

_PER_AGENT_LIMIT = 800
_TOTAL_LIMIT = 6000


def _summarize(agent_name: str, output: dict) -> Optional[str]:
    """Extract the contract-relevant fragment from an agent's output."""
    if agent_name == "api_designer":
        design = output.get("api_design", output)
        endpoints = design.get("endpoints", [])
        if endpoints:
            lines = []
            for ep in endpoints[:12]:
                line = f"  {ep.get('method', '?')} {ep.get('path', '?')}"
                resp = ep.get("response") or ep.get("response_body")
                if resp:
                    line += f" → {json.dumps(resp)}"
                lines.append(line)
            return "Endpoints:\n" + "\n".join(lines)
        return json.dumps(design, indent=1)[:_PER_AGENT_LIMIT]

    if agent_name == "database_schema":
        sql = output.get("sql_ddl", "")
        if sql:
            return sql[:_PER_AGENT_LIMIT]
        schema = output.get("schema", {})
        if schema:
            return json.dumps(schema, indent=1)[:_PER_AGENT_LIMIT]
        return None

    if agent_name == "code_generator":
        code = output.get("code") or output.get("raw_output", "")
        if not code:
            return None
        lines = code.split("\n")
        # Keep imports, class/function signatures, and route decorators
        kept = [
            ln for ln in lines
            if ln.strip().startswith(("import ", "from ", "class ", "def ",
                                      "@app.", "@router.", "async def "))
        ]
        if kept:
            return "\n".join(kept[:40])
        return code[:_PER_AGENT_LIMIT]

    if agent_name == "frontend_generator":
        components = output.get("components", [])
        if not components:
            return None
        snippets = []
        for comp in components[:4]:
            lines = comp.split("\n")
            kept = [
                ln for ln in lines
                if ln.strip().startswith(("import ", "export ", "interface ",
                                          "type ", "fetch(", "const ", "function "))
            ]
            snippets.append("\n".join(kept[:15]) if kept else comp[:200])
        return "\n---\n".join(snippets)

    if agent_name == "testing_agent":
        code = output.get("test_code") or output.get("raw_output", "")
        if not code:
            return None
        lines = code.split("\n")
        kept = [
            ln for ln in lines
            if ln.strip().startswith(("def test_", "it(", "describe(", "class Test"))
        ]
        return "\n".join(kept[:20]) if kept else code[:_PER_AGENT_LIMIT]

    if agent_name == "devops":
        files = output.get("files", {})
        if files:
            return "Files: " + ", ".join(files.keys())
        return None

    if agent_name in ("security_auditor", "performance_optimizer"):
        return json.dumps(output, indent=1)[:_PER_AGENT_LIMIT]

    if agent_name == "documentation_agent":
        doc = output.get("documentation") or output.get("raw_output", "")
        if doc:
            return doc[:_PER_AGENT_LIMIT]
        return None

    return None


class ProjectContext:
    """Accumulates compact agent summaries during a single orchestrator run."""

    def __init__(self) -> None:
        self._entries: Dict[str, str] = {}

    def add(self, agent_name: str, output: dict) -> None:
        summary = _summarize(agent_name, output)
        if summary:
            self._entries[agent_name] = summary[:_PER_AGENT_LIMIT]

    def snapshot(self) -> Optional[str]:
        """Returns a formatted string of all accumulated context, or None if empty."""
        if not self._entries:
            return None
        sections = []
        budget = _TOTAL_LIMIT
        for agent, summary in self._entries.items():
            section = f"── {agent} ──\n{summary}"
            if len(section) > budget:
                section = section[:budget] + "\n... (truncated)"
                sections.append(section)
                break
            sections.append(section)
            budget -= len(section)
        return "\n\n".join(sections)
