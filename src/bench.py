"""Run the demo task N times per loading mode on fresh copies of demo/ and compare tokens and success."""
import argparse, json, os, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

from check import check, read_log

ROOT = Path(__file__).resolve().parent.parent
TASK = "An alert fired on the payments service. Investigate, fix it, and close it out per team process."


def run_once(mode: str, i: int, stamp: str, max_turns: int) -> dict:
    workdir = Path(tempfile.mkdtemp(prefix=f"demo-{mode}-{i}-")) / "demo"
    shutil.copytree(ROOT / "demo", workdir)
    log_path = ROOT / "runs" / f"{stamp}-{mode}-{i}.jsonl"
    out_path = log_path.with_suffix(".out")
    env = {**os.environ, "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}"}  # pytest on PATH for bash
    started = time.time()
    with open(out_path, "w") as out:
        proc = subprocess.run([sys.executable, "-u", str(ROOT / "src" / "agent.py"), "--loading", mode,
                               "--log", str(log_path), "--max-turns", str(max_turns), TASK],
                              cwd=workdir, stdout=out, stderr=subprocess.STDOUT, env=env)
    result = check(log_path, workdir) if log_path.exists() else {"success": False, "reason": "no log"}
    end = next((e for e in read_log(log_path) if e["type"] == "end"), {}) if log_path.exists() else {}
    turns = sum(1 for e in read_log(log_path) if e["type"] == "turn") if log_path.exists() else 0
    start = next((e for e in read_log(log_path) if e["type"] == "start"), {}) if log_path.exists() else {}
    row = {"mode": mode, "run": i, "success": result["success"], "turns": turns, "exit": proc.returncode,
           "seconds": round(time.time() - started), "prefix_chars": start.get("system_chars", 0) + start.get("tools_chars", 0),
           **end.get("totals", {}), "counts": end.get("counts", {}), "checks": result.get("checks"),
           "log": str(log_path.relative_to(ROOT)), "workdir": str(workdir)}
    print(json.dumps(row), flush=True)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", default="fixed,dynamic")
    parser.add_argument("-n", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=60)
    args = parser.parse_args()
    (ROOT / "runs").mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    rows = [run_once(mode, i, stamp, args.max_turns) for mode in args.modes.split(",") for i in range(1, args.n + 1)]
    (ROOT / "runs" / f"{stamp}-summary.json").write_text(json.dumps(rows, indent=1))
    print(f"\n{'mode':8} {'success':>8} {'turns':>6} {'prefix_chars':>12} {'input':>9} {'cached':>9} {'uncached':>9} {'output':>8} {'in/turn':>8}")
    for mode in args.modes.split(","):
        rs = [r for r in rows if r["mode"] == mode]
        mean = lambda k: round(statistics.mean(r.get(k, 0) for r in rs))
        print(f"{mode:8} {sum(r['success'] for r in rs):>4}/{len(rs):<3} {mean('turns'):>6} {mean('prefix_chars'):>12} "
              f"{mean('input_tokens'):>9} {mean('cached_input_tokens'):>9} "
              f"{mean('input_tokens') - mean('cached_input_tokens'):>9} {mean('output_tokens'):>8} {round(sum(r.get('input_tokens', 0) for r in rs) / max(1, sum(r['turns'] for r in rs))):>8}")


if __name__ == "__main__":
    main()
