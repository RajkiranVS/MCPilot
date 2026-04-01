"""
MCPilot — Tenant isolation unit tests
"""
import pytest
import pytest_asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.base import Base
from app.db.repository import TenantRepository


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
    return TenantRepository(session)


@pytest.mark.asyncio
async def test_create_tenant(repo, session):
    tenant = await repo.create_tenant("tenant-1", "Test Org")
    await session.commit()
    assert tenant.tenant_id == "tenant-1"
    assert tenant.name == "Test Org"
    assert tenant.active is True


@pytest.mark.asyncio
async def test_get_tenant(repo, session):
    await repo.create_tenant("tenant-1", "Test Org")
    await session.commit()
    tenant = await repo.get_tenant("tenant-1")
    assert tenant is not None
    assert tenant.name == "Test Org"


@pytest.mark.asyncio
async def test_get_nonexistent_tenant(repo, session):
    tenant = await repo.get_tenant("nonexistent")
    assert tenant is None


@pytest.mark.asyncio
async def test_list_tenants(repo, session):
    await repo.create_tenant("tenant-1", "Org One")
    await repo.create_tenant("tenant-2", "Org Two")
    await session.commit()
    tenants = await repo.list_tenants()
    assert len(tenants) == 2


@pytest.mark.asyncio
async def test_create_api_key(repo, session):
    await repo.create_tenant("tenant-1", "Test Org")
    await session.commit()
    api_key = await repo.create_api_key(
        tenant_id="tenant-1",
        client_id="client-1",
        raw_key="mcpilot-testkey-001",
    )
    await session.commit()
    assert api_key.key_prefix == "mcpilot-"
    assert api_key.active is True


@pytest.mark.asyncio
async def test_lookup_valid_api_key(repo, session):
    await repo.create_tenant("tenant-1", "Test Org")
    await session.commit()
    await repo.create_api_key(
        tenant_id="tenant-1",
        client_id="client-1",
        raw_key="mcpilot-testkey-001",
    )
    await session.commit()
    result = await repo.lookup_api_key("mcpilot-testkey-001")
    assert result is not None
    assert result["tenant_id"] == "tenant-1"
    assert result["client_id"] == "client-1"


@pytest.mark.asyncio
async def test_lookup_invalid_api_key(repo, session):
    await repo.create_tenant("tenant-1", "Test Org")
    await session.commit()
    result = await repo.lookup_api_key("invalid-key-000")
    assert result is None


@pytest.mark.asyncio
async def test_deactivate_api_key(repo, session):
    await repo.create_tenant("tenant-1", "Test Org")
    await session.commit()
    await repo.create_api_key(
        tenant_id="tenant-1",
        client_id="client-1",
        raw_key="mcpilot-testkey-001",
    )
    await session.commit()
    success = await repo.deactivate_api_key("mcpilot-", "tenant-1")
    await session.commit()
    assert success is True
    result = await repo.lookup_api_key("mcpilot-testkey-001")
    assert result is None


@pytest.mark.asyncio
async def test_tenant_isolation_in_api_keys(repo, session):
    """API keys from different tenants should be completely isolated."""
    await repo.create_tenant("tenant-A", "Org A")
    await repo.create_tenant("tenant-B", "Org B")
    await session.commit()
    await repo.create_api_key("tenant-A", "client-a", "mcpilot-keyAAA-001")
    await repo.create_api_key("tenant-B", "client-b", "mcpilot-keyBBB-001")
    await session.commit()
    result_a = await repo.lookup_api_key("mcpilot-keyAAA-001")
    result_b = await repo.lookup_api_key("mcpilot-keyBBB-001")
    assert result_a["tenant_id"] == "tenant-A"
    assert result_b["tenant_id"] == "tenant-B"
    assert result_a["tenant_id"] != result_b["tenant_id"]


@pytest.mark.asyncio
async def test_scopes_stored_correctly(repo, session):
    await repo.create_tenant("tenant-1", "Test Org")
    await session.commit()
    await repo.create_api_key(
        tenant_id="tenant-1",
        client_id="client-1",
        raw_key="mcpilot-testkey-001",
        scopes=["gateway:invoke", "admin"],
    )
    await session.commit()
    result = await repo.lookup_api_key("mcpilot-testkey-001")
    assert "gateway:invoke" in result["scopes"]
    assert "admin" in result["scopes"]