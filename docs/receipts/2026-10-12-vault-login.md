# T1.2 vault and login checkpoint — 2026-10-12

Owner: Security engineering, edu P1 issue #2; implementation PR #9. T1.2 remains in progress.

Implemented filesystem envelope vault with separate identity/content/session key domains, immutable atomic publication, authenticated scope binding, key rewrapping and private path validation. Added persistent encrypted browser sessions and OIDC code/PKCE login, MFA verification, one-use state, server-side tokens, CSRF/origin checks and local logout revocation. Login is explicitly configured and remains off when not configured. No real records, provider calls or model inference were used.

Verification: `uv run --locked --extra test pytest tests/test_foundation.py tests/test_backend.py tests/test_durable_vault.py tests/test_login.py -k 'not schema_reapply and not authenticated_course and not cross_course and not rls_without' -q` passed 53 tests, with four PostgreSQL cases explicitly deselected because their execution remains blocked. One upstream Starlette test-client deprecation warning. `python3 scripts/check_delivery.py` passed all 8 phases and 24 tranches; `git diff --check` passed. Earlier vault/login-focused batch passed 18 tests before final hardening; compatibility batch above is current evidence.

Existing PostgreSQL heavy admission and GitHub runner admission blockers remain recorded in docs/receipts/2026-10-12-protected-backend.md and P1 issue #2. No unchanged heavy retry or CI rerun was made. Next predicate after admission changes is the full pytest suite against disposable PostgreSQL. Hosted KMS/IAM separation, live institution OIDC configuration, backup lifecycle/deletion and staging smoke remain owned by T1.2/T1.3/T6.2. Component tests are not production acceptance.

Checkout retained for open PR #9 and ongoing authorized edu implementation; existing synthetic demo is preserved. No destructive cleanup or merge requested by this checkpoint.
