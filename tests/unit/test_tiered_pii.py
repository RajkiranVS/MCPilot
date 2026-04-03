"""
MCPilot — Tiered PII detection tests
Tests the novelty_check() and cache behaviour.
"""
import pytest
from app.compliance.phi_detector import detect, novelty_check
from app.compliance.cache import PIICache


# ── Novelty check — should NOT escalate ──────────────────────────────────────
def test_novelty_check_clean_text():
    result = detect("Requesting sector-4 frequency logs")
    assert novelty_check("Requesting sector-4 frequency logs", result) is False


def test_novelty_check_email_caught_by_spacy():
    text = "Send to john@example.com"
    result = detect(text)
    assert novelty_check(text, result) is False


def test_novelty_check_ssn_caught_by_regex():
    text = "SSN is 123-45-6789"
    result = detect(text)
    assert novelty_check(text, result) is False


def test_novelty_check_short_text():
    result = detect("hello")
    assert novelty_check("hello", result) is False


def test_novelty_check_phone_caught():
    text = "Call 555-123-4567"
    result = detect(text)
    assert novelty_check(text, result) is False


# ── Novelty check — SHOULD escalate ──────────────────────────────────────────
def test_novelty_check_rank_without_person():
    text = "Major Arjun is requesting access"
    result = detect(text)
    # spaCy may miss rank+name — novelty check should catch it
    if not any(e.label in {"PERSON", "RANK_NAME"} for e in result.entities):
        assert novelty_check(text, result) is True


def test_novelty_check_badge_without_entity():
    text = "Operator badge 778-334-2290 requesting access"
    result = detect(text)
    if not any(e.label in {"BADGE", "SSN"} for e in result.entities):
        assert novelty_check(text, result) is True


# ── Cache tests ───────────────────────────────────────────────────────────────
def test_cache_miss_returns_none():
    cache = PIICache()
    assert cache.get("some text") is None


def test_cache_set_and_get():
    cache = PIICache()
    result = detect("Patient John Smith")
    cache.set("Patient John Smith", result)
    cached = cache.get("Patient John Smith")
    assert cached is not None
    assert cached.phi_detected == result.phi_detected


def test_cache_different_text_returns_none():
    cache = PIICache()
    result = detect("Patient John Smith")
    cache.set("Patient John Smith", result)
    assert cache.get("Different text entirely") is None


def test_cache_stats_initial():
    cache = PIICache()
    stats = cache.stats()
    assert stats["size"] == 0
    assert stats["total_hits"] == 0
    assert stats["total_misses"] == 0


def test_cache_stats_after_miss():
    cache = PIICache()
    cache.get("text that isnt cached")
    assert cache.stats()["total_misses"] == 1


def test_cache_stats_after_hit():
    cache = PIICache()
    result = detect("John Smith")
    cache.set("John Smith", result)
    cache.get("John Smith")
    assert cache.stats()["total_hits"] == 1


def test_cache_evicts_when_full():
    cache = PIICache(max_size=3)
    result = detect("test")
    cache.set("text1", result)
    cache.set("text2", result)
    cache.set("text3", result)
    cache.set("text4", result)  # triggers eviction
    assert cache.stats()["size"] == 3


def test_cache_clear():
    cache = PIICache()
    result = detect("John Smith")
    cache.set("John Smith", result)
    cache.clear()
    assert cache.stats()["size"] == 0
    assert cache.get("John Smith") is None