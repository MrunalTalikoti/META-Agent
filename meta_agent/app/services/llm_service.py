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
    # Returned by the orchestrator's decomposition step (a task list, not a
    # single artifact). Kept separate from the per-agent artifacts below.
    DECOMPOSER_RESPONSE = '''[
    {"id": 1, "description": "Design REST API endpoints", "agent": "api_designer", "dependencies": [], "inputs": {}},
    {"id": 2, "description": "Design database schema", "agent": "database_schema", "dependencies": [], "inputs": {}},
    {"id": 3, "description": "Generate implementation code", "agent": "code_generator", "dependencies": [1, 2], "inputs": {}},
    {"id": 4, "description": "Write unit and integration tests", "agent": "testing_agent", "dependencies": [3], "inputs": {}},
    {"id": 5, "description": "Create README and API documentation", "agent": "documentation_agent", "dependencies": [3], "inputs": {}}
]'''

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

        "testing": '''```python
import pytest

def test_create_user_valid_returns_201():
    resp = create_user(email="a@b.com", password="secret123")
    assert resp.status_code == 201

def test_create_user_duplicate_email_returns_409():
    create_user(email="a@b.com", password="secret123")
    resp = create_user(email="a@b.com", password="secret123")
    assert resp.status_code == 409

def test_create_user_empty_email_raises():
    with pytest.raises(ValueError):
        create_user(email="", password="secret123")
```''',

        "documentation": '''# User Service

A small service for creating and managing user accounts.

## Overview
This service exposes a REST API for registering users and looking them up.

## Installation
```bash
pip install -r requirements.txt
```

## Usage
Call the `/api/v1/users` endpoint with an email and password to create a user.

## Troubleshooting
If requests fail with 409, the email is already registered.''',

        # Frontend: at least one component block (tsx) + a style block (css), so
        # FrontendGeneratorAgent.parse_output extracts a non-empty component list.
        "frontend": '''```tsx
// UserList.tsx
import React, { useState, useEffect } from 'react';

interface User {
  id: number;
  name: string;
}

export default function UserList() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/users')
      .then((r) => r.json())
      .then((data) => setUsers(data))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p role="status">Loading…</p>;

  return (
    <ul aria-label="User list">
      {users.map((u) => (
        <li key={u.id}>{u.name}</li>
      ))}
    </ul>
  );
}
```
```css
/* UserList.css */
.user-list { display: flex; flex-direction: column; gap: 0.5rem; }
```''',

        # DevOps: one block per file, each classifiable by DevOpsAgent.parse_output
        # (dockerfile / docker-compose yaml / GitHub Actions yaml / .env).
        "devops": '''```dockerfile
# Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m appuser
USER appuser
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
```
```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
```
```env
DATABASE_URL=postgresql://localhost/app
SECRET_KEY=replace-me
```''',

        # Security / performance: raw JSON matching each agent's documented schema,
        # so json.loads succeeds and the "unknown"/"raw" fallback is never hit.
        "security": '''{"severity": "high", "issues": [{"type": "SQL Injection", "location": "app/api/users.py:42", "description": "User input is concatenated directly into a SQL query.", "fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))"}, {"type": "Hardcoded Secret", "location": "app/core/config.py:12", "description": "An API key is committed in source control.", "fix": "Load secrets from environment variables instead."}], "recommendations": ["Enable rate limiting on authentication endpoints", "Add CSRF protection to state-changing routes"]}''',

        "performance": '{"current_performance": "Average API response time is 850ms under load.", "bottlenecks": [{"location": "app/api/conversations.py:get_messages", "issue": "N+1 query loading messages per conversation", "impact": "high", "fix": "Use selectinload to eager-load messages in a single query."}], "optimizations": ["Add a Redis cache for hot conversation reads", "Add a composite index on (conversation_id, created_at)"]}',

        "requirements": '{"status": "needs_clarification", "question": "What backend framework would you like to use? (1) Python/FastAPI, (2) Python/Django, (3) Node.js/Express, (4) Go/Gin", "gathered_so_far": {"functional": "TBD", "tech_stack": "", "architecture": "", "scale": "", "deliverables": "", "constraints": ""}}',

        # Legacy generic artifact. Routing no longer returns this — every known
        # agent maps to a schema-correct artifact above (see _route).
        "default": "I have analyzed your request and generated a comprehensive response following best practices.",
    }

    # Distinctive phrase from each agent's system prompt → mock artifact key.
    # The system prompt is authoritative (it is messages[0]); routing on it means
    # an agent always gets schema-correct content regardless of task wording.
    # Checked in order; first contained marker wins.
    SYSTEM_ROUTES = [
        ("requirements analyst", "requirements"),
        ("api architect", "api"),
        ("database architect", "database"),
        ("qa engineer", "testing"),
        ("technical writer", "documentation"),
        ("frontend developer", "frontend"),
        ("devops engineer", "devops"),
        ("security expert", "security"),
        ("performance optimization expert", "performance"),
        ("senior software engineer", "code"),
    ]

    def _route(self, system_content: str, last_message: str) -> str:
        """Pick the mock artifact for a request. Never returns the generic default."""
        # 1. Orchestrator decomposition (special — returns a task list).
        if "break down" in system_content or "available agents" in system_content:
            return self.DECOMPOSER_RESPONSE

        # 2. Agent fingerprint via system prompt (authoritative).
        for marker, key in self.SYSTEM_ROUTES:
            if marker in system_content:
                return self.MOCK_RESPONSES[key]

        # 3. Keyword fallback for bare user-only prompts (no system prompt).
        if "api" in last_message or "endpoint" in last_message:
            return self.MOCK_RESPONSES["api"]
        if "database" in last_message or "schema" in last_message or "table" in last_message:
            return self.MOCK_RESPONSES["database"]

        # 4. Final default: a valid code artifact (not the prose "default").
        return self.MOCK_RESPONSES["code"]

    async def generate(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        await asyncio.sleep(0.1)

        system_content = next((m.get("content", "") for m in messages if m["role"] == "system"), "").lower()
        last_message = messages[-1].get("content", "").lower()

        content = self._route(system_content, last_message)

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