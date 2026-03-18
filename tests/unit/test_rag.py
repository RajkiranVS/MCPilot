"""
MCPilot — RAG Indexer + Retriever unit tests
No real MCP connections needed — tests use synthetic tool schemas.
"""
import pytest
from app.rag.indexer import MCPToolIndexer
from app.rag.retriever import retrieve_tools, retrieve_best_tool
from app.rag import tool_indexer


def make_tools() -> list[dict]:
    return [
        {
            "server_id":    "filesystem",
            "name":         "read_file",
            "description":  "Read the complete contents of a file from disk.",
            "input_schema": {
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "server_id":    "filesystem",
            "name":         "write_file",
            "description":  "Write content to a file on disk.",
            "input_schema": {
                "properties": {
                    "path":    {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "server_id":    "fetch",
            "name":         "fetch",
            "description":  "Fetch a URL from the internet and return its content.",
            "input_schema": {
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
        {
            "server_id":    "echo",
            "name":         "echo",
            "description":  "Echo the input text back unchanged.",
            "input_schema": {
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    ]


# ── Indexer tests ─────────────────────────────────────────────────────────────
def test_indexer_not_ready_before_build():
    indexer = MCPToolIndexer()
    assert indexer.is_ready is False


def test_indexer_ready_after_build():
    indexer = MCPToolIndexer()
    indexer.build(make_tools())
    assert indexer.is_ready is True


def test_indexer_build_empty_tools():
    indexer = MCPToolIndexer()
    indexer.build([])
    assert indexer.is_ready is False


def test_indexer_refresh_rebuilds_index():
    indexer = MCPToolIndexer()
    indexer.build(make_tools())
    assert indexer.is_ready is True
    indexer.refresh(make_tools()[:2])
    assert indexer.is_ready is True


# ── Retriever tests ───────────────────────────────────────────────────────────
def test_retrieve_returns_empty_when_not_ready():
    indexer = MCPToolIndexer()
    # Don't build — index not ready
    from app.rag import retriever as r
    original = r.tool_indexer
    r.tool_indexer = indexer
    results = retrieve_tools("read a file")
    r.tool_indexer = original
    assert results == []


def test_retrieve_returns_results_after_build():
    indexer = MCPToolIndexer()
    indexer.build(make_tools())
    from app.rag import retriever as r
    original = r.tool_indexer
    r.tool_indexer = indexer
    results = retrieve_tools("read a file from disk", top_k=2)
    r.tool_indexer = original
    assert len(results) > 0
    assert len(results) <= 2


def test_retrieve_result_shape():
    indexer = MCPToolIndexer()
    indexer.build(make_tools())
    from app.rag import retriever as r
    original = r.tool_indexer
    r.tool_indexer = indexer
    results = retrieve_tools("fetch a web page", top_k=1)
    r.tool_indexer = original
    assert len(results) == 1
    result = results[0]
    assert "server_id"    in result
    assert "tool_name"    in result
    assert "description"  in result
    assert "input_schema" in result
    assert "score"        in result


def test_retrieve_best_tool_returns_single():
    indexer = MCPToolIndexer()
    indexer.build(make_tools())
    from app.rag import retriever as r
    original = r.tool_indexer
    r.tool_indexer = indexer
    result = retrieve_best_tool("echo some text")
    r.tool_indexer = original
    assert result is not None
    assert isinstance(result, dict)
    assert result["tool_name"] is not None


def test_retrieve_best_tool_none_when_not_ready():
    indexer = MCPToolIndexer()
    from app.rag import retriever as r
    original = r.tool_indexer
    r.tool_indexer = indexer
    result = retrieve_best_tool("read a file")
    r.tool_indexer = original
    assert result is None