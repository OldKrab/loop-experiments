"""Judge one run: tests pass in its workdir, and the service state shows the hotfix process was followed."""
import json, re, subprocess, sys
from pathlib import Path

import demo_tools


def read_log(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def check(log_path: Path, workdir: Path) -> dict:
    events = read_log(log_path)
    end = next((e for e in events if e["type"] == "end"), None)
    if end is None:
        return {"success": False, "reason": "no end event in log (agent crashed or was killed)"}
    state = end["state"]
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=workdir,
                           capture_output=True, text=True)
    new_green = {rid for rid, r in state["ci_runs"].items()
                 if rid not in demo_tools.SEED["ci_runs"] and r["status"] == "passed"}
    issue, alert = state["issues"]["PAY-142"], state["alerts"]["ALERT-7"]
    comments = [c["body"] for c in issue["comments"] if c["author"] == "agent"]
    checks = {
        "agent_finished": end["status"] == "finished",
        "tests_pass": tests.returncode == 0,
        "ci_green_run": bool(new_green),
        "issue_resolved": issue["status"] == "resolved",
        # One comment must carry both, as the hotfix-workflow skill's comment format requires.
        "closing_comment": any("root cause" in c.lower() and any(re.search(rf"\b{rid}\b", c) for rid in new_green)
                               for c in comments),
        "alert_acked_with_issue": alert["state"] == "acked" and "PAY-142" in (alert["ack_note"] or ""),
    }
    return {"success": all(checks.values()), "checks": checks, "status": end["status"], "error": end["error"]}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: check.py RUN.jsonl WORKDIR")
    print(json.dumps(check(Path(sys.argv[1]), Path(sys.argv[2])), indent=1))
