# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

MCPilot is a FastAPI **MCP (Model Context Protocol) gateway** — a single server that aggregates and routes requests to multiple upstream MCP servers. It adds auth, rate limiting, RAG-powered semantic routing, and PHI compliance (healthcare) on top of standard MCP.

## Commands

### Run the server
```bash
python -m uvicorn main:app --reload
# API docs at http://localhost:8000/docs
```

### Run tests
```bash
pytest tests/unit/ -v          # unit tests (no real connections)
pytest tests/integration/ -v   # integration tests (real echo server via STDIO)
pytest tests/ -v               # all tests

# Single test file
pytest tests/unit/test_gateway.py -v

# Single test
pytest tests/unit/test_gateway.py::test_explicit_routing -v
```

### Database migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Environment setup
```bash
cp .env.example .env
# Required: DATABASE_URL, AWS_SAGEMAKER_PHI_ENDPOINT, AWS_REGION
# Optional: ANTHROPIC_API_KEY, SECRET_KEY (default is insecure dev value)
```

## Architecture

### Request Flow
```
POST /gateway/tool
  → AuthMiddleware (Bearer JWT or X-API-Key header)
  → RequestLoggingMiddleware
  → SlowAPI rate limit (30 req/min per IP)
  → scan_input()  ← PHI compliance pipeline
  → resolve_route() ← RAG semantic routing
  → MCPManager.call_tool()
  → scan_output() ← PHI compliance pipeline
  → ToolCallResponse
```

### Key Layers

**`app/mcp/`** — MCP client pool
- `MCPClient`: wraps MCP SDK, manages lifecycle (connect/disconnect)
- `MCPManager`: owns multiple `MCPClient` instances, routes by `server_id`
- `MCPRegistry`: metadata store for server configs and tool schemas
- Transport types: STDIO (subprocess) and SSE (HTTP)

**`app/rag/`** — Semantic routing via LlamaIndex
- `MCPToolIndexer`: indexes all tool schemas into ChromaDB (collection: `"mcp_tools"`) using HuggingFace embeddings
- Three routing modes:
  - `EXPLICIT`: client provides `server_id + tool_name` → confidence 1.0
  - `SEMANTIC`: client provides natural language intent → RAG resolves both server and tool
  - `HYBRID`: client provides `server_id` → RAG resolves tool within that server
- Confidence threshold: 0.4

**`app/compliance/`** — PHI detection (healthcare)
- Calls AWS SageMaker BYOC endpoint for NER-based PHI detection
- `scan_input()` / `scan_output()`: redact PHI in parameters before dispatch and responses after
- Falls back gracefully when `ENVIRONMENT=test` or endpoint unavailable

**`app/db/`** — Async SQLAlchemy
- Models: `MCPServer`, `MCPTool`, `HealthEvent`
- `ToolRegistryRepository`: all DB access goes through this, no raw SQL in routers
- Production: PostgreSQL (`asyncpg`); Tests: SQLite (`aiosqlite`)

**`app/middleware/`** — Middleware stack (applied in order in `main.py`):
1. CORS (allow all)
2. Auth (JWT or API key → injects tenant context into `request.state`)
3. RequestLogging
4. SlowAPI rate limiting

**`app/routers/`**
- `/health` — liveness + readiness (checks DB, vector store, SageMaker)
- `/gateway` — tool invocation (main business logic)
- `/auth` — token/API key management (partial implementation)

### Testing Patterns
- Unit tests mock `MCPManager` — no real MCP connections
- Integration tests spin up a real echo server via STDIO subprocess
- `conftest.py` provides `client` (bare manager) and `integration_client` fixtures
- `ENVIRONMENT=test` suppresses real AWS/DB connections throughout the codebase
- Windows requires `asyncio.SelectorEventLoop` — set in conftest for integration tests

### Database Schema
Tables: `mcp_servers`, `mcp_tools`, `health_events`. Migrations live in `alembic/versions/`.

### Hardcoded Dev Values (not for production)
- Dev API key: `mcpilot-dev-key-001` (in `app/core/security.py`)
- Default `SECRET_KEY` in config is insecure — override in `.env` before deploying
