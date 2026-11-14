# Agent harness

A minimal coding agent (`baseline/agent.py`) extended with dynamic loading of skills and tools.

## Run

```sh
uv sync
cd demo && uv run python ../src/agent.py --loading dynamic "your task"   # or --loading fixed
uv run python src/bench.py -n 3          # benchmark both modes on fresh copies of demo/
```

Config: `LLM_BASE_URL` (default `http://127.0.0.1:8787/v1`), `LLM_API_KEY`, `LLM_MODEL` (default `deepseek-flash`).

## Loading modes

The agent has `bash`, 20 service tools in 5 namespaces (`issues`, `ci`, `docs`, `metrics`, `deploy`; mock services whose state is only reachable through the tools), and the skills found in `<cwd>/.agents/skills/`.

| | `fixed` | `dynamic` |
|---|---|---|
| `tools` | `bash` + all 20 service tool schemas | `bash`, `load_skill`, `load_tools`, `call_tool` |
| System prompt | instructions + every skill body | instructions + skill catalog (name, description) + tool catalog (namespace, purpose, tool names) |
| Getting a skill | already in context | `load_skill(name)` returns the body as a tool result |
| Getting a tool | native call | `load_tools(namespaces)` returns the schemas as a tool result; `call_tool(name, arguments)` validates with `jsonschema` and dispatches |

In both modes the system prompt and `tools` are built once and stay byte-identical for the whole session, so the backend's prefix cache keeps working: loaded content arrives as appended tool results.

`baseline/agent.py` itself is not benchmarked. It can't run against the test backend, which requires `reasoning_content` to be passed back, and it has neither the service tools nor the skills, so it couldn't do the task. `--loading fixed` is the "everything up front" version of it with the same capabilities as `dynamic`.

## Benchmark

Task: *"An alert fired on the payments service. Investigate, fix it, and close it out per team process."* The agent has to find the alert, follow it to issue PAY-142 and failing CI run 4812, fix a minor-units bug in `demo/payments/currency.py`, get a green run from `ci_run_pipeline`, and close out according to the `hotfix-workflow` skill. `src/check.py` checks that tests pass, a new CI run is green, PAY-142 is `resolved` with a comment that states the root cause and cites the green run, and ALERT-7 is acknowledged with the issue key.

Results (`deepseek-flash`, N=3 per mode, means):

| mode | success | turns | turn-1 input | input | cached input | uncached input | output |
|---|---|---|---|---|---|---|---|
| fixed | 3/3 | 15 | 5,284 | 161,002 | 150,016 | 10,986 | 6,409 |
| dynamic | 3/3 | 13 | 1,269 | 105,213 | 95,829 | 9,384 | 3,305 |

- The prefix sent on every turn shrinks from about 5.3k to 1.3k tokens, so total input drops by about 35%.
- Prefix caching works in both modes (about 91–94% of input is cached), because neither mode mutates the prefix.
- Fixed mode varied more (11–20 turns): with every skill inlined it sometimes also followed the distractor skills (a postmortem, a follow-up issue).
- In every dynamic run the model loaded all 5 tool namespaces at once, including `docs` and `deploy`, which it didn't use. Loading only the needed ones would save more.
