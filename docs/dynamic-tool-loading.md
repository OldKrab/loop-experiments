# Dynamic tool and skill loading in coding agents

Research input for adding dynamic skill/tool loading to `baseline/agent.py` (OpenAI-compatible `/chat/completions`, any model, possibly a self-hosted vLLM/SGLang/llama.cpp-style server). Central question from `TASK.md`: how to load skills/tools **without invalidating the prompt cache (KV-cache of the prefix) on every step**. Context compaction is out of scope except where it touches tool loading.

Researched 2026-11-14. Code was read (not run) from shallow clones; web docs were fetched the same day. Citations: `repo:path:Lstart-Lend` at the commit below, or a URL.

| Repo | Commit read |
|---|---|
| openai/codex | `b1573f102413e96a6481087922bf425231222dee` |
| anomalyco/opencode (formerly sst/opencode; branch `dev`) | `c9957fd50858aafd43fb8167b117b3a8e5210529` |
| OpenHands/software-agent-sdk | `3c66af1d14d0a7fbe74b8dc4218412ec7a877b79` |
| OpenHands/OpenHands (formerly All-Hands-AI/OpenHands) | `830c0459e2f6056ab81e020c22970e782ae1be75` |
| google-gemini/gemini-cli | `4ed06ed0ddc523a6d356a4ad35ddfea331041888` |
| block/goose | `2365bc5e898a38133c373eef2d1357416acd66e2` |
| cline/cline | `72b3d7140553a733242126e51a7c2e87efe75c64` |
| langchain-ai/langgraph-bigtool | `7064d14be5d0ac391551aa56add1df34478b1a25` |
| vllm-project/vllm | `2ab8e2f746696ad7aab6cc6178ee37afa072ec8e` |
| sgl-project/sglang | `b77d7b8573747aee535612413b5deb2fa178f86e` |

---

## 1. Summary of approaches

| # | Approach | Idea | Who does it |
|---|---|---|---|
| A | Everything up front | All schemas in `tools` for the whole session | Cline (MCP), Gemini CLI (MCP), OpenHands (MCP), baseline |
| B | Catalog + load action (progressive disclosure) | Prompt carries `name + description` per skill (~50–100 tokens each); the body is loaded on demand by a file read or a `load_skill` tool, and arrives as a **tool result** | Anthropic Agent Skills, Claude Code, Codex, opencode, OpenHands SDK, Gemini CLI, Goose, Cline |
| C | Search tool that returns schemas | Model calls `search(query)`; matched schemas become callable | Anthropic Tool Search (`defer_loading`), OpenAI Responses `tool_search`, Codex (client-side BM25 over MCP), Claude Code `ToolSearch`, opencode Code Mode `search()`, langgraph-bigtool |
| D | Meta-tool dispatch | Fixed `call_tool(name, args)` (plus a list/describe tool); schemas travel as text in tool results; the harness validates and dispatches | Goose code mode (`list_functions` / `get_function_details` / `execute_javascript`), Cline Composio meta-tools |
| E | Retrieval-based selection | Harness embeds the user query and binds top-k tools per step, without the model asking | RAG-MCP, Toolshed (papers); bigtool is the model-driven variant |
| F | Per-agent / per-mode subsets | Static filtering by agent profile, mode or config; fixed for a session or subagent | opencode agents, Gemini CLI plan mode / excludeTools, OpenHands subagents |
| G | Mask, don't remove | Keep `tools` constant and constrain which tools may be called (logit masking / prefill / `allowed_tools`) | Manus; OpenAI `allowed_tools`; vLLM named/required `tool_choice` via structured outputs |

The cache rule behind all of this: every serving stack caches an **exact token prefix**, and tool definitions are rendered **at or near the start** of that prefix. So the cache-safe variants are B, C-with-append, D and G, where new material is **appended** to the message list and the `tools` array plus system prompt stay byte-identical. A, E and naive C (rebinding `tools` per step) rewrite the start of the prompt whenever the set changes.

The most cache-conscious clients have converged on one design: **freeze a baseline at session start, append diffs as messages, and re-render the baseline only at compaction**. Codex calls this "world state" diffs; opencode calls it an instructions baseline with an epoch. The hosted APIs implement the same idea server-side (Anthropic `tool_reference`/`tool_addition`; OpenAI tools "injected at the end of the context window").

---

## 2. Per project

### 2.1 Anthropic (API, Agent Skills, engineering posts)

**Agent Skills: progressive disclosure.**
- Level 1 metadata (`name`, `description`, about 100 tokens per skill) is "loaded at startup and include[d] in the system prompt". Level 2 is the `SKILL.md` body (under 5k tokens): "Claude reads `SKILL.md` from the filesystem using bash. Only then does this content enter the context window." Level 3 is bundled files and scripts, loaded only when read; for scripts, only their output enters context ([Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), "Level 1/2/3" and the token-cost table).
- The engineering post: "At startup, the agent pre-loads the `name` and `description` of every installed skill into its system prompt". It also says the amount of context bundled in a skill is "effectively unbounded" because it is read through a filesystem ([Equipping agents… with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills), 2025-10-16).
- Open spec at [agentskills.io/specification](https://agentskills.io/specification):
  - `name` is ≤64 chars, `[a-z0-9-]`, and must match the directory name.
  - `description` is ≤1024 chars and should say what the skill does and when to use it.
  - Optional fields: `license`, `compatibility`, `metadata`, `allowed-tools` (experimental).
  - The body should stay under 500 lines; file references should be one level deep.
- Client guide ([agentskills.io: adding skills support](https://agentskills.io/client-implementation/adding-skills-support)). Directly applicable to this harness:
  - Scan `<project>/.agents/skills/` and `~/.agents/skills/`. Project scope overrides user scope. Gate project skills on trust.
  - The catalog goes either in the system prompt or in the description of a dedicated activation tool. Hide skills that can't be used; omit the catalog if it is empty.
  - Activation is model-driven, by file read or by an `activate_skill` tool. A dedicated tool can strip frontmatter, wrap the body in `<skill_content name=…>`, list bundled resources **without reading them**, and deduplicate.
  - "exempt skill content from pruning" during compaction.

**Tool Search Tool and `defer_loading`** ([tool-search-tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)).
- Variants: `tool_search_tool_regex_20251119` (Python regex, ≤200 chars) and `tool_search_tool_bm25_20251119` (natural language, ≤500 chars). A search returns 5 `tool_reference` blocks by default, which "The API automatically expands … into full tool definitions".
- "You still send every tool's full definition in the `tools` array on every request, including the deferred ones." At least one tool must be non-deferred. Up to 10,000 deferred tools per request.
- Cache: "Internally, the API excludes deferred tools from the system-prompt prefix. When Claude discovers a deferred tool … the API appends a `tool_reference` block inline in the conversation". [Tool use with prompt caching](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching) adds: "The prefix is untouched, so prompt caching is preserved."
- Custom client-side search is supported: your own tool returns `tool_result` content of `{"type":"tool_reference","tool_name":…}`. Every referenced tool must still be declared in `tools` (deferred).
- Guidance: use it at ≥10 tools or >10k tokens of definitions. Keep the 3–5 most-used tools non-deferred. Namespace tool names by prefix (`github_`, `slack_`). Add a system-prompt line naming the tool categories that can be searched. Selection accuracy "degrades once you exceed 30–50 available tools".
- [Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) (2025-11-24) reports ~77K→~8.7K tokens of tool context. MCP evals with search rose from 49%→74% (Opus 4) and 79.5%→88.1% (Opus 4.5). It also says: "Tool Search Tool doesn't break prompt caching because deferred tools are excluded from the initial prompt entirely."

**Mid-conversation tool changes** (newer than the posts above): see [Mid-conversation system messages and tool changes](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages) and [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).
- "The `tools` array sits even earlier in the hashed request prefix than the top-level `system` field, so editing it invalidates the prompt cache for the entire conversation."
- Fix: declare tools up front (optionally deferred), then append a `role:"system"` message holding `tool_addition` / `tool_removal` blocks. The blocks hold a `tool_reference`, or, with beta `inline-tools-2026-09-15`, a full `tool_definition`. "The `tools` array and every earlier message stay exactly as sent, so the prompt cache still hits and only the appended message is processed as new input."
- The same mechanism handles appended system instructions: "Append a `{"role": "system"}` message to `messages` instead of editing the top-level `system` field." This works on listed recent models but not on Sonnet 5.
- Placement rule: the message must follow a `user` turn, which may be the `tool_result` message, and it must not sit between a `tool_use` and its `tool_result`.

**Cache invalidation hierarchy** ([tool-use-with-prompt-caching](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching), "What invalidates your cache"):
- The order is `tools → system → messages`. "Modifying tool definitions: Entire cache".
- Changing `tool_choice` invalidates the messages cache only, as do `disable_parallel_tool_use` and toggling images.
- Under the hood, "the API constructs a special system prompt from the tool definitions" ([define-tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)).

**Writing tools for agents** ([post](https://www.anthropic.com/engineering/writing-tools-for-agents), 2025-09-11):
- "More tools don't always lead to better outcomes". Consolidate tools (`schedule_event` instead of list+create), namespace by prefix, and offer a `response_format` concise/detailed enum.
- "For Claude Code, we restrict tool responses to 25,000 tokens by default."
- [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (2025-09-29) frames this as "just in time" retrieval of lightweight identifiers and names "bloated tool sets" as a common failure mode.

### 2.2 Claude Code (documented behaviour)

**MCP tool search** ([code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp), "Scale with MCP tool search").
- On by default: "Only tool names and server instructions load at session start". Claude loads the full schemas through the `ToolSearch` tool.
- `ENABLE_TOOL_SEARCH` takes:
  - unset/`true`: deferred.
  - `auto`: defer only once MCP definitions exceed 10% of the context window.
  - `auto:N`: the same with a threshold of N%.
  - `false`: everything loaded up front.
- Per-server `alwaysLoad`; per-tool `_meta["anthropic/alwaysLoad"]`.
- Description caps: 4,096 chars for up-front tools and server instructions; 16,384 chars for a tool loaded through search.
- Behind a gateway it needs `defer_loading` and `tool_reference` to be forwarded. From v2.1.305 it retries without tool search after a 400/422.
- Once tool search is on in a conversation it stays on, even if the total drops below the threshold. This is cache-friendly hysteresis.

**Skills** ([code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills)).
- The listing of names and descriptions is in context every turn. Its budget is 1% of the context window (`skillListingBudgetFraction`, `SLASH_COMMAND_TOOL_CHAR_BUDGET`). Each entry is capped at 1,536 chars. On overflow, descriptions of the least-used skills are dropped first ("Skill descriptions are cut short").
- `disable-model-invocation: true` removes the description from context.
- An invoked skill's "rendered `SKILL.md` content enters the conversation as a single message and stays there". An identical re-invocation adds a short "already loaded" note instead of a second copy.
- After auto-compaction, the most recent invocation of each skill is re-attached: first 5,000 tokens each, 25,000 total ("Skill content lifecycle").

### 2.3 OpenAI Codex CLI

Paths are under `codex/codex-rs/`. Codex now speaks **only the Responses API**: "`wire_api = \"chat\"` is no longer supported" (`model-provider-info/src/lib.rs:L110-143`). Its tool-loading mechanisms therefore lean on Responses features (`namespace`, `tool_search`, `defer_loading`). Its general principle, **append diffs and never rewrite the prefix**, carries over to any backend.

**Skills.**
- Roots: project `.codex/skills`, every `.agents/skills` from the project root (`.git` marker) down to cwd, `~/.agents/skills`, `$CODEX_HOME/skills` (deprecated), the system and admin folders, and plugins (`ext/skills/src/host_roots.rs:L127-333`).
- Scan limits: depth 6, 2,000 dirs and 20,000 entries per root (`ext/skills/src/loader/mod.rs:L21-27`).
- Frontmatter: `name`, `description` (required), `metadata.short-description`. A repair pass handles colon-heavy YAML (`skills/src/parser.rs:L4-181`).
- Catalog: a `## Skills` section with one line per skill, `- {name}: {description} (file: {path})`, followed by "How to use skills" rules (`ext/skills/src/catalog_prompt.rs:L3-133`). Key wording: "If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description … you must use that skill for that turn"; "open and read its `SKILL.md` completely before taking task actions" (`catalog_prompt.rs:L24-40`).
- Injection: a **developer-role message** wrapped in `<skills_instructions>`, not the system/instructions field and not the tools (`ext/skills/src/fragments.rs:L42-70`).
- Budget: 2% of the context window, or 8,000 chars if the window is unknown. Configurable, capped at 10k tokens. Descriptions are cut to 1,024 chars and then shortened round-robin. If even names don't fit, skills are dropped with the warning "Exceeded skills context budget…". Order is deterministic: scope, then name (`ext/skills/src/render.rs:L23-33, L91-107, L140-195`).
- Loading the body:
  - Implicit: the model reads `SKILL.md` through the shell. Core only detects this for telemetry (`core/src/skills.rs:L237-322`).
  - Explicit `$name` mention: the harness injects a user-role `<skill><name>…<path>…` message with the body (`skills/src/selection.rs:L33-109`; `ext/skills/src/fragments.rs:L87-127`).
- Catalog changes mid-session (flag `SkillCatalogDeltas`, off by default): appended developer messages "`## {source} skills update` / `### Added or updated skills:`" (`ext/skills/src/catalog_delta.rs:L1-200`).

**MCP and tool search.**
- Each MCP server is a Responses `namespace` named `mcp__<server>`, whose description is the server instructions. Per-server `enabled_tools`/`disabled_tools` (`codex-mcp/src/tools.rs:L24, L84-190`; `core/src/tools/handlers/mcp.rs:L577-608`).
- If model metadata has `supports_search_tool`, MCP tools are registered as `ToolExposure::Deferred` and left out of the initial list. A client-executed `tool_search` tool is added, described as "Searches over deferred tool metadata with BM25 and exposes matching tools for the next model call" (`core/src/mcp_tool_exposure.rs:L155-159`; `core/src/tools/handlers/tool_search_spec.rs:L16-106`).
- BM25 runs locally (`core/src/tools/handlers/tool_search.rs:L152-178, L341-356`). Results are returned as `tool_search_output` with namespace specs flagged `defer_loading: true` (`tools/src/tool_search.rs:L98-132`).
- The search tool's spec is cached so it stays byte-stable (`tool_search.rs:L64-138`).
- With `DeferredToolWorldState` (on by default), the list of searchable sources is taken *out* of the tool description. It is delivered as an appended developer `<tools>` message with "Added…/Removed deferred tool namespaces" diffs, capped at 4 KB (`core/src/tools/spec_plan.rs:L1685-1702`; `core/src/context/world_state/tools.rs:L29-159`).

**AGENTS.md.**
- Discovery walks from the project root to cwd, preferring `AGENTS.override.md`, then `AGENTS.md`, then fallbacks (`core/src/agents_md.rs:L196-303`). The default limit is 32 KiB in total (`config/src/config_toml.rs:L76`).
- Injected as a user-role message: `# AGENTS.md instructions for <dir>` `<INSTRUCTIONS>…` (`core/src/context/user_instructions.rs:L22-41`).
- Changes are appended: "These AGENTS.md instructions replace all previously provided AGENTS.md instructions." (`core/src/context/world_state/agents_md.rs:L11-80`).

**Cache design ("world state" diffing).**
- The full context is rendered once. Later turns append only per-section diffs: environment (`<environment_context>` with changed fields only), model switch (`<model_switch>` developer message), and permissions (`core/src/context/world_state/mod.rs:L73-85, L361-459`; `world_state/environment.rs:L141-236`; `core/src/context/model_switch_instructions.rs:L32-39`).
- Compaction triggers a fresh full render (`core/src/compact.rs:L435`).
- `prompt_cache_key` = session id (`core/src/client.rs:L712-732`).
- "Incremental tools" mode (Responses Lite and some cloud routes): tool declarations move out of the top-level `tools` into `AdditionalTools` history items. Changes append "This is an incremental tools update. Previously declared tools remain available … If a tool is redefined here, its latest definition replaces the earlier one." plus removal notices (`prompts/src/model_messages/incremental_tools.rs:L30-58`; `core/src/context/world_state/top_level_tools.rs:L215-363`; `core/src/session/turn.rs:L1853-1875`). On standard Responses models the `tools` array is simply re-sent and changes when the tools change.
- Unverified: how the server treats `AdditionalTools`. Responses Lite looks internal.

### 2.4 opencode

The repo moved to `anomalyco/opencode`. At this commit the code is in `packages/core`, `packages/ai` and `packages/codemode`, and the docs are in `services/site/src/docs/content/`. Of all the clients surveyed, this one has the most explicit cache-preserving design.

**Registry and per-request snapshot.**
- `Tool.snapshot(permissions)` drops tools whose action is wholly denied (`packages/core/src/tool.ts:L254-327, L385-388`). It then splits the rest into direct tools and "Code Mode" tools that sit behind a single `execute` tool. Direct tools are **sorted by name**, with `execute` last (`tool.ts:L296-300`).
- The snapshot is taken every step from `Permission.merge(agent.permissions, session.permissions)` (`packages/core/src/session/context.ts:L136-176`; `session/runner/llm.ts:L227-251`).
- Per-agent filtering is permission rules. The legacy `tools: {x: bool}` setting maps to allow/deny rules (`packages/core/src/config/normalize.ts:L511-522`). The built-in `explore` agent is "deny *" plus read/search tools (`packages/core/src/plugin/agent.ts:L55-117`).
- Model-specific swap: `gpt-*` models get `patch` instead of `edit`/`write` (`packages/core/src/tool/plugin/patch.ts:L292-305`).

**Skills.**
- Discovered from `.opencode/skill(s)`, `~/.config/opencode/skill(s)`, `~/.claude/skills`, `~/.agents/skills` (plus ancestors) and remote `index.json` catalogs. Scan depth is 6 (`packages/core/src/config/plugin/skill.ts:L86-104`; `config/plugin/compatibility.ts:L45`; `config/plugin/skill-scan.ts:L7-45`).
- The catalog is an *instructions* source (`core/skill-guidance`): "Use the skill tool to load a skill when a task matches its description." followed by `<available_skills>`. It is filtered by permission and sorted by id (`packages/core/src/skill/instructions.ts:L25-80`).
- The `skill` tool has a **fixed** description and input `{id}` (`packages/core/src/tool/plugin/skill.ts:L12-62`). It returns `<skill_content name=…>` with the body, the base directory, and a sampled `<skill_files>` list of at most 10 files (`packages/core/src/skill.ts:L40-94`).

**Instructions baseline plus appended deltas. This is the key cache mechanism.**
- The system prompt is the base prompt plus an instruction baseline. Instructions are "Ordered from most to least shared across sessions so the baseline stays a reusable prompt-cache prefix": Code Mode catalog, then MCP, then references, then skills, then AGENTS.md, then date/env, then session entries (`packages/core/src/session/context.ts:L162-173`).
- The baseline is **frozen per session epoch** (`packages/core/src/session/instruction-state.ts:L159-169`). Later changes are hash-diffed (`packages/core/src/instructions/index.ts:L144-161`) and **appended as chronological `system` messages** (`packages/core/src/session/message-updater.ts:L154-165`).
- Skill deltas, for example: "New skills are available in addition to those previously listed:" and "The following skill IDs are no longer available and must not be used: …" (`skill/instructions.ts:L35-46`).
- The epoch advances only at compaction (`packages/core/src/session/projector.ts:L1118-1123`).
- For Anthropic, these become native mid-conversation system messages. Otherwise they become `<system-update>` text inside the user turn, never between a tool call and its result (`packages/ai/src/protocols/anthropic-messages.ts:L801-827`; `packages/ai/src/protocols/shared.ts:L224-248`).

**MCP and Code Mode (deferred tools).**
- MCP tools are namespaced `<server>_<tool>` and are Code Mode by default (`packages/core/src/tool/mcp.ts:L23-25, L49-121`). They are not sent as native tool schemas. They appear in an instructions catalog with a budget of about 2,000 tokens, descriptions cut to 120 chars, and pinned tools always shown (`packages/core/src/codemode/catalog.ts:L50-126`).
- When the catalog is partial: "find it with the global `search(...)` function. Do not guess tool names." The model then calls `await tools.ns.tool(...)` from JavaScript inside `execute` (`packages/core/src/codemode/instructions.ts:L9-17`; search in `packages/codemode/src/tool-runtime.ts:L432-477`).
- The `execute` description is "Invariant model-facing guidance; the changing tool catalog is delivered through Instructions" (`packages/core/src/codemode/tool.ts:L74-83`).
- Docs: denying `execute` means tools are "listed as direct tools, each with its full definition in every request" (`services/site/src/docs/content/tools.mdx:L227-245`).

**Other cache measures.**
- At the step limit, tools stay in the request and `toolChoice:"none"` is set: "Keep tool definitions on the final Step to preserve the provider's cached prefix" (`session/runner/llm.ts:L276-280`).
- Schema min/max noise is stripped "so tool schemas don't change and bust prompt caches" (`packages/core/src/tool/runtime.ts:L196-210`).
- `prompt_cache_key` comes from the session's affinity id (`session/model-request.ts:L335-337`).
- Anthropic breakpoints go on the last tool, the first and last system parts, and the last message (`packages/ai/src/cache-policy.ts:L99-127, L215-227`).

**Unknown tools.**
- "No tool named "X" is currently available. Please use a tool from the available tool list." (`tool.ts:L311-323`).
- A repair plugin aliases `bash`→`shell` and coerces stringified JSON arguments (`packages/core/src/plugin/tool-input-repair.ts:L22-72`).

### 2.5 OpenHands (software-agent-sdk)

The legacy `RecallObservation`/`MicroagentKnowledge` design no longer exists. The OpenHands repo is now a frontend whose backend is the SDK Agent Server (`OpenHands:docs/architecture.md:L23`). Paths below are in `software-agent-sdk:openhands-sdk/openhands/sdk/`.

**Skill types.**
- Triggers are `KeywordTrigger`, `TaskTrigger` and `PathTrigger`. A skill with no trigger is always on (`skills/trigger.py:L19-47`; selection logic in `skills/skill.py:L548-635`).
- `SKILL.md` (AgentSkills format) is detected by file name, and `scripts/`, `references/`, `assets/` are discovered (`skills/skill.py:L387-448`).
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `.cursorrules` are always on. Nested `dir/AGENTS.md` becomes a `PathTrigger` on `dir/**` (`skills/skill.py:L349-355, L638-674`).
- Directories: `.agents/skills`, `.openhands/skills`, `.openhands/microagents` (legacy), plus the user-level equivalents. Precedence: public < user < project (`skills/skill.py:L953-957, L1076-1166, L1431-1432`).

**Keyword triggering.**
- Matching is whole-token and case-insensitive: `(?<![a-z0-9])kw(?![a-z0-9])`, "so `git` does not fire on `github`" (`skills/skill.py:L165-176`).
- Only user messages are checked (`context/agent_context.py:L535-592`; called from `conversation/impl/local_conversation.py:L2211-2228`).
- The triggered text is rendered as `<EXTRA_INFO>` and **appended as extra content blocks of that same user message** (`event/llm_convertible/message.py:L44-50, L117-120`). It is not a system-prompt change.
- It is deduplicated once per conversation through `activated_knowledge_skills` (`local_conversation.py:L2216, L2228`; `conversation/state.py:L186-189`). A TODO notes that this does not yet interact with the condenser (`local_conversation.py:L2218-2220`).
- Path rules are injected the same way into the `extended_content` of tool observations (`local_conversation.py:L686-713`).

**Progressive disclosure.**
- `<available_skills><skill><name>…<description>…` goes in the system prompt. `<location>` is "intentionally omitted so the agent cannot bypass `invoke_skill`" (`skills/skill.py:L1495-1575`, esp. `L1566-1568`).
- The `invoke_skill(name)` tool returns the rendered body as a tool result and records `state.invoked_skills` (`tool/builtins/invoke_skill.py:L51-198`). It is auto-attached only when an invocable skill exists (`agent/base.py:L593-607`).

**Cache structure.**
- The system message has two content blocks: a static `system_prompt` and a `dynamic_context` that is "not cached" (`event/llm_convertible/system.py:L12-41, L72-85`). Sections are tagged `CacheTier.STATIC` or `DYNAMIC` (`context/prompts/section.py:L25-31`).
- The skills catalog, repo context, date and secrets are DYNAMIC (`context/prompts/sections/dynamic.py:L32-169`). The rationale: "should NOT be included in the cached system prompt to enable cross-conversation cache sharing" (`agent/base.py:L520-544`).
- Anthropic `cache_control` goes on the static system block and on the last user/tool message (`llm/llm.py:L3161-3189`).
- The system prompt is built once per conversation (`agent/agent.py:L567-574`).

**MCP.**
- MCP tools are loaded eagerly at startup, prefixed `{server}_{tool}` when there are several servers, and filtered by `filter_tools_regex` (`conversation/impl/local_conversation.py:L1614-1678`; `agent/base.py:L849-863`). There is no tool search or `defer_loading`.
- `tools/list_changed` notifications add or replace tools (`agent/base.py:L902-1010`), and tools are re-sent from the live map every step (`agent/agent.py:L853-856`). So an MCP change mid-conversation rewrites the tools prefix. That consequence is my inference.
- On resume, tools may be added but not removed: "the LLM may have already been told about them" (`agent/base.py:L705-756`).

**Per-agent subsets.** Subagent frontmatter `tools: list[str]` (`subagent/schema.py:L215-222`), agent profiles (`profiles/agent_profile.py:L210, L302-308`).

### 2.6 Manus: "Context Engineering for AI Agents"

Source: [manus.im blog](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus), Yichao 'Peak' Ji, 2025-07-18.

**KV-cache basics.**
- KV-cache hit rate is "the single most important metric" for a production agent. The input:output ratio is about 100:1. Cached input on Claude Sonnet costs 0.30 vs 3 USD/MTok.
- Keep the prefix stable: "even a single-token difference can invalidate the cache". Don't put timestamps in the system prompt.
- Keep context append-only, with deterministic serialization (JSON key order).
- On vLLM, enable prefix caching and route by session ID.

**"Mask, Don't Remove".**
- Avoid adding or removing tools mid-iteration. Tool definitions sit near the front of the serialized context, so "any change will invalidate the KV-cache for all subsequent actions and observations".
- Earlier steps that reference now-undefined tools also confuse the model and lead to schema violations or hallucinated actions.
- Instead, a state machine masks token logits. Prefill modes (Hermes format):
  - Auto: prefill `<|im_start|>assistant`.
  - Required: prefill up to `<tool_call>`.
  - Specified: prefill up to `{"name": "browser_`.
- Tool-name prefixes (`browser_`, `shell_`) let a group be selected by prefix without a stateful logits processor.

**File system as context.** Compression should be reversible: drop a page's content but keep its URL or path.

### 2.7 OpenAI API docs: prompt caching, tool search, namespaces, `allowed_tools`

**Prompt caching** ([guide](https://developers.openai.com/api/docs/guides/prompt-caching)).
- "Cache reuse requires the entire rendered prefix to match." `tools` invalidates the prefix if names, descriptions, schemas, **ordering** or tool-specific instructions change. The minimum prefix is 1,024 tokens.
- Routing uses a hash of the initial tokens, "including tool definitions", plus `prompt_cache_key`, which matters on models before GPT-5.6.
- The section "Manage tools with append-only updates":
  - keep definitions, ordering and schemas stable;
  - use `tool_choice: "none"` instead of removing tools;
  - use `allowed_tools` to restrict calls "while keeping the supplied `tools` list stable";
  - use tool search with `defer_loading`, where "Discovered tools are appended at the end of context";
  - add tools mid-thread with an `additional_tools` input item.

**Tool search** ([guide](https://developers.openai.com/api/docs/guides/tools-tool-search)).
- Responses API only, `gpt-5.4`+. "When new tools are discovered by the model, they are injected at the end of the context window." "All tools are loaded at the end of the model's context window … This allows the model's cache to be preserved".
- Two modes: hosted, and client-executed (`execution:"client"`, where your code answers a `tool_search_call` with a `tool_search_output`).
- For a deferred function, the model still sees its name and description, "so in practice tool search is mostly deferring the parameter schema". Namespaces and MCP servers show only the namespace description, and fewer than 10 functions per namespace is recommended.

**`allowed_tools`** ([function calling](https://developers.openai.com/api/docs/guides/function-calling), "Tool choice").
- `tool_choice: {"type":"allowed_tools","mode":"auto","tools":[…]}` lets you "not modify the list of tools you pass in, so you can maximize savings from prompt caching".
- Unverified: whether every Chat-Completions-compatible server honours it. vLLM's chat path does not appear to (§2.8).

### 2.8 Self-hosted: vLLM and SGLang prefix caching

**vLLM Automatic Prefix Caching.**
- Each KV block's hash is `hash((parent_hash, block_token_ids, extra_keys))`. Extra keys are LoRA, multimodal hashes, `cache_salt` and prompt embeds (`vllm:docs/design/prefix_caching.md:L15-19`; `vllm:vllm/v1/core/kv_cache_utils.py:L627-665, L697-727`).
- "We only cache full blocks" (`docs/design/prefix_caching.md:L21-22`), with a default block size of 64 (`vllm/config/cache.py:L186`). Unverified: the backend may choose a different size; check the startup log.
- Prefix caching is on by default (`vllm/config/cache.py:L268`; `vllm/engine/arg_utils.py:L3138-3144`) with LRU eviction (`docs/design/prefix_caching.md:L198-208`).
- Because hashes chain, a change in any token invalidates every later block. A request reuses exactly the longest block-aligned common prefix.

**SGLang RadixAttention.**
- A radix tree over tokens, on by default (`--disable-radix-cache` defaults to False). Page size defaults to 1, so match granularity is per token, but some attention backends force 64. Eviction is LRU (`sglang:docs/docs/advanced_features/server_arguments.mdx:L560-563, L590-594, L2592-2595`).
- Matching lives in `sglang:python/sglang/srt/mem_cache/radix_cache.py:L369-453`.

**Where tools land in the token stream.**
- vLLM passes `tools` to `tokenizer.apply_chat_template(…, tools=tools)` (`vllm:vllm/renderers/online_renderer.py:L301-325`; `vllm:vllm/renderers/hf.py:L886-938`). The template decides placement.
- Hermes and Qwen3-Coder templates render tools **inside the first system turn** (`vllm:examples/tool_chat_template_hermes.jinja:L35-77`; `vllm:examples/tool_chat_template_qwen3coder.jinja:L24-35`).
- Llama 3.1 renders them in the first user message by default (`examples/tool_chat_template_llama3.1_json.jinja:L5-8, L56`). That template also inserts today's date (`L9-13`), so the prefix changes daily.
- Mistral renders `[AVAILABLE_TOOLS]` before the **last** user message (`examples/tool_chat_template_mistral.jinja:L19-47`). The tools block moves every user turn, so even a constant `tools` array can cost cache. Mistral templates also reject non-initial system messages (`L14, L84`).
- ChatML-style templates (Hermes, Qwen3-Coder) render a later `role:"system"` message in place (`tool_chat_template_qwen3coder.jinja:L97-98`).
- **Consequence:** with the common ChatML family, any change to `tools` changes tokens right after the system header, and almost nothing is reused.

**`tool_choice` side effects.**
- vLLM still renders tools when `tool_choice="none"` unless `--exclude-tools-when-tool-choice-none` is set (`vllm:docs/features/tool_calling.md:L107-110`).
- SGLang drops tools for `"none"` and passes **only the named tool** for a named `tool_choice` (`sglang:python/sglang/srt/entrypoints/openai/serving_chat.py:L1794-1809`). On SGLang, changing `tool_choice` therefore rewrites the prefix (inference from code).

**Constrained decoding as masking.** vLLM's named and `required` `tool_choice` use structured outputs to constrain the call (`vllm:docs/features/tool_calling.md:L76, L86-103`). This gives a server-side "mask" for forcing one specific tool without changing `tools`. There is no generic "subset of N tools" mask on the chat path.

**`defer_loading` and `tool_addition` on vLLM.**
- vLLM's protocol accepts `defer_loading` on chat-completions tools (`vllm/entrypoints/openai/chat_completion/protocol.py:L210-227`). Its Anthropic-compatible endpoint accepts `tool_addition`/`tool_removal` but documents: "Chat templates see a single tool list, so this resolves the tools in effect at the end of the conversation" (`vllm:vllm/entrypoints/anthropic/serving.py:L824-866`).
- So on a self-hosted server these features are only syntax. The merged list is rendered at the top, and the cache benefit Anthropic's API gets does not carry over. No template in `vllm/examples` references `defer_loading`.

**Measuring.**
- vLLM: `usage.prompt_tokens_details.cached_tokens` is returned only with `--enable-prompt-tokens-details` (`vllm:vllm/entrypoints/common/cli_args.py:L156-157`; `vllm/entrypoints/openai/chat_completion/serving.py:L98-117`). Prometheus exposes `vllm:prefix_cache_queries` / `vllm:prefix_cache_hits` (`vllm/v1/metrics/loggers.py:L667-679`).
- SGLang: `--enable-cache-report` (`python/sglang/srt/entrypoints/openai/usage_processor.py:L36-46`).
- Isolation between tenants: `cache_salt` (vLLM, `chat_completion/protocol.py:L511-520`; SGLang `protocol.py:L1191-1193`).

### 2.9 Others (brief)

**Gemini CLI.**
- Skills: `SKILL.md` discovered by `packages/core/src/skills/skillLoader.ts:L142-211`. The system prompt lists `<available_skills>` and tells the model to call `activate_skill` (`packages/core/src/prompts/snippets.ts:L314-334`).
- `activate_skill` returns `<activated_skill><instructions>…<available_resources>` as a tool result (`packages/core/src/tools/activate-skill.ts:L111-153`). Its `name` parameter is `z.enum(skillNames)` (`tools/definitions/dynamic-declaration-helpers.ts:L195-216`), so **the tool schema changes when the skill set changes**. That is a cache hazard at session boundaries, not mid-session.
- "JIT context": subdirectory `GEMINI.md` files are appended to the outputs of file tools when those tools touch the directory (`packages/core/src/tools/jit-context.ts:L10-20`; `utils/memoryDiscovery.ts:L512`).
- MCP is eager, with include/exclude filtering (`tools/mcp-client.ts:L2489-2510`; `tools/tool-registry.ts:L564-653`). No tool search.

**Goose.**
- The `extensionmanager` platform extension exposes `search_available_extensions` (a catalogue from config) and `manage_extensions` (enable/disable) (`crates/goose/src/agents/platform_extensions/ext_manager.rs:L68-114, L240-290`).
- Enabling changes the tool list, which is rebuilt every inference (`crates/goose/src/agents/state_machine/inference_preparation.rs:L43-61`).
- "Code mode" hides non-core extension tools behind `list_functions` / `get_function_details` / `execute_javascript`. This is the meta-tool pattern (D) (`crates/goose/src/agents/reply_parts.rs:L184-211`; `platform_extensions/code_execution.rs:L24, L277-310`).
- Tools are sorted by name: "Stable tool ordering is important for multi session prompt caching" (`reply_parts.rs:L208-209`). `cache_control` goes on the system message, the last tool and the tail (`crates/goose-provider-types/src/cache_semantics.rs:L59-103, L156-176`).
- Skills: `load_skill` tool plus a `name - description` list (`crates/goose/src/skills/client.rs:L84-90, L243-263`).
- The older "router" tool-selection strategy appears to have been removed (`documentation/docs/tutorials/rpi.md:L153, L189`). Unverified beyond that doc mention.

**Cline.**
- MCP tools are now native, eagerly registered `AgentTool`s (`sdk/packages/core/src/extensions/mcp/tools.ts:L17-47`).
- A single `skills` tool whose description lists skill names (`sdk/packages/core/src/extensions/tools/definitions.ts:L774-823`).
- Composio meta-tools (`COMPOSIO_SEARCH_TOOLS`, `COMPOSIO_MULTI_EXECUTE_TOOL`) are the lazy path (`sdk/packages/core/src/extensions/composio/composio-meta-tools.ts:L1-29`).
- The older XML-in-system-prompt tool format and `load_mcp_documentation` survive only as enum values (`apps/vscode/src/shared/tools.ts:L19-21`). Medium confidence.

**langgraph-bigtool.**
- `selected_tool_ids` in the state only grows (`langgraph_bigtool/graph.py:L16-22`). `retrieve_tools(query)` does a vector-store search over descriptions, default `limit=2` (`langgraph_bigtool/tools.py:L14-50`; `graph.py:L45-54`).
- Every step calls `llm.bind_tools([retrieve_tools, *selected_tools])` (`graph.py:L85-97`). That mutates `tools` after each retrieval; appending in registry order is my reading. Result message: `"Available tools: …"` (`graph.py:L25-42`).

**Papers (retrieval over tools).**
- RAG-MCP ([arXiv:2505.03275](https://arxiv.org/abs/2505.03275)): over 50% fewer prompt tokens, and tool-selection accuracy of 43.13% vs a 13.62% baseline.
- Toolshed ([arXiv:2410.14594](https://arxiv.org/abs/2410.14594)): a tool knowledge base plus pre-, intra- and post-retrieval RAG fusion; +46/56/47% absolute Recall@5 on ToolE single, ToolE multi and Seal-Tools.
- Neither addresses the KV cache. Harness-side top-k binding per step changes `tools` per step, which is the worst case for caching.

---

## 3. Comparison

"Cache impact" means what happens to the cached prefix when a new tool or skill becomes available mid-session.

| System / mechanism | Where definitions live | When loaded | Cache impact | Requires | Complexity |
|---|---|---|---|---|---|
| Everything up front (baseline; Cline, Gemini CLI and OpenHands for MCP) | `tools` array, all schemas | Session start | Stable while the set is fixed; any change (MCP `list_changed`, enabling an extension) rewrites the very start of the prompt | Any endpoint | Trivial; token cost grows linearly with tool count |
| Agent Skills catalog + file read (Anthropic, Claude Code) | Catalog in system prompt; body via `bash cat` → tool result | Body on demand | Safe if the catalog is frozen per session | Any endpoint and a model with a shell/read tool | Very low |
| Catalog + dedicated `load_skill` tool (opencode `skill`, OpenHands `invoke_skill`, Gemini `activate_skill`, Goose `load_skill`) | Catalog in system prompt (or tool description, Cline); body → tool result | On demand | Safe, unless the tool's schema embeds the skill list (Gemini's `z.enum`) or the catalog is regenerated | Any endpoint | Low |
| Catalog deltas as appended messages (opencode instructions; Anthropic mid-conversation `system`) | Frozen baseline in system prompt + appended `system` / `<system-update>` messages | When the set changes | Safe: prefix untouched | Mid-conversation `system` needs template/provider support; user-role text works everywhere | Medium |
| Codex skills | Catalog in a developer message (2% budget); body read via shell or injected on `$name` | On demand | Safe; catalog changes appended as deltas (flagged) | Responses API only (Codex); the pattern itself is portable | Low |
| Codex MCP `tool_search` (client-executed BM25) + world-state diffs | Deferred namespaces; loaded specs in `tool_search_output`; source list in appended developer message | Model searches | Designed to keep the prefix stable | Responses `tool_search`/`namespace`/`defer_loading` | Medium |
| Anthropic Tool Search + `defer_loading` (incl. Claude Code `ToolSearch`) | All schemas in `tools` (deferred ones excluded from the prefix server-side); `tool_reference` expanded inline | Model searches | Preserved (documented) | Anthropic API, specific models; gateways must forward fields | Low for the client |
| Anthropic `tool_addition` (beta) | Appended `system` message with reference or full definition | Any time | Preserved (documented) | Anthropic API beta header, recent models | Low |
| OpenAI Responses `tool_search` / `additional_tools` / namespaces | Deferred in `tools`; loaded tools "injected at the end of the context window" | Model searches or the app appends | Preserved (documented) | Responses API, `gpt-5.4`+ | Low |
| OpenAI `allowed_tools`, `tool_choice:"none"` | Fixed `tools`; restriction in `tool_choice` | Per request | Tools prefix kept (documented for OpenAI); on SGLang `tool_choice` changes the rendered tools | OpenAI; partial elsewhere | Low |
| Manus masking / prefill | Fixed `tools`; decoding constrained per state | Per step | Preserved | Control of decoding (self-hosted logits processors or prefill); prefix-named tool groups | High |
| Meta-tool dispatch (Goose code mode, opencode Code Mode, Cline Composio) | Small catalog in prompt; schemas as text in tool results; one fixed `execute`/`call_tool` | On demand | Preserved: `tools` never changes | Any endpoint; model must handle a two-step or JS-wrapped protocol; no native schema-constrained decoding for inner calls | Medium (harness validates and dispatches) |
| bigtool / retrieval rebinding (RAG-MCP, Toolshed) | `tools` re-bound per step to retrieved subset | Every retrieval / step | Breaks the prefix at each change (tools render at the top) | Embeddings / vector store | Medium |
| Per-agent subsets (opencode permissions, OpenHands subagents, Gemini plan mode) | `tools` filtered per agent | Session / subagent start | Safe if fixed per session; a mode switch mid-session rewrites the prefix | Any endpoint | Low |
| vLLM `defer_loading` / `tool_addition` (Anthropic-compat endpoint) | Merged into one list for the chat template | Request render | Not preserved: the merged list renders at the top | vLLM | n/a |

---

## 4. Prompt cache: what an OpenAI-compatible, possibly self-hosted backend actually needs

**How matching works.**
- vLLM and SGLang reuse the **longest common token prefix** of the rendered prompt. vLLM works at full-block granularity with chained hashes; SGLang uses a radix tree (§2.8). Hosted OpenAI does the same at the rendered-prefix level (§2.7).
- The prompt is rendered by the model's chat template. For the families used most with tool calling (ChatML: Qwen, Hermes), `tools` are printed **inside the first system turn**, right after the system text. Llama 3.1 prints them in the first user message. Either way they sit within the first few hundred tokens.
- Rule: **any byte change in `tools` or in the system prompt invalidates essentially the whole cache**. Only appended messages are cheap.

**Safe to change between steps:**
- appending new messages at the end: assistant turns, `tool` results, user turns;
- `max_tokens`, `temperature` and other sampling parameters. They don't enter the prompt; inferred from the server design, unverified per server.

**Not safe (each one forces re-prefill from the changed token on):**
- adding, removing, reordering or re-describing anything in `tools`, including JSON key order inside schemas, and a skill-name enum that grows;
- editing the system prompt: timestamps, cwd/env listings, a regenerated skill catalog;
- changing `tool_choice` on SGLang (`"none"` or a named tool alters which tools render), and on vLLM with `--exclude-tools-when-tool-choice-none`;
- rewriting or truncating earlier messages. That includes "cleaning" old tool outputs, which is compaction: do it rarely and in batches;
- switching chat template, LoRA adapter or `cache_salt`;
- templates that move the tools block (Mistral renders it before the last user message), or that inject the date (Llama 3.1). These are properties of the model and must be measured.

The match is against **re-rendered** history, not against the tokens the model generated. If the template re-renders the previous assistant turn differently, the miss starts at that turn. For example, a template that strips reasoning from past turns, or a harness that re-serializes `tool_calls.arguments` with different spacing or key order. This is an inference from how prefix matching works, not checked per template. Keep assistant messages byte-for-byte as received; the baseline already appends `tool_call` unchanged.

**Where newly loaded content should go:**
1. **Skill bodies and tool schemas go in the `tool` result of the call that requested them.** Every tool-calling template supports this role. It is chronologically correct, and it is what every surveyed client does (Anthropic file-read skills, opencode `skill`, OpenHands `invoke_skill`, Gemini `activate_skill`). The OpenAI and Anthropic hosted mechanisms do the same thing server-side: "appended at the end", "inline `tool_reference`".
2. **Harness-initiated additions** (keyword triggers, a newly installed skill, an MCP server coming up) are appended. Put them in the next user message's content, as OpenHands `extended_content` and opencode `<system-update>` do. Use a mid-conversation `role:"system"` message only where it's known to render: ChatML templates do, Mistral templates raise, and Anthropic supports it on recent models.
3. **Never mutate `tools` or the system prompt mid-session.** If a newly loaded tool must become a native function, rebuild the frozen prefix (system prompt + `tools`) only at a point where the prefix is being rewritten anyway, which in practice is compaction. opencode advances its instruction epoch exactly there (`projector.ts:L1118-1123`).
4. If you must add to `tools` mid-session, **append at the end** of the array and never remove. The miss is still near-total under ChatML templates, so batch the additions.

**Determinism checklist.**
- Build `tools` once per session, sorted by name (Goose and opencode do).
- Serialize schemas with stable key order.
- No dates in the system prompt.
- Keep the skill catalog sorted and frozen.
- Send a stable `prompt_cache_key` / session affinity when the backend is hosted OpenAI or a multi-replica deployment (Manus: route by session id).

**Make it observable.**
- Log `usage.prompt_tokens_details.cached_tokens / prompt_tokens` per turn.
- Start vLLM with `--enable-prompt-tokens-details`, or SGLang with `--enable-cache-report`. Otherwise the field is absent and the harness should log that it is absent, not report 0% caching.
- A drop in the cached ratio on a step where nothing was compacted is the signature of an accidental prefix mutation.

---

## 5. Recommendation for this harness

Constraints: `/chat/completions` only; any model, including self-hosted; no reliance on provider beta features. Provider-native search (`defer_loading` on Anthropic, `tool_search` on OpenAI Responses) is not available through this interface. On vLLM it is accepted but doesn't help the cache (§2.8), so the design must be client-side.

**Frozen prefix per session.**
- `system` = static instructions plus two sorted catalogs:
  - skills: `name — description`, Agent Skills format, about 50–100 tokens each;
  - deferred tools: `name — one-line description`, grouped by namespace prefix.
- `tools` = a small fixed core, sorted. Suggested: `bash`, `load_skill(name)`, `load_tools(names[])`, `call_tool(name, arguments)`.
- Neither changes until a compaction epoch.

**Skills.**
- Directory scan per the Agent Skills client guide.
- `load_skill` returns `<skill_content name=…>` with the body, the base dir, and a capped resource listing (not the contents) as the tool result.
- Deduplicate: a repeat load returns "already loaded". Tag the result so compaction keeps it.
- File-read activation through `bash cat` costs nothing extra and also works. The dedicated tool adds dedupe, tagging and logging.

**Deferred tools.**
- `load_tools` returns the full JSON schemas as tool-result text.
- `call_tool(name, arguments)` validates `arguments` against the registry schema in the harness and dispatches. Validation errors go back to the model as the tool result, including the schema, so the model can fix the call itself.
- A `call_tool` for a tool that was never loaded can simply run if the arguments validate, and fail with the schema attached if they don't. That makes `load_tools` an optimization, not a required round trip.
- This is the meta-tool pattern used by Goose code mode, opencode Code Mode and Cline/Composio. It is cache-safe on every backend because `tools` never changes.

**Optional promotion at compaction.**
- When the context is compacted, the prefix is rebuilt anyway. At that point, move frequently used deferred tools into native `tools` and refresh the catalogs, so they get native function calling and constrained decoding.
- Cost: zero extra cache misses beyond the one compaction already causes.

**Mid-session catalog changes** (a skill added on disk, etc.): append a delta notice in the next user-turn content, as opencode does ("New skills are available in addition to those previously listed: …"). Don't regenerate `system`.

**Trade-offs and risks.**
- *Meta-tool vs native.* Inner calls lose server-side schema enforcement (vLLM structural tags or strict mode apply only to declared `tools`). Weaker models may handle a nested `arguments` object or a two-step protocol worse than a native function. Harness-side validation with self-correction errors, plus promotion at compaction, mitigates this. Measure success rate against an all-up-front baseline.
- *Catalog budget.* Anthropic reports selection accuracy degrading past 30–50 tools. Claude Code caps its skill listing at 1% of context and drops the least-used descriptions first. With many entries, use a `search_tools(query)` tool (BM25 or regex over name and description, in the style of Anthropic's tool search) instead of listing everything. Keep the 3–5 most-used tools native.
- *Mutating `tools` instead* (bigtool, Goose extension enable) is simpler and gives native calls. The cost is a near-full re-prefill per change under ChatML templates. Acceptable only if loads are rare and early in the session.
- *Keyword auto-injection* (OpenHands) saves the model a decision and is cache-safe when appended to the user message, but it has false positives and only checks user text. Treat it as optional, behind dedupe.
- *Masking* (Manus) is the most cache-friendly and the most accurate, but it needs control over decoding. A generic OpenAI-compatible client doesn't have that, except named or `required` `tool_choice` on vLLM.

**What to measure (for TASK.md's before/after):**
- prompt tokens per step;
- cached-token ratio per step;
- tokens in `tools` + `system` at session start;
- number of `load_*` calls;
- schema-validation errors from `call_tool`;
- task success. Compare against `baseline/agent.py` with every tool loaded up front.

---

## 6. Unverified or inferred

- Per-server confirmation that sampling parameters (`temperature`, `max_tokens`) never affect the prefix cache. This is inferred from the vLLM and SGLang hashing design.
- Chat templates that re-render past assistant turns differently, such as stripping reasoning, and so cause a miss at the previous turn. Inferred from exact-prefix matching; not checked per model.
- Whether self-hosted Chat-Completions servers honour OpenAI's `tool_choice: {"type":"allowed_tools"}`. Not found on vLLM's chat path; not checked on SGLang or llama.cpp.
- The effective vLLM KV block size on a given backend. 64 is the code default; the platform may override it.
- llama.cpp server prefix-cache behaviour. Not researched; it is assumed to be prefix-based like the others.
- OpenHands: MCP `list_changed` mid-conversation rewrites the tools prefix, and condensation loses the message-level cache. Both inferred from code.
- Goose: the router/LLM tool-selection strategy was removed. Based on a doc mention only.
- Cline: the XML tool prompt and `load_mcp_documentation` are no longer live. Medium confidence.
- langgraph-bigtool: tool order after rebinding, and that it breaks caching. Inferred.
- Codex: how the server handles `AdditionalTools` (Responses Lite). This is not visible in the client repo.
- Anthropic engineering-post numbers (token savings, accuracy) are self-reported.
- Paper results (RAG-MCP, Toolshed) come from their abstracts only.
