---
name: incident-postmortem
description: How to write a blameless postmortem after a production incident. Use only when explicitly asked to write a postmortem or incident report.
---
# Incident postmortem

Postmortems are written within 5 working days of a critical incident and stored on the docs wiki as `postmortem-<issue-key>` (service tools: `docs_get_page`, `docs_update_page`, `issues_get`, `issues_create`, `metrics_get_alert`, `metrics_query`).

## Sections
1. **Summary**: two or three sentences: what broke, for whom, and for how long.
2. **Impact**: affected customers, money, and requests, with numbers from `metrics_query`.
3. **Timeline**: UTC timestamps from first symptom to resolution: alert fired, acknowledged, fix merged, verified.
4. **Root cause**: the technical cause, and why our safeguards (tests, review, alerts) did not catch it earlier.
5. **What went well / what went badly.**
6. **Action items**: each one an issue (`issues_create`) with an owner and a priority.

## Tone
Blameless: describe systems and decisions, not people. Write "the refactor removed the per-currency exponent", not "X broke it".
