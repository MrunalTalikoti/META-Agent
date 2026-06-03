# META-Agent

A hierarchical AI orchestration system built with FastAPI. Send a natural language request and the meta-agent decomposes it into subtasks, routes each to a specialized AI agent, and returns the aggregated result.

**Python:** 3.11+ | **License:** See [LICENSE](LICENSE)

---

## How It Works

```
User Request
    │
    ▼
API Gateway (FastAPI)
    │  Auth guard · Redis rate limiter · Request ID injection
    ▼
Task Decomposer (LLM)
    │  Breaks request into 1–8 subtasks with a dependency DAG
    ▼
Agent Router
    │  Resolves execution order, passes outputs as inputs
    ▼
Specialized Agents Pool ──────────────────────────────────┐
    code_generator · api_designer · database_schema        │
    testing_agent · documentation_agent · frontend_generator│
    devops · security_auditor · performance_optimizer      │
    requirements_gatherer                                  │
    └──────────────────────────────────────────────────────┘
    ▼
Validation Layer
    │  Syntax check · LLM quality check
    ▼
Aggregated Result → User
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER DEVICE                              │
│                  React SPA · SSE streaming                        │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTPS
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Auth (JWT)  │  │ Rate Limiter │  │  Logging     │          │
│  │              │  │   (Redis)    │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   META-AGENT ORCHESTRATOR                         │
│  Task Decomposer → Agent Router → Background Execution           │
│  (LLM-powered DAG planning with circular dependency detection)   │
│  Async job-based — HTTP returns immediately with job_id          │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SPECIALIZED AGENTS POOL                        │
│  code_generator  │  api_designer    │  database_schema           │
│  testing_agent   │  documentation   │  frontend_generator         │
│  devops          │  security_auditor│  performance_optimizer      │
│  requirements_gatherer                                            │
│  All agents powered by: OpenAI GPT-4o / Anthropic Claude         │
│  Concurrent execution via asyncio.gather with cost tracking      │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                               │
│  PostgreSQL  (users, projects, tasks, conversations, results)    │
│  Redis       (rate limiting, job state, response caching)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Specialized Agents

| Agent | Capability |
|---|---|
| `code_generator` | Production code in Python, JavaScript, Go, Java, etc. |
| `api_designer` | REST endpoints, request/response schemas, auth flows |
| `database_schema` | Tables, relations, indexes, SQL DDL generation |
| `testing_agent` | Unit, integration, and E2E tests with fixtures |
| `documentation_agent` | README, API docs, user guides, inline comments |
| `frontend_generator` | React/Vue/HTML components with Tailwind CSS |
| `devops` | Dockerfile, docker-compose, GitHub Actions, GitLab CI, Kubernetes |
| `security_auditor` | SQLi, XSS, auth flaws, secrets exposure audits |
| `performance_optimizer` | Bottleneck detection, N+1 queries, caching opportunities |
| `requirements_gatherer` | Clarifying questions to gather complete project requirements |

---

## User Tiers

| Tier | Daily Requests |
|---|---|
| FREE | 10 |
| PRO | Unlimited |
| ENTERPRISE | Unlimited |

---

## Project Structure

```
meta_agent/
├── app/
│   ├── api/                    # FastAPI routers
│   │   ├── auth.py             #   Register, login, /me
│   │   ├── agents.py           #   Execute (async jobs), task status
│   │   ├── conversations.py    #   Interactive conversation mode + SSE
│   │   ├── projects.py         #   Project CRUD
│   │   └── export.py           #   File export & cost metrics
│   ├── agents/                 # Specialized AI agents
│   │   ├── base_agent.py       #   Base class with caching, DB logging, cost tracking
│   │   ├── code_generator.py
│   │   ├── api_designer.py
│   │   ├── database_schema.py
│   │   ├── testing_agent.py
│   │   ├── documentation_agent.py
│   │   ├── frontend_generator.py
│   │   ├── devops_agent.py
│   │   ├── security_auditor.py
│   │   ├── performance_optimizer.py
│   │   └── requirements_gatherer.py
│   ├── core/                   # Infrastructure
│   │   ├── config.py           #   Pydantic settings with SECRET_KEY validation
│   │   ├── database.py         #   SQLAlchemy engine & session
│   │   ├── orchestrator.py     #   MetaAgentOrchestrator (background execution)
│   │   ├── task_decomposer.py  #   LLM-powered DAG planner
│   │   ├── cache.py            #   Redis client & CacheService
│   │   └── security.py         #   JWT, password hashing
│   ├── models/
│   │   └── database.py         #   SQLAlchemy models + enums
│   ├── services/
│   │   ├── llm_service.py      #   OpenAI + Anthropic providers
│   │   ├── validation.py       #   Output quality checks
│   │   ├── file_export.py      #   Export generated artifacts
│   │   └── job_manager.py      #   Redis-backed async job state
│   └── utils/
│       ├── logger.py
│       ├── rate_limiter.py     #   Redis distributed sliding window
│       ├── retry.py
│       ├── tier_limits.py      #   Per-tier daily quota enforcement
│       └── cost_monitor.py     #   Async-safe LLM spend tracking
├── alembic/                    # Database migrations
│   └── versions/
├── tests/
│   ├── fixtures/               # Realistic LLM output samples
│   │   └── llm_outputs/
│   ├── integration/
│   │   └── test_api.py         #   HTTP integration tests
│   ├── unit/
│   │   └── test_parser_robustness.py
│   └── test_main_agent.py      #   Core unit tests
├── .env.example
├── requirements.txt
└── Dockerfile
```

```
frontend/
├── src/
│   ├── Conversation.jsx        #   Chat UI with SSE streaming
│   ├── ProgressTracker.jsx     #   Live agent execution progress
│   ├── ResultsPanel.jsx        #   Output display
│   ├── FileBrowser.jsx         #   Browse & download generated files
│   ├── Layout.jsx
│   └── api.js                  #   API client + SSE helpers
├── package.json
└── vite.config.js
```

---

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (for frontend)
- An OpenAI API key **or** an Anthropic API key (or both)

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-org/meta-agent.git
cd meta-agent/meta_agent

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/metaagent

# Cache
REDIS_URL=redis://localhost:6379/0

# LLM — provide at least one
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Security — minimum 32 characters, generate with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# App
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO
APP_NAME=MetaAgent
```

> **Note:** The app will refuse to start if `SECRET_KEY` is shorter than 32 characters or is a known weak value.

### 3. Start services

Using Docker:

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=metaagent -p 5432:5432 postgres:15-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`

### 6. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account, returns `{access_token, token_type}` |
| POST | `/api/auth/token` | Login (OAuth2 form), returns JWT |
| GET | `/api/auth/me` | Current user info |

### Projects

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List your projects (paginated) |
| GET | `/api/projects/{id}` | Get project details |
| DELETE | `/api/projects/{id}` | Delete project |

### Agent Execution (Async)

Execution is non-blocking. The endpoint returns a job ID immediately; poll for results.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/agents/execute` | Submit request, returns `{job_id, status}` |
| GET | `/api/agents/jobs/{job_id}` | Poll job status and results |
| GET | `/api/agents/tasks/{task_id}` | Get individual task output |
| GET | `/api/agents/projects/{pid}/tasks` | List all tasks for a project |

**Execute request:**

```json
{
  "project_id": 1,
  "request": "Create a user authentication REST API in Python with JWT tokens"
}
```

**Immediate response:**

```json
{
  "job_id": "a1b2c3d4...",
  "status": "pending"
}
```

**Job status (poll `GET /api/agents/jobs/{job_id}`):**

```json
{
  "job_id": "a1b2c3d4...",
  "status": "completed",
  "result": { "...agent outputs..." },
  "error": null,
  "created_at": "...",
  "started_at": "...",
  "completed_at": "..."
}
```

Job lifecycle: `pending → running → completed | failed`

### Conversations (Interactive Mode)

Two modes: **normal** (single turn, immediate execution) and **hardcore** (multi-turn requirements gathering before execution).

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/conversations` | Start conversation |
| GET | `/api/conversations/{id}` | Get conversation state |
| POST | `/api/conversations/{id}/message` | Send follow-up message |
| GET | `/api/conversations/{id}/stream` | SSE stream for live progress |
| POST | `/api/conversations/{id}/reset` | Reset stuck/failed conversation |
| DELETE | `/api/conversations/{id}` | Delete conversation |
| GET | `/api/conversations` | List conversations (paginated) |

**Conversation lifecycle (hardcore mode):**

```
GATHERING → READY → EXECUTING → COMPLETED
              ↑                      │
              └── (refinement) ──────┘

GATHERING → FAILED (on unrecoverable error)
FAILED → GATHERING (via /reset endpoint)
```

Gathering is capped at 10 turns to prevent infinite token burn. If the limit is reached, the conversation transitions to READY with partial requirements.

### Export & Metrics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/export/...` | Download generated artifacts as zip |
| GET | `/api/metrics` | Usage stats: projects, tasks, token/cost totals |
| GET | `/health` | Health check |

---

## Key Design Decisions

### Async Job Execution

All orchestrator calls run in background tasks (`asyncio.create_task`) with their own DB sessions. HTTP endpoints return immediately — safe behind nginx/load balancer timeouts of 30–60s. Clients poll `/agents/jobs/{id}` or connect to the SSE stream for live updates.

### Distributed Rate Limiting

Redis sorted-set sliding window (`ZADD` + `ZREMRANGEBYSCORE` + `ZCARD` in a pipeline). Works correctly across multiple uvicorn workers. Falls back to allowing requests if Redis is unavailable.

### Cost Tracking

Per-request LLM costs stored as microdollars (`USD × 1,000,000`) in a `BIGINT` column. An `asyncio.Lock` in the `CostMonitor` prevents concurrent agents from undercounting spend during `asyncio.gather`.

### Robust LLM Output Parsing

Agent parsers extract all fenced code blocks in a single pass and classify them heuristically by content (e.g., `jobs:` → GitHub Actions, `services:` → docker-compose, `apiVersion:` → Kubernetes). Parsers never silently return empty output — unmatched content is logged and the raw LLM response is preserved.

### SSE Streaming

Change-gated polling: the task query is skipped when `conversation.updated_at` hasn't changed. Only the conversation row is refreshed each cycle (not `expire_all()`). Heartbeat comments keep proxy connections alive during idle periods.

---

## Example Request Flow

```
POST /api/agents/execute
{ "project_id": 1, "request": "Create a user authentication API in Python" }

→ Returns: { "job_id": "abc123", "status": "pending" }

  Orchestrator runs in background:
    [1] api_designer      → Design /register, /login, /me endpoints
    [2] database_schema   → Design users table with password hashing
    [3] code_generator    → Generate FastAPI code (depends on 1, 2)
    [4] security_auditor  → Audit for auth flaws (depends on 3)
    [5] testing_agent     → Write tests (depends on 3)
    [6] documentation_agent → Create README + API docs (depends on 3)

  Tasks 1 & 2 run in parallel.
  Task 3 waits for both.
  Tasks 4, 5, 6 run in parallel once 3 finishes.

→ Poll GET /api/agents/jobs/abc123 until status = "completed"
```

---

## Running Tests

```bash
cd meta_agent

# All tests
pytest tests/ -v

# Unit tests only
pytest tests/test_main_agent.py tests/unit/ -v

# Parser robustness tests (realistic LLM outputs)
pytest tests/unit/test_parser_robustness.py -v

# Integration tests (HTTP endpoints)
pytest tests/integration/ -v
```

Tests use a `MockProvider` and in-memory SQLite — no API keys or external services needed.

---

## LLM Providers

| Provider | Models |
|---|---|
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo-preview` |
| Anthropic | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022` |
| Mock | Used in tests — zero cost, no API key needed |

The active provider is selected based on which API key is present in `.env`. If neither is set, the mock provider is used (useful for development).

---

## Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description"

# Rollback one step
alembic downgrade -1
```

Current migration chain:

```
20ba7ba12955  Initial schema
eb0b779848e2  Add conversational modes
97e6945f15bc  Add requirements_gatherer to AgentType
f3a91c2d4e55  Add extended agent types
a1b2c3d4e5f6  Widen estimated_cost_usd to BIGINT
b2c3d4e5f6a7  Add gathering_turn_count and failed status
c4d5e6f7a8b9  Align ConversationStatus FAILED casing
d5e6f7a8b9c0  Rename estimated_cost_usd to estimated_cost_microdollars
```
