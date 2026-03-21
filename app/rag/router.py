"""
MCPilot — Semantic Router
Resolves a natural language intent to a specific server_id + tool_name.
Sits between the gateway router and MCPManager.

Routing modes:
  EXPLICIT  → client provides server_id + tool_name directly
  SEMANTIC  → client provides intent, RAG resolves server + tool
  HYBRID    → client provides server_id only, RAG resolves tool within that server
"""
from enum import Enum
from dataclasses import dataclass
from app.rag.retriever import retrieve_tools, retrieve_best_tool
from app.core.logging import get_logger

logger = get_logger(__name__)

# Minimum confidence score to accept a semantic match
CONFIDENCE_THRESHOLD = 0.4


class RoutingMode(str, Enum):
    EXPLICIT = "explicit"   # server_id + tool_name provided
    SEMANTIC = "semantic"   # intent provided, RAG resolves both
    HYBRID   = "hybrid"     # server_id provided, RAG resolves tool


@dataclass
class RoutingResult:
    server_id:    str
    tool_name:    str
    mode:         RoutingMode
    confidence:   float        # 0.0–1.0, 1.0 for explicit routing
    alternatives: list[dict]   # other candidate tools from RAG


def resolve_route(
    intent:    str | None = None,
    server_id: str | None = None,
    tool_name: str | None = None,
) -> RoutingResult:
    """
    Resolve the correct MCP server + tool for a request.

    Priority:
      1. If server_id + tool_name provided → EXPLICIT routing
      2. If server_id only → HYBRID routing (RAG within server)
      3. If intent only → SEMANTIC routing (RAG across all servers)
      4. If none provided → raises ValueError

    Args:
        intent:    Natural language description of the task
        server_id: Explicit server identifier (optional)
        tool_name: Explicit tool name (optional)

    Returns:
        RoutingResult with resolved server_id, tool_name, mode, confidence

    Raises:
        ValueError: If routing cannot be resolved
    """

    # ── Mode 1: Explicit routing ──────────────────────────────────────────────
    if server_id and tool_name:
        logger.debug(
            f"Explicit routing | server={server_id} tool={tool_name}"
        )
        return RoutingResult(
            server_id=server_id,
            tool_name=tool_name,
            mode=RoutingMode.EXPLICIT,
            confidence=1.0,
            alternatives=[],
        )

    # ── Mode 2: Hybrid routing (server known, tool unknown) ───────────────────
    if server_id and not tool_name:
        if not intent:
            raise ValueError(
                f"server_id '{server_id}' provided without tool_name. "
                "Provide either tool_name or intent to resolve the tool."
            )
        candidates = retrieve_tools(intent, top_k=5)
        # Filter to only tools on the specified server
        server_candidates = [
            c for c in candidates
            if c["server_id"] == server_id
        ]
        if not server_candidates:
            raise ValueError(
                f"No tools found on server '{server_id}' "
                f"matching intent: '{intent}'"
            )
        best = server_candidates[0]
        if best["score"] < CONFIDENCE_THRESHOLD:
            raise ValueError(
                f"Low confidence ({best['score']:.2f}) matching intent "
                f"'{intent}' to tools on server '{server_id}'. "
                f"Best match: {best['tool_name']}. "
                "Provide tool_name explicitly or rephrase intent."
            )
        logger.info(
            f"Hybrid routing | server={server_id} "
            f"tool={best['tool_name']} score={best['score']}"
        )
        return RoutingResult(
            server_id=server_id,
            tool_name=best["tool_name"],
            mode=RoutingMode.HYBRID,
            confidence=best["score"],
            alternatives=server_candidates[1:],
        )

    # ── Mode 3: Semantic routing (full RAG resolution) ────────────────────────
    if intent and not server_id:
        candidates = retrieve_tools(intent, top_k=5)
        if not candidates:
            raise ValueError(
                f"No tools found matching intent: '{intent}'. "
                "Ensure MCP servers are connected and the RAG index is built."
            )
        best = candidates[0]
        if best["score"] < CONFIDENCE_THRESHOLD:
            raise ValueError(
                f"Low confidence ({best['score']:.2f}) matching intent: "
                f"'{intent}'. Best match: "
                f"{best['server_id']}.{best['tool_name']}. "
                "Try rephrasing or use explicit server_id + tool_name."
            )
        logger.info(
            f"Semantic routing | intent='{intent[:50]}' "
            f"→ server={best['server_id']} tool={best['tool_name']} "
            f"score={best['score']}"
        )
        return RoutingResult(
            server_id=best["server_id"],
            tool_name=best["tool_name"],
            mode=RoutingMode.SEMANTIC,
            confidence=best["score"],
            alternatives=candidates[1:],
        )

    # ── No routing info provided ──────────────────────────────────────────────
    raise ValueError(
        "Cannot resolve route. Provide one of: "
        "(server_id + tool_name) for explicit routing, "
        "(intent) for semantic routing, or "
        "(server_id + intent) for hybrid routing."
    )