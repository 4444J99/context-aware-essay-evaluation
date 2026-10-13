"""Validate delivery ownership, unique IDs and acyclic complete dependencies."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = json.loads((root / "delivery/tranches.json").read_text())
assert data["product"] == "edu"
phases = data["phases"]
assert data["phase_order"] == [p["id"] for p in phases]
items = [t for p in phases for t in p["tranches"]]
by_id = {t["id"]: t for t in items}
assert len(by_id) == len(items) == 24
assert all(t["owner"] and t["acceptance"] for t in items)
allowed = {"planned", "in_progress", "implemented_verified", "accepted"}
assert all(t["status"] in allowed for t in items)
visited = set()
active = set()
def visit(key):
    assert key in by_id, f"unknown dependency {key}"
    assert key not in active, f"cycle at {key}"
    if key in visited:
        return
    active.add(key)
    for parent in by_id[key]["depends_on"]:
        visit(parent)
    active.remove(key)
    visited.add(key)
for key in by_id:
    visit(key)
assert len(visited) == 24
assert (root / ".codex/plans/2026-10-12-context-aware-essay-evaluation.md").is_file()
print("PASS: edu ownership; 8 phases; 24 owned tranches; complete acyclic dependencies")
