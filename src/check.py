"""Judge one run: tests pass in its workdir, and the service state shows the team process was followed for every
incident (hotfix) or feature ticket of the run's scenario. Feature tickets are also judged by hidden acceptance
tests, copied into the workdir only after the run (failures are logged to <workdir>/_acceptance/<key>.log)."""
import json, re, shutil, subprocess, sys
from pathlib import Path

import demo_tools

ACCEPTANCE = Path(__file__).resolve().parent / "demo_data" / "feature" / "acceptance"


def read_log(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def scenario_of(events: list[dict]) -> str:
    return next((e.get("scenario", "short") for e in events if e["type"] == "start"), "short")


def check(log_path: Path, workdir: Path) -> dict:
    events = read_log(log_path)
    end = next((e for e in events if e["type"] == "end"), None)
    if end is None:
        return {"success": False, "reason": "no end event in log (agent crashed or was killed)"}
    state, scenario = end["state"], scenario_of(events)
    seed = demo_tools.SEEDS[scenario]
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=workdir,
                           capture_output=True, text=True)
    new_green = {rid for rid, r in state["ci_runs"].items()
                 if rid not in seed["ci_runs"] and r["status"] == "passed"}
    checks = {
        "agent_finished": end["status"] == "finished",
        "tests_pass": tests.returncode == 0,
        "ci_green_run": bool(new_green),
    }
    for alert_id, issue_key in demo_tools.INCIDENTS[scenario]:
        alert = state["alerts"][alert_id]
        note = alert["ack_note"] or ""
        issue = state["issues"].get(issue_key) if issue_key else None
        comments = [c["body"] for c in issue["comments"] if c["author"] == "agent"] if issue else []
        checks |= {
            f"{alert_id}.alert_acked_with_issue": alert["state"] == "acked" and bool(issue) and issue_key in note,
            f"{alert_id}.issue_resolved": bool(issue) and issue["status"] == "resolved",
            # One comment must carry both, as the hotfix-workflow skill's comment format requires.
            f"{alert_id}.closing_comment": any(
                "root cause" in c.lower() and any(re.search(rf"\b{rid}\b", c) for rid in new_green)
                for c in comments),
        }
    cited = []
    for key in demo_tools.TICKETS.get(scenario, []):
        issue = state["issues"][key]
        comments = [c["body"] for c in issue["comments"] if c["author"] == "agent"]
        closing = [c for c in comments if "summary:" in c.lower() and any(re.search(rf"\b{rid}\b", c) for rid in new_green)]
        cited += [next(rid for rid in sorted(new_green) if re.search(rf"\b{rid}\b", closing[-1]))] if closing else []
        # Hidden tests run only after the agent is done, from a directory it never saw.
        (workdir / "_acceptance").mkdir(exist_ok=True)
        test_file = next(ACCEPTANCE.glob(f"test_{key.lower().replace('-', '')}_*.py"))
        shutil.copy(test_file, workdir / "_acceptance" / test_file.name)
        hidden = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                 f"_acceptance/{test_file.name}"], cwd=workdir, capture_output=True, text=True)
        checks |= {f"{key}.acceptance_tests": hidden.returncode == 0,
                   f"{key}.resolved": issue["status"] == "resolved",
                   f"{key}.closing_comment": bool(closing)}
        if hidden.returncode:
            (workdir / "_acceptance" / f"{key}.log").write_text(hidden.stdout + hidden.stderr)
    if demo_tools.TICKETS.get(scenario):
        checks["ci_run_per_ticket"] = len(cited) == len(set(cited)) == len(demo_tools.TICKETS[scenario])
    for key in demo_tools.UNTOUCHED.get(scenario, []):
        checks[f"{key}.untouched"] = state["issues"][key] == seed["issues"][key]
    return {"success": all(checks.values()), "checks": checks, "status": end["status"], "error": end["error"]}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: check.py RUN.jsonl WORKDIR")
    print(json.dumps(check(Path(sys.argv[1]), Path(sys.argv[2])), indent=1))
