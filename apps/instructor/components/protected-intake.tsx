"use client";
import { useEffect, useRef, useState } from "react";
import { loadCoursePage, type CoursePage } from "../lib/backend";
import { createFixture, readReview, submitReview, readWorkspace, createAssignment, resolveIntake, type Workspace, IntakeError, type ReviewView, type Decision } from "../lib/protected-intake";
export function ProtectedIntake({ configured }: { configured: boolean }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [assignment, setAssignment] = useState(""); const [enrollment, setEnrollment] = useState(""); const [reason, setReason] = useState("duplicate");
  const [courses, setCourses] = useState<CoursePage | null>(null);
  const [course, setCourse] = useState(""); const [fixture, setFixture] = useState("argument");
  const [view, setView] = useState<ReviewView | null>(null); const [decisions, setDecisions] = useState<Record<number, Decision>>({});
  const [status, setStatus] = useState("Protected fixture intake is separate from the local preview. Qualification pending.");
  const [busy, setBusy] = useState(false); const controller = useRef<AbortController | null>(null); const request = useRef<string | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function clear() { setWorkspace(null); setAssignment(""); setEnrollment(""); setView(null); setDecisions({}); request.current = null; }
  async function action(task: (signal: AbortSignal) => Promise<void>) {
    controller.current?.abort(); const current = new AbortController(); controller.current = current; setBusy(true);
    const timer = setTimeout(() => current.abort(), 15000);
    try { await task(current.signal); }
    catch (error) { if (controller.current === current) { setView(null); setDecisions({}); setStatus(current.signal.aborted ? "Protected request timed out. No automatic write retry." : error instanceof IntakeError ? error.message : "Protected service unavailable. No fixture fallback."); } }
    finally { clearTimeout(timer); if (controller.current === current) setBusy(false); }
  }
  async function load(after: string | null = null) {
    clear(); setCourses(null); setCourse("");
    await action(async signal => { const result = await loadCoursePage(signal, after); setCourses(result); setCourse(result.items[0]?.id ?? ""); setStatus(result.items.length ? "Choose an authorized course and a server-owned fixture." : "No courses in this authorized scope."); });
  }
  async function ingest() {
    request.current ??= crypto.randomUUID(); const key = request.current; setView(null); setDecisions({});
    await action(async signal => { const created = await createFixture(course, fixture, key, signal); setView(await readReview(course, created.id, signal)); setStatus("Fixture persisted. Decide each passage; qualification holds remain."); });
  }
  async function review() {
    if (!view) return;
    await action(async signal => { const result = await submitReview(view, decisions, signal); setView(await readReview(course, result.id, signal)); setDecisions({}); setStatus("Review recorded at a new generation. Release remains held."); });
  }
  async function refresh() {
    setView(null); setWorkspace(null);
    await action(async signal => { setWorkspace(await readWorkspace(course, signal)); setStatus("Assignment rosters are snapshots. Coverage counts active matched documents, not approved work."); });
  }
  async function resolve(kind: "mapping" | "exclude" | "restore") {
    if (!view) return;
    await action(async signal => { const result = await resolveIntake(view, kind, assignment, enrollment, reason, signal); setView(await readReview(course, result.id, signal)); setDecisions({}); setWorkspace(await readWorkspace(course, signal)); setStatus("Resolution recorded. Privacy review must be repeated; qualification holds remain."); });
  }
  return <section className="panel" aria-labelledby="protected-intake-title"><h2 id="protected-intake-title">Protected intake and passage review</h2><p>Only server-owned fictional documents are accepted. Originals and review records stay in the identity vault; reviewed text uses the separate content vault.</p><p role="status">{status}</p><button disabled={!configured || busy} onClick={() => load()}>Load authorized intake courses</button>{courses?.next_cursor && <button disabled={busy} onClick={() => load(courses.next_cursor)}>Next intake course page</button>}{courses && <><label>Protected intake course<select disabled={busy} value={course} onChange={e => { clear(); setCourse(e.target.value); }}>{courses.items.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label><label>Server-owned fixture<select disabled={busy} value={fixture} onChange={e => { clear(); setFixture(e.target.value); }}><option value="argument">Argument · TXT</option><option value="literary">Literary · TXT</option><option value="contextual">Contextual disclosure · TXT</option><option value="docx-argument">Argument · DOCX</option><option value="pdf-held">PDF · worker qualification hold</option></select></label><button disabled={busy || !course} onClick={ingest}>Persist fictional intake</button></>}{course && <button disabled={busy} onClick={refresh}>Load protected assignment and exception queue</button>}{workspace && <><h3>Protected assignment roster</h3><p>{workspace.missing.length} expected submissions missing. {workspace.submissions.filter(r => r.excluded).length} excluded.</p>{workspace.sections.map(section => <button disabled={busy} key={section.id} onClick={() => action(async signal => { await createAssignment(course, section.id, signal); setWorkspace(await readWorkspace(course, signal)); })}>Create fictional assignment from {section.label}</button>)}<label>Assignment<select disabled={busy} value={assignment} onChange={e => { setAssignment(e.target.value); setEnrollment(""); }}><option value="">Choose assignment</option>{workspace.assignments.map(a => <option key={a.id} value={a.id}>{a.label} · {a.id.slice(0,8)}</option>)}</select></label><label>Expected enrollment<select disabled={busy} value={enrollment} onChange={e => setEnrollment(e.target.value)}><option value="">Choose enrollment</option>{workspace.expected.filter(e => e.assignment_id === assignment).map(e => <option key={e.enrollment_id} value={e.enrollment_id}>{e.enrollment_id}</option>)}</select></label><h3>Intake exceptions and review queue</h3>{workspace.submissions.map(row => <button disabled={busy} key={row.id} onClick={() => action(async signal => { setView(await readReview(course, row.id, signal)); setDecisions({}); })}>{row.id.slice(0,8)} · {row.excluded ? "excluded" : row.assignment_id ? "matched" : "unmatched"} · {row.state}</button>)}</>}{view && <><p>Mapping: {view.assignment_id ?? "unresolved"} · Enrollment: {view.enrollment_id ?? "unresolved"} · {view.excluded ? "excluded" : "active"}</p><button disabled={busy || !assignment || !enrollment} onClick={() => resolve("mapping")}>Record assignment and enrollment match</button><label>Resolution reason<select disabled={busy} value={reason} onChange={e => setReason(e.target.value)}><option value="duplicate">Duplicate</option><option value="wrong_assignment">Wrong assignment</option><option value="withdrawn">Withdrawn</option><option value="instructor_correction">Instructor correction</option></select></label><button disabled={busy} onClick={() => resolve(view.excluded ? "restore" : "exclude")}>{view.excluded ? "Restore intake" : "Exclude intake"}</button><p>State: {view.state} · review generation {view.review_generation}</p><ul>{view.holds.map(h => <li key={h}>{h.replaceAll("_", " ")}</li>)}</ul>{view.passages.map(p => <div className="exception" key={p.id}><h3>Passage {p.id}</h3><p className="essay">{p.text}</p><small>{p.flags.length ? p.flags.join(" · ") : "No detector flag; explicit review still required"}</small><label>Decision for passage {p.id}<select disabled={busy} value={decisions[p.id] ?? ""} onChange={e => { const next = { ...decisions }; if (e.target.value) next[p.id] = e.target.value as Decision; else delete next[p.id]; setDecisions(next); }}><option value="">Choose a decision</option><option value="retain">Retain context; direct identifiers stay scrubbed</option><option value="redact">Redact this passage</option><option value="hold">Hold for further review</option></select></label></div>)}<button disabled={busy || view.excluded || !view.passages.length || view.passages.some(p => !decisions[p.id])} onClick={review}>Record version-bound review</button><p>No grade, model call or release is enabled.</p></>}</section>;
}
