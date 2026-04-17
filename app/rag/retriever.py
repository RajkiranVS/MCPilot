"""
MCPilot — RAG Tool Retriever
Semantic search over the indexed MCP tool schemas.

Takes a natural language intent string and returns
the most relevant tools with their server routing info.

This is the bridge between:
  - What the user/LLM wants to do (intent)
  - Which MCP server + tool to call (routing)
"""
from llama_index.core import VectorStoreIndex
from app.rag.indexer import tool_indexer
from app.core.logging import get_logger
import json

logger = get_logger(__name__)

DEFAULT_TOP_K = 3


def retrieve_tools(
    intent: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    Retrieve the top-k most semantically relevant tools for a given intent.

    Args:
        intent:  Natural language description of what needs to be done.
                 e.g. "read a file from disk" or "fetch a web page"
        top_k:   Number of results to return (default: 3)

    Returns:
        List of tool dicts with routing metadata, ranked by relevance:
        [
          {
            "server_id":    "filesystem",
            "tool_name":    "read_file",
            "description":  "Read the complete contents of a file.",
            "input_schema": {...},
            "score":        0.87,
          },
          ...
        ]

    Returns empty list if index is not ready.
    """
    if not tool_indexer.is_ready:
        logger.warning("RAG index not ready — returning empty results")
        return []

    retriever = tool_indexer.index.as_retriever(
        similarity_top_k=top_k,
    )

    nodes = retriever.retrieve(intent)

    results = []
    for node in nodes:
        meta = node.metadata
        try:
            input_schema = json.loads(meta.get("input_schema", "{}"))
        except json.JSONDecodeError:
            input_schema = {}

        results.append({
            "server_id":    meta.get("server_id", ""),
            "tool_name":    meta.get("tool_name", ""),
            "description":  meta.get("description", ""),
            "input_schema": input_schema,
            "score":        round(node.score or 0.0, 4),
        })

    logger.info(
        f"RAG retrieve | intent='{intent[:50]}' "
        f"top_k={top_k} results={len(results)}"
    )
    return results


def retrieve_best_tool(intent: str) -> dict | None:
    """
    Returns the single best matching tool for an intent.
    Returns None if no tools are indexed or no match found.
    Convenience wrapper around retrieve_tools().
    """
    results = retrieve_tools(intent, top_k=1)
    return results[0] if results else None