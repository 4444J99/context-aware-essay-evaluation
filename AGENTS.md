# Essay evaluation engineering protocol

Global policy at ~/AGENTS.md applies when present.

This public source repository owns the evaluator application. 4444J99/edu-organism owns course operations.
Public source visibility does not authorize publishing student records, vault contents or credentials.
The approved design is .codex/plans/2026-10-12-context-aware-essay-evaluation.md.
Execution order and acceptance gates live in docs/delivery-program.md and delivery/tranches.json.

- Never commit student records, roster identities, real essays, credentials, or model prompts containing them.
- Tests and development use synthetic fixtures exclusively until the protected pilot gate is satisfied.
- Scores depend on current submission and rubric; history and cohort affect feedback only.
- De-identification reduces exposure; it does not establish anonymity.
- Missing privacy, evidence, authentication, or model qualification gates hold output; never silently downgrade them.
- No automatic LMS delivery, email, cloud fallback, or cross-course identity linking.
- Changes use isolated branches/worktrees and a PR. Preserve concurrent work.
- Run uv run --extra test pytest and python3 scripts/check_delivery.py for implicated changes.
- Update the delivery receipt honestly: implemented component, verified integration, and production acceptance are distinct.
