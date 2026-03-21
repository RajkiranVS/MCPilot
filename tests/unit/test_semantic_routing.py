"""
MCPilot — Semantic Routing unit tests
Tests resolve_route() across all three routing modes.
No HTTP calls — pure routing logic.
"""
import pytest
from app.rag.router import resolve_route, RoutingMode
from app.rag.indexer import MCPToolIndexer
from app.rag import retriever as r


TOOLS = [
    {
        "server_id":    "filesystem",
        "name":         "read_file",
        "description":  "Read the complete contents of a file from disk.",
        "input_schema": {"properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "server_id":    "filesystem",
        "name":         "write_file",
        "description":  "Write content to a file on disk.",
        "input_schema": {"properties": {"path": {"type": "string"}, "content": {"type": "string"}}},
    },
    {
        "server_id":    "fetch",
        "name":         "fetch",
        "description":  "Fetch a URL from the internet and return its content.",
        "input_schema": {"properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
    {
        "server_id":    "echo",
        "name":         "echo",
        "description":  "Echo the input text back unchanged.",
        "input_schema": {"properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
]


@pytest.fixture(scope="module")
def indexed_retriever():
    """Build a real index and swap the module-level retriever singleton."""
    indexer = MCPToolIndexer()
    indexer.build(TOOLS)
    original = r.tool_indexer
    r.tool_indexer = indexer
    yield
    r.tool_indexer = original


# ── Explicit routing ──────────────────────────────────────────────────────────
def test_explicit_routing_returns_exact_match():
    result = resolve_route(
        server_id="filesystem",
        tool_name="read_file",
    )
    assert result.server_id  == "filesystem"
    assert result.tool_name  == "read_file"
    assert result.mode       == RoutingMode.EXPLICIT
    assert result.confidence == 1.0
    assert result.alternatives == []


def test_explicit_routing_does_not_need_intent():
    result = resolve_route(server_id="echo", tool_name="echo")
    assert result.mode == RoutingMode.EXPLICIT
    assert result.confidence == 1.0


# ── Semantic routing ──────────────────────────────────────────────────────────
def test_semantic_routing_resolves_file_read(indexed_retriever):
    result = resolve_route(intent="read a file from disk")
    assert result.mode      == RoutingMode.SEMANTIC
    assert result.server_id == "filesystem"
    assert result.tool_name == "read_file"
    assert result.confidence > 0.4


def test_semantic_routing_resolves_fetch(indexed_retriever):
    result = resolve_route(intent="fetch content from a URL on the internet")
    assert result.mode      == RoutingMode.SEMANTIC
    assert result.server_id == "fetch"
    assert result.confidence > 0.4


def test_semantic_routing_resolves_echo(indexed_retriever):
    result = resolve_route(intent="echo some text back")
    assert result.mode      == RoutingMode.SEMANTIC
    assert result.server_id == "echo"
    assert result.tool_name == "echo"
    assert result.confidence > 0.4


def test_semantic_routing_returns_alternatives(indexed_retriever):
    result = resolve_route(intent="do something with a file")
    assert result.mode == RoutingMode.SEMANTIC
    assert isinstance(result.alternatives, list)


# ── Hybrid routing ────────────────────────────────────────────────────────────
def test_hybrid_routing_resolves_tool_within_server(indexed_retriever):
    result = resolve_route(
        server_id="filesystem",
        intent="read file contents",
    )
    assert result.mode      == RoutingMode.HYBRID
    assert result.server_id == "filesystem"
    assert result.tool_name in ["read_file", "write_file"]
    assert result.confidence > 0.4


def test_hybrid_routing_wrong_server_raises(indexed_retriever):
    with pytest.raises(ValueError, match="No tools found on server"):
        resolve_route(
            server_id="nonexistent-server",
            intent="read a file",
        )


# ── Error cases ───────────────────────────────────────────────────────────────
def test_no_routing_info_raises():
    with pytest.raises(ValueError, match="Cannot resolve route"):
        resolve_route()


def test_server_id_without_tool_or_intent_raises():
    with pytest.raises(ValueError, match="tool_name or intent"):
        resolve_route(server_id="filesystem")