# T2.1/T2.2 component checkpoint — 2026-10-12

Owners: Application/Privacy engineering, P2 issue #3; edu parent issue #55; implementation PR #9.
T2.1 and T2.2 are in progress, following the human authorization for parallel component work.

Implemented bounded in-memory UTF-8 TXT, document-body DOCX and ordinal-based ZIP batch extraction.
Limits cover input, member count/size, aggregate expansion, ratio and text length. Traversal,
symlinks, encryption, nested archives, malformed XML, DTD/entities, external relationships and
ambiguous DOCX content hold. No raw filenames enter results/errors and no files are extracted to
disk. PDF is an explicit worker-unqualified hold until supervised PDF/layout/OCR work is accepted.
These byte/expansion limits are not OS process isolation or parser acceptance.

Implemented course/submission/source-version-bound privacy plans, all-nonempty-passage decisions,
heuristic priority flags, incomplete/uncertain holds, reviewer consistency, stale-scope rejection,
context redaction, direct-identifier preservation and normalized-source mapping. No detector can
auto-approve a passage. The service must still authorize and persist reviewers/maps/decisions;
no student upload endpoint or protected review transaction is introduced. Synthetic UI privacy
controls are not acceptance evidence for these internal contracts.

Tests exposed an existing email scrubber punctuation boundary defect. Corrected the pattern and
added six punctuation regressions. Also bounded known identifier lengths before regex construction.

Verification: `uv run --locked --extra test pytest tests/test_foundation.py tests/test_extraction_privacy.py -q`
passed 53 tests (23 foundation + 30 new cases) after final candidate-amplification hardening. Direct
redaction collection now stops at 2,000 candidates, including repeated known identifiers. An earlier
52-case batch passed; after enabling explicit DTD rejection, the implicated
DOCX/XML shard passed six tests with 23 deselected. One upstream Starlette test-client deprecation
warning in the foundation batch. `python3 scripts/check_delivery.py` and `git diff --check` passed.
No PostgreSQL, build/browser, live issuer, cloud or model run was attempted for this component slice.

Existing local heavy/build/browser, PostgreSQL and GitHub runner gates remain with P1/P2 issue
owners; no unchanged retry. New acceptance owners: T2.1 supervised parser/PDF/OCR qualification;
T2.2 reviewed contextual attack corpus and protected version-bound review workflow. Next reversible
integration is scoped durable ingestion/audit through the protected service after its qualification.
Current originals/maps remain private in memory; they are never repository fixtures from students.
Checkout retained for the open PR and existing demo; no merge or destructive cleanup performed.
