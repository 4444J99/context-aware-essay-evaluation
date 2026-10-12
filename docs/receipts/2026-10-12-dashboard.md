# T2.3 reusable dashboard checkpoint — 2026-10-12

Owner: Product engineering, P2 issue #3. Parent: edu-organism issue #55. Implementation: PR #9.
The human explicitly authorized component integration in parallel with pending qualification.
T2.3 is in progress; acceptance dependencies were preserved.

Added Next.js/React/strict TypeScript workspace at apps/instructor. Adapted Teacher Dashboard
course/assignment selection, rubric matrix, reflection review and snippet browsing/insertion.
The fictional class queue exposes coverage, unmatched enrollment and privacy review state. Feedback
is an in-memory draft per writer; course/assignment switching clears selection. Privacy completion
never clears rubric/assessment/release holds. No upload, model or external delivery route was added.
Original predecessor files are unchanged; no Aetheria source code was copied.

Added a separate same-origin protected course metadata adapter, with session/MFA validation,
response validation, pagination and explicit login/provisioning/unavailable states. Server-configured
gateway permits HTTPS origins in production and loopback HTTP only in development. Unconfigured
gateway disables connection and hides the login link. No token/secret/browser provider dependency
is embedded in the UI. Gateway/login/PostgreSQL integration is not yet verified.

Validation on this checkpoint:

- `npm run typecheck`: passed application and dependency declarations, without skipLibCheck.
  Initial dependency declaration incompatibilities were corrected by aligning TypeScript/Node/JSDOM
  versions; no checks were disabled.
- `npm test`: 8 passed, including actual React/JSDOM interaction, class/writer separation, privacy
  holds, snippet insertion, safe rubric rendering, API denial and gateway restrictions.
- `npm audit --omit=dev --audit-level=high`: 0 vulnerabilities in the production dependency set.
- `python3 scripts/check_delivery.py`: passed 8 phases, 24 tranches and dependency ownership.
- `git diff --check`: passed.

JSDOM is not real-browser/visual acceptance. Production build and browser smoke were not executed
locally under the existing heavy admission constraint. CI now owns instructor typecheck, tests
and build, but runner admission remains a tracked external gate; no unchanged CI rerun or local
heavy retry was made. P1 issue #2 retains PostgreSQL/runner/KMS/login qualification; P2 issue #3
owns build/browser/HTTPS gateway and full intake/exception integration. Next predicate after
admission changes: `npm run build`, then a real browser flow through HTTPS plus the protected
backend and full PostgreSQL suite. Student data and grade release remain held.

Open PR retains the checkout for continued implementation and review; existing Python demo is
preserved. No merge or destructive cleanup performed.
