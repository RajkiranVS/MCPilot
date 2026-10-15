"""
MCPilot — On-prem LLM helper for MCP servers
Narrative summaries from the local Ollama model. Shared by the healthcare and
BFSI servers, which run as standalone STDIO subprocesses (no app.* imports).

The gateway PHI/PII-redacts tool inputs before a server sees them, and the
model runs on this host, so no document content leaves the facility.
"""
import os


async def local_llm_summary(prompt: str, max_tokens: int = 500) -> dict:
    """
    Run `prompt` against the local Ollama model.
    Never raises: returns status UNAVAILABLE so rule-based output still ships.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider != "ollama":
        return {"status": "UNAVAILABLE", "reason": f"LLM_PROVIDER={provider} — local summary disabled"}

    url   = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=float(os.getenv("LOCAL_LLM_TIMEOUT", "120"))) as client:
            resp = await client.post(f"{url}/api/generate", json={
                "model":   model,
                "prompt":  prompt,
                "stream":  False,
                "options": {"temperature": 0.1, "num_predict": max_tokens, "num_ctx": 4096},
            })
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
        if not text:
            return {"status": "UNAVAILABLE", "reason": "Model returned an empty response"}
        return {"status": "OK", "model": model, "provider": "ollama (on-prem)", "text": text}
    except Exception as e:
        return {"status": "UNAVAILABLE", "reason": f"Local model not reachable: {type(e).__name__}"}
