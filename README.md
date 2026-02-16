# META-Agent
A hierarchical Orchestrator Agent with Multi-Sub-Agent features for efficient 

1. **Meta-Agent Orchestrator** 
2. **Task Decomposer** 
3. **Specialized Agents** 
4. **Agent Router** 
5. **Validation Layer**

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER DEVICE                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ HTTPS Request
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (FastAPI)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Auth Guard   │  │ Rate Limiter │  │ Logging      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   REQUEST PROCESSING LAYER                       │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Intent Classifier (LLM)                               │     │
│  │  "What is the user actually asking for?"               │     │
│  └────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Context Manager                                        │     │
│  │  • Load user preferences                                │     │
│  │  • Retrieve project history                             │     │
│  │  • Get relevant past results                            │     │
│  └────────────────────────────────────────────────────────┘     │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   META-AGENT ORCHESTRATOR                        │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  TASK DECOMPOSER (LLM-powered)                         │     │
│  │  Input: "Create a REST API with user authentication"   │     │
│  │  Output:                                                │     │
│  │    Task 1: Design API endpoints [api_designer]         │     │
│  │    Task 2: Design database schema [database_schema]    │     │
│  │    Task 3: Generate auth code [code_generator]         │     │
│  │    Task 4: Generate API code [code_generator]          │     │
│  │    Task 5: Write tests [testing_agent]                 │     │
│  │    Task 6: Create docs [documentation_agent]           │     │
│  └────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  AGENT ROUTER                                           │     │
│  │  • Selects appropriate agent for each task              │     │
│  │  • Manages execution order (DAG)                        │     │
│  │  • Passes output from one task as input to next         │     │
│  └────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  EXECUTION MANAGER                                      │     │
│  │  • Executes tasks sequentially or in parallel           │     │
│  │  • Handles retries on failure                           │     │
│  │  • Aggregates results                                   │     │
│  └────────────────────────────────────────────────────────┘     │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SPECIALIZED AGENTS POOL                       │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Code       │  │   API        │  │  Database    │          │
│  │  Generator   │  │  Designer    │  │   Schema     │          │
│  │              │  │              │  │  Designer    │          │
│  │ • Python     │  │ • REST API   │  │ • Tables     │          │
│  │ • JavaScript │  │ • GraphQL    │  │ • Relations  │          │
│  │ • Java       │  │ • Endpoints  │  │ • Indexes    │          │
│  │ • Go         │  │ • Auth       │  │ • SQL        │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Testing    │  │Documentation │  │   (Future)   │          │
│  │    Agent     │  │    Agent     │  │   Add more   │          │
│  │              │  │              │  │   as needed  │          │
│  │ • Unit tests │  │ • README     │  │              │          │
│  │ • Integration│  │ • API docs   │  │              │          │
│  │ • E2E tests  │  │ • Guides     │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  All agents use: LLM Service (Claude/GPT-4)                      │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDATION & QUALITY LAYER                    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Syntax Validator                                       │     │
│  │  • Verify code compiles/runs                            │     │
│  │  • Check JSON schema validity                           │     │
│  │  • Validate SQL syntax                                  │     │
│  └────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  LLM Quality Checker                                    │     │
│  │  Ask LLM: "Does this code meet requirements?"           │     │
│  │  "Are there any bugs or security issues?"               │     │
│  └────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  User Feedback Handler                                  │     │
│  │  • Allow user to request changes                        │     │
│  │  • Iterate on results                                   │     │
│  │  • Learn from corrections                               │     │
│  └────────────────────────────────────────────────────────┘     │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                            │
│                                                                   │
│  ┌─────────────────────┐    ┌──────────────────┐               │
│  │    PostgreSQL       │    │      Redis       │               │
│  │                     │    │                  │               │
│  │ • users             │    │ • session cache  │               │
│  │ • projects          │    │ • task queue     │               │
│  │ • tasks             │    │ • rate limiting  │               │
│  │ • agent_executions  │    │                  │               │
│  │ • task dependencies │    │                  │               │
│  │ • results (JSON)    │    │                  │               │
│  └─────────────────────┘    └──────────────────┘               │
│                                                                   │
│  ┌─────────────────────┐                                        │
│  │   Object Storage    │                                        │
│  │   (S3 / Cloudinary) │                                        │
│  │                     │                                        │
│  │ • Generated code    │                                        │
│  │ • Documentation     │                                        │
│  │ • API specs         │                                        │
│  │ • User uploads      │                                        │
│  └─────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## DATA FLOW EXAMPLE

### Example Request: "Create a user authentication API in Python"

```
1. USER → API Gateway
   POST /api/agents/execute
   {
     "project_id": 123,
     "request": "Create a user authentication API in Python"
   }

2. API Gateway → Auth ✓ → Request Processing Layer

3. Intent Classifier (LLM):
   "User wants a REST API with authentication in Python"

4. Task Decomposer (LLM) generates:
   [
     {id: 1, agent: "api_designer", description: "Design auth endpoints"},
     {id: 2, agent: "database_schema", description: "Design user table"},
     {id: 3, agent: "code_generator", description: "Generate FastAPI code", 
      dependencies: [1, 2]},
     {id: 4, agent: "testing_agent", description: "Write tests", 
      dependencies: [3]},
     {id: 5, agent: "documentation_agent", description: "Create docs", 
      dependencies: [3]}
   ]

5. Agent Router executes in order:
   
   Task 1 (api_designer):
   ┌─────────────────────────────────────┐
   │ Input: "Design auth endpoints"      │
   │ Output: {                            │
   │   endpoints: [                       │
   │     {path: "/register", method: POST}│
   │     {path: "/login", method: POST}   │
   │     {path: "/me", method: GET}       │
   │   ]                                  │
   │ }                                    │
   └─────────────────────────────────────┘
   
   Task 2 (database_schema):
   ┌─────────────────────────────────────┐
   │ Input: "Design user table"          │
   │ Output: {                            │
   │   tables: [{                         │
   │     name: "users",                   │
   │     columns: [                       │
   │       {name: "id", type: "INTEGER"}  │
   │       {name: "email", type: "VARCHAR}│
   │       {name: "password", ...}        │
   │     ]                                │
   │   }]                                 │
   │ }                                    │
   └─────────────────────────────────────┘
   
   Task 3 (code_generator):
   ┌─────────────────────────────────────┐
   │ Input: Results from Task 1 & 2      │
   │ Output: {                            │
   │   code: "from fastapi import..."    │
   │   language: "python"                 │
   │ }                                    │
   └─────────────────────────────────────┘
   
   Task 4 & 5 execute in parallel...

6. Validation Layer:
   ✓ Code compiles
   ✓ LLM quality check passes
   ✓ All requirements met

7. Response to user:
   {
     "status": "success",
     "tasks": [...],
     "results": {
       "code": "...",
       "tests": "...",
       "docs": "...",
       "api_spec": {...}
     }
   }
```

---

## WHY THIS WORKS

### ✅ Advantages:
1. **Simpler** - 1 database instead of 5
2. **Faster to build** - 12 weeks vs 9 months
3. **Actually works** - No experimental features
4. **Debuggable** - Clear data flow
5. **Scalable** - Can add complexity later
6. **Cost-effective** - Lower infrastructure costs
7. **Student-friendly** - Uses familiar tech

---

## EVOLUTION PATH

After MVP is working, you can add:

**Phase 2** (Months 4-6):
- Vector DB for semantic search
- Agent result caching
- A/B testing for prompts
- Usage analytics

**Phase 3** (Months 7-12):
- More specialized agents
- Custom agent training
- Team collaboration features
- Advanced workflow builder
