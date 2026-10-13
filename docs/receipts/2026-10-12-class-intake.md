# Synthetic class intake and exception resolution — 2026-10-12

Owner: Product engineering, T2.3 / P2 issue #3. Product: edu, parent issue #55; PR #9.

The current heavy-admission attempt returned exit 3, allowed false, reason `swap-fraction`.
Sensor observed 20:24:04 UTC: swap fraction 0.64685, roughly 11.1 GB swap used. No Next build,
server or browser was started after denial. Existing P1 PostgreSQL and GitHub runner admission
owners are preserved; no account remedy or CI result is inferred. Next build/browser predicate
is owned by P2: after admission changes, run npm run build and npm run test:browser in apps/instructor.

Implemented explicit fictional expected enrollments separately from source submissions. Fixture
imports are repeat-safe and preserve decisions/drafts. Coverage tracks exactly-one submissions,
missing writers, unmatched records, duplicate enrollment groups and excluded source records.
Instructor matching is assignment-bound, rejects an occupied enrollment and resets privacy review.
Exclusion requires an enumerated reason, preserves source/draft and can be reversed. Restoring a
duplicate restores its conflict. In-memory decision events record sequence/action/scope/record.
No student upload, arbitrary text ingestion, provider call or grade release was added. This is not
a durable protected intake service or server authorization boundary.

Verification: npm run typecheck passed with dependency declarations enabled. npm test passed
11 tests, including actual React/JSDOM controls for matching, duplicate exclusion/restoration and
course/writer separation. npx playwright test --list discovered two authored browser flows;
discovery is not execution. Delivery graph and whitespace checks pass. Browser tests include
mobile overflow and page-error assertions, but no browser/visual acceptance is claimed.
CI includes bounded single-worker Chromium tests after production build. Existing runner admission
remains unqualified; there was no ad-hoc rerun or synchronous CI wait.

T2.3/P2 remain in progress; T2.1 bounded document extraction and T2.2 contextual privacy are still
pending. HTTPS gateway/live login/PostgreSQL, durable import/decision audit and actual student
intake remain acceptance work. Checkout retained for the open implementation PR; original
predecessor artifact and existing Python demo preserved.
