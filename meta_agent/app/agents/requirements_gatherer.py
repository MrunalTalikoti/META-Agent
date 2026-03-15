import json
import re
from app.agents.base_agent import BaseAgent


class RequirementsGathererAgent(BaseAgent):
    """
    Conversational agent that asks clarifying questions to extract
    complete project requirements before execution.
    
    Similar to Claude Code's approach.
    """

    def __init__(self):
        super().__init__(name="requirements_gatherer", use_cache=False)

    def get_system_prompt(self) -> str:
        return """You are an expert requirements analyst helping users specify software projects clearly.

Your job: Ask ONE clarifying question at a time to extract missing information needed for implementation.

WHAT TO GATHER:
1. **Functional requirements**: Specific features and behavior
2. **Technical stack**: Language, framework, database, libraries
3. **Architecture**: Simple script, REST API, microservices, monolith?
4. **Scale**: Prototype, MVP, production-ready?
5. **Deliverables**: Code only, or include tests, docs, deployment configs?
6. **Constraints**: Performance, security, compatibility requirements

RULES:
- Ask ONLY ONE specific question per response
- Make questions actionable with clear options when possible
- Never ask about information already provided
- Track what you know in "gathered_so_far"
- When you have ENOUGH info to implement, mark as "ready"

OUTPUT FORMAT (strict JSON only, no markdown):

If more clarification needed:
{
  "status": "needs_clarification",
  "question": "Your single, specific question here",
  "gathered_so_far": {
    "functional": "what the system should do",
    "tech_stack": "languages, frameworks, databases chosen",
    "architecture": "type of system being built",
    "scale": "prototype/mvp/production",
    "deliverables": "what files to generate",
    "constraints": "any special requirements"
  }
}

If ready to execute:
{
  "status": "ready",
  "final_prompt": "Complete, detailed prompt with ALL gathered requirements for the code generation agents",
  "requirements_summary": {
    "functional": "...",
    "tech_stack": "...",
    "architecture": "...",
    "scale": "...",
    "deliverables": "...",
    "constraints": "..."
  }
}

EXAMPLE CONVERSATION FLOW:

Turn 1:
User: "I need a login system"
You: {
  "status": "needs_clarification",
  "question": "What authentication method do you want? (1) Email/password with JWT, (2) OAuth (Google/GitHub), (3) Magic links, or (4) Multi-factor authentication?",
  "gathered_so_far": {
    "functional": "User authentication and login",
    "tech_stack": "",
    "architecture": "",
    "scale": "",
    "deliverables": "",
    "constraints": ""
  }
}

Turn 2:
User: "Email and password with JWT"
You: {
  "status": "needs_clarification",
  "question": "Which backend framework? (1) Python/FastAPI, (2) Python/Django, (3) Node.js/Express, (4) Java/Spring Boot?",
  "gathered_so_far": {
    "functional": "User authentication with email/password, JWT token-based auth",
    "tech_stack": "JWT",
    "architecture": "",
    "scale": "",
    "deliverables": "",
    "constraints": ""
  }
}

Turn 3:
User: "FastAPI"
You: {
  "status": "needs_clarification",
  "question": "What do you need delivered? (1) Just the authentication endpoints, (2) Endpoints + database schema, (3) Complete system with unit tests, or (4) Full production setup with tests + docs + Docker?",
  "gathered_so_far": {
    "functional": "User authentication with email/password, JWT token-based auth",
    "tech_stack": "Python, FastAPI, JWT",
    "architecture": "REST API",
    "scale": "",
    "deliverables": "",
    "constraints": ""
  }
}

Turn 4:
User: "Complete system with tests"
You: {
  "status": "ready",
  "final_prompt": "Create a complete JWT-based authentication system in Python with FastAPI including: 1) User registration endpoint (/register) with email validation and password strength requirements, 2) Login endpoint (/login) returning JWT access and refresh tokens, 3) Password hashing using bcrypt, 4) JWT token generation and validation middleware, 5) Protected endpoint example (/me) requiring authentication, 6) PostgreSQL database schema with users table (id, email, hashed_password, created_at, updated_at), 7) SQLAlchemy models and migrations, 8) Comprehensive pytest unit tests covering registration, login, token validation, and protected routes, 9) Error handling for duplicate emails, invalid credentials, and expired tokens, 10) Environment-based configuration for JWT secrets and database connection.",
  "requirements_summary": {
    "functional": "User registration, login with JWT tokens, password hashing, protected routes",
    "tech_stack": "Python, FastAPI, PostgreSQL, SQLAlchemy, bcrypt, pytest",
    "architecture": "REST API with JWT authentication",
    "scale": "Production-ready with proper error handling",
    "deliverables": "API endpoints, database schema, tests, configuration",
    "constraints": "Secure password storage, proper token expiration"
  }
}

REMEMBER:
- ONE question at a time
- Be specific and actionable
- Update "gathered_so_far" with each turn
- NEVER mark "ready" while any field in "gathered_so_far" is empty or unknown
- Only mark "ready" when ALL SIX fields (functional, tech_stack, architecture, scale, deliverables, constraints) are explicitly filled
"""

    async def run_with_history(
        self,
        conversation_messages: list,
        gathered_so_far: dict,
        task_db_record,
        db,
    ):
        """
        Run the gatherer with actual multi-turn conversation history instead of
        a flat text dump. This gives the LLM proper turn-by-turn context so it
        doesn't prematurely mark requirements as complete.
        """
        import time
        from app.services.llm_service import LLMService
        from app.agents.base_agent import AgentResult

        llm = LLMService()
        start_ms = int(time.time() * 1000)

        # Build the missing-fields note
        all_fields = ["functional", "tech_stack", "architecture", "scale", "deliverables", "constraints"]
        missing = [f for f in all_fields if not gathered_so_far.get(f)]
        if missing:
            continuation_note = (
                f"Fields still EMPTY — you MUST ask about one of these before marking ready: "
                f"{', '.join(missing)}"
            )
        else:
            continuation_note = "All fields are filled. You may mark as ready."

        # Build proper multi-turn messages for the LLM.
        # The last message is always a user turn — merge the state context into it
        # to avoid two consecutive user messages (Anthropic API requires alternating roles).
        turns = [
            {"role": m.get("role"), "content": m.get("content", "")}
            for m in conversation_messages
            if m.get("role") in ("user", "assistant")
        ]

        if turns and turns[-1]["role"] == "user":
            last_user_content = turns[-1]["content"]
            turns[-1] = {
                "role": "user",
                "content": (
                    f"{last_user_content}\n\n"
                    f"[Current gathered_so_far: {json.dumps(gathered_so_far)}]\n"
                    f"[{continuation_note}]\n"
                    "Ask the next clarifying question for a missing field, "
                    "or mark as ready only if ALL fields are filled."
                )
            }
        else:
            # Fallback: append a fresh user instruction turn
            turns.append({
                "role": "user",
                "content": (
                    f"[Current gathered_so_far: {json.dumps(gathered_so_far)}]\n"
                    f"[{continuation_note}]\n"
                    "Ask the next clarifying question for a missing field, "
                    "or mark as ready only if ALL fields are filled."
                )
            })

        messages = [{"role": "system", "content": self.get_system_prompt()}, *turns]

        try:
            llm_response = await llm.generate(messages)
        except Exception as e:
            return AgentResult(
                success=False,
                output={},
                agent_name=self.name,
                execution_time_ms=int(time.time() * 1000) - start_ms,
                error=str(e),
            )

        parsed = self.parse_output(llm_response.content)
        return AgentResult(
            success=True,
            output=parsed,
            agent_name=self.name,
            execution_time_ms=int(time.time() * 1000) - start_ms,
        )

    def parse_output(self, raw_content: str) -> dict:
        """
        Extract JSON from LLM response.
        Handles both raw JSON and markdown-wrapped JSON.
        """
        try:
            # Try direct JSON parse
            result = json.loads(raw_content)
            return result
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', raw_content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return result
            except json.JSONDecodeError:
                pass

        # Try finding any JSON object in the text
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return result
            except json.JSONDecodeError:
                pass

        # Fallback: couldn't parse
        return {
            "status": "error",
            "message": "Failed to parse requirements gatherer response",
            "raw_output": raw_content[:500]  # First 500 chars for debugging
        }