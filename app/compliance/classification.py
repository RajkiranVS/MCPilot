"""
MCPilot — Classification-Aware Data Gating Layer
================================================
Implements defence-grade classification levels and clearance registry
for need-to-know enforcement across MCP tool calls.

Architecture:
  ClassificationLevel  — enum of data sensitivity tiers (UNCLASSIFIED → TOP_SECRET)
  ClearanceLevel       — enum of operator/system clearance tiers (mirrors Classification)
  ClassificationPolicy — rules for what happens when levels don't match
  ClearanceRegistry    — maps tenant_id + server_id → maximum clearance level
  ClassificationResult — outcome of a gating decision with audit trail

Usage in gateway.py:
  from app.compliance.classification import registry, GatingDecision
  decision = registry.gate(
      requestor_tenant="navy-ops",
      target_server="sigint_server",
      data_classification=ClassificationLevel.SECRET,
  )
  if decision.denied:
      raise HTTPException(403, detail=decision.reason)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICATION LEVELS
# Ordered numerically so comparisons work naturally:
#   ClassificationLevel.SECRET > ClassificationLevel.CONFIDENTIAL  → True
# ══════════════════════════════════════════════════════════════════════════════

class ClassificationLevel(IntEnum):
    """
    Data classification tiers — applied to tool responses and data blocks.
    Mirrors Indian defence classification doctrine:
      UNCLASSIFIED  — public / open source data (AIS, PANS, weather)
      RESTRICTED    — limited distribution, no foreign nationals
      CONFIDENTIAL  — unit-level sensitive (force disposition, logistics)
      SECRET        — operational plans, HUMINT, SIGINT-derived
      TOP_SECRET    — strategic intelligence, nuclear, special access
    """
    UNCLASSIFIED = 0
    RESTRICTED   = 1
    CONFIDENTIAL = 2
    SECRET       = 3
    TOP_SECRET   = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ")

    @property
    def colour(self) -> str:
        """UI colour code for dashboards."""
        return {
            0: "#00FF88",   # green
            1: "#F5A623",   # amber
            2: "#00AAFF",   # blue
            3: "#FF8800",   # orange
            4: "#FF3344",   # red
        }[self.value]

    @classmethod
    def from_str(cls, s: str) -> "ClassificationLevel":
        """Parse from string, case-insensitive."""
        try:
            return cls[s.upper().replace(" ", "_")]
        except KeyError:
            raise ValueError(f"Unknown classification level: {s!r}")


# ══════════════════════════════════════════════════════════════════════════════
# CLEARANCE LEVELS
# Mirrors ClassificationLevel — an operator/system cleared at SECRET
# can access data up to and including SECRET.
# ══════════════════════════════════════════════════════════════════════════════

class ClearanceLevel(IntEnum):
    """
    Operator / system clearance tiers.
    A clearance of X grants access to data classified at X or below.
    """
    UNCLASSIFIED = 0
    RESTRICTED   = 1
    CONFIDENTIAL = 2
    SECRET       = 3
    TOP_SECRET   = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ")

    @classmethod
    def from_str(cls, s: str) -> "ClearanceLevel":
        try:
            return cls[s.upper().replace(" ", "_")]
        except KeyError:
            raise ValueError(f"Unknown clearance level: {s!r}")

    def can_access(self, data_level: ClassificationLevel) -> bool:
        """True if this clearance permits access to data at data_level."""
        return self.value >= data_level.value


# ══════════════════════════════════════════════════════════════════════════════
# CLASSIFICATION POLICY
# ══════════════════════════════════════════════════════════════════════════════

class GatingAction(str):
    """What to do when clearance doesn't match classification."""
    PASS    = "PASS"     # clearance ≥ classification → full access
    REDACT  = "REDACT"   # clearance is one level below → redact sensitive fields
    DENY    = "DENY"     # clearance is two+ levels below → full denial


@dataclass
class GatingDecision:
    """
    Result of a classification gate check.
    Attached to every tool call response for audit purposes.
    """
    action:              str                        # PASS | REDACT | DENY
    requestor_tenant:    str
    target_server:       str
    requestor_clearance: ClearanceLevel
    data_classification: ClassificationLevel
    reason:              str
    timestamp:           str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    audit_hash:          str = field(default="")

    def __post_init__(self):
        self.audit_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Cryptographic hash of the gating decision for audit chain."""
        payload = json.dumps({
            "action":              self.action,
            "requestor_tenant":    self.requestor_tenant,
            "target_server":       self.target_server,
            "requestor_clearance": self.requestor_clearance.name,
            "data_classification": self.data_classification.name,
            "reason":              self.reason,
            "timestamp":           self.timestamp,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def denied(self) -> bool:
        return self.action == GatingAction.DENY

    @property
    def requires_redaction(self) -> bool:
        return self.action == GatingAction.REDACT

    @property
    def passed(self) -> bool:
        return self.action == GatingAction.PASS

    def to_dict(self) -> dict:
        return {
            "action":              self.action,
            "requestor_tenant":    self.requestor_tenant,
            "target_server":       self.target_server,
            "requestor_clearance": self.requestor_clearance.name,
            "data_classification": self.data_classification.name,
            "reason":              self.reason,
            "timestamp":           self.timestamp,
            "audit_hash":          self.audit_hash,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CLEARANCE REGISTRY
# Maps tenant_id + server_id → ClearanceLevel
# Defines the default classification of each MCP server's data
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ServerProfile:
    """
    Classification profile of an MCP server.
    Defines what classification level data this server typically produces.
    """
    server_id:              str
    name:                   str
    default_classification: ClassificationLevel
    description:            str = ""


@dataclass
class TenantProfile:
    """
    Clearance profile of a tenant (operator role / unit).
    Defines the maximum clearance level this tenant holds.
    """
    tenant_id:       str
    name:            str
    clearance:       ClearanceLevel
    unit:            str = ""
    description:     str = ""


class ClearanceRegistry:
    """
    Central registry of tenant clearances and server classification profiles.
    Called by the gateway on every tool invocation to enforce need-to-know.

    Usage:
        decision = registry.gate(
            requestor_tenant="icg-watchkeeper",
            target_server="maritime",
            data_classification=ClassificationLevel.RESTRICTED,
        )
    """

    def __init__(self):
        self._tenants: dict[str, TenantProfile]  = {}
        self._servers: dict[str, ServerProfile]  = {}
        self._load_defaults()

    def _load_defaults(self):
        """
        Load default tenant clearances and server profiles.
        In production this would load from a classified configuration
        store or HSM-backed secrets manager.
        """

        # ── DEFAULT SERVER PROFILES ───────────────────────────────────────────
        # Each MCP server is tagged with its typical data classification level.

        self.register_server(ServerProfile(
            server_id="echo",
            name="Echo Server",
            default_classification=ClassificationLevel.UNCLASSIFIED,
            description="Test server — unclassified data only",
        ))
        self.register_server(ServerProfile(
            server_id="maritime",
            name="Maritime Security Server",
            default_classification=ClassificationLevel.RESTRICTED,
            description="AIS tracks, PANS notices, vessel intelligence — RESTRICTED",
        ))
        self.register_server(ServerProfile(
            server_id="intel",
            name="Intelligence Fusion Server",
            default_classification=ClassificationLevel.SECRET,
            description="Multi-source intelligence fusion — SECRET",
        ))
        self.register_server(ServerProfile(
            server_id="sigint",
            name="SIGINT Processing Server",
            default_classification=ClassificationLevel.TOP_SECRET,
            description="Signals intelligence — TOP SECRET",
        ))
        self.register_server(ServerProfile(
            server_id="logistics",
            name="Logistics & Supply Chain Server",
            default_classification=ClassificationLevel.CONFIDENTIAL,
            description="Force disposition, readiness data — CONFIDENTIAL",
        ))
        self.register_server(ServerProfile(
            server_id="siepmu",
            name="SIEPMU Server (IAF)",
            default_classification=ClassificationLevel.SECRET,
            description="Secure information exchange — SECRET",
        ))
        self.register_server(ServerProfile(
            server_id="wargame",
            name="Wargaming Server (IAF)",
            default_classification=ClassificationLevel.SECRET,
            description="Operational wargaming — SECRET",
        ))

        # ── DEFAULT TENANT CLEARANCES ─────────────────────────────────────────
        # Dev tenant gets RESTRICTED for development purposes.
        # Production tenants reflect actual defence roles.

        self.register_tenant(TenantProfile(
            tenant_id="dev-tenant",
            name="Development Tenant",
            clearance=ClearanceLevel.RESTRICTED,
            unit="MCPilot Development",
            description="Local development — restricted clearance",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="icg-watchkeeper",
            name="ICG Watchkeeper",
            clearance=ClearanceLevel.RESTRICTED,
            unit="Indian Coast Guard",
            description="Coast Guard maritime watchkeeper — RESTRICTED",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="icg-ops",
            name="ICG Operations Officer",
            clearance=ClearanceLevel.CONFIDENTIAL,
            unit="Indian Coast Guard HQ",
            description="Coast Guard operations officer — CONFIDENTIAL",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="navy-ops",
            name="Navy Operations",
            clearance=ClearanceLevel.SECRET,
            unit="Indian Navy",
            description="Navy operations room — SECRET",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="navy-intel",
            name="Navy Intelligence",
            clearance=ClearanceLevel.TOP_SECRET,
            unit="Naval Intelligence Directorate",
            description="Naval intelligence officer — TOP SECRET",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="iaf-ops",
            name="IAF Operations",
            clearance=ClearanceLevel.SECRET,
            unit="Indian Air Force",
            description="IAF operations — SECRET",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="army-field",
            name="Army Field Commander",
            clearance=ClearanceLevel.CONFIDENTIAL,
            unit="Indian Army",
            description="Army field commander — CONFIDENTIAL",
        ))

        self.register_server(ServerProfile(
            server_id="bfsi",
            name="BFSI Intelligence Server",
            default_classification=ClassificationLevel.CONFIDENTIAL,
            description="Financial documents, KYC, credit risk — CONFIDENTIAL",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="bfsi-analyst",
            name="BFSI Analyst",
            clearance=ClearanceLevel.CONFIDENTIAL,
            unit="Banking & Financial Services",
            description="BFSI analyst — CONFIDENTIAL clearance",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="bfsi-compliance",
            name="BFSI Compliance Officer",
            clearance=ClearanceLevel.SECRET,
            unit="Compliance & Risk",
            description="Compliance officer — SECRET clearance",
        ))

        self.register_server(ServerProfile(
            server_id="healthcare",
            name="Healthcare Intelligence Server",
            default_classification=ClassificationLevel.CONFIDENTIAL,
            description="Patient records, clinical documents — CONFIDENTIAL",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="hospital-admin",
            name="Hospital Administrator",
            clearance=ClearanceLevel.CONFIDENTIAL,
            unit="Healthcare",
            description="Hospital admin — CONFIDENTIAL clearance",
        ))
        self.register_tenant(TenantProfile(
            tenant_id="tpa-analyst",
            name="TPA Claims Analyst",
            clearance=ClearanceLevel.RESTRICTED,
            unit="Insurance TPA",
            description="TPA claims analyst — RESTRICTED clearance",
        ))

    # ── Registration ──────────────────────────────────────────────────────────

    def register_server(self, profile: ServerProfile) -> None:
        self._servers[profile.server_id] = profile
        logger.debug(f"Server registered | id={profile.server_id} classification={profile.default_classification.name}")

    def register_tenant(self, profile: TenantProfile) -> None:
        self._tenants[profile.tenant_id] = profile
        logger.debug(f"Tenant registered | id={profile.tenant_id} clearance={profile.clearance.name}")

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get_tenant(self, tenant_id: str) -> Optional[TenantProfile]:
        return self._tenants.get(tenant_id)

    def get_server(self, server_id: str) -> Optional[ServerProfile]:
        return self._servers.get(server_id)

    def get_tenant_clearance(self, tenant_id: str) -> ClearanceLevel:
        """Return clearance level for tenant, defaulting to UNCLASSIFIED."""
        profile = self._tenants.get(tenant_id)
        if not profile:
            logger.warning(f"Unknown tenant '{tenant_id}' — defaulting to UNCLASSIFIED")
            return ClearanceLevel.UNCLASSIFIED
        return profile.clearance

    def get_server_classification(self, server_id: str) -> ClassificationLevel:
        """Return default classification for server, defaulting to RESTRICTED."""
        profile = self._servers.get(server_id)
        if not profile:
            logger.warning(f"Unknown server '{server_id}' — defaulting to RESTRICTED")
            return ClassificationLevel.RESTRICTED
        return profile.default_classification

    # ── Gating ───────────────────────────────────────────────────────────────

    def gate(
        self,
        requestor_tenant:    str,
        target_server:       str,
        data_classification: Optional[ClassificationLevel] = None,
    ) -> GatingDecision:
        """
        Core gating function — called on every tool invocation.

        Rules:
          clearance >= classification       → PASS
          clearance == classification - 1   → REDACT (one level below)
          clearance <  classification - 1   → DENY   (two+ levels below)

        Args:
            requestor_tenant:    tenant_id of the calling operator/system
            target_server:       server_id being invoked
            data_classification: override classification level (if known);
                                 defaults to server's registered level

        Returns:
            GatingDecision with action, reason and cryptographic audit hash
        """
        clearance       = self.get_tenant_clearance(requestor_tenant)
        classification  = data_classification or self.get_server_classification(target_server)
        level_gap       = classification.value - clearance.value

        if level_gap <= 0:
            # Clearance meets or exceeds classification — full access
            action = GatingAction.PASS
            reason = (
                f"Access granted — {clearance.label} clearance meets "
                f"{classification.label} classification requirement"
            )
        elif level_gap == 1:
            # One level below — allow with redaction of sensitive fields
            action = GatingAction.REDACT
            reason = (
                f"Partial access — {clearance.label} clearance is one level "
                f"below {classification.label} data. Sensitive fields redacted."
            )
        else:
            # Two or more levels below — full denial
            action = GatingAction.DENY
            reason = (
                f"Access denied — {clearance.label} clearance insufficient "
                f"for {classification.label} data (gap: {level_gap} levels)"
            )

        decision = GatingDecision(
            action=action,
            requestor_tenant=requestor_tenant,
            target_server=target_server,
            requestor_clearance=clearance,
            data_classification=classification,
            reason=reason,
        )

        # Emit log at appropriate level
        if decision.denied:
            logger.warning(
                f"GATING DENIED | tenant={requestor_tenant} server={target_server} "
                f"clearance={clearance.name} classification={classification.name} "
                f"hash={decision.audit_hash}"
            )
        elif decision.requires_redaction:
            logger.info(
                f"GATING REDACT | tenant={requestor_tenant} server={target_server} "
                f"clearance={clearance.name} classification={classification.name} "
                f"hash={decision.audit_hash}"
            )
        else:
            logger.debug(
                f"GATING PASS | tenant={requestor_tenant} server={target_server} "
                f"clearance={clearance.name} classification={classification.name}"
            )

        return decision

    def list_tenants(self) -> list[dict]:
        return [
            {
                "tenant_id":  t.tenant_id,
                "name":       t.name,
                "clearance":  t.clearance.name,
                "unit":       t.unit,
            }
            for t in self._tenants.values()
        ]

    def list_servers(self) -> list[dict]:
        return [
            {
                "server_id":      s.server_id,
                "name":           s.name,
                "classification": s.default_classification.name,
                "description":    s.description,
            }
            for s in self._servers.values()
        ]


# ── Singleton registry ────────────────────────────────────────────────────────
# Import this instance everywhere:
#   from app.compliance.classification import registry
registry = ClearanceRegistry()
