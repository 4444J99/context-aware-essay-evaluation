"""Deterministic rubric, evidence, release, and retention contracts."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class ContractError(ValueError):
    """A machine-readable contract failure; never include student content."""


@dataclass(frozen=True)
class Criterion:
    id: str
    maximum: Decimal
    weight: Decimal


@dataclass(frozen=True)
class Rubric:
    version: str
    criteria: tuple[Criterion, ...]

    def __post_init__(self):
        if not self.version or not self.criteria:
            raise ContractError("rubric_empty")
        ids = [c.id for c in self.criteria]
        if any(not key for key in ids) or len(set(ids)) != len(ids):
            raise ContractError("criterion_id_invalid")
        for c in self.criteria:
            if not c.maximum.is_finite() or not c.weight.is_finite():
                raise ContractError("rubric_nonfinite")
            if c.maximum <= 0 or c.weight <= 0:
                raise ContractError("rubric_range_invalid")
        if sum(c.weight for c in self.criteria) != Decimal("1"):
            raise ContractError("weights_must_sum_to_one")

    def total(self, scores: dict[str, Decimal]) -> Decimal:
        if set(scores) != {c.id for c in self.criteria}:
            raise ContractError("criterion_coverage_mismatch")
        total = Decimal("0")
        for c in self.criteria:
            value = scores[c.id]
            if not value.is_finite() or value < 0 or value > c.maximum:
                raise ContractError("score_out_of_range")
            total += value / c.maximum * c.weight * 100
        return total.quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Evidence:
    document_version: str
    start: int
    end: int
    quote: str

    def validate(self, text: str, version: str) -> bool:
        # Half-open Unicode code-point offsets; no fuzzy quotation repair.
        return (
            self.document_version == version
            and 0 <= self.start < self.end <= len(text)
            and text[self.start:self.end] == self.quote
        )


@dataclass(frozen=True)
class ReleaseInputs:
    extraction_ok: bool = False
    identity_resolved: bool = False
    privacy_reviewed: bool = False
    evidence_valid: bool = False
    rubric_valid: bool = False
    route_qualified: bool = False
    scope_authorized: bool = False
    synthetic: bool = False


def release_holds(inputs: ReleaseInputs) -> tuple[str, ...]:
    gates = {
        "extraction_failed": inputs.extraction_ok,
        "identity_unresolved": inputs.identity_resolved,
        "privacy_review_required": inputs.privacy_reviewed,
        "evidence_invalid": inputs.evidence_valid,
        "rubric_invalid": inputs.rubric_valid,
        "route_unqualified": inputs.route_qualified,
        "scope_unauthorized": inputs.scope_authorized,
    }
    holds = [code for code, passed in gates.items() if not passed]
    if inputs.synthetic:
        holds.append("synthetic_demonstration_only")
    return tuple(holds)


class CacheMode(StrEnum):
    AFTER_RUN = "after_run"
    HOURS_24 = "hours_24"
    DAYS_7 = "days_7"
    TERM = "term"


@dataclass(frozen=True)
class RetentionPolicy:
    mode: CacheMode
    term_end: datetime
    grace_days: int = 7

    def __post_init__(self):
        if self.term_end.tzinfo is None or not 0 <= self.grace_days <= 90:
            raise ContractError("retention_policy_invalid")

    def cache_expires(self, now: datetime, completed: bool = True) -> datetime:
        if now.tzinfo is None:
            raise ContractError("timezone_required")
        term_limit = self.term_end + timedelta(days=self.grace_days)
        durations = {
            CacheMode.AFTER_RUN: timedelta(0) if completed else timedelta(hours=24),
            CacheMode.HOURS_24: timedelta(hours=24),
            CacheMode.DAYS_7: timedelta(days=7),
        }
        candidate = term_limit if self.mode == CacheMode.TERM else now + durations[self.mode]
        return min(candidate, term_limit)
