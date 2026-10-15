"""
MCPilot — PHI Client
Abstraction layer over PHI detection.

Runs entirely on-premise via the local spaCy pipeline — no PHI leaves the host.
"""
from app.compliance.phi_detector import detect, scan_dict, DetectionResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class PHIClient:
    """Unified interface for PHI detection."""

    def __init__(self):
        logger.info("PHI client using local spaCy pipeline")

    def detect(self, text: str) -> DetectionResult:
        """Detect and redact PHI in a text string."""
        return detect(text)

    def scan_dict(self, data: dict) -> tuple[dict, bool]:
        """Scan a dictionary for PHI in string values."""
        return scan_dict(data)

    async def detect_async(self, text: str) -> DetectionResult:
        """
        Async PHI detection — uses LLM for contextual detection.
        Use this for gateway requests where Ollama is available.
        """
        from app.compliance.phi_detector import detect_with_llm
        return await detect_with_llm(text)


# Module-level singleton
phi_client = PHIClient()