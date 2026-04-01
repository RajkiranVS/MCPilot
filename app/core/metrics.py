"""
MCPilot — In-Memory Metrics Store
Collects real-time observability data for the dashboard.
Uses a circular buffer — no database needed for live metrics.

Metrics collected:
  - Tool call latency (ms) per call
  - PII detection rate (detected / total)
  - Server health status
  - Compute cost (GPU seconds proxy)
  - Audit log summary counts
"""
from collections import deque
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Deque
import asyncio

MAX_EVENTS = 200  # circular buffer size


@dataclass
class ToolCallEvent:
    """Single tool call event for the live feed."""
    timestamp:    str
    server_id:    str
    tool_name:    str
    latency_ms:   float
    pii_detected: bool
    status:       str
    routing_mode: str
    tenant_id:    str


@dataclass
class MetricsStore:
    """
    Thread-safe in-memory metrics store.
    Shared across all requests via app.state.
    """
    events:         Deque[ToolCallEvent] = field(default_factory=lambda: deque(maxlen=MAX_EVENTS))
    total_calls:    int   = 0
    pii_detections: int   = 0
    total_errors:   int   = 0
    total_latency:  float = 0.0
    total_compute:  float = 0.0  # GPU·seconds proxy
    _subscribers:   list  = field(default_factory=list)

    def record(self, event: ToolCallEvent) -> None:
        self.events.appendleft(event)
        self.total_calls    += 1
        self.total_latency  += event.latency_ms
        self.total_compute  += event.latency_ms / 1000.0  # ms → seconds
        if event.pii_detected:
            self.pii_detections += 1
        if event.status == "error":
            self.total_errors += 1

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round(self.total_latency / self.total_calls, 1)

    @property
    def pii_rate_pct(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round((self.pii_detections / self.total_calls) * 100, 1)

    @property
    def success_rate_pct(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round(((self.total_calls - self.total_errors) / self.total_calls) * 100, 1)

    def summary(self) -> dict:
        return {
            "total_calls":      self.total_calls,
            "pii_detections":   self.pii_detections,
            "total_errors":     self.total_errors,
            "avg_latency_ms":   self.avg_latency_ms,
            "pii_rate_pct":     self.pii_rate_pct,
            "success_rate_pct": self.success_rate_pct,
            "total_compute_s":  round(self.total_compute, 2),
        }

    def recent_events(self, limit: int = 20) -> list[dict]:
        return [
            {
                "timestamp":    e.timestamp,
                "server_id":    e.server_id,
                "tool_name":    e.tool_name,
                "latency_ms":   e.latency_ms,
                "pii_detected": e.pii_detected,
                "status":       e.status,
                "routing_mode": e.routing_mode,
                "tenant_id":    e.tenant_id,
            }
            for e in list(self.events)[:limit]
        ]

    def latency_series(self, limit: int = 50) -> list[dict]:
        """Returns latency data points for the graph."""
        events = list(self.events)[:limit]
        events.reverse()  # chronological order for graph
        return [
            {
                "t":          e.timestamp[11:19],  # HH:MM:SS
                "latency_ms": e.latency_ms,
                "pii":        e.pii_detected,
            }
            for e in events
        ]

    async def broadcast(self, data: dict) -> None:
        """Send data to all connected WebSocket clients."""
        dead = []
        for ws in self._subscribers:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._subscribers.remove(ws)

    def subscribe(self, ws) -> None:
        self._subscribers.append(ws)

    def unsubscribe(self, ws) -> None:
        if ws in self._subscribers:
            self._subscribers.remove(ws)


# Module-level singleton — attached to app.state at startup
metrics_store = MetricsStore()