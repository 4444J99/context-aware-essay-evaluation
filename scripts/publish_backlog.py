"""Idempotently publish the versioned phase graph to this component's GitHub backlog."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = "4444J99/context-aware-essay-evaluation"


def api(endpoint, payload=None):
    command = ["gh", "api", endpoint]
    if payload is not None:
        command += ["--method", "POST", "--input", "-"]
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            capture_output=True, text=True, check=True, timeout=30)
    return json.loads(result.stdout)


def pages(endpoint):
    records = []
    for page in range(1, 11):
        batch = api(f"{endpoint}&page={page}&per_page=100")
        records.extend(batch)
        if len(batch) < 100:
            return records
    raise RuntimeError("pagination_bound_exceeded")


def main():
    data = json.loads((ROOT/"delivery/tranches.json").read_text())
    milestones = {m["title"]: m for m in pages(f"repos/{REPO}/milestones?state=all")}
    issues = {i["title"]: i for i in pages(f"repos/{REPO}/issues?state=all") if "pull_request" not in i}
    for phase in data["phases"]:
        title = f'{phase["id"]} {phase["title"]}'
        if title not in milestones:
            milestones[title] = api(f"repos/{REPO}/milestones", {
                "title": title, "description": "edu essay evaluation. Acceptance: " +
                " ".join(t["acceptance"] for t in phase["tranches"])})
        dependency = ", ".join(phase["depends_on"]) or "Authorized project creation"
        content = [
            f'Part of **edu**; implementation component: {REPO}.',
            "Accountable delivery owner: Codex project lead. Roles below identify responsibilities, not separate independent reviewers.",
            f"Entry dependencies: {dependency}.",
            "## Tranches",
        ]
        for t in phase["tranches"]:
            content.append(f'- [ ] **{t["id"]} {t["title"]}** — {t["owner"]}. Acceptance: {t["acceptance"]}')
        content += [
            "## Completion evidence",
            "Exact commit/PR, passing acceptance predicates, review dispositions, and demonstrated integration are required. Leave this issue open until accepted.",
            "Approved design: https://chatgpt.com/space/page_e0e6016aa0c48191bfc2cf643a47a9c0",
            "Delivery contract: delivery/tranches.json and docs/delivery-program.md in this repository.",
            "P0 is synthetic only. No real student processing or automatic grade release is authorized by a passing foundation test.",
        ]
        if title not in issues:
            issues[title] = api(f"repos/{REPO}/issues", {
                "title": title, "body": "\n\n".join(content),
                "milestone": milestones[title]["number"]})
        phase["issue_url"] = issues[title]["html_url"]
        phase["milestone_url"] = milestones[title]["html_url"]
        (ROOT/"delivery/tranches.json").write_text(json.dumps(data, indent=2)+"\n")
        print(f'{phase["id"]}: {phase["issue_url"]}', flush=True)


if __name__ == "__main__":
    main()
