"""Passage review contracts; heuristics prioritize review and never certify anonymity."""
from dataclasses import dataclass, field
from hashlib import sha256
import re
import unicodedata
from uuid import UUID

from .privacy import Replacement, ScrubbedDocument, scrub


@dataclass(frozen=True)
class Passage:
    id: int
    start: int
    end: int
    flags: tuple[str, ...]


@dataclass(frozen=True)
class ReviewPlan:
    course_id: str
    submission_id: str
    version: str = field(repr=False)
    source: str = field(repr=False)
    direct: ScrubbedDocument = field(repr=False)
    passages: tuple[Passage, ...] = ()


@dataclass(frozen=True)
class PrivacyResult:
    document: ScrubbedDocument | None = field(repr=False)
    holds: tuple[str, ...] = ()
    reviewer_id: str | None = None
    source_version: str | None = field(default=None, repr=False)


RULES = (
    ("health_or_disability", re.compile(r"\b(?:diagnosed|diagnosis|therapy|therapist|hospital|disability|medication|pregnant)\b", re.I)),
    ("family_or_legal", re.compile(r"\b(?:immigration|undocumented|arrested|abuse|custody|deported|prison)\b", re.I)),
    ("distinctive_location_or_role", re.compile(r"\b(?:only (?:student|person|child)|live at|work at|my address|my school|my employer)\b", re.I)),
)


def plan_review(text: str, course_id: str, submission_id: str, known_identifiers: tuple[str, ...] = ()) -> ReviewPlan:
    course_id, submission_id = str(UUID(course_id)), str(UUID(submission_id))
    if len(text) > 100_000:
        raise ValueError("input_limit")
    source = unicodedata.normalize("NFC", text)
    direct = scrub(source, known_identifiers)
    passages, offset = [], 0
    for paragraph in source.split("\n"):
        if paragraph.strip():
            flags = tuple(name for name, pattern in RULES if pattern.search(paragraph))
            if any(offset < r.original_end and offset + len(paragraph) > r.original_start for r in direct.replacements):
                flags += ("direct_identifier",)
            passages.append(Passage(len(passages) + 1, offset, offset + len(paragraph), flags))
        offset += len(paragraph) + 1
    if len(passages) > 2000:
        raise ValueError("passage_limit")
    return ReviewPlan(course_id, submission_id, sha256(source.encode()).hexdigest(), source, direct, tuple(passages))


def finalize_review(plan: ReviewPlan, current_text: str, course_id: str, submission_id: str,
                    reviewer_id: str, decisions: dict[int, str]) -> PrivacyResult:
    # The authenticated service must own plans/decisions and establish reviewer authority.
    # UUID binding here is a consistency contract, not a replacement for authorization.
    reviewer_id = str(UUID(reviewer_id))
    if (str(UUID(course_id)), str(UUID(submission_id))) != (plan.course_id, plan.submission_id):
        raise ValueError("review_scope_mismatch")
    current = unicodedata.normalize("NFC", current_text)
    if current != plan.source or sha256(current.encode()).hexdigest() != plan.version:
        raise ValueError("review_version_stale")
    if not plan.passages:
        return PrivacyResult(None, ("empty_document",))
    expected = {p.id for p in plan.passages}
    if not set(decisions).issubset(expected) or any(v not in {"retain", "redact", "hold"} for v in decisions.values()):
        raise ValueError("review_decision_invalid")
    if set(decisions) != expected or "hold" in decisions.values():
        return PrivacyResult(None, ("contextual_review_incomplete",))
    ranges = [(p.start, p.end, "CONTEXT") for p in plan.passages if decisions[p.id] == "redact"]
    ranges += [(r.original_start, r.original_end, r.category) for r in plan.direct.replacements
               if not any(start <= r.original_start and end >= r.original_end for start, end, _ in ranges)]
    ranges.sort()
    if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
        raise ValueError("redaction_overlap")
    output, replacements, cursor, length = [], [], 0, 0
    for index, (start, end, category) in enumerate(ranges, 1):
        prefix = plan.source[cursor:start]
        output.append(prefix); length += len(prefix)
        label = f"[{category}_{index}]"
        output.append(label)
        replacements.append(Replacement(start, end, length, length + len(label), category))
        length += len(label); cursor = end
    output.append(plan.source[cursor:])
    return PrivacyResult(ScrubbedDocument("".join(output), tuple(replacements), False), (), reviewer_id, plan.version)
