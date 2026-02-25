import re
from app.agents.base_agent import BaseAgent


class CodeGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="code_generator")

    def get_system_prompt(self) -> str:
        return """You are a senior software engineer writing production-quality code.

RULES:
1. Always wrap code in triple backticks with the language name: ```python ... ```
2. Include error handling for edge cases
3. Add type hints to all functions
4. Add a brief docstring to each function/class
5. After the code block, write 2-3 sentences explaining key design decisions

OUTPUT FORMAT (follow exactly):
```language
# Your code here
```

Brief explanation of what the code does and why you made specific design choices."""

    def parse_output(self, raw_content: str) -> dict:
        """Extract code block and explanation from LLM response."""
        # Find the first code block
        pattern = r"```(\w+)?\n(.*?)```"
        match = re.search(pattern, raw_content, re.DOTALL)

        if match:
            language = match.group(1) or "python"
            code = match.group(2).strip()

            # Everything after the code block is the explanation
            after_block = raw_content[match.end():].strip()

            return {
                "code": code,
                "language": language,
                "explanation": after_block,
                "line_count": len(code.splitlines()),
            }

        # No code block found — return raw
        return {"raw_output": raw_content, "code": None}