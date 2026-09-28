# `[OPS] 01 · Route monitoring alerts` — the single monitoring recipient

**Slug:** `ops-error-router` · **Mode badge:** **none** — a LIVE Webhook intake; no MCP surface (it feeds the Mode 3 sweep through Send to Story, but exposes nothing itself) · **Tier:** ops · **Owner:** ops (a role; CODEOWNERS adds security-platform) · **Descends from:** Library **1231438** (Monitor action failures in Tines and notify via Slack) — the pattern, not the canvas · **Spec:** `../../DESIGN.md` §3.6, §4.4 step 2, §5.2 entry 2

> `story.json` in this folder is a **labelled SKELETON**: the 32 actions, their names, types, formula sketches and index-based links that `/tines-build-story` produces, with placeholder GUIDs. The first `/tines-export ops-error-router` replaces it with the real export. Never edit it by hand. Every key or type marked `VERIFY` inside it is unconfirmed until read from a real export (`../../docs/VERIFY.md` #8, #9, #19, #23, #24).
>
> `samples/monitoring-payload.sample.json` is a **placeholder shape, not a capture** (VERIFY #9). No Tines page documents the body of a story-monitoring notification. Until one is captured by a deliberate LIVE failure (procedure below), `normalize` reads it defensively and nothing about this story is a headline claim.

## Purpose

Every production story names this story's webhook as its monitoring recipient (with the email DL beside it). The router receives each failure and no-events notification — plus the tenant's AI credit usage alerts, event-limit alerts, the teams' change-control webhooks and the pipeline's own ship notifications — normalises it, **dedupes it per story + action + 15-minute window** against the `ops_alerts` Record, enriches an action failure with that action's last error log, classifies it by a fixed rule table, and delivers it **to Slack (one thread per story per day) or to email, as the `ops_routing` Resource says**. It records every alert (change-control notices are posted, not recorded) in `ops_alerts` and hands a story-scoped alert of severity medium or above — or one that repeats to the window threshold — to `[OPS] 10 · Monitor story health and credits` exactly once. It changes nothing, spends no AI credits, and never posts a payload body. (This paragraph, with the mode badge and the by-name lists, is the on-canvas Note.)

### The Library 1231438 pattern — what is kept, what is added

Library story 1231438 carries the pattern Tines itself recommends: a story's monitoring recipient can be a Tines webhook, so failures become events a story can route. This story keeps that pattern and adds what a shared, production-wide recipient needs:

| From the pattern | Added here | Why |
|---|---|---|
| A webhook as the monitoring recipient | One webhook for **every** production story, set by `ship.yml` from `stories/_manifest.yaml` | Coverage is configuration, and the sweep detects any story that lacks it |
| Post the failure to Slack | A thread per story per day; channel **or email** from `ops_routing` | A vendor outage is one thread, not a channel flood |
| — | Dedupe per story + action + 15 minutes against `ops_alerts` | A notification storm after a disable or an outage is counted, not re-posted |
| — | The action's last level-4 log and a severity class from a rule table | The owner sees the cause, not just the name |
| — | A dead letter for anything the router cannot read or deliver | Nothing is lost silently |
| — | A hand-off to the sweep, once per window | The sweep triages; the router only routes |

**Start from the seed, build the story.** Import Library 1231438 into the **`90 Seeds`** folder (reference only — never demo from it, never edit it, never export it as truth), read its canvas, and confirm its entry action (expected: a Webhook — **VERIFY #23**). Then build `[OPS] 01` in the **dev team** (the manifest's `dev` environment — the ops trio has no team of its own) from this README with `/tines-build-story`. Take the Slack message shape from the seed if it helps; take nothing else.

## Mode badge — none

The router has no MCP surface. It is not a sub-story (Send to Story is **off**): it *calls* the sweep through a Send to Story action, and the sweep is the Mode 3 story. An editor or the on-call person reaches the same evidence through the Mode 4 `[OPS] 20 · Ops tools (MCP server)` (`../ops-tools-server/`), never through the router.

## Entries and expected input

One Webhook, `receive_alert` (#0), receives five kinds of sender. `classify_source` (#2) decides which one arrived; the sender's shape is known for exactly one of them.

| Sender | Configured where | `source` after `classify_source` | Shape | Written to `ops_alerts`? | Forwarded to `[OPS] 10`? |
|---|---|---|---|---|---|
| Story monitoring — "Notify when any action fails" and "Notify if no events emitted" on every production story | recipients set by `ship.yml` (`POST /api/v1/stories/{id}/recipients`) from `${OPS_ROUTER_URL}` | `story_monitoring` | **VERIFY #9** — `samples/monitoring-payload.sample.json` | yes | when severity ≥ medium, or when a low alert repeats to the threshold |
| Tenant AI credit usage alert | Admin → AI [BY HAND — no API] | `ai_credit_alert` | **VERIFY #9** | yes (`story_id: 0` when tenant- or team-level) | only when it names a story (`story_id > 0`) and is severity ≥ medium |
| Tenant event-limit alert | tenant settings [BY HAND] | `event_limit_alert` | **VERIFY #9** | yes (`story_id: 0`) | only when it names a story |
| Team change-control webhook (created / cancelled / approved / rejected / pushed) | team settings [BY HAND] | `change_control` | **VERIFY #9** | no | no — posted to the approvals channel only |
| Pipeline ship notification | `scripts/ship_story.py` (run by `ship.yml`) posts to `OPS_ROUTER_URL` | `change_control` | **known** — `{source: "ship_story.py", event, env, slug, story_id, draft_id, change_request_id, sha, source_url, run_url, requires}` (see `tests/expectations.yaml` variant `ci_change_request_opened`) | no | no — posted to the approvals channel only |

Anything `classify_source` cannot place is `unrecognised` → `error` (`error_category: validation`) → `dead_letter`, with the payload's **key names** (never its values) in the message, so a person can read the run's event and capture a new sample.

`normalize` (#1) wraps every field in `DEFAULT()` over candidate paths and computes, once: `story_id`, `story_name`, `action_id`, `action_name`, `action_type`, `event_raw`, `status_code`, `pct`, `message` (≤ 200 characters), `occurred_at`, `day` (`YYYY-MM-DD`), the 15-minute `bucket` (`YYYY-MM-DDTHH-MM`, minutes floored to 00/15/30/45), `alert_id` = `<story_id>-<action_id>-<bucket>` (the dedupe key in `records/record-types.md`), the CI fields (`slug`, `env`, `change_request_id`, `sha`, `source_url`, `run_url`), `raw_keys` and `run_id`.

## Output

The router is not a sub-story and has no `result` transform. It produces three things:

1. **An `ops_alerts` row** (`../ops-story-health-monitor/records/record-types.md`): `alert_id, story_id, story_name, action_id, action_name, source, category, severity, first_seen, last_seen, count, status: open, thread_ts, channel, day`. On a repeat inside the window, only `count`, `last_seen` and (at the threshold) `severity` change.
2. **A delivery**: a Slack thread root or thread reply, or an email — never both, never twice per window.
3. **The hand-off to the sweep** — the asserted shape, emitted by `shape_forward` (#27) and sent by `forward_to_sweep` (#28). It is exactly the shape `[OPS] 10`'s `receive_from_router` expects (`../ops-story-health-monitor/tests/sample-event.json`):

```json
{
  "trigger": "router",
  "alert_id": "0-0-2026-09-24T17-00",
  "story_id": 0,
  "story_name": "[SEC] 01 · Enrich IP (sub)",
  "action_id": 0,
  "action_name": "lookup_virustotal",
  "action_type": "Agents::HTTPRequestAgent",
  "source": "story_monitoring",
  "category": "upstream_5xx",
  "severity": "medium",
  "count": 1,
  "first_seen": "2026-09-24T17:00:00Z",
  "last_seen": "2026-09-24T17:00:00Z",
  "last_error_excerpt": "HTTP 503 from upstream after final retry (log id 0)",
  "thread_ts": "0000000000.000000",
  "channel": "#ops-tines"
}
```

Sixteen fields; `trigger` is always `router`. A change to this shape is a change to both stories, in two PRs that land together.

## Failure shape

Every failure branch lands on `error` (#30) → `dead_letter` (#31):

```json
{ "status": "error", "error_category": "auth | rate_limit | upstream_5xx | validation | unknown", "retryable": true, "message": "ops router <run guid> failed at post_thread_root with HTTP 403 — see the run's events", "failed_action": "post_thread_root", "run_id": "<run guid>" }
```

The `ops_dead_letter` row carries `ref` = `ops-error-router-<run guid>-<failed action>`, `error_class`, `status: open`, `at`, `payload_ref` (the run guid and action name — **never the body**) and the message (≤ 300 characters, no secrets). Expected non-2xx — an empty log lookup's 404 on an action deleted since it notified — is excluded from `log_error_on_status` and is not a failure.

A Slack failure does not blind anyone: every production story also notifies the email DL directly, so the DL holds the raw notification while the dead letter holds the reference.

## Storyboard walk-through — action by action

Indices are the `agents[]` order in `story.json`; links reference them by index, which is why the order is fixed and the file is never hand-edited. `Records` marks a Records action whose export type is **VERIFY** (#8). Every HTTP Request action is hardened as in the table further down.

### Intake, normalise, classify the source (#0–#6)

| # | Action | Type | What it does | Next |
|---|---|---|---|---|
| 0 | `receive_alert` | Webhook | The single recipient URL (`${OPS_ROUTER_URL}` — it carries a secret, so it lives only in `.env` and GitHub environment secrets). Responds immediately with a static response; the sender never waits on this story (response option labels under `+ Option` VERIFY). No-events watchdog 604,800 s | → 1 |
| 1 | `normalize` | Event Transform | `DEFAULT()` over candidate paths for every field (paths **VERIFY #9** — written against the placeholder sample); computes `bucket`, `alert_id`, `day`, `raw_keys`, `run_id` | → 2 |
| 2 | `classify_source` | Event Transform | Decides `source`: `change_control` (a `ship_story.py` body, or a change-control webhook), `ai_credit_alert`, `event_limit_alert`, `story_monitoring`, else `unrecognised`. The discriminating fields for every Tines-origin shape are **VERIFY #9** | → 3, 4, 5, 6 |
| 3 | `is_story_monitoring` | Trigger | `source == story_monitoring` | → 7 |
| 4 | `is_tenant_alert` | Trigger | `source` in `[ai_credit_alert, event_limit_alert]` | → 7 |
| 5 | `is_change_control` | Trigger | `source == change_control` | → 29 |
| 6 | `is_unrecognised` | Trigger | `source == unrecognised` → `error` with `validation` | → 30 |

`../../DESIGN.md` §3.6 names `classify_source` as a Trigger. A Trigger passes or does not; it cannot choose among four sources. The build therefore makes `classify_source` a message-only Event Transform that computes `source`, followed by one `is_<source>` Trigger per branch — the `AGENTS.md` §4 naming rule for Triggers.

### Dedupe against `ops_alerts` (#7–#11)

| # | Action | Type | What it does | Next |
|---|---|---|---|---|
| 7 | `dedupe_lookup` | Records | `ops_alerts` where `alert_id == normalize.alert_id` — the story + action + 15-minute window | → 8, 9; failure → 30 |
| 8 | `is_new_alert` | Trigger | no row → a new alert in this window | → 12, 13 |
| 9 | `is_repeat_alert` | Trigger | a row exists → count it, do not re-post | → 10 |
| 10 | `increment_count` | Records | `count + 1`, `last_seen`; at the threshold (`RESOURCE.ops_limits.error_threshold_per_window`, 3) a `low` row becomes `medium` and a persistent `medium` becomes `high` | → 11; failure → 30 |
| 11 | `reached_threshold` | Trigger | the new count **equals** the threshold, the row was `low` (so it was never forwarded), and the alert is story-scoped (`source == story_monitoring`, or `story_id > 0`). Fires once per window | → 27 |

Dedupe is a Records check, not the Event Transform's Deduplicate mode, because the router also needs the count and the thread. If you switch to Deduplicate mode, its time-gate behaviour is **VERIFY #19**. A repeat is never posted to Slack: the sweep reads the updated `count` from `ops_alerts` on its next run (`load_open_alerts`).

### Enrich and classify (#12–#15)

| # | Action | Type | What it does | Next |
|---|---|---|---|---|
| 12 | `is_action_failure` | Trigger | `event_raw` is a failure **and** `source == story_monitoring` (the notification names an action) | → 14 |
| 13 | `is_not_action_failure` | Trigger | the complement: no-events, tenant alerts, story-level notifications | → 15 |
| 14 | `enrich_logs` | HTTP Request | `GET /api/v1/actions/{action_id}/logs?level=4&per_page=5` with `tines_api_readonly` (Viewer role — read-only by role is **VERIFY #18**); a 404 (the action was deleted since it notified) is excluded from error logging | → 15; failure → 30 |
| 15 | `classify` | Event Transform | The rule table below → `category`, `severity`, `owner_action`, `status`, `excerpt` (the newest log message with secret-looking spans replaced by `[redacted]` — the `scripts/tines_common.py` `SECRET_PATTERNS` list — then truncated to ≤ 200 characters) | → 16 |

**The severity rule table** — fixed rules, never a model, never sentiment:

| Signal | `category` | `severity` | `owner_action` in the post |
|---|---|---|---|
| action failure, HTTP 401 or 403 | `auth` | `high` | the story owner rotates or re-scopes the credential [BY HAND]; not a story change |
| action failure, HTTP 429 | `rate_limit` | `low` → `medium` at the window threshold | back off: pace or cache; a story change only if it persists |
| action failure, HTTP 5xx | `upstream_5xx` | `medium` → `high` when it persists to the threshold | escalate to the vendor; a longer retry is a story change |
| no events emitted | `silent_source` | `medium` | check the source system and its key; silent is not failing |
| action failure, any other or unknown status | `unknown` | `medium` | read the log; the sweep triages |
| AI credit usage alert | `credit_burn` | `medium` at ≥ 80 %, `high` at ≥ 100 % | the costliest agent is in the next sweep's credit check; at 100 % the platform stops the story |
| event-limit alert | `unknown` | `medium` at ≥ 80 %, `high` at ≥ 100 % | find the chatty story in the digest; at 100 % Tines stops the story |

`status` comes from the notification if it carries one (VERIFY #9), else from the newest log message (`HTTP (\d{3})` — the log message format is **VERIFY** against a real level-4 log). Only an HTTP Request action's **final** retry notifies, and a handled failure-path error may still notify (**VERIFY #24**): both are why dedupe exists.

### Route — Slack or email, per `ops_routing` (#16–#18)

| # | Action | Type | What it does | Next |
|---|---|---|---|---|
| 16 | `route` | Event Transform | Looks up `RESOURCE.ops_routing[story_id]`, falls back to `RESOURCE.ops_routing.default`; emits `delivery` (`slack` when the entry has a `channel`, `email` when it has only an `email`), `channel`, `owner_team`, `slug` | → 17, 18 |
| 17 | `is_slack_route` | Trigger | `delivery == slack` | → 19 |
| 18 | `is_email_route` | Trigger | `delivery == email` | → 24 |

**The `ops_routing` entries this story reads.** The committed example (`../ops-story-health-monitor/resources/ops_routing.example.json`) is keyed by repository slug, but a monitoring notification carries a story **id** and name, not a slug. The router therefore looks up by story id first — the same key the sweep's `dispatch_fix` reads (`ops_routing[story_id].slug`) — and falls back to `default`. The id-keyed entries are set **in the tenant**, after the first ship, when the production ids are known; until then every alert lands in the default channel, which is correct behaviour, only less targeted:

```json
{
  "0": { "slug": "example-enrich-ip", "channel": "#sec-automation", "owner_team": "security-automation" },
  "<another prod story id>": { "slug": "<slug>", "email": "owner-team-dl@example.invalid", "owner_team": "<team>" }
}
```

An entry with a `channel` routes to Slack; an entry with only an `email` routes to email. The address is a **distribution list** — never a person (`tines-skills/alert-policy` §2) — and it lives only in the tenant's Resource, never in the repository or in a Record (the `ops_alerts` row stores `channel: "email"`, not the address).

### Deliver and record (#19–#25)

| # | Action | Type | What it does | Next |
|---|---|---|---|---|
| 19 | `find_thread` | Records | `ops_alerts` for this `story_id` and `day` with a `thread_ts` — the thread per story per day | → 20, 21; failure → 30 |
| 20 | `has_thread` | Trigger | a thread exists today | → 23 |
| 21 | `needs_thread` | Trigger | none yet | → 22 |
| 22 | `post_thread_root` | HTTP Request (the Slack send-message template, `slack_bot`) | The first alert of the day for this story **is** the thread root: `[SEVERITY] <story> — <category> on <action> (<type>): <owner_action>. Last error: <excerpt>. Alert <alert_id>` | → 25; failure → 30 |
| 23 | `post_reply` | HTTP Request (the same template, `slack_bot`) | the same line as a reply in today's thread (`thread_ts` from #19) | → 25; failure → 30 |
| 24 | `send_alert_email` | Send Email action (export type and option keys **VERIFY #8**) | the same text to the entry's DL address, subject `[OPS] <severity> <story name> — <category>` | → 25; failure → 30 |
| 25 | `write_alert` | Records | the `ops_alerts` row; `thread_ts` from #22 or #19 (empty for email); `channel` from `route` (or `email`); `count: 1`, `status: open` | → 26; failure → 30 |

### Hand-off to the sweep (#26–#28)

| # | Action | Type | What it does | Next |
|---|---|---|---|---|
| 26 | `should_forward` | Trigger | `severity` in `[medium, high, critical]` **and** the alert is story-scoped (`source == story_monitoring`, or `story_id > 0`) | → 27 |
| 27 | `shape_forward` | Event Transform | the sixteen-field shape above, from the new-alert path (#15, #16, #25) or the threshold path (#7, #10) via `DEFAULT()` | → 28 |
| 28 | `forward_to_sweep` | Send to Story → `[OPS] 10 · Monitor story health and credits` | 30-second timeout (the sweep's `send_to_story.timeout_seconds`). The sweep's own `kill_switch` and lock decide what happens next; a busy sweep leaves the alert `open` for its next run | failure → 30 |

Tenant- and team-level credit and event-limit alerts (`story_id: 0`) are recorded and posted but **not** forwarded: the sweep reads AI usage itself every 15 minutes, and forwarding an alert with no story would ask `triage` to diagnose story 0. Change-control events are never forwarded: they have nothing to triage, and the weekly digest reads pending change requests itself.

### Change control, failure, dead letter (#29–#31)

| # | Action | Type | What it does | Next |
|---|---|---|---|---|
| 29 | `post_change_control` | HTTP Request (Slack, `slack_bot`) | to `RESOURCE.ops_routing._approvals.channel`: for a ship notification, `[<env>] change request <id> opened for <slug> at <sha7> — requires a named approver in Tines` with the source and run links; for a Tines change-control webhook, the transition (created / approved / rejected / pushed / cancelled — field names **VERIFY #9**). Nothing to do; approvals stay in Tines | failure → 30 |
| 30 | `error` | Event Transform | the failure shape; `error_category` from the failing action's status, `validation` for an unrecognised payload | → 31 |
| 31 | `dead_letter` | Records | the `ops_dead_letter` row — `payload_ref`, never the body | — |

## What it never does

| Never | Enforced by |
|---|---|
| Changes a story, an action, a recipient, a monitor flag, a credential or a Resource | It holds only `tines_api_readonly` (Viewer role, VERIFY #18) and `slack_bot`; no Editor key is referenced anywhere in the export — the reviewer greps for it |
| Runs an AI Agent action or spends AI credits | No `Agents::LLMAgent` in the export; `ai.agents: []` in meta |
| Posts an event body, a payload, a raw log or a vendor response | `classify` emits a secret-scrubbed, ≤ 200-character excerpt of the newest log message (a vendor error body can echo a token); the dead letter stores a reference |
| Pages per log line or per retry | Dedupe per story + action + 15 minutes; one delivery per window; repeats only increment `count` |
| Forwards the same window twice, a tenant-level alert or a change-control event | `should_forward` / `reached_threshold` rules (story-scoped only — `source == story_monitoring` or `story_id > 0`; the threshold path only for rows that started `low`) |
| Stops routing when the kill switch is thrown | `ops_limits.enabled` is deliberately **not** read here: the kill switch stops the sweep's spend, not the intake (`../../docs/06-rollback-and-recovery.md` §7 rung 1) |
| Lists itself as a recipient, or is a recipient of the sweep or the tools server | Its own recipients are the email DL (+ a second Slack channel [BY HAND]); the three `ops-*` stories never list the router (`tines-skills/alert-policy` §2). `ship.yml` and `rollback.yml` apply the list in `story.meta.yaml: monitoring.recipients` (a list, not `manifest`), so the manifest's router URL is never added to this story |
| Writes an email address or a person's name into a Record | `write_alert` stores `channel: "email"`, never the address |
| Drops a payload it cannot read | `unrecognised` → `error` (`validation`) → `dead_letter` with key names only |
| Decides severity from prose | The rule table in `classify`; the sweep's agent reasons, the router does not |
| Appears in a demo, or is changed outside its own change request | `^\[OPS\]` in `policies/never-touch.yml`; `locked: true` in prod |

## Credentials, Resources and Records — by reference

| Kind | Name | Type / shape | `allowed_hosts` | Workbench access | Used by |
|---|---|---|---|---|---|
| Credential | `tines_api_readonly` | Text — **Viewer-role team API key** (read-only by role, VERIFY #18) | the tenant host | off | #14 |
| Credential | `slack_bot` | the Slack bot token | the Slack API host | off | #22, #23, #29 |
| Resource | `ops_routing` | `../ops-story-health-monitor/resources/ops_routing.example.json` plus the id-keyed entries above, set in the tenant | — | — | #16, #29 |
| Resource | `ops_limits` | `../ops-story-health-monitor/resources/ops_limits.example.json` — only `error_threshold_per_window` is read here | — | — | #10, #11 |
| Record type | `ops_alerts` | fields in `../ops-story-health-monitor/records/record-types.md`; also the dedupe store | — | — | #7, #10, #19, #25 |
| Record type | `ops_dead_letter` | same file | — | — | #31 |

No value appears in this folder. The export references them as `<<CREDENTIAL.name>>` / `<<RESOURCE.name>>` (the `<< >>` form observed in real exports; the `{{ }}` form named in the root design is VERIFY #8). The router's webhook `path` and `secret` **are** in the export (observed): keep `randomize_urls=false` so every production story's recipient keeps working, treat the repository as internal, and never commit `${OPS_ROUTER_URL}` anywhere but environment secrets (`../README.md`).

## Monitoring — the router is monitored by something other than itself

- Runs **LIVE** in every environment: monitoring notifications come only from LIVE stories, and the router must be LIVE to receive them from the scratch stories in dev.
- Story-level "Notify when any action fails" on. Recipients: the **email DL** and a **second Slack channel** — never the router itself. `ship.yml` and `rollback.yml` (`scripts/ship_story.py` → `set_monitoring.py --from-manifest`) add the list in `story.meta.yaml: monitoring.recipients` because it is a list, not `manifest`; the manifest's `${OPS_ROUTER_URL}` is never added to this story, so the router cannot become its own recipient. The approver still confirms the live-vs-draft view shows only the DL.
- No-events watchdog on `receive_alert` at **604,800 s** (7 days). An intake has no interval, and silence is usually good news; but a week with not one failure, credit alert, change request or ship notification more likely means the URL fell off the recipients than that the tenant is perfect. The sweep's coverage check catches the recipient side (a production story without the router); this catches the intake side. Tune after two weeks of `ops_alerts` counts.
- `keep_events_for` 30 days (`2592000` s) [BY HAND above 7 days]; change control on; `locked: true` in prod via `./scripts/tines story-update` after ship; in `policies/never-touch.yml` by the `^\[OPS\]` name pattern.

## HTTP hardening — every HTTP Request action (#14, #22, #23, #29)

| Setting | Value | Export key |
|---|---|---|
| Retry on status | `[429, 500-599]` | `retry_on_status` (observed as an array of strings; range notation **VERIFY**) |
| Retries | 5 (never the default 25 ≈ 3 h 20 min — an alert three hours late is worse than none) | **VERIFY** |
| Emit failure event | **Always** (the default "Error response only" misses timeouts and DNS failures) | **VERIFY** |
| Log error on status | excludes 404 on #14 (the action was deleted) | **VERIFY** |
| Log error if | Slack returns HTTP 200 with `"ok": false` on an error — set `log_error_if` on #22, #23, #29 so a rejected post is a failure | **VERIFY** |
| Failure path | → `error` (#30) → `dead_letter` (#31) | link representation **VERIFY** |

## Cost

- **One flow.** No AI Agent action, no AI credits, no model in the loop — the simplest rung of `../../docs/01-decision-rules.md`.
- API calls: one log read per **new** action-failure alert (never per repeat), Records reads and writes, one Slack call per delivery. A storm of 500 notifications about one action in one window costs one log read, one post and 499 Records updates.
- Rate limits it must respect: `records` 400/min and `actions` 100/min tenant-wide (`../../DESIGN.md` §6.6). A sustained storm above that is itself an incident: the dead letter fills, and the DL still has every notification.

## Tests

- `tests/sample-event.json` is the placeholder monitoring notification (the `body` of `samples/monitoring-payload.sample.json`): an HTTP 503 on `lookup_virustotal` in `[SEC] 01 · Enrich IP (sub)`. Post it to `receive_alert` (`?draft=<name>` when change control is on); `tests/expectations.yaml` asserts the new-alert Slack path, the `ops_alerts` row and the sixteen-field hand-off.
- **Replace the sample with the real capture before trusting any result.** Until then the tests prove the wiring, not the parsing.
- Variants in `tests/expectations.yaml`: a repeat inside the window, a `low` alert repeated to the threshold, a second action on the same story the same day (thread reply), a no-events notification, the email route, a tenant credit alert (not forwarded), the pipeline's ship notification (the one **known** shape), and an unrecognised payload (dead letter).
- Preconditions (dev team, [BY HAND]): `ops_routing`, `ops_limits` and the `ops_alerts` / `ops_dead_letter` Record types exist; `tines_api_readonly` and `slack_bot` exist; `[OPS] 10` is built and Send-to-Story-enabled; **set the dev `ops_limits.enabled` to `false` while testing the router**, so the forward lands but the sweep exits at its `kill_switch` and no credits are spent. For `enrich_logs` to return a real log, point the sample's `action.id` at an action in a scratch story that has actually failed.

## Capturing the real payload — once, deliberately (VERIFY #9, #24)

1. In the **dev team**, build two scratch stories (never in `90 Seeds`, never in prod): a **receiver** with one Webhook action named `capture`, and a **failer** with one HTTP Request action to `https://example.invalid/` (it fails on DNS), `emit_failure_event` Always, retries 0.
2. On the failer: story-level "Notify when any action fails" on; recipient = the `capture` webhook URL; run it **LIVE** once. On a second run, route the failure down a failure path to an Event Transform and see whether it still notifies (**VERIFY #24**).
3. Set "Notify if no events emitted" on the failer's entry at the smallest value the UI accepts (minimum **VERIFY**) and wait for one no-events notification.
4. Copy the `capture` event bodies into `samples/monitoring-payload.sample.json` (`body` for the failure, `body_no_events` for the no-events notification) and fill `_captured`. Scrub first: ids → `0`, story and action names → the example names, the tenant host → `<your-tenant>`, any URL with a path or secret → removed, any address → `*.example.invalid`.
5. Repeat once per other Tines-origin sender and commit each as its own file: `samples/ai-credit-alert.sample.json` (a team credit alert at a low threshold), `samples/event-limit-alert.sample.json`, `samples/change-control.sample.json` (approve and reject a scratch change request with the team webhook set).
6. Record the outcome in `../../docs/VERIFY.md` (#9, #24) and rewrite `normalize` and `classify_source` against the captures: `/tines-build-story ops-error-router "Rewrite normalize and classify_source against samples/*.sample.json"`. Then replace `tests/sample-event.json` with the scrubbed capture and re-run the tests.
7. Delete both scratch stories.

## Build prompts — Mode 2, through the Tines Stories MCP server

Run **`/tines-build-story ops-error-router "Build the monitoring router from stories/ops-error-router/README.md"`** in the **dev team** (the manifest's `dev` environment — the ops trio has no team of its own; it ships to the prod team like every other story) with `TINES_ENV=dev`. The skill delegates to the `tines-builder` subagent, which works on one story at a time, plans before anything bigger than a sentence, and ends every step with **Validate**. `guard-mcp.sh` mirrors every call to `.tines/mcp-activity.jsonl` and blocks any production or never-touch id. Two failed corrections on one issue → stop and re-prompt.

**Build order.** The router's hand-off (#26–#28) targets `[OPS] 10` by name, so it needs the sweep to exist and be Send-to-Story-enabled. Build the intake (prompts 1–6) first, then `[OPS] 10` (`../ops-story-health-monitor/README.md`), then prompt 7 here. This matches the sweep README's order: sub-stories → router → sweep → Mode 4 server.

**Preconditions the skill checks:** the slug is in `stories/_manifest.yaml`; `tines_api_readonly`, `slack_bot`, `ops_routing`, `ops_limits`, `ops_alerts` and `ops_dead_letter` exist in the dev team under these exact names (`story.meta.yaml`); the dev team is a real team, never personal space.

The prompts below are the pack (`.claude/skills/tines-build-story/references/prompt-pack.md`) instantiated for this story. The Tines Stories MCP server is described by its capabilities — reading and changing stories, creating and updating actions, validation — never by tool names, which are unpublished.

1. **Create, intake, normalise.** "In the Tines team `<dev team>`, folder `<manifest folder>`, create a new story named `[OPS] 01 · Route monitoring alerts`. Add a Webhook action named `receive_alert` that accepts POST with a JSON body and responds immediately; set a no-events-emitted monitor of 604800 seconds. After it add a message-only Event Transform named `normalize` that outputs, each with `DEFAULT()` over the candidate paths listed in `stories/ops-error-router/samples/monitoring-payload.sample.json` under `_normalize_reads`: `story_id`, `story_name`, `action_id`, `action_name`, `action_type`, `event_raw`, `status_code`, `pct`, `message` truncated to 200 characters, `occurred_at` (default now), `day` as `%Y-%m-%d`, `bucket` as the hour plus the minute floored to 00, 15, 30 or 45 in the form `%Y-%m-%dT%H-MM`, `alert_id` as `story_id-action_id-bucket`, the CI fields `origin`, `slug`, `env`, `change_request_id`, `draft_id`, `sha`, `source_url`, `run_url`, `ci_event`, `raw_keys` as the body's key names, and `run_id` as `STORY_RUN_GUID()`. Then validate."
2. **Classify the source.** "In `[OPS] 01 · Route monitoring alerts`, after `normalize` add a message-only Event Transform named `classify_source` that outputs `source`: `change_control` when `normalize.origin` is `ci` or the body is a change-control webhook, `ai_credit_alert` or `event_limit_alert` by the alert's type field, `story_monitoring` when `event_raw` is a failure or a no-events notification and the body names a story, otherwise `unrecognised`. After it add four Triggers: `is_story_monitoring` (source equals `story_monitoring`), `is_tenant_alert` (source is `ai_credit_alert` or `event_limit_alert`), `is_change_control` (source equals `change_control`), `is_unrecognised` (source equals `unrecognised`). Then validate."
3. **Dedupe.** "In `[OPS] 01 · Route monitoring alerts`, after `is_story_monitoring` and `is_tenant_alert` add a Records action named `dedupe_lookup` that searches the `ops_alerts` record type for `alert_id` equal to `normalize.alert_id`. After it add Triggers `is_new_alert` (no record returned) and `is_repeat_alert` (at least one). After `is_repeat_alert` add a Records action named `increment_count` that updates that record with `count` plus 1, `last_seen` as `normalize.occurred_at`, and `severity` raised from `low` to `medium`, or from `medium` to `high`, when the new count reaches `RESOURCE.ops_limits.error_threshold_per_window`. After it add a Trigger named `reached_threshold` that passes when the new count equals `RESOURCE.ops_limits.error_threshold_per_window`, the record's previous severity was `low`, and `classify_source.source` is `story_monitoring` or `normalize.story_id` is above 0. Then validate."
4. **Enrich and classify.** "In `[OPS] 01 · Route monitoring alerts`, after `is_new_alert` add two Triggers: `is_action_failure` when `normalize.event_raw` is a failure and `classify_source.source` is `story_monitoring`, and `is_not_action_failure` for the complement. After `is_action_failure` add an HTTP Request action named `enrich_logs`: GET `https://<your-tenant>.tines.com/api/v1/actions/<<normalize.action_id>>/logs` with query `level=4` and `per_page=5`, header `Authorization: Bearer` from the credential named `tines_api_readonly`; do not log a 404 as an error. Connect `enrich_logs` and `is_not_action_failure` to a message-only Event Transform named `classify` that outputs `status` (from `normalize.status_code`, else the first three-digit code after `HTTP` in the newest log message), `category` and `severity` by the rule table in `stories/ops-error-router/README.md`, `owner_action` from the same table, and `excerpt` as the newest log message with every match of the secret patterns in `scripts/tines_common.py` `SECRET_PATTERNS` replaced by `[redacted]`, then truncated to 200 characters, with `DEFAULT()` everywhere. Then validate."
5. **Route and deliver.** "In `[OPS] 01 · Route monitoring alerts`, after `classify` add a message-only Event Transform named `route` that outputs `channel`, `email_route` (true when the entry has an `email` and no `channel`), `delivery` (`email` or `slack`), `owner_team` and `slug` from `RESOURCE.ops_routing[normalize.story_id]`, falling back to `RESOURCE.ops_routing.default`. After it add Triggers `is_slack_route` and `is_email_route` on `route.delivery`. After `is_slack_route` add a Records action named `find_thread` that searches `ops_alerts` for `story_id` equal to `normalize.story_id`, `day` equal to `normalize.day` and a non-empty `thread_ts`; then Triggers `has_thread` and `needs_thread`. After `needs_thread` add the Slack send-message template as an HTTP Request action named `post_thread_root` with the credential named `slack_bot`, channel `route.channel`, and the text `[SEVERITY] story — category on action (type): owner_action. Last error: excerpt. Alert alert_id`. After `has_thread` add the same template as `post_reply` with `thread_ts` from the first record of `find_thread`. After `is_email_route` add a Send Email action named `send_alert_email` to the entry's `email`, subject `[OPS] <severity> <story name> — <category>`, with the same text. Connect `post_thread_root`, `post_reply` and `send_alert_email` to a Records action named `write_alert` that creates an `ops_alerts` record with `alert_id, story_id, story_name, action_id, action_name, source, category, severity, first_seen, last_seen, count: 1, status: "open", thread_ts, channel, day` — `thread_ts` from `post_thread_root` or `find_thread`, empty for email, and `channel` set to `email` (never the address) on the email route. Then validate."
6. **Change control, failure, dead letter.** "In `[OPS] 01 · Route monitoring alerts`, after `is_change_control` add the Slack send-message template as an HTTP Request action named `post_change_control` with the credential named `slack_bot` to `RESOURCE.ops_routing._approvals.channel`, text: for a `ship_story.py` body `[<env>] change request <change_request_id> opened for <slug> at <first seven of sha> — requires a named approver in Tines` with `source_url` and `run_url`; otherwise the change-control transition with the story name and change request id. Add a message-only Event Transform named `error` emitting `{status: "error", error_category, retryable, message, failed_action, run_id}` where `error_category` is `validation` when `is_unrecognised` fired (message: the unrecognised payload's key names only, never values), else derived from the failing action's status (`401`/`403` → `auth`, `429` → `rate_limit`, `5xx` → `upstream_5xx`, else `unknown`) and `retryable` true only for `rate_limit` and `upstream_5xx`. Connect `is_unrecognised` to `error`. After `error` add a Records action named `dead_letter` that creates an `ops_dead_letter` record with `ref` as `ops-error-router-<run_id>-<failed_action>`, `story_id` of this story, `error_class`, `status: "open"`, `at`, `payload_ref` as the run guid and action name only, and `message`. Then validate."
7. **Hand-off (after `[OPS] 10` exists).** "In `[OPS] 01 · Route monitoring alerts`, after `write_alert` add a Trigger named `should_forward` that passes when `classify.severity` is `medium`, `high` or `critical` and either `classify_source.source` is `story_monitoring` or `normalize.story_id` is above 0. Connect `should_forward` and `reached_threshold` to a message-only Event Transform named `shape_forward` that emits exactly `trigger: "router"`, `alert_id`, `story_id`, `story_name`, `action_id`, `action_name`, `action_type`, `source`, `category`, `severity`, `count`, `first_seen`, `last_seen`, `last_error_excerpt`, `thread_ts`, `channel` — each from the new-alert path, else from the first record of `dedupe_lookup` and `increment_count`. After it add a Send to Story action named `forward_to_sweep` targeting `[OPS] 10 · Monitor story health and credits` with `shape_forward` as the payload and a 30-second timeout. Then validate."
8. **Harden and finish.** "In `[OPS] 01 · Route monitoring alerts`, on `enrich_logs`, `post_thread_root`, `post_reply` and `post_change_control` set retry on status to `429` and `500-599`, retries to 5, emit failure event to Always; on the three Slack actions log an error when the response body's `ok` is false; connect every HTTP Request, Records, Send Email and Send to Story action's failure path to `error`. Add a Note to the canvas with the Purpose paragraph from `stories/ops-error-router/README.md`, the line `Mode badge: none`, and the credential, Resource and Record names. Then validate."
9. **Test.** The skill posts `tests/sample-event.json` to `receive_alert` and asserts `tests/expectations.yaml`, then runs the variants.
10. **Export** is the script, not the editor: `/tines-export ops-error-router`. Then update `story.meta.yaml` if anything in the build changed a name, and commit on `story/ops-error-router/<short>`.

Correction habits (from the prompt pack): a wrong reference → "the payload arrives at `receive_alert`'s body; fix the reference"; "credential not found" → wrong team or a different name, fix by hand once; "story not found" on `forward_to_sweep` → `[OPS] 10` is not built or not Send-to-Story-enabled in this team; two failures on one issue → clear and restart with a better prompt.

## By hand — what the Tines Stories MCP server cannot do

- Import Library 1231438 into `90 Seeds` and read it (VERIFY #23); never build on the seed itself.
- Create the Record types `ops_alerts` and `ops_dead_letter` (`../ops-story-health-monitor/records/record-types.md`; whether `/mcp` can create them is VERIFY #26), the Resources `ops_routing` and `ops_limits` with tenant values (including the id-keyed routing entries after the first ship), and the credentials `tines_api_readonly` (Viewer role) and `slack_bot` as Text credentials with `allowed_hosts` and Workbench access **off**, in the dev team and the prod-side ops team under these exact names.
- Put the router's webhook URL into `.env` (`OPS_ROUTER_URL`) and the GitHub environment secrets — nowhere else.
- Point the tenant's **AI credit usage alerts** and **event-limit alerts** (Admin → AI and tenant settings; no API) and every team's **change-control webhooks** at the router URL.
- Raise event retention to 30 days; turn change control on; run **LIVE**; after ship, `locked: true` in prod; recipients = the email DL + a second Slack channel.
- Capture the real payloads (procedure above) and record them in `../../docs/VERIFY.md`.

## Runbook — when the router itself misbehaves

| Signal | Likely cause | First check | Fix path |
|---|---|---|---|
| The DL receives "no events emitted" from `receive_alert` | the router URL was dropped from recipients, the story is disabled or in TEST mode, or the tenant was genuinely quiet for a week | `./scripts/tines live-activity --slug ops-error-router`; the sweep's coverage findings | re-apply recipients through `ship.yml` (or `./scripts/tines recipients-add` in dev); re-enable; tune the watchdog |
| Everything lands in `ops_dead_letter` with `validation` | the notification shape changed, or a new sender was pointed at the router | the dead-letter message (key names) and the run's event | capture the new shape into `samples/`, then `/tines-build-story ops-error-router "Handle <shape> in normalize and classify_source"` |
| `post_thread_root` / `post_reply` fail with 401/403, or HTTP 200 with `ok: false` | `slack_bot` rotated, revoked, or not in the channel | level-4 logs on the action; the Slack app | rotate [BY HAND]; invite the bot; the DL still has every notification meanwhile |
| `enrich_logs` fails with 401/403 | `tines_api_readonly` expired or from the wrong team | credential `expires_at`, `allowed_hosts` | owner rotates [BY HAND]; no story change |
| A storm: one story, hundreds of notifications | a vendor outage, or a break-glass disable of an upstream story | `ops_alerts` `count` for the window | nothing — that is the dedupe working; if the storm is the router's own Slack credential, the DL still receives everything |
| The sweep never hears about a failure | severity `low` below the threshold, or `story_id: 0`, or the sweep's `kill_switch` is off | the `ops_alerts` row; `ops_limits.enabled` | expected by design; the sweep's next run reads open `ops_alerts` rows anyway |
| The router URL leaked | a secret in a log or a commit | where it appeared | rotate the webhook secret [BY HAND], update `OPS_ROUTER_URL` everywhere, re-run `ship.yml` for every production slug so recipients carry the new URL |
| The router is wrong after a ship | shipped change | `git log --oneline -- stories/ops-error-router/story.json` | `/tines-rollback ops-error-router previous` — through its own change request, as every `[OPS]` story |

If the router is down, nobody is blind: every production story also notifies the email DL directly (`../../docs/06-rollback-and-recovery.md` §7 rung 6).

## Verify in your tenant before presenting

Nothing below is a headline claim; each numbered item is in `../../docs/VERIFY.md`.

- **#9** The body of a story-monitoring notification, an AI credit usage alert, an event-limit alert and a team change-control webhook — every path `normalize` and `classify_source` read.
- **#23** Library 1231438's entry action after import (expected Webhook).
- **#24** Whether an error routed down a failure path still fires "Notify when action fails" (double signals; the dedupe absorbs them either way).
- **#8** Export key names for the retry count, `emit_failure_event`, `log_error_on_status`, `log_error_if`, the Records action type, the Send Email action type and options, and the Send to Story timeout key.
- **#18** A Viewer-role team API key is effectively read-only (attempt a write; expect 404).
- **#19** The Deduplicate mode's time gate, if the build uses it instead of the Records check.
- **#26** Whether the Tines Stories MCP server can create Record types.
- The Webhook response option labels; the minimum "Notify if no events emitted" interval; the level-4 log message format the `status` regex reads; whether a timed-out Send to Story lets the sweep keep running.

## Change log

| Short sha | Date | What changed | Change request |
|---|---|---|---|
| — | 2026-09-25 | design, skeleton, placeholder sample, tests; not yet built in a tenant | — |
