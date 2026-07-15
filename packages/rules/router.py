"""Deterministic clause router — Master Spec §9.1.

Uses regex + keyword families to select candidate paragraphs for each
clause family, constraining LLM context and reducing hallucination.
"""

from __future__ import annotations

import re
from typing import Optional

# ── §9.1 Clause family regex patterns ──────────────────────────────────────
# Each entry is (clause_family_name, compiled_pattern)

ROUTE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("change_of_control", re.compile(
        r"(change\s+of\s+control|change\s+in\s+control|acquisition\s+of\s+control|"
        r"transfer\s+of\s+control|controlling\s+interest|beneficial\s+ownership)",
        re.IGNORECASE,
    )),
    ("assignability", re.compile(
        r"(assign|assignability|assignment|novation|subcontract(ing)?|"
        r"delegat(e|ion))\b",
        re.IGNORECASE,
    )),
    ("termination", re.compile(
        r"\b(terminat(e|ion|ing)|expir(e|ation|y)\s+of|dissolution)\b",
        re.IGNORECASE,
    )),
    ("notice", re.compile(
        r"\b(notice\s+period|notice\s+requirement|written\s+notice|"
        r"prior\s+notice|days[^\w]*(prior|written|notice))\b",
        re.IGNORECASE,
    )),
    ("automatic_renewal", re.compile(
        r"(auto(matic)?\s*renew|renew(ed|al)?\s+automatic|"
        r"evergreen|silently\s+renew|tacit\s+reconduction)",
        re.IGNORECASE,
    )),
    ("price_escalation", re.compile(
        r"\b(escalat(e|ion)|price\s+increase|rate\s+increase|"
        r"incremental\s+fee|surcharge|step[- ]?up)\b",
        re.IGNORECASE,
    )),
    ("liquidated_damages", re.compile(
        r"(liquidated\s+damages|ld\b|penalty\s+clause|"
        r"delay\s+damages|fixed\s+damages)",
        re.IGNORECASE,
    )),
    ("penalty", re.compile(
        r"\b(penal(t|ty|ize)|late\s+fee|default\s+interest|"
        r"consequential\s+damages)\b",
        re.IGNORECASE,
    )),
    ("stamp_duty", re.compile(
        r"(stamp\s*duty|stamp(ing)?\s*(sufficien|inadequ|requir|insufficien[t]?)|"
        r"(insufficien[t]?|inadequ|requir)\s+stamp(ing)?|"
        r"non[- ]?judicial|stamp\s+paper|duly\s+stamp)",
        re.IGNORECASE,
    )),
    ("arbitration", re.compile(
        r"\b(arbitra(tion|tor|te|ble)|arbitral\s+tribunal|"
        r"adr\b|alternate\s+dispute|arbitration\s+clause)\b",
        re.IGNORECASE,
    )),
    ("jurisdiction", re.compile(
        r"\b(jurisdiction|exclusive\s+jurisdiction|"
        r"governing\s+law|proper\s+law|forum|venue|seat\s+of\s+arbitration)\b",
        re.IGNORECASE,
    )),
    ("indemnity", re.compile(
        r"\b(indemn\w*|hold\s+harmless)\b",
        re.IGNORECASE,
    )),
    ("consequential_damages", re.compile(
        r"(consequential\s+damages|indirect\s+damages|"
        r"incidental\s+damages|special\s+damages|exclusion\s+of\s+damages)",
        re.IGNORECASE,
    )),
    ("lock_in", re.compile(
        r"\b(lock[- ]?in|lock-in\s+period|minimum\s+period|"
        r"non[- ]?cancellable|irrevocable\s+term)\b",
        re.IGNORECASE,
    )),
]


class ClauseRouter:
    """Deterministic regex router — selects candidate chunks by clause family.

    Spec §9.1: regex + keyword families operate on chunk text.
    """

    def __init__(self, patterns: Optional[list[tuple[str, re.Pattern]]] = None) -> None:
        self.patterns = patterns or ROUTE_PATTERNS

    def match(self, text: str) -> list[tuple[str, float]]:
        """Return list of (clause_family, score) for all matching families.

        Score is 1.0 when the pattern matches; sub-pattern matches could
        refine this in future (spec allows semantic scoring later).
        """
        results: list[tuple[str, float]] = []
        seen: set[str] = set()
        for family, pattern in self.patterns:
            if pattern.search(text):
                if family not in seen:
                    results.append((family, 1.0))
                    seen.add(family)
        return results

    def match_family(self, text: str, family: str) -> bool:
        """Return True if text matches the given clause family."""
        for f, pattern in self.patterns:
            if f == family:
                return bool(pattern.search(text))
        return False
