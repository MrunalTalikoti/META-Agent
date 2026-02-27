from app.agents.base_agent import BaseAgent


class DocumentationAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="documentation_agent")

    def get_system_prompt(self) -> str:
        return """You are a technical writer creating clear, comprehensive documentation.

        Your responsibilities:
        1. Write README files, API documentation, and user guides
        2. Use proper markdown formatting
        3. Include code examples where relevant
        4. Add troubleshooting sections
        5. Keep language clear and concise

        OUTPUT FORMAT (markdown):

        # Project/Feature Name

        Brief one-sentence description.

        ## Overview
        What this does and why it exists.

        ## Installation/Setup
        Step-by-step setup instructions with code blocks.

        ## Usage
        ### Basic Example
        ```language
        # Example code
        Advanced Features
        More complex examples.

        API Reference (if applicable)
        Document functions, classes, endpoints.

        Configuration
        Environment variables, config files, etc.

        Troubleshooting
        Common issues and solutions.

        Contributing (if open source)
        How to contribute.

        Guidelines:

        Use clear headings (##, ###)

        Code blocks with language specification

        Bullet points for lists

        Bold for important terms

        Links to related documentation

        Keep paragraphs short (2-3 sentences)"""

    def parse_output(self, raw_content: str) -> dict:
        """Return formatted documentation"""
        # Count sections
        import re
        headings = re.findall(r'^#+\s+(.+)$', raw_content, re.MULTILINE)

        # Count code blocks
        code_blocks = re.findall(r'```', raw_content)
        code_block_count = len(code_blocks) // 2
        
        return {
            "documentation": raw_content,
            "format": "markdown",
            "section_count": len(headings),
            "sections": headings,
            "code_examples": code_block_count,
            "word_count": len(raw_content.split()),
        }