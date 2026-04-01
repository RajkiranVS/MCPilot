<div align="center">

# ◈ MCPilot

**Universal AI Orchestration Gateway — On-Premise · Secure · Auditable**

[![CI](https://github.com/RajkiranVS/MCPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/RajkiranVS/MCPilot/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-134%20passing-brightgreen.svg)](tests/)

*Route natural language commands to the right system. Redact PII automatically. Log every action immutably. Run entirely on your infrastructure.*

</div>

---

## What is MCPilot?

MCPilot is an open-source AI orchestration gateway built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). It acts as a secure, intelligent routing layer between operators and multiple backend systems — understanding natural language, protecting sensitive identifiers, and maintaining a tamper-proof audit trail.

Originally designed for healthcare compliance (HIPAA), MCPilot's architecture is equally suited to **defence communications**, **government data systems**, and any environment where:

- Operators work across **multiple systems simultaneously**
- **Personally Identifiable Information (PII)** must never reach downstream systems
- Every action must be **cryptographically logged** and verifiable
- The AI layer must run **entirely on-premise** — no data leaves the facility

---

## Core Capabilities

| Capability | Description |
|---|---|
| **Semantic Routing** | Natural language → correct tool, automatically. 95% Precision@1 across tool categories |
| **PII Redaction** | Military ranks, badge numbers, SSNs, emails, phones — detected and masked before any system interaction |
| **Immutable Audit Log** | SHA-256 hash-chained PostgreSQL records. Nothing can be deleted or modified |
| **On-Premise LLM** | Ollama integration — llama3.2 / llama3.1:8b running locally. Zero data egress |
| **Multi-Tenant** | DB-backed API key isolation. Each tenant sees only their own audit records |
| **GDPR / DPDP Act** | Pseudonymisation hooks, right-to-erasure stubs, retention policy config |
| **Real-Time Observability** | WebSocket-powered dashboard — latency graphs, PII detection rate, live tool call feed |

---

## Architecture

```
Operator Input (text or voice)
        │
        ▼
┌─────────────────────────────────────────────┐
│              MCPilot Gateway                │
│                                             │
│  ┌─────────────┐    ┌─────────────────────┐ │
│  │ Auth Layer  │    │   PII Scanner       │ │
│  │ JWT / API   │───▶│   spaCy NER +       │ │
│  │ Key (DB)    │    │   Ollama LLM        │ │
│  └─────────────┘    └──────────┬──────────┘ │
│                                │ redacted   │
│  ┌─────────────────────────────▼──────────┐ │
│  │         Semantic Router (RAG)          │ │
│  │   LlamaIndex + ChromaDB + BGE embed    │ │
│  │   95% Precision@1 · MRR 0.975         │ │
│  └──────────────────┬─────────────────────┘ │
│                     │                       │
│  ┌──────────────────▼─────────────────────┐ │
│  │            MCP Client Pool             │ │
│  │   filesystem · fetch · echo · custom  │ │
│  └──────────────────┬─────────────────────┘ │
│                     │                       │
│  ┌──────────────────▼─────────────────────┐ │
│  │         Audit Log (PostgreSQL)         │ │
│  │   SHA-256 hash chain · append-only    │ │
│  │   DPDP Act 2023 · HIPAA compliant     │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
        │
        ▼
   Response (PII-free) → Operator
```

**Everything runs on your infrastructure.** No API calls to external services required.

---

## RAG Benchmark

Semantic tool routing evaluated against 20 queries across 4 intent categories.
Model: `BAAI/bge-small-en-v1.5` · Threshold: `score ≥ 0.40`

| Metric | Score |
|---|---|
| Precision@1 | **95.0%** |
| Precision@3 | **100.0%** |
| Mean Reciprocal Rank | **0.9750** |

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- [Ollama](https://ollama.ai) (for on-premise LLM)

### Installation

```bash
git clone https://github.com/RajkiranVS/MCPilot.git
cd MCPilot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your database URL and settings
```

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/mcpilot
SECRET_KEY=your-secret-key
ENVIRONMENT=development
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_URL=http://localhost:11434
```

### Database Setup

```bash
alembic upgrade head
```

### Start MCPilot

```bash
# Pull a local LLM model
ollama pull llama3.2

# Start MCPilot
uvicorn main:app --reload
```

MCPilot is now running at `http://localhost:8000`.

### Open the Tactical Dashboard

```
http://localhost:8000/frontend/mcpilot_dashboard.html
```

### Test PII Redaction

```bash
curl -X POST http://localhost:8000/gateway/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mcpilot-dev-key-001" \
  -d '{"query": "Major Ram Prasad Sharma with badge 123-45-67-890 requesting sector-4 frequency logs"}'
```

**Response:**
```json
{
  "phi_detected": true,
  "clean_query": "[RANK_NAME] with badge [BADGE] requesting sector-4 frequency logs",
  "llm_summary": "Request for sector-4 frequency logs from an identified operator.",
  "llm_provider": "ollama (on-premise)",
  "model": "llama3.2"
}
```

### Verify Audit Chain Integrity

```bash
curl http://localhost:8000/gateway/audit/verify \
  -H "X-API-Key: mcpilot-dev-key-001"
```

```json
{
  "is_valid": true,
  "records_checked": 42,
  "broken_links": []
}
```

---

## Compliance

| Framework | Coverage |
|---|---|
| **DPDP Act 2023 (India)** | PII redaction, data retention policy, right-to-erasure stubs |
| **HIPAA** | Audit log retention (7 years), PHI detection, access controls |
| **GDPR** | Pseudonymisation, erasure requests, processing basis documentation |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Gateway | FastAPI · Python 3.11 · Uvicorn |
| Routing | LlamaIndex · ChromaDB · HuggingFace BGE |
| PII Detection | spaCy NER · Ollama LLM (hybrid pipeline) |
| Database | PostgreSQL · SQLAlchemy · Alembic |
| Auth | JWT · API Keys · Multi-tenant isolation |
| LLM (on-premise) | Ollama · llama3.2 · llama3.1:8b |
| Observability | WebSocket · Real-time metrics dashboard |
| CI/CD | GitHub Actions |

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/gateway/query` | POST | Natural language query with PII redaction |
| `/gateway/tool` | POST | Direct MCP tool invocation |
| `/gateway/audit` | GET | Recent audit log entries |
| `/gateway/audit/verify` | GET | Verify hash chain integrity |
| `/metrics/summary` | GET | Aggregated system metrics |
| `/metrics/ws` | WS | Real-time WebSocket metrics stream |
| `/compliance/erasure` | POST | GDPR/DPDP right-to-erasure request |
| `/compliance/retention` | GET | Data retention policy |
| `/admin/tenants` | POST | Create tenant (admin) |
| `/admin/api-keys` | POST | Issue API key (admin) |
| `/docs` | GET | Interactive API documentation |

---

## Development

```bash
# Run all tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests (requires echo server)
pytest tests/integration/ -v
```

**Test coverage:** 134 unit tests · 17 integration tests · 151 total

---

## Roadmap

- [x] MCP gateway with semantic routing
- [x] PII detection pipeline (spaCy + LLM hybrid)
- [x] Immutable audit log with hash chaining
- [x] Real-time observability dashboard (WebSocket)
- [x] Multi-tenant isolation with DB-backed API keys
- [x] GDPR / DPDP Act compliance hooks
- [ ] Voice layer — Whisper STT + Piper TTS (v1.1)
- [ ] GuardrailsAI integration (v1.1)
- [ ] DRDO Technology Development Fund application

---

## Contributing

Contributions are welcome. Please read [docs/contributing/getting-started.md](docs/contributing/getting-started.md) before submitting a PR.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

<div align="center">

Built in India 🇮🇳 · Indigenous AI for critical systems

*MCPilot is designed for environments where security, compliance, and data sovereignty are non-negotiable.*

</div>