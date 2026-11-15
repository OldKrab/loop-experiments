"""Mock internal services for the demo: issue tracker, CI, docs wiki, metrics, deploys.

Their state lives only in this process, so the model can reach it through these tools and
not through bash. Each tool is a plain function plus a hand-written schema, registered in TOOLS.
`ci_run_pipeline` is the one real tool: it runs pytest in the agent's working directory.
The seed data depends on the scenario in DEMO_SCENARIO: `short` (project demo/),
`feature` or `feature-xl` (demo-feature/, 4 or 10 tickets).
"""
import copy
import os
import subprocess
import sys

# ---------------------------------------------------------------- seed data

FAILING_LOG = """\
$ python -m pytest -q
..FF.FF......                                                            [100%]
=================================== FAILURES ===================================
_______________________________ test_usd_to_jpy ________________________________
    def test_usd_to_jpy():
>       assert convert(1_000, "USD", "JPY") == 1_495  # $10.00 -> ¥1495
E       AssertionError: assert 149500 == 1495
tests/test_currency.py:16: AssertionError
_______________________________ test_jpy_to_usd ________________________________
>       assert convert(1_495, "JPY", "USD") == 1_000  # ¥1495 -> $10.00
E       AssertionError: assert 10 == 1000
tests/test_currency.py:20: AssertionError
_______________________________ test_usd_to_kwd ________________________________
>       assert convert(10_000, "USD", "KWD") == 30_700  # $100.00 -> 30.700 KWD
E       AssertionError: assert 3070 == 30700
tests/test_currency.py:24: AssertionError
_________________________ test_jpy_invoice_from_usd_prices _____________________
>       assert invoice_total(lines, "JPY") == 2_990
E       AssertionError: assert 299000 == 2990
tests/test_invoice.py:11: AssertionError
=========================== short test summary info ============================
FAILED tests/test_currency.py::test_usd_to_jpy
FAILED tests/test_currency.py::test_jpy_to_usd
FAILED tests/test_currency.py::test_usd_to_kwd
FAILED tests/test_currency.py::test_format_amount
FAILED tests/test_invoice.py::test_jpy_invoice_from_usd_prices
5 failed, 8 passed in 0.04s
"""

SEED = {
    "issues": {
        "PAY-139": {"key": "PAY-139", "title": "Refund emails show amount without currency symbol",
                    "status": "open", "assignee": None, "labels": ["ux", "email"], "priority": "low",
                    "description": "Customers see '10.50' instead of '$10.50' in refund confirmation emails.",
                    "comments": []},
        "PAY-140": {"key": "PAY-140", "title": "Add GBP to supported billing currencies",
                    "status": "in_progress", "assignee": "maria", "labels": ["feature"], "priority": "medium",
                    "description": "Finance wants GBP invoices for UK customers from next quarter.",
                    "comments": [{"author": "maria", "body": "Rates table updated, invoices next."}]},
        "PAY-141": {"key": "PAY-141", "title": "Flaky test_refund_capped_at_remaining on CI",
                    "status": "closed", "assignee": "lee", "labels": ["ci", "flaky"], "priority": "low",
                    "description": "Failed twice last week, could not reproduce.",
                    "comments": [{"author": "lee", "body": "Not reproducible after runner upgrade, closing."}]},
        "PAY-142": {"key": "PAY-142", "title": "JPY and KWD invoice amounts are wrong after currency refactor",
                    "status": "open", "assignee": None, "labels": ["bug", "incident"], "priority": "high",
                    "description": ("Alert ALERT-7 (invoice reconciliation mismatch) started firing after the "
                                    "currency module refactor merged. JPY invoices look ~100x too large. "
                                    "CI run 4812 on main is red since that merge. Owner: whoever is on call."),
                    "comments": []},
    },
    "ci_runs": {
        "4810": {"id": "4810", "branch": "main", "status": "passed", "commit": "a1c9e2f",
                 "summary": "13 passed", "log": "$ python -m pytest -q\n13 passed in 0.03s\n",
                 "artifacts": {"junit.xml": "<testsuite tests=\"13\" failures=\"0\"/>"}},
        "4811": {"id": "4811", "branch": "feature/gbp", "status": "passed", "commit": "77d01b3",
                 "summary": "13 passed", "log": "$ python -m pytest -q\n13 passed in 0.03s\n",
                 "artifacts": {"junit.xml": "<testsuite tests=\"13\" failures=\"0\"/>"}},
        "4812": {"id": "4812", "branch": "main", "status": "failed", "commit": "e5b4410",
                 "summary": "5 failed, 8 passed (commit e5b4410: 'Refactor currency helpers')",
                 "log": FAILING_LOG,
                 "artifacts": {"junit.xml": "<testsuite tests=\"13\" failures=\"5\"/>"}},
    },
    "alerts": {
        "ALERT-5": {"id": "ALERT-5", "service": "payments", "state": "acked", "severity": "warning",
                    "title": "Checkout latency p95 above 800ms", "metric": "payments.checkout_latency_p95_ms",
                    "issue": None, "ack_note": "Upstream bank API slowness, resolved itself."},
        "ALERT-7": {"id": "ALERT-7", "service": "payments", "state": "firing", "severity": "critical",
                    "title": "Invoice reconciliation mismatch (JPY, KWD)",
                    "metric": "payments.invoice_mismatch_total",
                    "description": ("Invoice totals disagree with the ledger for non-2-decimal currencies. "
                                    "Started right after deploy of commit e5b4410."),
                    "issue": "PAY-142", "ack_note": None},
        "ALERT-8": {"id": "ALERT-8", "service": "search", "state": "firing", "severity": "warning",
                    "title": "Search index lag above 5 minutes", "metric": "search.index_lag_s",
                    "issue": None, "ack_note": None},
    },
    "metrics": {
        "payments.invoice_mismatch_total": [0, 0, 0, 14, 37, 52, 61],
        "payments.checkout_latency_p95_ms": [410, 420, 905, 430, 415, 422, 418],
        "payments.refunds_per_hour": [12, 9, 15, 11, 13, 10, 12],
        "search.index_lag_s": [40, 55, 120, 310, 330, 360, 340],
    },
    "docs": {
        "oncall-handbook": "# On-call handbook\nAcknowledge critical alerts within 15 minutes. "
                           "Every critical alert must link to an issue. Team procedures live in the agent skills.",
        "payments-architecture": "# Payments architecture\nModules: currency (conversion, minor units), "
                                 "invoice (totals), refunds. Amounts are always integers in minor units.",
        "release-process": "# Release process\nDeploy to staging, run smoke tests, promote to production "
                           "with deploy_promote. Roll back with deploy_rollback.",
        "glossary": "# Glossary\nMinor unit: the smallest unit of a currency (cent, yen, fils).",
    },
    "deploys": {
        "payments": {"staging": "e5b4410", "production": "e5b4410", "history": ["a1c9e2f", "e5b4410"]},
        "search": {"staging": "9f0c1aa", "production": "9f0c1aa", "history": ["9f0c1aa"]},
    },
}



def _feature_seed(xl: bool = False) -> dict:
    """Four (ten with `xl`) detailed feature tickets for marshmallow 4.4.0 (project demo-feature/), done one after
    another, plus
    distractors: a ticket someone else owns, a docs ticket, and an unrelated alert. Ticket texts live in
    demo_data/feature/<key>.md; check.py runs the hidden tests in demo_data/feature/acceptance/."""
    seed = copy.deepcopy(SEED)
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data", "feature")
    text = lambda key: open(os.path.join(data, f"{key}.md")).read()
    ticket = lambda key, title, **kw: {"key": key, "title": title, "status": "open", "assignee": None,
                                       "labels": ["feature"], "priority": "medium", "description": text(key),
                                       "comments": [], **kw}
    seed["issues"] = {
        "MM-198": {"key": "MM-198", "title": "Docs: quickstart still passes the removed `context` argument",
                   "status": "open", "assignee": None, "labels": ["docs"], "priority": "low",
                   "description": "The quickstart page shows `Schema(context=...)`, removed in 4.0.", "comments": []},
        "MM-199": {"key": "MM-199", "title": "Flaky test_registry test on Python 3.13", "status": "closed",
                   "assignee": "lee", "labels": ["ci", "flaky"], "priority": "low",
                   "description": "Failed once on CI, not reproducible.", "comments": []},
        "MM-200": {"key": "MM-200", "title": "Add fields.Color (hex colours)", "status": "in_progress",
                   "assignee": "dana", "labels": ["feature"], "priority": "medium",
                   "description": "Accept '#rgb' and '#rrggbb', normalise to lower case. Dana is on it.",
                   "comments": [{"author": "dana", "body": "Half done on my branch."}]},
        "MM-201": ticket("MM-201", "Add validate.Unique validator"),
        "MM-202": ticket("MM-202", "Add fields.Duration for ISO 8601 durations"),
        "MM-203": ticket("MM-203", "Add Meta.key_case option for camelCase and kebab-case keys"),
        "MM-204": ticket("MM-204", "Add fields.Union for values with several possible shapes"),
    }
    if xl:
        seed["issues"] |= {
            "MM-205": ticket("MM-205", "Add Meta.dump_skip_none option"),
            "MM-206": ticket("MM-206", "Add validate.Each for per-item validation"),
            "MM-207": ticket("MM-207", "Add fields.Interval for start/end pairs"),
            "MM-208": ticket("MM-208", "Add Meta.strip_strings option"),
            "MM-209": ticket("MM-209", "Add fields.Masked for partially hidden values"),
            "MM-210": ticket("MM-210", "Add Schema.json_schema() export"),
        }
    seed["ci_runs"] = {
        "5119": {"id": "5119", "branch": "main", "status": "passed", "commit": "a38b7f6",
                 "summary": "1192 passed (tag 4.4.0)", "log": "$ python -m pytest -q\n1192 passed in 1.5s\n",
                 "artifacts": {"junit.xml": "<testsuite tests=\"1192\" failures=\"0\"/>"}},
        "5120": {"id": "5120", "branch": "dana/color-field", "status": "failed", "commit": "c0ffee1",
                 "summary": "1 failed, 1195 passed", "log": "$ python -m pytest -q\nFAILED tests/test_fields.py::"
                 "TestColor::test_short_form\n1 failed, 1195 passed in 1.6s\n",
                 "artifacts": {"junit.xml": "<testsuite tests=\"1196\" failures=\"1\"/>"}},
    }
    seed["alerts"] = {k: v for k, v in seed["alerts"].items() if v["service"] != "payments" or k == "ALERT-5"}
    seed["docs"] = {
        "oncall-handbook": seed["docs"]["oncall-handbook"],
        "release-process": seed["docs"]["release-process"],
        "marshmallow-overview": "# marshmallow\nObject serialization library: schemas declare fields, `dump` "
                                "serializes, `load` validates and deserializes. Source in src/marshmallow/.",
    }
    return seed


SEEDS = {"short": SEED, "feature": _feature_seed(), "feature-xl": _feature_seed(xl=True)}
# (alert, linked issue) pairs that check.py judges; None: the agent must create the issue.
INCIDENTS = {"short": [("ALERT-7", "PAY-142")], "feature": [], "feature-xl": []}
# Feature tickets that check.py judges with hidden acceptance tests, and tickets the agent must leave alone.
TICKETS = {"feature": [f"MM-{n}" for n in range(201, 205)], "feature-xl": [f"MM-{n}" for n in range(201, 211)]}
UNTOUCHED = {"feature": ["MM-200"], "feature-xl": ["MM-200"]}
SCENARIO = os.environ.get("DEMO_SCENARIO", "short")  # set by bench.py; must match the project in the cwd
if SCENARIO not in SEEDS:
    raise SystemExit(f"DEMO_SCENARIO={SCENARIO!r}: expected one of {', '.join(SEEDS)}")
STATE = copy.deepcopy(SEEDS[SCENARIO])
_next_run_id = max(int(r) for r in STATE["ci_runs"]) + 1


def _get(collection: str, key: str) -> dict:
    item = STATE[collection].get(key)
    if item is None:
        raise ValueError(f"{collection} '{key}' not found; existing: {', '.join(sorted(STATE[collection]))}")
    return item


# ---------------------------------------------------------------- issues

ISSUE_STATUSES = ["open", "in_progress", "resolved", "closed"]


def issues_search(query: str = "", status: str | None = None) -> list[dict]:
    q = query.lower()
    return [{k: i[k] for k in ("key", "title", "status", "assignee", "priority")}
            for i in STATE["issues"].values()
            if (not q or q in (i["title"] + i["description"]).lower()) and (not status or i["status"] == status)]


def issues_get(key: str) -> dict:
    return _get("issues", key)


def issues_create(title: str, description: str, labels: list[str] | None = None, priority: str = "medium") -> dict:
    project = next(iter(STATE["issues"])).split("-")[0]  # one project per scenario: PAY or MM
    key = f"{project}-{max(int(k.split('-')[1]) for k in STATE['issues']) + 1}"
    STATE["issues"][key] = {"key": key, "title": title, "status": "open", "assignee": None,
                            "labels": labels or [], "priority": priority, "description": description,
                            "comments": []}
    return {"key": key}


def issues_comment(key: str, body: str) -> dict:
    _get("issues", key)["comments"].append({"author": "agent", "body": body})
    return {"key": key, "comments": len(STATE["issues"][key]["comments"])}


def issues_transition(key: str, status: str) -> dict:
    issue = _get("issues", key)
    if status not in ISSUE_STATUSES:
        raise ValueError(f"unknown status '{status}'; allowed: {', '.join(ISSUE_STATUSES)}")
    old, issue["status"] = issue["status"], status
    return {"key": key, "from": old, "to": status}


def issues_assign(key: str, assignee: str) -> dict:
    _get("issues", key)["assignee"] = assignee
    return {"key": key, "assignee": assignee}


# ---------------------------------------------------------------- ci

def ci_list_runs(branch: str | None = None, status: str | None = None, limit: int = 10) -> list[dict]:
    runs = [{k: r[k] for k in ("id", "branch", "status", "commit", "summary")}
            for r in STATE["ci_runs"].values()
            if (not branch or r["branch"] == branch) and (not status or r["status"] == status)]
    return sorted(runs, key=lambda r: int(r["id"]), reverse=True)[:limit]


def ci_get_log(run_id: str) -> str:
    return _get("ci_runs", str(run_id))["log"]


def ci_run_pipeline(branch: str = "main") -> dict:
    """Runs the test suite in the agent's working directory and records the run."""
    global _next_run_id
    run_id, _next_run_id = str(_next_run_id), _next_run_id + 1
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                              cwd=os.getcwd(), capture_output=True, text=True, timeout=300)
        log, ok = proc.stdout + proc.stderr, proc.returncode == 0
    except subprocess.TimeoutExpired:
        log, ok = "pipeline timed out after 300s", False
    lines = log.strip().splitlines()
    summary = lines[-1] if lines else "no output"
    STATE["ci_runs"][run_id] = {"id": run_id, "branch": branch, "status": "passed" if ok else "failed",
                                "commit": "workdir", "summary": summary, "log": log,
                                "artifacts": {"junit.xml": f"<!-- {summary} -->"}}
    return {"id": run_id, "status": STATE["ci_runs"][run_id]["status"], "summary": summary}


def ci_get_artifact(run_id: str, name: str) -> str:
    artifacts = _get("ci_runs", str(run_id))["artifacts"]
    if name not in artifacts:
        raise ValueError(f"run {run_id} has no artifact '{name}'; available: {', '.join(artifacts)}")
    return artifacts[name]


# ---------------------------------------------------------------- docs

def docs_search(query: str) -> list[dict]:
    q = query.lower()
    return [{"slug": slug, "snippet": text[:120]} for slug, text in STATE["docs"].items()
            if q in (slug + text).lower()]


def docs_get_page(slug: str) -> str:
    return _get("docs", slug)


def docs_update_page(slug: str, content: str) -> dict:
    created = slug not in STATE["docs"]
    STATE["docs"][slug] = content
    return {"slug": slug, "created": created}


# ---------------------------------------------------------------- metrics

def metrics_list_alerts(state: str | None = None, service: str | None = None) -> list[dict]:
    return [{k: a[k] for k in ("id", "service", "state", "severity", "title")}
            for a in STATE["alerts"].values()
            if (not state or a["state"] == state) and (not service or a["service"] == service)]


def metrics_get_alert(alert_id: str) -> dict:
    return _get("alerts", alert_id)


def metrics_ack_alert(alert_id: str, note: str) -> dict:
    alert = _get("alerts", alert_id)
    alert["state"], alert["ack_note"] = "acked", note
    return {"id": alert_id, "state": "acked"}


def metrics_query(metric: str, window: str = "7h") -> dict:
    series = STATE["metrics"].get(metric)
    if series is None:
        raise ValueError(f"unknown metric '{metric}'; available: {', '.join(sorted(STATE['metrics']))}")
    return {"metric": metric, "window": window, "step": "1h", "values": series}


# ---------------------------------------------------------------- deploy

def deploy_status(service: str) -> dict:
    d = _get("deploys", service)
    return {"service": service, "staging": d["staging"], "production": d["production"]}


def deploy_promote(service: str, from_env: str = "staging", to_env: str = "production") -> dict:
    d = _get("deploys", service)
    d[to_env] = d[from_env]
    return {"service": service, to_env: d[to_env]}


def deploy_rollback(service: str, env: str, version: str) -> dict:
    d = _get("deploys", service)
    if version not in d["history"]:
        raise ValueError(f"version '{version}' was never deployed; history: {', '.join(d['history'])}")
    d[env] = version
    return {"service": service, env: version}


# ---------------------------------------------------------------- schemas

NAMESPACES = {
    "issues": "Issue tracker: find, read, comment on, assign, and change status of issues",
    "ci": "CI system: list pipeline runs, read logs and artifacts, run the test pipeline on the working copy",
    "docs": "Team docs wiki: search, read, and edit pages",
    "metrics": "Monitoring: list, inspect, and acknowledge alerts; query metric time series",
    "deploy": "Deployments: see deployed versions per environment, promote, roll back",
}


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required, "additionalProperties": False}}}


_KEY = {"type": "string", "description": "Issue key, e.g. 'PAY-123'. Keys are case-sensitive."}
_RUN = {"type": "string", "description": "CI run id as shown by ci_list_runs, e.g. '4812'."}
_ALERT = {"type": "string", "description": "Alert id as shown by metrics_list_alerts, e.g. 'ALERT-3'."}
_SERVICE = {"type": "string", "description": "Service name, e.g. 'payments' or 'search'."}
_ENV = {"type": "string", "enum": ["staging", "production"], "description": "Target environment."}

SCHEMAS = [
    _schema("issues_search",
            "Search issues in the PAY project by free text over title and description. Returns a compact list "
            "(key, title, status, assignee, priority) without descriptions or comments; use issues_get for the "
            "full record. An empty query lists every issue. Combine with status to narrow the list.",
            {"query": {"type": "string", "description": "Case-insensitive substring to match. May be empty."},
             "status": {"type": "string", "enum": ISSUE_STATUSES, "description": "Only return issues in this status."}},
            []),
    _schema("issues_get",
            "Fetch one issue with its full description, labels, priority, assignee, status, and the complete "
            "comment thread in chronological order. Descriptions often reference alerts and CI runs by id.",
            {"key": _KEY}, ["key"]),
    _schema("issues_create",
            "Create a new issue in the PAY project. The issue starts in status 'open' and unassigned. Returns the "
            "new key. Do not create duplicates: search first. Use for follow-up work discovered during a task.",
            {"title": {"type": "string", "description": "One-line summary, imperative or descriptive."},
             "description": {"type": "string", "description": "Context, impact, and links to alerts or runs."},
             "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels such as 'bug', 'ci'."},
             "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Defaults to medium."}},
            ["title", "description"]),
    _schema("issues_comment",
            "Append a comment to an issue's thread, authored by you. Comments are permanent and visible to the "
            "whole team; markdown is supported. Returns the new comment count.",
            {"key": _KEY, "body": {"type": "string", "description": "Comment text (markdown)."}},
            ["key", "body"]),
    _schema("issues_transition",
            "Move an issue to another workflow status. Statuses: open (not started), in_progress (someone is "
            "working on it), resolved (fix done and verified), closed (no further action). Returns old and new status.",
            {"key": _KEY, "status": {"type": "string", "enum": ISSUE_STATUSES, "description": "New status."}},
            ["key", "status"]),
    _schema("issues_assign",
            "Set the assignee of an issue. Use your own handle 'agent' when you take an issue yourself.",
            {"key": _KEY, "assignee": {"type": "string", "description": "User handle, e.g. 'agent' or 'maria'."}},
            ["key", "assignee"]),
    _schema("ci_list_runs",
            "List CI pipeline runs, newest first, with id, branch, status (passed/failed), commit, and a one-line "
            "summary. Use ci_get_log for the full output of a run.",
            {"branch": {"type": "string", "description": "Only runs for this branch, e.g. 'main'."},
             "status": {"type": "string", "enum": ["passed", "failed"], "description": "Only runs with this result."},
             "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Maximum runs to return (default 10)."}},
            []),
    _schema("ci_get_log",
            "Return the full console log of a CI run, including the test command and every failure with its "
            "traceback. Logs of failed runs are the fastest way to find which tests broke and why.",
            {"run_id": _RUN}, ["run_id"]),
    _schema("ci_run_pipeline",
            "Run the CI test pipeline (pytest) on the current working copy and record it as a new CI run. Returns "
            "the new run id, its status, and the summary line. Only a run recorded here counts as CI evidence; "
            "local test runs through the shell do not. Takes a few seconds.",
            {"branch": {"type": "string", "description": "Branch label to record for the run (default 'main')."}},
            []),
    _schema("ci_get_artifact",
            "Download a named artifact of a CI run, such as 'junit.xml'. Returns the artifact's text content.",
            {"run_id": _RUN, "name": {"type": "string", "description": "Artifact file name, e.g. 'junit.xml'."}},
            ["run_id", "name"]),
    _schema("docs_search",
            "Search the team docs wiki by substring over page slug and text. Returns slugs with a short snippet.",
            {"query": {"type": "string", "description": "Case-insensitive substring."}}, ["query"]),
    _schema("docs_get_page",
            "Read a docs wiki page in full (markdown).",
            {"slug": {"type": "string", "description": "Page slug as returned by docs_search, e.g. 'oncall-handbook'."}},
            ["slug"]),
    _schema("docs_update_page",
            "Create or overwrite a docs wiki page with new markdown content. Overwrites the whole page: read it "
            "first and send the complete new text. Returns whether the page was newly created.",
            {"slug": {"type": "string", "description": "Page slug, lowercase with dashes."},
             "content": {"type": "string", "description": "Full markdown content of the page."}},
            ["slug", "content"]),
    _schema("metrics_list_alerts",
            "List monitoring alerts with id, service, state (firing or acked), severity, and title. Use "
            "metrics_get_alert for the description, metric, and linked issue.",
            {"state": {"type": "string", "enum": ["firing", "acked"], "description": "Only alerts in this state."},
             "service": _SERVICE},
            []),
    _schema("metrics_get_alert",
            "Fetch one alert in full: description, severity, the metric it watches, the linked issue key (if any), "
            "and the acknowledgement note.",
            {"alert_id": _ALERT}, ["alert_id"]),
    _schema("metrics_ack_alert",
            "Acknowledge an alert so it stops paging. The note is shown to the on-call team and must explain why "
            "it is safe to acknowledge (e.g. the fix and the issue tracking it).",
            {"alert_id": _ALERT, "note": {"type": "string", "description": "Acknowledgement note."}},
            ["alert_id", "note"]),
    _schema("metrics_query",
            "Return an hourly time series for a metric over a window. Useful to see when a problem started.",
            {"metric": {"type": "string", "description": "Metric name, e.g. 'payments.invoice_mismatch_total'."},
             "window": {"type": "string", "description": "Look-back window such as '7h' (informational)."}},
            ["metric"]),
    _schema("deploy_status",
            "Show which commit is deployed to staging and production for a service.",
            {"service": _SERVICE}, ["service"]),
    _schema("deploy_promote",
            "Promote the version running in one environment to another (default staging -> production). "
            "Affects real traffic in production; only do this when a release procedure says so.",
            {"service": _SERVICE, "from_env": _ENV, "to_env": _ENV}, ["service"]),
    _schema("deploy_rollback",
            "Roll an environment back to a previously deployed version from the service's deploy history.",
            {"service": _SERVICE, "env": _ENV,
             "version": {"type": "string", "description": "Commit from the deploy history, e.g. 'a1c9e2f'."}},
            ["service", "env", "version"]),
]

_FUNCS = {f.__name__: f for f in [
    issues_search, issues_get, issues_create, issues_comment, issues_transition, issues_assign,
    ci_list_runs, ci_get_log, ci_run_pipeline, ci_get_artifact,
    docs_search, docs_get_page, docs_update_page,
    metrics_list_alerts, metrics_get_alert, metrics_ack_alert, metrics_query,
    deploy_status, deploy_promote, deploy_rollback]}

# name -> (schema, function); namespace = the name's prefix before the first underscore.
TOOLS = {s["function"]["name"]: (s, _FUNCS[s["function"]["name"]]) for s in SCHEMAS}
assert set(TOOLS) == set(_FUNCS) and {n.split("_")[0] for n in TOOLS} == set(NAMESPACES)
