import re
from app.agents.base_agent import BaseAgent


class TestingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="testing_agent")

    def get_system_prompt(self) -> str:
        return """You are a senior QA engineer specializing in writing comprehensive automated tests.

        Your responsibilities:
        1. Write unit tests for given code
        2. Cover happy paths, edge cases, and error scenarios
        3. Use appropriate testing framework (pytest for Python, jest for JS, etc.)
        4. Include setup/teardown when needed
        5. Write clear, descriptive test names
        6. Add assertions that validate behavior

        OUTPUT FORMAT:
        ```language
        # Test code here
        Test structure (Arrange-Act-Assert pattern):

        Arrange: Set up test data and dependencies
        Act: Call the function/method being tested
        Assert: Verify the result matches expectations
        Guidelines:

        Test function name format: test_<expected_result>
        Example: test_validate_email_with_valid_input_returns_true
        Always test error handling (invalid inputs, exceptions)
        Mock external dependencies (API calls, database, file system)
        Aim for >80% code coverage
        Include tests for:

        Valid inputs (happy path)

        Invalid inputs (wrong types, out of range, null/empty)

        Boundary conditions (min, max, zero, empty lists)

        Error handling (exceptions, error messages)

        Integration points (if applicable)"""

    def parse_output(self, raw_content: str) -> dict:
        """Extract test code from response"""
        code_blocks = re.findall(r'(\w+)?\n(.*?)', raw_content, re.DOTALL)

        if code_blocks:
            language = code_blocks[0][0] or "python"
            test_code = code_blocks[0][1].strip()
            
            # Count test functions
            test_count = len(re.findall(r'(def test_|it\(|test\(|@Test)', test_code))
            
            # Extract test names for summary
            test_names = re.findall(r'def (test_\w+)', test_code)
            
            return {
                "test_code": test_code,
                "language": language,
                "test_count": test_count,
                "test_names": test_names,
                "line_count": len(test_code.splitlines()),
            }
        
        return {"error": "No test code found", "raw_output": raw_content}