---
name: commit-style
description: Git commit message and branch naming conventions. Use when creating commits or branches.
---
# Commit style

## Branches
- `fix/<issue-key>-<short-slug>` for bug fixes, e.g. `fix/PAY-123-refund-rounding`.
- `feature/<short-slug>` for features.

## Messages
- Subject: imperative mood, at most 72 characters, no trailing period. Start with the issue key: `PAY-123: Fix refund rounding for JPY`.
- Blank line, then a body explaining **why** the change is needed and what the root cause was. The diff already shows what changed.
- Wrap the body at 72 characters.
- One logical change per commit. Formatting-only changes go in their own commit.

## Before committing
- Run the test suite.
- Do not commit generated files, secrets, or local configuration.
