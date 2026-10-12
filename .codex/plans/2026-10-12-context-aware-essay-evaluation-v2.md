# edu evaluator: predecessor integration addendum

Date: 2026-10-12. Owner: edu program lead. Status: planned integration, source review complete.

The user supplied the Teacher Dashboard React artifact and `4444J99/classroom-rpg-aetheria`
as previous versions after approving the evaluator build. This addendum preserves that
lineage and amends delivery sequencing. The original approved plan remains unchanged.

## Decision

Build the protected evaluator as a shared edu service. Use the earlier Teacher Dashboard
as the plain instructor workflow reference and Aetheria's extracted React components as
reuse candidates. Aetheria can later consume the same service through its own interface.
Its RPG presentation is a separate consumer concern; it does not change rubric scoring.
The approved Next.js instructor workspace and Python core remain the delivery targets.
No wholesale Vite/Spark migration or expansion into parent portals, games, or billing is
required to complete the essay pilot.

## Integration sequence

1. **P0: establish evidence.** Pin source versions, document actual runtime boundaries,
   identify overlapping workflows, and map each reuse item to an existing owner tranche.
2. **T1.1–T1.3: establish protected storage and authority.** Add scoped external-reference
   mappings for prior course/realm, assignment/quest and submission IDs. Legacy IDs and
   client-side role fields never confer authorization. Identity remains separate from content.
3. **T2.1–T2.3: adapt intake and instructor views.** Retain course/assignment setup, upload
   progress, exception review and student reflection capture. Extract presentation from
   Firebase/Spark hooks before reuse. Use synthetic import dry runs, with counts and explicit
   holds, before authorizing any historical classroom data transfer.
4. **T3.1: normalize three rubric shapes into inactive drafts.** Support Teacher Dashboard
   level points, Aetheria editor maxPoints, and Aetheria weighted levels. Preserve labels,
   descriptions, criterion provenance and source version. Never invent weights or silently
   equate standards mastery with a percentage. Instructor verification activates a version.
5. **T3.2–T3.3: adapt feedback and review.** Reuse snippet search/insertion and editable
   teacher review. The protected service owns evaluation, evidence, deterministic arithmetic,
   holds and release. Snippets cannot manufacture claims about a student's work. Imported
   grades/feedback remain historical records, not qualified evaluation results.
6. **T4.1–T4.3: restore full contextual intent.** Link reflections and actual prior work
   within the term/course scope. Report whole-assignment coverage, including missing and held
   work. Snippet usage analytics and five-sample summaries are not whole-class analysis.
7. **T5–T7: qualify both processing routes and the instructor pilot.** No browser-side model
   calls, silent storage fallback, or static-demo response may masquerade as assessment.
   A future Aetheria client must use the same authenticated job and release contracts.

## Acceptance

The existing eight phases and 24 tranches remain the delivery denominator. Updated acceptance
is in `delivery/tranches.json`; findings and exact source anchors are in `docs/legacy-review.md`.
No tranche becomes implemented merely because similar code exists in a predecessor. Component
reuse requires dependency/license accounting and new integration verification. No predecessor
build, live Firebase/Spark configuration, deployed privacy posture or assessment quality was
qualified during this source review.
