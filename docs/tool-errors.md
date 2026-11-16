# Tool errors: feed back to the model, or handle in the harness?

Research input for question 2 of the task: "which tool errors should be returned to the model for self-correction, and which should be intercepted deterministically at the harness level?" Scope: error handling only. Dynamic tool loading and context compaction are covered elsewhere; compaction appears here only as the response to a context-overflow error.

## Sources and method

Code was read, not run, from shallow clones. Citations are `alias:path:lines` at the commit below. Codex paths are relative to `codex-rs/`. OpenHands paths use `sdk/` = `openhands-sdk/openhands/sdk/` and `tools/` = `openhands-tools/openhands/tools/`.

| Alias | Repo | Commit |
|---|---|---|
| `codex` | github.com/openai/codex | `b1573f102413e96a6481087922bf425231222dee` |
| `oc` | github.com/anomalyco/opencode (`sst/opencode` redirects here), branch `dev` | `c9957fd50858aafd43fb8167b117b3a8e5210529` |
| `oc149` | same repo, tag `v1.4.9`, the older AI-SDK-based loop | `803d9eb7ad5f4dfd832d7506a7cad83ded52253e` |
| `oh` | github.com/OpenHands/software-agent-sdk | `3c66af1d14d0a7fbe74b8dc4218412ec7a877b79` |
| `aider` | github.com/Aider-AI/aider | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` |
| `swe` | github.com/SWE-agent/SWE-agent | `3ea751c087f32b16e039a2233dd6eefecef325d5` |
| `gem` | github.com/google-gemini/gemini-cli | `4ed06ed0ddc523a6d356a4ad35ddfea331041888` |
| `cline` | github.com/cline/cline | `72b3d7140553a733242126e51a7c2e87efe75c64` |
| `agents` | github.com/openai/openai-agents-python | `64fbde5d02b42ae5f9db668eb0184cdb3fc9d775` |

`github.com/All-Hands-AI/OpenHands` now redirects to `OpenHands/OpenHands`, which is a frontend ("Agent Canvas", commit `830c0459`). The agent loop lives in the software-agent-sdk, so that is what was read.

Documents:
- Anthropic, "Handle tool calls": https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
- Anthropic, "Writing effective tools for agents" (2025-09-11): https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic, "Building effective agents" (2024-12-19): https://www.anthropic.com/engineering/building-effective-agents
- OpenAI, function calling guide: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI, Chat Completions reference: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
- vLLM, tool calling: https://docs.vllm.ai/en/latest/features/tool_calling.html
- Manus, "Context Engineering for AI Agents: Lessons from Building Manus" (2025-07-18): https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- SWE-agent paper (Yang et al., 2024): https://arxiv.org/abs/2405.15793
- Python `subprocess` docs: https://docs.python.org/3/library/subprocess.html

---

## 1. Taxonomy

Each class is listed with its typical examples and who can fix it.

**T. Transport / LLM API.** The model cannot fix these, and only some are transient.
- T1, transient: 429, 5xx, 408/409, connection reset or DNS failure, request timeout, stream cut mid-response, stream idle timeout.
- T2, context overflow: a 400 with "maximum context length", "prompt is too long" and similar.
- T3, output limit: `finish_reason == "length"`. It truncates text and, worse, truncates tool-call arguments into invalid JSON.

**M. Malformed model output.** The model caused these, and usually can fix them.
- M1: tool arguments are not valid JSON.
- M2: unknown tool name.
- M3: arguments violate the schema (missing, extra or wrong-typed fields).
- M4: empty response, reasoning-only response, or a tool call written as text when the server's tool parser failed.

**X. Tool execution.** Mostly model-fixable. X5 is a harness bug.
- X1: non-zero exit code.
- X2: command timeout or hang, including interactive commands waiting on stdin.
- X3: huge output.
- X4: domain failure, such as an edit whose `old_string` is missing or not unique, or a missing file.
- X5: exception inside harness code (decode error, OSError, bug).

**P. Policy.** The model can adapt; the user decides.
- P1: a configured deny rule or sandbox denial.
- P2: the user rejects, with or without feedback.
- P3: a sandbox denial that could be retried with escalated permissions after approval.

**B. Behavioural.** The model is stuck, and the harness must notice.
- B1: identical calls repeated.
- B2: the same error repeated.
- B3: alternating A/B cycles.
- B4: monologue or no tool use.
- B5: a turn or budget cap reached.

**F. Fatal.** Nobody in the loop can fix these.
- F1: 401/403 after a refresh attempt, unknown model (404), quota exhausted (402 or `insufficient_quota`), a malformed request the harness built (a non-overflow 400).
- F2: local fatal conditions such as a full disk or an invalid config.

---

## 2. First-party guidance

**Anthropic, "Handle tool calls".**
- Tool execution errors go back as a `tool_result` with `"is_error": true` and the message as content. Example content: `"ConnectionError: the weather service API is not available (HTTP 500)"`.
- "Write instructive error messages. Instead of generic errors such as `"failed"`, include what went wrong and what Claude should try next (for example, `"Rate limit exceeded. Retry after 60 seconds."`)."
- For invalid calls (e.g. a missing required parameter): "If a tool request is invalid or missing parameters, Claude will retry 2–3 times with corrections before apologizing to the user." To prevent them, use `strict: true`.
- Pairing rules: "Tool result blocks must immediately follow their corresponding tool use blocks", and `tool_result` blocks "must come FIRST in the content array". A violation gives the 400 error "tool_use ids were found without tool_result blocks immediately after".

**Anthropic, "Writing effective tools for agents".**
- "prompt-engineer your error responses to clearly communicate specific and actionable improvements".
- Bound responses with "pagination, range selection, filtering, and/or truncation". "For Claude Code, we restrict tool responses to 25,000 tokens by default."
- "Tool truncation and error responses can steer agents towards more token-efficient tool-use behaviors".
- The article's helpful and unhelpful error examples are images, so their exact text is not quotable.

**Anthropic, "Building effective agents".**
- Agents "gain 'ground truth' from the environment at each step (such as tool call results or code execution)".
- "it's also common to include stopping conditions (such as a maximum number of iterations)".
- "Agents can then pause for human feedback at checkpoints or when encountering blockers."
- "Poka-yoke your tools. Change the arguments so that it is harder to make mistakes." The cited example: requiring absolute paths fixed a class of SWE-bench errors.

**OpenAI, function calling guide.** Strict mode "will ensure function calls reliably adhere to the function schema, instead of being best effort". Requirements: `additionalProperties: false`, and every property listed in `required` (express optional fields as `["T","null"]`). "We recommend always enabling strict mode." The format of the result string "is up to you (JSON, error codes, plain text, etc.)". The Chat Completions `tool` message has only `role`, `content` and `tool_call_id`, so there is no error flag: an error must be signalled in the text. `finish_reason` is "`length` if the maximum number of tokens specified in the request was reached".

**vLLM (relevant to self-hosted backends).**
- With `tool_choice="auto"`, when calls are extracted from raw text, "arguments may occasionally be malformed or violate the function's parameter schema".
- `tool_choice="required"` guarantees one or more tool calls.
- For a named function: "You are guaranteed a validly-parsable function call - not a high-quality one."
- `--tool-strict-level auto|function|parameter` pins argument schemas server-side. Only `strict: true` or `parameter` enforces the schema.
- Conclusion: against arbitrary OpenAI-compatible servers, M1 to M4 are routine, not exotic.

**Manus, "Keep the Wrong Stuff In".** Agents make mistakes; cleaning up the trace, retrying the action or resetting state "removes evidence". When the model sees a failed action with its "observation or stack trace", it "implicitly updates its internal beliefs" and is less likely to repeat the mistake. "Error recovery is one of the clearest indicators of true agentic behavior." The same post prefers constraining tool choice by logit masking or prefill over editing the tool list.

**SWE-agent paper (ACI design).**
- Principles: "Environment feedback should be informative but concise." "Guardrails mitigate error propagation and hasten recovery."
- Ablation (Sec. 5.1, Table 3): a lint guardrail on edits gave 18.0% resolved; "without linting, 15.0% ↓ 3.0".
- Sec. 5.2: "Any attempt at editing has a 90.5% chance of eventually being successful. This probability drops off to 57.2% after a single failed edit." "Cascading failed edits make up another 23.4% of failures."
- Empty output is reported explicitly: "Your command ran successfully and did not produce any output." No ablation of that message was found.

---

## 3. Per project

### 3.1 OpenAI Codex CLI (`codex`, Rust)

**Mechanism.** The handler error type has two variants (`codex:tools/src/function_call_error.rs:5-10`):
- `RespondToModel(String)` becomes a `function_call_output` whose body is the bare message, with internal `success=false` (`codex:core/src/tools/parallel.rs:466-490`).
- `Fatal(String)` becomes `CodexErr::Fatal`: the turn ends with an error event and nothing goes to the model (`parallel.rs:146`).
- The `success` flag is never serialised; only the body goes on the wire (`codex:protocol/src/models.rs:2496-2504, 2582-2592`).

**M1, bad JSON.** `"failed to parse function arguments: {serde_err}"` (`codex:core/src/tools/handlers/mod.rs:90-97`). No repair, no retry. MCP tools get `"err: {e}"` (`core/src/mcp_tool_call.rs:174-182`).

**M2, unknown tool.** `"unsupported call: {tool_name}"` / `"unsupported custom tool call: {tool_name}"` (`core/src/tools/registry.rs:804-823, 1187-1191`). A known tool called with the wrong payload kind is `Fatal`: `"tool {name} invoked with incompatible payload"` (`registry.rs:837-853`).

**X1, exit code.** The shell tool (`exec_command`) always reports `success=true`. The exit code is only text, inside a plain-text envelope (`core/src/tools/context.rs:458-467, 549-600`):

```
Chunk ID: …
Wall time: … seconds
Process exited with code N
Original token count: N
Output:
…
```

**X2, timeouts.** Interactive `exec_command` never kills on timeout.
- After `yield_time_ms` (default 10 s, clamped to 250 ms–30 s) the process keeps running and the model gets `"Process running with session ID N"`. It can then poll with `write_stdin` (`core/src/unified_exec/mod.rs:68-76, 210-215`).
- One-shot mode kills at `timeout_ms` (default 10 s), reports exit 124, and keeps head+tail partial output (`core/src/unified_exec/process_manager.rs:664-671, 759-771`; `process.rs:215-218`).
- The legacy exec path prepends `"command timed out after {ms} milliseconds\n"` (`core/src/tools/mod.rs:133-141`).

**X3, truncation.**
- Capture is a 1 MiB head/tail buffer: `"... {n} bytes omitted ..."` (`utils/head-tail-buffer/src/lib.rs`).
- The model budget defaults to 10,000 tokens (`models-manager/models.json:15-17`), cut in the middle with `"…{n} tokens truncated…"` and the header `"Warning: truncated output (original token count: {n})\nTotal output lines: {lines}"` (`utils/string/src/truncate.rs:27-53`; `utils/output-truncation/src/lib.rs:34-48`).
- History truncates again at 1.2× the policy (`core/src/context_manager/history.rs:679-691`).

**X4, apply_patch.** All `RespondToModel`:
- `"apply_patch verification failed: {e}"`
- `"invalid patch: The first line of the patch must be '*** Begin Patch'"`
- `"invalid hunk at line {n}, {message}"`
- `"Failed to find expected lines in {path}:\n{old_lines}"`
- `"Failed to find context '{ctx}' in {path}"`

Sources: `core/src/tools/handlers/apply_patch.rs:350-352, 484-519`; `apply-patch/src/parser.rs:57-60, 263-272`; `apply-patch/src/file_update.rs:80-81, 155-158`. Parsing is lenient, e.g. it strips heredoc wrappers (`parser.rs:47-53`).

**P1/P3, sandbox.** Denial is detected heuristically after exit (`codex:sandboxing/src/denial.rs:13-72`):
- Exit 0 or no sandbox means not denied.
- Output containing "operation not permitted", "permission denied", "read-only file system", "seccomp", "sandbox", "landlock" or "failed to write file" means denied.
- Exit codes 2, 126 and 127 mean not denied.

The orchestrator (`core/src/tools/orchestrator.rs:140-232, 401-489, 556-630`) then:
1. asks for approval up front if policy requires;
2. runs sandboxed;
3. on a denial, asks the user `"command failed; retry without sandbox?"` if the policy allows (`untrusted`, or `granular` with `sandbox_approval`; `core/src/tools/sandboxing.rs:353-360`);
4. reruns unsandboxed.

Headless `codex exec` forces policy `never` (`exec/src/lib.rs:632`). A model asking for escalation under a forbidding policy gets `"approval policy is {p:?}; reject command — you cannot ask for escalated permissions if the approval policy is {p:?}"` (`core/src/tools/handlers/unified_exec/preparation.rs:276-282`).

**P2, user rejection.**
- "Decline" becomes `"rejected by user"` fed back. apply_patch shows `"patch rejected by user"` (`core/src/tools/events.rs:445-469`).
- "Cancel" becomes `ReviewDecision::Abort`, then `TurnAborted`: the turn stops (`core/src/tools/approvals.rs:519`).

**T1, retry.** Two layers.
- Transport (`codex:codex-client/src/retry.rs:22-52`; `model-provider-info/src/lib.rs:73-82, 499-505`): 4 attempts, 200 ms × 2^n ±10% jitter. Retries 5xx and timeout/connection errors, explicitly not 429 (`retry_429: false`).
- Stream/turn (`core/src/responses_retry.rs:56-182`): 5 retries, honouring the server's Retry-After; the user sees `"Reconnecting... n/max"`. Classification is in `protocol/src/error.rs:460-534`:
  - Backoff: stream errors, timeouts, unexpected status, 500, connection failure, rate limit.
  - Retry only if the server supplies a delay: a plain 429 (`RetryLimit`), overload.
  - Never: context window, usage limit, quota, invalid request, auth denial, sandbox.
- Stream idle timeout is 300 s, retryable.
- 401: one token refresh, then retry (`core/src/client.rs:2981-3160`).

**T2, context overflow.** No retry. The turn ends with `"Codex ran out of room in the model's context window. Start a new thread or clear earlier history before retrying."` (`protocol/src/error.rs:137-141`). Compaction is proactive, on token thresholds (`core/src/session/turn.rs:749-776`).

**Pairing.** Cancelled calls get synthetic outputs: `"Wall time: …\naborted by user"`, `"aborted by user after {s}s"`, `"aborted before dispatch"` (`parallel.rs:398-449, 493-513`). Before each request, a normalisation pass adds `"aborted"` to any call lacking an output and drops orphan outputs (`core/src/context_manager/normalize.rs:21-155`). An interrupt also injects a `<turn_aborted>` note saying commands "may have partially executed" (`core/src/context/turn_aborted.rs:12`).

**B, loops.** None found. Only token/session budgets: `SessionBudgetExceeded` (`core/src/model_request.rs:12-26`).

### 3.2 opencode (`oc`, TypeScript/Effect; the current `dev` branch is a rewrite)

**Mechanism.** A failed call is stored as `{type, message}` and lowered to an error tool result, `{"error":{"type":"tool.execution","message":"…"},"content":[]}` as JSON text. Anthropic also gets `is_error: true` (`oc:packages/core/src/session/runner/to-llm-message.ts:130-139`; `packages/ai/src/protocols/shared.ts:310-319`; `anthropic-messages.ts:904`).

**M1 / T3, bad or truncated JSON.** The call is not executed (`oc:packages/core/src/session/runner/publish-llm-event.ts:50-65, 342-365, 395-400`). Messages:
- `"The tool input could not be parsed as JSON, so the call was not executed. Reissue the call with valid JSON arguments."`
- With `finish_reason=length`: `"The tool call was not executed because the output token limit (stop reason: length) was reached before you could complete the arguments. Break large payloads into smaller tool calls and reissue the call with complete arguments."`

These errors are kept in history even when the message itself was cut (`to-llm-message.ts:160-170`).

**M2.** `No tool named "${name}" is currently available. Please use a tool from the available tool list.` (`oc:packages/core/src/tool.ts:321-323`).

**M3.** At most 5 issues are listed (`oc:packages/core/src/tool/runtime.ts:65-102`):

```
Invalid arguments for tool "${tool}":
- ${path}: ${message}
- ...and N more issues

Arguments provided:
${JSON}

Update the arguments and call the tool again.
```

**Deterministic repair** (`oc:packages/core/src/plugin/tool-input-repair.ts:8-206`) runs before validation:
- The alias `bash` maps to `shell`, applied only when no tool has the called name. The model is told: `There is no "bash" tool, so this ran as "shell". Call "shell" directly.`
- Type coercion only where the schema makes it unambiguous: stringified JSON, `"20"`→20, `"false"`→false, dropping null placeholders and extra keys on closed objects, wrapping a scalar into an array.

The older loop (`oc149`) used the AI SDK hook `experimental_repairToolCall` (`oc149:packages/opencode/src/session/llm.ts:327-347`):
- It lowercases the tool name if that matches a real tool.
- Otherwise it rewrites the call to a hidden `invalid` tool whose output is `"The arguments provided to the tool are invalid: ${error}"` (`oc149:packages/opencode/src/tool/invalid.ts`). That tool is excluded from `activeTools`.

**X1.** A non-zero exit is not an error; `"Exit code: N"` is appended to the output (`oc:packages/core/src/shell/result.ts:54-62`).

**X2.** Default timeout 2 min (`oc:packages/core/src/tool/plugin/shell.ts:25`). On timeout a foreground command moves to the background instead of being killed: `"…did not finish within its timeout of N seconds and was moved to the background. Do not start another copy while it is running."` (`shell.ts:111-122, 425-464`). A background timeout gives `"Command timed out after N seconds. If it needs longer and isn't waiting for input, rerun with a larger timeout."` (`result.ts:50-53`).

**X3.** Limits are 2000 lines / 50 KiB (configurable). The full output is saved to a file kept for 7 days. Markers:
- `"[showing lines 1-N of M (last line cut); full output saved to <file>]"` (`oc:packages/core/src/tool-output.ts:13-16, 113-115`)
- Shell keeps the tail: `"[showing the last K lines; …]"`

Error messages are not truncated.

**X4, edit** (`oc:packages/core/src/tool/plugin/edit.ts`). Matching is a fallback chain: exact, then typographic quote/dash/space normalisation, then ignoring trailing whitespace (`:45-98, 164-184`). Errors:
- `Could not find oldString in ${path}. It must match exactly, including whitespace and indentation.`, plus a hint: either `newString is already in the file, so this edit may already be applied.` or `The closest lines in the file:` and up to 12 lines (`:195-237, 318-330`).
- `Found ${n} matches for oldString, but expected exactly one. Add more surrounding context to make oldString unique, or set replaceAll to true to replace every occurrence.` (`:331-335`)
- `No changes to apply: oldString and newString are identical.` (`:276-280`)

**X5.** Typed failures become tool errors. An uncaught defect fails the call via `toSessionError(Cause.squash(…))` (`oc:packages/core/src/session/runner/step.ts:150-157, 272-279, 345-366`).

**P.** Rules are allow/ask/deny; the last match wins and the default is ask (`oc:packages/core/src/permission.ts:94-104`).
- A deny is fed back: `Permission denied: ${permission}`, or the configured reason (`:77-86, 262-269`).
- A user rejection with feedback feeds back the feedback text, and the loop continues (`:69-75, 317-321`).
- A user rejection without feedback stops the turn. The call is recorded as `"The user declined this tool call"` and other in-flight calls as `"Tool execution interrupted"` (`step.ts:262-280, 321-324`).
- Unattended runs turn ask into deny: `Permission ${action} needs approval, and nobody is present to give it` (`permission.ts:199-209`).

**B.** The `dev` rewrite has no doom-loop detector; only the config key and TUI label remain (`oc:packages/core/src/v1/config/permission.ts:27-38`).
- `oc149` had one (`oc149:packages/opencode/src/session/processor.ts:24, 305-330`): `DOOM_LOOP_THRESHOLD = 3`. If the last 3 tool parts have the same tool and `JSON.stringify`-identical input, it raises a `doom_loop` permission ask to the user.
- `dev` keeps a step cap: on the last step it forces `toolChoice: "none"` with a max-steps prompt (`packages/core/src/session/runner/max-steps.ts`).
- `dev` also bounds output-limit continuations. After a length finish it injects `"Your last response hit the output token limit … Break the remaining work into smaller pieces."`. After two continuations the step fails with `"Response still truncated after two output token limit continuations"` (`oc:packages/core/src/session/runner/llm.ts:38-39, 346-374`).

**T1/F.** Classification is in `oc:packages/ai/src/provider-error.ts:16-288`:
- overflow (about 35 regexes)
- 413
- content policy
- 402 → quota
- 401/403 → auth
- 429 → rate limit
- 408/409/5xx/`overloaded_error` → provider internal
- any other 4xx → invalid request

Retryable: rate limit, provider internal, unknown, transport (only if the request was not accepted), and incomplete stream. Not retried: auth, quota, content policy, invalid request, timeout. The header `x-should-retry` overrides both ways (`packages/ai/src/schema/errors.ts:197-230`).

Schedule (`oc:packages/core/src/model-retry.ts:12-86`): exponential from 2 s, gaps capped at 10 s, 10 retries, jittered. Retry-After is a floor, capped at 15 min. An unreachable host gets its own budget of up to 1 h. Transport timeouts get at most 3 retries.

A step retries transparently only if no output had started; otherwise it settles the partial message and retries fresh (`step.ts:244-259`). Exhausted or fatal errors go to the user, not the model.

**T2.** Proactive compaction runs at window − max(15%, 16k). On a provider overflow before any output, it compacts and retries once per step. Overflow is never retried as-is (`step.ts:198-209, 245`; `llm.ts:319-325`).

**Pairing.** A final guard gives any call without a result a synthetic `"Tool result missing"`, and empty output becomes `"(no tool output)"` (`oc:packages/ai/src/tool-history.ts:3-58`). After a crash, running calls become `Tool execution interrupted: ${name}` (`llm.ts:79, 419-442`).

### 3.3 OpenHands software-agent-sdk (`oh`, Python)

**Mechanism.** Per-call failures become an `AgentErrorEvent`, rendered as a `role="tool"` message with the same `tool_call_id` (`oh:sdk/event/llm_convertible/observation.py:195-203`). The loop continues.

Run-level failures become a `ConversationErrorEvent`, documented as "NOT sent back to the LLM" (`oh:sdk/event/conversation_error.py:11-27`), and status `ERROR`.

Tool observations with `is_error=True` are prefixed `"[An error occurred during execution.]\n"` (`oh:sdk/tool/schema.py:390, 444-457`).

**X5.** Any tool exception becomes `"Error executing tool '{name}': {e}"`. A `ValueError` is classed as the agent's outcome; anything else is classed INTERNAL and logged with a traceback (`oh:sdk/agent/parallel_executor.py:313-337`).

**M2.** First, deterministic normalisation (`oh:sdk/agent/utils.py:470-551`; aliases at `sdk/llm/mixins/fn_call_converter.py:636-645`):
- strips junk like `"str_replace </parameter"`;
- maps aliases (`bash`/`execute_bash`/`command` → `terminal`, `str_replace` → `file_editor`);
- treats `ls`/`git`/`pwd` used as a tool name as a terminal command;
- infers a missing `command` for `file_editor`.

Then: `"Tool '{name}' not found. Available: {available}"` (`oh:sdk/agent/agent.py:1455-1472`).

**M1/M3.** JSON is parsed again after stripping control characters (`utils.py:293-302`); lists and dicts sent as strings are repaired (`utils.py:125-175`). Errors:
- `"Error validating tool '{name}': {e}. Arguments: unparseable JSON"`
- `"Error validating tool '{name}': {e}. Parameters provided: [keys]"`, where `{e}` is pydantic's message (`agent.py:1499-1548`)

The stored call's arguments are replaced with `{"_openhands_malformed_tool_call": true, "error": …}`, so the replayed assistant `tool_call` is valid JSON (`agent.py:1368-1379`).

**M4** (`oh:sdk/agent/response_dispatch.py:55-79, 286-315`). A text-only reply finishes the turn. An empty or reasoning-only reply gets a user-role nudge: `"Your last response did not include a function call or a message. Please use a tool to proceed with the task."`

**B, StuckDetector** (`oh:sdk/conversation/stuck_detector.py`; thresholds in `sdk/conversation/types.py:150-161`). The window is the last 20 events since the last user message. Patterns:

| Pattern | Default threshold |
|---|---|
| Same action + same observation | 4 |
| Same action + error | 3: nudge on the 3rd, STUCK on the 4th. Parallel calls from one response count once. |
| Monologue | 3 agent messages in a row |
| A,B,A,B alternation | 6 actions + 6 observations |
| Context-error loop | stub, always False |

The nudge is a user-role message:
- `"You've called \`{tool}\` with the same arguments {N} times in a row and gotten the same error each time: {error}. Repeating the exact same call again will not work — review the error message and either correct the arguments or try a different approach."`
- For validation errors: `"Your calls to \`{tool}\` have failed validation {N} times without resolving the failing fields…"` (`:367-407`)

When STUCK, the run loop stops. The model is not told and the user is not prompted; a new user message resumes (`oh:sdk/conversation/impl/local_conversation.py:870-907, 2198-2205`).

**T1** (`oh:sdk/llm/llm.py:184-192, 388-399`; `sdk/llm/utils/retry_mixin.py`; `sdk/llm/exceptions/classifier.py:79-82, 163-217`).
- 5 attempts, exponential wait 8–64 s (multiplier 8), or Retry-After if longer. It gives up immediately if Retry-After exceeds the 64 s maximum.
- Retried: connection errors, 502, 503, 429, timeout, 500, `LLMNoResponseError`, and any status 408/409/429/5xx.
- Never retried: quota exhaustion; also bad request, auth, context window and content policy.
- On an empty response with temperature 0, the retry raises temperature to 1.0 (`retry_mixin.py:76-98`).

**T2.** Detection by litellm's error class plus message patterns (`classifier.py:28-37`). If a condenser exists, it emits a `CondensationRequest`; otherwise it re-raises, giving ERROR (`agent.py:894-935`). The default preset is `LLMSummarizingCondenser(max_size=80, keep_first=4)`. A provider rejection of broken tool pairing is classified separately and routed to the same recovery (`classifier.py:43-63`).

**F.** `ERROR` comes from an uncaught exception, auth (`"Your LLM API key appears to be invalid or has expired."`), the iteration cap (500, `"Agent reached maximum iterations limit (500)."`) or the budget cap (`local_conversation.py:274, 846-852, 2448-2530`).

**P.** Confirmation policy: `NeverConfirm` (default), `AlwaysConfirm`, or `ConfirmRisky`. A rejection gives `"Action rejected: User rejected the action"` and status IDLE (`observation.py:86-125`; `local_conversation.py:3117-3156`).

**X1/X2/X3, terminal** (`oh:tools/terminal/`).
- Soft timeout, when no `timeout` is set: after 30 s with no new output the model gets `"[The command has no new output after 30 seconds. You may wait longer to see additional output by sending empty command '', send other commands to interact with the current process, send keys ("C-c", "C-z", "C-d") to interrupt/kill the previous command…]"` (`constants.py:22-31`; `terminal_session.py:369-372`).
- Neither the soft nor the hard timeout kills the process.
- A non-zero exit is not `is_error`. The output ends with `"[The command completed with exit code {n}.]"` (`terminal_session.py:320-327`).
- Truncation at 30,000 chars keeps head and tail: `"<response clipped><NOTE>Due to the max output limit, only part of the full response has been shown to you.</NOTE>"`, plus the saved-file path when available (`oh:sdk/utils/truncate.py:15-124`).

**X4, file_editor** (`tools/file_editor/editor.py:159-260`):
- `"No replacement was performed, old_str \`{old_str}\` did not appear verbatim in {path}."` (after first retrying with the string stripped)
- `"No replacement was performed. Multiple occurrences of old_str … in lines {lines}. Please ensure it is unique."`

No lint-on-edit.

**Pairing.**
- Interrupts backfill `"Tool call interrupted before completion. The conversation was paused."` (`local_conversation.py:3019-3024, 3160-3186`).
- View properties drop unpaired calls or results and duplicate results, and condensation never splits a pair (`oh:sdk/context/view/properties/tool_call_matching.py:25-95`; `observation_uniqueness.py:21-40`).
- Parallel calls are merged back into one assistant message (`oh:sdk/event/base.py:109-148`).

### 3.4 Others, briefly

**Aider** (edit formats, no tool calls).
- A failed SEARCH/REPLACE match is reflected to the model (`aider:aider/coders/editblock_coder.py:84-124`). The message lists the failed blocks, the closest actual lines, `"The SEARCH section must exactly match an existing block of lines including all white space, comments, indentation, docstrings, etc"`, and `"The other {n} SEARCH/REPLACE blocks were applied successfully. Don't re-send them."`
- Matching first tries exact, then whitespace-tolerant, then `...` elision.
- `max_reflections = 3`, then the user sees `"Only 3 reflections allowed, stopping."` (`aider:aider/coders/base_coder.py:101, 932-944`).
- Lint and test failures are reflected only after the user confirms (`:1599-1623`).
- LLM retry: per-exception flags (`aider:aider/exceptions.py:13-110`); backoff 0.125 s doubling until the delay passes 60 s (`base_coder.py:1449-1487`).
- Context overflow is not retried; the user gets advice (`/drop`, `/clear`) (`:1628-1678`).

**SWE-agent.**
- Format, blocklist and bash-syntax errors re-query the model with an error template, up to `max_requeries = 3`, then exit and autosubmit (`swe:sweagent/agent/agents.py:158, 1106-1218`).
- The bad output and the error live only in temporary history; once the model recovers, they are dropped from the prompt (kept in the trajectory) (`agents.py:790-821`). This is the opposite of Manus's advice, applied only to errors that carry no information about the environment.
- Templates: `"Your last output did not use any tool calls!…"`, `"Your action could not be parsed properly: {exception_message}."`, `"Tool call arguments are not valid JSON."` (`swe:sweagent/tools/parsing.py:373-418`).
- Blocklist (vim, less, `python` with no arguments, …): `"Operation '{action}' is not supported by this environment."` (`swe:sweagent/tools/tools.py:34-72`).
- Timeout 30 s: `"The command '{command}' was cancelled because it took more than {timeout} seconds. Please try a different command that completes more quickly. Note: A common source of this error is if the command is interactive…"`. Three consecutive timeouts trigger an exit (`tools.py:139-151`; `agents.py:112-116, 968-989, 1168-1173`).
- Edit lint guardrail: flake8 checks F821, E999 and others before and after the edit. A new error reverts the edit with `"Your changes have NOT been applied. Please fix your edit command and try again. DO NOT re-run the same failed edit command."` (`swe:tools/windowed_edit_replace/bin/edit:58-161`).
- Observations are truncated at 100k chars with a hint to use head/tail/grep (`agents.py:69-82`).
- LLM retry: 20 attempts, random-exponential 10–120 s; context overflow, cost, auth and similar are excluded (`swe:sweagent/agent/models.py:55-63, 809-834`).

**Gemini CLI.**
- About 40 `ToolErrorType`s. Only `NO_SPACE_LEFT` is fatal; all others are "sent back to the model, allowing it to self-correct" (`gem:packages/core/src/tools/tool-error.ts:14-109`; `packages/cli/src/utils/errors.ts:112-166`).
- Unknown tool: `Tool "${name}" not found.` plus a Levenshtein suggestion, `" Did you mean one of: …"` (`gem:packages/core/src/scheduler/scheduler.ts:403-419`).
- Errors reach the model as `functionResponse.response = {error: message}`.
- Loop detection (`gem:packages/core/src/services/loopDetectionService.ts:29-66, 319-680`): a tool-call cycle repeated 5 times, content chunks repeated 10 times, or an LLM judge after 30 turns.
- The first detection injects `"System: Potential loop detected. … Avoid repeating the same tool calls or responses without new results."`; the second aborts the turn (`gem:packages/core/src/core/client.ts:791-897, 1374-1400`).
- Retry (`gem:packages/core/src/utils/retry.ts:20-456`): 10 attempts, 5–30 s ±30% jitter. Retries 429, 499, 5xx and network codes, never 400. Persistent 429 offers a model fallback.
- Edit errors (`gem:packages/core/src/tools/edit.ts:361-389`):
  - `"Could not find an exact match for 'old_string' … please use ReadFile to inspect the target lines before retrying"`
  - `"Expected 1 occurrence but found ${n} … set 'allow_multiple' to true."`

  Matching chain: exact, flexible, regex, fuzzy.
- Shell output above min(4 × remaining context tokens, 40k) chars is saved to a file, and the model sees the first 20% and last 80% (`gem:packages/core/src/utils/fileUtils.ts:814-833`).

**Cline** (the agent loop now lives in `sdk/`; the old `formatResponse.*` strings are not imported anywhere).
- Unknown tool `{error:"Unknown tool: X"}`, exceptions and bad JSON (`"Tool call X emitted invalid JSON arguments: …"`) are returned as error results (`cline:sdk/packages/agents/src/agent-runtime.ts:2594-2624, 2894-2938`).
- Mistake counter (`cline:sdk/packages/core/src/runtime/orchestration/session-runtime-orchestrator.ts:474, 1412-1436`; `runtime/safety/mistake-tracker.ts`): a turn counts if it had a failed call and no successful one; the limit is 6. The CLI asks the user to "Try a different approach" or "Stop this run"; VS Code stops.
- Identical-call detection (`runtime/safety/loop-detection.ts:113-156`): at 3 the model is told `"Detected 3 consecutive identical calls to \`X\`; consider trying a different approach."`; at 5 the run stops.
- API retry: 3 attempts, 1–15 s, only if nothing was streamed. Overflow gives one forced compaction and retry (`agent-runtime.ts:78-90, 1255-1401`).

**OpenAI Agents SDK.**
- A tool exception goes to `failure_error_function`. The default now returns the fixed `"An error occurred while running the tool."`, deliberately "without exposing the exception to the model" (`agents:src/agents/tool.py:697-711, 1997-2041`).
- Invalid JSON raises `ModelBehaviorError`, which the default formatter converts into the same generic message (`tool.py:1969-1985, 2778-2814`).
- An unknown tool raises by default; `tool_not_found_behavior="return_error_to_model"` sends `"Tool '{name}' not found."` instead (`agents:src/agents/run_config.py:78, 498-504`).
- Timeouts default to `error_as_result`: `"Tool '{name}' timed out after {s} seconds."` (`tool.py:518`).
- `MaxTurnsExceeded` (default 10) can be turned into a final output by `error_handlers["max_turns"]` (`run_config.py:45`; `run.py:1585-1609`).
- Guardrail tripwires end the run. Tool guardrails can either `reject_content` (the model sees the message) or raise.
- Model retry is opt-in, through `ModelSettings.retry` with policies `network_error`, `retry_after`, `http_status(...)` and others. Streams that already emitted output are never replayed (`agents:src/agents/run_internal/model_retry.py:428-444`).

---

## 4. Comparison

Abbreviations: **M** = fed back to the model as a tool result; **H** = the harness handles it silently; **U** = asks the user; **A** = aborts the turn or run.

| Class | Codex | opencode (`dev`) | OpenHands SDK | Gemini CLI | Cline SDK | SWE-agent | Agents SDK |
|---|---|---|---|---|---|---|---|
| T1: 429/5xx/network | H: transport 4× (5xx/network only), stream 5×; 429 only with Retry-After | H: 10× 2–10 s, Retry-After floor ≤15 min; 1 h budget for unreachable host | H: 5× 8–64 s; quits if Retry-After > max | H: 10× 5–30 s; 429 → offers model fallback | H: 3× 1–15 s, only if nothing streamed | H: 20× 10–120 s | opt-in policy |
| T2: context overflow | A, with message to user; proactive compaction | H: compact + retry once; proactive at 85% | H: condenser, else A | (not traced) | H: compact + retry once | A + autosubmit | (not traced) |
| T3: output limit / truncated args | (not traced) | M: "not executed… output token limit"; ≤2 continuations, then A | (not traced) | (not traced) | M: nudge ≤3× | (not traced) | (not traced) |
| M1: invalid JSON args | M: `failed to parse function arguments` | M: "could not be parsed as JSON… not executed" | H repair, then M; history args sanitised | M | M | M requery ≤3, then A | M (generic), or A |
| M2: unknown tool | M: `unsupported call` | H alias (bash→shell, model told), else M with hint | H alias/normalise, else M with list of available tools | M + "did you mean" | M | M requery | A default; M opt-in |
| M3: schema violation | M (serde error) | H coercion, else M (≤5 issues + args) | H repair, else M (pydantic) | M | M (zod) | M requery | M (generic) |
| M4: empty / no tool call | (not traced) | (not traced) | M nudge; text-only = finish | (not traced) | (not traced) | M requery | (not traced) |
| X1: non-zero exit | M, as data (success=true) | M, as data | M, as data (not is_error) | (not traced) | (not traced) | M, as data | n/a |
| X2: timeout | one-shot: kill, exit 124, partial output; interactive: keeps running, session id | moved to background, model told | process keeps running; model told to wait or send C-c | (not traced) | (not traced) | M cancel msg; 3 in a row → A | M `timed out after` |
| X3: big output | H: middle cut to 10k tokens + header | H: 2000 lines/50 KiB, full output saved to file | H: 30k chars head+tail, saved to file | H: ≤40k chars, saved to file | (not traced) | H: 100k chars + hint | n/a |
| X4: edit mismatch | M (apply_patch errors) | H fuzzy chain, else M + closest lines | M (after strip retry) | H fuzzy chain, else M | M | M; lint guardrail reverts edit | n/a |
| X5: harness exception | M or `Fatal` → A | M | M (INTERNAL, logged) | M (only NO_SPACE_LEFT is fatal) | M | A + autosubmit | M generic, exception hidden |
| P1: deny rule / sandbox | M; sandbox denial → U to escalate | M | M (hook reject) | M | (not traced) | M blocklist | M (`reject_content`) or A |
| P2: user rejects | decline → M; cancel → A | with feedback → M; without → A | M "Action rejected", IDLE | (not traced) | (not traced) | n/a | M |
| B1/B2: repetition | none | none in `dev`; `v1.4.9`: 3 identical → U | nudge at 3, STUCK (A) at 4 | nudge at 5 cycles, A on 2nd detection | nudge at 3, A at 5; 6 failing turns → U (CLI) / A | 3 failed requeries → A | n/a |
| B5: caps | token/session budget | step cap (last step tool-free) | 500 iterations, budget | (not traced) | (not traced) | cost, total time | `max_turns` = 10, handler |
| F: auth/quota | 1 refresh, then A | A (user-facing text) | 1 key refresh, then A | A | A | A + autosubmit | raise |

The convergence is clear. Malformed calls, execution failures and policy denials go back to the model as paired tool results with actionable text. Transient API errors are retried invisibly with bounded backoff. Overflow is compacted, not reported to the model. Auth and quota errors abort. Repetition is detected by the harness and handled first with a nudge, then by stopping. Exit codes are data, not errors.

---

## 5. Decision rule

Ask two questions: who caused the error, and who can fix it. Then:

1. **The model caused it and the model can fix it (M1–M4, X1–X4, P1): feed it back.**
   - Answer the same `tool_call_id`, so pairing holds.
   - Say what failed, why, and what to do next.
   - Echo the bad input, and list valid options (tool names, closest matching lines).
   - Never retry this kind of error silently: the same input gives the same failure.
   - Repair deterministically only when the fix is unambiguous (name alias, case, `"20"`→20, a JSON string inside a field). When repair changes behaviour, say so in the result (opencode).
   - Prevent rather than repair where the backend allows: `strict: true`, or vLLM `--tool-strict-level parameter`.

2. **Transient infrastructure failure (T1): the harness retries; the model never sees it.**
   - Exponential backoff with jitter, honouring Retry-After but capped.
   - A per-class budget: every project caps attempts (3–20) or total time.
   - Retry only while nothing has been committed: no streamed output, no executed tool (opencode, Cline, Agents SDK).
   - After the budget is spent, treat it as fatal and save state.

3. **Resource limits of the conversation (T2, T3): the harness acts deterministically.**
   - Overflow: compact and retry once. Never send the request as-is again, and never tell the model "context too long" (it cannot act on that).
   - `finish_reason=length` with a cut-off tool call: do not run the call and do not report a JSON error. Tell the model its output was cut and that it should split the work (opencode). Cap such continuations at about 2–3.

4. **Fatal (F, and X5 when local state is broken): abort with a clear message for the user and keep the transcript.**
   - Covers 401/403 after one refresh, 402/quota, 404 model, a 400 the harness caused, a full disk.
   - A harness exception during one call is not fatal. Report it to the model as a generic tool error, and log the traceback for the operator (OpenHands' INTERNAL class).

5. **Behavioural (B): the harness detects, the model gets one nudge, then the harness stops or asks.**
   - Fingerprint each call as (tool, canonical JSON args) and each result as (error flag, hash of the output).
   - Thresholds in use:
     - identical calls: 3 (opencode, Cline soft); 4 with identical results (OpenHands); 5 (Cline hard)
     - same error: nudge at 3, stop at 4 (OpenHands)
     - turns with only failing calls: 6 (Cline)
     - re-queries for format errors: 3 (SWE-agent, Aider)
   - Escalation ladder: nudge text, then stop and ask the user (interactive) or end with a status (headless).

**Where fed-back errors escalate to an abort.** Self-correction loses value with each attempt. Anthropic says Claude retries invalid calls 2–3 times before giving up. SWE-agent measured edit recovery falling from 90.5% to 57.2% after a single failure. Every project therefore bounds consecutive failures (3–6) and converts the next one into a stop. Counting must be per LLM response, not per call, so that one response with several bad parallel calls counts once (OpenHands, Cline). Any productive turn resets the counter.

**Keep errors in context, with one exception.** Errors that tell the model something about the environment stay in history (Manus): exit codes, missing files, edit mismatches. Pure format errors with no information content can be dropped once the next attempt succeeds (SWE-agent's temporary history). Dropping only the tail of the conversation does not change the earlier prefix.

**Pairing invariants**, needed by both the Anthropic and OpenAI APIs:
- Append the assistant message once, with all of its `tool_calls`.
- Every call gets exactly one result, including calls never executed: bad JSON, an earlier call in the batch aborted, a user interrupt, a harness crash. Codex writes "aborted before dispatch"; opencode "Tool execution interrupted".
- If the arguments were invalid JSON, sanitise them before replaying history; some servers reject replayed invalid JSON (OpenHands replaces them with a valid stub).
- Before every request, run a normalisation pass: add a synthetic result to unanswered calls and drop orphan results (Codex `normalize.rs`, opencode `tool-history.ts`, OpenHands view properties).

**Signalling errors without `is_error`.** Chat Completions tool messages have no error flag, so use a stable text prefix (`Error:` or `[error]`) and keep exit-code reporting separate from error status.

---

## 6. Recommendations for this harness

This is design input, mapped to `baseline/agent.py` gaps (line numbers are in that file).

**Transport (T, F); `call_llm`, L57-65.**
1. Give `requests.post` (L60) a connect/read timeout. Today it can hang forever.
2. Classify failures:
   - retry 408, 409, 429, 5xx, connection errors and timeouts with exponential backoff and jitter (e.g. 1 s × 2^n capped at 30 s, 5–8 attempts), honouring a capped `Retry-After`;
   - context-overflow 400s (match the vLLM/OpenAI message patterns) are T2 and go to compaction;
   - 401, 403, 404 and other 400s are fatal.

   Today `raise_for_status()` (L61) crashes the loop on the first 429.
3. Validate the response shape. A missing `choices` (L62) is a retryable "empty response" (OpenHands `LLMNoResponseError`), not a `KeyError`.
4. Read `finish_reason`. On `length`, do not execute truncated tool calls and do not treat truncated text as the final answer (L77-80). Feed back the "output limit reached, split the work" text, at most 2–3 times.
5. On fatal errors, or when retries run out, print a clear reason and save the message list to `runs/` before exiting. Today a crash loses the whole transcript.

**Model output (M); the loop body, L82-90.**
6. Wrap `json.loads` (L84). On failure, do not execute; answer the call with `Error: arguments are not valid JSON (<parser message>). The call was not executed. Reissue it with a JSON object matching the schema.` Store a valid stub in place of the bad arguments in history.
7. Check that the arguments are a JSON object and validate them against the tool's schema (required and unknown keys, types) before dispatch. Feed back each failing field plus the arguments received. Coerce only unambiguous cases (a stringified JSON object, a numeric string for an int).
8. Unknown tool (L50): list the available tools in the message. Alias obvious names (`shell`, `execute_bash` → `bash`) and say so.
9. Append the assistant message once, with all `tool_calls`; today L89 writes one assistant message per call and duplicates `content`. Answer every call, including those skipped after a failure. Before each request, run a check that adds `Error: tool call was not executed` to unanswered calls and drops orphan results.
10. Empty response (no content, no tool calls): nudge once ("Your last response contained neither a tool call nor an answer…") instead of treating it as finished (L77-80); stop on the second.
11. Send `strict: true` and an `additionalProperties: false` schema when the backend supports them. They are harmless where ignored (unverified for every server; check against the target vLLM/llama.cpp version).

**Tool execution (X); `run_bash`, L38-44.**
12. Timeout (L43-44): keep partial output (`TimeoutExpired.output` is bytes regardless of `text=True`, per the Python docs). Return it with `Error: command timed out after Ns; partial output above. If it is long-running, run it in the background with output redirected to a file, or raise the timeout.` Accept a model-supplied `timeout`, capped.
13. Run the command in its own process group (`start_new_session=True`) and kill the whole group on timeout. `Popen.kill()` signals only the shell (`pid` is the shell when `shell=True`, per the Python docs), so background children survive today.
14. Use `stdin=DEVNULL`. Today commands inherit the agent's stdin, so interactive tools (pagers, editors, prompts) hang until the timeout. Point the model at non-interactive flags in the timeout message (SWE-agent's wording).
15. Decode with `errors="replace"`. Under `text=True`, binary output raises `UnicodeDecodeError`, and the output is lost behind `Error calling bash` (L53-54).
16. Bound output: keep head and tail (e.g. about 10k tokens or 30–50 KB), mark the cut with byte and line counts, and save the full output under `runs/` with its path in the marker so the model can `grep` it (opencode, OpenHands, Gemini).
17. Keep non-zero exit as data (`Exit code: N` is already right, L42), not as an error prefix. Say `(no output)` explicitly when output is empty (SWE-agent).
18. Harness exceptions (L53-54): report them as `Error: internal harness error in <tool>: <type>: <msg>` to the model, and log the traceback separately.

**Loops and budgets (B).**
19. Fingerprint (tool, canonical args) and the result hash. On the 3rd identical call with an identical result, or the 3rd identical error, inject the OpenHands-style nudge. On the 4th, stop with status `stuck` and save the transcript.
20. Count consecutive turns in which all calls failed. Stop at about 5 (Cline: 6).
21. Lower `MAX_TURNS` (L10) to a realistic value, and add a token/cost budget. On the last turn send `tool_choice: "none"` so the model must summarise (opencode).

**Observability** (this repo has only `print` with a 500-char preview, L88).
22. Log one structured record per turn: request id, attempt number, HTTP status, retry delay, `finish_reason`, token usage, each tool call (name, args hash, duration, exit code, output size, truncated?, error class), and any loop-detector decision. These are the fields needed to tell transient, model and harness errors apart after the fact, and to measure the before/after numbers the task asks for.

---

## 7. Unverified or partial

- **Codex.** The exact final text the model sees for an `exec_command` user rejection is derived from code. It is probably `exec_command failed: CreateProcess { message: "Rejected(\"rejected by user\")" }`; tests only assert it contains "rejected by user".
- **Codex.** The one-shot timeout shows only `Process exited with code 124`, with no "timed out" text. Inferred from code.
- **Codex.** A sandbox denial in `exec_command` is only seen by the orchestrator if the process exits within the 150 ms spawn window. Inferred from code, not tested.
- **Codex.** Not traced: whether partial stream output survives a stream retry, and how `finish_reason=length` / incomplete responses reach the model.
- **opencode `dev`.** That a lone defect (uncaught throw) lets the step continue, with the error as the call's result. Inferred from control flow.
- **OpenHands.** Whether both exit-code lines appear together on command completion. Read from code, not run.
- **OpenHands.** The legacy OpenHands V0 controller (old StuckDetector, AgentState.ERROR) was not traced; only the SDK was.
- **Cline.** How the `{error}` object is serialised onto the wire. Also whether the per-tool `maxRetries` setting is used anywhere.
- **Agents SDK.** Retries inside the underlying OpenAI client (its own `max_retries`) were not checked.
- **Gemini, Cline, SWE-agent, Agents SDK.** Cells marked "(not traced)" in the table were not researched.
- **SWE-agent.** The bash syntax check runs in `swe-rex`, outside the repo. The `_RetryWithOutput` re-queries appear not to be bounded by `max_requeries`; not tested.
- **Anthropic, "Writing effective tools for agents".** The helpful and unhelpful error examples are images and could not be quoted.
- **Section 6, item 11.** Whether each OpenAI-compatible server (vLLM versions, llama.cpp) accepts or ignores `strict`.
