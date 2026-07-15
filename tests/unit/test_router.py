"""Tests for deterministic clause router — Master Spec §9.1.

Validates that regex patterns match representative clause variants and
correctly reject unrelated text (no false positives).

Clause families tested:
  - change_of_control (and variants)
  - arbitration
  - indemnification
  - liquidated damages (and variants)
  - stamp duty (and variants)
"""

from __future__ import annotations

import pytest

from packages.rules.router import ClauseRouter, ROUTE_PATTERNS


# ── Fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture
def router() -> ClauseRouter:
    """A fresh ClauseRouter instance using the default ROUTE_PATTERNS."""
    return ClauseRouter()


# ── Clause family text tables ────────────────────────────────────────────────
# Each entry: (text_to_match, expected_family, description)


CHANGE_OF_CONTROL_VARIANTS = [
    ("Upon any change of control of the Company...", "change_of_control"),
    ("In the event of a change in control of the Vendor...", "change_of_control"),
    ("Acquisition of control by a third party shall...", "change_of_control"),
    ("Transfer of control to an affiliate...", "change_of_control"),
    ("Any transaction resulting in a change of controlling interest...", "change_of_control"),
    ("Beneficial ownership of voting shares...", "change_of_control"),
    ("change of control of the service provider", "change_of_control"),
]

ARBITRATION_VARIANTS = [
    ("Any dispute shall be referred to arbitration...", "arbitration"),
    ("The arbitral tribunal shall consist of...", "arbitration"),
    ("The arbitrator shall be appointed by...", "arbitration"),
    ("The parties agree to arbitrate all disputes...", "arbitration"),
    ("Any arbitration clause shall be governed by...", "arbitration"),
    ("The seat of arbitration shall be...", "arbitration"),
    ("Disputes shall be resolved by adr...", "arbitration"),
    ("alternate dispute resolution mechanism", "arbitration"),
]

INDEMNITY_VARIANTS = [
    ("The Vendor shall indemnify the Company...", "indemnity"),
    ("Indemnification obligations shall survive...", "indemnity"),
    ("Each party agrees to hold harmless the other...", "indemnity"),
    ("The indemnitor shall defend any claim...", "indemnity"),
    ("Indemnitee shall provide prompt notice...", "indemnity"),
    ("Indemnity cap of INR 5,00,00,000...", "indemnity"),
]

LIQUIDATED_DAMAGES_VARIANTS = [
    ("Liquidated damages shall be payable at...", "liquidated_damages"),
    ("The LD amount is INR 50,000 per day...", "liquidated_damages"),
    ("Delay damages of INR 10,000 per week...", "liquidated_damages"),
    ("Fixed damages of INR 1,00,000 per event...", "liquidated_damages"),
    ("This penalty clause shall apply...", "liquidated_damages"),
    ("A penalty clause for breach of confidentiality...", "liquidated_damages"),
]

STAMP_DUTY_VARIANTS = [
    ("Stamp duty of INR 500 paid...", "stamp_duty"),
    ("Executed on stamp paper of INR 100...", "stamp_duty"),
    ("Non-judicial stamp paper of appropriate value...", "stamp_duty"),
    ("The stamping requirements under the Act...", "stamp_duty"),
    ("Duly stamped in accordance with...", "stamp_duty"),
    ("Insufficient stamping may render...", "stamp_duty"),
]

UNRELATED_TEXTS = [
    "The parties agree to the terms and conditions set forth herein.",
    "This agreement shall be effective from the date of signing.",
    "INR 10,00,000 shall be paid as consideration.",
    "The company shall maintain books of accounts.",
    "Force majeure shall excuse delay in performance.",
    "The address for correspondence shall be...",
    "Nothing in this agreement shall create a partnership.",
]


class TestClauseRouterMatch:
    """§9.1 — router.match() returns matching clause families."""

    @pytest.mark.parametrize("text,expected_family", CHANGE_OF_CONTROL_VARIANTS)
    def test_change_of_control_variants(self, router: ClauseRouter, text: str, expected_family: str) -> None:
        """All change-of-control variants are correctly routed."""
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert expected_family in families, f"Expected '{expected_family}' in matches for: {text!r}"

    @pytest.mark.parametrize("text,expected_family", ARBITRATION_VARIANTS)
    def test_arbitration_variants(self, router: ClauseRouter, text: str, expected_family: str) -> None:
        """All arbitration variants are correctly routed."""
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert expected_family in families, f"Expected '{expected_family}' in matches for: {text!r}"

    @pytest.mark.parametrize("text,expected_family", INDEMNITY_VARIANTS)
    def test_indemnity_variants(self, router: ClauseRouter, text: str, expected_family: str) -> None:
        """All indemnity variants are correctly routed."""
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert expected_family in families, f"Expected '{expected_family}' in matches for: {text!r}"

    @pytest.mark.parametrize("text,expected_family", LIQUIDATED_DAMAGES_VARIANTS)
    def test_liquidated_damages_variants(self, router: ClauseRouter, text: str, expected_family: str) -> None:
        """All liquidated damages variants are correctly routed."""
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert expected_family in families, f"Expected '{expected_family}' in matches for: {text!r}"

    @pytest.mark.parametrize("text,expected_family", STAMP_DUTY_VARIANTS)
    def test_stamp_duty_variants(self, router: ClauseRouter, text: str, expected_family: str) -> None:
        """All stamp duty variants are correctly routed."""
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert expected_family in families, f"Expected '{expected_family}' in matches for: {text!r}"


class TestClauseRouterNoFalsePositives:
    """§9.1 — router must not match on completely unrelated text."""

    @pytest.mark.parametrize("text", UNRELATED_TEXTS)
    def test_no_false_positives(self, router: ClauseRouter, text: str) -> None:
        """Unrelated legal boilerplate should produce zero matches."""
        matches = router.match(text)
        assert len(matches) == 0, f"Expected 0 matches for unrelated text: {text!r} — got {matches}"


class TestClauseRouterMatchSpecificity:
    """§9.1 — router correctly matches specific clause families."""

    def test_match_change_of_control_only(self, router: ClauseRouter) -> None:
        """Text containing only CoC language should match only CoC (and penalty)."""
        text = "Upon a change of control, the non-acquiring party may terminate."
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert "change_of_control" in families

    def test_multiple_families_in_one_text(self, router: ClauseRouter) -> None:
        """Text containing multiple clause keywords matches all relevant families."""
        text = (
            "Upon a change of control, the non-acquiring party may terminate "
            "upon thirty days written notice. Any dispute shall be referred to "
            "arbitration in Bengaluru."
        )
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert "change_of_control" in families
        assert "termination" in families
        assert "notice" in families
        assert "arbitration" in families

    def test_stamp_duty_and_arbitration(self, router: ClauseRouter) -> None:
        """Text mixing stamp duty and arbitration matches both."""
        text = "Stamp duty of INR 500 paid. Arbitration in Bengaluru."
        matches = router.match(text)
        families = {f for f, _ in matches}
        assert "stamp_duty" in families
        assert "arbitration" in families

    def test_match_returns_score(self, router: ClauseRouter) -> None:
        """Each match returns a (family, score) tuple with score 1.0."""
        text = "Change of control clause."
        matches = router.match(text)
        assert all(isinstance(s, float) and s == 1.0 for _, s in matches)


class TestClauseRouterMatchFamily:
    """§9.1 — router.match_family() checks a specific family."""

    def test_match_family_true(self, router: ClauseRouter) -> None:
        """match_family returns True when text matches the given family."""
        assert router.match_family("Arbitration in Bengaluru.", "arbitration") is True

    def test_match_family_false(self, router: ClauseRouter) -> None:
        """match_family returns False when text does not match."""
        assert router.match_family("Confidentiality obligations.", "arbitration") is False

    def test_match_family_unknown_family(self, router: ClauseRouter) -> None:
        """match_family returns False for a family name that does not exist."""
        assert router.match_family("Any text", "nonexistent_family") is False


class TestRoutePatternsConstants:
    """§9.1 — ROUTE_PATTERNS constant has expected structure."""

    def test_all_patterns_are_tuples(self) -> None:
        """Each entry in ROUTE_PATTERNS is a (str, Pattern) tuple."""
        for entry in ROUTE_PATTERNS:
            assert isinstance(entry, tuple) and len(entry) == 2
            name, pattern = entry
            assert isinstance(name, str)
            assert hasattr(pattern, "search")

    def test_all_family_names_are_unique(self) -> None:
        """No duplicate clause family names in the pattern list."""
        names = [name for name, _ in ROUTE_PATTERNS]
        assert len(names) == len(set(names)), f"Duplicate family names: {names}"
