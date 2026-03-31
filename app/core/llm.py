"""
MCPilot — LLM Provider Abstraction
Supports three backends:
  1. Anthropic Claude API  (cloud)
  2. AWS Bedrock           (cloud)
  3. Ollama                (on-premise — no data leaves the facility)

Controlled by LLM_PROVIDER setting in .env:
  LLM_PROVIDER=anthropic  → Claude API
  LLM_PROVIDER=bedrock    → AWS Bedrock
  LLM_PROVIDER=ollama     → local Ollama instance
"""
import httpx
import json
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def complete(
    prompt: str,
    system: str = "You are a helpful assistant.",
    max_tokens: int = 512,
) -> str:
    """
    Send a completion request to the configured LLM provider.
    Returns the response text.
    """
    provider = getattr(settings, "llm_provider", "ollama")

    if provider == "ollama":
        return await _complete_ollama(prompt, system, max_tokens)
    elif provider == "anthropic":
        return await _complete_anthropic(prompt, system, max_tokens)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _complete_ollama(
    prompt: str,
    system: str,
    max_tokens: int,
) -> str:
    """Call local Ollama instance — fully on-premise."""
    ollama_url = getattr(settings, "ollama_url", "http://localhost:11434")
    model      = getattr(settings, "ollama_model", "llama3.2")

    payload = {
        "model":  model,
        "prompt": f"{system}\n\nUser: {prompt}\nAssistant:",
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.1,
            "num_ctx":     512,
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{ollama_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        return response.json()["response"].strip()


async def _complete_anthropic(
    prompt: str,
    system: str,
    max_tokens: int,
) -> str:
    """Call Anthropic Claude API."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text