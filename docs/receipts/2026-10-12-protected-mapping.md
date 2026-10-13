# Protected assignment mapping and exception workflow

Owner: edu-organism #55; evaluator P2 #3; implementation PR #9.

Implemented migration 003 with scoped assignments, expected-enrollment snapshots, composite
mapping constraints, active-match uniqueness and forced RLS. Protected intake now records
assignment/enrollment decisions and reversible exclusion/restoration with encrypted audit,
optimistic generation checks, source preservation and privacy invalidation. Dashboard controls
use the authenticated same-origin gateway with CSRF and no automatic write retries.

Qualification remains pending: PostgreSQL execution (six authored integration cases), production
build/browser execution, live OIDC/HTTPS, hosted key custody/restore, isolated parsers/PDF/OCR,
contextual recall and retention/orphan reconciliation. Existing P1 #2 and P2 #3 retain ownership;
no model call, grade, real-data upload or release is enabled. No unchanged heavy gate was retried.

Validation: 97 lightweight Python tests passed in the eligible batch; the final changed
intake shard passed all 10 tests (two PostgreSQL cases excluded explicitly). Strict frontend
type checking and all 15 frontend tests passed. Delivery graph and whitespace checks passed.
The frontend regression initially selected a control by numeric position; it now selects its
passage label, and the corrected suite passed. PostgreSQL execution, build and real-browser
verification were not performed and are not implied by these results.
