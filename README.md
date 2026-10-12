# edu essay evaluation

A private component of [edu](https://github.com/4444J99/edu-organism) for rubric-grounded evaluation,
personal feedback, and semester-long writing development across composition sections.

**Current build: synthetic intake foundation.** It runs a local workbench with invented essays,
direct-identifier replacement, encrypted temporary storage, rubric/evidence contracts, term-cache
policy previews and explicit review holds. It does not accept student uploads, call a model,
generate grades, or constitute the hosted pilot.

## Run the workbench

Requires Python 3.11+ and uv.

```sh
uv sync --locked --extra test
uv run essay-evaluation serve
```

Open http://127.0.0.1:8765. Select one of the three fictional essays and process it.
The service binds only to loopback. Each result stays held because contextual privacy review,
real assessment and route qualification are not implemented. The random ID is stable within
the demo session; temporary encrypted content is removed on shutdown. Do not deploy this
workbench publicly.

## Verify

```sh
uv run --locked --extra test pytest
python3 scripts/check_delivery.py
```

## Delivery

- [Approved implementation plan](.codex/plans/2026-10-12-context-aware-essay-evaluation.md)
- [Phases, tranches, sequence and acceptance](docs/delivery-program.md)
- [Machine-readable dependency graph](delivery/tranches.json)
- [Decisions and edu ownership](docs/decisions.md)
- [Production release gates](docs/release-gates.md)

Source: [Implementation plan Page](https://chatgpt.com/space/page_e0e6016aa0c48191bfc2cf643a47a9c0)
under [education](https://chatgpt.com/space/page_6acd2c920d308191b5d6866506d58481).
All classroom examples are invented. Student records and credentials never belong in Git.
