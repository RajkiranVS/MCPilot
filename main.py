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

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.routers import health, gateway, auth
from app.mcp import mcp_manager, registry, MCPServerConfig, TransportType

settings = get_settings()
setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    if settings.environment != "test":
        registry.register(MCPServerConfig(
            server_id="filesystem",
            name="MCP Filesystem Server",
            transport=TransportType.STDIO,
            command=["python", "-m", "mcp.server.filesystem", "."],
        ))
        logger.info("Connecting to MCP servers...")
        await mcp_manager.connect_all()
        connected = [s for s in mcp_manager.list_servers() if s["connected"]]
        logger.info(f"MCP servers connected: {len(connected)}")

    app.state.mcp_manager = mcp_manager
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

# Middleware — order matters, outermost runs first
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
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