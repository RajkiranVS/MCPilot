"""
MCPilot — Gateway Router
BUILD-006: Semantic routing integrated.
Supports explicit, semantic, and hybrid routing modes.
"""
from app.compliance.pipeline import scan_input, scan_output
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.core.logging import get_logger
from app.middleware.rate_limit import limiter
from app.rag.router import resolve_route, RoutingMode
from app.core.config import get_settings
from app.compliance.audit import write_audit_record

settings = get_settings()
router = APIRouter(prefix="/gateway", tags=["Gateway"])
logger = get_logger(__name__)


class ToolCallRequest(BaseModel):
    server_id:  str | None = None
    tool_name:  str | None = None
    parameters: dict        = {}
    intent:     str | None = None
    session_id: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Explicit routing",
                    "value": {
                        "server_id": "filesystem",
                        "tool_name": "read_file",
                        "parameters": {"path": "./README.md"},
                    }
                },
                {
                    "title": "Semantic routing",
                    "value": {
                        "intent": "read a file from disk",
                        "parameters": {"path": "./README.md"},
                    }
                },
                {
                    "title": "Hybrid routing",
                    "value": {
                        "server_id": "filesystem",
                        "intent": "read a file",
                        "parameters": {"path": "./README.md"},
                    }
                },
            ]
        }
    }

class ToolCallResponse(BaseModel):
    status:       str
    server_id:    str
    tool_name:    str
    routing_mode: str          # explicit | semantic | hybrid
    confidence:   float        # 1.0 for explicit, 0.0–1.0 for semantic
    result:       dict | None = None
    error:        str | None  = None
    alternatives: list[dict]  = []  # other candidate tools from RAG


@router.post("/tool", response_model=ToolCallResponse, summary="Invoke MCP tool")
@limiter.limit("30/minute")
async def invoke_tool(
    payload: ToolCallRequest,
    request: Request,
) -> ToolCallResponse:
    manager = request.app.state.mcp_manager

    # ── Resolve route ─────────────────────────────────────────────────────────
    try:
        route = resolve_route(
            intent=payload.intent,
            server_id=payload.server_id,
            tool_name=payload.tool_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        f"Routing resolved | mode={route.mode} "
        f"server={route.server_id} tool={route.tool_name} "
        f"confidence={route.confidence} "
        f"tenant={getattr(request.state, 'tenant_id', 'unknown')}"
    )

    # ── Scan input parameters for PHI ─────────────────────────────────────────
    input_scan = scan_input(payload.parameters)
    if input_scan.phi_detected:
        logger.warning(
            f"PHI in input | server={route.server_id} "
            f"tool={route.tool_name} "
            f"tenant={getattr(request.state, 'tenant_id', 'unknown')}"
        )

    # ── Execute tool call with redacted parameters ────────────────────────────
    try:
        result = await manager.call_tool(
            server_id=route.server_id,
            tool_name=route.tool_name,
            parameters=input_scan.redacted,  # use redacted params
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Tool call failed | {e}")
        raise HTTPException(status_code=500, detail=f"Tool call failed: {e}")

    # ── Scan output for PHI ───────────────────────────────────────────────────
    output_scan = scan_output(result)
    if output_scan.phi_detected:
        logger.warning(
            f"PHI in output | server={route.server_id} "
            f"tool={route.tool_name} "
            f"tenant={getattr(request.state, 'tenant_id', 'unknown')}"
        )

    logger.info(
        f"Tool call OK | server={route.server_id} tool={route.tool_name} "
        f"phi_input={input_scan.phi_detected} "
        f"phi_output={output_scan.phi_detected}"
    )

    # ── Write audit record ────────────────────────────────────────────────────
    import time
    await write_audit_record(
        tenant_id=getattr(request.state, "tenant_id", "unknown"),
        client_id=getattr(request.state, "client_id", "unknown"),
        server_id=route.server_id,
        tool_name=route.tool_name,
        routing_mode=str(route.mode),
        session_id=payload.session_id,
        pii_in_input=input_scan.phi_detected,
        pii_in_output=output_scan.phi_detected,
        redacted_count=input_scan.redacted_count + output_scan.redacted_count,
        status="ok",
        latency_ms=float(
            request.headers.get("x-response-time-ms", 0) or 0
        ),
    )

    logger.info(
        f"Tool call OK | server={route.server_id} tool={route.tool_name} "
        f"pii_input={input_scan.phi_detected} "
        f"pii_output={output_scan.phi_detected}"
    )

    return ToolCallResponse(
        status="ok",
        server_id=route.server_id,
        tool_name=route.tool_name,
        routing_mode=route.mode,
        confidence=route.confidence,
        result=output_scan.redacted,
        alternatives=route.alternatives,
    )


@router.get("/servers", summary="List registered MCP servers")
async def list_servers(request: Request) -> dict:
    manager = request.app.state.mcp_manager
    return {"servers": manager.list_servers()}


@router.get("/tools", summary="List all tools across all servers")
async def list_tools(request: Request) -> dict:
    manager = request.app.state.mcp_manager
    tools = manager.get_all_tools()
    return {"tools": tools, "total": len(tools)}


@router.get("/tools/search", summary="Semantic tool search")
async def search_tools(
    intent: str,
    top_k: int = 3,
    request: Request = None,
) -> dict:
    from app.rag.retriever import retrieve_tools
    results = retrieve_tools(intent, top_k=top_k)
    return {
        "intent":  intent,
        "results": results,
        "total":   len(results),
    }

@router.post("/query", summary="Natural language query with local LLM")
async def natural_language_query(request: Request) -> dict:
    from app.core.llm import complete
    from app.compliance.pipeline import scan_input_async

    body = await request.json()
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query field required")

    # Run PII scan and LLM summary in parallel
    pii_task     = scan_input_async({"query": query})
    summary_task = complete(
        prompt=f"In one sentence, what is this request asking for: '{query}'",
        system="You are a helpful assistant that summarises requests concisely.",
        max_tokens=80,
    )

    # Wait for both simultaneously
    import asyncio
    input_scan, summary = await asyncio.gather(pii_task, summary_task)
    clean_query = input_scan.redacted.get("query", query)

    return {
        "query":        query,
        "phi_detected": input_scan.phi_detected,
        "clean_query":  clean_query,
        "llm_summary":  summary,
        "llm_provider": "ollama (on-premise)",
        "model":        settings.ollama_model,
    }

@router.get("/audit", summary="Recent audit log entries")
async def get_audit_log(
    limit: int = 20,
    request: Request = None,
) -> dict:
    """Returns recent audit log entries for the dashboard."""
    from app.db.base import get_session_factory
    from app.db.repository import AuditLogRepository

    tenant_id = getattr(request.state, "tenant_id", None)
    factory = get_session_factory()
    async with factory() as session:
        repo = AuditLogRepository(session)
        records = await repo.list_recent(tenant_id=tenant_id, limit=limit)
        return {
            "records": [
                {
                    "id":           r.id,
                    "tenant_id":    r.tenant_id,
                    "server_id":    r.server_id,
                    "tool_name":    r.tool_name,
                    "pii_detected": r.pii_in_input or r.pii_in_output,
                    "status":       r.status,
                    "latency_ms":   r.latency_ms,
                    "created_at":   r.created_at.isoformat(),
                    "record_hash":  r.record_hash[:16] + "...",
                }
                for r in records
            ],
            "total": len(records),
        }


@router.get("/audit/verify", summary="Verify audit log hash chain integrity")
async def verify_audit_chain() -> dict:
    """Verifies the tamper-proof hash chain of the audit log."""
    from app.db.base import get_session_factory
    from app.db.repository import AuditLogRepository

    factory = get_session_factory()
    async with factory() as session:
        repo = AuditLogRepository(session)
        return await repo.verify_chain()