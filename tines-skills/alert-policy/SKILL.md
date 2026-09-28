---
name: alert-policy
description: States which monitoring options, recipients and thresholds each tier of Tines story must carry and how each threshold is derived from baseline data, so alert proposals and Workbench answers about monitoring match the repository policy. Used when deciding what monitoring a story needs, filling an alert_rule_proposal, or explaining why an alert fired or did not.
license: Proprietary
compatibility: Tines AI Agent action (Task mode) and Workbench presets
metadata:
  owner: ops
  source: "AGENTS.md section 6; policies/cost-ceilings.yml; stories/_manifest.yaml"
  version: "1"
---

# Alert policy

This is the monitoring policy of the repository that owns this tenant's stories, stated so that an agent or a person inside Tines gives the same answer the repository would. It describes **what is set, by whom, and how each number is derived**. It grants nobody the right to set it: in `prod` every monitoring change is a proposal a named approver applies through a change request; in `dev` the ops sweep applies recipients and monitor flags itself so builders can see the behaviour.

## 1. The monitoring options, in the platform's terms

| Option | Where | What it does | Repository name |
|---|---|---|---|
| **Notify when any action fails** (story level) | story settings; `PUT /api/v1/stories/{id}` | one notification per failing action to the story's recipients | `monitor_failures` |
| **Notify if no events emitted** (per action) | action settings; `PUT /api/v1/actions/{id}` | pages when an action emits nothing for N seconds — the watchdog | `monitor_no_events_emitted` (seconds) |
| **Notify on every event** (per action; the exact UI label is VERIFY) | action settings | one notification per event — for rare, important actions only | `monitor_all_events` |
| **Recipients** (story level) | `POST` / `DELETE /api/v1/stories/{id}/recipients` | an email address or a webhook URL that receives the story's notifications | `recipients` |
| **Token-usage alert** (per AI Agent action) | the action's Status tab | Daily / Weekly / Monthly / All-time thresholds; Notify, or Disable action | `ai.agents[].token_alert` — **by hand, no API** |
| **AI credit usage alert** (tenant / unallocated / per team) | Admin → AI | email, in-app or webhook when a share of the allocation is used; defaults 80 % and 100 % (VERIFY #10) | `policies/cost-ceilings.yml: tenant.alert_pct` — **by hand, no API** |
| **Event-limit alert** (tenant) | tenant settings | fires as the event allocation is consumed; at the limit the platform stops stories, so the 80 % alert is the actionable one | routed to the ops router |
| **Change-control team webhooks** | team settings | created / cancelled / approved / rejected / pushed | routed to the ops router |

Monitoring notifications come only from a story running **LIVE**; a story in TEST mode is not monitored. A notification is one event per failing action per window, never one per log line; an HTTP Request action notifies on its final retry only. A handled failure (the failure path ran) may still notify — VERIFY #24 — so the router dedupes and the triage step reads the run shape.

## 2. Recipients — the only addresses

Every story's recipients come from `stories/_manifest.yaml: environments.<env>.recipients` and are set by `ship.yml` on the change-control draft, never typed by hand:

| Environment | Recipients |
|---|---|
| `dev` | the ops router webhook (`${OPS_ROUTER_URL}`) |
| `prod` | the ops router webhook **and** the ops email distribution list (`${OPS_EMAIL_DL}`) |
| the three `ops-*` stories | the email distribution list and a **second** Slack channel — never the router they feed, so the monitor is monitored by something other than itself |

Rules: a person's address is never a recipient (people change; the list does not); the router URL carries a secret and lives in the environment, so a proposal names it as `${OPS_ROUTER_URL}`, never as a literal; a story with recipients but `monitor_failures` off is a coverage gap, and so is a story with `monitor_failures` on and no recipients.

## 3. What each tier must carry

`tier` lives in `story.meta.yaml` and `stories/_manifest.yaml`.

| Tier | `monitor_failures` | watchdog | `monitor_all_events` | recipients | token alert per agent | credit budget line | `keep_events_for` | change control |
|---|---|---|---|---|---|---|---|---|
| `production` | **on** | **on** every scheduled or ingress action, at ≈ 2× the interval | off (opt in per action, with the reason in the story README) | manifest | required | required (`policies/cost-ceilings.yml`) | ≥ 30 days | required; "Require approval for all changes" |
| `ops` (`[OPS] 01 / 10 / 20`) | on | on; the sweep's own schedule action at **1,800 s** | off | DL + second channel | required | required | raised above the default | required; `locked: true` |
| `internal` | on | recommended | off | manifest | required if it has an agent | required if it has an agent | default | on; a lighter review path is acceptable |
| `seed` (the Seeds folder) | off | off | off | none | — | — | default | off; never demoed, never monitored, never a tool |

`lint.yml` and the reviewer enforce the `production` row (`monitoring_required_for_prod`); the sweep detects drift from it (`coverage_gap`) every 15 minutes and fixes it in `dev` only.

## 4. How each number is derived — never picked

Thresholds come from baseline data the daily sweep stores in `ops_baselines`; the agent proposes them, a person applies them.

| Threshold | Rule | Source rows |
|---|---|---|
| **watchdog** `monitor_no_events_emitted` | `watchdog_multiplier` (2) × the p95 inter-event interval of the entry or scheduled action; never below 2× the schedule interval on a scheduled story; the sweep's own is fixed at 1,800 s | the story's events and runs list, stored daily |
| **error threshold** per window (a pre-filter rule, not a platform option) | max(3, 3 × the median count of level-4 error logs per window) | `ops_baselines.error_logs` |
| **per-story daily credit budget** | p95 of the last 7 days' `credits_used` × 1.5, proposed into `ops_limits.credit_budget_daily.per_story` | `ops_credit_ledger` |
| **per-agent token alert** | Notify at ≈ p95 daily tokens × 1.5; Disable action at 2 × Notify; period Daily | the agent's event `meta` over 7 days |
| **overlap** (a pre-filter rule) | run `max_duration_s` ≥ `overlap_ratio` (0.8) × the schedule interval | `ops_get_recent_runs` |
| **recipient proposals** | any newly published story without the router among its recipients | `ops_get_live_activity` |

A number without its rows is not a proposal. With fewer than 7 days of baseline, propose nothing numeric; say the baseline is incomplete.

## 5. Filling `alert_rule_proposal`

| `type` | `value` format | `action_id` | Who applies it, and how |
|---|---|---|---|
| `monitor_failures` | `"true"` | null | dev: the sweep (`PUT /api/v1/stories/{id}`); prod: approval → the apply sub-story into a draft → change request `monitor-<finding_id>` |
| `monitor_no_events_emitted` | seconds, as a string (`"7200"`) | the entry or scheduled action | dev: the sweep (`PUT /api/v1/actions/{id}`); prod: as above (whether this needs a draft on a change-controlled story is VERIFY #7) |
| `monitor_all_events` | `"true"` | the action | prod only, by approval; rare — say why in `rationale` |
| `recipient` | `"${OPS_ROUTER_URL}"` or `"${OPS_EMAIL_DL}"` | null | dev: the sweep (`POST /api/v1/stories/{id}/recipients`); prod: approval (live-vs-draft semantics VERIFY #7) |
| `token_threshold` | `"notify=<tokens>,disable=<tokens>,period=daily"` | the AI Agent action | **a person, on the Status tab** — no API; the story opens a Case task (if Cases is entitled) or a Record and a thread |
| `credit_budget` | integer credits per day, as a string | null | **a person** edits `policies/cost-ceilings.yml` by pull request and mirrors `ops_limits` |
| `none` | `""` | null | — |

`rationale` cites the rows from §4. `story_id` is always the story in the finding; a proposal for another story is another finding.

## 6. What not to propose

- `monitor_all_events` on a high-volume action — it turns every event into a notification and the router into the incident
- a watchdog shorter than the schedule interval, or on an action that legitimately idles (a Send to Story entry with no callers is silent by design — say so)
- a recipient outside §2, or a literal URL or address
- any option on a `seed` story, on an `ops-*` story (report only; ops changes go through their own change requests) or on a never-touch entry
- a change to the tenant-level alerts or to per-team credit allocation — those have no API; write the proposal as a Case task or a Record and set `needs_human`
- retries above 8 or a schedule under one minute as a "fix" for an alert — those are build conventions (`story-build-conventions`), not monitoring

## 7. Why an alert fired, or did not — the short answers

- *"It failed but nobody was paged"* → check, in order: is the story LIVE; is `monitor_failures` on; are recipients present; was the failure handled on a failure path (may not notify — VERIFY #24); did the router dedupe it into an existing thread (per story + action + 15 minutes)?
- *"It paged but nothing failed"* → an expected non-2xx (the lock's `422`, an empty lookup's `404`) not excluded from the action's error logging; a watchdog set below the real interval; `monitor_all_events` left on.
- *"The monitor itself went quiet"* → its own watchdog (1,800 s) pages the distribution list; check `ops_limits.enabled` (the kill switch) and the `ops_lock` Resource (a lock older than `stale_lock_minutes` is treated as free).
- *"We got a credit alert"* → 80 % is the actionable one; use the `credit-budget-analyst` skill; 100 % is the platform's stop, not the plan.

## 8. Boundary

This skill states policy. It applies nothing and overrides no Trigger, Resource or person. Where it disagrees with `policies/`, `AGENTS.md` or `stories/_manifest.yaml`, those files win and this skill is out of date — say so and set `needs_human`.
