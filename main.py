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
from app.routers import health, gateway

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment  : {settings.environment}")
    logger.info("MCP gateway initialising...")
    # TODO Week 2: init ChromaDB + LlamaIndex
    # TODO Week 3: warm SageMaker PHI endpoint
    logger.info(f"{settings.app_name} ready ✓")
    yield
    logger.info(f"{settings.app_name} shutting down...")


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