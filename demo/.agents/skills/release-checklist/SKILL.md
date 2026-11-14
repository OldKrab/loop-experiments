---
name: release-checklist
description: Steps for releasing a service to production - verifying staging, promoting, monitoring, and rolling back. Use when asked to release, deploy, promote, or roll back a service.
---
# Release checklist

Load the `deploy`, `ci`, and `metrics` service tools.

1. Confirm the latest CI run on `main` passed (`ci_list_runs`, branch `main`). Never release a red build.
2. Check what is deployed (`deploy_status`). Staging must run the commit you intend to release.
3. Check alerts for the service (`metrics_list_alerts`). Do not release while a critical alert is firing, unless the release is the fix.
4. Promote staging to production (`deploy_promote`).
5. Watch the service's key metrics for the next hour (`metrics_query`). For payments: `payments.invoice_mismatch_total` must not grow, and `payments.checkout_latency_p95_ms` must stay below 800.
6. If a metric regresses, roll back immediately (`deploy_rollback` to the previous version from the deploy history) and open an issue.
7. Post a short release note on the docs page `releases` (`docs_update_page`): date, service, commit, and linked issues.

Releases happen Monday to Thursday only. Never release on Friday.
