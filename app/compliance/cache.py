"""
MCPilot — PII Detection Cache
In-memory LRU cache for LLM-based PII detection results.
Prevents repeated LLM calls for identical or seen inputs.

TTL: 1 hour (configurable)
Max: 1000 entries (oldest evicted when full)
"""
import hashlib
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from app.compliance.phi_detector import DetectionResult
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    result:     DetectionResult
    expires_at: datetime
    hits:       int = 0


class PIICache:
    def __init__(self, ttl_minutes: int = 60, max_size: int = 1000):
        self._store: dict[str, CacheEntry] = {}
        self._ttl      = timedelta(minutes=ttl_minutes)
        self._max_size = max_size
        self._total_hits   = 0
        self._total_misses = 0

    def get(self, text: str) -> DetectionResult | None:
        key = self._hash(text)
        entry = self._store.get(key)
        if entry and entry.expires_at > datetime.now(timezone.utc):
            entry.hits += 1
            self._total_hits += 1
            logger.debug(f"PII cache hit | key={key[:8]} hits={entry.hits}")
            return entry.result
        if key in self._store:
            del self._store[key]  # expired
        self._total_misses += 1
        return None

    def set(self, text: str, result: DetectionResult) -> None:
        if len(self._store) >= self._max_size:
            oldest = min(self._store, key=lambda k: self._store[k].expires_at)
            del self._store[oldest]
            logger.debug("PII cache evicted oldest entry")
        key = self._hash(text)
        self._store[key] = CacheEntry(
            result=result,
            expires_at=datetime.now(timezone.utc) + self._ttl,
        )
        logger.debug(f"PII cache set | key={key[:8]} size={len(self._store)}")

    def stats(self) -> dict:
        return {
            "size":         len(self._store),
            "max_size":     self._max_size,
            "total_hits":   self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate_pct": round(
                self._total_hits / max(1, self._total_hits + self._total_misses) * 100, 1
            ),
        }

    def clear(self) -> None:
        self._store.clear()

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]


# Module-level singleton
pii_cache = PIICache(ttl_minutes=60, max_size=1000)