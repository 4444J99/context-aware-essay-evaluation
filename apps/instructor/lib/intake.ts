import { syntheticWorkspace, type Submission, type Workspace } from "./workspace";
export type Enrollment = { id: string; courseId: string; assignmentId: string; label: string };
export const fictionalRoster: Enrollment[] = [
  { id: "enroll-1", courseId: "composition", assignmentId: "argument", label: "Writer 01" },
  { id: "enroll-2", courseId: "composition", assignmentId: "argument", label: "Writer 02" },
  { id: "enroll-4", courseId: "composition", assignmentId: "argument", label: "Writer 04" },
  { id: "enroll-3", courseId: "rhetoric", assignmentId: "audience", label: "Writer 03" }
];
export type IntakeEvent = { sequence: number; action: "import" | "match" | "exclude" | "restore"; recordId: string; scope: string; detail: string };
export type IntakeState = { work: Workspace; events: IntakeEvent[]; imported: string[] };
export function emptyIntake(): IntakeState { return { work: { courses: syntheticWorkspace().courses, submissions: [] }, events: [], imported: [] }; }
function event(state: IntakeState, action: IntakeEvent["action"], recordId: string, course: string, assignment: string, detail: string): IntakeEvent {
  return { sequence: state.events.length + 1, action, recordId, scope: `${course}/${assignment}`, detail };
}
// Only named, generated fixtures are admitted. No arbitrary file/text intake before qualification.
export function importFictionalBatch(state: IntakeState, bundle: "class" | "duplicate"): IntakeState {
  if (bundle !== "class" && bundle !== "duplicate") throw new Error("unknown_fixture");
  if (state.imported.includes(bundle)) return state;
  if (bundle === "duplicate" && !state.imported.includes("class")) throw new Error("class_fixture_required");
  const source = syntheticWorkspace().submissions;
  const records: Submission[] = bundle === "class" ? source : [{ ...source[0], id: "essay-1-copy", text: "An alternate fictional draft also claims the same enrollment.", privacy: "pending", feedback: "" }];
  if (records.some(r => state.work.submissions.some(s => s.id === r.id))) throw new Error("record_id_conflict");
  return { work: { ...state.work, submissions: [...state.work.submissions, ...records] }, imported: [...state.imported, bundle], events: [...state.events, event(state, "import", bundle, "fixture", "batch", `${records.length} fictional records`)] };
}
export function coverage(state: IntakeState, courseId: string, assignmentId: string) {
  const roster = fictionalRoster.filter(e => e.courseId === courseId && e.assignmentId === assignmentId);
  const records = state.work.submissions.filter(s => s.courseId === courseId && s.assignmentId === assignmentId);
  const active = records.filter(s => !s.excluded);
  const duplicateEnrollmentIds = roster.filter(e => active.filter(s => s.enrollmentId === e.id).length > 1).map(e => e.id);
  return { roster, records, active, duplicateEnrollmentIds,
    missing: roster.filter(e => !active.some(s => s.enrollmentId === e.id)),
    unmatched: active.filter(s => !s.enrollmentId),
    covered: roster.filter(e => active.filter(s => s.enrollmentId === e.id).length === 1).length };
}
export function resolveRecord(state: IntakeState, courseId: string, assignmentId: string, recordId: string, decision: { kind: "match"; enrollmentId: string } | { kind: "exclude" | "restore"; reason: "duplicate" | "wrong-assignment" | "review-again" }): IntakeState {
  if (!["match", "exclude", "restore"].includes(decision.kind)) throw new Error("unknown_decision");
  const record = state.work.submissions.find(s => s.id === recordId && s.courseId === courseId && s.assignmentId === assignmentId);
  if (!record) throw new Error("record_outside_scope");
  let updated: Submission; let detail: string;
  if (decision.kind === "match") {
    const enrollment = fictionalRoster.find(e => e.id === decision.enrollmentId && e.courseId === courseId && e.assignmentId === assignmentId);
    if (!enrollment || record.excluded || record.enrollmentId) throw new Error("invalid_match");
    if (state.work.submissions.some(s => s.id !== recordId && !s.excluded && s.courseId === courseId && s.assignmentId === assignmentId && s.enrollmentId === enrollment.id)) throw new Error("enrollment_already_has_submission");
    updated = { ...record, enrollmentId: enrollment.id, studentRef: enrollment.label, match: "matched", privacy: "pending" }; detail = enrollment.id;
  } else {
    if (decision.kind === "exclude" && !["duplicate", "wrong-assignment"].includes(decision.reason) || decision.kind === "restore" && decision.reason !== "review-again") throw new Error("decision_reason_required");
    if (Boolean(record.excluded) === (decision.kind === "exclude")) return state;
    updated = { ...record, excluded: decision.kind === "exclude", privacy: "pending" }; detail = decision.reason;
  }
  // Decisions never erase source content or instructor drafts; excluded records remain reviewable.
  return { ...state, work: { ...state.work, submissions: state.work.submissions.map(s => s.id === recordId ? updated : s) }, events: [...state.events, event(state, decision.kind, recordId, courseId, assignmentId, detail)] };
}
