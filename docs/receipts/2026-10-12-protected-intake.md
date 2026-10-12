# Protected extraction/privacy workflow checkpoint — 2026-10-12

Owners: edu P1 issue #2 and P2 issue #3; parent edu-organism issue #55; implementation PR #9.
The human authorized connecting extraction and version-bound review while qualification remains
pending. T1.1/T2.1/T2.2/T2.3 remain in progress; no acceptance dependency was waived.

Implemented disabled-by-default, authenticated server-fixture intake with durable identity-vault
originals, separate content-vault processed text, PostgreSQL scoped metadata/event schema and a
protected dashboard panel. No arbitrary work/name/filename upload is accepted. The panel obtains
session CSRF, requires per-passage decisions and submits immutable source revision plus expected
review generation. Source/pointer binding, replay-safe request keys, stale review rejection and
scope checks remain server-owned. Assignment/enrollment, synthetic/parser/route/release holds
remain even after successful privacy review. PDF cannot pass extraction or review.

Migration 002 adds two forced-RLS tables with composite scope FKs and event generation uniqueness.
Migration 001 is unchanged. The migration runner now verifies the existing checksum prefix and
applies pending revisions; runtime verifies eight protected tables. Runtime event rights are
SELECT/INSERT only; intake metadata can UPDATE. Scoped advisory admission lock plus row review
lock prevents concurrent request-key/review decisions from silently overwriting state. Real SQL
execution/transaction qualification is pending, not inferred from repository doubles.

JSON writes are bounded to 64 KiB/five seconds before parsing; errors omit supplied values/dynamic
field names. Storage errors are sanitized. Immutable encrypted writes precede SQL transaction
commit, so failures can leave unreferenced ciphertext but cannot clear metadata holds. T6.2 owns
orphan/retention reconciliation; no source is eagerly deleted.

Verification evidence:
- Full eligible Python batch: 91 passed, five PostgreSQL cases explicitly deselected.
- Final intake shard: nine passed, including new distinct-key rejection case (eight cases overlap
  the previous batch). Four new migration-control-flow cases passed. Total distinct lightweight
  cases with current implicated receipts: 96. Migration doubles do not execute SQL.
- Frontend strict typecheck passed. Fourteen React/JSDOM/adapter tests passed, including protected
  fixture creation, session CSRF, explicit passage decisions and version/generation writes.
- Delivery graph (8 phases/24 tranches) and whitespace checks passed.
- One upstream Starlette test-client deprecation warning; no student data or model requests used.

Five real PostgreSQL cases remain unexecuted, including the new protected intake persistence/RLS/
rollback test and upgraded 001-to-002 migration rehearsal. Existing host/runner admission blockers,
Next build/browser, live HTTPS OIDC and KMS gates remain tracked; no unchanged heavy/CI retry.
PDF/OCR/parser isolation and contextual attack-corpus qualification remain T2.1/T2.2 owners.
Next acceptance predicate: full pytest on disposable PostgreSQL, then Next build and real browser
through protected HTTPS gateway. Configuration/grants and remaining server assignment/enrollment
integration are documented in docs/protected-intake.md. Checkout retained for open PR; demo and
predecessor originals preserved. No merge or destructive cleanup performed.
