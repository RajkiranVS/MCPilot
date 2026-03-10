"""
MCPilot — Gateway Router
MCP tool call routing. Stub until BUILD-003.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.logging import get_logger

router = APIRouter(prefix="/gateway", tags=["Gateway"])
logger = get_logger(__name__)


class ToolCallRequest(BaseModel):
    server_id: str
    tool_name: str
    parameters: dict
    session_id: str | None = None


class ToolCallResponse(BaseModel):
    status: str
    server_id: str
    tool_name: str
    result: dict | None = None
    error: str | None = None


@router.post("/tool", response_model=ToolCallResponse, summary="Invoke MCP tool")
async def invoke_tool(request: ToolCallRequest) -> ToolCallResponse:
    logger.info(f"Tool call: server={request.server_id} tool={request.tool_name}")
    # BUILD-003: MCP SDK routing goes here
    raise HTTPException(status_code=501, detail="MCP routing coming in BUILD-003")


@router.get("/servers", summary="List registered MCP servers")
async def list_servers() -> dict:
    # BUILD-007: PostgreSQL tool registry goes here
    return {"servers": [], "note": "Tool registry coming in BUILD-007"}