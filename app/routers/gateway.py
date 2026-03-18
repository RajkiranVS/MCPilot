from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.core.logging import get_logger
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/gateway", tags=["Gateway"])
logger = get_logger(__name__)


class ToolCallRequest(BaseModel):
    server_id:  str
    tool_name:  str
    parameters: dict
    session_id: str | None = None


class ToolCallResponse(BaseModel):
    status:    str
    server_id: str
    tool_name: str
    result:    dict | None = None
    error:     str | None = None


@router.post("/tool", response_model=ToolCallResponse, summary="Invoke MCP tool")
@limiter.limit("30/minute")   # stricter limit on tool calls specifically
async def invoke_tool(
    payload: ToolCallRequest,
    request: Request,
) -> ToolCallResponse:
    manager = request.app.state.mcp_manager
    try:
        result = await manager.call_tool(
            server_id=payload.server_id,
            tool_name=payload.tool_name,
            parameters=payload.parameters,
        )
        logger.info(
            f"Tool call OK | server={payload.server_id} "
            f"tool={payload.tool_name} "
            f"tenant={getattr(request.state, 'tenant_id', 'unknown')}"
        )
        return ToolCallResponse(
            status="ok",
            server_id=payload.server_id,
            tool_name=payload.tool_name,
            result=result,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Tool call failed | {e}")
        raise HTTPException(status_code=500, detail=f"Tool call failed: {e}")


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
    """
    Semantic search over all registered MCP tools.
    Returns ranked tool matches for a natural language intent.
    """
    from app.rag.retriever import retrieve_tools
    results = retrieve_tools(intent, top_k=top_k)
    return {
        "intent": intent,
        "results": results,
        "total": len(results),
    }