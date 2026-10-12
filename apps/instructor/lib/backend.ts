export class ServiceError extends Error {
  constructor(public readonly kind: "login" | "forbidden" | "unavailable" | "invalid") { super(kind); }
}
export type ProtectedCourse = { id: string; term_id: string; title: string };
export type CoursePage = { items: ProtectedCourse[]; next_cursor: string | null };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
async function read(path: string, signal: AbortSignal, transport: typeof fetch): Promise<unknown> {
  let response: Response;
  try { response = await transport(path, { credentials: "same-origin", cache: "no-store", redirect: "error", signal, headers: { Accept: "application/json" } }); }
  catch { throw new ServiceError("unavailable"); }
  if (!response.ok) throw new ServiceError(response.status === 401 ? "login" : response.status === 403 ? "forbidden" : "unavailable");
  try { return await response.json(); } catch { throw new ServiceError("invalid"); }
}
export async function loadCoursePage(signal: AbortSignal, after: string | null = null, transport: typeof fetch = fetch): Promise<CoursePage> {
  if (after && !uuid.test(after)) throw new ServiceError("invalid");
  const session = await read("/v1/session", signal, transport) as Record<string, unknown>;
  if (!session || session.product !== "edu" || session.mfa_verified !== true || typeof session.instructor_id !== "string" || !uuid.test(session.instructor_id)) throw new ServiceError("invalid");
  const page = await read("/v1/courses" + (after ? "?after=" + encodeURIComponent(after) : ""), signal, transport) as CoursePage;
  if (!page || !Array.isArray(page.items) || page.items.length > 100 || !(page.next_cursor === null || typeof page.next_cursor === "string" && uuid.test(page.next_cursor))) throw new ServiceError("invalid");
  if (!page.items.every(c => c && typeof c.id === "string" && uuid.test(c.id) && typeof c.term_id === "string" && uuid.test(c.term_id) && typeof c.title === "string" && c.title.length <= 200)) throw new ServiceError("invalid");
  return page;
}
