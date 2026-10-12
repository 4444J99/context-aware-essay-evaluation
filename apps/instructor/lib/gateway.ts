export function backendOrigin(value: string | undefined, production: boolean): string | null {
  if (!value) return null;
  const url = new URL(value);
  const local = ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/" || (url.protocol !== "https:" && !(url.protocol === "http:" && local && !production))) throw new Error("pinned_backend_origin_required");
  return url.origin;
}
