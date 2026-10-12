# Protected synthetic intake and version-bound review

Owners: T1.1 Platform engineering; T2.1 Application engineering; T2.2 Privacy engineering;
T2.3 Product engineering. Parent: edu. PR #9 / phase issues #2 and #3.

This implementation connects bounded extraction and privacy contracts to authenticated backend
routes, PostgreSQL metadata/audit references, durable encrypted vaults and a separate dashboard
panel. It is fixture-only while qualification gates are pending. There is no student-upload route,
client-supplied essay/filename/name/identifier list, arbitrary PDF parser, model call or release.

## Schema and configuration

Run the existing administrator migration command before starting the runtime. Migration 001 is
unchanged; 002 adds forced-RLS intake_submissions and append-only-by-runtime intake_events.
The migrator verifies the full existing checksum prefix and applies pending revisions in one
transaction. Startup now requires all three revisions and all ten forced-RLS tables. Never edit the
001 checksum to upgrade. Empty-schema rollback removes 002 before 001 and still refuses populated
schemas; this is rehearsal, not deletion of classroom records.

In addition to existing runtime grants, an administrator grants:

```sql
GRANT SELECT, INSERT ON intake_submissions, intake_events, assignments, assignment_enrollments TO edu_api;
GRANT UPDATE ON intake_submissions TO edu_api;
```

Do not grant event UPDATE/DELETE, table ownership or RLS bypass. Both tables use composite
course/instructor foreign keys, and events bind to the same scoped submission. Source bytes,
normalized text, private content fingerprints, identifiers, reviewer decisions and passage maps
never enter metadata SQL. SQL stores only opaque references, states, counters and server hold codes.

The default `EDU_INTAKE_MODE=disabled` leaves authenticated routes at an explicit unconfigured hold.
Only `synthetic` is accepted as an enabled mode; other values fail startup. Supply these through the
operator credential boundary, not source/history/chat:

- `EDU_INTAKE_IDENTITY_ROOT`, `EDU_INTAKE_CONTENT_ROOT`: trusted private vault roots.
- `EDU_INTAKE_IDENTITY_KEYS_JSON`, `EDU_INTAKE_CONTENT_KEYS_JSON`: externally supplied versioned
  base64 32-byte wrapping keys, with no shared key material across domains.
- `EDU_INTAKE_IDENTITY_KEY_VERSION`, `EDU_INTAKE_CONTENT_KEY_VERSION`: active versions.

The intake/review process is an authorized identity-vault reader and also writes processed content.
A future assessment worker must receive only content-domain access. These separate key rings are
a development adapter; hosted KMS/IAM separation is still unqualified. Browser OIDC/gateway setup
continues to use the exact public HTTPS origin and existing CSRF enforcement.

## API and dashboard sequence

1. Sign in to the protected service, then load authorized intake courses in the separate dashboard
   panel. Existing local preview records are never substituted for protected responses.
2. POST `/v1/courses/{course}/intake` with request_id UUID and one fixed fixture_id: argument,
   literary, contextual, docx-argument or pdf-held. No raw work is accepted. A scoped transaction
   advisory lock plus unique request key makes retries repeat-safe; conflicting fixture reuse is 409.
3. GET `/v1/courses/{course}/intake/{submission}/review` reads originals only after scoped metadata
   lookup. The response includes opaque source_revision, review_generation and each original
   passage with flags. Original passages are restricted to the authenticated instructor, no-store.
4. POST that review route with source_revision, expected_generation and a passage decision map.
   Every passage requires retain/redact/hold. Stale source/generation is 409 and never retried
   automatically. The dashboard obtains CSRF from the opaque session, requires explicit choices,
   clears review data when scope changes and bounds request wait time.
5. Complete decisions create a processed content object. Missing/held decisions leave privacy
   pending and clear any current processed pointer. Every successful review gets a new encrypted
   identity-domain audit object and SQL event within the metadata transaction.

JSON writes are capped at 64 KiB before framework parsing with a five-second body-read deadline.
Validation responses omit supplied values and dynamic field names. Database/vault failures return
sanitized codes. API responses expose no vault object IDs or private content fingerprint.

Source revision is immutable; review generation increments under a row lock. Encrypted payloads
bind instructor/course/submission/revision as well as vault AAD. Swapped pointers are rejected.
Original bytes/normalized source live only in the identity vault; passage maps remain private there.
Vault objects are published before SQL commit. A failed transaction cannot publish SQL metadata
or clear holds, but can leave unreferenced ciphertext. T6.2 owns orphan reconciliation, retention
and deletion across database/vault/backups; no eager deletion is attempted.

Course intake is quarantine staging: assignment and enrollment association are unresolved, and
those holds remain alongside synthetic/parser/route/release qualification. A reviewed record is
not a releasable assessment. PDF always remains extraction-held and cannot be approved through
privacy decisions. Class enrollment matching and assignment mapping must become server-owned
before this fixture path can qualify as student intake.

## Evidence and required acceptance

Service tests use real durable ciphertext and generated JWTs with a repository contract double;
frontend tests use mocked transport/JSDOM. These verify wiring and consistency, not PostgreSQL
transactions or RLS. A real-PostgreSQL test covers fixture persistence/idempotency, cross-instructor
reads/writes, stale reviews, event counts and transaction failure after vault publication. The
existing migration test now rehearses 001-to-002 upgrade as well as rollback/reapply. Those five
PostgreSQL cases remain unexecuted under tracked admission; no acceptance is inferred.

Next predicates: full pytest against disposable PostgreSQL; Next production build and real browser
through HTTPS/login; hosted key separation/restore; supervised parser/PDF/OCR and reviewed privacy
attack corpus; then scoped assignment/enrollment and durable decision workflow acceptance. Existing
P1/P2 blockers stay tracked, with no unchanged bootstrap/CI rerun in this slice.


## Protected assignment mapping and exceptions

Migration 003 adds instructor/course-scoped assignments and immutable expected-enrollment
snapshots from an authorized section. Creating an assignment requires a nonempty roster of at
most 1,000 enrollments. The synthetic route accepts only the fixed fictional assignment label.
Later enrollment changes do not silently change the denominator; roster revision is future work.
The bounded workspace fails closed above 1,000 rows in any collection rather than reporting
partial coverage. Coverage means an active mapped document exists, not privacy or grading approval.

The instructor maps a persisted intake to an expected assignment/enrollment pair, or excludes /
restores it with an enumerated reason. Composite foreign keys enforce scope and a partial unique
index prevents two active documents covering one assignment enrollment. Occupied mappings and
restores return conflict; exclude the duplicate explicitly before restoring its predecessor.
Original ciphertext remains intact. Every successful resolution advances the same generation as
privacy review, clears the processed pointer, resets privacy approval, and writes an encrypted
audit record in the SQL transaction. Stale decisions fail before publication. Course transaction
locks serialize intake/review/resolution writes; the unique index is independent protection.
Mapping clears only assignment/enrollment holds. Exclusion and matching never clear PDF/OCR,
parser, route, synthetic-only, or release qualification holds. Excluded records cannot be privacy
approved. The protected dashboard exposes assignment creation, queue, coverage, matching and
exclusion/restoration separately from the in-memory preview.
