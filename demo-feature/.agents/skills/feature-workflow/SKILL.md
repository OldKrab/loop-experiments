---
name: feature-workflow
description: Team process for implementing a feature ticket end to end - taking the ticket, implementing it to spec with tests, proving it in CI, and closing it out. Use whenever you work on tickets labelled `feature`.
---
# Feature workflow

Service tools used: `issues_search`, `issues_get`, `issues_assign`, `issues_transition`, `issues_comment`, `ci_run_pipeline`, `ci_get_log`.

## 0. Pick tickets
- Take only open, unassigned tickets labelled `feature`, oldest key first. Leave tickets that someone else owns or that are already in progress alone.
- Work on **one ticket at a time**: finish step 5 for a ticket before you start the next one.

## 1. Take ownership
- Read the full ticket with `issues_get`.
- Assign it to yourself (`issues_assign`, assignee `agent`) and move it to `in_progress`.

## 2. Implement to spec
- Load the codebase skill for the project first (for marshmallow: `marshmallow-conventions`).
- Implement exactly the API in the ticket: names, signatures, error messages and behaviour. Do not change existing public behaviour.
- If the ticket is ambiguous, choose the reading closest to the existing code, and say so in the closing comment.

## 3. Test
- Add tests for every example and edge case in the ticket, in the test module the ticket names.
- Run the whole suite locally (`python -m pytest -q`). It must pass.

## 4. Prove it in CI
- Run `ci_run_pipeline` for this ticket. Only a recorded CI run counts as evidence; a local pytest run does not.
- If it fails, read the log with `ci_get_log`, fix, and run it again.

## 5. Close out
Post one comment on the ticket (`issues_comment`) in exactly this format:

```
Summary: <one sentence>
Changes: <files changed and what changed>
Tests: <test functions added>
CI: run <run id> passed
```

Then move the ticket to `resolved`; the reporter closes it after review.
