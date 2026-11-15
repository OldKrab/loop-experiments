# Design: dynamic loading of skills and tools, and context compaction

Decisions for `src/`. Background research: `docs/dynamic-tool-loading.md` and `docs/context-compaction.md`.

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

## Error handling

Errors the model can fix come back as the tool result; errors only the harness can handle are handled in `src/agent.py`. Every handled error is printed and logged as an `error` event with its `kind`.

| Error | Handled by | What happens |
|---|---|---|
| Bash non-zero exit or 120 s timeout | model | exit code and stderr, or "timed out" |
| Tool call arguments not valid JSON (often a reply cut off by `max_tokens`) | model | "not valid JSON, resend the call" (`bad_tool_json`) |
| Arguments that fail the schema, for core and service tools alike | model | `jsonschema` message plus the schema (`validation_error`) |
| Unknown tool or skill name | model | list of valid names (`unknown_tool`, `unknown_skill`) |
| Tool raises (not found, bad state) | model | "Error calling X: …", with existing ids where useful (`tool_error`) |
| LLM connection error, timeout, or HTTP 408/409/429/5xx | harness | up to 5 retries with exponential backoff, honoring `Retry-After` (`llm_retry`) |
| Any other LLM HTTP error, or a response without `choices` | harness | run stops; the `end` event holds the error |
| Reply cut off by `max_tokens` with no tool call | harness | ask the model to continue; stop with status `truncated` after 3 in a row (`truncated`) |
| Turn limit | harness | stop with status `max_turns` |

Not handled yet: detecting a model that repeats the same failing call, and compacting reactively on a context-length error.

## Context compaction

- One flag, `--compact-at TOKENS` (default 0: off). LLM summarization only; no observation masking.
- **Trigger:** before each LLM call, estimate the next request as the last response's `prompt_tokens + completion_tokens` (exact for the history up to that reply) plus chars/4 of the messages appended since. Compact when the estimate reaches `--compact-at`. Each `turn` event logs the estimate next to the reported `input_tokens`.
- **Summary call:** the current history unchanged, the same `tools` and parameters, plus one appended user instruction, so the server reuses the cached prefix. The prompt is free-form, with a checklist of what must survive: the objective, the current work and next step, the skills loaded and progress in each, exact identifiers, and failed approaches. It replaces any earlier summary and must not call tools.
- **New history:** `[system][task][user: <checkpoint>summary</checkpoint>][tail]`. The tail is the newest messages within 30% of `--compact-at`, starting at an assistant message so no tool result loses its call. The system prompt, `tools` and task stay byte-identical, so they stay cached; the checkpoint is frozen until the next compaction, and everything after it is append-only.
- **Skills after compaction:** loaded skill bodies and tool schemas are gone with the history.
  - The summarizer decides which loaded skills are still in progress, meaning the remaining work must still follow their steps, formats or rules. It ends the summary with `Load before continuing: <names>` or `none`.
  - The harness parses that line and puts those skill bodies into the checkpoint message, right after the summary. The loaded-skill set becomes exactly those skills. Other skills and all tool schemas are loaded again by the model as needed.
  - The `compaction` event logs `reload_skills` (`null` if the line is missing) and `reload_tokens`.
  - This replaced two weaker versions:
    - With only a list of loaded skills in the summary, agents in the feature runs at 22k and 60k did not re-load `feature-workflow` and drifted from its comment format.
    - With the checkpoint merely telling the model to load the named skills, it still skipped the load in a test run.
- **Failures:** a reply with a tool call, an empty reply or a cut-off reply gets one nudge. If that fails too, or the result is not under the threshold, the run continues uncompacted (`compaction_failed`); after 2 failures compaction is off for the rest of the run.
- **Accounting:** summary calls count toward the run's token totals. A `compaction` event logs the estimate before and after, the threshold, the message counts, the tail size, the summary and its call's usage, the skills it says to reload, and duration.

## Bash output cap

- Always on, independent of compaction, and applied before the output enters the history (cache-neutral).
- Output over 8,000 chars keeps the first and last 3,000 chars, with a marker giving the size and the path of the full output under `/tmp/agent-<pid>/`, outside the working directory. Logged as `output_capped`.

## Benchmark

- `demo/` is the project the agent works in: a `payments` package with a planted minor-units bug, tests, and 8 skills (2 needed, 6 distractors).
- Short task (`--task short`): alert ALERT-7 → issue PAY-142 → CI log → fix → green `ci_run_pipeline` → comment, resolve, acknowledge per the `hotfix-workflow` skill.
- Feature task (`--task feature`, project `demo-feature/`, a marshmallow 4.4.0 snapshot; the choice is explained in `docs/long-task-benchmarks.md`): "work through the open feature tickets, oldest first, per team process". There are 4 detailed tickets: `validate.Unique`, `fields.Duration`, a `Meta.key_case` option, and `fields.Union`. Each fixes the API, messages and examples. The `feature-workflow` skill requires one ticket at a time, one CI run and one formatted comment per ticket. `marshmallow-conventions` describes the codebase. The distractors are a ticket owned by someone else (MM-200, which must stay untouched), a docs ticket, an unrelated alert, and the 8 skills of the other tasks.
- Feature-xl task (`--task feature-xl`, same project): the same task with 10 tickets (MM-201..210). It adds `Meta.dump_skip_none`, `validate.Each`, `fields.Interval`, `Meta.strip_strings`, `fields.Masked`, and `Schema.json_schema()`, which maps every earlier field type. Without compaction the context peaks at about 110–135k tokens.
- Feature judging: hidden acceptance tests per ticket (`src/demo_data/feature/acceptance/`, validated against a reference solution and failing on the untouched snapshot), copied into the workdir only after the run. Each ticket must also be resolved with a `Summary:` comment citing its own new green CI run, and the project's own suite must pass.
- `bench.py` prints the cost per run at `deepseek-flash` peak prices ($0.30 / $0.006 / $1.20 per 1M uncached input / cached input / output).
- `src/bench.py` runs each loading mode and `--compact-at` threshold (comma list, 0 = off) N=3 times, 6 runs in parallel, each on a fresh temp copy of the task's project; `src/check.py` judges each run from the final service state and the tests.
- Logged per turn and per run (`runs/*.jsonl`): `input_tokens`, `cached_input_tokens`, `output_tokens`, load calls, validation and tool errors.
- Backend: `http://127.0.0.1:8787/v1`, model `deepseek-flash` (reports cached tokens).
