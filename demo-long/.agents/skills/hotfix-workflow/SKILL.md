---
name: hotfix-workflow
description: Team process for fixing a production bug or a firing alert end to end - taking the issue, fixing, proving it in CI, and closing out the issue and alert. Use whenever an alert fires or a bug issue needs a fix.
---
# Hotfix workflow

Service tools used: `metrics_get_alert`, `metrics_ack_alert`, `issues_get`, `issues_create`, `issues_assign`, `issues_transition`, `issues_comment`, `ci_list_runs`, `ci_get_log`, `ci_run_pipeline`.

## 1. Take ownership
- Find the issue linked to the alert (`metrics_get_alert` shows it). If none exists, create one with `issues_create`, labels `bug` and `incident`.
- Assign it to yourself (`issues_assign`, assignee `agent`) and move it to `in_progress`.

## 2. Find the cause
- Read the failing CI run's log (`ci_get_log`); the issue or `ci_list_runs` tells you which run.
- Reproduce locally with the test suite before changing code.
- Find the root cause, not just the symptom. Check the domain skill for the area (e.g. `payments-domain`).

## 3. Fix
- Make the smallest change that fixes the root cause. Do not weaken or delete tests to make them pass.
- If a test itself is wrong, say so explicitly in the issue comment.

## 4. Prove it in CI
- Run `ci_run_pipeline`. Only a recorded CI run counts as evidence; a local pytest run does not.
- If it fails, go back to step 2. Repeat until the run passes.

## 5. Close out
Post one comment on the issue (`issues_comment`) in exactly this format:

```
Root cause: <one or two sentences>
Fix: <files changed and what changed>
CI: run <run id> passed
```

Then:
- Move the issue to `resolved` (not `closed`; the reporter closes it after verifying).
- Acknowledge the alert with `metrics_ack_alert`. The note must name the issue key and the CI run id, e.g. `Fixed in PAY-123, CI run 4900 green`.

Do not deploy as part of a hotfix; releases follow the `release-checklist` skill.
