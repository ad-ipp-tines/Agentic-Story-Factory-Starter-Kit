# `triage` — the exact tool set

_Spec: `../DESIGN.md` §5.4 and §5.9. Descriptions are the API: a Send to Story tool carries no output schema, so the description text is the only place the output shape lives, and the model relies entirely on the name and description to choose. Each description is 3–4 sentences with one example argument, says what the tool does **not** do, and is identical wherever the tool appears (on this agent and on the Mode 4 `ops-tools-server`) — with one exception: the Mode 4 copy of `ops_get_error_logs` returns categories and log ids, never message text (below)._

## The rules the set obeys

- **Five tools, all read-only, added one at a time.** Each is a Send to Story sub-story with a **Timeout Duration** of 20 s (under the 30-second tool-response ceiling of the Mode 4 server, where the same sub-stories are exposed), ending on a message-only Event Transform named `result` that returns 3–5 fields, with a structured `{status: "error", error_category, retryable, message}` on the failure path. The enabled set stays fixed per action (changing any tool definition invalidates the prompt cache on a custom provider).
- **All five call the Tines API with `tines_api_readonly`** — a Viewer-role team API key stored as a Text credential, `allowed_hosts` = the tenant host, Workbench access off. Read-only by role is **VERIFY** (`docs/VERIFY.md` #18: attempt a write with it and expect a 404).
- **No write tool exists on this agent.** `[OPS] 16 · Apply approved alert rule (sub)` (holds `tines_api_ops`) and `[OPS] 17 · Request approval (sub)` are called by the **story** after a Trigger, never by the model.
- **Rejected proposals are injected into the prompt by the story** (`rejected_proposals` Records search), not exposed as a sixth tool.
- **At most one MCP connection, never alongside this set.** Once the Mode 4 `ops-tools-server` is stable, the agent may hold it as its single MCP connection instead of the five Send to Story tools (Mode 3 → Mode 4). Never both: the tool names would collide and the count would double.
- **Tool outputs are untrusted data.** Log messages and payload excerpts can carry attacker-influenced strings; the instructions say to quote, never follow.
- Every tool call is an event on the tool itself and is logged in the audit log with name, inputs, outputs and status; the agent's event payload carries the full `steps`.

## The five tools

| Tool name (≤ 64 chars, snake_case, `ops_` namespace) | Sub-story (its own folder, copied from `stories/_template/`, built after `example-enrich-ip`) | Wraps (Tines API, `tines_api_readonly`) | Arguments | `result` fields (3–5) |
|---|---|---|---|---|
| `ops_get_error_logs` | `[OPS] 11 · Get error logs (sub)` — slug `ops-get-error-logs` | `GET /api/v1/actions/{id}/logs?level=4&per_page=<limit>` | `action_id` (integer, required) · `limit` (integer, default 20, max 100) · `include_messages` (boolean, default true — **never model-supplied**: the Mode 4 tool fixes it to `false`) | `{count, last_at, categories[], log_ids[], sample_messages[]}` — `sample_messages` secret-scrubbed inside the sub-story and returned only when `include_messages` is true (this agent); the Mode 4 server gets `{count, last_at, categories[], log_ids[]}` |
| `ops_get_story_export` | `[OPS] 12 · Get story export summary (sub)` — slug `ops-get-story-export` | `GET /api/v1/stories/{id}/export?clear_recipients=true` (parsed in the sub-story; the export never leaves it) | `story_id` (integer, required) | `{action_count, http_actions_without_retry[], agents_without_schema[], schedules[]}` |
| `ops_get_live_activity` | `[OPS] 13 · Get live activity (sub)` — slug `ops-get-live-activity` | `GET /api/v1/stories/{id}?include_live_activity=true` | `story_id` (integer, required) | `{not_working_actions_count, pending_action_runs_count, monitor_failures, recipients_count}` |
| `ops_get_recent_runs` | `[OPS] 14 · Get recent runs (sub)` — slug `ops-get-recent-runs` | `GET /api/v1/stories/{id}/runs?since=` + `GET /api/v1/stories/{id}/runs/{guid}/summary` | `story_id` (integer, required) · `since` (ISO 8601, default 24 h ago) | `{runs, median_duration_s, max_duration_s, last_start}` |
| `ops_get_ai_usage` | `[OPS] 15 · Get AI usage (sub)` — slug `ops-get-ai-usage` | `GET /api/v1/ai_usage?story_id=&relative_date=&group_by=action` | `story_id` (integer, required) · `relative_date` (string, default `today`; accepted values **VERIFY**) | `{credits_used, billed_cost, top_actions[]}` |

Each sub-story is one flow; whether a Send to Story sub-story used as a tool counts as an additional flow is **VERIFY** (`docs/VERIFY.md` #13). Once stable, consolidate the five into **Custom tools (Groups)** on the agent to reduce the count (a Custom tool invokes every action inside it and returns one combined output — less flexible than a root-level tool, which is why the scaffold starts with sub-stories).

## Descriptions (verbatim — paste into each tool's description field)

### `ops_get_error_logs`

> Returns the most recent error-level (level 4) logs for one Tines action: how many in the window, when the last one happened, the error categories seen (auth, rate_limit, upstream_5xx, timeout, validation, unknown), the ids of those logs, and up to five sample messages truncated to 200 characters with secret-looking spans redacted. Use it to confirm what an action is actually failing with before naming a cause; call it once per action, not once per log line. Does not read events, payloads, credential values or other stories, and cannot change the action. Returns `{count, last_at, categories, log_ids, sample_messages}`; on failure `{status: "error", error_category, retryable, message}`. Example: `{"action_id": 0, "limit": 20}`.

**The Mode 4 copy** (on `ops-tools-server`; the tool fixes `include_messages: false`, so the sub-story returns no message text — log messages are third-party free text, and in Mode 4 the result feeds someone else's model):

> Returns the most recent error-level (level 4) logs for one Tines action: how many in the window, when the last one happened, the error categories seen (auth, rate_limit, upstream_5xx, timeout, validation, unknown) and the ids of up to five of those logs — never their message text. Use it to confirm what kind of failure an action has before naming a cause, and read a log by its id in Tines when the text matters; call it once per action, not once per log line. Does not read events, payloads, credential values or other stories, and cannot change the action. Returns `{count, last_at, categories, log_ids}`; on failure `{status: "error", error_category, retryable, message}`. Example: `{"action_id": 0, "limit": 20}`.

Fixing an input on a Send to Story tool is **VERIFY E10** (`../../../docs/VERIFY.md`). If it cannot be set, build the Mode 4 `ops_get_error_logs` as a **Custom tool** (a Group inside the server: an Event Transform that sets `include_messages: false`, then a Send to Story action to `[OPS] 11`), the same fallback the two request tools use. The default stays `true` only because this agent's tool cannot be assumed to carry a fixed input either; the messages it receives are scrubbed inside `[OPS] 11` and again by `scrub` (#79) before anything is posted.

### `ops_get_story_export`

> Summarises one story's configuration from its export: the action count, the names of HTTP Request actions that lack retry-on-status or emit-failure-event settings, the names of AI Agent actions that lack an output schema, and every schedule with its cron expression. Use it when the error logs point at a configuration gap rather than an upstream outage. Returns configuration only — never credential values, resource contents, events or the full export — and cannot change the story. Returns `{action_count, http_actions_without_retry, agents_without_schema, schedules}`; on failure the standard error object. Example: `{"story_id": 0}`.

### `ops_get_live_activity`

> Returns the live-activity counters for one story right now: how many actions are not working, how many action runs are pending, whether story-level failure notifications are on, and how many monitoring recipients are configured. Use it to tell an ongoing problem from a past one and to confirm or rule out a coverage gap. Read-only; it cannot change monitoring, recipients or the story. Returns `{not_working_actions_count, pending_action_runs_count, monitor_failures, recipients_count}`; on failure the standard error object. Example: `{"story_id": 0}`.

### `ops_get_recent_runs`

> Returns run statistics for one story since a timestamp: the number of runs, the median and maximum run duration in seconds, and when the last run started. Story runs carry no status field, so use duration and count against the baseline in your prompt to detect overlap or a silent source; do not infer failure from this tool alone. Read-only; returns nothing about events or payloads. Returns `{runs, median_duration_s, max_duration_s, last_start}`; on failure the standard error object. Example: `{"story_id": 0, "since": "2026-09-23T17:00:00Z"}`.

### `ops_get_ai_usage`

> Returns AI credit usage for one story over a relative date: total credits used, the externally billed cost for actions on a custom provider, and the three costliest actions with their credits. Use it for credit_burn findings and to name the single action to pause or reroute; compare against the daily budget given in your prompt. Read-only; it cannot change providers, budgets, allocations or alerts. Returns `{credits_used, billed_cost, top_actions}`; on failure the standard error object. Example: `{"story_id": 0, "relative_date": "today"}`.

## Contract every one of the five follows (the `example-enrich-ip` shape)

```
Webhook entry (Send to Story, team access)  →  normalize (DEFAULT() on every argument)
  →  is_valid_input / is_invalid_input (Triggers)
  →  HTTP Request to the Tines API with <<CREDENTIAL.tines_api_readonly>>
       retry_on_status [429, 500-599] · retries 5 · emit_failure_event Always · log_error_on_status excludes an empty lookup's 404
  →  summarise (message-only Event Transform: counts, medians, names — never bodies)
  →  result (message-only Event Transform; 3–5 fields)      ← exit
  →  error  (message-only Event Transform; {status, error_category, retryable, message})   ← exit
Note on the canvas: purpose, inputs, outputs, "Mode badge: sub-story".
Story-level: Send to Story enabled, team access, timeout 20 s; keep_events_for 30 days; monitor_failures on; recipients = manifest.
story.meta.yaml: tier ops · mode sub-story · credentials [tines_api_readonly] · owner_team OPS.
```

## Sub-stories the story (not the agent) calls

These are Send to Story actions in `../story.json`, reached only after a Trigger. They are listed here so nobody adds them to the agent.

| Sub-story | Called from | Input | `result` |
|---|---|---|---|
| `[OPS] 17 · Request approval (sub)` — slug `ops-request-approval` | `request_approval` (after `kind_alert_rule` / `kind_credit_action` / `kind_disable` / `coverage_proposal`); also the two request tools on the Mode 4 server | `{kind: alert_rule \| disable \| credit_action, story_id, action_id?, type?, value?, rationale, requester, finding_id?}` | `{approval_id, status: "pending", approvers[], expires_at}` — it writes `ops_alert_proposals` (pending, `expires_at` = now + `proposal_expiry_hours`), checks never-touch and `max_proposals_per_day`, and posts the Block Kit approval to the `_approvals` channel in `ops_routing` |
| `[OPS] 16 · Apply approved alert rule (sub)` — slug `ops-apply-alert-rule` | `apply` (after `is_fully_approved`) | `{proposal_id, kind, story_id, action_id, type, value, approver}` | `{status: applied \| queued_for_hand \| refused, change_request_id, message}` — the **only** place `tines_api_ops` lives: `recipient` → `POST /api/v1/stories/{id}/recipients` (live-vs-draft semantics VERIFY #7); `monitor_*` → `PUT /api/v1/actions/{id}` / `PUT /api/v1/stories/{id}` into a draft → `POST /api/v1/stories/{id}/change_request` titled `monitor-<finding_id>`; `token_threshold` / `credit_budget` → no API → a Case task (if Cases is entitled) or a Record + thread [BY HAND]; `credit_action` (two approvers) → a draft + change request only, never live; `disable` (two approvers) → never a direct `POST /api/v1/stories/{id}/disable`: it dispatches `rollback.yml` with `emergency: true`, whose break-glass job (two GitHub reviewers) disables the named story only, never a never-touch entry, and appends `policies/break-glass-log.md` in the same run |

Both live in the dev and prod teams like the rest of the ops trio (owned by the ops role), run LIVE, are `locked: true` in prod and are in `policies/never-touch.yml` by the `^\[OPS\]` name pattern.
