from app.agents.base_agent import BaseAgent

class SecurityAuditorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="security_auditor")
    
    def get_system_prompt(self) -> str:
        return """You are a security expert auditing code for vulnerabilities.

Check for:
1. SQL injection (use parameterized queries?)
2. XSS vulnerabilities (input sanitization?)
3. Authentication flaws (weak passwords, session management)
4. Secrets in code (hardcoded API keys, passwords)
5. Dependency vulnerabilities (outdated packages)
6. CSRF protection
7. Rate limiting
8. Input validation

OUTPUT JSON:
{
  "severity": "critical|high|medium|low|none",
  "issues": [
    {
      "type": "SQL Injection",
      "location": "file.py:line 42",
      "description": "...",
      "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))"
    }
  ],
  "recommendations": [...]
}"""

    def parse_output(self, raw_content: str) -> dict:
        import json
        import re
        
        try:
            return json.loads(raw_content)
        except:
            match = re.search(r'```json\n(.*?)```', raw_content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        return {"severity": "unknown", "issues": [], "raw": raw_content}