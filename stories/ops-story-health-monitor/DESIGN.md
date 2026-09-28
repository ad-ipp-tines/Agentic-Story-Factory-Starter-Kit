# The agentic monitoring story — design (in-repo copy)

_This is §5 of the root `DESIGN.md` (Tines Stories as Code, merged design v1, 2026-09-24), copied here verbatim so the story folder is self-contained, followed by three appendices that map the design onto the files in this folder. If the two ever differ, the root wins and this copy is refreshed in the same PR. Platform: **Tines Stories** (Tines Classic). Nothing marked VERIFY is a headline claim; every item is tracked in `../../docs/VERIFY.md`._

---

## 5. The agentic monitoring story

### 5.1 Name, place, mode

`[OPS] 10 · Monitor story health and credits` (slug `ops-story-health-monitor`), with `[OPS] 01 · Route monitoring alerts` (`ops-error-router`) as its intake and `[OPS] 20 · Ops tools (MCP server)` (`ops-tools-server`) as its external face. All three are built in the **dev team** and shipped to the **prod team**, like every other story (amended: `stories/_manifest.yaml` maps the `ops-*` slugs to the same `dev` and `prod` environments, so `resolve_target`, `/tines-build-story` and `ship.yml` target those teams; a separate ops team would need its own manifest environment and key, which is not built). They are owned by the ops role (`owner: ops`, the `[OPS]` prefix), never personal space (the AI Agent action is unavailable there), run **LIVE** (monitoring is not available in TEST mode), have change control on, are `locked: true` in prod, and are listed in `policies/never-touch.yml` so no hook, skill or pipeline writes to them outside their own change requests. Their own recipients point at the email DL and a second Slack channel so the monitor is monitored.

**Mode badge: Mode 3** — one AI Agent action in **Task mode** whose tools are Tines tools (Send to Story sub-stories). No external MCP connection is attached by default; the only MCP connection it may ever hold is the repo's own Mode 4 `ops-tools-server`, as a single tool, and never alongside the Send to Story set.

### 5.2 Trigger

Three entries into one story:
1. **Schedule** — `{"cron": "*/15 * * * *"}` (the 15-minute sweep) and a second schedule action at `06:00` tenant time (the daily credits/coverage/baseline sweep, `{"cron": "0 6 * * *", "timezone": "<tenant tz>"}`). Each schedule action carries `monitor_no_events_emitted: 1800` so a dead monitor is itself an alert.
2. **Send to Story** from the router — any failure notification with severity ≥ medium or ≥ 3 occurrences in a window; the router also forwards the tenant AI credit usage alert, event-limit alert and change-control webhooks it receives.
3. **Webhook** — Slack interactivity callbacks for the approval buttons (`JSON_PARSE(webhook.body.payload)` → `actions[0].action_id`, `user.id`, `message.ts`, `channel.id`).

First action after any entry: a **Trigger** on `ops_limits.enabled == true` (the kill switch). Second: the **compare-and-swap lock** — `POST /api/v1/global_resources/<ops_lock>/replace {key: "lock", value: "<<STORY_RUN_GUID()>>", if_value: "free"}`; a 422 (already running) is excluded from `log_error_on_status` and branched on in a Trigger to exit; a lock older than `stale_lock_minutes` is treated as free. Released with `if_value` = the run's GUID on the last action and on every failure branch.

### 5.3 Inputs

All reads use a **Viewer-role team API key** stored as a Text credential (`tines_api_readonly`) with `allowed_hosts` = the tenant host and Workbench access off (read-only by role — VERIFY).

| Input | Endpoint / source | What it gives |
|---|---|---|
| **Story runs** | `GET /api/v1/stories/{id}/runs?since=` · `GET /api/v1/stories/{id}/runs/{guid}/summary` · `GET /api/v1/stories/{id}/runs/{guid}` | `guid`, `duration`, `start_time`, `end_time`, `action_count`, `event_count` — **no status field**, so failure is derived |
| **Action events and logs** | `GET /api/v1/actions/{id}/logs?level=4` · `GET /api/v1/actions/{id}?include_live_activity=true` · `GET /api/v1/actions/{id}/events?per_page=` · `GET /api/v1/events?story_id=&since=&per_page=500` | error logs (`id`, `message`, `created_at`, `inbound_event`), `last_error_log_at`, `pending_action_runs_count`, `monitor_*` flags, event cadence for baselines |
| **Live activity** | `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true&per_page=100` · `GET /api/v1/stories/{id}?include_live_activity=true` | `not_working_actions_count`, `pending_action_runs_count`, `monitor_failures`, `actions_with_monitoring`, `recipients`, `change_control_enabled`, `locked`, `mode` |
| **Credit usage** | `GET /api/v1/ai_usage?relative_date=today&group_by=story` · `…&group_by=team` · `…&story_id=&group_by=action` · `…&start_date=&end_date=&group_by=day` | `credits_used`, `billed_cost`, input/output/cached tokens, `usage_count` |
| **Monitoring notifications** | the router's Webhook (payload shape VERIFY — captured once) | story, action, action type, failure/no-events, timestamps |
| **Audit** | `GET /api/v1/audit_logs?after=&per_page=` (client-side `story_id` filter; `operation_name[]` once the MCP operation name is known — VERIFY) | `user_email`, `operation_name`, `source`, `request_user_agent` for the digest and drift attribution |
| **Repo state** | `ops_baselines`, `ops_alerts`, `ops_alert_proposals`, `ops_dead_letter` Records; `ops_limits`, `ops_routing`, `ops_responders` Resources | thresholds, budgets, kill switch, who may approve, what was already proposed or rejected |

### 5.4 The AI Agent action's tools

One AI Agent action, **`triage`**, Task mode, temperature 0.2, timeout raised above the 30 s default, retries low, system instructions from `agent/system-instructions.md`, skills `story-health-triage` and `credit-budget-analyst` attached, output schema from `agent/output-schema.json`. Tools are **five read-only Send to Story sub-stories**, added one at a time, each with a **Timeout Duration**, each ending on a `result` Event Transform returning 3–5 fields, each returning a structured error on its failure branch, each description 3–4 sentences with one example argument:

| Tool (sub-story) | Wraps | Returns |
|---|---|---|
| `ops_get_error_logs(action_id, limit)` | `GET /api/v1/actions/{id}/logs?level=4` | `{count, last_at, categories[], log_ids[], sample_messages[]}` — messages secret-scrubbed in the sub-story; the Mode 4 copy fixes `include_messages: false` and returns `{count, last_at, categories[], log_ids[]}` only |
| `ops_get_story_export(story_id)` | `GET /api/v1/stories/{id}/export?clear_recipients=true` | `{action_count, http_actions_without_retry[], agents_without_schema[], schedules[]}` — configuration only, never values |
| `ops_get_live_activity(story_id)` | `GET /api/v1/stories/{id}?include_live_activity=true` | `{not_working_actions_count, pending_action_runs_count, monitor_failures, recipients_count}` |
| `ops_get_recent_runs(story_id, since)` | `GET /api/v1/stories/{id}/runs?since=` + `/summary` | `{runs, median_duration_s, max_duration_s, last_start}` |
| `ops_get_ai_usage(story_id, relative_date)` | `GET /api/v1/ai_usage?story_id=&group_by=action` | `{credits_used, billed_cost, top_actions[]}` |

Rejected proposals from `ops_alert_proposals` are injected into the prompt **by the story**, not as a sixth tool, so the agent does not repeat them. **No write tool exists on this agent.** The same five sub-stories are what `ops-tools-server` exposes in Mode 4 (§5.9). A second, tool-less AI Agent action, **`critic`** (fast model), runs only for `high`/`critical`: it re-reads `evidence[]` and may only confirm or downgrade; disagreement sets `needs_human`.

### 5.5 Output schema (validated by the action; the Trigger after it branches only on these fields)

```json
{
  "story_id": "integer",
  "story_name": "string",
  "severity": "low | medium | high | critical",
  "category": "auth | rate_limit | upstream_5xx | silent_source | schema_failure | credit_burn | overlap | coverage_gap | lock_stale | mcp_health | unknown",
  "root_cause_hypothesis": "string",
  "evidence": [ { "source": "string", "ref": "string", "excerpt": "string" } ],
  "recommended_fix": "string",
  "proposed_change": { "kind": "none | story_config | alert_rule | disable_action | credit_action", "target": "string", "summary": "string" },
  "alert_rule_proposal": {
    "type": "monitor_failures | monitor_no_events_emitted | monitor_all_events | recipient | token_threshold | credit_budget | none",
    "story_id": "integer", "action_id": "integer | null", "value": "string", "rationale": "string"
  },
  "needs_human": "boolean",
  "confidence": "number"
}
```

### 5.6 Guards (story elements, never prompt text)

- **Kill switch** `ops_limits.enabled` and the **CAS lock** on `ops_lock` (§5.2).
- **Deterministic pre-filter before any AI** (an Event Transform): error count vs `error_threshold_per_window`; `not_working_actions_count > 0`; `pending_action_runs_count` > baseline × 3; `monitor_failures: false` or empty recipients (coverage gap); credits today ≥ 80 % or 95 % of `credit_budget_daily` (per story or default); run duration ≥ `overlap_ratio` × schedule interval; no events beyond 2× interval on a scheduled story; a lock older than `stale_lock_minutes`; for Mode 4 stories no `initialize` events over a window or tools nearing the 30-second ceiling. **Only anomalous stories reach the agent; a healthy sweep costs zero credits.** Info-level findings are logged, never sent to the model.
- **Rate and run caps:** agent runs today < `agent_runs_per_day_max` (a Records count) and the ops team's own credits below `credit_alert_pct[1]` — both Triggers; `max_proposals_per_day` from `ops_limits`.
- **Dedupe** per story+action+window in the router (Deduplicate mode or an `ops_alerts` check); one event per notification, never per log line.
- **No write credential on the agent.** `tines_api_ops` (Editor-role team key) lives only inside the apply sub-story, behind a verified approval. This story holds only `tines_api_readonly`, the lock-only `tines_api_ops_lock` (the `ops_lock` compare-and-swap, nothing else) and `tines_api_dev_autofix` (the dev coverage auto-fix — a real key only in the dev team, so it fails closed in prod even if `ops_limits` is mis-set; the committed example defaults to `environment: prod`, `auto_apply_in_dev: false`).
- **Approvals:** the Slack request signature and a 5-minute timestamp window are verified before any callback is parsed (credential `slack_signing_secret`); then every button click is verified against `ops_responders` (the button is UI, the Resource is the control); two approvers for `disable` and `credit_action` in prod; proposals expire.
- **Never-touch:** a Trigger checks the target story against the never-touch mirror before any proposal that would change it; `ops-*` stories can only be *reported on*.
- **Schema, not sentiment:** Triggers fire on `severity`, `proposed_change.kind`, `needs_human` — never on confidence or prose. An output-schema validation failure → Record + human.
- **Expected non-2xx** (the lock's 422, an empty lookup's 404) excluded from `log_error_on_status`.
- **Tool outputs are data:** error logs and webhook payloads can contain attacker-influenced strings; the agent can only propose, the critic re-checks, and every path to production passes lint, an independent review, a human merge and a human change-request approval.
- **Token alerts** on both agents' Status tabs (Notify at `daily_tokens_notify`, Disable action at `daily_tokens_disable`); event retention raised on all three ops stories; the sweep's own watchdog at 1,800 s → the DL.

### 5.7 Actions — what the story does with a finding

| `proposed_change.kind` / signal | What happens | Endpoint(s) | Human? |
|---|---|---|---|
| `none` (record_only) | `ops_findings` Record with `meta.credits_used`, tokens, model; thread reply | Records API | no |
| **coverage gap in dev** | recipients added and `monitor_failures` set immediately (`environment: dev` and `auto_apply_in_dev: true` in the dev team's `ops_limits`; credential `tines_api_dev_autofix`, a real key only in the dev team) | `POST /stories/{id}/recipients`, `PUT /stories/{id}` | no |
| **coverage gap in prod** / `alert_rule` | `ops_alert_proposals` (pending) → Slack Block Kit approval → on approve, the apply sub-story: `recipient` → `POST /recipients` (live vs draft semantics VERIFY); `monitor_*` → `PUT /actions/{id}` or `PUT /stories/{id}` with `draft_id` → `POST /change_request` `monitor-<finding_id>` for the same approver; `token_threshold` / `credit_budget` → no API → Case task (if Cases is entitled) or Record + thread [BY HAND]; status → `applied` | as listed | **yes** (verified approver) |
| **open a Case or ticket** | severity ≥ high, or any `credit_burn` at warn: a Case with priority so SLA timers run (if Cases is entitled; Case notifications allow up to 5 webhooks per team), else a ticket through an `open_ticket` sub-story, else a GitHub issue | Cases / ticket API / GitHub | no (creation); yes (resolution) |
| **Slack post** | every finding ≥ medium: thread per story per day, channel from `ops_routing`; approvals as Block Kit buttons; the credit digest at 80 % | Slack API (credential `slack_bot`) | no |
| `story_config` | GitHub issue with diagnosis, `evidence[]` and an exact `/tines-build-story` prompt; if the kind is on the auto-PR allow-list (add `retry_on_status`/`emit_failure_event`, change a schedule, adjust a `DEFAULT()`), also `repository_dispatch` `tines-fix-proposal` → `propose-fix.yml` → `/tines-propose-fix` → PR `ops-proposal` | GitHub (credential `github_dispatch`, `allowed_hosts` `api.github.com`) | **yes** (merge + change-request approval) |
| `disable_action` | Slack approval (two approvers in prod) → the apply sub-story dispatches `rollback.yml` with `emergency: true`: its break-glass job (two GitHub reviewers, neither the dispatcher) disables the named story only, never a never-touch entry, and appends `policies/break-glass-log.md` in the same run; safe-disable note in the thread | `POST /api/v1/stories/{id}/disable` (inside `rollback.yml` only) | **yes** (two approvers + two break-glass reviewers) |
| `credit_action` | at 80 %: summary by team/story with the costliest agents; at 95 %: proposal to pause the costliest agent or route it to a custom provider — two different approvers (`ops_responders.two_required_for`), landed by the apply sub-story only as a draft + change request, never a live write; the platform's 100 % stop is the backstop | `GET /api/v1/ai_usage` | **yes** (two approvers + change-request approval) |

### 5.8 Alert-setting behaviour (agentic, human-approved)

The story learns each story's normal from data rather than fixed numbers, and the agent fills `alert_rule_proposal`; it never sets a threshold itself:
- **Watchdog** `monitor_no_events_emitted` = `watchdog_multiplier` (2) × the p95 inter-event interval of the entry or scheduled action, from `GET /api/v1/events?story_id=` and the runs list, stored daily in `ops_baselines`.
- **Per-story credit budget** = p95 of the last 7 days' `credits_used` × 1.5, proposed into `ops_limits.credit_budget_daily.per_story`.
- **Error threshold** = max(3, 3 × median level-4 logs per window).
- **Recipient proposals** whenever a new published story appears without the router.
- Every proposal carries `rationale` and the evidence rows; rejected proposals record a reason and are fed back next run; approved ones are applied deterministically by the apply sub-story (into a draft + change request) and mirrored into `story.meta.yaml` by the next `drift.yml` PR so the repo stays the truth. In dev (the dev team's `ops_limits` sets `environment: dev` and `auto_apply_in_dev: true`; the committed example defaults to `prod` / `false`) recipient and monitor-flag proposals apply without a click so builders see the behaviour, through `tines_api_dev_autofix`, which holds a real key only in the dev team; in prod nothing applies without a verified approver.

### 5.9 The Mode 4 face (`ops-tools-server`)

The five read sub-stories plus `request_alert_rule` and `request_disable` are exposed by one MCP server action. Lookups carry **Tool hints: Read only**; request tools keep the default hints (Destructive on). Hints are MCP annotations a client may use — whether a client prompts on them is VERIFY per client and never a control; the control is that the request tools only post an approval through `[OPS] 17` and nothing changes until a verified approver approves. Access control **With a Tines API Key**, members of the ops team; the caller's email (`META.headers.email`) is written into `ops_alert_proposals.requester`. This is how a human — or the builder's editor — asks the monitor's questions and requests the monitor's actions without a second implementation of the guards: the request tools run the same sub-stories that post the same approvals to the same channel. One flow; no AI credits; 30-second tool ceiling (the lookups return in well under that; anything slower returns `{status: started, id}` and a status tool).

### 5.10 What needs a human — the boundary

**The story may do alone:** read anything with the read-only key; write Records; post threads and digests; add recipients and monitor flags **in dev**; open GitHub issues; open Cases or tickets; fire `repository_dispatch` (which only ever yields a PR).
**A named human must:** approve any alert rule applied to prod (verified against `ops_responders`); approve any disable (two people in prod, then two break-glass reviewers in GitHub) and any `credit_action` pause or reroute (two people, then the change request); merge any PR; approve any change request in Tines; set token thresholds on the Status tab, per-team credit allocation and credit-usage alert thresholds in Admin → AI (no API); create Record types; answer `needs_human` findings (severity high/critical, confidence < 0.6, category unknown, critic disagreement, schema validation failure).

### 5.11 Weekly digest (Monday branch)

Monitoring coverage (stories with `monitor_failures: false` / empty recipients / `actions_with_monitoring: 0`), credits per team and per story vs `policies/cost-ceilings.yml` (from `ops_credit_ledger`), credits per completed finding, top failing actions, dead-letter depth and age, pending change requests (`GET …/change_request/view` per production story), MCP activity count from `GET /api/v1/audit_logs` (operation name VERIFY), drift PRs opened — to Slack and to Records for a Dashboard. Audit logs themselves reach the SIEM through the native S3 export every 15 minutes, not through a story.

### 5.12 Flows and cost

Router 1 + sweep 1 + Mode 4 server 1 + five read sub-stories + apply sub-story ≈ **9 flows** (whether Send to Story sub-stories used as tools count as flows is VERIFY with the account team); consolidate the read tools into **Custom tools (Groups)** on the agent once stable to reduce the count. Credits are spent only on anomalous stories and only by `triage` (smart model, tools attached) and `critic` (fast model, no tools); a healthy tenant costs the API calls and nothing else.

---

## Appendix A — where each element of §5 lives in this folder

| §5 element | File / action in `stories/ops-story-health-monitor/` |
|---|---|
| Three entries (§5.2) | `story.json` actions `sweep_15m` (#0), `sweep_daily` (#1), `receive_from_router` (#2), `slack_callback` (#3) |
| Kill switch, CAS lock | `kill_switch` (#5); `acquire_lock` (#8) / `lock_acquired` / `lock_busy` / `is_stale_lock` / `is_fresh_lock` / `exit_busy` / `steal_lock` (#9–#14); `release_lock` (#74) |
| Inputs (§5.3) | `live_activity` (#15), `ai_usage_today` (#16), `recent_runs` (#17), `load_baselines` (#18), `load_open_alerts` (#19); `pending_change_requests` (#70), `audit_mcp_count` (#71) |
| Deterministic pre-filter (§5.6) | `findings` (#20) — the rules are in its description; `write_info` (#21) logs info rows |
| Coverage drift (§4.4 step 4, §5.7) | `has_coverage_gap` (#22) → dev: `recipients_add_dev` / `story_update_dev` (#24–#25); prod: `coverage_proposal` (#27) → `request_approval` (#48) |
| Run and credit caps | `count_agent_runs` (#30), `under_run_cap` / `over_run_cap` (#31–#32), `capped` (#33) |
| Rejected proposals in the prompt | `rejected_proposals` (#34) → the `prompt` of `triage` |
| The AI Agent action `triage` (§5.4) | `triage` (#35); `agent/system-instructions.md` §1; `agent/output-schema.json`; `agent/tools.md` |
| The `critic` | `needs_critic` / `skip_critic` (#36–#37), `critic` (#38); `agent/system-instructions.md` §2; `agent/critic-output-schema.json` |
| Schema-not-sentiment routing; never-touch guard | `verdict` (#39) → `kind_none` / `kind_alert_rule` / `kind_credit_action` / `kind_disable` / `kind_story_config` (#42–#46) |
| Actions per kind (§5.7) | `write_finding` (#40), `scrub` (#79 — the secret scrub every Slack and GitHub post reads), `post_thread` (#41), `shape_proposal` (#47) → `request_approval` (#48) → `[OPS] 17 · Request approval (sub)`; `open_issue` (#49), `is_auto_pr_kind` (#50), `dispatch_fix` (#51) |
| Approvals (§5.6, §5.10) | `verify_slack_signature` / `is_signed_callback` (#77–#78) before anything is parsed, then `parse_callback` … `mark_applied` (#52–#65); the control is `is_verified_approver` (#55) against `resources/ops_responders.example.json`; `apply` (#64) → `[OPS] 16 · Apply approved alert rule (sub)` |
| Alert-setting behaviour (§5.8) | `write_baselines` (#67) feeds `ops_baselines`; the derivations are rules 5 in `agent/system-instructions.md` and the `alert-policy` tenant skill |
| Weekly digest (§5.11) | `is_daily` / `write_baselines` / `write_credit_ledger` / `is_monday` / `pending_change_requests` / `audit_mcp_count` / `digest` / `post_digest` (#66–#73) |
| Failure handling | `error` (#75) → `dead_letter` (#76) → `release_lock` (#74) |
| Resources | `resources/ops_limits.example.json`, `ops_responders.example.json`, `ops_routing.example.json`, `ops_lock.example.json` |
| Records (§2.3 row 11) | `records/record-types.md` |
| Budgets, token alerts | `story.meta.yaml: ai.agents[]`; `policies/cost-ceilings.yml: agents.ops-story-health-monitor/*` |
| Tests | `tests/sample-event.json` (the router path), `tests/expectations.yaml` (happy path + kill switch, busy/stale lock, healthy sweep costs nothing, forged or replayed Slack signature, unverified click, approve, two-approver disable, never-touch) |

## Appendix B — flow budget for this scaffold (counted, not assumed)

| Story | Flows | Notes |
|---|---|---|
| `[OPS] 01 · Route monitoring alerts` | 1 | Webhook intake |
| `[OPS] 10 · Monitor story health and credits` | 1 | two schedules + Send to Story + Webhook in one connected graph — whether several triggers in one graph count as one flow is deferred to the account team (VERIFY #13) |
| `[OPS] 20 · Ops tools (MCP server)` | 1 | the MCP server action counts as a flow; no AI credits |
| `[OPS] 11–15` · the five read sub-stories | 5 | a Send to Story sub-story's Webhook input is an autonomous trigger, so each counts (VERIFY #13); collapse into Custom tools (Groups) on `triage` once stable |
| `[OPS] 16 · Apply approved alert rule (sub)` | 1 | holds `tines_api_ops` |
| `[OPS] 17 · Request approval (sub)` | 1 | shared by the sweep and the Mode 4 request tools — the reason there is no second implementation of the guards; §5.12's "≈ 9" did not count it separately |
| **Total** | **≈ 10** | Community Edition (3 flows) cannot run this; Business plans start at 30 |

Credits: `triage` (smart model) only on anomalies; `critic` (fast model) only on high/critical. A healthy sweep costs API calls only. Both agents carry Status-tab token alerts; the ops team's monthly allocation (`policies/cost-ceilings.yml: teams.ops`) is the outer wall, and the platform's own 100 % stop is the backstop, not the plan.

## Appendix C — the decision table (what may happen without a person)

| Signal / kind | Alone | With one verified approver | With two verified approvers | Only through a PR + change request |
|---|---|---|---|---|
| Info-level finding | Record | — | — | — |
| `none` (record only) | Record + thread reply | — | — | — |
| Coverage gap, **dev** | recipients + `monitor_failures` applied | — | — | — |
| Coverage gap, **prod** | proposal + Slack approval posted | applied into a draft + change request (`monitor-<finding_id>`) | — | the change request itself is approved in Tines by a person |
| `alert_rule` (`monitor_*`, `recipient`) | proposal posted | applied into a draft + change request | — | as above |
| `alert_rule` (`token_threshold`, `credit_budget`) | proposal posted | queued as a Case task or Record + thread [BY HAND] — no API | — | — |
| `credit_action` | at 80 %: summary posted | — | at 95 %: pause / reroute landed by the apply sub-story as a draft + change request, never live | the change request itself is approved in Tines by a person |
| `story_config` | GitHub issue with an exact `/tines-build-story` prompt; `repository_dispatch` when on the allow-list | — | — | PR → lint → independent review → human merge → `ship.yml` → human change-request approval |
| `disable_action` | proposal posted | (dev: one approver) | **prod: two different approvers** → the apply sub-story dispatches `rollback.yml` (`emergency: true`); its break-glass job (two GitHub reviewers) calls `POST /api/v1/stories/{id}/disable` and logs it in `policies/break-glass-log.md` | — |
| Any target in never-touch | report only (`final_kind` forced to `none`, `needs_human` true) | — | — | its own change request, by ops |
| `needs_human` | thread marked, Record written | a person answers | — | — |
