# Implementation plan: Context-aware essay evaluation

Build a **private instructor workspace** that processes entire classes of essays, evaluates them against the assignment rubric, tracks writing development across a semester, and produces individualized feedback plus teaching insights.

The first version serves your multiple composition sections through **batch upload and export**. It supports an encrypted hosted vault, temporary working caches, and both cloud and local model processing.

## 1. Product behavior

For each assignment, you provide:

- Assignment instructions and rubric.

- Relevant readings, teaching notes, and optional annotated examples.

- A class roster and batch of essays.

- Your feedback preferences and any assignment-specific guidance.

The system produces:

| <p>Output</p> | <p>Contents</p> |
| - | - |
| Individual evaluation | Rubric scores, criterion explanations, and supporting essay passages |
| Personal feedback | Specific strengths, two or three revision priorities, and a useful reflection question |
| Passage comments | Comments anchored to the student’s actual writing |
| Progress report | Evidence of development relative to previous work within the course |
| Class overview | Common strengths, misunderstandings, and suggested teaching priorities |
| Export package | Individual feedback documents, grade spreadsheet, and processing manifest |

**The rubric and current submission determine the grade.** Prior work informs developmental feedback. Class patterns inform teaching and feedback emphasis, without silently curving grades.

Supported evaluations become export-ready automatically. Exceptions enter an instructor review queue. The pilot does not email students, publish grades to an LMS, or create student accounts.

## 2. Instructor workflow

1. **Create a term and sections.** Set dates, processing permissions, retention policy, and feedback defaults.

2. **Set up the assignment.** Upload instructions and rubric; inspect the extracted criteria, weights, and score ranges before activating that rubric version.

3. **Import the class batch.** Upload essays and a roster; resolve unmatched submissions and extraction problems.

4. **Run evaluation.** See progress by submission and stage, with estimated and actual model usage.

5. **Review exceptions and inspect results.** Open the original essay alongside its evaluation, evidence, and privacy transformations.

6. **Export.** Download feedback and grades for all eligible submissions. Clearly identify held, missing, or failed submissions.

7. **Process revisions.** Upload another version under the same assignment; compare writing changes and responses to previous feedback.

Instructor corrections create versioned overrides. They never disappear when a model reruns. Reusing a correction as general teaching guidance requires an explicit “apply to future feedback” action.

## 3. Architecture and technology

Use a monorepo with four application components:

| <p>Component</p> | <p>Responsibility</p> | <p>Proposed implementation</p> |
| - | - | - |
| Instructor web app | Setup, upload, review, class insights, exports | Next.js and TypeScript |
| Application API | Authorization, records, policies, workflow | Python FastAPI with validated request/response schemas |
| Background workers | Extraction, scrubbing, evaluation, validation, export | Python workers using a PostgreSQL-backed job queue |
| Mac companion | Execute assigned local-model jobs | Python service with a small command-line interface |

Supporting services:

- **PostgreSQL:** relationships, workflow state, version records, and audit metadata.

- **Private object storage:** encrypted originals, normalized documents, evaluations, and exports.

- **Managed key service:** encryption-key protection and access separation.

- **OIDC authentication with MFA:** instructor access.

- **Provider adapters:** cloud inference and a local inference endpoint through the companion.

Keep student-bearing text in encrypted payloads. Database workflow rows should contain opaque references and necessary operational metadata rather than essay bodies.

Use containers for hosted deployment, migrations under version control, and separate development, staging, and production environments. Development and routine CI use synthetic student records.

Hosting location, cloud provider, and model are deployment configuration—not hardcoded assumptions. Real student processing remains disabled until those configurations are explicitly permitted for the course.

## 4. Data model and interfaces

The core relationships are:

**Instructor → Term → Course → Section → Enrollment → Submission**

Assignments belong to courses and can be assigned to several sections.

Version the following records:

- Assignment instructions and rubric.

- Submission and normalized document.

- De-identification transformation.

- Instructor feedback guidance.

- Evaluation and instructor override.

- Student learning record.

- Class snapshot.

- Processing and retention policy.

Maintain a separate **IdentityLink** connecting roster identity to a random course-and-term-scoped student ID. Do not derive IDs from names, emails, or student numbers. No automatic linking across courses or terms.

Each evaluation records:

- Exact submission, rubric, and guidance versions.

- Processing route, model identity, and evaluation configuration.

- Context references used.

- Criterion scores and evidence anchors.

- Feedback and revision priorities.

- Validation findings and release status.

Implement these interface groups:

| <p>Interface</p> | <p>Required behavior</p> |
| - | - |
| Import | Create upload batches; report extraction and roster-matching results |
| Assignment configuration | Activate validated rubric and guidance versions |
| Evaluation jobs | Start, inspect, cancel, and resume processing |
| Review | Resolve exceptions and save instructor overrides |
| Export | Generate documents and CSV from a fixed set of result versions |
| Retention | Preview and apply policy actions with audit receipts |
| Companion | Claim authorized local jobs, heartbeat, and return validated results |

Mutating requests accept idempotency keys. Repeated requests must not create duplicate submissions, model charges, or exports.

## 5. Ingestion and identity protection

### Supported input

The pilot accepts:

- DOCX.

- Text-based PDF.

- TXT.

- ZIP batches containing those formats.

- CSV rosters.

Detect scanned PDFs and hold them as requiring OCR; do not evaluate empty or incomplete extraction. OCR can be added after the initial pipeline is validated.

Validate file type, size, archive expansion limits, malformed documents, and password protection. Parse files in isolated workers without document-triggered network access.

### Processing sequence

1. Store the original in the encrypted vault.

2. Extract document structure and text.

3. Match the submission to an enrollment.

4. Assign or retrieve the random student ID.

5. Produce a clean evaluation copy.

6. Scan that copy for identifying and sensitive information.

7. Validate the transformation before inference.

Roster matching prioritizes explicit upload mappings and identifiers. Filename or name similarity may suggest matches but cannot silently resolve ambiguity.

### Scrubbing rules

Remove identifying information from evaluation copies, including:

- Student names and institutional identifiers.

- Personal email addresses, phone numbers, and addresses.

- Identifying headers and filenames.

- Document author metadata, comments, and tracked-change history.

- Contextual details that could reveal the writer or another private person.

Use consistent placeholders such as `[PERSON_1]` and `[LOCATION_1]`. Preserve paragraph structure and maintain a protected mapping between original and scrubbed passages.

Do not indiscriminately remove literary characters, cited authors, historical figures, or information necessary to understand an argument.

Combine deterministic detection with contextual analysis inside the controlled ingestion boundary. Raw text must not be sent to an external service merely to prepare it for that service.

If redaction materially damages meaning, or identifying details cannot be resolved reliably, hold the submission for review.

**Call this pseudonymization, not guaranteed anonymity.** Essays can remain identifiable through distinctive narratives even after direct identifiers are removed. Treat scrubbed copies as protected student material. [NIST guidance](https://csrc.nist.gov/pubs/ir/8053/final)

## 6. Encryption and access boundaries

Separate three security domains:

| <p>Domain</p> | <p>Contents</p> | <p>Access</p> |
| - | - | - |
| Identity | Roster details and identity mappings | Authorized instructor and narrowly scoped identity service |
| Student archive | Originals, history, feedback, transformations | Authorized application services |
| Evaluation | Scrubbed submission and bounded context package | Assigned evaluation worker or permitted provider |

Use TLS in transit and authenticated envelope encryption for sensitive stored payloads, with separate key access for identity mappings and student content. Object-storage encryption adds another layer. Managed KMS-backed object encryption is an established implementation option. [AWS documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html)

Additional requirements:

- Evaluation workers cannot retrieve identity mappings.

- Mac companions receive only assigned job context.

- Short-lived download links require authorization before issuance.

- Logs contain opaque IDs, timings, and error categories—not essay text or prompts.

- Crash reporting and tracing must redact sensitive request bodies.

- Database authorization includes section ownership checks and row-level security using non-owner application roles. [PostgreSQL documentation](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)

Encryption does not prevent an authorized processing service from seeing plaintext during inference. The product must describe that boundary accurately.

## 7. Evaluation pipeline

Use staged processing so each type of context has a defined role.

### A. Assignment preparation

Convert the rubric into validated criteria, descriptors, score ranges, and weights. Preserve its original wording alongside the structured representation.

Require an explicit grading rule for nonnumeric rubrics before generating numeric grades. Do not invent weights, penalties, or missing requirements.

### B. Independent essay assessment

Evaluate each complete essay against the active assignment and rubric.

For each criterion, produce:

- Proposed score.

- Explanation.

- Supporting passage anchors.

- Missing evidence or uncertainty.

Do not include prior grades or cohort performance in this scoring stage. Do not silently truncate essays that exceed the model’s input capacity; hold them or use a separately validated long-document route.

### C. Class analysis

After initial assessments, construct a versioned section snapshot containing:

- Criterion-level distributions.

- Recurring strengths and difficulties.

- Submission coverage and unresolved cases.

- Suggested teaching priorities.

Exclude peer identities and raw classmates’ essays from individual feedback context. Label incomplete batches explicitly. Cross-section comparisons require an instructor action and show each section separately.

### D. Student personalization

Use the current assessment plus bounded, relevant history:

- Previous work addressing the same writing skills.

- Prior feedback and instructor corrections.

- Revision evidence.

- Student-provided writing goals, when available.

Generate personalized feedback while preserving the already established rubric score.

History must describe observed writing behavior, not inferred intelligence, personality, diagnosis, motivation, or fixed ability.

### E. Validation and release

Validate outputs before making them export-ready:

- Scores fit rubric ranges; totals are calculated in code.

- Quoted evidence exists in the selected document version.

- Passage anchors survive transformation back to the original.

- Historical claims have supporting records.

- Feedback does not expose identifying details or peer information.

- Comments address the actual assignment.

- No unsupported citation-verification or misconduct claims appear.

Use a separate critique pass for substantive inconsistencies. Model agreement or self-reported confidence alone is insufficient for release.

Treat essays as untrusted content: embedded instructions cannot change scoring policy, access tools, or trigger external actions. This boundary addresses the prompt-injection risk described by [OWASP](https://genai.owasp.org/llm-top-10/).

## 8. Feedback design and semester memory

Default feedback should contain:

- A short, specific account of what works.

- Two or three priorities, emphasizing argument, development, evidence, and organization before surface corrections.

- Passage comments explaining why a change matters.

- Concrete next steps without rewriting the whole essay.

- One question that invites revision or reflection.

- A progress observation only when supported by prior work.

The learning record stores evidence-backed observations linked to assignments. It distinguishes instructor-confirmed feedback from automatically generated observations.

Retrieve history by course, assignment sequence, and rubric skill. Start with structured retrieval; a general-purpose vector database is unnecessary for the pilot.

When there is no history, say nothing about improvement or decline. When a prior evaluation is corrected, invalidate dependent learning summaries and regenerate them before future use.

## 9. Cloud and local processing

Both routes implement the same evaluation contract and validation requirements.

**Cloud route**

- Send only the permitted scrubbed context.

- Enforce a course-level provider allowlist.

- Record the actual model and configuration used.

- Configure request deadlines, usage limits, and bounded retries.

- Do not assume provider retention behavior; verify it during deployment setup.

**Local route**

- The Mac companion makes outbound authenticated connections.

- It retrieves a short-lived job lease and minimal context package.

- It evaluates through a configured local inference runtime.

- It returns results and removes temporary working material.

- Jobs wait when the Mac is offline.

No silent local-to-cloud fallback. The two routes qualify independently against the quality benchmark. If local hardware or model quality is insufficient, local results remain review-required.

## 10. Retention and hot-cache policy

Support both requested controls:

1. Different policies for different terms.

2. Working material retained through an active semester when configured.

Keep separate policies for:

| <p>Data</p> | <p>Proposed pilot default</p> |
| - | - |
| Decrypted processing files | Purge after the job; recover interrupted-job remnants within 24 hours |
| Encrypted working cache | Retain through the active term, then expire after a configurable grace period |
| Original essays and official results | Retain in the encrypted vault under the configured course policy |
| Identity mapping | Retain only while identifiable course records require it |
| Export downloads | Expire after seven days; regenerate from retained results |
| Audit records | Retain content-free operational evidence under a separate policy |

The active-term cache is encrypted working storage, not semester-long plaintext storage.

Term closure moves records out of the working set; it does not silently delete the authoritative archive. Configure vault deletion separately before production use.

Deletion must cover originals, derivatives, learning summaries, exports, temporary files, and backup-expiration behavior. Track deletion requests through completion, and prevent restored backups from resurrecting deleted records.

## 11. Reliability, review, and observability

Use a resumable state machine:

**Received → Extracted → Matched → Scrubbed → Assessed → Personalized → Validated → Export-ready**

Any stage may enter **Held**, **Failed**, or **Cancelled**, with a specific reason and next action.

- Save each completed stage against immutable input versions.

- Retry transient failures at most twice.

- Do not automatically retry unchanged validation failures.

- Preserve successful submissions when another submission fails.

- Supersede results explicitly after rubric or submission changes.

- Show model usage and enforce per-run and per-term budgets.

The review queue groups exceptions by cause: identity mismatch, extraction failure, privacy concern, unsupported assessment, or inconsistent evaluation.

Monitor extraction failures, privacy holds, unsupported evidence, instructor overrides, processing time, usage, and export failures. Content-free metrics should identify regressions without collecting student prose.

## 12. Testing and acceptance

Build a synthetic test suite and a separate, appropriately authorized instructor-scored benchmark.

| <p>Area</p> | <p>Acceptance criteria</p> |
| - | - |
| Ingestion | Supported documents preserve essay order and content; malformed or incomplete files are held |
| Identity | Ambiguous matches never attach automatically to a student |
| Privacy | Seeded identifiers do not reach evaluation payloads, logs, or unauthorized exports |
| Isolation | Attempts to access another section, identity mapping, or unassigned companion job fail |
| Evidence | Every emitted quotation and passage anchor resolves to the selected submission |
| Scoring | Totals match configured rubric arithmetic exactly |
| History | Progress statements cite prior evidence; no history produces no invented progress |
| Cohort independence | Changing classmates’ essays does not change a fixed essay’s scoring inputs or stored assessment |
| Recovery | Restarts resume work without duplicating results or charges from completed stages |
| Retention | Expiry and deletion tests cover caches, derivatives, downloads, and restore handling |
| Export | Correct students receive correct documents; held submissions cannot masquerade as completed grades |

For automated grading qualification, use an initial benchmark of at least 50 essays across multiple assignments and sections, including atypical and borderline cases. Keep tuning examples separate from the held-out evaluation set.

Proposed pilot thresholds:

- At least 90% of total scores within five percentage points of instructor reference scores.

- No unexplained discrepancy greater than ten percentage points.

- At least 90% of sampled feedback rated usable without substantive correction.

- Zero unsupported quotations, student-result mismatches, or seeded identifier leaks in the release test set.

These are initial engineering gates, not claims of universal grading validity. Inspect disagreement by rubric criterion and essay type. A failing route remains review-required rather than lowering the threshold to release it.

## 13. Implementation sequence

| <p>Phase</p> | <p>Deliverable</p> | <p>Exit condition</p> |
| - | - | - |
| 1. Foundation | Authentication, sections, encrypted vault, identity separation, versioned records | Isolation and encryption tests pass |
| 2. Ingestion | Batch uploads, extraction, roster matching, scrubbing, passage mapping | Synthetic class processes with correct holds and privacy checks |
| 3. Evaluation | Rubric scoring, evidence validation, feedback, exceptions, exports | Complete assignment works end to end in review-required mode |
| 4. Semester and class context | Learning history, revisions, section summaries | Historical claims are grounded; grades remain cohort-independent |
| 5. Processing routes | Cloud adapter, Mac companion, job recovery, usage controls | Each route passes functional and recovery tests independently |
| 6. Qualification and retention | Benchmarking, term lifecycle, backup restore, deletion checks | Qualified routes can automatically release eligible results |
| 7. Pilot | Several composition sections using upload/export | Full-class results, exceptions, overrides, and operating costs are measured |

Deliver application code, database migrations, deployment configuration, synthetic fixtures, benchmark tooling, an instructor guide, and operational runbooks in a dedicated repository. Keep all student records and real evaluation datasets outside Git.

The pilot is complete when an entire assignment batch can move from upload to correctly attributed feedback and grades, with privacy controls, semester context, exception handling, recovery, and retention behavior all demonstrated—not merely when the model can generate comments on one essay.
