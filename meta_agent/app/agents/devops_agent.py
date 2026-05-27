import re
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.utils.logger import logger

_BLOCK_RE = re.compile(
    r'```(\w+)?\s*\n(.*?)```',
    re.DOTALL,
)


def _classify_yaml(content: str) -> Optional[str]:
    """Map a YAML block to a filename based on its content."""
    lower = content.lower()

    # GitHub Actions — "jobs:" is the defining key
    if "jobs:" in lower and ("on:" in lower or "workflow" in lower or "runs-on:" in lower):
        return ".github/workflows/ci.yml"

    # GitLab CI
    if "stages:" in lower and ("script:" in lower or "image:" in lower):
        return ".gitlab-ci.yml"

    # Docker Compose
    if "services:" in lower and ("image:" in lower or "build:" in lower or "ports:" in lower):
        return "docker-compose.yml"

    # Kubernetes manifests
    if "apiversion:" in lower and "kind:" in lower:
        kind = re.search(r'kind:\s*(\w+)', content, re.IGNORECASE)
        suffix = kind.group(1).lower() if kind else "resource"
        return f"k8s/{suffix}.yml"

    return None


class DevOpsAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="devops")

    def get_system_prompt(self) -> str:
        return """You are a DevOps engineer creating deployment configurations.

Generate the following, each in its own fenced code block with the correct
language tag (`dockerfile`, `yaml`, `env`, etc.):

1. Dockerfile (multi-stage builds)
2. docker-compose.yml
3. CI/CD config (GitHub Actions preferred)
4. Kubernetes manifests (if applicable)
5. Environment template (.env.example)

Best practices:
- Minimize image size
- Non-root user
- Health checks
- Secrets management
- Caching layers

OUTPUT FORMAT: One fenced code block per file. Start each block with a
comment naming the file, e.g. `# docker-compose.yml` or `# Dockerfile`."""

    def parse_output(self, raw_content: str) -> dict:
        files: dict[str, str] = {}
        unclassified: list[str] = []

        for lang, body in _BLOCK_RE.findall(raw_content):
            body = body.strip()
            if not body:
                continue
            lang = (lang or "").lower()

            if lang == "dockerfile" or body.lstrip().upper().startswith("FROM "):
                files.setdefault("Dockerfile", body)
                continue

            if lang in ("env", "dotenv", "sh") and "=" in body.split("\n")[0]:
                files.setdefault(".env.example", body)
                continue

            if lang in ("yaml", "yml", ""):
                filename = _classify_yaml(body)
                if filename:
                    files.setdefault(filename, body)
                    continue

            unclassified.append(body[:120])

        if unclassified:
            logger.warning(
                "DevOps agent: %d block(s) could not be classified: %s",
                len(unclassified),
                [b[:60] for b in unclassified],
            )

        if not files:
            logger.warning("DevOps agent: no files extracted from LLM output")
            return {
                "files": {},
                "file_count": 0,
                "raw_output": raw_content,
                "warning": "Could not extract any configuration files from LLM response",
            }

        return {
            "files": files,
            "file_count": len(files),
        }
