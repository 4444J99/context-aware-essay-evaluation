"use client";
import { useEffect, useRef, useState } from "react";
import { loadCoursePage, type CoursePage } from "../lib/backend";
import { createFixture, readReview, submitReview, IntakeError, type ReviewView, type Decision } from "../lib/protected-intake";
export function ProtectedIntake({ configured }: { configured: boolean }) {
  const [courses, setCourses] = useState<CoursePage | null>(null);
  const [course, setCourse] = useState(""); const [fixture, setFixture] = useState("argument");
  const [view, setView] = useState<ReviewView | null>(null); const [decisions, setDecisions] = useState<Record<number, Decision>>({});
  const [status, setStatus] = useState("Protected fixture intake is separate from the local preview. Qualification pending.");
  const [busy, setBusy] = useState(false); const controller = useRef<AbortController | null>(null); const request = useRef<string | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function clear() { setView(null); setDecisions({}); request.current = null; }
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
  return <section className="panel" aria-labelledby="protected-intake-title"><h2 id="protected-intake-title">Protected intake and passage review</h2><p>Only server-owned fictional documents are accepted. Originals and review records stay in the identity vault; reviewed text uses the separate content vault.</p><p role="status">{status}</p><button disabled={!configured || busy} onClick={() => load()}>Load authorized intake courses</button>{courses?.next_cursor && <button disabled={busy} onClick={() => load(courses.next_cursor)}>Next intake course page</button>}{courses && <><label>Protected intake course<select disabled={busy} value={course} onChange={e => { clear(); setCourse(e.target.value); }}>{courses.items.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label><label>Server-owned fixture<select disabled={busy} value={fixture} onChange={e => { clear(); setFixture(e.target.value); }}><option value="argument">Argument · TXT</option><option value="literary">Literary · TXT</option><option value="contextual">Contextual disclosure · TXT</option><option value="docx-argument">Argument · DOCX</option><option value="pdf-held">PDF · worker qualification hold</option></select></label><button disabled={busy || !course} onClick={ingest}>Persist fictional intake</button></>}{view && <><p>State: {view.state} · review generation {view.review_generation}</p><ul>{view.holds.map(h => <li key={h}>{h.replaceAll("_", " ")}</li>)}</ul>{view.passages.map(p => <div className="exception" key={p.id}><h3>Passage {p.id}</h3><p className="essay">{p.text}</p><small>{p.flags.length ? p.flags.join(" · ") : "No detector flag; explicit review still required"}</small><label>Decision for passage {p.id}<select disabled={busy} value={decisions[p.id] ?? ""} onChange={e => { const next = { ...decisions }; if (e.target.value) next[p.id] = e.target.value as Decision; else delete next[p.id]; setDecisions(next); }}><option value="">Choose a decision</option><option value="retain">Retain context; direct identifiers stay scrubbed</option><option value="redact">Redact this passage</option><option value="hold">Hold for further review</option></select></label></div>)}<button disabled={busy || !view.passages.length || view.passages.some(p => !decisions[p.id])} onClick={review}>Record version-bound review</button><p>No grade, model call or release is enabled.</p></>}</section>;
}
