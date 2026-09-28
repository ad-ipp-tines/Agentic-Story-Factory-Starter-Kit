# `[OPS] 16 · Apply approved alert rule (sub)` — the only place the monitor's approvals reach production

**Slug:** `ops-apply-alert-rule` · **Mode badge:** `sub-story` · **Tier:** `ops` · **Owner:** ops (CODEOWNERS: security-platform) · **Descends from:** —

> **Not built yet.** This folder holds the contract, the meta file and the manifest entry so lint, review, ship and drift see this story before `[OPS] 10 · Monitor story health and credits` ships — the monitor must not ship before this story is built, reviewed and shipped itself. Build it in the dev team with `/tines-build-story ops-apply-alert-rule "Build [OPS] 16 · Apply approved alert rule (sub) from stories/ops-apply-alert-rule/README.md"` (the owner sets `TINES_ALLOW_OPS_BUILD=1`), record its dev id in `../_manifest.yaml`, then `/tines-export ops-apply-alert-rule`. The calling side is `apply` (#64) in `../ops-story-health-monitor/story.json`.

## Purpose

Called by the sweep's `apply` action **only** after the Slack request signature (#77/#78), the approver check against `ops_responders` (#55) and, for a two-approver kind, the second approval (#63). It holds `tines_api_ops` — the Editor-role team key that exists in no other story — and applies exactly one approved proposal. It is never a tool on an AI Agent action and never exposed by the Mode 4 server.

| `kind` / `type` | What it does | Endpoint(s) | Approvers |
|---|---|---|---|
| `alert_rule` · `recipient` | add the recipient (live vs draft semantics VERIFY #7) | `POST /api/v1/stories/{id}/recipients` | one verified |
| `alert_rule` · `monitor_*` | set the flag **into a draft**, then open a change request titled `monitor-<finding_id>` for a person to approve in Tines | `PUT /api/v1/actions/{id}` or `PUT /api/v1/stories/{id}` → `POST /api/v1/stories/{id}/change_request` | one verified, then the change-request approver |
| `alert_rule` · `token_threshold` / `credit_budget` | no API: a Case task (if Cases is entitled) or a Record + thread [BY HAND] | — | one verified |
| `credit_action` (`pause_agent` / `reroute_provider`) | **only as a draft + change request, never a live write**; the action key that pauses an agent is VERIFY — until confirmed, a Record + thread [BY HAND] | as `monitor_*` | **two different** (`ops_responders.two_required_for`), then the change-request approver |
| `disable` | **never** `POST /api/v1/stories/{id}/disable` from here: it dispatches `rollback.yml` (`workflow_dispatch`, inputs `slug`, `target`, `reason` with the finding id and the two approvers' roles, `emergency: true`) with the credential `github_dispatch`, so the break-glass job's two GitHub reviewers (neither the dispatcher) approve, the job disables the named story and appends `policies/break-glass-log.md` in the same run. A story with no slug in `../_manifest.yaml` cannot be dispatched: the result is `refused` and the thread says a person runs the break-glass path by hand. The dispatch endpoint and the token permission it needs are **VERIFY** | via `rollback.yml` only | **two different**, then two break-glass reviewers |

Never-touch targets are refused before any call (the `ops_limits.never_touch` mirror, including `^\[OPS\]`). The sweep's `mark_applied` writes the `ops_alert_proposals` status from this story's result.

## Mode badge

`sub-story` — Send to Story enabled (team access, Timeout Duration 25 s); called by the sweep's `apply` action only.

## Entry and expected input

| Entry | Action name | Expected fields | Notes |
|---|---|---|---|
| Send to Story (a Webhook entry, team access) | named at build | `proposal_id`, `kind`, `story_id`, `action_id`, `type`, `value`, `approver`, `finding_id` (the payload `apply` #64 sends) | `normalize` wraps every field in `DEFAULT()`; a guard Trigger refuses a never-touch target or an unknown `kind` before any write |

## Output — the `result` shape

```json
{ "status": "applied | refused | error", "change_request_id": "string or null — the monitor-<finding_id> request, when one was opened", "message": "one sentence a person can act on" }
```

## Failure shape

```json
{ "status": "error", "error_category": "auth | rate_limit | upstream_5xx | validation | permission | unknown", "retryable": true, "message": "human-readable, no secrets, no raw bodies" }
```

## Credentials and Resources — by reference

| Kind | Name | Type | `allowed_hosts` | Workbench access | Must exist in |
|---|---|---|---|---|---|
| Credential | `tines_api_ops` | Text — Editor-role team API key; lives in this story only | the tenant host | off | the prod ops team (and the dev team for the build) |
| Credential | `github_dispatch` | GitHub token (scope stated in `../ops-story-health-monitor/story.meta.yaml`) | `api.github.com` | off | the ops team |
| Resource | `ops_limits` | JSON — the `never_touch` mirror | — | — | dev team + prod team |

## Monitoring

- Story-level **Notify when any action fails**: on, set by `ship.yml`; recipients from `../_manifest.yaml`.
- Event-driven: no own watchdog. Event retention raised to 30 days [BY HAND]; `locked: true` in prod; never-touch by the `^\[OPS\]` name pattern — it changes only through its own change request.

## Verify in your tenant before presenting

- Whether `POST /api/v1/stories/{id}/recipients` with a draft waits for promotion or applies live — **VERIFY #7**.
- The action key that pauses an AI Agent action or reroutes its provider — **VERIFY**; until confirmed, `credit_action` is a Record + thread [BY HAND].
- The GitHub endpoint and the token permission that dispatch `rollback.yml`, and the `github_dispatch` scope — **VERIFY**.
- Whether a Send to Story sub-story counts as a flow — **VERIFY #13**.
- Every VERIFY item still open in `../../docs/VERIFY.md` is a sentence you cannot say as fact.
