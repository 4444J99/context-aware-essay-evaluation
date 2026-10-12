"""Bounded direct-identifier scrubber. Contextual privacy approval is always separate."""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class Replacement:
    original_start: int
    original_end: int
    scrubbed_start: int
    scrubbed_end: int
    category: str


@dataclass(frozen=True)
class ScrubbedDocument:
    text: str
    replacements: tuple[Replacement, ...]
    contextual_review_required: bool = True

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        """Map an unchanged scrubbed passage back; reject overlap with placeholders."""
        if not 0 <= start < end <= len(self.text):
            raise ValueError("invalid_span")
        if any(start < r.scrubbed_end and end > r.scrubbed_start for r in self.replacements):
            raise ValueError("span_intersects_redaction")
        delta_start = sum(
            (r.original_end-r.original_start)-(r.scrubbed_end-r.scrubbed_start)
            for r in self.replacements if r.scrubbed_end <= start
        )
        delta_end = sum(
            (r.original_end-r.original_start)-(r.scrubbed_end-r.scrubbed_start)
            for r in self.replacements if r.scrubbed_end <= end
        )
        return start + delta_start, end + delta_end


PATTERNS = (
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w-])")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?!\w)")),
    ("STUDENT_ID", re.compile(r"(?i)\b(?:student\s*(?:id|number)|sid)\s*[:#-]?\s*[A-Z0-9-]{4,}\b")),
)


def scrub(text: str, known_identifiers: tuple[str, ...] = ()) -> ScrubbedDocument:
    # Normalize before assigning offsets; normalized text is the document-version basis.
    if len(text) > 100_000 or len(known_identifiers) > 100 or any(len(value) > 256 for value in known_identifiers):
        raise ValueError("input_limit")
    text = unicodedata.normalize("NFC", text)
    if len(text) > 100_000 or len(known_identifiers) > 100:
        raise ValueError("input_limit")
    candidates = []

    def collect(pattern, category):
        for match in pattern.finditer(text):
            if len(candidates) >= 2000:
                raise ValueError("redaction_candidate_limit")
            candidates.append((match.start(), match.end(), category, match.group()))

    for identifier in known_identifiers:
        value = unicodedata.normalize("NFC", identifier).strip()
        if len(value) < 2:
            raise ValueError("identifier_too_short")
        pattern = re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)", re.IGNORECASE)
        collect(pattern, "PERSON")
    for category, pattern in PATTERNS:
        collect(pattern, category)
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    selected = []
    for item in candidates:
        if not selected or item[0] >= selected[-1][1]:
            selected.append(item)
    output = []
    spans = []
    labels = {}
    counters = {}
    cursor = 0
    output_length = 0
    for start, end, category, value in selected:
        prefix = text[cursor:start]
        output.append(prefix)
        output_length += len(prefix)
        key = (category, value.casefold())
        if key not in labels:
            counters[category] = counters.get(category, 0) + 1
            labels[key] = f"[{category}_{counters[category]}]"
        label = labels[key]
        spans.append(Replacement(start, end, output_length, output_length+len(label), category))
        output.append(label)
        output_length += len(label)
        cursor = end
    output.append(text[cursor:])
    return ScrubbedDocument("".join(output), tuple(spans))
