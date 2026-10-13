"""Bounded in-memory TXT/DOCX/ZIP intake. No filenames or document text in errors."""
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePosixPath
import stat
import unicodedata
import zipfile

from defusedxml import ElementTree as XML

MAX_FILE = 1_048_576
MAX_ARCHIVE = 8 * MAX_FILE
MAX_EXPANDED = 8 * MAX_FILE
MAX_MEMBERS = 64
MAX_DOCUMENTS = 20
MAX_TEXT = 100_000
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ExtractionHold(ValueError):
    pass


@dataclass(frozen=True)
class Extracted:
    text: str = field(repr=False)
    paragraphs: tuple[tuple[int, int], ...]
    format: str


@dataclass(frozen=True)
class IntakeItem:
    ordinal: int
    format: str
    document: Extracted | None = field(repr=False)
    hold: str | None


def archive_members(data: bytes):
    if len(data) > MAX_ARCHIVE:
        raise ExtractionHold("archive_size_limit")
    try:
        archive = zipfile.ZipFile(BytesIO(data))
        members = archive.infolist()
        if len(members) > MAX_MEMBERS or sum(m.file_size for m in members) > MAX_EXPANDED:
            raise ExtractionHold("archive_expansion_limit")
        seen = set()
        for m in members:
            path = PurePosixPath(m.filename)
            if not m.filename or "\\" in m.filename or path.is_absolute() or any(part in {".", ".."} for part in m.filename.rstrip("/").split("/")) or ":" in m.filename or m.filename in seen:
                raise ExtractionHold("archive_path_invalid")
            seen.add(m.filename)
            if stat.S_ISLNK(m.external_attr >> 16) or m.flag_bits & 1 or m.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise ExtractionHold("archive_member_unsupported")
            if m.file_size > MAX_FILE or m.file_size > max(1, m.compress_size) * 100:
                raise ExtractionHold("archive_ratio_or_member_limit")
        return archive, members
    except ExtractionHold:
        raise
    except Exception:
        raise ExtractionHold("archive_malformed") from None


def bounded_read(archive, member):
    try:
        with archive.open(member) as source:
            value = source.read(MAX_FILE + 1)
        if len(value) > MAX_FILE or len(value) != member.file_size:
            raise ExtractionHold("archive_member_limit")
        return value
    except ExtractionHold:
        raise
    except Exception:
        raise ExtractionHold("archive_member_malformed") from None


def document(paragraphs, kind):
    text_parts = [unicodedata.normalize("NFC", p) for p in paragraphs]
    text = "\n".join(text_parts)
    if len(text) > MAX_TEXT:
        raise ExtractionHold("text_limit")
    if not text.strip():
        raise ExtractionHold("empty_or_scanned_document")
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise ExtractionHold("text_control_character")
    spans, cursor = [], 0
    for paragraph in text_parts:
        spans.append((cursor, cursor + len(paragraph)))
        cursor += len(paragraph) + 1
    return Extracted(text, tuple(spans), kind)


def extract(data: bytes, kind: str) -> Extracted:
    if len(data) > MAX_FILE:
        raise ExtractionHold("file_size_limit")
    if kind == "txt":
        try:
            text = data.decode("utf-8-sig", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeError:
            raise ExtractionHold("text_encoding_unsupported") from None
        return document(text.split("\n"), kind)
    if kind == "pdf":
        # Parser/OCR sandbox and layout qualification are mandatory before PDF text is trusted.
        raise ExtractionHold("pdf_extraction_worker_unqualified")
    if kind != "docx":
        raise ExtractionHold("format_unsupported")
    archive, members = archive_members(data)
    with archive:
        names = {m.filename: m for m in members}
        if "word/document.xml" not in names or "[Content_Types].xml" not in names:
            raise ExtractionHold("docx_structure_invalid")
        if any(name.endswith(("vbaProject.bin", ".bin")) or name.startswith(("word/embeddings/", "word/header", "word/footer", "word/footnotes", "word/endnotes", "word/comments")) for name in names):
            raise ExtractionHold("docx_extra_content_review")
        try:
            for name, member in names.items():
                if name.endswith(".rels"):
                    relationships = XML.fromstring(bounded_read(archive, member), forbid_dtd=True)
                    if any(e.get("TargetMode") == "External" for e in relationships):
                        raise ExtractionHold("docx_external_relationship")
            root = XML.fromstring(bounded_read(archive, names["word/document.xml"]), forbid_dtd=True)
            if root.tag != W + "document":
                raise ExtractionHold("docx_structure_invalid")
            if any(e.tag in {W + t for t in ("altChunk", "del", "ins", "object", "drawing", "fldSimple", "instrText", "moveFrom", "moveTo", "delText", "txbxContent", "vanish", "webHidden", "subDoc", "sym", "footnoteReference", "endnoteReference", "commentReference")} for e in root.iter()):
                raise ExtractionHold("docx_ambiguous_content")
            if len(root.findall(W + "body")) != 1 or any(e.text and e.text.strip() and e.tag != W + "t" for e in root.iter()):
                raise ExtractionHold("docx_ambiguous_content")
            if any(any(child.tag == W + "p" for child in paragraph.iter() if child is not paragraph) for paragraph in root.iter(W + "p")):
                raise ExtractionHold("docx_ambiguous_content")
            paragraphs = []
            for paragraph in root.iter(W + "p"):
                paragraphs.append("".join((e.text or "") if e.tag == W + "t" else "\t" if e.tag == W + "tab" else "\n" if e.tag in {W + "br", W + "cr"} else "" for e in paragraph.iter()))
            return document(paragraphs, kind)
        except ExtractionHold:
            raise
        except Exception:
            raise ExtractionHold("docx_xml_invalid") from None


def extract_batch(data: bytes) -> tuple[IntakeItem, ...]:
    archive, members = archive_members(data)
    with archive:
        files = [m for m in members if not m.is_dir()]
        if not files or len(files) > MAX_DOCUMENTS:
            raise ExtractionHold("batch_document_limit")
        output = []
        for ordinal, member in enumerate(files, 1):
            kind = PurePosixPath(member.filename).suffix.lower().lstrip(".")
            try:
                item = extract(bounded_read(archive, member), kind)
                output.append(IntakeItem(ordinal, kind if kind in {"txt", "docx", "pdf"} else "unsupported", item, None))
            except ExtractionHold as error:
                output.append(IntakeItem(ordinal, kind if kind in {"txt", "docx", "pdf"} else "unsupported", None, str(error)))
        return tuple(output)
