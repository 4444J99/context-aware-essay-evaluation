# Hosted verification corrections

Owner: edu-organism #55; P1 #2 / P2 #3; implementation PR #9.

Hosted Verify 38326956233 ran after public visibility on source head
9c5765f6125868bbbbfeaf2c55f9d8da22b69059 (PR merge ref 2c538f0758606d8b9f9ac318b96732a95625c85a).
Runner admission is therefore no longer the observed hosted blocker. Preserve earlier admission
receipts as history, not current diagnosis.

Observed results: PostgreSQL-backed Python batch 104 passed / 1 failed; five of six database cases
passed. Roster/mapping case failed at assignment creation because its setup sent student_ref to
an empty-input enrollment API. The rejected setup response was not asserted, leaving no roster.
Correction sends empty enrollment input and asserts section/enrollment creation before mapping.
No production input or privacy protection was weakened.

Hosted instructor strict types, 17 frontend tests and Next production build passed. Browser batch
ran: one passed, two timed out selecting Assignment. Wrapping label text included option labels;
exact text lookup did not match. Added stable accessible names to Course/Assignment controls,
with a distinct Protected assignment name, and switched affected browser locators to combobox
roles. No timeout increase, test removal or skip. Failed browser traces now upload as a bounded
seven-day hosted artifact for concrete evidence if subsequent assertions fail.

Correction validation and fresh exact-head hosted run are bound in PR #9 and owner issues.
Previously green receipts remain scoped to the tested source/merge ref, not production acceptance.
Roster SQL path and two browser flows still require successful corrected execution. Local heavy
admission remains unaccepted; no database/build/browser workload launched locally.
PDF/OCR, supervised parser, live OIDC/HTTPS, KMS/IAM/restore, contextual recall, retention and
release retain their existing owners. No real student uploads, model calls or grades enabled.
Existing worktree retained for qualification follow-through.
