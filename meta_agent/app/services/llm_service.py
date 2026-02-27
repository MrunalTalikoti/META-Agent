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
        """Rough cost in USD. Stored as microdollars in DB."""
        rates = {
            "gpt-4-turbo-preview": {"in": 0.01, "out": 0.03},
            "claude-3-5-sonnet-20241022": {"in": 0.003, "out": 0.015},
            "mock": {"in": 0.0, "out": 0.0},
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


# ── Mock Provider (use when no API keys) ─────────────────────────────────────

class MockProvider(LLMProvider):
    """
    Returns realistic-looking fake responses.
    Use this during development to avoid API costs.
    """

    MOCK_RESPONSES = {
        "code": '''```python
def process_user_request(user_id: int, request: str) -> dict:
    """
    Process a user request and return structured result.
    """
    if not request or not request.strip():
        raise ValueError("Request cannot be empty")
    
    result = {
        "user_id": user_id,
        "request": request,
        "status": "processed",
        "data": {}
    }
    return result
```

This function validates input, processes the request, and returns a structured dictionary.''',

        "api": '{"endpoints": [{"path": "/api/v1/users", "method": "POST", "description": "Create user", "auth_required": false}], "authentication": "JWT", "base_url": "/api/v1"}',

        "database": '{"tables": [{"name": "users", "columns": [{"name": "id", "type": "SERIAL", "primary_key": true}, {"name": "email", "type": "VARCHAR(255)", "unique": true}]}], "relationships": []}',

        "default": "I have analyzed your request and generated a comprehensive response following best practices."
    }

    async def generate(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        await asyncio.sleep(0.3)

        # Check if this is a task decomposition request (look at system prompt)
        system_content = next((m.get("content", "") for m in messages if m["role"] == "system"), "")
        is_decomposer = "task decomposition" in system_content.lower() or "break down" in system_content.lower()

        if is_decomposer:
            # Always return valid task JSON for decomposer
            content = '''[
    {
        "id": 1,
        "description": "Generate code based on the user's request",
        "agent": "code_generator",
        "dependencies": [],
        "inputs": {}
    }
]'''
        else:
            # For agent execution, pick response based on content
            last_message = messages[-1].get("content", "").lower()
            
            if "api" in last_message or "endpoint" in last_message:
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
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4-turbo-preview"

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
        # Split system message from user messages (Anthropic API requires this)
        system_msg = next(
            (m["content"] for m in messages if m["role"] == "system"),
            "You are a helpful AI assistant."
        )
        user_messages = []

        for m in messages:
            if m["role"] == "system":
                continue

            user_messages.append({
                "role": m["role"],
                "content": [
                    {
                        "type": "text",
                        "text": m["content"]
                    }
                ]
            })

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
    Use this everywhere in the codebase. Never instantiate providers directly.
    
    Auto-selects provider:
      - If ANTHROPIC_API_KEY set → AnthropicProvider
      - If OPENAI_API_KEY set → OpenAIProvider  
      - Otherwise → MockProvider (free, for development)
    """

    def __init__(self, force_mock: bool = False):
        if force_mock:
            self._provider = MockProvider()
            logger.info("LLM: Using MOCK provider (forced)")
        elif settings.anthropic_api_key and settings.anthropic_api_key != "your_anthropic_key_here":
            self._provider = AnthropicProvider()
            logger.info("LLM: Using Anthropic (Claude)")
        elif settings.openai_api_key and settings.openai_api_key != "your_openai_key_here":
            self._provider = OpenAIProvider()
            logger.info("LLM: Using OpenAI (GPT-4)")
        else:
            self._provider = MockProvider()
            logger.info("LLM: Using MOCK provider (no API keys set)")

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
            f"LLM call | provider={response.provider} | "
            f"tokens={response.total_tokens} | "
            f"cost=${response.estimated_cost_usd():.4f} | "
            f"time={elapsed_ms}ms"
        )

        return response