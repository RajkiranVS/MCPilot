"""
MCPilot — Classification Layer Tests
Tests for ClassificationLevel, ClearanceLevel, ClearanceRegistry and GatingDecision.
"""
import pytest
from app.compliance.classification import (
    ClassificationLevel,
    ClearanceLevel,
    ClearanceRegistry,
    GatingAction,
    GatingDecision,
    ServerProfile,
    TenantProfile,
)


# ══════════════════════════════════════════════════════════════════════════════
# ClassificationLevel tests
# ══════════════════════════════════════════════════════════════════════════════

class TestClassificationLevel:

    def test_ordering(self):
        assert ClassificationLevel.UNCLASSIFIED < ClassificationLevel.RESTRICTED
        assert ClassificationLevel.RESTRICTED   < ClassificationLevel.CONFIDENTIAL
        assert ClassificationLevel.CONFIDENTIAL < ClassificationLevel.SECRET
        assert ClassificationLevel.SECRET       < ClassificationLevel.TOP_SECRET

    def test_from_str(self):
        assert ClassificationLevel.from_str("secret")      == ClassificationLevel.SECRET
        assert ClassificationLevel.from_str("SECRET")      == ClassificationLevel.SECRET
        assert ClassificationLevel.from_str("top_secret")  == ClassificationLevel.TOP_SECRET
        assert ClassificationLevel.from_str("TOP SECRET")  == ClassificationLevel.TOP_SECRET

    def test_from_str_invalid(self):
        with pytest.raises(ValueError):
            ClassificationLevel.from_str("ULTRA_SECRET")

    def test_label(self):
        assert ClassificationLevel.TOP_SECRET.label == "TOP SECRET"
        assert ClassificationLevel.UNCLASSIFIED.label == "UNCLASSIFIED"

    def test_colour(self):
        assert ClassificationLevel.UNCLASSIFIED.colour == "#00FF88"
        assert ClassificationLevel.TOP_SECRET.colour   == "#FF3344"


# ══════════════════════════════════════════════════════════════════════════════
# ClearanceLevel tests
# ══════════════════════════════════════════════════════════════════════════════

class TestClearanceLevel:

    def test_can_access_equal(self):
        assert ClearanceLevel.SECRET.can_access(ClassificationLevel.SECRET)

    def test_can_access_above(self):
        assert ClearanceLevel.TOP_SECRET.can_access(ClassificationLevel.SECRET)
        assert ClearanceLevel.SECRET.can_access(ClassificationLevel.UNCLASSIFIED)

    def test_cannot_access_below(self):
        assert not ClearanceLevel.RESTRICTED.can_access(ClassificationLevel.SECRET)
        assert not ClearanceLevel.UNCLASSIFIED.can_access(ClassificationLevel.CONFIDENTIAL)

    def test_from_str(self):
        assert ClearanceLevel.from_str("confidential") == ClearanceLevel.CONFIDENTIAL


# ══════════════════════════════════════════════════════════════════════════════
# GatingDecision tests
# ══════════════════════════════════════════════════════════════════════════════

class TestGatingDecision:

    def _make_decision(self, action, clearance, classification):
        return GatingDecision(
            action=action,
            requestor_tenant="test-tenant",
            target_server="test-server",
            requestor_clearance=clearance,
            data_classification=classification,
            reason="test reason",
        )

    def test_pass_decision(self):
        d = self._make_decision(
            GatingAction.PASS,
            ClearanceLevel.SECRET,
            ClassificationLevel.SECRET,
        )
        assert d.passed
        assert not d.denied
        assert not d.requires_redaction

    def test_redact_decision(self):
        d = self._make_decision(
            GatingAction.REDACT,
            ClearanceLevel.RESTRICTED,
            ClassificationLevel.CONFIDENTIAL,
        )
        assert d.requires_redaction
        assert not d.passed
        assert not d.denied

    def test_deny_decision(self):
        d = self._make_decision(
            GatingAction.DENY,
            ClearanceLevel.UNCLASSIFIED,
            ClassificationLevel.SECRET,
        )
        assert d.denied
        assert not d.passed
        assert not d.requires_redaction

    def test_audit_hash_generated(self):
        d = self._make_decision(
            GatingAction.PASS,
            ClearanceLevel.SECRET,
            ClassificationLevel.SECRET,
        )
        assert len(d.audit_hash) == 16
        assert d.audit_hash.isalnum()

    def test_audit_hash_deterministic_same_timestamp(self):
        """Same inputs at same timestamp produce same hash."""
        import copy
        d1 = self._make_decision(GatingAction.PASS, ClearanceLevel.SECRET, ClassificationLevel.SECRET)
        d2 = copy.copy(d1)
        d2.timestamp = d1.timestamp
        assert d1._compute_hash() == d2._compute_hash()

    def test_to_dict(self):
        d = self._make_decision(GatingAction.PASS, ClearanceLevel.SECRET, ClassificationLevel.SECRET)
        result = d.to_dict()
        assert result["action"]              == GatingAction.PASS
        assert result["requestor_clearance"] == "SECRET"
        assert result["data_classification"] == "SECRET"
        assert "audit_hash" in result
        assert "timestamp"  in result


# ══════════════════════════════════════════════════════════════════════════════
# ClearanceRegistry tests
# ══════════════════════════════════════════════════════════════════════════════

class TestClearanceRegistry:

    @pytest.fixture
    def registry(self):
        """Fresh registry with defaults loaded."""
        return ClearanceRegistry()

    # ── Registration ──────────────────────────────────────────────────────────

    def test_default_tenants_loaded(self, registry):
        assert registry.get_tenant("dev-tenant")      is not None
        assert registry.get_tenant("icg-watchkeeper") is not None
        assert registry.get_tenant("navy-ops")        is not None
        assert registry.get_tenant("navy-intel")      is not None
        assert registry.get_tenant("iaf-ops")         is not None
        assert registry.get_tenant("army-field")      is not None

    def test_default_servers_loaded(self, registry):
        assert registry.get_server("echo")     is not None
        assert registry.get_server("maritime") is not None
        assert registry.get_server("intel")    is not None
        assert registry.get_server("sigint")   is not None
        assert registry.get_server("logistics")is not None

    def test_register_custom_tenant(self, registry):
        registry.register_tenant(TenantProfile(
            tenant_id="test-unit",
            name="Test Unit",
            clearance=ClearanceLevel.CONFIDENTIAL,
        ))
        assert registry.get_tenant("test-unit").clearance == ClearanceLevel.CONFIDENTIAL

    def test_register_custom_server(self, registry):
        registry.register_server(ServerProfile(
            server_id="test-server",
            name="Test Server",
            default_classification=ClassificationLevel.SECRET,
        ))
        assert registry.get_server("test-server").default_classification == ClassificationLevel.SECRET

    # ── Clearance lookups ─────────────────────────────────────────────────────

    def test_tenant_clearances(self, registry):
        assert registry.get_tenant_clearance("dev-tenant")      == ClearanceLevel.RESTRICTED
        assert registry.get_tenant_clearance("icg-watchkeeper") == ClearanceLevel.RESTRICTED
        assert registry.get_tenant_clearance("icg-ops")         == ClearanceLevel.CONFIDENTIAL
        assert registry.get_tenant_clearance("navy-ops")        == ClearanceLevel.SECRET
        assert registry.get_tenant_clearance("navy-intel")      == ClearanceLevel.TOP_SECRET
        assert registry.get_tenant_clearance("iaf-ops")         == ClearanceLevel.SECRET
        assert registry.get_tenant_clearance("army-field")      == ClearanceLevel.CONFIDENTIAL

    def test_server_classifications(self, registry):
        assert registry.get_server_classification("echo")      == ClassificationLevel.UNCLASSIFIED
        assert registry.get_server_classification("maritime")  == ClassificationLevel.RESTRICTED
        assert registry.get_server_classification("intel")     == ClassificationLevel.SECRET
        assert registry.get_server_classification("sigint")    == ClassificationLevel.TOP_SECRET
        assert registry.get_server_classification("logistics") == ClassificationLevel.CONFIDENTIAL

    def test_unknown_tenant_defaults_unclassified(self, registry):
        assert registry.get_tenant_clearance("unknown-tenant") == ClearanceLevel.UNCLASSIFIED

    def test_unknown_server_defaults_restricted(self, registry):
        assert registry.get_server_classification("unknown-server") == ClassificationLevel.RESTRICTED

    # ── Gating decisions ──────────────────────────────────────────────────────

    def test_gate_pass_equal_level(self, registry):
        """SECRET clearance → SECRET server = PASS"""
        decision = registry.gate("navy-ops", "intel")
        assert decision.passed
        assert decision.action == GatingAction.PASS

    def test_gate_pass_above_level(self, registry):
        """TOP_SECRET clearance → SECRET server = PASS"""
        decision = registry.gate("navy-intel", "intel")
        assert decision.passed

    def test_gate_pass_unclassified(self, registry):
        """Any clearance → UNCLASSIFIED server = PASS"""
        decision = registry.gate("dev-tenant", "echo")
        assert decision.passed

    def test_gate_redact_one_level_below(self, registry):
        """RESTRICTED clearance → CONFIDENTIAL server = REDACT"""
        decision = registry.gate("dev-tenant", "logistics")
        assert decision.requires_redaction
        assert decision.action == GatingAction.REDACT

    def test_gate_deny_two_levels_below(self, registry):
        """RESTRICTED clearance → SECRET server = DENY"""
        decision = registry.gate("dev-tenant", "intel")
        assert decision.denied
        assert decision.action == GatingAction.DENY

    def test_gate_deny_three_levels_below(self, registry):
        """RESTRICTED clearance → TOP_SECRET server = DENY"""
        decision = registry.gate("dev-tenant", "sigint")
        assert decision.denied

    def test_gate_icg_watchkeeper_maritime_pass(self, registry):
        """ICG watchkeeper (RESTRICTED) → maritime (RESTRICTED) = PASS"""
        decision = registry.gate("icg-watchkeeper", "maritime")
        assert decision.passed

    def test_gate_icg_watchkeeper_intel_deny(self, registry):
        """ICG watchkeeper (RESTRICTED) → intel (SECRET) = DENY"""
        decision = registry.gate("icg-watchkeeper", "intel")
        assert decision.denied

    def test_gate_navy_ops_maritime_pass(self, registry):
        """Navy ops (SECRET) → maritime (RESTRICTED) = PASS"""
        decision = registry.gate("navy-ops", "maritime")
        assert decision.passed

    def test_gate_navy_ops_sigint_redact(self, registry):
        """Navy ops (SECRET) → sigint (TOP_SECRET) = REDACT"""
        decision = registry.gate("navy-ops", "sigint")
        assert decision.requires_redaction

    def test_gate_army_field_sigint_deny(self, registry):
        """Army field (CONFIDENTIAL) → sigint (TOP_SECRET) = DENY"""
        decision = registry.gate("army-field", "sigint")
        assert decision.denied

    def test_gate_with_override_classification(self, registry):
        """Override classification overrides server default."""
        # maritime normally RESTRICTED, but this response is SECRET
        decision = registry.gate(
            "icg-watchkeeper",
            "maritime",
            data_classification=ClassificationLevel.SECRET,
        )
        assert decision.denied  # RESTRICTED clearance vs SECRET data

    def test_gate_decision_has_audit_hash(self, registry):
        decision = registry.gate("navy-ops", "intel")
        assert len(decision.audit_hash) == 16

    def test_gate_decision_has_timestamp(self, registry):
        decision = registry.gate("navy-ops", "intel")
        assert "T" in decision.timestamp  # ISO format

    def test_gate_reason_contains_level_names(self, registry):
        decision = registry.gate("dev-tenant", "intel")
        assert "RESTRICTED" in decision.reason
        assert "SECRET" in decision.reason

    # ── List methods ──────────────────────────────────────────────────────────

    def test_list_tenants(self, registry):
        tenants = registry.list_tenants()
        assert len(tenants) >= 6
        tenant_ids = [t["tenant_id"] for t in tenants]
        assert "navy-ops"        in tenant_ids
        assert "icg-watchkeeper" in tenant_ids

    def test_list_servers(self, registry):
        servers = registry.list_servers()
        assert len(servers) >= 5
        server_ids = [s["server_id"] for s in servers]
        assert "maritime" in server_ids
        assert "sigint"   in server_ids


# ══════════════════════════════════════════════════════════════════════════════
# Cross-service scenario tests (mirrors problem definition scenarios)
# ══════════════════════════════════════════════════════════════════════════════

class TestOperationalScenarios:
    """
    Tests mirror the four operational scenarios from the product definition:
    A: Secure multi-agency intelligence sharing
    B: Field communications across service systems
    C: Logistics coordination
    D: Surveillance data fusion
    """

    @pytest.fixture
    def registry(self):
        return ClearanceRegistry()

    def test_scenario_a_cross_service_sharing(self, registry):
        navy_to_maritime = registry.gate("navy-intel", "maritime")
        army_to_intel    = registry.gate("army-field",  "intel")
        icg_to_intel     = registry.gate("icg-watchkeeper", "intel")  # gap=2 → DENY

        assert navy_to_maritime.passed
        assert army_to_intel.requires_redaction   # CONFIDENTIAL vs SECRET — one level, REDACT
        assert icg_to_intel.denied                # RESTRICTED vs SECRET — two levels, DENY

    def test_scenario_b_unified_operational_picture(self, registry):
        """
        Scenario B: Navy ops building unified picture.
        Navy ops (S) can access maritime (R) and logistics (C) but not sigint (TS).
        """
        maritime  = registry.gate("navy-ops", "maritime")
        logistics = registry.gate("navy-ops", "logistics")
        sigint    = registry.gate("navy-ops", "sigint")

        assert maritime.passed
        assert logistics.passed
        assert sigint.requires_redaction   # one level below TS

    def test_scenario_c_logistics_gating(self, registry):
        maritime = registry.gate("army-field", "maritime")
        intel    = registry.gate("army-field", "intel")
        sigint   = registry.gate("army-field", "sigint")

        assert maritime.passed              # CONFIDENTIAL vs RESTRICTED — PASS
        assert intel.requires_redaction    # CONFIDENTIAL vs SECRET — one level, REDACT
        assert sigint.denied               # CONFIDENTIAL vs TOP_SECRET — two levels, DENY

    def test_scenario_d_sigint_contamination_prevention(self, registry):
        """
        Scenario D: SIGINT data (TS) must not reach CONFIDENTIAL COP.
        ICG ops (C) trying to access SIGINT-tagged data → DENY.
        ICG ops can access maritime (R) data → PASS.
        """
        sigint_data = registry.gate(
            "icg-ops", "maritime",
            data_classification=ClassificationLevel.TOP_SECRET,
        )
        maritime_data = registry.gate("icg-ops", "maritime")

        assert sigint_data.denied       # SIGINT contamination prevented
        assert maritime_data.passed     # Normal maritime data flows through
