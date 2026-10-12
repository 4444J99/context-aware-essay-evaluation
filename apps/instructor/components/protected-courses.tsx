"use client";
import { useEffect, useRef, useState } from "react";
import { loadCoursePage, ServiceError, type CoursePage } from "../lib/backend";
export function ProtectedCourses({ configured }: { configured: boolean }) {
  const [page, setPage] = useState<CoursePage | null>(null);
  const [status, setStatus] = useState(configured ? "Not connected. Qualification pending." : "Protected gateway is not configured. Qualification pending.");
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function connect(after: string | null = null) {
    controller.current?.abort(); const current = new AbortController(); controller.current = current;
    setBusy(true); setPage(null); setStatus("Checking protected session…");
    try { const next = await loadCoursePage(current.signal, after); if (!current.signal.aborted) { setPage(next); setStatus(next.items.length ? "Protected course metadata loaded." : "No courses in this authorized scope."); } }
    catch (error) { if (!current.signal.aborted) setStatus(error instanceof ServiceError && error.kind === "login" ? "Sign in to the protected service first." : error instanceof ServiceError && error.kind === "forbidden" ? "Instructor access is not provisioned." : "Protected service unavailable or response invalid. No sample fallback."); }
    finally { if (!current.signal.aborted) setBusy(false); }
  }
  return <section className="panel" aria-labelledby="protected-title"><h2 id="protected-title">Protected course service</h2><p>This separate connection reads authorized course metadata. The review workspace below contains fictional records only.</p><p role="status">{status}</p><div className="actions"><button disabled={busy || !configured} onClick={() => connect()}>Connect protected courses</button>{configured && <a href="/auth/login">Sign in</a>}</div>{page && <><ul>{page.items.map(c => <li key={c.id}>{c.title}</li>)}</ul>{page.next_cursor && <button disabled={busy} onClick={() => connect(page.next_cursor)}>Next course page</button>}</>}</section>;
}
