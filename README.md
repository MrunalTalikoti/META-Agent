# META-Agent

A hierarchical AI orchestration system built with FastAPI. Send a natural language request and the meta-agent decomposes it into subtasks, routes each to a specialized AI agent, and returns the aggregated result.

**Version:** 0.2.0 | **Python:** 3.11 | **License:** See [LICENSE](LICENSE)

---

## How It Works

```
User Request
    │
    ▼
API Gateway (FastAPI)
    │  Auth guard · Rate limiter · Request ID injection
    ▼
Intent Classifier (LLM)
    │  "What is the user actually asking for?"
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

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER DEVICE                              │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTPS Request
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Auth Guard  │  │ Rate Limiter │  │  Logging     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   META-AGENT ORCHESTRATOR                         │
│  Task Decomposer → Agent Router → Execution Manager             │
│  (LLM-powered DAG planning with circular dependency detection)   │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SPECIALIZED AGENTS POOL                        │
│  code_generator  │  api_designer    │  database_schema           │
│  testing_agent   │  documentation   │  frontend_generator         │
│  devops          │  security_auditor│  performance_optimizer      │
│  requirements_gatherer                                            │
│  All agents powered by: OpenAI GPT-4o / Anthropic Claude 3.5    │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                               │
│  PostgreSQL (users, projects, tasks, results)                    │
│  Redis      (session cache, rate limiting)                        │
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
| `devops` | Dockerfile, docker-compose, GitHub Actions CI/CD |
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
│   │   ├── agents.py           #   Execute, task status
│   │   ├── conversations.py    #   Interactive conversation mode
│   │   ├── projects.py         #   Project CRUD
│   │   └── export.py           #   File export & cost metrics
│   ├── agents/                 # Specialized AI agents
│   │   ├── base_agent.py
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
│   │   ├── config.py           #   Pydantic settings from .env
│   │   ├── database.py         #   SQLAlchemy engine & session
│   │   ├── orchestrator.py     #   Main MetaAgentOrchestrator
│   │   ├── task_decomposer.py  #   LLM-powered DAG planner
│   │   ├── cache.py            #   Redis client
│   │   └── security.py         #   JWT, password hashing
│   ├── models/
│   │   └── database.py         #   SQLAlchemy models + enums
│   ├── services/
│   │   ├── llm_service.py      #   OpenAI + Anthropic providers
│   │   ├── validation.py       #   Output quality checks
│   │   └── file_export.py      #   Export generated artifacts
│   └── utils/
│       ├── logger.py
│       ├── rate_limiter.py
│       ├── retry.py
│       ├── tier_limits.py      #   Per-tier daily quota enforcement
│       └── cost_monitor.py     #   LLM spend tracking
├── alembic/                    # Database migrations
│   └── versions/
├── tests/
│   ├── integration/
│   └── unit/
├── .env.example
├── requirements.txt
└── Dockerfile
```

---

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- An OpenAI API key **or** an Anthropic API key (or both)

---

## Implementation Steps

### 1. Clone the repository

```bash
git clone https://github.com/your-org/meta-agent.git
cd meta-agent/meta_agent
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/metaagent

# Cache
REDIS_URL=redis://localhost:6379/0

# LLM — provide at least one
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Security — generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# App
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO
APP_NAME=MetaAgent
```

### 5. Start PostgreSQL and Redis

Using Docker (quickest):

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=metaagent -p 5432:5432 postgres:15-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

Or use any existing local installations.

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now live at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account, returns JWT |
| POST | `/api/auth/token` | Login (OAuth2 form), returns JWT |
| GET | `/api/auth/me` | Current user info |

### Projects

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List your projects |
| GET | `/api/projects/{id}` | Get project details |
| DELETE | `/api/projects/{id}` | Delete project |

### Agent Execution

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/agents/execute` | Submit a natural language request |
| GET | `/api/agents/tasks/{task_id}` | Get task status and output |
| GET | `/api/agents/projects/{project_id}/tasks` | List all tasks for a project |

**Execute request body:**
```json
{
  "project_id": 1,
  "request": "Create a user authentication REST API in Python with JWT tokens"
}
```

**Response:**
```json
{
  "status": "success",
  "tasks": [...],
  "results": {
    "code": "...",
    "tests": "...",
    "docs": "...",
    "api_spec": {}
  }
}
```

### Conversations (Interactive Mode)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/conversations` | Start a conversation (`normal` or `hardcore` mode) |
| GET | `/api/conversations/{id}` | Get conversation history |
| POST | `/api/conversations/{id}/message` | Send a follow-up message |

### Export & Metrics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/export/...` | Download generated artifacts |
| GET | `/health` | Health check with DB status and daily LLM spend |

---

## Example Request Flow

```
POST /api/agents/execute
{ "project_id": 1, "request": "Create a user authentication API in Python" }

  Task Decomposer plans:
    [1] api_designer      → Design /register, /login, /me endpoints
    [2] database_schema   → Design users table with password hashing
    [3] code_generator    → Generate FastAPI code (depends on 1, 2)
    [4] security_auditor  → Audit for auth flaws (depends on 3)
    [5] testing_agent     → Write tests (depends on 3)
    [6] documentation_agent → Create README + API docs (depends on 3)

  Tasks 1 & 2 run in parallel.
  Task 3 waits for both.
  Tasks 4, 5, 6 run in parallel once 3 finishes.
```

---

## Running Tests

```bash
pytest tests/ -v --asyncio-mode=auto
```

CI tests use a `MockProvider` so no API keys are needed in the test environment.

---

## CI/CD (GitHub Actions)

Three jobs run on every push to `main` or `develop`:

| Job | What it does |
|---|---|
| `test` | Lint with `ruff`, run Alembic migrations, run `pytest` against real Postgres + Redis |
| `docker` | Build the Docker image (runs after `test` passes) |
| `security` | Run `bandit` static security analysis on `app/` |

---

## LLM Providers

The `LLMService` in [app/services/llm_service.py](meta_agent/app/services/llm_service.py) supports:

| Provider | Models |
|---|---|
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo-preview` |
| Anthropic | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022` |
| Mock | Used in tests — zero cost, no API key needed |

The active provider is selected based on which API key is present in `.env`.

---

## Data Flow Diagram

```
Meta-Agent final flow.jpeg
```

See the [Meta-Agent final flow](Meta-Agent%20final%20flow.jpeg) image in the repo root for a visual overview.
