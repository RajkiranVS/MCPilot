"""
MCPilot — Database repository unit tests
Uses SQLite in-memory for fast, isolated tests.
No PostgreSQL required.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.base import Base
from app.db.repository import ToolRegistryRepository


@pytest_asyncio.fixture(scope="function")
async def session():
    """Fresh in-memory SQLite database per test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def repo(session):
    return ToolRegistryRepository(session)


# ── Server tests ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_upsert_server_creates_new(repo, session):
    server = await repo.upsert_server(
        server_id="echo",
        name="Echo Server",
        transport="stdio",
        command=["python", "echo_server.py"],
    )
    await session.commit()
    assert server.server_id == "echo"
    assert server.connected is False


@pytest.mark.asyncio
async def test_upsert_server_updates_existing(repo, session):
    await repo.upsert_server(
        server_id="echo",
        name="Echo Server",
        transport="stdio",
        command=["python", "echo_server.py"],
    )
    await session.commit()

    # Upsert again with new name
    server = await repo.upsert_server(
        server_id="echo",
        name="Echo Server v2",
        transport="stdio",
        command=["python", "echo_server.py"],
    )
    await session.commit()
    assert server.name == "Echo Server v2"


@pytest.mark.asyncio
async def test_set_server_connected(repo, session):
    await repo.upsert_server(
        server_id="echo",
        name="Echo Server",
        transport="stdio",
    )
    await session.commit()
    await repo.set_server_connected("echo", True)
    await session.commit()

    server = await repo.get_server("echo")
    assert server.connected is True


@pytest.mark.asyncio
async def test_list_servers_returns_enabled(repo, session):
    await repo.upsert_server("srv-1", "Server 1", "stdio")
    await repo.upsert_server("srv-2", "Server 2", "sse", url="http://example.com")
    await session.commit()

    servers = await repo.list_servers()
    assert len(servers) == 2


# ── Tool tests ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_tools_inserts_tools(repo, session):
    server = await repo.upsert_server("echo", "Echo Server", "stdio")
    await session.commit()

    tools = [
        {"name": "echo", "description": "Echoes text", "input_schema": {"properties": {"text": {"type": "string"}}}},
        {"name": "ping", "description": "Returns pong", "input_schema": {}},
    ]
    await repo.sync_tools(server, tools)
    await session.commit()

    refreshed = await repo.get_server("echo")
    assert len(refreshed.tools) == 2


@pytest.mark.asyncio
async def test_sync_tools_replaces_on_reconnect(repo, session):
    server = await repo.upsert_server("echo", "Echo Server", "stdio")
    await session.commit()

    await repo.sync_tools(server, [
        {"name": "echo", "description": "Echo", "input_schema": {}},
        {"name": "ping", "description": "Ping", "input_schema": {}},
    ])
    await session.commit()

    # Reconnect with only one tool
    await repo.sync_tools(server, [
        {"name": "echo", "description": "Echo", "input_schema": {}},
    ])
    await session.commit()

    refreshed = await repo.get_server("echo")
    assert len(refreshed.tools) == 1


@pytest.mark.asyncio
async def test_list_all_tools_only_connected(repo, session):
    s1 = await repo.upsert_server("echo", "Echo", "stdio")
    s2 = await repo.upsert_server("fetch", "Fetch", "stdio")
    await repo.set_server_connected("echo", True)
    # fetch stays disconnected
    await session.commit()

    await repo.sync_tools(s1, [{"name": "echo", "description": "Echo", "input_schema": {}}])
    await repo.sync_tools(s2, [{"name": "fetch", "description": "Fetch", "input_schema": {}}])
    await session.commit()

    tools = await repo.list_all_tools()
    assert len(tools) == 1
    assert tools[0]["server_id"] == "echo"


# ── Health event tests ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_record_health_event(repo, session):
    server = await repo.upsert_server("echo", "Echo", "stdio")
    await session.commit()

    await repo.record_health_event(server, "connected", latency_ms=42.5)
    await session.commit()

    events = await repo.list_health_events("echo")
    assert len(events) == 1
    assert events[0].event_type == "connected"
    assert events[0].latency_ms == 42.5


@pytest.mark.asyncio
async def test_health_events_append_only(repo, session):
    server = await repo.upsert_server("echo", "Echo", "stdio")
    await session.commit()

    await repo.record_health_event(server, "connected")
    await repo.record_health_event(server, "disconnected")
    await repo.record_health_event(server, "connected")
    await session.commit()

    events = await repo.list_health_events("echo")
    assert len(events) == 3