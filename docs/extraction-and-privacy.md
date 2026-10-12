# Bounded extraction and contextual privacy review

Owners: T2.1 Application engineering and T2.2 Privacy engineering, edu P2 issue #3.
These are internal components tested only with generated documents. They are not upload endpoints,
server authorization, an accepted extraction sandbox, or proof of anonymity.

## Extraction contract

`extract(bytes, format)` returns NFC text, half-open Unicode paragraph spans and a format tag.
TXT is strict UTF-8 (optional BOM), with normalized line endings. DOCX preserves document-body
paragraph order, including table cells, tabs and explicit breaks. It does not reconstruct visual
page layout. Headers, footers, footnotes, comments, tracked changes, textboxes, hidden content,
fields, embedded objects and external relationships hold instead of being silently discarded.
DTD/entity processing is forbidden. Invalid XML/package structure holds.

`extract_batch(zip_bytes)` keeps source archive order and returns ordinal-based outcomes for every
member, including held formats. No filename enters result metadata or exception text; the future
authorized service must preserve the original ordinal/source manifest separately in protected
storage. The library neither writes files nor follows archive paths. It rejects traversal, absolute
or alternate paths, duplicate names, symlinks, encryption, unsupported compression and high ratios.
Nested ZIPs are held rather than recursively extracted.

Limits: 1 MiB per file/member, 8 MiB archive input/aggregate expansion, 64 archive members, 20 batch
documents, 100,000 normalized text characters. Member reads are capped and checked against declared
size. Empty/image-only documents and unsupported encoding hold. These are input/expansion bounds,
not process CPU/memory isolation. Adversarial parser qualification and a supervised worker with
OS-enforced resources remain acceptance work before arbitrary student documents are admitted.

PDF always returns `pdf_extraction_worker_unqualified`. PDF layout extraction, scanned-document
OCR and their isolated resource limits remain required T2.1 work; they are visible holds, not a
missing optional capability or fabricated empty result. DOCX/TXT admission does not clear that gate.

## Privacy contract

`plan_review` binds normalized source to course/submission UUIDs and a private content version.
It runs the direct scrubber and produces a review item for every non-empty paragraph, including
unflagged ones. Health/disability, family/legal and distinctive-role/location patterns only
prioritize review; they are deliberately incomplete. Reflection and other student-authored context
must receive their own source-bound review before use. Known identifier values are separately
bounded and must come from an authorized identity scope. At most 2,000 direct redaction
candidates are collected; excessive/repeated identifier matches hold rather than amplify memory.

`finalize_review` requires the same source version and scope, reviewer identity and an explicit
retain/redact/hold decision for each passage. Missing or uncertain decisions return no processed
document. Retaining a passage never restores its direct identifiers. Redacting a whole passage
subsumes internal identifier replacements. Unchanged passages map back to exact normalized-source
spans; evidence intersecting replacements is rejected. Source normalization defines the version
basis, so offsets are not claimed to match raw DOCX bytes or a pre-normalized TXT file.

Source text and processed content are omitted from object representations. Review maps, private
versions, originals and reviewer decisions still belong in the protected vault/audit boundary.
The authenticated service must own plans and verify actual reviewer/course authority; a UUID
consistency check is not authorization. These contracts now feed a fixture-only protected intake/review service and separate dashboard
panel; see protected-intake.md. Arbitrary student upload and PostgreSQL/live gateway acceptance
remain pending, and the local synthetic dashboard checkbox is not a qualified privacy gate.
Human review reduces exposure but does not establish anonymity or clear model/release qualification.

## Qualification and next integration

T2.1/T2.2 are in progress. Next: supervised parser/PDF/OCR qualification, protected scoped intake
persistence, durable source/paragraph mapping and reviewer decision audit, then replace the synthetic
UI privacy interaction with this version-bound service. Test contextual detection with a reviewed
attack corpus; the current generated cases establish mechanics rather than detector recall.
Existing build/browser, PostgreSQL, live issuer, KMS and runner admission blockers remain with
P1/P2 owners. No unchanged heavy/bootstrap/CI retry is needed for these component changes.
