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

## CI admission observation

Pushed implementation f308226fb19118adb19cb933e6f870fe9cfcdfaf. Verify run
https://github.com/4444J99/context-aware-essay-evaluation/actions/runs/38299555855
finished without starting the foundation job. GitHub's annotation said recent account payments
had failed or a spending limit needed to be increased; no test logs exist. This is a runner
admission failure, not a failing PostgreSQL predicate or verified account diagnosis. No account
change, spending increase, CI rerun or repeated merge submission was made.

External gate owner: P1 issue #2 / GitHub account Actions admission. Completion predicate: the
existing full suite executes on a disposable PostgreSQL service and passes. After that gate is
resolved, next command: `gh run rerun 38299555855 --repo 4444J99/context-aware-essay-evaluation`
for the recorded source revision, or the current Verify job if a newer revision supersedes it.
Local alternative remains the admission-gated native cluster; do not bypass host rejection.

A subsequent source review added a startup check requiring all six application tables to have
forced RLS, and removed unavailable Swagger HTML routes under the API's strict content policy.
These changes do not establish database acceptance.

Final lightweight additions: signed-token cases with missing MFA/expiry claims were added; the
identity shard passed all 10 cases. The API/transport shard passed 2 cases after the startup/RLS
review, and Python source compilation passed. Source-only amendments leave unchanged green
shards as prior evidence; the PostgreSQL integration boundary remains unverified.

Wheel packaging passed and contains both SQL migration directions and protected backend modules.
A final multi-host transport case ensures a Unix-socket fallback cannot exempt a remote host
from verified TLS. The implicated transport shard passed. No merge submission was repeated.
