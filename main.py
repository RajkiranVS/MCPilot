"""
MCPilot — Entry Point
Universal MCP Gateway with RAG + Healthcare Compliance

Week 1  → Scaffold + health         ← YOU ARE HERE
Week 2  → RAG tool discovery
Week 3  → Compliance + audit log
Week 4  → Observability dashboard
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import health, gateway, auth
from app.mcp import mcp_manager, registry, MCPServerConfig, TransportType
from app.rag import tool_indexer

settings = get_settings()
setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    if settings.environment != "test":
        # ── Filesystem MCP server ─────────────────────────────────────────
        registry.register(MCPServerConfig(
            server_id="filesystem",
            name="MCP Filesystem Server",
            transport=TransportType.STDIO,
            command=["uvx", "mcp-server-filesystem", "."],
        ))

        # ── Fetch MCP server ──────────────────────────────────────────────
        registry.register(MCPServerConfig(
            server_id="fetch",
            name="MCP Fetch Server",
            transport=TransportType.STDIO,
            command=["uvx", "mcp-server-fetch"],
        ))

        logger.info("Connecting to MCP servers...")
        await mcp_manager.connect_all()
        connected = [s for s in mcp_manager.list_servers() if s["connected"]]
        logger.info(f"MCP servers connected: {len(connected)}")

        # ── Build RAG tool index ──────────────────────────────────────────
        all_tools = mcp_manager.get_all_tools()
        if all_tools:
            logger.info(f"Building RAG index for {len(all_tools)} tools...")
            tool_indexer.build(all_tools)
            logger.info("RAG index ready ✓")
        else:
            logger.warning("No tools discovered — RAG index skipped")

    app.state.mcp_manager = mcp_manager
    app.state.tool_indexer = tool_indexer
    yield

    if settings.environment != "test":
        logger.info("Disconnecting MCP servers...")
        await mcp_manager.disconnect_all()

    logger.info(f"{settings.app_name} shutdown complete")

app = FastAPI(
    title=settings.app_name,
    description="Universal MCP Gateway with RAG + Healthcare Compliance",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Rate limiter state ────────────────────────────────────────────────────────
app.state.limiter = limiter

# ── Middleware (order matters — outermost runs first) ─────────────────────────
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler) # type: ignore
app.add_exception_handler(StarletteHTTPException, http_exception_handler) # type: ignore
app.add_exception_handler(RequestValidationError, validation_exception_handler) # type: ignore
app.add_exception_handler(Exception, unhandled_exception_handler)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(gateway.router)
app.include_router(auth.router)


@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    })


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return JSONResponse(status_code=204, content={})