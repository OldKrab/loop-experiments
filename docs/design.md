# Design: dynamic loading of skills and tools

Decisions for `src/`. Background research: `docs/dynamic-tool-loading.md`.

## Switch

- One flag, `--loading fixed|dynamic` (default `dynamic`), covers both tools and skills.
- `fixed`: `tools` = `bash` + every service tool schema; every skill body is inlined in the system prompt.
- `dynamic`: `tools` = `bash`, `load_skill`, `load_tools`, `call_tool`; the system prompt carries only catalogs.
- `baseline/agent.py` stays untouched and is not benchmarked: the test backend requires `reasoning_content` to be passed back, which the baseline drops, and it lacks the tools and skills the task needs. `fixed` is the "before" version.

## Prompt cache

- The system prompt and `tools` are built once per session and never change.
- Loaded skill bodies and tool schemas arrive as tool results appended to the history.
- Assistant messages are appended exactly as received, including `reasoning_content`.

## Skills

- Read only from `<cwd>/.agents/skills/<name>/SKILL.md` (Agent Skills format); no global skills.
- Frontmatter parsed with `pyyaml`; skills without `name` or `description` are skipped with a warning.
- `load_skill(name)` returns the body wrapped in `<skill_content>`; a repeat load returns "already loaded".
- Skills don't declare tools; a skill body lists the tool names it uses.
- Fixed mode inlines each skill with its description ("When to use: ..."), and both modes say to follow a skill only when its description matches the task.

## Tools

- Mock team services that bash can't reach (state lives in the harness process): `issues`, `ci`, `docs`, `metrics`, `deploy`; 20 tools.
- Plain Python functions with hand-written schema dicts, in `src/demo_tools.py`. No generic or YAML-driven handlers.
- `ci_run_pipeline` is real: it runs pytest in the working directory.
- Catalog in the system prompt: one line per namespace with its purpose and full tool names, so the model never guesses names.
- `load_tools(names)` takes individual tool names (not namespaces, which the model over-loaded) and returns compact schemas; `call_tool(name, arguments)` validates with `jsonschema` and dispatches. Errors (unknown name, invalid arguments) go back to the model with the valid names or the schema.
- Any registered tool name is dispatched, including native calls in dynamic mode; no special handling.

## Benchmark

- `demo/` is the project the agent works in: a `payments` package with a planted minor-units bug, tests, and 8 skills (2 needed, 6 distractors).
- Task: alert ALERT-7 → issue PAY-142 → CI log → fix → green `ci_run_pipeline` → comment, resolve, acknowledge per the `hotfix-workflow` skill.
- `src/bench.py` runs each mode N=3 times on fresh temp copies of `demo/`; `src/check.py` judges each run from the final service state and the tests.
- Logged per turn and per run (`runs/*.jsonl`): `input_tokens`, `cached_input_tokens`, `output_tokens`, load calls, validation and tool errors.
- Backend: `http://127.0.0.1:8787/v1`, model `deepseek-flash` (reports cached tokens).
