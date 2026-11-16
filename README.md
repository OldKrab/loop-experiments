# Agent harness

The solution is in `src/`. The original harness is untouched in `baseline/`. The benchmark projects are `demo/` (short task) and `demo-feature/` (feature tasks, a copy of marshmallow 4.4.0, MIT). The agent sessions that built it are in `sessions/`: research, dynamic loading, and compaction.

```sh
uv sync
cd demo && uv run python ../src/agent.py --loading dynamic --compact-at 100000 "your task"
uv run python src/bench.py --task feature --modes fixed,dynamic --compact-at 0,38000 -n 3
```

Set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` for any OpenAI-compatible endpoint. All runs below used `deepseek-flash`.

## Solution

**Dynamic loading of skills.** Skills are read from `<cwd>/.agents/skills/` when the agent starts. The system prompt lists only their names and descriptions, and the agent loads a skill's full text with the `load_skill` tool.

**Dynamic loading of tools.** The baseline has only `bash`, so I added 20 mock tools for testing in `src/demo_tools.py`: an issue tracker, CI, a docs wiki, monitoring and deploys. Their data lives inside the harness, so `bash` can't replace them. The system prompt lists only the tool names, grouped with a short description per group. The agent gets the schemas with `load_tools` and runs a tool with `call_tool`.

**Compaction.** Before each model call the harness estimates the context size: the size the model reported on the last call, plus the characters added since divided by 4. Over the threshold (`--compact-at`), the model writes a summary that keeps the main goal and the current work. It ends with the skills that are still in progress. The history is then replaced by the system prompt, the task, the summary with those skills loaded again, and the last few messages.

Also fixed in the baseline: the assistant message is stored once and as received (the baseline split parallel tool calls and dropped `reasoning_content`, which DeepSeek requires back), malformed tool-call JSON no longer crashes the loop, and config comes from env vars.

## Answers

**1. How to do compaction and skill loading without breaking the prompt cache?**
The system prompt and the tool list never change until a compaction. Loaded skills and tool schemas arrive as tool results appended to the end of the history, so the cached prefix stays the same. Compaction happens only at the threshold, so it breaks the cache once, not on every step, and the summary request is the current history plus one message at the end, so it is cached too.

**2. Which errors go back to the model, and which does the harness handle?**
Every tool error goes back to the model, so it can decide how to fix it: a failed command, invalid arguments (with the tool's schema), an unknown tool or skill (with the valid names), a tool's own errors. The harness handles only problems of its own that the model can't fix: network and HTTP errors when calling the model (retried), a reply cut off at `max_tokens`, and the turn limit.

## Comparison

| task | what the agent does |
|---|---|
| short | fixes one bug from an alert and closes the issue |
| feature | implements 4 feature tickets in marshmallow, each checked by hidden tests |
| feature-xl | the same with 10 tickets |

**Dynamic vs fixed loading.** In fixed mode all skills and tool schemas are in the prompt from the start. Mean of 3 runs, all successful:

| task | fixed | dynamic |
|---|---|---|
| short | 137k tokens, 0.85¢ | 81k tokens, 0.62¢ |
| feature | 2.87M tokens, 7.34¢ | 2.46M tokens, 6.46¢ |

**Compaction**, with dynamic loading. Mean of 3 runs:

| task | off | compaction |
|---|---|---|
| feature (peak ~65k) | 6.46¢, 3/3 | at 38k: 7.10¢, 3/3; at 22k: 9.22¢, 3/3 |
| feature-xl (peak ~120k) | 15.14¢, 3/3 | at 100k: 13.80¢, 3/3; at 60k: 17.36¢, 2/3 |

On short sessions compaction costs more: the tokens it removes were cached and nearly free, while the agent spends extra turns reading files again. It saved money only on the longest task, and only a little. I assume it pays off on sessions over about 150k tokens, but I didn't measure that. In the first version, the summary only listed the skills, and the agent often didn't load the workflow skill again, so it broke the team process. Now the harness loads the skills the summary names. The one failure left (at 60k) happened before the first compaction.

Details of all runs are in `docs/`.
