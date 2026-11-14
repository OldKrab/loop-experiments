"""Run a demo task N times per loading mode and compaction threshold, in parallel, each on a fresh copy of
its project, and compare tokens and success."""
import argparse, json, os, shutil, statistics, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from check import check, read_log

ROOT = Path(__file__).resolve().parent.parent
# task name -> (project directory, DEMO_SCENARIO for demo_tools, prompt)
TASKS = {
    "short": ("demo", "short",
              "An alert fired on the payments service. Investigate, fix it, and close it out per team process."),
    "long": ("demo-long", "long",
             "Several alerts are firing on the payments service. Investigate each one, fix it, and close it out "
             "per team process."),
    "feature": ("demo-feature", "feature",
                "Work through the open feature tickets in the issue tracker, oldest first, per team process."),
    "feature-xl": ("demo-feature", "feature-xl",
                   "Work through the open feature tickets in the issue tracker, oldest first, per team process."),
}
# USD per 1M tokens: deepseek-flash at peak hours (https://api-docs.deepseek.com/quick_start/pricing, 2026-11-14).
PRICE_UNCACHED, PRICE_CACHED, PRICE_OUTPUT = 0.30, 0.006, 1.20


def cost_usd(row: dict) -> float:
    cached = row.get("cached_input_tokens") or 0
    return ((row.get("input_tokens", 0) - cached) * PRICE_UNCACHED + cached * PRICE_CACHED
            + row.get("output_tokens", 0) * PRICE_OUTPUT) / 1e6


def run_once(task: str, mode: str, compact_at: int, i: int, stamp: str, max_turns: int) -> dict:
    project, scenario, prompt = TASKS[task]
    label = f"{task}-{mode}-c{compact_at}"
    workdir = Path(tempfile.mkdtemp(prefix=f"{label}-{i}-")) / "demo"  # same dir name for both tasks
    shutil.copytree(ROOT / project, workdir)
    log_path = ROOT / "runs" / f"{stamp}-{label}-{i}.jsonl"
    out_path = log_path.with_suffix(".out")
    env = {**os.environ, "DEMO_SCENARIO": scenario,
           "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}"}  # pytest on PATH for bash
    started = time.time()
    with open(out_path, "w") as out:
        proc = subprocess.run([sys.executable, "-u", str(ROOT / "src" / "agent.py"), "--loading", mode,
                               "--log", str(log_path), "--max-turns", str(max_turns),
                               "--compact-at", str(compact_at), prompt],
                              cwd=workdir, stdout=out, stderr=subprocess.STDOUT, env=env)
    events = read_log(log_path) if log_path.exists() else []
    result = check(log_path, workdir) if events else {"success": False, "reason": "no log"}
    end = next((e for e in events if e["type"] == "end"), {})
    start = next((e for e in events if e["type"] == "start"), {})
    turns = [e for e in events if e["type"] == "turn"]
    row = {"task": task, "mode": mode, "compact_at": compact_at, "run": i, "success": result["success"],
           "turns": len(turns), "exit": proc.returncode, "seconds": round(time.time() - started),
           "prefix_chars": start.get("system_chars", 0) + start.get("tools_chars", 0),
           "peak_input": max((e["input_tokens"] for e in turns), default=0),
           **end.get("totals", {}), "cost_usd": round(cost_usd(end.get("totals", {})), 5), "compactions": end.get("counts", {}).get("compaction", 0),
           "counts": end.get("counts", {}), "checks": result.get("checks"), "status": end.get("status"),
           "log": str(log_path.relative_to(ROOT)), "workdir": str(workdir)}
    print(json.dumps(row), flush=True)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=list(TASKS), default="short")
    parser.add_argument("--modes", default="fixed,dynamic")
    parser.add_argument("-n", type=int, default=3)
    parser.add_argument("-j", "--jobs", type=int, default=6, help="runs in parallel")
    parser.add_argument("--max-turns", type=int, default=150)
    parser.add_argument("--compact-at", default="0", help="comma-separated thresholds in tokens; 0 is off")
    args = parser.parse_args()
    (ROOT / "runs").mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    configs = [(mode, int(c)) for mode in args.modes.split(",") for c in args.compact_at.split(",")]
    jobs = [(args.task, mode, c, i, stamp, args.max_turns) for mode, c in configs for i in range(1, args.n + 1)]
    with ThreadPoolExecutor(args.jobs) as pool:  # each run is its own agent process with its own service state
        rows = list(pool.map(lambda job: run_once(*job), jobs))
    (ROOT / "runs" / f"{stamp}-summary.json").write_text(json.dumps(rows, indent=1))
    print(f"\ntask={args.task}\n{'mode':8} {'compact':>7} {'success':>8} {'turns':>6} {'prefix_chars':>12} "
          f"{'input':>9} {'cached':>9} {'uncached':>9} {'output':>8} {'in/turn':>8} {'peak':>7} {'compacts':>8} {'cost¢':>7}")
    for mode, c in configs:
        rs = [r for r in rows if r["mode"] == mode and r["compact_at"] == c]
        mean = lambda k: round(statistics.mean(r.get(k) or 0 for r in rs))
        per_turn = round(sum(r.get("input_tokens", 0) for r in rs) / max(1, sum(r["turns"] for r in rs)))
        print(f"{mode:8} {c or 'off':>7} {sum(r['success'] for r in rs):>4}/{len(rs):<3} {mean('turns'):>6} "
              f"{mean('prefix_chars'):>12} {mean('input_tokens'):>9} {mean('cached_input_tokens'):>9} "
              f"{mean('input_tokens') - mean('cached_input_tokens'):>9} {mean('output_tokens'):>8} {per_turn:>8} "
              f"{mean('peak_input'):>7} {statistics.mean(r['compactions'] for r in rs):>8.1f} "
              f"{statistics.mean(r['cost_usd'] for r in rs) * 100:>7.3f}")


if __name__ == "__main__":
    main()
