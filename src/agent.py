"""Coding agent loop: bash + team service tools + skills, loaded up front (fixed) or on demand (dynamic)."""
import argparse, itertools, json, os, subprocess, sys, tempfile, time
from pathlib import Path

import jsonschema
import requests

import demo_tools
import skills as skills_mod

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8787/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "none")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-flash")
LLM_HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}
MAX_TOKENS = 16384  # reasoning models spend output tokens on thinking; 4096 can truncate a turn
LLM_RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504}  # transient: retried by the harness, never shown to the model
LLM_MAX_RETRIES = 5
MAX_TRUNCATIONS = 2  # consecutive replies cut off by max_tokens before the run gives up
TRUNCATED_NUDGE = "Your previous reply was cut off by the output token limit. Continue where you left off, more concisely."
OUTPUT_CAP, OUTPUT_HEAD, OUTPUT_TAIL = 8000, 3000, 3000  # bash output over the cap keeps head + tail, full text in a file
OUTPUT_DIR = Path(tempfile.gettempdir()) / f"agent-{os.getpid()}"  # outside cwd: never pollutes the project or its tests
CHARS_PER_TOKEN = 4  # estimate for messages not yet counted by the server's usage
COMPACT_TAIL_SHARE = 0.3  # newest messages kept verbatim after compaction, as a share of --compact-at
MAX_COMPACTION_FAILURES = 2  # failed compactions before the run stops trying

COMPACT_PROMPT = """\
Stop working on the task for a moment: the conversation is getting long, and everything above this message \
except the system prompt and the task will be replaced by your summary. Write that summary now, so you can \
continue the task from it alone.

Write it in plain prose, as short as possible while keeping what you will need. It must keep:
- the main objective of the task;
- what you are doing right now and what comes next;
- which skills you loaded and how far along each one you are, so you can load them again;
- exact identifiers you will need later: file paths, issue, alert and CI run ids, commands, error messages;
- approaches that failed, and why.

If an earlier summary is present above, your summary replaces it: carry forward whatever still matters. \
Do not call any tools. Reply with the summary only, under 400 words."""
COMPACT_NUDGE = "\n\nYour previous attempt called a tool or returned nothing. Reply with the summary text only."
CHECKPOINT = """<checkpoint>
Earlier messages were removed to save context. This is your summary of the work so far:

{summary}
</checkpoint>
Continue the task from here. Skill bodies and tool schemas loaded earlier are gone: load again with \
`load_skill` / `load_tools` whatever you still need."""

SYSTEM_PROMPT = """\
You are a coding agent. Your job is to help the user with programming tasks in the current directory.

Besides `bash`, you can use the team's internal services: issue tracker, CI, docs wiki, monitoring, \
and deploys. Their data is reachable only through their tools, never through the shell.

Workflow:
1. Plan what needs to be done.
2. Use the tools to read files, run commands, write code, and work with the team's services.
3. After gathering enough information or completing the task, give your final answer in natural language.
4. To finish, reply with a regular message (no tool call).

Be concise. Explain what you're doing before each command."""

FIXED_SKILLS = """

## Skills
Team procedures. Each skill's description says when to use it. Follow a skill only when its description \
matches the task.

{bodies}"""

DYNAMIC_SKILLS = """

## Skills
Team procedures. Each skill's description says when to use it. When it matches the task, load the skill \
with `load_skill` before anything else and follow it; a skill names the service tools it needs.

{catalog}"""

DYNAMIC_TOOLS = """

## Service tools
These tools are not in your tool list. Load only the tools you need with `load_tools(names)` to get their \
schemas, then run a tool with `call_tool(name, arguments)`.

{catalog}"""

BASH_TOOL = {"type": "function", "function": {
    "name": "bash", "description": "Execute a shell command and return the output.",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string", "description": "The bash command to execute."}}, "required": ["command"],
        "additionalProperties": False}}}

LOAD_SKILL_TOOL = {"type": "function", "function": {
    "name": "load_skill", "description": "Load the full instructions of a skill listed under 'Skills'.",
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "Skill name from the catalog."}}, "required": ["name"],
        "additionalProperties": False}}}

LOAD_TOOLS_TOOL = {"type": "function", "function": {
    "name": "load_tools",
    "description": "Return the JSON schemas of the given service tools, to use with call_tool.",
    "parameters": {"type": "object", "properties": {
        "names": {"type": "array", "items": {"type": "string"},
                  "description": "Full tool names from the 'Service tools' list, e.g. ['issues_get']."}},
        "required": ["names"], "additionalProperties": False}}}

CALL_TOOL_TOOL = {"type": "function", "function": {
    "name": "call_tool", "description": "Run a service tool by its full name, e.g. 'issues_get'.",
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "Full tool name from the 'Service tools' list."},
        "arguments": {"type": "object", "description": "Arguments matching the tool's schema from load_tools."}},
        "required": ["name", "arguments"], "additionalProperties": False}}}


class RunLog:
    """Per-run JSONL event log plus running token totals."""

    def __init__(self, path: Path | None):
        self.file = open(path, "w") if path else None
        self.totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
        self.counts: dict[str, int] = {}

    def event(self, type_: str, **data) -> None:
        if self.file:
            self.file.write(json.dumps({"type": type_, "t": round(time.time(), 3), **data}, ensure_ascii=False) + "\n")
            self.file.flush()

    def count(self, key: str) -> None:
        self.counts[key] = self.counts.get(key, 0) + 1

    def error(self, kind: str, message: str, **data) -> None:
        """Count, log, and print a handled error, so failed runs can be diagnosed from the log."""
        self.count(kind)
        self.event("error", kind=kind, message=message[:1000], **data)
        print(f"⚠️  {kind}: {message[:300]}")


def build_prompt(mode: str, skills: dict) -> tuple[str, list[dict]]:
    """System prompt and tools for the whole session. Both stay byte-identical across turns."""
    if mode == "fixed":
        system = SYSTEM_PROMPT
        if skills:
            system += FIXED_SKILLS.format(bodies="\n\n".join(skills_mod.render(s) for s in skills.values()))
        return system, [BASH_TOOL] + [schema for schema, _ in demo_tools.TOOLS.values()]
    system = SYSTEM_PROMPT
    if skills:
        system += DYNAMIC_SKILLS.format(catalog=skills_mod.catalog(skills))
    tool_catalog = "\n".join(
        f"- {ns}: {desc}. Tools: {', '.join(n for n in demo_tools.TOOLS if n.split('_')[0] == ns)}"
        for ns, desc in demo_tools.NAMESPACES.items())
    system += DYNAMIC_TOOLS.format(catalog=tool_catalog)
    return system, [BASH_TOOL, LOAD_SKILL_TOOL, LOAD_TOOLS_TOOL, CALL_TOOL_TOOL]


def run_bash(command: str) -> str:
    try:
        command_result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        out = command_result.stdout + (f"\nSTDERR:\n{command_result.stderr}" if command_result.stderr else "")
        return f"Exit code: {command_result.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s"


_output_ids = itertools.count(1)


def cap_output(text: str) -> tuple[str, Path | None]:
    """Keep head and tail of an oversized output; the full text goes to a file the model can grep or sed."""
    if len(text) <= OUTPUT_CAP:
        return text, None
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"out-{next(_output_ids)}.txt"
    path.write_text(text)
    omitted = len(text) - OUTPUT_HEAD - OUTPUT_TAIL
    return (f"{text[:OUTPUT_HEAD]}\n[... {omitted} chars omitted; full output ({len(text)} chars): {path}]\n"
            f"{text[-OUTPUT_TAIL:]}"), path


def estimate_tokens(obj) -> int:
    return len(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)) // CHARS_PER_TOKEN


class Agent:
    def __init__(self, mode: str, log: RunLog, compact_at: int = 0):
        self.mode, self.log, self.compact_at = mode, log, compact_at
        self.compaction_failures = 0
        # Exact size of messages[:usage_upto] (tools + system + messages, as the server rendered them), from the
        # last response's usage; None right after a compaction, until the next response reports it.
        self.usage_tokens: int | None = None
        self.usage_upto = 0
        self.skills = skills_mod.discover()
        self.loaded_skills: set[str] = set()
        self.system, self.tools = build_prompt(mode, self.skills)
        self.native = {t["function"]["name"]: t["function"]["parameters"] for t in self.tools}
        # Native non-service tools, all validated against their schema in call_tool.
        self.core = {"bash": self.bash}
        if mode == "dynamic":
            self.core |= {"load_skill": self.load_skill, "load_tools": self.load_tools,
                          "call_tool": lambda name, arguments: self.run_service_tool(name, arguments)}

    def bash(self, command: str) -> str:
        result, path = cap_output(run_bash(command))
        if path:
            self.log.event("output_capped", tool="bash", chars=path.stat().st_size, path=str(path))
        return result

    def fail(self, kind: str, message: str, **data) -> str:
        """Log an error and return it as the tool result, so the model can correct itself."""
        self.log.error(kind, message, **data)
        return message

    def validate(self, name: str, parameters: dict, arguments) -> str | None:
        try:
            jsonschema.validate(arguments, parameters)
            return None
        except jsonschema.ValidationError as e:
            return self.fail("validation_error", f"Error: invalid arguments for {name}: {e.message}\n"
                             f"Schema: {json.dumps(parameters)}", tool=name, arguments=str(arguments)[:500])

    def load_skill(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            return self.fail("unknown_skill", f"Error: unknown skill '{name}'. "
                             f"Available: {', '.join(self.skills) or 'none'}", name=name)
        self.log.count("load_skill")
        self.log.event("load_skill", name=name, repeat=name in self.loaded_skills)
        if name in self.loaded_skills:
            return f"Skill '{name}' is already loaded earlier in this conversation; follow it from there."
        self.loaded_skills.add(name)
        return skills_mod.render(skill)

    def load_tools(self, names: list[str]) -> str:
        unknown = [n for n in names if n not in demo_tools.TOOLS]
        if unknown:
            return self.fail("unknown_tool", f"Error: unknown tools {unknown}. "
                             f"Available: {', '.join(demo_tools.TOOLS)}", names=unknown)
        self.log.count("load_tools")
        self.log.event("load_tools", names=names)
        schemas = [demo_tools.TOOLS[n][0]["function"] for n in dict.fromkeys(names)]
        return json.dumps(schemas, ensure_ascii=False) + "\n\nRun these with call_tool(name, arguments)."

    def run_service_tool(self, name: str, arguments) -> str:
        if name not in demo_tools.TOOLS:
            return self.fail("unknown_tool", f"Error: unknown tool '{name}'. "
                             f"Available: {', '.join(demo_tools.TOOLS)}", tool=name)
        schema, func = demo_tools.TOOLS[name]
        if error := self.validate(name, schema["function"]["parameters"], arguments):
            return error
        try:
            result = func(**arguments)
        except Exception as e:  # domain errors (not found, bad state) go back to the model to correct
            return self.fail("tool_error", f"Error calling {name}: {type(e).__name__}: {e}", tool=name)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=1)

    def call_tool(self, name: str, arguments) -> str:
        try:
            if name not in self.core:
                return self.run_service_tool(name, arguments)  # native call (fixed mode, or any registered name)
            if name == "call_tool" and isinstance(arguments, dict) and isinstance(arguments.get("arguments"), str):
                try:  # some models send the nested arguments as a JSON string
                    arguments = {**arguments, "arguments": json.loads(arguments["arguments"] or "{}")}
                except json.JSONDecodeError as e:
                    return self.fail("bad_tool_json", f"Error: call_tool 'arguments' is not valid JSON ({e}); "
                                     "send it as an object.", tool=name, raw=arguments["arguments"][:500])
            if error := self.validate(name, self.native[name], arguments):
                return error
            return self.core[name](**arguments)
        except Exception as e:
            return self.fail("tool_error", f"Error calling {name}: {type(e).__name__}: {e}", tool=name)

    def call_llm(self, messages: list[dict]) -> dict:
        """POST to the LLM. Transient failures are retried here; anything else stops the run."""
        payload = {"model": LLM_MODEL, "messages": messages, "tools": self.tools, "tool_choice": "auto",
                   "temperature": 0.1, "max_tokens": MAX_TOKENS}
        for attempt in range(LLM_MAX_RETRIES + 1):
            delay = 2 ** attempt
            try:
                response = requests.post(f"{LLM_BASE_URL}/chat/completions", json=payload, headers=LLM_HEADERS,
                                         timeout=600)
            except (requests.ConnectionError, requests.Timeout) as e:
                problem = f"{type(e).__name__}: {e}"
            else:
                if response.ok:
                    data = response.json()
                    if not data.get("choices"):
                        raise RuntimeError(f"LLM response has no choices: {response.text[:2000]}")
                    return data
                problem = f"HTTP {response.status_code}: {response.text[:1000]}"
                if response.status_code not in LLM_RETRY_STATUSES:
                    raise RuntimeError(f"LLM {problem}")
                retry_after = response.headers.get("Retry-After", "")
                delay = int(retry_after) if retry_after.isdigit() else delay
            if attempt == LLM_MAX_RETRIES:
                raise RuntimeError(f"LLM failed after {LLM_MAX_RETRIES} retries: {problem}")
            self.log.error("llm_retry", problem, attempt=attempt + 1, delay_s=min(delay, 60))
            time.sleep(min(delay, 60))

    def add_usage(self, data: dict) -> dict:
        """Add a response's token usage to the run totals (summary calls included) and return it."""
        usage = data.get("usage") or {}
        tokens = {"input_tokens": usage.get("prompt_tokens", 0),
                  "cached_input_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                  "output_tokens": usage.get("completion_tokens", 0)}
        for key, value in tokens.items():
            self.log.totals[key] += value or 0
        return tokens

    def record_usage(self, turn: int, data: dict, tool_names: list[str], estimate: int) -> None:
        tokens = self.add_usage(data)
        cached = tokens["cached_input_tokens"]
        finish = data["choices"][0].get("finish_reason")
        self.log.event("turn", turn=turn, finish_reason=finish, tool_calls=tool_names, estimate=estimate, **tokens)
        print(f"📊 in={tokens['input_tokens']} (est {estimate}) cached={'n/a' if cached is None else cached} "
              f"out={tokens['output_tokens']} finish={finish}")

    def estimate(self, messages: list[dict]) -> int:
        """Context size of the next request: last reported usage plus chars/4 of what was appended since."""
        if self.usage_tokens is None:
            return estimate_tokens(self.tools) + sum(estimate_tokens(m) for m in messages)
        return self.usage_tokens + sum(estimate_tokens(m) for m in messages[self.usage_upto:])

    def summarize(self, messages: list[dict]) -> tuple[str | None, str, dict]:
        """Ask the model for a summary, nudging once. The request is the current history plus one appended
        instruction, with the same tools and parameters, so the server reuses the cached prefix."""
        reason, tokens = "", {}
        for prompt in (COMPACT_PROMPT, COMPACT_PROMPT + COMPACT_NUDGE):
            data = self.call_llm(messages + [{"role": "user", "content": prompt}])
            tokens = self.add_usage(data)
            choice = data["choices"][0]
            summary = (choice["message"].get("content") or "").strip()
            if choice["message"].get("tool_calls"):
                reason = "summary reply called a tool"
            elif not summary:
                reason = "summary reply is empty"
            elif choice.get("finish_reason") == "length":
                reason = "summary reply was cut off by max_tokens"
            else:
                return summary, "", tokens
            self.log.event("compaction_retry", reason=reason, **tokens)
        return None, reason, tokens

    def compact(self, messages: list[dict], before: int) -> list[dict] | None:
        """Replace everything after the task with a summary checkpoint plus a verbatim tail; None on failure."""
        started = time.time()
        print(f"\n🗜️  Compacting: ~{before} tokens >= {self.compact_at}")
        summary, reason, tokens = self.summarize(messages)
        # Tail: the newest messages within budget, starting at an assistant message so no tool result is orphaned.
        # Index 2 onward only: [0] is the system prompt, [1] the task, and an old checkpoint sits at [2].
        budget, tail_start = COMPACT_TAIL_SHARE * self.compact_at, len(messages)
        for i in range(len(messages) - 1, 2, -1):
            if sum(estimate_tokens(m) for m in messages[i:]) > budget:
                break
            if messages[i]["role"] == "assistant":
                tail_start = i
        tail = messages[tail_start:]
        new = None
        if summary:
            new = messages[:2] + [{"role": "user", "content": CHECKPOINT.format(summary=summary)}] + tail
            after = estimate_tokens(self.tools) + sum(estimate_tokens(m) for m in new)
            if after >= self.compact_at:
                reason, new = f"compacted history is still ~{after} tokens, not under {self.compact_at}", None
        info = dict(before=before, threshold=self.compact_at, messages_before=len(messages),
                    tail_messages=len(tail), tail_tokens=sum(estimate_tokens(m) for m in tail),
                    summary_chars=len(summary or ""), seconds=round(time.time() - started, 1),
                    summary_usage=tokens)
        if new is None:
            self.compaction_failures += 1
            self.log.error("compaction_failed", reason, failures=self.compaction_failures, **info)
            if self.compaction_failures >= MAX_COMPACTION_FAILURES:
                print(f"⚠️  {self.compaction_failures} failed compactions: compaction is off for the rest of the run")
            return None
        self.log.count("compaction")
        self.log.event("compaction", after=after, messages_after=len(new), summary=summary, **info)
        print(f"🗜️  ~{before} → ~{after} tokens; kept {len(tail)} tail messages; summary {len(summary)} chars")
        print(f"   {summary[:500]}{'...' if len(summary) > 500 else ''}")
        # Loaded skills are gone with the history; the summary names them so the model can load them again.
        self.loaded_skills.clear()
        self.usage_tokens, self.usage_upto = None, 0
        return new

    def run(self, user_message: str, max_turns: int) -> str:
        print(f"⚙️  mode={self.mode} model={LLM_MODEL} skills={len(self.skills)} tools={len(self.tools)} "
              f"system_chars={len(self.system)} tools_chars={len(json.dumps(self.tools))} "
              f"compact_at={self.compact_at or 'off'}")
        self.log.event("start", mode=self.mode, model=LLM_MODEL, cwd=os.getcwd(), task=user_message,
                       scenario=demo_tools.SCENARIO,
                       compact_at=self.compact_at,
                       skills=list(self.skills), native_tools=[t["function"]["name"] for t in self.tools],
                       system_chars=len(self.system), tools_chars=len(json.dumps(self.tools)))
        messages: list[dict] = [{"role": "system", "content": self.system}, {"role": "user", "content": user_message}]
        truncations = 0
        for turn in range(1, max_turns + 1):
            print(f"\n{'='*60}\n🔄 Turn {turn}\n{'='*60}")
            estimate = self.estimate(messages)
            if self.compact_at and estimate >= self.compact_at and self.compaction_failures < MAX_COMPACTION_FAILURES:
                # TODO: also compact and retry once on a context-length HTTP 400; the demo task never overflows.
                if compacted := self.compact(messages, estimate):
                    messages = compacted
                    estimate = self.estimate(messages)
            data = self.call_llm(messages)
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            tool_calls = msg.get("tool_calls") or []
            self.record_usage(turn, data, [tc["function"]["name"] for tc in tool_calls], estimate)
            # Append the assistant message as received: DeepSeek requires reasoning_content back, and
            # re-serializing it differently would break the prompt-cache prefix.
            messages.append(msg)
            usage = data.get("usage") or {}
            if usage.get("prompt_tokens"):
                self.usage_tokens = usage["prompt_tokens"] + usage.get("completion_tokens", 0)
                self.usage_upto = len(messages)
            if content:
                print(f"\n🤖 {content}")
            if data["choices"][0].get("finish_reason") == "length" and not tool_calls:
                # A cut-off reply is not a final answer: ask the model to continue instead of finishing.
                truncations += 1
                self.log.error("truncated", f"reply hit max_tokens={MAX_TOKENS} ({truncations} in a row)", turn=turn)
                if truncations > MAX_TRUNCATIONS:
                    print("❌ Replies keep hitting the output limit. Stopping.")
                    return "truncated"
                messages.append({"role": "user", "content": TRUNCATED_NUDGE})
                continue
            truncations = 0
            if not tool_calls:
                print("✅ Agent finished")
                return "finished"
            for tool_call in tool_calls:
                function = tool_call["function"]["name"]
                raw = tool_call["function"]["arguments"] or "{}"
                try:
                    arguments = json.loads(raw)
                    print(f"🔧 Tool: {function}({json.dumps(arguments, ensure_ascii=False)})")
                    result = self.call_tool(function, arguments)
                except json.JSONDecodeError as e:  # often a tool call cut off by max_tokens
                    result = self.fail("bad_tool_json", f"Error: tool call arguments are not valid JSON ({e}); "
                                       "resend the call.", tool=function, raw=raw[:500])
                print(f"   → {result[:500]}{'...' if len(result) > 500 else ''}")
                messages.append({"role": "tool", "tool_call_id": tool_call["id"], "content": result})
        print(f"\n⚠️  Max turns ({max_turns}) reached. Stopping.")
        return "max_turns"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loading", choices=["fixed", "dynamic"], default="dynamic")
    parser.add_argument("--log", type=Path, help="write a JSONL event log of the run here")
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--compact-at", type=int, default=0,
                        help="summarize the history when the context reaches this many tokens (0: off)")
    parser.add_argument("task", nargs="+")
    args = parser.parse_args()
    log = RunLog(args.log)
    agent = Agent(args.loading, log, args.compact_at)
    status, error = "error", None
    try:
        status = agent.run(" ".join(args.task), args.max_turns)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        print(f"❌ {error}", file=sys.stderr)
        raise
    finally:
        log.event("end", status=status, error=error, totals=log.totals, counts=log.counts,
                  state=demo_tools.STATE)
        print(f"\n📊 totals {json.dumps(log.totals)} counts {json.dumps(log.counts)}")


if __name__ == "__main__":
    main()
