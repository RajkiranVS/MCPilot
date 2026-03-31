"""
MCPilot — Audit Log unit tests
Uses SQLite in-memory — no PostgreSQL required.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.base import Base
from app.db.repository import AuditLogRepository


@pytest_asyncio.fixture(scope="function")
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def repo(session):
    return AuditLogRepository(session)


@pytest.mark.asyncio
async def test_write_creates_record(repo, session):
    record = await repo.write(
        tenant_id="tenant-1",
        client_id="client-1",
        server_id="echo",
        tool_name="echo",
        status="ok",
    )
    await session.commit()
    assert record.id is not None
    assert record.tenant_id == "tenant-1"
    assert record.status == "ok"
    assert record.prev_hash == "GENESIS"
    assert len(record.record_hash) == 64


@pytest.mark.asyncio
async def test_hash_chain_links_records(repo, session):
    r1 = await repo.write(
        tenant_id="t1", client_id="c1",
        server_id="echo", tool_name="echo", status="ok",
    )
    await session.commit()

    r2 = await repo.write(
        tenant_id="t1", client_id="c1",
        server_id="echo", tool_name="ping", status="ok",
    )
    await session.commit()

    assert r2.prev_hash == r1.record_hash


@pytest.mark.asyncio
async def test_genesis_record_has_genesis_prev_hash(repo, session):
    record = await repo.write(
        tenant_id="t1", client_id="c1",
        server_id="echo", tool_name="echo", status="ok",
    )
    await session.commit()
    assert record.prev_hash == "GENESIS"


@pytest.mark.asyncio
async def test_pii_flags_recorded(repo, session):
    record = await repo.write(
        tenant_id="t1", client_id="c1",
        server_id="echo", tool_name="echo",
        pii_in_input=True, pii_in_output=False,
        redacted_count=2, status="ok",
    )
    await session.commit()
    assert record.pii_in_input is True
    assert record.pii_in_output is False
    assert record.redacted_count == 2


@pytest.mark.asyncio
async def test_list_recent_returns_records(repo, session):
    for i in range(3):
        await repo.write(
            tenant_id="t1", client_id="c1",
            server_id="echo", tool_name="echo", status="ok",
        )
    await session.commit()
    records = await repo.list_recent(tenant_id="t1")
    assert len(records) == 3


@pytest.mark.asyncio
async def test_list_recent_filters_by_tenant(repo, session):
    await repo.write(tenant_id="tenant-A", client_id="c1",
                     server_id="echo", tool_name="echo", status="ok")
    await repo.write(tenant_id="tenant-B", client_id="c1",
                     server_id="echo", tool_name="echo", status="ok")
    await session.commit()

    records = await repo.list_recent(tenant_id="tenant-A")
    assert len(records) == 1
    assert records[0].tenant_id == "tenant-A"


@pytest.mark.asyncio
async def test_verify_chain_valid(repo, session):
    for i in range(3):
        await repo.write(
            tenant_id="t1", client_id="c1",
            server_id="echo", tool_name="echo", status="ok",
        )
    await session.commit()
    result = await repo.verify_chain()
    assert result["is_valid"] is True
    assert result["records_checked"] == 3
    assert result["broken_links"] == []