import re
from app.agents.base_agent import BaseAgent


class TestingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="testing_agent")

    def get_system_prompt(self) -> str:
        return """You are a senior QA engineer writing comprehensive automated tests.

Your responsibilities:
1. Write unit tests covering happy paths, edge cases, and error scenarios
2. Use appropriate framework (pytest for Python, Jest for JS/TS)
3. Follow Arrange-Act-Assert pattern
4. Mock external dependencies (APIs, databases, file system)
5. Aim for >80% code coverage
6. Write descriptive test names: test_<what>_<condition>_<expected>

OUTPUT FORMAT (wrap ALL test code in a single fenced block):
```python
import pytest
# test code here
```

Include tests for:
- Valid inputs (happy path)
- Invalid/boundary inputs (empty, null, out of range)
- Error handling and exception messages
- Integration points (mocked)"""

    def parse_output(self, raw_content: str) -> dict:
        # Fixed regex — was r'(\w+)?\n(.*?)' which never matched
        pattern = r"```(\w+)?\n(.*?)```"
        match = re.search(pattern, raw_content, re.DOTALL)

        if match:
            language = match.group(1) or "python"
            test_code = match.group(2).strip()
            test_count = len(re.findall(r"(def test_|it\(|test\(|@Test)", test_code))
            test_names = re.findall(r"def (test_\w+)", test_code)

            return {
                "test_code": test_code,
                "language": language,
                "test_count": test_count,
                "test_names": test_names,
                "line_count": len(test_code.splitlines()),
            }

        return {"error": "No test code found", "raw_output": raw_content}