# ADE - Agentic Developer Environment

A multi-agent AI coding assistant that plans, writes code, executes tests, and iterates. Built with LangGraph for agent orchestration, Claude for LLM intelligence, and FastAPI for the API layer.

## Architecture

```
Task Description
      |
  [Planner] ── RAG context + file tree
      |
  [Codegen] ── generates code changes per step
      |
  [Executor] ── runs tests in sandbox (Docker/subprocess)
      |         ╲
  [pass?]──no──>[Retry] (up to 3x)
      |
  [Apply] ── writes changes to real project
      |
  [Complete]
```

**Agents** are LangGraph nodes connected in a `StateGraph`. The orchestrator compiles the graph and runs it for each task.

### Key Components

| Component | Purpose |
|-----------|---------|
| `ade/agents/` | LangGraph agent nodes (planner, codegen, executor, orchestrator) |
| `ade/core/` | Config, database, Redis cache, Claude LLM wrapper |
| `ade/rag/` | Code indexing (AST chunking), embedding, retrieval with reranking |
| `ade/sandbox/` | Docker-based sandboxed execution, workspace management |
| `ade/api/` | FastAPI REST API + WebSocket for real-time events |
| `ade/cli/` | Click CLI for interacting with ADE |
| `ade/ui/` | React + TypeScript + Tailwind frontend |

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Node.js 18+ (for the UI)
- [uv](https://docs.astral.sh/uv/) (recommended for Python dependency management)

## Setup

```bash
# Clone and enter the repo
cd Agentic_DE

# Create .env from template
cp .env.example .env
# Edit .env — set at minimum ANTHROPIC_API_KEY

# Create venv and install dependencies
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Start Postgres (pgvector) and Redis
docker compose up -d

# Run database migrations
alembic upgrade head
```

### Build the Sandbox Image (optional, for Docker executor)

```bash
docker build -t ade-sandbox:latest -f ade/sandbox/Dockerfile.sandbox .
```

### Install UI Dependencies (optional)

```bash
cd ade/ui
npm install
cd ../..
```

## Usage

### CLI

```bash
# Start the API server
ade serve

# Register a project
ade init /path/to/your/project --name my-project

# Create a task
ade task my-project "Add input validation to the signup form"

# Check task status
ade status <task-id>

# View agent logs
ade logs <task-id>

# List all projects
ade projects
```

### API

The REST API runs at `http://localhost:8000` by default.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (DB + Redis) |
| `/api/projects` | GET/POST | List or create projects |
| `/api/projects/{id}` | GET | Get project details |
| `/api/projects/{id}/tasks` | POST | Create a task |
| `/api/projects/{id}/tasks` | GET | List tasks for a project |
| `/api/tasks/{id}` | GET | Get task details with plan, changes, results |
| `/api/tasks/{id}/logs` | GET | Get agent logs for a task |
| `/ws/tasks/{id}` | WebSocket | Real-time task events |

### UI

```bash
cd ade/ui
npm run dev
# Opens at http://localhost:5173, proxies API to :8000
```

## Configuration

All settings are loaded from environment variables (or `.env`). See [.env.example](.env.example) for the full list.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | required | Claude API key |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async database connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for caching and pub/sub |
| `SANDBOX_BACKEND` | `docker` | Execution backend: `docker`, `subprocess`, or `mock` |
| `EMBEDDING_PROVIDER` | `openai` | Embedding provider: `openai` or `voyage` |
| `DEFAULT_CODEGEN_MODEL` | `claude-sonnet-4-20250514` | Model for code generation |
| `LLM_CACHE_TTL_SECONDS` | `3600` | Redis LLM cache TTL |

## Testing

```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run specific test modules
.venv/bin/python -m pytest tests/test_agents/ -v
.venv/bin/python -m pytest tests/test_integration/ -v
.venv/bin/python -m pytest tests/test_sandbox/test_apply_to_project.py -v

# Lint
ruff check ade/ tests/
```

## Project Structure

```
ade/
  agents/
    orchestrator.py    # LangGraph StateGraph: plan → code → execute → apply
    planner.py         # Planning agent with RAG + file tree context
    codegen.py         # Code generation agent
    executor.py        # Test execution (Docker/subprocess/mock backends)
    parsers.py         # XML output parsing for LLM responses
    state.py           # AgentState TypedDict
    prompts/           # System prompt templates
  core/
    config.py          # pydantic-settings configuration
    database.py        # Async SQLAlchemy engine + sessions
    models.py          # ORM models (7 tables) + Pydantic schemas
    redis_client.py    # Redis cache + LLM cache key builder
    llm.py             # Claude API wrapper with retry + caching
  rag/
    chunker.py         # AST-based Python code chunking
    embeddings.py      # OpenAI/Voyage embedding providers
    indexer.py         # Project indexing pipeline
    retriever.py       # Vector similarity search + LLM reranking
  sandbox/
    docker_manager.py  # Docker container execution
    workspace.py       # Sandbox workspace + apply-to-project
    security.py        # Container security policy
    Dockerfile.sandbox # Sandbox container image
  api/
    main.py            # FastAPI app factory
    routes/            # REST + WebSocket endpoints
    events.py          # Redis pub/sub event publishing
    task_runner.py     # Background task execution
  cli/
    main.py            # Click CLI commands
    client.py          # Async HTTP client
    formatters.py      # Terminal output formatting
  ui/                  # React + Vite + Tailwind frontend
```

## Tech Stack

- **Orchestration**: LangGraph StateGraph
- **LLM**: Claude (Anthropic SDK) with async, retry, Redis caching
- **Database**: PostgreSQL + pgvector (async SQLAlchemy + Alembic)
- **Cache/PubSub**: Redis
- **RAG**: AST chunking + OpenAI/Voyage embeddings + HNSW index
- **Sandbox**: Docker containers with security policies
- **API**: FastAPI + WebSocket
- **CLI**: Click
- **UI**: React 18 + TypeScript + Vite + Tailwind CSS
