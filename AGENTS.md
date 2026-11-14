# Agent harness

A minimal coding agent (one `bash` tool, OpenAI-compatible `/chat/completions`) to be extended with dynamic tool and skill loading and with context compaction. `TASK.md` is the task as given; read it before planning.

- `baseline/agent.py` is the code as received: keep it as the "before" version for the measurements.
- The repo is public: keep personal details out.

## Layout

- `src/agent.py`: the agent loop. `--compact-at TOKENS` (0 = off) summarizes the history when the context reaches the threshold; bash output over 8k chars is capped to head + tail with the full text in `/tmp`. `--loading fixed` puts every service tool schema in `tools` and every skill body in the system prompt. `--loading dynamic` (default) keeps `tools` at `bash`, `load_skill`, `load_tools` and `call_tool`, and the system prompt carries only catalogs. Neither the system prompt nor `tools` changes during a session, including across compactions.
- `src/skills.py`: discovers skills only in `<cwd>/.agents/skills/*/SKILL.md`.
- `src/demo_tools.py`: mock team services (issues, ci, docs, metrics, deploy) with in-process state; `ci_run_pipeline` really runs pytest in the working directory.
- `demo/`: the project the benchmark task runs in (planted bug in `payments/currency.py`, skills in `demo/.agents/skills/`). Never fix the bug in the repo copy.
- `demo-long/`: the long benchmark task, three incidents at once (the same currency bug, a refund cap in `payments/refunds.py`, VAT truncation in `payments/tax.py`). Never fix these in the repo copy either. `src/demo_tools.py` picks the matching service seed from `DEMO_SCENARIO` (`short` or `long`); its failing CI logs live in `src/demo_data/`.
- `demo-feature/`: the feature benchmark, a vendored snapshot of marshmallow 4.4.0 (MIT, `a38b7f6`, docs and CI files stripped, `pythonpath = ["src"]` added) with 4 feature tickets (MM-201..204). Ticket texts are in `src/demo_data/feature/MM-*.md`, and the hidden acceptance tests in `src/demo_data/feature/acceptance/`; the agent must never see the tests. Don't implement the tickets in the repo copy.
- `src/bench.py` / `src/check.py`: run a task (`--task short|long|feature`) N times per loading mode and compaction threshold, in parallel (`-j`), on temp copies of its project, and judge each run per incident. Logs go to `runs/` (gitignored).
