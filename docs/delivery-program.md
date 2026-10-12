# edu essay evaluation delivery program

Date: 2026-10-12. Product owner: edu. Engineering and delivery owner: Codex in this project.
Status: protected backend T1.1 in progress; no production release or real student processing.

## Product boundary and source of truth

This repository is a dedicated component of **edu**, not an independent product.
edu owns course operations, teaching context, and product direction. This component owns ingestion,
privacy transformations, assessment, feedback, and the instructor evaluation workspace.
Course integration will use explicit contracts; it must not read edu's private data or assume
authorization merely because both repositories belong to the same account.

The approved plan is preserved verbatim in
[the dated plan](../.codex/plans/2026-10-12-context-aware-essay-evaluation.md).
The user's clarification that this is part of edu is recorded in
[the decision log](decisions.md). This program adds delivery order, responsibilities and executable
acceptance; it does not replace or reduce the approved scope.

The user subsequently supplied the Teacher Dashboard React artifact and classroom-rpg-aetheria
as previous versions. Their [source review](legacy-review.md) and
[v2 integration addendum](../.codex/plans/2026-10-12-context-aware-essay-evaluation-v2.md)
add reuse requirements to the existing tranches. The evaluator remains a shared edu service;
adapted React instructor views and a future Aetheria client use the same protected contracts.
Source similarity does not count as implemented integration. delivery/tranches.json records
the expanded acceptance, including rubric compatibility, reflection, snippets and full coverage.

## Milestones and tranches

### P0 Program and executable foundation

Entry: authorized project creation.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T0.1 | Repository, approved plan, delivery graph and edu ownership | Program lead | Plan provenance, dependency graph, remote issues and PR are published. |
| T0.2 | Synthetic intake and deterministic assessment contracts | Application engineering | Synthetic API and privacy, rubric, evidence, retention, encryption tests pass. |
| T0.3 | Reproducible verification and qualification boundaries | Quality lead | Clean installation, CI definition, smoke test and explicit unqualified routes exist. |

### P1 Protected hosted foundation

Entry: P0 accepted.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T1.1 | PostgreSQL schema, migrations and scoped authorization | Platform engineering | Instructor, term, course, section and enrollment models survive migrate/rollback tests; cross-scope access is denied. Legacy course/realm, assignment/quest and submission references are scoped mappings; client IDs or roles grant no authority. |
| T1.2 | OIDC MFA, object vault and separate identity keys | Security engineering | Private login works; content worker cannot decrypt identity; backup restore is demonstrated. |
| T1.3 | Hosted staging, secrets and operational controls | Platform engineering | Synthetic staging smoke passes; budgets, logs, key rotation and rollback have executable checks. |

### P2 Class ingestion and privacy review

Entry: P1 accepted.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T2.1 | DOCX PDF TXT ZIP and roster ingestion | Application engineering | Bounded extraction preserves text and paragraph order; scanned, malformed, zip-bomb and ambiguous roster cases hold. Legacy import dry runs report exact source, imported, duplicate and held counts without writing historical student records. |
| T2.2 | Contextual de-identification and passage mapping | Privacy engineering | Direct identifiers and contextual disclosures tested; uncertain cases hold; original passage mapping survives redactions. |
| T2.3 | Next.js intake workspace and exception resolution | Product engineering | Instructor imports a whole synthetic class and resolves mismatches without cross-student disclosure. Adapt prior course, assignment, upload and reflection views after removing direct Firebase/Spark/model dependencies; demonstrate the authorized service path. |

### P3 Rubric evaluation and exports

Entry: P2 accepted.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T3.1 | Versioned rubric setup and assessment provider contract | Assessment engineering | Instructor activates verified criteria; exact versions govern jobs; full text fits or holds; arithmetic is deterministic. Teacher Dashboard level-point, Aetheria maxPoints and Aetheria weighted-level formats import as inactive drafts; labels and provenance survive; ambiguous totals or weights hold. |
| T3.2 | Evidence-grounded feedback and release validation | Assessment engineering | Unsupported quotes, conflicting feedback, prompt injection and unqualified routes cannot yield released grades. Instructor snippet insertion retains evidence obligations; reused templates cannot imply unsupported student-specific observations. |
| T3.3 | Review overrides and versioned export packages | Product engineering | Original/feedback side-by-side review works; overrides persist; export contains only eligible student-result pairs. Preserve snippet edits and standards-mastery reporting; percentage conversion requires an explicit verified policy. Historical grades never become newly qualified results. |

### P4 Semester and class context

Entry: P3 accepted.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T4.1 | Student learning record and revision linkage | Learning engineering | History claims reference actual prior work; corrections invalidate derived summaries; no cross-course links. Optional student reflections retain provenance and affect feedback only unless the activated rubric explicitly assesses them. |
| T4.2 | Section snapshots and instructor teaching insights | Learning engineering | Coverage denominator is explicit; classmates' identities and raw essays are absent from personal feedback. All assignment entries, including missing and held work, are accounted for; first-five sampling and snippet usage are never presented as whole-class coverage. |
| T4.3 | Personalization separated from grading | Assessment engineering | Cohort/history changes cannot alter fixed scoring inputs; progress and revision priorities remain evidence-grounded. |

### P5 Processing routes and recovery

Entry: P3 accepted.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T5.1 | Permitted cloud route and usage accounting | Platform engineering | Only scrubbed authorized payloads leave; provider policy, spend caps, deadlines and request receipts are enforced. Adapted clients cannot call models directly; unavailable static/demo providers produce typed holds, not feedback, and storage/provider fallback remains explicit. |
| T5.2 | Mac companion with outbound leases | Platform engineering | Assigned jobs run locally; expired credentials fail; offline machine leaves jobs waiting; no cloud fallback. |
| T5.3 | Idempotency, resumable jobs and cancellation | Reliability engineering | Injected crashes resume completed stages without duplicate exports; uncertain provider charging is reconciled without blind replay. |

### P6 Qualification and term lifecycle

Entry: P4, P5 accepted.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T6.1 | Held-out grading and feedback benchmark | Quality lead | At least 50 authorized essays across assignments/sections; score and feedback thresholds pass separately per route. |
| T6.2 | Term cache, vault retention and deletion closure | Security engineering | All cache modes, term transitions, derived records, exports and backup tombstones pass expiry/restore tests. |
| T6.3 | Operational rehearsal and release decision | Release lead | Load, isolation, rollback, restore and wrong-student tests pass; unresolved release gates are explicit. |

### P7 Composition pilot and launch

Entry: P6 accepted.

| Tranche | Deliverable | Accountable role | Acceptance |
| --- | --- | --- | --- |
| T7.1 | One-assignment shadow run | Product lead | Instructor compares every pilot result; no automatic external distribution; documented error and effort measurements. |
| T7.2 | Multiple-section controlled pilot | Product lead | Qualified routes export full-class results; holds, overrides, costs and turnaround are measured against manifest coverage. |
| T7.3 | Accepted instructor release | Release lead | Whole-assignment success predicate passes; support/runbooks, recovery owner and next-term setup are demonstrated. |

## Execution sequence

P0 → P1 → P2 → P3. After P3, P4 and P5 can proceed independently; P6 requires both.
P7 follows a complete qualification and operational rehearsal. Within each phase, numbered
tranches execute in order. Capacity permits at most two implementation lanes and one heavy
local workload. Delegation requires broker reservation and exclusive write scopes.

P0 is a thin executable foundation. Its local HTML workbench is temporary validation UI;
the approved Next.js workspace remains T2.3. Ephemeral local encryption validates primitives;
it does not satisfy hosted KMS, durable vault, authentication, or restoration acceptance.
Regular expressions do not satisfy contextual de-identification. No AI evaluation is claimed.

The active implementation is T1.1 schema/authorization with PostgreSQL/RLS and API token verification.
Database integration qualification is pending; see [protected backend](protected-backend.md).
The following sequence is T1.2 identity/vault, then T1.3
staging. Work on synthetic fixtures remains possible while permitted student-processing
configuration is being resolved. Repository structure is apps/web, services/api,
workers, companion, and shared contracts as those components are introduced; the initial
Python package supplies reusable core contracts and a synthetic workbench.

## Management and operating cadence

- Program lead maintains the dependency graph, GitHub milestones, and phase issue acceptance.
- Product/learning lead owns rubric faithfulness, feedback usefulness, and course integration.
- Security lead owns threat boundaries, identity separation, retention, and release holds.
- Engineering lead owns implementation, migrations, reproducibility, and measured recovery.
- Quality/release lead owns independent qualification evidence and the accepted release decision.
- One person/agent may fill several roles; that never counts as independent review.
- Every tranche PR records what runs, exact checks, outstanding integration, and its owner issue.
- Status vocabulary here is planned, in_progress, implemented_verified, accepted. These are
  delivery dispositions, not Limen task states. No automatic closure of human acceptance atoms.
- Updating remote phase issues and delivery records is part of each completed implementation
  batch. Do not repeatedly rerun already green exact-tree checks.
- Session work is bounded to 30-minute attempts and 120 cumulative agent-minutes per approved
  outcome. Checkpoint honestly with pushed owner records when a bound is reached.

## Release and economics

The pilot remains private and single-instructor. No subscription billing, marketing site,
multi-institution tenancy, student portal, LMS publishing, email delivery, or speculative
model training is required for the agreed launch. These do not displace promised local/cloud
routes, whole-class intake, personalized semester feedback, or term-based retention.

No paid infrastructure or inference is provisioned in P0. In T1.3 and T5.1, record the actual
provider, region, policy, cost ceiling and credential reference. Secrets themselves stay outside
Git. Measure cost per essay and assignment; preflight limits must halt before the configured
ceiling. Keep unknown prices explicit until verified rather than promising a fictitious budget.

## Qualification and completion

The initial held-out benchmark contains at least 50 appropriately authorized essays, separate
from tuning examples. Each route must achieve at least 90% of scores within five percentage
points of instructor references, no unexplained discrepancy over ten points, and at least
90% feedback usability. Zero unsupported quotations, student-result mismatches, or seeded
identifier leaks are tolerated in the release test set. Sample confidence and subgroup/genre
coverage are recorded; a green small sample is not a universal validity claim.

Launch means a whole assignment across several sections reaches correct export-ready
results or explicit holds, with recoverable storage, attributable evidence, qualified models,
and demonstrated retention. A running demo, passing unit tests, or an open PR is not launch.

## Owner records

GitHub milestones and phase issues are the execution backlog. delivery/tranches.json is the
version-controlled dependency and acceptance contract. docs/receipts records observed evidence.
docs/release-gates.md owns missing production capabilities. The Page remains the original
design reference; its repository link is the route to current implementation truth.

### Parallel dashboard implementation authorization — 2026-10-12

The human authorized reusable dashboard integration while protected qualification gates are pending.
T2.3 presentation/components proceed against synthetic fixtures and a separate protected metadata
adapter. Its dependency and acceptance gates are unchanged. No student-processing path is enabled.
See [workspace integration](instructor-workspace.md) and the T2.3 receipt.
