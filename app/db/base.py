"""
MCPilot — Database Engine + Session Factory
Async SQLAlchemy setup for PostgreSQL (production) and SQLite (testing).
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """
    Create async SQLAlchemy engine.
    Uses DATABASE_URL from settings by default.
    Accepts override for testing (SQLite).
    """
    settings = get_settings()
    url = database_url or settings.database_url

    # SQLite for testing — no pool needed
    if url.startswith("sqlite"):
        return create_async_engine(
            url,
            echo=settings.debug,
            connect_args={"check_same_thread": False},
        )

    # PostgreSQL for production
    return create_async_engine(
        url,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # verify connections before use
    )


# Module-level engine and session factory
# Replaced at startup by init_db() with production settings
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def init_db(database_url: str | None = None) -> None:
    """Initialise engine and session factory. Called at app startup."""
    global _engine, _session_factory
    _engine = create_engine(database_url)
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("Database engine initialised")


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker:
    if _session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    return _session_factory


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields a database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session