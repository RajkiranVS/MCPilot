"""
MCPilot — Metrics + WebSocket Router
Serves real-time observability data to the dashboard.

Endpoints:
  GET  /metrics/summary    → aggregated stats
  GET  /metrics/events     → recent tool call feed
  GET  /metrics/latency    → latency series for graph
  GET  /metrics/health     → server health status
  WS   /metrics/ws         → WebSocket live stream
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from app.core.logging import get_logger

router = APIRouter(prefix="/metrics", tags=["Metrics"])
logger = get_logger(__name__)


@router.get("/summary", summary="Aggregated metrics summary")
async def get_summary(request: Request) -> dict:
    store = request.app.state.metrics
    return store.summary()


@router.get("/events", summary="Recent tool call events")
async def get_events(
    limit:   int = 20,
    request: Request = None,
) -> dict:
    store = request.app.state.metrics
    return {
        "events": store.recent_events(limit=limit),
        "total":  store.total_calls,
    }


@router.get("/latency", summary="Latency time series for graph")
async def get_latency_series(
    limit:   int = 50,
    request: Request = None,
) -> dict:
    store = request.app.state.metrics
    return {
        "series": store.latency_series(limit=limit),
        "avg_ms": store.avg_latency_ms,
    }


@router.get("/health", summary="MCP server health status")
async def get_server_health(request: Request) -> dict:
    manager = request.app.state.mcp_manager
    servers = manager.list_servers()
    return {
        "servers":   servers,
        "connected": sum(1 for s in servers if s.get("connected")),
        "total":     len(servers),
    }


@router.websocket("/ws")
async def metrics_websocket(websocket: WebSocket):
    """
    WebSocket endpoint — accepts api_key as query param for browser clients.
    Browsers cannot send custom headers on WS connections so key goes in URL.
    """
    # Read query param directly — Query() injection is unreliable for WS endpoints
    api_key = websocket.query_params.get("api_key", "")
    valid_keys = {"mcpilot-dev-key-001", "mcpilot-dev-key-002"}
    if api_key not in valid_keys:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    store = websocket.app.state.metrics
    store.subscribe(websocket)
    logger.info("WebSocket client connected to metrics stream")

    try:
        while True:
            snapshot = {
                "type":    "snapshot",
                "summary": store.summary(),
                "events":  store.recent_events(limit=10),
                "latency": store.latency_series(limit=30),
            }
            await websocket.send_json(snapshot)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        store.unsubscribe(websocket)