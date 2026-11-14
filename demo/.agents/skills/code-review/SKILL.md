---
name: code-review
description: Checklist for reviewing a change or pull request. Use when asked to review code, a diff, or a PR.
---
# Code review checklist

Read the linked issue first so you know what the change is meant to do.

## Correctness
- Does the change fix the root cause, or only the symptom?
- Edge cases: empty inputs, zero, negative amounts, currencies with 0 or 3 decimal places.
- Error handling: are errors raised with a useful message, and are they caught only where they can be handled?

## Tests
- Is there a test that would have caught the bug?
- Were existing tests weakened or deleted? That needs a written justification.

## Design
- Is the change as small as it can be? Unrelated refactors belong in another change.
- Are names clear? Is there duplicated logic that already exists elsewhere?

## Output
Post findings as a list, most severe first. Mark each as `blocker`, `should-fix`, or `nit`. Approve only when there are no blockers.
