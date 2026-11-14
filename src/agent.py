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
Team procedures. Follow every skill that applies to the task.

{bodies}"""

DYNAMIC_SKILLS = """

## Skills
Team procedures. When a task matches a skill's description, load it with `load_skill` before starting \
and follow it.

{catalog}"""

DYNAMIC_TOOLS = """

## Service tools
These tools are not in your tool list. Load the namespaces the task needs with `load_tools` to get their \
tool schemas, then run a tool with `call_tool(name, arguments)`.

{catalog}"""

BASH_TOOL = {"type": "function", "function": {
    "name": "bash", "description": "Execute a shell command and return the output.",
    "parameters": {"type": "object", "properties": {
        "command": {"type": "string", "description": "The bash command to execute."}}, "required": ["command"]}}}

LOAD_SKILL_TOOL = {"type": "function", "function": {
    "name": "load_skill", "description": "Load the full instructions of a skill listed under 'Skills'.",
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "Skill name from the catalog."}}, "required": ["name"]}}}

LOAD_TOOLS_TOOL = {"type": "function", "function": {
    "name": "load_tools",
    "description": "Return the JSON schemas of every tool in the given namespaces, to use with call_tool.",
    "parameters": {"type": "object", "properties": {
        "namespaces": {"type": "array", "items": {"type": "string", "enum": sorted(demo_tools.NAMESPACES)},
                       "description": "Namespaces from the 'Service tools' list."}}, "required": ["namespaces"]}}}

CALL_TOOL_TOOL = {"type": "function", "function": {
    "name": "call_tool", "description": "Run a service tool by its full name, e.g. 'issues_get'.",
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "Full tool name from the 'Service tools' list."},
        "arguments": {"type": "object", "description": "Arguments matching the tool's schema from load_tools."}},
        "required": ["name", "arguments"]}}}


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

    def load_skill(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            return f"Error: unknown skill '{name}'. Available: {', '.join(self.skills) or 'none'}"
        self.log.count("load_skill")
        self.log.event("load_skill", name=name, repeat=name in self.loaded_skills)
        if name in self.loaded_skills:
            return f"Skill '{name}' is already loaded earlier in this conversation; follow it from there."
        self.loaded_skills.add(name)
        return skills_mod.render(skill)

    def load_tools(self, namespaces: list[str]) -> str:
        unknown = [ns for ns in namespaces if ns not in demo_tools.NAMESPACES]
        if unknown:
            return f"Error: unknown namespaces {unknown}. Available: {', '.join(demo_tools.NAMESPACES)}"
        self.log.count("load_tools")
        self.log.event("load_tools", namespaces=namespaces)
        schemas = [schema["function"] for name, (schema, _) in demo_tools.TOOLS.items()
                   if name.split("_")[0] in namespaces]
        return json.dumps(schemas, indent=1) + "\n\nRun these with call_tool(name, arguments)."

    def run_service_tool(self, name: str, arguments) -> str:
        if name not in demo_tools.TOOLS:
            return f"Error: unknown tool '{name}'. Available: {', '.join(demo_tools.TOOLS)}"
        schema, func = demo_tools.TOOLS[name]
        if isinstance(arguments, str):  # some models send the nested arguments as a JSON string
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError as e:
                return f"Error: arguments for {name} are not valid JSON ({e})"
        try:
            jsonschema.validate(arguments, schema["function"]["parameters"])
        except jsonschema.ValidationError as e:
            self.log.count("validation_error")
            self.log.event("validation_error", tool=name, error=e.message)
            return (f"Error: invalid arguments for {name}: {e.message}\n"
                    f"Schema: {json.dumps(schema['function']['parameters'])}")
        result = func(**arguments)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=1)

    def call_tool(self, name: str, arguments: dict) -> str:
        try:
            if name == "bash":
                return run_bash(**arguments)
            if self.mode == "dynamic" and name == "load_skill":
                return self.load_skill(**arguments)
            if self.mode == "dynamic" and name == "load_tools":
                return self.load_tools(**arguments)
            if self.mode == "dynamic" and name == "call_tool":
                return self.run_service_tool(arguments.get("name", ""), arguments.get("arguments", {}))
            return self.run_service_tool(name, arguments)  # native call (fixed mode, or any registered name)
        except Exception as e:
            self.log.count("tool_error")
            self.log.event("tool_error", tool=name, error=f"{type(e).__name__}: {e}")
            return f"Error calling {name}: {e}"

    def call_llm(self, messages: list[dict]) -> dict:
        payload = {"model": LLM_MODEL, "messages": messages, "tools": self.tools, "tool_choice": "auto",
                   "temperature": 0.1, "max_tokens": MAX_TOKENS}
        response = requests.post(f"{LLM_BASE_URL}/chat/completions", json=payload, headers=LLM_HEADERS, timeout=600)
        if not response.ok:
            raise RuntimeError(f"LLM HTTP {response.status_code}: {response.text[:2000]}")
        return response.json()

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
        if finish == "length":
            print("⚠️  output hit max_tokens; the turn was truncated")

    def run(self, user_message: str, max_turns: int) -> str:
        print(f"⚙️  mode={self.mode} model={LLM_MODEL} skills={len(self.skills)} tools={len(self.tools)} "
              f"system_chars={len(self.system)} tools_chars={len(json.dumps(self.tools))}")
        self.log.event("start", mode=self.mode, model=LLM_MODEL, cwd=os.getcwd(), task=user_message,
                       skills=list(self.skills), native_tools=[t["function"]["name"] for t in self.tools],
                       system_chars=len(self.system), tools_chars=len(json.dumps(self.tools)))
        messages: list[dict] = [{"role": "system", "content": self.system}, {"role": "user", "content": user_message}]
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
            if not tool_calls:
                print("✅ Agent finished")
                return "finished"
            for tool_call in tool_calls:
                function = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"] or "{}")
                    print(f"🔧 Tool: {function}({json.dumps(arguments, ensure_ascii=False)})")
                    result = self.call_tool(function, arguments)
                except json.JSONDecodeError as e:
                    self.log.count("bad_tool_json")
                    result = f"Error: tool call arguments are not valid JSON ({e}); resend the call."
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
