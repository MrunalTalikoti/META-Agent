import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict

import openai
import anthropic
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.utils.logger import logger
from app.utils.retry import async_retry


# ── Response Schema ───────────────────────────────────────────────────────────

class LLMResponse:
    def __init__(
        self,
        content: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        provider: str,
    ):
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.model = model
        self.provider = provider

    def estimated_cost_usd(self) -> float:
        rates = {
            "gpt-4o":                        {"in": 0.0025, "out": 0.010},
            "gpt-4o-mini":                   {"in": 0.00015, "out": 0.0006},
            "gpt-4-turbo-preview":           {"in": 0.01,   "out": 0.03},
            "claude-3-5-sonnet-20241022":    {"in": 0.003,  "out": 0.015},
            "claude-3-5-haiku-20241022":     {"in": 0.0008, "out": 0.004},
            "mock":                          {"in": 0.0,    "out": 0.0},
        }
        r = rates.get(self.model, {"in": 0.01, "out": 0.03})
        return (self.prompt_tokens / 1000 * r["in"]) + (self.completion_tokens / 1000 * r["out"])


# ── Abstract Provider ─────────────────────────────────────────────────────────

class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        pass


# ── Mock Provider ─────────────────────────────────────────────────────────────

class MockProvider(LLMProvider):
    MOCK_RESPONSES = {
        "code": '''```python
def process_user_request(user_id: int, request: str) -> dict:
    """Process a user request and return structured result."""
    if not request or not request.strip():
        raise ValueError("Request cannot be empty")
    return {"user_id": user_id, "request": request, "status": "processed", "data": {}}
```

This function validates input, processes the request, and returns a structured dictionary.''',

        "api": '{"endpoints": [{"path": "/api/v1/users", "method": "POST", "description": "Create user", "auth_required": false, "request_body": {"email": "string", "password": "string"}, "response_200": {"id": "integer", "email": "string"}, "error_responses": [{"code": 400, "description": "Bad request"}, {"code": 409, "description": "Email already exists"}], "rate_limit": "100 requests per minute"}], "authentication": "JWT Bearer Token", "base_url": "/api/v1", "notes": "All endpoints require HTTPS"}',

        "database": '{"tables": [{"name": "users", "description": "Stores user accounts", "columns": [{"name": "id", "type": "SERIAL", "primary_key": true, "nullable": false}, {"name": "email", "type": "VARCHAR(255)", "unique": true, "nullable": false}, {"name": "created_at", "type": "TIMESTAMP", "nullable": true, "default": "NOW()"}], "indexes": [{"name": "idx_users_email", "columns": ["email"], "unique": true}]}], "relationships": [], "database_type": "PostgreSQL", "notes": "Standard user table"}',

        "default": "I have analyzed your request and generated a comprehensive response following best practices.",

        "requirements": '{"status": "needs_clarification", "question": "What backend framework would you like to use? (1) Python/FastAPI, (2) Python/Django, (3) Node.js/Express, (4) Go/Gin", "gathered_so_far": {"functional": "TBD", "tech_stack": "", "architecture": "", "scale": "", "deliverables": "", "constraints": ""}}',
    }

    async def generate(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        await asyncio.sleep(0.1)

        system_content = next((m.get("content", "") for m in messages if m["role"] == "system"), "")
        last_message = messages[-1].get("content", "").lower()

        is_decomposer = "break down" in system_content.lower() or "available agents" in system_content.lower()
        is_gatherer = "requirements analyst" in system_content.lower()

        if is_decomposer:
            content = '''[
    {"id": 1, "description": "Design REST API endpoints", "agent": "api_designer", "dependencies": [], "inputs": {}},
    {"id": 2, "description": "Design database schema", "agent": "database_schema", "dependencies": [], "inputs": {}},
    {"id": 3, "description": "Generate implementation code", "agent": "code_generator", "dependencies": [1, 2], "inputs": {}},
    {"id": 4, "description": "Write unit and integration tests", "agent": "testing_agent", "dependencies": [3], "inputs": {}},
    {"id": 5, "description": "Create README and API documentation", "agent": "documentation_agent", "dependencies": [3], "inputs": {}}
]'''
        elif is_gatherer:
            content = self.MOCK_RESPONSES["requirements"]
        elif "api" in last_message or "endpoint" in last_message:
            content = self.MOCK_RESPONSES["api"]
        elif "database" in last_message or "schema" in last_message or "table" in last_message:
            content = self.MOCK_RESPONSES["database"]
        else:
            content = self.MOCK_RESPONSES["code"]

        fake_prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
        fake_completion_tokens = len(content) // 4

        return LLMResponse(
            content=content,
            prompt_tokens=fake_prompt_tokens,
            completion_tokens=fake_completion_tokens,
            model="mock",
            provider="mock",
        )


# ── OpenAI Provider ───────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o"):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model

    async def generate(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            model=self.model,
            provider="openai",
        )


# ── OpenAI Mini Provider (cheap fallback) ─────────────────────────────────────

class OpenAIMiniProvider(OpenAIProvider):
    def __init__(self):
        super().__init__(model="gpt-4o-mini")


# ── Anthropic Provider ────────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-3-5-sonnet-20241022"

    async def generate(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        system_msg = next(
            (m["content"] for m in messages if m["role"] == "system"),
            "You are a helpful AI assistant."
        )
        user_messages = [
            {"role": m["role"], "content": [{"type": "text", "text": m["content"]}]}
            for m in messages if m["role"] != "system"
        ]
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_msg,
            messages=user_messages,
        )
        return LLMResponse(
            content=response.content[0].text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            model=self.model,
            provider="anthropic",
        )


# ── Factory ───────────────────────────────────────────────────────────────────

class LLMService:
    """
    Auto-selects provider:
      - ANTHROPIC_API_KEY set  → AnthropicProvider (Claude)
      - OPENAI_API_KEY set     → OpenAIProvider (GPT-4o)
      - Neither                → MockProvider (free, for dev)

    Override with force_provider: "openai", "openai_mini", "anthropic", "mock"
    """

    def __init__(self, force_mock: bool = False, force_provider: str = None):
        if force_mock or force_provider == "mock":
            self._provider = MockProvider()
            logger.info("LLM: Using MOCK provider")
        elif force_provider == "openai_mini":
            self._provider = OpenAIMiniProvider()
            logger.info("LLM: Using OpenAI GPT-4o-mini")
        elif force_provider == "openai":
            self._provider = OpenAIProvider()
            logger.info("LLM: Using OpenAI GPT-4o")
        elif force_provider == "anthropic":
            self._provider = AnthropicProvider()
            logger.info("LLM: Using Anthropic Claude")
        elif settings.openai_api_key and settings.openai_api_key not in ("", "your_openai_key_here"):
            self._provider = OpenAIProvider()
            logger.info("LLM: Using OpenAI GPT-4o")
        elif settings.anthropic_api_key and settings.anthropic_api_key not in ("", "your_anthropic_api_key_here"):
            self._provider = AnthropicProvider()
            logger.info("LLM: Using Anthropic Claude")
        else:
            self._provider = MockProvider()
            logger.info("LLM: Using MOCK provider (no API keys set)")

    @async_retry(max_attempts=3, initial_delay=2.0)
    async def generate(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        start = time.time()
        response = await self._provider.generate(messages, temperature, max_tokens)
        elapsed_ms = int((time.time() - start) * 1000)

        logger.debug(
            f"LLM call | provider={response.provider} | model={response.model} | "
            f"tokens={response.total_tokens} | cost=${response.estimated_cost_usd():.4f} | "
            f"time={elapsed_ms}ms"
        )
        return response