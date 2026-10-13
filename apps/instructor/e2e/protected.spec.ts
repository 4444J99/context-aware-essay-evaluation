import { test, expect } from "@playwright/test";
// Browser interaction contract only: synthetic intercepted responses are not live auth/SQL proof.
test("protected roster history is read-only and clears when assignment changes", async ({ page }) => {
  const id = "11111111-1111-4111-8111-111111111111";
  const other = "22222222-2222-4222-8222-222222222222";
  const errors: string[] = []; let writes = 0;
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/v1/**", async route => {
    const request = route.request(); if (request.method() !== "GET") writes++;
    const path = new URL(request.url()).pathname;
    let body: unknown;
    if (path === "/v1/session") body = { product: "edu", instructor_id: id, authenticated: true, mfa_verified: true, real_student_processing: false };
    else if (path === "/v1/courses") body = { items: [{ id, term_id: id, title: "Synthetic protected course" }], next_cursor: null };
    else if (path.endsWith("/intake-workspace")) body = { assignments: [{ id, section_id: id, label: "Synthetic assignment", roster_generation: 1 }, { id: other, section_id: id, label: "Other assignment", roster_generation: 0 }], sections: [{ id, label: "A" }], enrollments: [{ id, section_id: id }], expected: [], missing: [], submissions: [] };
    else if (path.endsWith(`/assignments/${id}/roster`)) body = { assignment_id: id, course_id: id, current_generation: 1, items: [{ generation: 1, enrollment_ids: [], created_at: "2026-10-13T00:00:00Z" }, { generation: 0, enrollment_ids: [id], created_at: "2026-10-12T00:00:00Z" }], older_versions_available: false, next_before: null };
    else { await route.fulfill({ status: 404, json: { detail: "record_not_found" } }); return; }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  const panel = page.getByRole("region", { name: "Protected intake and passage review" });
  await panel.getByRole("button", { name: "Load authorized intake courses" }).click();
  await panel.getByRole("button", { name: "Load protected assignment and exception queue" }).click();
  await panel.getByLabel("Assignment", { exact: true }).selectOption(id);
  await panel.getByRole("button", { name: "Review roster history" }).click();
  await expect(panel.getByText("Current roster version 1.", { exact: false })).toBeVisible();
  await panel.getByText("Version 1 ·", { exact: false }).click();
  await expect(panel.getByText("Added: 0 · Removed: 1")).toBeVisible();
  await expect(panel.getByText(`Removed ${id}`, { exact: true })).toBeVisible();
  await panel.getByLabel("Assignment", { exact: true }).selectOption(other);
  await expect(panel.getByRole("heading", { name: "Roster history", exact: true })).toHaveCount(0);
  expect(writes).toBe(0); expect(errors).toEqual([]);
});
