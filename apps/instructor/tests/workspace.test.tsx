import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { emptyIntake, importFictionalBatch, coverage, resolveRecord } from "../lib/intake";
import { syntheticWorkspace, visibleSubmissions, updateSubmission, holds } from "../lib/workspace";
import { loadCoursePage, ServiceError } from "../lib/backend";
import { createFixture, readReview, submitReview, IntakeError } from "../lib/protected-intake";
import { ProtectedIntake } from "../components/protected-intake";
import { backendOrigin } from "../lib/gateway";
import { Dashboard } from "../components/dashboard";
import { RubricMatrix } from "../components/rubric-matrix";
const id = "11111111-1111-4111-8111-111111111111";
const session = { product: "edu", mfa_verified: true, instructor_id: id };
function mockFetch(replies: { status?: number; body: unknown }[], paths: string[] = []): typeof fetch {
  return (async (path: string | URL | Request, options?: RequestInit) => {
    paths.push(String(path)); assert.equal(options?.credentials, "same-origin"); assert.equal(options?.cache, "no-store"); assert.equal(options?.redirect, "error");
    const next = replies.shift(); assert.ok(next);
    return new Response(JSON.stringify(next.body), { status: next.status ?? 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
}
test("scope filtering and patching never alter another course or assignment", () => {
  const work = syntheticWorkspace();
  assert.equal(visibleSubmissions(work, "composition", "argument").length, 2);
  assert.equal(visibleSubmissions(work, "composition", "revision").length, 0);
  assert.deepEqual(updateSubmission(work, "composition", "argument", "essay-3", { feedback: "wrong scope" }), work);
  const updated = updateSubmission(work, "composition", "argument", "essay-1", { feedback: "draft", privacy: "reviewed" });
  assert.equal(updated.submissions[0].feedback, "draft"); assert.equal(work.submissions[0].feedback, "");
  assert.ok(holds(updated.submissions[0]).includes("Assessment route unqualified"));
  assert.ok(holds(updated.submissions[1]).includes("Enrollment match required"));
});
test("protected adapter verifies session, preserves pagination and uses same-origin only", async () => {
  const paths: string[] = [];
  const page = await loadCoursePage(new AbortController().signal, id, mockFetch([{ body: session }, { body: { items: [{ id, term_id: id, title: "Course" }], next_cursor: id } }], paths));
  assert.equal(page.next_cursor, id); assert.deepEqual(paths, ["/v1/session", `/v1/courses?after=${id}`]);
});
test("unauthenticated and unprovisioned responses never request courses", async () => {
  for (const [status, kind] of [[401, "login"], [403, "forbidden"]] as const) {
    const paths: string[] = [];
    await assert.rejects(loadCoursePage(new AbortController().signal, null, mockFetch([{ status, body: {} }], paths)), (e: unknown) => e instanceof ServiceError && e.kind === kind);
    assert.equal(paths.length, 1);
  }
});
test("malformed sessions, pages and cursors fail closed", async () => {
  await assert.rejects(loadCoursePage(new AbortController().signal, "https://other.example"), ServiceError);
  await assert.rejects(loadCoursePage(new AbortController().signal, null, mockFetch([{ body: { ...session, mfa_verified: false } }])), ServiceError);
  for (const body of [{ items: [], next_cursor: "unsafe" }, { items: [{ id, term_id: id, title: null }], next_cursor: null }, { items: Array(101).fill({ id, term_id: id, title: "x" }), next_cursor: null }]) {
    await assert.rejects(loadCoursePage(new AbortController().signal, null, mockFetch([{ body: session }, { body }])), ServiceError);
  }
});
test("network failure remains unavailable without synthetic fallback", async () => {
  await assert.rejects(loadCoursePage(new AbortController().signal, null, (async () => { throw new Error("private backend details"); }) as typeof fetch), (e: unknown) => e instanceof ServiceError && e.kind === "unavailable" && !e.message.includes("private"));
});
test("rubric table has semantic headers and escapes source text", () => {
  const html = renderToStaticMarkup(<RubricMatrix criteria={[{ id: "x", name: "<script>unsafe</script>", levels: [{ name: "Level", description: "Evidence", points: 2 }] }]} />);
  assert.ok(html.includes('scope="row"')); assert.ok(html.includes('scope="col"')); assert.ok(html.includes("&lt;script&gt;")); assert.ok(!html.includes("<script>"));
});
test("dashboard class selection, privacy holds, snippet insertion and writer isolation", async () => {
  const dom = new JSDOM("<!doctype html><div id='root'></div>", { url: "https://edu.example" });
  Object.defineProperty(globalThis, "window", { value: dom.window, configurable: true });
  Object.defineProperty(globalThis, "document", { value: dom.window.document, configurable: true });
  Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const container = document.getElementById("root")!; const root = createRoot(container);
  const button = (text: string) => [...container.querySelectorAll("button")].find(b => b.textContent?.includes(text))!;
  async function click(text: string) { await act(async () => button(text).dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }))); }
  async function select(index: number, value: string) { const element = container.querySelectorAll("select")[index]; await act(async () => { element.value = value; element.dispatchEvent(new dom.window.Event("change", { bubbles: true })); }); }
  try {
    await act(async () => root.render(<Dashboard />));
    assert.ok(container.textContent?.includes("No class loaded."));
    assert.equal(container.querySelector('input[type="file"]'), null);
    await click("Load fictional class");
    assert.ok(container.textContent?.includes("2 records · 1 enrollment exceptions"));
    await click("Insert reasoning snippet");
    assert.equal(container.querySelector("textarea")?.value, "Explain how this example supports your claim.");
    await click("Unmatched fictional record"); assert.equal(container.querySelector("textarea")?.value, "");
    assert.ok(container.textContent?.includes("Enrollment match required"));
    await click("Writer 01"); assert.ok(container.querySelector("textarea")?.value.includes("supports your claim"));
    const checkbox = container.querySelector('input[type="checkbox"]')!;
    await act(async () => checkbox.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })));
    assert.ok(!container.textContent?.includes("Contextual privacy review required"));
    assert.ok(button("Release unavailable").disabled);
    await select(2, "enroll-2");
    assert.ok(container.textContent?.includes("2 of 3 expected writers have one submission"));
    await click("Load fictional duplicate case");
    assert.ok(container.textContent?.includes("1 duplicate enrollment groups"));
    await click("Exclude essay-1-copy as duplicate");
    assert.ok(container.textContent?.includes("0 duplicate enrollment groups · 1 excluded records"));
    await click("Restore essay-1-copy");
    assert.ok(container.textContent?.includes("1 duplicate enrollment groups"));
    await select(1, "revision"); assert.equal(container.querySelector("textarea"), null);
    await select(0, "rhetoric"); await click("Writer 03");
    assert.ok(container.textContent?.includes("welcoming question")); assert.ok(!container.textContent?.includes("shift workers"));
  } finally { await act(async () => root.unmount()); dom.window.close(); }
});

test("gateway rejects browser-controlled URLs and insecure production transport", () => {
  assert.equal(backendOrigin(undefined, true), null);
  assert.equal(backendOrigin("http://127.0.0.1:8767", false), "http://127.0.0.1:8767");
  assert.equal(backendOrigin("https://backend.example", true), "https://backend.example");
  for (const value of ["http://127.0.0.1:8767", "http://remote.example", "https://user:password@backend.example", "https://backend.example/path", "https://backend.example?target=x", "file:///tmp/backend"]) assert.throws(() => backendOrigin(value, true));
});

test("whole-class imports are repeat-safe and retain an explicit expected denominator", () => {
  const empty = emptyIntake(); const loaded = importFictionalBatch(empty, "class");
  assert.equal(empty.work.submissions.length, 0);
  assert.equal(loaded.work.submissions.length, 3);
  assert.strictEqual(importFictionalBatch(loaded, "class"), loaded);
  assert.throws(() => importFictionalBatch(empty, "duplicate"));
  assert.throws(() => importFictionalBatch(empty, "arbitrary-file" as "class"));
  const report = coverage(loaded, "composition", "argument");
  assert.equal(report.roster.length, 3); assert.equal(report.covered, 1);
  assert.equal(report.unmatched.length, 1); assert.equal(report.missing.length, 2);
});
test("explicit matching is scope-bound, never overwrites existing enrollment and resets privacy", () => {
  let state = importFictionalBatch(emptyIntake(), "class");
  state.work = updateSubmission(state.work, "composition", "argument", "essay-2", { privacy: "reviewed", feedback: "Keep instructor draft" });
  assert.throws(() => resolveRecord(state, "composition", "argument", "essay-2", { kind: "match", enrollmentId: "enroll-3" }));
  assert.throws(() => resolveRecord(state, "composition", "argument", "essay-2", { kind: "match", enrollmentId: "enroll-1" }));
  assert.throws(() => resolveRecord(state, "rhetoric", "audience", "essay-2", { kind: "exclude", reason: "duplicate" }));
  const matched = resolveRecord(state, "composition", "argument", "essay-2", { kind: "match", enrollmentId: "enroll-2" });
  const row = matched.work.submissions.find(s => s.id === "essay-2")!;
  assert.equal(row.studentRef, "Writer 02"); assert.equal(row.privacy, "pending"); assert.equal(row.feedback, "Keep instructor draft");
  assert.equal(coverage(matched, "composition", "argument").covered, 2);
  assert.ok(holds(row).includes("Assessment route unqualified"));
  assert.equal(matched.events.at(-1)?.action, "match");
  assert.equal(matched.events.at(-1)?.scope, "composition/argument");
});
test("duplicate decisions preserve source, produce a log and reverse without hiding conflicts", () => {
  const initial = importFictionalBatch(emptyIntake(), "class");
  const duplicated = importFictionalBatch(initial, "duplicate");
  assert.strictEqual(importFictionalBatch(duplicated, "duplicate"), duplicated);
  assert.deepEqual(coverage(duplicated, "composition", "argument").duplicateEnrollmentIds, ["enroll-1"]);
  const excluded = resolveRecord(duplicated, "composition", "argument", "essay-1-copy", { kind: "exclude", reason: "duplicate" });
  assert.equal(excluded.work.submissions.length, duplicated.work.submissions.length);
  assert.equal(coverage(excluded, "composition", "argument").duplicateEnrollmentIds.length, 0);
  assert.equal(coverage(excluded, "composition", "argument").covered, 1);
  assert.strictEqual(resolveRecord(excluded, "composition", "argument", "essay-1-copy", { kind: "exclude", reason: "duplicate" }), excluded);
  const restored = resolveRecord(excluded, "composition", "argument", "essay-1-copy", { kind: "restore", reason: "review-again" });
  assert.equal(coverage(restored, "composition", "argument").duplicateEnrollmentIds.length, 1);
  assert.equal(restored.events.at(-1)?.sequence, 4);
  assert.equal(restored.work.submissions.at(-1)?.text, duplicated.work.submissions.at(-1)?.text);
});

const protectedView = { assignment_id: null, enrollment_id: null, excluded: false, id, course_id: id, source_revision: id, review_generation: 0, state: "privacy_pending" as const, holds: ["route_unqualified"], passages: [{ id: 1, start: 0, end: 8, flags: ["health_or_disability"], text: "Original" }] };
test("protected intake writes require CSRF and bind version/generation without write retries", async () => {
  const calls: { path: string; options?: RequestInit }[] = [];
  const transport = (async (path: string | URL | Request, options?: RequestInit) => {
    calls.push({ path: String(path), options });
    if (String(path) === "/auth/session") return Response.json({ product: "edu", csrf_token: "synthetic-csrf-value-000000000" });
    assert.equal((options?.headers as Record<string, string>)["X-CSRF-Token"], "synthetic-csrf-value-000000000");
    assert.equal(options?.credentials, "same-origin"); assert.equal(options?.redirect, "error");
    const body = JSON.parse(options?.body as string);
    assert.equal(body.source_revision, id); assert.equal(body.expected_generation, 0);
    return Response.json({ ...protectedView, review_generation: 1, state: "privacy_reviewed" });
  }) as typeof fetch;
  assert.equal((await submitReview(protectedView, { 1: "redact" }, new AbortController().signal, transport)).review_generation, 1);
  assert.equal(calls.length, 2);
  await assert.rejects(submitReview(protectedView, {}, new AbortController().signal, transport), IntakeError);
  assert.equal(calls.length, 2);
  let deniedCalls = 0;
  await assert.rejects(createFixture(id, "argument", id, new AbortController().signal, (async () => { deniedCalls++; return Response.json({}, { status: 401 }); }) as typeof fetch), IntakeError);
  assert.equal(deniedCalls, 1);
});
test("protected passage adapter rejects wrong scope and forged passage ranges", async () => {
  for (const value of [{ ...protectedView, course_id: "wrong-scope" }, { ...protectedView, passages: [{ ...protectedView.passages[0], end: 99 }] }]) {
    await assert.rejects(readReview(id, id, new AbortController().signal, (async () => Response.json(value)) as typeof fetch), IntakeError);
  }
});
test("protected dashboard persists a fixture and submits explicit passage decisions", async () => {
  const dom = new JSDOM("<!doctype html><div id='protected-root'></div>", { url: "https://edu.example" });
  Object.defineProperty(globalThis, "window", { value: dom.window, configurable: true });
  Object.defineProperty(globalThis, "document", { value: dom.window.document, configurable: true });
  Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const previous = globalThis.fetch; let generation = 0; let writes = 0;
  globalThis.fetch = (async (path: string | URL | Request, options?: RequestInit) => {
    const url = String(path);
    if (url === "/v1/session") return Response.json(session);
    if (url === "/v1/courses") return Response.json({ items: [{ id, term_id: id, title: "Protected synthetic course" }], next_cursor: null });
    if (url === "/auth/session") return Response.json({ product: "edu", csrf_token: "synthetic-csrf-value-000000000" });
    if (url.endsWith("/intake-workspace")) return Response.json({ assignments: [{ id, section_id: id, label: "Fictional assignment", roster_generation: 0 }], sections: [{ id, label: "A" }], enrollments: [{ id, section_id: id }], expected: [{ assignment_id: id, enrollment_id: id }], missing: [], submissions: [{ ...protectedView, review_generation: generation }] });
    if (url.endsWith("/roster")) {
      writes++; const body = JSON.parse(options?.body as string); assert.equal(body.expected_generation, 0); assert.deepEqual(body.enrollment_ids, []);
      return Response.json({ id, roster_generation: 1, invalidated_submissions: 1 });
    }
    if (options?.method === "POST") {
      assert.equal((options.headers as Record<string, string>)["X-CSRF-Token"], "synthetic-csrf-value-000000000"); writes++;
      if (url.endsWith("/review")) { assert.equal(JSON.parse(options.body as string).decisions["1"], "redact"); generation = 1; }
    }
    return Response.json({ ...protectedView, review_generation: generation, state: generation ? "privacy_reviewed" : "privacy_pending" });
  }) as typeof fetch;
  const container = document.getElementById("protected-root")!; const root = createRoot(container);
  const button = (text: string) => [...container.querySelectorAll("button")].find(b => b.textContent === text)!;
  async function click(text: string) { await act(async () => { button(text).dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })); }); }
  try {
    await act(async () => root.render(<ProtectedIntake configured />));
    await click("Load authorized intake courses"); await click("Persist fictional intake");
    assert.ok(container.textContent?.includes("Original")); assert.ok(button("Record version-bound review").disabled);
    const choice = [...container.querySelectorAll("label")].find(label => label.textContent?.startsWith("Decision for passage 1"))!.querySelector("select")!;
    await act(async () => { choice.value = "redact"; choice.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await click("Record version-bound review");
    assert.equal(writes, 2); assert.ok(container.textContent?.includes("privacy_reviewed"));
    assert.ok(container.textContent?.includes("route unqualified")); assert.ok(button("Record version-bound review").disabled);
    await click("Load protected assignment and exception queue");
    const assignmentChoice = [...container.querySelectorAll("label")].find(label => label.textContent?.startsWith("Assignment"))!.querySelector("select")!;
    await act(async () => { assignmentChoice.value = id; assignmentChoice.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    const member = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    assert.ok(member.checked);
    await act(async () => { member.click(); });
    await click("Record new roster version");
    assert.equal(writes, 3); assert.ok(container.textContent?.includes("New roster version recorded"));
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
});

test("protected resolution binds generation and rejects malformed mapping metadata", async () => {
  const { resolveIntake, readWorkspace } = await import("../lib/protected-intake");
  const signal = new AbortController().signal; let writes = 0;
  const transport = (async (path: string | URL | Request, options?: RequestInit) => {
    if (String(path) === "/auth/session") return Response.json({ product: "edu", csrf_token: "synthetic-csrf-value-000000000" });
    writes++; const body = JSON.parse(options?.body as string);
    assert.equal(body.action, "mapping"); assert.equal(body.expected_generation, 0); assert.equal(body.enrollment_id, id);
    return Response.json({ ...protectedView, review_generation: 1, assignment_id: id, enrollment_id: id });
  }) as typeof fetch;
  assert.equal((await resolveIntake(protectedView, "mapping", id, id, "", signal, transport)).assignment_id, id);
  assert.equal(writes, 1);
  await assert.rejects(readWorkspace(id, signal, (async () => Response.json({ assignments: [], sections: [], expected: [{ assignment_id: "bad", enrollment_id: id }], missing: [], submissions: [] })) as typeof fetch), IntakeError);
  await assert.rejects(readReview(id, id, signal, (async () => Response.json({ ...protectedView, assignment_id: id })) as typeof fetch), IntakeError);
});

test("roster adapter sends explicit members and generation without retrying stale updates", async () => {
  const { updateRoster } = await import("../lib/protected-intake"); let writes = 0;
  const transport = (async (path: string | URL | Request, options?: RequestInit) => {
    if (String(path) === "/auth/session") return Response.json({ product: "edu", csrf_token: "synthetic-csrf-value-000000000" });
    writes++; const body = JSON.parse(options?.body as string);
    assert.equal(body.expected_generation, 3); assert.deepEqual(body.enrollment_ids, []);
    return Response.json({}, { status: 409 });
  }) as typeof fetch;
  await assert.rejects(updateRoster(id, id, 3, [], new AbortController().signal, transport), IntakeError);
  assert.equal(writes, 1);
  await assert.rejects(updateRoster(id, id, 3, [id,id], new AbortController().signal, transport), IntakeError);
  assert.equal(writes, 1);
});
