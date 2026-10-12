# Protected backend implementation checkpoint

Date: 2026-10-12. Product: edu. Owner: P1 / issue #2.
Publication owner: existing implementation PR #9.

Implemented T1.1's versioned PostgreSQL schema, transactional migration/reapply and empty-schema
rollback guard; instructor/term/course/section/enrollment metadata; scoped external references;
composite foreign keys, target-scope trigger and forced row-level security. Added a separate
FastAPI backend with protected endpoints, explicit provisioning/revocation, pinned-issuer RS256
API-token/MFA validation, bounded pagination, generic errors and no-store responses. Runtime
roles cannot be elevated or own application tables. Remote database configuration requires
verified TLS. The synthetic workbench remains a separate application.

Local checks: foundation and identity/API contract batch 32 passed, 4 PostgreSQL integration
cases deselected because local heavy admission returned swap-fraction. A subsequent database
transport-policy shard passed (1 case). These are not full database acceptance. Graph checker
passed 8 phases / 24 tranches; whitespace check passed. Existing Starlette TestClient deprecation
warning remains upstream. No student data or model calls were used.

The PostgreSQL integration suite is committed to CI using a disposable PostgreSQL 17 service.
It exercises schema reapply/rollback, refusal to roll back populated data, unsafe runtime roles,
provisioning/revocation, foreign-ID denial, cross-course constraints, references, RLS without
API filters and unset transaction scope. Local cluster bootstrap was not run after admission
rejected it; no heavy lease is claimed. Owner for acceptance: P1 issue #2; predicate:
`uv run --locked --extra test pytest` against the disposable CI service or a writer-admitted
native test cluster. T1.1 remains in_progress until that evidence is observed.

T1.2 still owns the durable encrypted vault, key separation/restore and actual issuer-backed
browser login; T1.3 owns hosted staging. Token-verifier code is not an implemented OIDC login
experience or a configured institution policy. Dashboard extraction remains next after protected
backend qualification, through the authenticated API described in docs/protected-backend.md.

The isolated worktree is retained for the open implementation PR and existing synthetic demo.
No merge, deployed backend, student-processing approval or completed project is claimed.
