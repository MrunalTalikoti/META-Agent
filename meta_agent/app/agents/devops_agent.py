from app.agents.base_agent import BaseAgent
import re

class DevOpsAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="devops")
    
    def get_system_prompt(self) -> str:
        return """You are a DevOps engineer creating deployment configurations.

Generate:
1. Dockerfile (multi-stage builds)
2. docker-compose.yml
3. CI/CD configs (GitHub Actions, GitLab CI)
4. Kubernetes manifests (if needed)
5. Environment templates

Best practices:
- Minimize image size
- Non-root user
- Health checks
- Secrets management
- Caching layers

OUTPUT: Separate code blocks for each file."""

    def parse_output(self, raw_content: str) -> dict:
        files = {}
        
        # Extract Dockerfile
        dockerfile = re.search(r'```dockerfile\n(.*?)```', raw_content, re.DOTALL | re.IGNORECASE)
        if dockerfile:
            files['Dockerfile'] = dockerfile.group(1).strip()
        
        # Extract docker-compose
        compose = re.search(r'```ya?ml\n(.*?)```', raw_content, re.DOTALL)
        if compose:
            files['docker-compose.yml'] = compose.group(1).strip()
        
        # Extract CI/CD
        github_actions = re.search(r'```(?:yaml|yml)\n# \.github.*?\n(.*?)```', raw_content, re.DOTALL)
        if github_actions:
            files['.github/workflows/ci.yml'] = github_actions.group(1).strip()
        
        return {
            "files": files,
            "file_count": len(files),
        }