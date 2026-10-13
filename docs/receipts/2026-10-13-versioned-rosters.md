# Versioned protected assignment rosters

Owner: edu-organism #55; evaluator P2 #3; implementation PR #9. Checkout retained on the
existing implementation branch for continued qualification; no source documents removed.

Migration 004 backfills revision-zero roster snapshots, adds active membership and forced-RLS
append-only roster history. Protected updates require expected generation and unique same-section
enrollment IDs. SQL transaction/course locks serialize revision, snapshot, membership, intake
invalidation and audit. All matched records advance privacy generation and clear content pointers;
removed members retain source and mapping with a persistent roster hold. Re-addition requires
fresh privacy review. Dashboard checkboxes send explicit members with CSRF and never retry writes.

Validation: 97 other Python tests passed in the eligible batch; the new roster test initially
exposed an incomplete section-membership contract double. Its section universe was corrected;
all 11 final intake service/route tests passed. Frontend strict type checking passed. All 16 frontend tests passed, including the protected roster checkbox/update flow and stale-write adapter. Delivery graph and whitespace checks passed. Six authored PostgreSQL integration cases remain
unexecuted; mapping integration now also covers roster history, invalidation, stale writes and RLS.

Fresh heavy admission at 2026-10-13 00:03:52 UTC denied swap-fraction (0.72503) and disk-throughput
(1020.15/2151.38 MiB/s samples). No database/build/browser process was started after denial.
Owner P1 #2 retains the gate: acquire admitted heavy capacity, then run the full Python suite,
instructor production build and Playwright predicates. Hosted Verify job admission remains with
that owner; no unchanged retry or billing diagnosis was made. Browser/component doubles do not
prove real browser, database, live auth or production operation.

PDF/OCR/supervised extraction stays held under P2/T2.1 until worker qualification. Live OIDC/HTTPS,
hosted KMS/IAM/restore, contextual recall, retention/orphan reconciliation and release qualification
retain existing owners. No real student upload, model call, grade or release was enabled.
