# Instructor workspace integration

Owner: Product engineering, T2.3 / P2 issue #3. Product parent: edu-organism issue #55.
The human authorized reusable dashboard work in parallel while qualification gates remain pending.
This changes execution order for presentation components, not acceptance dependencies.

## Run the synthetic preview

From `apps/instructor`, use Node 26 and run:

```sh
npm ci --ignore-scripts --no-fund
npm run dev
```

Open http://127.0.0.1:8766. The existing Python workbench at port 8765 is separate and preserved.
Load the fictional class, resolve the unmatched record against an expected enrollment, inspect
missing submissions, then load the duplicate case and exclude or restore a record. Select a writer,
inspect the rubric and reflection, mark synthetic privacy review, search snippets and edit a draft. Course/assignment changes
clear the selected writer. Drafts stay only in memory and reset on reload. No file/paste intake,
model call, grade calculation, external delivery or persistent feedback write is present.

The class denominator is an explicit fictional expected-enrollment manifest, separate from imported
records. Composition expects three writers: one matched submission, one unmatched record and two
initially missing writers. Explicitly matching the record to Writer 02 leaves Writer 04 missing.
Repeated fixture imports preserve existing drafts and decisions. Duplicate submissions reduce
coverage until one record is explicitly excluded; restoration brings the conflict back. Exclusion
never deletes the source. Assignment-scoped matching rejects occupied or cross-scope enrollment.
The in-memory decision log records import, match, exclusion and restoration; it is not a durable
server audit. Unmatched records remain exceptions until an explicit decision; no automatic guess. Completing
privacy review never clears rubric, assessment or release holds. No score is derived from history,
reflection, snippets or class composition.

## Reusable components and provenance

- Course and assignment selectors preserve Teacher Dashboard's course/assignment workflow.
- `RubricMatrix` adapts its `RubricDisplay` presentation pattern into typed criteria and semantic
  table headers. This fixture rubric remains a draft; three-format import validation is still T3.1.
- The writer view retains current work, optional reflection and editable feedback concepts from
  `StudentSampleForm`, using fictional references instead of name collection.
- `SnippetBank` retains category/content browsing and adds search and insertion. Suggestions are
  instructor draft material, with explicit evidence obligations; no model or persistence hook.
- `ProtectedCourses` is isolated from the fictional review dataset. It cannot substitute sample
  results for unavailable/unauthorized protected data.

Source identities and original locations are pinned in `docs/legacy-review.md` and
`delivery/sources.json`. The original download remains read-only. No Aetheria code was copied;
its review informs the workflow. Firebase, Spark, localStorage and browser model requests are
absent. These components can receive qualified service data later without retaining those hooks.

## Protected gateway

`EDU_BACKEND_ORIGIN` is operator-controlled server configuration. It accepts a single HTTPS origin
with no credentials, path, query or fragment. Development alone permits explicit loopback HTTP.
The default has no gateway, disables the connect action and omits sign-in instead of linking to a
missing route. Never expose the development server publicly.

The Next.js gateway forwards only `/auth/*` and `/v1/*` to the configured protected service. The
public HTTPS origin must equal backend `EDU_APP_ORIGIN`, and the issuer callback must be that
origin plus `/auth/callback`. Secure host cookies remain on the public origin. No access token or
client secret is sent to the React application. The metadata adapter checks `/v1/session` and its
MFA/product/instructor contract before each course page, validates bounded UUID-bearing responses,
uses no-store credentials and represents 401, 403 and unavailable/invalid states explicitly. Page
cursors are retained; a failed next page does not silently show stale data.

HTTPS gateway/cookie/login behavior against a live issuer and actual PostgreSQL is still a
qualification predicate. Same-origin CSRF/origin enforcement is implemented in the protected
backend; this slice only reads metadata and cannot save academic records. No auth bypass or
anonymous protected-data fallback exists.

## Verification and owned pending predicates

Run `npm run typecheck` and `npm test` from the app. Eleven component/contract tests pass.
After host admission clears, run `npm run build`, `npx playwright install chromium` and
`npm run test:browser`. Two Playwright flows are defined for class matching/duplicate resolution
and writer separation/mobile layout; test discovery passed, but actual browser execution is pending. Tests cover component interaction in JSDOM,
writer/course/assignment separation, holds after privacy review, snippet insertion, safe rubric
rendering, malformed/unauthorized responses, pagination and gateway restrictions. JSDOM is not a
real browser, visual review or database integration proof. Application and dependency declarations
are checked without disabling library type checks.

The CI instructor job owns type checking, component tests and `npm run build`. Existing GitHub
runner admission and local heavy admission blockers remain tracked in P1 issue #2. No unchanged
heavy retry or CI rerun is requested. Production build and actual browser smoke remain unexecuted
locally; after admission changes, run the build and a browser flow through HTTPS plus the protected
service. T2.3 acceptance additionally needs qualified whole-class intake, actual exception resolution
and privacy-review integration. T3.1–T3.3 own activated rubrics, evidence-grounded feedback and
exports. Hosted KMS/live OIDC qualification and physical retention remain T1.2/T1.3/T6.2.

## Protected intake panel

A separate panel now connects authorized course metadata, server-owned fixture extraction and
version/generation-bound passage decisions through the existing HTTPS gateway and CSRF session.
It is independent of local fictional-class state. See [protected intake](protected-intake.md).
Database and real browser qualification remain pending; no student upload is enabled.
