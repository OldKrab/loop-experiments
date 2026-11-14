# Agent harness

A minimal coding agent (one `bash` tool, OpenAI-compatible `/chat/completions`) to be extended with dynamic tool and skill loading and with context compaction. `TASK.md` is the task as given; read it before planning.

- `baseline/agent.py` is the code as received: keep it as the "before" version for the measurements.
- The repo is public: keep personal details out.

## Layout

- `src/agent.py`: the agent loop. `--loading fixed` puts every service tool schema in `tools` and every skill body in the system prompt. `--loading dynamic` (default) keeps `tools` at `bash`, `load_skill`, `load_tools` and `call_tool`, and the system prompt carries only catalogs. Neither the system prompt nor `tools` changes during a session.
- `src/skills.py`: discovers skills only in `<cwd>/.agents/skills/*/SKILL.md`.
- `src/demo_tools.py`: mock team services (issues, ci, docs, metrics, deploy) with in-process state; `ci_run_pipeline` really runs pytest in the working directory.
- `demo/`: the project the benchmark task runs in (planted bug in `payments/currency.py`, skills in `demo/.agents/skills/`). Never fix the bug in the repo copy.
- `src/bench.py` / `src/check.py`: run the task N times per mode on temp copies of `demo/` and judge each run. Logs go to `runs/` (gitignored).
