# Session: 1-research, detailed

Source: Claude Code session `d7a38151-09ea-4749-b616-2d4929f6cdd9`.

## User

You can read task in TASK.md. In this session i want you to make research on these two areas: dynamic skills/tools loading and compaction. I want you to read related articles, open-source projects (codex, opencode, openhands) and documentations. Compare different approaches. Save results in docs folder.

## Assistant

**Tool: Bash**

```sh
cat TASK.md && ls -la baseline && wc -l baseline/* && cat pyproject.toml .gitignore
```

<details><summary>Result</summary>

```
[contents of TASK.md omitted]
```

</details>

**Tool: Skill**

```json
{
 "skill": "research",
 "args": "Dynamic skills/tools loading and context compaction for coding agents; compare approaches in codex, opencode, openhands, plus articles and docs. Save in docs/."
}
```

<details><summary>Result</summary>

```
Launching skill: research
```

</details>

**Tool: Bash**

```sh
cat baseline/agent.py; ls docs 2>/dev/null; which gh git; ls ~/src
```

<details><summary>Result</summary>

```
"""Minimal coding agent loop — one tool: bash."""
import json, sys, subprocess
import requests


LLM_BASE_URL = "http://ip:port/v1"
LLM_API_KEY = "..."
LLM_MODEL = "..."
LLM_HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}
MAX_TURNS = 1000

SYSTEM_PROMPT = """\
You are a coding agent. Your job is to help the user with programming tasks.

You have access to ONE tool: `bash` — which executes shell commands and returns stdout/stderr.

Workflow:
1. Plan what needs to be done.
2. Use `bash` to read files, run commands, write code, etc.
3. After gathering enough information or completing the task, give your final answer in natural language.
4. To finish, reply with a regular message (no tool call).

Be concise. Explain what you're doing before each command."""

LLM_TOOLS = [
    {"type": "function",
     "function": {"name": "bash",
                  "description": "Execute a shell command and return the output.",
                  "parameters": {"type": "object",
                                 "properties": {
                                     "command": {"type": "string", "description": "The bash command to execute."}
                                 },
                                 "required": ["command"]}
                 }
            }]


def run_bash(command: str) -> str:
    try:
        command_result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        out = command_result.stdout + (f"\nSTDERR:\n{command_result.stderr}" if command_result.stderr else "")
        return f"Exit code: {command_result.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s"


def call_tool(name: str, arguments: dict) -> str:
    func = {"bash": run_bash}.get(name)
    if not func:
        return f"Error: unknown tool '{name}'"
    try:
        return func(**arguments)
    except Exception as e:
        return f"Error calling {name}: {e}"


def cal
… [2270 more chars]
```

</details>

**Tool: Bash**

```sh
cd ~/src/codex && git log -1 --format='%h %cd %s' && git status -sb | head -3
```

<details><summary>Result</summary>

```
54b8f112a3 Sat Jul 11 15:20:49 2026 +0000 Preserve parent sandbox enforcement for memory consolidation (#32441)
## main...origin/main [behind 5253]
Shell cwd was reset to ~/src/agent-harness
```

</details>

**Tool: Agent**

```json
{
 "description": "Research dynamic tool/skill loading",
 "subagent_type": "general-purpose",
 "run_in_background": true,
 "prompt": "Research task: how coding agents load tools and skills dynamically, so the system prompt doesn't carry dozens of tool descriptions at once. Write the findings to `~/src/agent-harness/docs/dynamic-tool-loading.md` (create `docs/`). Don't edit anything else in that repo, and don't commit.\n\n## Context\n`~/src/agent-harness` holds a minimal Python coding agent, `baseline/agent.py` (~100 lines): it calls OpenAI-compatible `/chat/completions` (any model, possibly self-hosted vLLM/llama.cpp-style servers), with one `bash` tool and a static system prompt. Read `TASK.md` (in Russian) and `baseline/agent.py` first. The next step is to implement dynamic skill/tool loading in this harness, so the doc is input for design decisions. TASK.md asks one question this doc must answer for its area: **how to load skills/tools without invalidating the prompt cache (KV-cache of the prefix) on every step.** A separate agent is researching context compaction; leave that topic out except where it touches tool loading (e.g., dropping old tool schemas or outputs).\n\n## Sources: primary only\nRead source code, official docs, specs and first-party engineering posts. Follow every claim back to the source that owns it, and cite each one: a URL, or a repo path plus line range at a named commit. Mark anything you couldn't verify as unverified.\n\nClone the repos shallowly into a scratch dir, `/tmp/research-tools/` (`git clone --depth 1`), and only read them: don't run their build scripts or code. Record the commit hash you read. Don't use `~/src/codex`: it's thousands of commits stale and belongs to the user.\n\nCover at least:\n- **OpenAI Codex CLI** (github.com/openai/codex): skills (SKILL.md discovery, how they're listed and injected), MCP tool handling, any tool-search or deferred-tool mechanism, AGENTS.md loading.\n- **opencode** (github.com/sst/opencode, or wherever it lives now; check): tools registry, skills, MCP, per-agent tool filtering, any lazy loading.\n- **OpenHands** (github.com/All-Hands-AI/OpenHands and/or the OpenHands software-agent-sdk): microagents/skills, keyword-triggered knowledge injection, MCP tools.\n- **Anthropic**: Agent Skills (progressive disclosure: metadata → SKILL.md → bundled files), the Tool Search Tool and `defer_loading`, \"Writing tools for agents\" and the advanced-tool-use posts, and the prompt-caching docs (what invalidates the cache, e.g. changing `tools`).\n- **Claude Code** behaviour where documented (deferred MCP tools / ToolSearch, skills).\n- **Manus** \"Context Engineering for AI Agents\" post: masking token logits instead of removing tools, keeping the prefix stable, append-only context.\n- OpenAI docs on prompt caching and any tool-search/namespace features; vLLM/SGLang automatic prefix caching (how the KV-cache prefix match works for self-hosted servers, since the harness may us
… [1399 more chars]
```

<details><summary>Result</summary>

```
Async agent launched successfully. (This tool result is internal metadata — never quote or paste any part of it, including the agentId below, into a user-facing reply.)
agentId: a1ddba725bd9937b4 (internal ID - do not mention to user. Use SendMessage with to: 'a1ddba725bd9937b4', summary: '<5-10 word recap>' to continue this agent.)
The agent is working in the background. You will be notified automatically when it completes. You know nothing about its results until that notification arrives — do not report, assume, or predict them; continue other work or respond to the user in the meantime.
Do not duplicate this agent's work — avoid working with the same files or topics it is using.
output_file: /tmp/claude-1000/-home-user-src-agent-harness/d7a38151-09ea-4749-b616-2d4929f6cdd9/tasks/a1ddba725bd9937b4.output
Do NOT Read or tail this file via the shell tool — it is the full subagent JSONL transcript and reading it will overflow your context. If the user asks for progress, say the agent is still running; you'll get a completion notification.
```

</details>

**Tool: Agent**

```json
{
 "description": "Research context compaction",
 "subagent_type": "general-purpose",
 "run_in_background": true,
 "prompt": "Research task: how coding agents compact their context when the conversation approaches the model's context window. Write the findings to `~/src/agent-harness/docs/context-compaction.md` (create `docs/` if missing). Don't edit anything else in that repo, and don't commit.\n\n## Context\n`~/src/agent-harness` holds a minimal Python coding agent, `baseline/agent.py` (~100 lines): it calls OpenAI-compatible `/chat/completions` (any model, possibly self-hosted vLLM/llama.cpp-style servers), with one `bash` tool. Its message list grows without bound and there is no token accounting. Read `TASK.md` (in Russian) and `baseline/agent.py` first. The next step is to implement \"smart context compaction on window overflow\" in this harness, so the doc is input for design decisions. TASK.md asks a question this doc must answer for its area: **how to do compaction without invalidating the prompt cache (KV-cache of the prefix) on every step.** A separate agent is researching dynamic tool/skill loading; leave that topic out.\n\n## Sources: primary only\nRead source code, official docs, specs and first-party engineering posts. Follow every claim back to the source that owns it, and cite each one: a URL, or a repo path plus line range at a named commit. Mark anything you couldn't verify as unverified.\n\nClone the repos shallowly into a scratch dir, `/tmp/research-compaction/` (`git clone --depth 1`), and only read them: don't run their build scripts or code. Record the commit hash you read. Don't use `~/src/codex`: it's thousands of commits stale and belongs to the user.\n\nCover at least:\n- **OpenAI Codex CLI** (github.com/openai/codex, Rust in `codex-rs/`): auto-compact trigger and threshold, the summarization prompt, what is kept after compaction (recent user messages? truncation budgets?), the remote `/responses/compact` endpoint vs local compaction, and how tool outputs are truncated.\n- **opencode** (github.com/sst/opencode, or wherever it lives now; check): its compaction/summarize flow, \"prune\" of old tool outputs, overflow detection, the prompt it uses.\n- **OpenHands** (github.com/All-Hands-AI/OpenHands and/or the OpenHands software-agent-sdk): condensers (LLMSummarizingCondenser, observation masking, amortized forgetting, recent-events, LLM attention, etc.), their published evaluation of condensers, and how the condensation event is represented.\n- **Anthropic**: the \"Effective context engineering for AI agents\" post, the API's server-side compaction / context editing (`clear_tool_uses`, compaction beta) and memory tool docs, Claude Code's `/compact` and auto-compact where documented, and the prompt-caching docs (what invalidates the cache).\n- **Manus** \"Context Engineering for AI Agents\" post: file system as external memory, restorable compression, KV-cache hit rate as the key metric, append-only context
… [1904 more chars]
```

<details><summary>Result</summary>

```
Async agent launched successfully. (This tool result is internal metadata — never quote or paste any part of it, including the agentId below, into a user-facing reply.)
agentId: a6a0291b259201481 (internal ID - do not mention to user. Use SendMessage with to: 'a6a0291b259201481', summary: '<5-10 word recap>' to continue this agent.)
The agent is working in the background. You will be notified automatically when it completes. You know nothing about its results until that notification arrives — do not report, assume, or predict them; continue other work or respond to the user in the meantime.
Do not duplicate this agent's work — avoid working with the same files or topics it is using.
output_file: /tmp/claude-1000/-home-user-src-agent-harness/d7a38151-09ea-4749-b616-2d4929f6cdd9/tasks/a6a0291b259201481.output
Do NOT Read or tail this file via the shell tool — it is the full subagent JSONL transcript and reading it will overflow your context. If the user asks for progress, say the agent is still running; you'll get a completion notification.
```

</details>

I've started two research agents in the background, one per area. Each reads the current source of Codex, opencode and OpenHands, Anthropic's docs and engineering posts, the Manus post, and research papers. They'll write:

- `docs/dynamic-tool-loading.md`
- `docs/context-compaction.md`

Each document will cover how the projects do it (with code pointers), a comparison table, and a recommendation for this harness. Each also answers TASK.md question 1, on keeping the prompt cache valid, for its own area.

Question 2, about which tool errors go back to the model, isn't covered, since it's outside the two areas you named. I can research it as a third document if you want.

I'll report back when the agents finish.

## User

Research tools errors too from sources of these projects.

## Assistant

**Tool: Agent**

```json
{
 "description": "Research tool error handling",
 "subagent_type": "general-purpose",
 "run_in_background": true,
 "prompt": "Research task: how coding agents handle tool errors. Which errors are returned to the model so it can correct itself, and which does the harness catch deterministically (retry, repair, abort, ask the user)? Write the findings to `~/src/agent-harness/docs/tool-errors.md` (create `docs/` if missing). Don't edit anything else in that repo, and don't commit.\n\n## Context\n`~/src/agent-harness` holds a minimal Python coding agent, `baseline/agent.py` (~100 lines). It calls OpenAI-compatible `/chat/completions` (any model, possibly self-hosted vLLM/llama.cpp-style servers) and has one `bash` tool. Read `TASK.md` (in Russian) and `baseline/agent.py` first. Note the baseline's current gaps, for example: `json.loads` on malformed tool arguments crashes the loop; no HTTP retry; a timeout loses partial output; output size is unbounded; an unknown tool returns an error string. TASK.md asks: **which tool errors should be fed back to the model for self-correction, and which should be intercepted deterministically at the harness level?** This doc must answer that. Other agents are researching dynamic tool loading and context compaction; leave those out.\n\n## Sources: primary only\nRead source code, official docs, specs and first-party engineering posts. Follow every claim back to the source that owns it, and cite each one: a URL, or a repo path plus line range at a named commit. Mark anything you couldn't verify as unverified.\n\nClone the repos shallowly into a scratch dir, `/tmp/research-errors/` (`git clone --depth 1`), and only read them: don't run their build scripts or code. Record the commit hash you read. Don't use `~/src/codex`: it's thousands of commits stale and belongs to the user.\n\nFor each project below, trace the error paths in the code:\n- **OpenAI Codex CLI** (github.com/openai/codex, `codex-rs/`): malformed or unparseable function-call arguments, unknown tool, sandbox denial and escalation/approval, command timeout, non-zero exit codes, output truncation, apply_patch verification failures, model/stream errors and retry/backoff policy (which HTTP statuses retry, context-window-exceeded handling), turn aborts, and how the result is formatted to the model (e.g. the success flag and exit code in the function output).\n- **opencode** (github.com/sst/opencode, or wherever it lives now; check): tool execute errors, invalid tool calls and repair (e.g. the AI SDK's `experimental_repairToolCall`, or an \"invalid\" tool), doom-loop detection, permission denials, edit-tool failures (oldString not found or not unique), LLM API retry logic.\n- **OpenHands** (github.com/All-Hands-AI/OpenHands and/or the OpenHands software-agent-sdk): ErrorObservation, AgentErrorEvent, function-call validation errors, stuck detection (StuckDetector loop patterns), LLM retry config, and what makes the agent state ERROR vs continue.\
… [2080 more chars]
```

<details><summary>Result</summary>

```
Async agent launched successfully. (This tool result is internal metadata — never quote or paste any part of it, including the agentId below, into a user-facing reply.)
agentId: afbe11231f5a75fd4 (internal ID - do not mention to user. Use SendMessage with to: 'afbe11231f5a75fd4', summary: '<5-10 word recap>' to continue this agent.)
The agent is working in the background. You will be notified automatically when it completes. You know nothing about its results until that notification arrives — do not report, assume, or predict them; continue other work or respond to the user in the meantime.
Do not duplicate this agent's work — avoid working with the same files or topics it is using.
output_file: /tmp/claude-1000/-home-user-src-agent-harness/d7a38151-09ea-4749-b616-2d4929f6cdd9/tasks/afbe11231f5a75fd4.output
Do NOT Read or tail this file via the shell tool — it is the full subagent JSONL transcript and reading it will overflow your context. If the user asks for progress, say the agent is still running; you'll get a completion notification.
```

</details>

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

**Tool: Bash**

```sh
ls -la docs && wc -l docs/*.md && grep -n '^#' docs/dynamic-tool-loading.md | head -40
```

<details><summary>Result</summary>

```
total 72
drwxrwxr-x 2 old old  4096 Nov 14 12:52 .
drwxrwxr-x 5 old old  4096 Nov 14 12:48 ..
-rw-rw-r-- 1 old old  1573 Nov 14 12:50 context-compaction.md
-rw-rw-r-- 1 old old 53839 Nov 14 12:52 dynamic-tool-loading.md
-rw-rw-r-- 1 old old   122 Nov 14 12:48 tool-errors.md
   19 docs/context-compaction.md
  443 docs/dynamic-tool-loading.md
    5 docs/tool-errors.md
  467 total
1:# Dynamic tool and skill loading in coding agents
22:## 1. Summary of approaches
40:## 2. Per project
42:### 2.1 Anthropic (API, Agent Skills, engineering posts)
82:### 2.2 Claude Code (documented behaviour)
102:### 2.3 OpenAI Codex CLI
137:### 2.4 opencode
175:### 2.5 OpenHands (software-agent-sdk)
209:### 2.6 Manus: "Context Engineering for AI Agents"
230:### 2.7 OpenAI API docs: prompt caching, tool search, namespaces, `allowed_tools`
251:### 2.8 Self-hosted: vLLM and SGLang prefix caching
286:### 2.9 Others (brief)
319:## 3. Comparison
343:## 4. Prompt cache: what an OpenAI-compatible, possibly self-hosted backend actually needs
384:## 5. Recommendation for this harness
430:## 6. Unverified or inferred
```

</details>

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

**Tool: Bash**

```sh
wc -l docs/*.md && grep -n '^## ' docs/context-compaction.md
```

<details><summary>Result</summary>

```
530 docs/context-compaction.md
   443 docs/dynamic-tool-loading.md
     5 docs/tool-errors.md
   978 total
25:## 1. Taxonomy
41:## 2. Per project
292:## 3. Comparison
312:## 4. Measured evidence
362:## 5. The prompt-cache question, for an OpenAI-compatible (possibly self-hosted) backend
447:## 6. Recommendation for this harness (design input)
521:## Unverified or caveated claims
```

</details>

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

**Tool: Bash**

```sh
wc -l docs/tool-errors.md && cat docs/tool-errors.md | head -20
```

<details><summary>Result</summary>

```
5 docs/tool-errors.md
# Tool errors: feed back to the model, or handle in the harness?

DRAFT: per-project sections pending.

<!-- PROJECTS -->
```

</details>

**Tool: ToolSearch**

```json
{
 "query": "select:SendMessage",
 "max_results": 1
}
```

<details><summary>Result</summary>

```
[tool_reference]
```

</details>

**Tool: SendMessage**

```json
{
 "to": "afbe11231f5a75fd4",
 "summary": "Resume tool-errors agent and finish doc",
 "message": "All four of your helper agents have finished, but their reports came to the main session, not to you, so finish `docs/tool-errors.md` now. The four helpers are opencode (a057921a57ae49cca), OpenHands SDK (a35c657a917694d88), Aider/SWE-agent/Gemini/Cline/Agents SDK (abe4ecbd6f002b354) and Codex (abc5b82262bd3799b). If you don't have their results, use SendMessage to ask each one to resend its full final report, then write the doc as originally briefed. Don't spawn new helpers to redo their work. If you're waiting on any helper other than these four, reply naming it instead.",
 "type": "message",
 "recipient": "afbe11231f5a75fd4",
 "recipient_kind": "agent",
 "content": "All four of your helper agents have finished, but…"
}
```

<details><summary>Result</summary>

```
{"success":true,"message":"Resuming agent afbe112","resumedAgentId":"afbe11231f5a75fd4","pin":{"id":"afbe11231f5a75fd4","name":"afbe11231f5a75fd4","ref":"784859"}}
```

</details>

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

**Tool: Bash**

```sh
wc -l docs/*.md && grep -n '^## ' docs/tool-errors.md && grep -rniE 'shushakov|daniil|~' docs/ | head
```

<details><summary>Result</summary>

```
530 docs/context-compaction.md
   443 docs/dynamic-tool-loading.md
   527 docs/tool-errors.md
  1500 total
5:## Sources and method
36:## 1. Taxonomy
76:## 2. First-party guidance
115:## 3. Per project
393:## 4. Comparison
421:## 5. Decision rule
470:## 6. Recommendations for this harness
513:## 7. Unverified or partial
```

</details>

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

**Tool: Bash**

```sh
git status --short && git config user.name && git config user.email && grep -rnIiE 'shushakov|daniil|gmail|~|api[_-]?key\s*=\s*"[^.]' --exclude-dir=.git --exclude-dir=.venv . | grep -v uv.lock | head
```

<details><summary>Result</summary>

```
?? .gitignore
?? AGENTS.md
?? CLAUDE.md
?? TASK.md
?? baseline/
?? docs/
?? pyproject.toml
?? uv.lock
Daniil Shushakov
<email>
```

</details>

**Tool: Bash**

```sh
git add -A && git status --short && git commit -q -m "Add baseline harness, task, and research notes

baseline/agent.py is the harness as received. docs/ holds research on
dynamic tool/skill loading, context compaction, and tool error handling
across Codex, opencode, OpenHands and related sources." && git log --stat --oneline
```

<details><summary>Result</summary>

```
A  .gitignore
A  AGENTS.md
A  CLAUDE.md
A  TASK.md
A  baseline/agent.py
A  docs/context-compaction.md
A  docs/dynamic-tool-loading.md
A  docs/tool-errors.md
A  pyproject.toml
A  uv.lock
9e1f811 Add baseline harness, task, and research notes
 .gitignore                   |   5 +
 AGENTS.md                    |   6 +
 CLAUDE.md                    |   1 +
 TASK.md                      |  18 ++
 baseline/agent.py            |  99 ++++++++
 docs/context-compaction.md   | 530 +++++++++++++++++++++++++++++++++++++++++++
 docs/dynamic-tool-loading.md | 443 ++++++++++++++++++++++++++++++++++++
 docs/tool-errors.md          | 527 ++++++++++++++++++++++++++++++++++++++++++
 pyproject.toml               |   9 +
 uv.lock                      | 256 +++++++++++++++++++++
 10 files changed, 1894 insertions(+)
```

</details>

I created the initial commit `9e1f811` on `main` with all 10 files, including the three docs in `docs/`. I put it on `main` rather than a `shushakov/` branch because the repo had no commits yet. It's still local; nothing has been pushed.

- **Personal details:** I checked the files before committing and found none.
- **Author email:** the commit's author email is your git config address, `<email>`. That becomes public when you push. GitHub's noreply address would avoid that, but you'd have to amend the commit before pushing.
- **Session log:** TASK.md also asks for a log of the agent session; it isn't in this commit yet.
