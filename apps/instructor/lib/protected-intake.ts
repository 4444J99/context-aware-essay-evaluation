export type IntakeView = { id: string; course_id: string; source_revision: string; review_generation: number; state: "extraction_held" | "privacy_pending" | "privacy_reviewed"; holds: string[]; assignment_id: string | null; enrollment_id: string | null; excluded: boolean };
export type ReviewView = IntakeView & { passages: { id: number; start: number; end: number; flags: string[]; text: string }[] };
export type Decision = "retain" | "redact" | "hold";
export class IntakeError extends Error {}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function identifier(value: string) { if (!uuid.test(value)) throw new IntakeError("Invalid protected record."); return value; }
export async function call(path: string, body: unknown, signal: AbortSignal, transport: typeof fetch): Promise<unknown> {
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) {
      const session = await transport("/auth/session", { credentials: "same-origin", cache: "no-store", redirect: "error", signal });
      if (!session.ok) throw new IntakeError("Protected session unavailable. Sign in again.");
      const value = await session.json();
      if (value.product !== "edu" || typeof value.csrf_token !== "string" || value.csrf_token.length < 16 || value.csrf_token.length > 256) throw new IntakeError("Protected session response invalid.");
      headers["X-CSRF-Token"] = value.csrf_token; headers["Content-Type"] = "application/json";
    }
    const response = await transport(path, { method: body === undefined ? "GET" : "POST", body: body === undefined ? undefined : JSON.stringify(body), headers, credentials: "same-origin", cache: "no-store", redirect: "error", signal });
    if (!response.ok) throw new IntakeError(response.status === 409 ? "Review or request conflict. Refresh before deciding again." : response.status === 401 || response.status === 403 ? "Protected session or instructor scope unavailable." : "Protected intake unavailable or request held.");
    return await response.json();
  } catch (error) { if (error instanceof IntakeError) throw error; throw new IntakeError("Protected intake unavailable. No automatic write retry."); }
}
function validate(value: unknown, course: string): IntakeView {
  const v = value as IntakeView;
  if (!v || typeof v.id !== "string" || !uuid.test(v.id) || v.course_id !== course || typeof v.source_revision !== "string" || !uuid.test(v.source_revision) || !Number.isSafeInteger(v.review_generation) || v.review_generation < 0 || !["extraction_held", "privacy_pending", "privacy_reviewed"].includes(v.state) || !Array.isArray(v.holds) || v.holds.length > 32 || !v.holds.every(h => typeof h === "string" && /^[a-z_]{1,80}$/.test(h))) throw new IntakeError("Protected intake response invalid.");
  if ((typeof v.excluded !== "boolean" || ![v.assignment_id, v.enrollment_id].every(id => id === null || typeof id === "string" && uuid.test(id)) || (v.assignment_id === null) !== (v.enrollment_id === null))) throw new IntakeError("Protected mapping response invalid.");
  return v;
}
export async function createFixture(course: string, fixture: string, requestId: string, signal: AbortSignal, transport: typeof fetch = fetch) {
  if (!["argument", "literary", "contextual", "docx-argument", "pdf-held"].includes(fixture)) throw new IntakeError("Unknown fixture.");
  return validate(await call(`/v1/courses/${identifier(course)}/intake`, { request_id: identifier(requestId), fixture_id: fixture }, signal, transport), course);
}
export async function readReview(course: string, submission: string, signal: AbortSignal, transport: typeof fetch = fetch): Promise<ReviewView> {
  const value = await call(`/v1/courses/${identifier(course)}/intake/${identifier(submission)}/review`, undefined, signal, transport) as ReviewView;
  validate(value, course);
  if (value.id !== submission || !Array.isArray(value.passages) || value.passages.length > 2000 || new Set(value.passages.map(p => p.id)).size !== value.passages.length || !value.passages.every(p => Number.isSafeInteger(p.id) && p.id > 0 && Number.isSafeInteger(p.start) && Number.isSafeInteger(p.end) && p.start >= 0 && p.end > p.start && typeof p.text === "string" && Array.from(p.text).length === p.end - p.start && Array.isArray(p.flags) && p.flags.every(f => typeof f === "string" && /^[a-z_]{1,80}$/.test(f))) || value.passages.reduce((n,p) => n + p.text.length, 0) > 200000) throw new IntakeError("Protected passage response invalid.");
  return value;
}
export async function submitReview(view: ReviewView, decisions: Record<number, Decision>, signal: AbortSignal, transport: typeof fetch = fetch) {
  if (Object.keys(decisions).length !== view.passages.length || !view.passages.every(p => ["retain", "redact", "hold"].includes(decisions[p.id]))) throw new IntakeError("Decide every passage explicitly.");
  const value = validate(await call(`/v1/courses/${identifier(view.course_id)}/intake/${identifier(view.id)}/review`, { source_revision: view.source_revision, expected_generation: view.review_generation, decisions }, signal, transport), view.course_id);
  if (value.id !== view.id || value.source_revision !== view.source_revision || value.review_generation !== view.review_generation + 1) throw new IntakeError("Protected review response invalid.");
  return value;
}

export type Workspace = { assignments: { id: string; section_id: string; label: string; roster_generation: number }[]; sections: { id: string; label: string }[]; expected: { assignment_id: string; enrollment_id: string }[]; missing: { assignment_id: string; enrollment_id: string }[]; submissions: IntakeView[]; enrollments: { id: string; section_id: string }[] };
export async function readWorkspace(course: string, signal: AbortSignal, transport: typeof fetch = fetch): Promise<Workspace> {
  const value = await call(`/v1/courses/${identifier(course)}/intake-workspace`, undefined, signal, transport) as Workspace;
  if (!value || ![value.assignments, value.sections, value.expected, value.missing, value.submissions, value.enrollments].every(a => Array.isArray(a) && a.length <= 1000)) throw new IntakeError("Protected workspace response invalid.");
  for (const a of value.assignments) { identifier(a.id); identifier(a.section_id); if (typeof a.label !== "string" || a.label.length > 120 || !Number.isSafeInteger(a.roster_generation) || a.roster_generation < 0) throw new IntakeError("Invalid assignment."); }
  for (const a of value.sections) { identifier(a.id); if (typeof a.label !== "string" || a.label.length > 120) throw new IntakeError("Invalid section."); }
  for (const a of [...value.expected, ...value.missing]) { identifier(a.assignment_id); identifier(a.enrollment_id); }
  for (const e of value.enrollments) { identifier(e.id); identifier(e.section_id); }
  for (const row of value.submissions) validate(row, course);
  return value;
}
export async function createAssignment(course: string, section: string, signal: AbortSignal) {
  await call(`/v1/courses/${identifier(course)}/assignments`, { section_id: identifier(section) }, signal, fetch);
}
export async function resolveIntake(view: IntakeView, action: "mapping" | "exclude" | "restore", assignment: string, enrollment: string, reason: string, signal: AbortSignal, transport: typeof fetch = fetch) {
  const body = { source_revision: identifier(view.source_revision), expected_generation: view.review_generation, action,
    ...(action === "mapping" ? { assignment_id: identifier(assignment), enrollment_id: identifier(enrollment) } : { reason }) };
  const value = validate(await call(`/v1/courses/${identifier(view.course_id)}/intake/${identifier(view.id)}/resolution`, body, signal, transport), view.course_id);
  if (value.id !== view.id || value.source_revision !== view.source_revision || value.review_generation !== view.review_generation + 1) throw new IntakeError("Protected resolution response invalid.");
  return value;
}

export async function updateRoster(course: string, assignment: string, generation: number, members: string[], signal: AbortSignal, transport: typeof fetch = fetch) {
  if (!Number.isSafeInteger(generation) || generation < 0 || members.length > 1000 || new Set(members).size !== members.length) throw new IntakeError("Invalid roster update.");
  const result = await call(`/v1/courses/${identifier(course)}/assignments/${identifier(assignment)}/roster`, { expected_generation: generation, enrollment_ids: members.map(identifier) }, signal, transport) as { id: string; roster_generation: number; invalidated_submissions: number };
  if (!result || result.id !== assignment || result.roster_generation !== generation + 1 || !Number.isSafeInteger(result.invalidated_submissions) || result.invalidated_submissions < 0 || result.invalidated_submissions > 1000) throw new IntakeError("Protected roster response invalid.");
  return result;
}

export type RosterVersion = { generation: number; enrollment_ids: string[]; created_at: string };
export type RosterHistory = { assignment_id: string; course_id: string; current_generation: number; items: RosterVersion[]; older_versions_available: boolean; next_before: number | null };
export async function readRosterHistory(course: string, assignment: string, before: number | null, signal: AbortSignal, transport: typeof fetch = fetch): Promise<RosterHistory> {
  if (before !== null && (!Number.isSafeInteger(before) || before < 1 || before > 2147483647)) throw new IntakeError("Invalid history cursor.");
  const value = await call(`/v1/courses/${identifier(course)}/assignments/${identifier(assignment)}/roster${before === null ? "" : `?before=${before}`}`, undefined, signal, transport) as RosterHistory;
  if (!value || value.assignment_id !== assignment || value.course_id !== course || !Number.isSafeInteger(value.current_generation) || value.current_generation < 0 || value.current_generation > 2147483647 || !Array.isArray(value.items) || value.items.length > 100 || typeof value.older_versions_available !== "boolean") throw new IntakeError("Protected roster history invalid.");
  let previous = before ?? value.current_generation + 1;
  for (const row of value.items) {
    if (!row || !Number.isSafeInteger(row.generation) || row.generation < 0 || row.generation >= previous || row.generation > value.current_generation || !Array.isArray(row.enrollment_ids) || row.enrollment_ids.length > 1000 || new Set(row.enrollment_ids).size !== row.enrollment_ids.length || !row.enrollment_ids.every(id => typeof id === "string" && uuid.test(id)) || typeof row.created_at !== "string" || row.created_at.length > 64 || !Number.isFinite(Date.parse(row.created_at))) throw new IntakeError("Protected roster version invalid.");
    previous = row.generation;
  }
  if (value.older_versions_available ? value.items.length !== 100 || value.next_before !== previous || previous < 1 : value.next_before !== null) throw new IntakeError("Protected history pagination invalid.");
  return value;
}
export function rosterChanges(newer: RosterVersion, older: RosterVersion) {
  const prior = new Set(older.enrollment_ids), next = new Set(newer.enrollment_ids);
  return { added: newer.enrollment_ids.filter(id => !prior.has(id)), removed: older.enrollment_ids.filter(id => !next.has(id)) };
}
