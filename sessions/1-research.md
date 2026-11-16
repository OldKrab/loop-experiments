# Session: 1-research

Source: Claude Code session `d7a38151-09ea-4749-b616-2d4929f6cdd9`. Tool inputs and outputs: [detailed/1-research.md](detailed/1-research.md).

## User

You can read task in TASK.md. In this session i want you to make research on these two areas: dynamic skills/tools loading and compaction. I want you to read related articles, open-source projects (codex, opencode, openhands) and documentations. Compare different approaches. Save results in docs folder.

## Assistant

```text
Bash     Read task and baseline overview
Skill    research
Bash     Read baseline agent and check docs dir
Bash     Check local codex checkout state
Agent    Research dynamic tool/skill loading
Agent    Research context compaction
```

I've started two research agents in the background, one per area. Each reads the current source of Codex, opencode and OpenHands, Anthropic's docs and engineering posts, the Manus post, and research papers. They'll write:

- `docs/dynamic-tool-loading.md`
- `docs/context-compaction.md`

Each document will cover how the projects do it (with code pointers), a comparison table, and a recommendation for this harness. Each also answers TASK.md question 1, on keeping the prompt cache valid, for its own area.

Question 2, about which tool errors go back to the model, isn't covered, since it's outside the two areas you named. I can research it as a third document if you want.

I'll report back when the agents finish.

## User

Research tools errors too from sources of these projects.

## Assistant

```text
Agent    Research tool error handling
```

I've started a third agent to research tool errors. It traces how Codex, opencode and OpenHands handle each kind of error in their code, then checks Anthropic's and OpenAI's tool-use docs, the Manus post, and SWE-agent and Aider. It will write `docs/tool-errors.md`, which will answer TASK.md question 2 and map its findings to the gaps in `baseline/agent.py`.

All three agents are still running, and I'll report when they finish.

*[Background task finished: Agent "Research tool error handling" is waiting on its own background work]*

## Assistant

The tool-errors agent has passed part of its reading to helper agents of its own and is waiting for them, so it isn't finished yet. The other two agents are also still running. I'll report when all three are done.

*[Background task finished: Agent "opencode error paths" finished]*

## Assistant

The helper that traced opencode's error handling has finished, and the tool-errors agent picks up its results itself. The main point from it is that opencode's current code is a rewrite. It has no doom-loop detection and no AI SDK tool-call repair; instead it has its own layer that fixes malformed tool arguments and returns actionable errors to the model. The full findings will go into `docs/tool-errors.md`.

All three research agents are still running.

*[Background task finished: Agent "OpenHands SDK error paths" finished]*

## Assistant

The helper that traced OpenHands has finished. Its main finding is that almost every failed tool call goes back to the model as a tool result paired to that call, so the model can correct itself. Failures of the whole run are not shown to the model: they stop the run and are reported to the client. Those are retries used up, auth errors, a context overflow with no way to compact, and a detected loop. The tool-errors agent will fold this into `docs/tool-errors.md`.

All three research agents are still running.

*[Background task finished: Agent "Research dynamic tool/skill loading" finished]*

## Assistant

```text
Bash     Check docs folder and outline of tool-loading doc
```

The first document is done: `docs/dynamic-tool-loading.md`, which compares approaches across Codex, opencode, OpenHands, Claude Code, Anthropic, Manus, OpenAI and vLLM/SGLang.

**How it answers question 1 (prompt cache):**
- Every backend checked, hosted or self-hosted, reuses only an exact matching token prefix.
- The tool list is usually rendered inside the first system turn, so changing `tools` or the system prompt mid-session throws away almost the whole cache. Only appended messages are cheap.
- The clients that guard the cache all do the same thing. They freeze the system prompt and tools at session start, add anything new as appended messages, and rebuild the frozen part only at compaction.

**Recommendation for the harness:**
- Keep a fixed core tool set: `bash`, `load_skill`, `load_tools`, and a `call_tool(name, args)` dispatcher.
- Skills appear as a short name-and-description catalog in the prompt; their bodies and extra tool schemas arrive as tool results.
- The harness checks `call_tool` arguments against the schema and returns errors to the model.
- The trade-off: calls made through the dispatcher lose the server's schema-constrained decoding.

**Notes:**
- The provider-side features (Anthropic's `defer_loading` and OpenAI's tool search) don't work through a generic `/chat/completions` endpoint, so the harness can't rely on them.
- To measure cache hits on vLLM, start it with `--enable-prompt-tokens-details`; without that flag the cached-token count is missing rather than zero.
- Some claims are inferred rather than verified (for example, whether sampling parameters ever affect the prefix cache, and llama.cpp's behaviour, which wasn't researched). They're listed in §6 of the doc.

The compaction and tool-errors documents are still being written.

*[Background task finished: Agent "Aider/SWE-agent/Gemini/Cline/AgentsSDK" finished]*

## Assistant

Another helper of the tool-errors agent has finished, the one that traced Aider, SWE-agent, Gemini CLI, Cline and the OpenAI Agents SDK. The tool-errors agent picks up its results itself.

Two of its findings bear on question 2. SWE-agent rejects an edit that introduces syntax errors, undoes it, and tells the model why. Gemini CLI treats only a full disk as fatal; every other tool error goes back to the model.

`docs/dynamic-tool-loading.md` is done. The compaction and tool-errors documents are still being written.

*[Background task finished: Agent "Codex CLI error paths" finished]*

## Assistant

The helper that traced Codex's error handling has finished, and the tool-errors agent picks up its results itself. The main points:

- **What reaches the model:** Codex returns nearly every tool error to the model as plain text. That covers bad JSON arguments, an unknown tool, a non-zero exit code and failed `apply_patch` checks.
- **What the harness handles itself:** sandbox denials (it asks the user, then retries without the sandbox), model-request retries, and interrupts. On an interrupt it fills each unfinished call with an "aborted" result so every call keeps a matching result.
- **No loop detection:** Codex has none, unlike OpenHands, Gemini CLI and Cline.

The context-compaction and tool-errors agents are still running.

*[Background task finished: Agent "Research context compaction" finished]*

## Assistant

```text
Bash     Check compaction doc size and outline
```

The second document is done: `docs/context-compaction.md`.

**How it answers question 1 (prompt cache):**
- Every backend checked reuses only an exact matching prefix, so trimming a little history on every step makes the server re-read almost the whole window each time.
- Compact rarely, in large batches, and down to well below the trigger point.
- Send the summarization request as the current messages unchanged, with the same tools, plus one appended instruction. That request is then itself a cache hit; opencode and Claude Code do this.
- After compaction, keep this order: tools, system prompt, the first task verbatim, the summary, then the recent turns verbatim. The tools and system prompt stay cached across compactions.

**Evidence:** on SWE-bench Verified, masking old tool outputs matched or beat LLM summarization at about half the cost of keeping everything. Summarization made runs 13–15% longer, and a hybrid of the two gained 2.6 points.

**Recommendation for the harness, in stages:**
1. Count tokens as the last API `usage` plus an estimate of what was appended since.
2. Trigger compaction at the window minus max(15%, `max_tokens` plus a summary budget), and retry once after an overflow error.
3. Cap each `bash` output when it's appended and save the full output to a file.
4. Mask old tool outputs in a batch, only when that frees enough tokens.
5. Then produce a structured summary.
6. As a last resort, drop the oldest turns.

**Notes:**
- Some of the brief's assumptions were out of date. Codex no longer uses a `/responses/compact` endpoint, the OpenHands condensers in my list were removed from the current repo (read at an older tag), and opencode's "prune" exists only in its V1 code.
- Some claims are unverified, mainly a few eval setups, and the doc marks them.

The tool-errors document is still being written.

*[Background task finished: Agent "Research tool error handling" is waiting on its own background work]*

## Assistant

The tool-errors agent is still waiting for one more of its helper agents before it writes `docs/tool-errors.md`. The other two documents are done.

## User

> The tool-errors agent is still waiting

Is it complete?

## Assistant

```text
Bash     Check tool-errors doc state
ToolSearch select:SendMessage
SendMessage Resume tool-errors agent and finish doc
```

No, it isn't finished yet. `docs/tool-errors.md` is still a five-line stub. The agent writing it had stopped: its four helper agents (for Codex, opencode, OpenHands, and Aider/SWE-agent/Gemini CLI/Cline/OpenAI Agents SDK) reported back to this session rather than to it, so it didn't know they were done.

I've restarted it and told it to collect those reports and write the document. The other two documents are complete:
- `docs/dynamic-tool-loading.md`
- `docs/context-compaction.md`

*[Background task finished: Agent "Research tool error handling" is waiting on its own background work]*

## Assistant

The tool-errors agent has asked its four helpers to resend their reports and will write the document when they arrive. Last time their reports came here instead of to it. If that happens again, I'll pass the reports to it myself, or write `docs/tool-errors.md` from them, since they're already in this session.

*[Background task finished: Agent "Research tool error handling" is waiting on its own background work]*

## Assistant

The resent reports are reaching the tool-errors agent this time: Codex's has arrived, and it's waiting on the other three before writing `docs/tool-errors.md`.

*[Background task finished: Agent "Codex CLI error paths" finished]*

## Assistant

The Codex helper's resent report reached the tool-errors agent. That agent is waiting on the opencode, OpenHands and Aider/SWE-agent/Gemini CLI/Cline/OpenAI Agents SDK reports before it writes `docs/tool-errors.md`.

*[Background task finished: Agent "Research tool error handling" is waiting on its own background work]*

## Assistant

The tool-errors agent has two of the four resent reports, Codex and opencode. It's waiting on OpenHands and the one covering Aider, SWE-agent, Gemini CLI, Cline and the OpenAI Agents SDK.

*[Background task finished: Agent "Research tool error handling" is waiting on its own background work]*

## Assistant

The tool-errors agent now has three of the four reports. It is waiting only on the one covering Aider, SWE-agent, Gemini CLI, Cline and the OpenAI Agents SDK before writing `docs/tool-errors.md`.

*[Background task finished: Agent "Research tool error handling" is waiting on its own background work]*

## Assistant

```text
Bash     Check tool-errors doc outline and scan docs for personal details
```

All three research documents are written in `docs/`. Each cites code at pinned commits plus official docs, and ends with a recommendation for this harness and a list of unverified claims. Nothing is committed yet.

- **`docs/dynamic-tool-loading.md`** answers TASK.md question 1 for tool and skill loading. Changing `tools` or the system prompt mid-session throws away almost the whole cache, so freeze both at session start. Load skill bodies and extra tool schemas as tool results, from a short catalog in the prompt. The recommended core set is `bash`, `load_skill`, `load_tools` and a `call_tool(name, args)` dispatcher.
- **`docs/context-compaction.md`** answers question 1 for compaction. Compact rarely, in large batches, to well below the trigger. Send the summary request as the unchanged history plus one appended instruction, so that request is itself a cache hit. Masking old tool outputs matched or beat LLM summarization on SWE-bench Verified at about half the cost of keeping everything. The recommended pipeline has these stages:
  - cap each `bash` output when it's appended;
  - mask old outputs in a batch;
  - write a structured summary;
  - as a last resort, drop the oldest turns.
- **`docs/tool-errors.md`** answers question 2. Errors the model caused and can fix go back to it as an actionable tool result. Temporary API errors are retried by the harness without the model seeing them, and a context overflow is handled by compacting rather than being reported. Auth and quota errors abort the run. The harness detects loops, nudges the model once, then stops. The document maps 22 recommended changes to lines in `baseline/agent.py`.

Some sources were out of date:
- opencode now lives at `anomalyco/opencode`.
- Codex no longer supports `/chat/completions`.
- The OpenHands condensers and the old keyword-triggered "microagents" have moved to the software-agent-sdk.

Several cache claims are inferred from code or docs rather than measured; each document lists them in its unverified section. For example: llama.cpp wasn't researched, and it's unconfirmed whether sampling parameters can affect the prefix cache or whether self-hosted servers honour `strict` in tool schemas.

The repo clones are in `/tmp/research-*/` and can be deleted.

*[Background task finished: Agent "Research tool error handling" finished]*

## Assistant

That last notification was only the tool-errors agent's leftover wait timer, so nothing has changed. All three documents in `docs/` are finished and none of them is committed.

## User

create initial commit with whole project and these docs.

## Assistant

```text
Bash     Show untracked files and scan for personal details
Bash     Stage everything and create the initial commit
```

I created the initial commit `9e1f811` on `main` with all 10 files, including the three docs in `docs/`. I put it on `main` rather than a `shushakov/` branch because the repo had no commits yet. It's still local; nothing has been pushed.

- **Personal details:** I checked the files before committing and found none.
- **Author email:** the commit's author email is your git config address, `<email>`. That becomes public when you push. GitHub's noreply address would avoid that, but you'd have to amend the commit before pushing.
- **Session log:** TASK.md also asks for a log of the agent session; it isn't in this commit yet.
