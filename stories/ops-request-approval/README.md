# `[OPS] 17 · Request approval (sub)` — one implementation of the approval request, for the sweep and the Mode 4 server

**Slug:** `ops-request-approval` · **Mode badge:** `sub-story` · **Tier:** `ops` · **Owner:** ops (CODEOWNERS: security-platform) · **Descends from:** —

> **Not built yet.** This folder holds the contract, the meta file and the manifest entry so lint, review, ship and drift see this story before `[OPS] 10 · Monitor story health and credits` and `[OPS] 20 · Ops tools (MCP server)` ship. Build it in the dev team with `/tines-build-story ops-request-approval "Build [OPS] 17 · Request approval (sub) from stories/ops-request-approval/README.md"` (the owner sets `TINES_ALLOW_OPS_BUILD=1`), record its dev id in `../_manifest.yaml`, then `/tines-export ops-request-approval`. Callers: `request_approval` (#48) in `../ops-story-health-monitor/story.json`, and `request_alert_rule` / `request_disable` in `../ops-tools-server/`.

## Purpose

Turns a proposal into a pending approval and nothing more — it changes no story. It re-checks on its own side that the target is not on the never-touch mirror (`ops_limits.never_touch`, including `^\[OPS\]`) and that proposals today are under `max_proposals_per_day`; returns the pending request on the same target instead of a second one (so a retried call creates no duplicate); writes an `ops_alert_proposals` row (`status: pending`, `requester`, `expires_at` = now + `proposal_expiry_hours`); and posts Block Kit approval buttons to `ops_routing._approvals` with the credential `slack_bot`. A person clicks; the sweep verifies the Slack signature and the approver; only then does `[OPS] 16 · Apply approved alert rule (sub)` act.

## Mode badge

`sub-story` — Send to Story enabled (team access, Timeout Duration 25 s); called by the sweep's `request_approval` action (never by its agent) and by the Mode 4 request tools, whose `kind` and `requester` are fixed on the tool (VERIFY E10).

## Entry and expected input

| Entry | Action name | Expected fields | Notes |
|---|---|---|---|
| Send to Story (a Webhook entry, team access) | named at build | `kind` (`alert_rule` · `disable` · `credit_action` · `proposal_pr`), `story_id`, `action_id` (or null), `type`, `value`, `rationale`, `requester` (`ops-story-health-monitor`, or `META.headers.email` for a Mode 4 caller), `finding_id` (null from Mode 4) | `normalize` wraps every field in `DEFAULT()`; guard Triggers refuse a never-touch target and a request over the daily cap before any write |

## Output — the `result` shape

```json
{ "approval_id": "string — an opaque name, never a capability", "status": "pending", "approvers": "array — the roles that may approve this kind", "expires_at": "ISO 8601" }
```

A refusal is the standard error object with `error_category: "policy"` and `retryable: false`.

## Failure shape

```json
{ "status": "error", "error_category": "auth | rate_limit | upstream_5xx | validation | permission | unknown", "retryable": true, "message": "human-readable, no secrets, no raw bodies" }
```

## Credentials and Resources — by reference

| Kind | Name | Type | `allowed_hosts` | Workbench access | Must exist in |
|---|---|---|---|---|---|
| Credential | `slack_bot` | Slack bot token | the Slack API host | off | dev team + prod team |
| Resource | `ops_limits` | JSON — `never_touch`, `max_proposals_per_day`, `proposal_expiry_hours` | — | — | dev team + prod team |
| Resource | `ops_routing` | JSON — `_approvals` channel | — | — | dev team + prod team |
| Resource | `ops_responders` | JSON — who may approve which kind; `two_required_for` | — | — | dev team + prod team |
| Record type | `ops_alert_proposals` | fields in `../ops-story-health-monitor/records/record-types.md` | — | — | created [BY HAND] |

## Monitoring

- Story-level **Notify when any action fails**: on, set by `ship.yml`; recipients from `../_manifest.yaml`.
- Event-driven: no own watchdog. Event retention raised to 30 days [BY HAND]; `locked: true` in prod; never-touch by the `^\[OPS\]` name pattern.

## Verify in your tenant before presenting

- Fixed, formula-valued inputs (`kind`, `requester: =META.headers.email`) on the Mode 4 request tools — **VERIFY E10**; the fallback is a Custom tool per request tool (`../ops-tools-server/README.md`).
- Creating Record types (`ops_alert_proposals`) through `/mcp` — **VERIFY #26**; create them [BY HAND].
- Whether a Send to Story sub-story counts as a flow — **VERIFY #13**.
- Every VERIFY item still open in `../../docs/VERIFY.md` is a sentence you cannot say as fact.
