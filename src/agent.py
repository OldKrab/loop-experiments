"""Coding agent loop: bash + team service tools + skills, loaded up front (fixed) or on demand (dynamic)."""
import argparse, json, os, subprocess, sys, time
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
        # TODO: cap huge outputs (head/tail + byte count) once compaction lands; today they go to the model whole.
        return f"Exit code: {command_result.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s"


class Agent:
    def __init__(self, mode: str, log: RunLog):
        self.mode, self.log = mode, log
        self.skills = skills_mod.discover()
        self.loaded_skills: set[str] = set()
        self.system, self.tools = build_prompt(mode, self.skills)
        self.native = {t["function"]["name"]: t["function"]["parameters"] for t in self.tools}
        # Native non-service tools, all validated against their schema in call_tool.
        self.core = {"bash": run_bash}
        if mode == "dynamic":
            self.core |= {"load_skill": self.load_skill, "load_tools": self.load_tools,
                          "call_tool": lambda name, arguments: self.run_service_tool(name, arguments)}

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

    def record_usage(self, turn: int, data: dict, tool_names: list[str]) -> None:
        usage = data.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        tokens = {"input_tokens": usage.get("prompt_tokens", 0), "cached_input_tokens": cached,
                  "output_tokens": usage.get("completion_tokens", 0)}
        for key, value in tokens.items():
            self.log.totals[key] += value or 0
        finish = data["choices"][0].get("finish_reason")
        self.log.event("turn", turn=turn, finish_reason=finish, tool_calls=tool_names, **tokens)
        print(f"📊 in={tokens['input_tokens']} cached={'n/a' if cached is None else cached} "
              f"out={tokens['output_tokens']} finish={finish}")

    def run(self, user_message: str, max_turns: int) -> str:
        print(f"⚙️  mode={self.mode} model={LLM_MODEL} skills={len(self.skills)} tools={len(self.tools)} "
              f"system_chars={len(self.system)} tools_chars={len(json.dumps(self.tools))}")
        self.log.event("start", mode=self.mode, model=LLM_MODEL, cwd=os.getcwd(), task=user_message,
                       skills=list(self.skills), native_tools=[t["function"]["name"] for t in self.tools],
                       system_chars=len(self.system), tools_chars=len(json.dumps(self.tools)))
        messages: list[dict] = [{"role": "system", "content": self.system}, {"role": "user", "content": user_message}]
        truncations = 0
        for turn in range(1, max_turns + 1):
            print(f"\n{'='*60}\n🔄 Turn {turn}\n{'='*60}")
            data = self.call_llm(messages)
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            tool_calls = msg.get("tool_calls") or []
            self.record_usage(turn, data, [tc["function"]["name"] for tc in tool_calls])
            # Append the assistant message as received: DeepSeek requires reasoning_content back, and
            # re-serializing it differently would break the prompt-cache prefix.
            messages.append(msg)
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
    parser.add_argument("task", nargs="+")
    args = parser.parse_args()
    log = RunLog(args.log)
    agent = Agent(args.loading, log)
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
