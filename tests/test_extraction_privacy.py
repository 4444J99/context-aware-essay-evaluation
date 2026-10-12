from io import BytesIO
import zipfile
from uuid import uuid4

import pytest

from essay_evaluation.extraction import extract, extract_batch, ExtractionHold, MAX_FILE
from essay_evaluation.contextual_privacy import plan_review, finalize_review


def zipped(entries, compression=zipfile.ZIP_STORED):
    result = BytesIO()
    with zipfile.ZipFile(result, "w", compression=compression) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return result.getvalue()


def docx(body):
    return zipped([("[Content_Types].xml", "<Types/>"), ("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>')])


def test_txt_normalized_paragraph_offsets():
    result = extract("cafe\u0301\r\nSecond\rThird".encode(), "txt")
    assert result.text == "café\nSecond\nThird"
    assert [result.text[a:b] for a, b in result.paragraphs] == ["café", "Second", "Third"]


def test_docx_order_tabs_and_table_paragraphs():
    result = extract(docx('<w:p><w:r><w:t>First</w:t><w:tab/><w:t>line</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'), "docx")
    assert result.text == "First\tline\nCell"


@pytest.mark.parametrize("data,kind,code", [(b"x" * (MAX_FILE + 1), "txt", "file_size_limit"), (b"\xff", "txt", "text_encoding_unsupported"), (b"", "txt", "empty_or_scanned_document"), (b"a\x00b", "txt", "text_control_character"), (b"%PDF", "pdf", "pdf_extraction_worker_unqualified"), (b"unknown", "rtf", "format_unsupported"), (b"broken", "docx", "archive_malformed")])
def test_extraction_holds(data, kind, code):
    with pytest.raises(ExtractionHold, match=code):
        extract(data, kind)


@pytest.mark.parametrize("body", ['<w:ins><w:p/></w:ins>', '<w:p><w:r><w:drawing/></w:r></w:p>', '<w:altChunk/>'])
def test_ambiguous_docx_never_silently_drops_content(body):
    with pytest.raises(ExtractionHold, match="docx_ambiguous_content"):
        extract(docx(body), "docx")


def test_entity_external_parts_and_side_text_hold():
    data = zipped([("[Content_Types].xml", "<Types/>"), ("word/document.xml", '<!DOCTYPE x [<!ENTITY a "sensitive">]><x>&a;</x>')])
    with pytest.raises(ExtractionHold, match="docx_xml_invalid"):
        extract(data, "docx")
    for name, value, code in [("word/header1.xml", "<x/>", "docx_extra_content_review"), ("word/_rels/document.xml.rels", '<Relationships><Relationship TargetMode="External"/></Relationships>', "docx_external_relationship")]:
        with zipfile.ZipFile(BytesIO(docx('<w:p><w:r><w:t>Body</w:t></w:r></w:p>'))) as base:
            entries = [(m.filename, base.read(m)) for m in base.infolist()]
        with pytest.raises(ExtractionHold, match=code):
            extract(zipped(entries + [(name, value)]), "docx")


@pytest.mark.parametrize("name", ["../private.txt", "/private.txt", "folder\\private.txt", "C:private.txt"])
def test_archive_paths_rejected(name):
    with pytest.raises(ExtractionHold, match="archive_path_invalid"):
        extract_batch(zipped([(name, "text")]))


def test_batch_count_ratio_nested_and_filename_non_disclosure():
    with pytest.raises(ExtractionHold, match="batch_document_limit"):
        extract_batch(zipped([(f"{i}.txt", "x") for i in range(21)]))
    with pytest.raises(ExtractionHold, match="archive_ratio_or_member_limit"):
        extract_batch(zipped([("fictional-private-name.txt", "x" * 10000)], zipfile.ZIP_DEFLATED))
    rows = extract_batch(zipped([("fictional-private-name.txt", "Essay"), ("nested.zip", zipped([("x.txt", "x")])), ("scan.pdf", "%PDF")]))
    assert len(rows) == 3 and rows[0].document.text == "Essay"
    assert rows[1].hold == "format_unsupported" and rows[2].hold == "pdf_extraction_worker_unqualified"
    assert "fictional-private-name" not in repr(rows)


def test_all_passages_require_review_even_without_detector_flags():
    course, submission, reviewer = map(str, (uuid4(), uuid4(), uuid4()))
    plan = plan_review("An ordinary paragraph.\nA unique detail the rules do not recognize.", course, submission)
    assert all(not p.flags for p in plan.passages)
    assert finalize_review(plan, plan.source, course, submission, reviewer, {1: "retain"}).holds
    assert finalize_review(plan, plan.source, course, submission, reviewer, {1: "retain", 2: "hold"}).document is None
    result = finalize_review(plan, plan.source, course, submission, reviewer, {1: "retain", 2: "retain"})
    assert not result.holds and not result.document.contextual_review_required


def test_context_redaction_preserves_mapping_and_direct_scrub_cannot_be_overridden():
    course, submission, reviewer = map(str, (uuid4(), uuid4(), uuid4()))
    text = "I was diagnosed at the hospital.\nContact fictional@example.invalid.\nA clear claim."
    plan = plan_review(text, course, submission)
    assert "health_or_disability" in plan.passages[0].flags
    result = finalize_review(plan, text, course, submission, reviewer, {1: "redact", 2: "retain", 3: "retain"})
    assert "hospital" not in result.document.text and "fictional@example.invalid" not in result.document.text
    start = result.document.text.index("A clear claim.")
    a, b = result.document.original_span(start, start + len("A clear claim."))
    assert text[a:b] == "A clear claim."
    with pytest.raises(ValueError, match="span_intersects_redaction"):
        result.document.original_span(0, 5)
    assert "hospital" not in repr(plan) and "hospital" not in repr(result)


def test_stale_cross_scope_and_unknown_review_decisions_rejected():
    course, submission, reviewer = map(str, (uuid4(), uuid4(), uuid4()))
    plan = plan_review("Original", course, submission)
    with pytest.raises(ValueError, match="review_version_stale"):
        finalize_review(plan, "Changed", course, submission, reviewer, {1: "retain"})
    with pytest.raises(ValueError, match="review_scope_mismatch"):
        finalize_review(plan, "Original", str(uuid4()), submission, reviewer, {1: "retain"})
    with pytest.raises(ValueError, match="review_decision_invalid"):
        finalize_review(plan, "Original", course, submission, reviewer, {1: "approve-automatically"})


def test_symlink_members_and_review_limits():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        info = zipfile.ZipInfo("link.txt")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, "target")
    with pytest.raises(ExtractionHold, match="archive_member_unsupported"):
        extract_batch(output.getvalue())
    with pytest.raises(ValueError, match="input_limit"):
        plan_review("x" * 100001, str(uuid4()), str(uuid4()))
    with pytest.raises(ValueError, match="input_limit"):
        plan_review("short", str(uuid4()), str(uuid4()), ("x" * 257,))


def test_full_passage_redaction_subsumes_direct_identifiers_and_mapping():
    course, submission, reviewer = map(str, (uuid4(), uuid4(), uuid4()))
    text = "Fictional Person works at fictional@example.invalid.\nEvidence survives."
    plan = plan_review(text, course, submission, ("Fictional Person",))
    result = finalize_review(plan, text, course, submission, reviewer, {1: "redact", 2: "retain"})
    assert result.document.text == "[CONTEXT_1]\nEvidence survives."
    assert len(result.document.replacements) == 1
    assert "Fictional Person" not in repr(result)


@pytest.mark.parametrize("suffix", [".", ",", ";", ")", "!", "?"])
def test_email_sentence_punctuation_is_scrubbed(suffix):
    from essay_evaluation.privacy import scrub
    result = scrub("Contact fictional@example.invalid" + suffix)
    assert "fictional@example.invalid" not in result.text
    assert result.text.endswith(suffix)
