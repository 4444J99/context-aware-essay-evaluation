import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { syntheticWorkspace, visibleSubmissions, updateSubmission, holds } from "../lib/workspace";
import { loadCoursePage, ServiceError } from "../lib/backend";
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
