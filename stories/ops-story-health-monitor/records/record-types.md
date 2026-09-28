# Record types for the ops pair

_Spec: `../DESIGN.md` §2.3 row 11 and §3.6. Six Record types serve `[OPS] 01 · Route monitoring alerts`, `[OPS] 10 · Monitor story health and credits`, the request/apply sub-stories and the Mode 4 `ops-tools-server`. Record-type creation is **[BY HAND]** in each team (dev and the prod-side ops team); whether the Tines Stories MCP server can create Record types is **VERIFY** (`docs/VERIFY.md` #26). Dashboards chart Records and Cases only, so these are also the weekly digest's data source._

Conventions: field names are `snake_case`; `story_id` / `action_id` are numbers (Tines ids); timestamps are ISO 8601 text unless the type says `datetime`; **no Record ever stores a payload body, a credential value, a Resource body or a person's name** — a reference (`payload_ref`, an approver's email as recorded by Slack, a role) at most. Records have no documented atomic semantics, which is why the run lock is a **Resource** (`ops_lock`, compare-and-swap), not a Record.

## `ops_alerts` — every notification the router saw; also the dedupe store

| Field | Type | Written by | Notes |
|---|---|---|---|
| `alert_id` | text | router `write_alert` | `<story_id>-<action_id>-<first_seen day+hour+15-min bucket>` — the dedupe key |
| `story_id` | number | router | |
| `story_name` | text | router | from the notification (shape VERIFY #9) |
| `action_id` | number | router | `0` for story-level and tenant-level alerts |
| `action_name` | text | router | |
| `source` | text | router | `story_monitoring` · `ai_credit_alert` · `event_limit_alert` · `change_control` |
| `category` | text | router `classify` | `auth` · `rate_limit` · `upstream_5xx` · `silent_source` · `credit_burn` · `unknown` |
| `severity` | text | router `classify` | `low` · `medium` · `high` · `critical` |
| `first_seen` | datetime | router | |
| `last_seen` | datetime | router `increment_count` | |
| `count` | number | router `increment_count` | occurrences inside the 15-minute window; ≥ 3 escalates to the sweep |
| `status` | text | router; sweep `write_finding` | `open` → `triaged` → `closed` |
| `thread_ts` | text | router `post_thread_root` | the Slack thread for this story for this day (thread per story per day) |
| `channel` | text | router `route` | from `ops_routing` |
| `day` | text | router | `YYYY-MM-DD`, tenant time — the thread lookup key |

Read by: router `dedupe_lookup` (story+action+window), router `find_thread` (story+day), the sweep's pre-filter (open rows), the digest.

## `ops_findings` — one row per agent run, plus one info row per sweep

| Field | Type | Written by | Notes |
|---|---|---|---|
| `run_id` | text | sweep `write_finding` / `write_info` | `STORY_RUN_GUID()` of the sweep run |
| `day` | text | sweep | `YYYY-MM-DD` — the run-cap count key (`count_agent_runs`) |
| `story_id` | number | sweep | the story diagnosed (`0` for the sweep summary row) |
| `agent_ran` | boolean | sweep | `true` only for rows written after `triage`; the run cap counts these |
| `severity` | text | sweep | final severity after `critic`; `info` for the summary row |
| `category` | text | sweep | from the output schema; `sweep_summary` for the summary row |
| `hypothesis` | text | sweep | `root_cause_hypothesis` |
| `recommended_fix` | text | sweep | |
| `proposed_kind` | text | sweep | `final_kind` after the never-touch guard |
| `confidence` | number | sweep | recorded, never routed on |
| `needs_human` | boolean | sweep | |
| `critic_agrees` | boolean | sweep | null when the critic did not run |
| `model` | text | sweep | from the agent event's `meta` (model) — so credits and `billed_cost` are never confused |
| `credits_used` | number | sweep | from `meta.credits_used` |
| `tokens_in` | number | sweep | from `meta` input tokens (exact path VERIFY at build) |
| `tokens_out` | number | sweep | from `meta` output tokens |
| `outcome` | text | sweep; later runs | `recorded` · `proposed` · `issue_opened` · `pr_dispatched` · `applied` · `rejected` · `expired` |
| `finding_id` | text | sweep | `<run_id>-<story_id>` — referenced by proposals and change-request titles (`monitor-<finding_id>`) |

Read by: `count_agent_runs` (rows today with `agent_ran == true`), the digest (credits per completed finding).

## `ops_alert_proposals` — every request that needs a human

| Field | Type | Written by | Notes |
|---|---|---|---|
| `proposal_id` | text | `[OPS] 17 · Request approval (sub)` | the approval handle carried by the Slack buttons and returned by the Mode 4 request tools; an opaque name, never a capability |
| `finding_id` | text | request sub-story | null for requests raised from the Mode 4 server |
| `kind` | text | request sub-story | `alert_rule` · `disable` · `credit_action` · `proposal_pr` |
| `story_id` | number | request sub-story | |
| `target_id` | number | request sub-story | action id, or null for story-level |
| `type` | text | request sub-story | `alert_rule_proposal.type` (`monitor_failures` … `credit_budget`) or `disable` / `pause_agent` / `reroute_provider` |
| `value` | text | request sub-story | the proposed value as text |
| `rationale` | text | request sub-story | with the evidence rows summarised |
| `requester` | text | request sub-story | `ops-story-health-monitor` for the sweep; `META.headers.email` for a Mode 4 caller |
| `status` | text | request; sweep callback path; apply | `pending` → `approved` → `applied`, or `rejected`, or `expired` |
| `approver` | text | sweep `mark_first_approval` / `mark_applied` | the verified email(s) from `ops_responders`; two for `disable` in prod |
| `approvals_count` | number | sweep | 1 or 2 |
| `at` | datetime | sweep | time of the last status change |
| `expires_at` | datetime | request sub-story | now + `ops_limits.proposal_expiry_hours`; an expired proposal is refused on click |
| `rejection_reason` | text | sweep `mark_rejected` | fed back into the next triage prompt (`rejected_proposals`) |
| `change_request_id` | text | apply sub-story | when the apply landed as a draft + change request |
| `pr_url` | text | `propose-fix.yml` result (via the router's change-control/GitHub intake) | for `proposal_pr` |
| `channel` / `thread_ts` / `message_ts` | text | request sub-story | where the approval message lives, so the callback can update it |

Read by: `load_proposal` (by `proposal_id`), `rejected_proposals` (story_id + `status == rejected`, last 30 days), the request sub-story's duplicate check (pending on the same target), the daily count against `max_proposals_per_day`, the digest (pending proposals).

## `ops_baselines` — what "normal" looks like, per story per day

| Field | Type | Written by | Notes |
|---|---|---|---|
| `story_id` | number | sweep `write_baselines` (daily 06:00 branch) | |
| `action_id` | number | sweep | the entry or scheduled action the watchdog applies to; `0` for story-level rows |
| `day` | text | sweep | `YYYY-MM-DD` |
| `runs` | number | sweep | runs that day (`GET /api/v1/stories/{id}/runs?since=`) |
| `error_logs` | number | sweep | level-4 logs that day |
| `credits` | number | sweep | `credits_used` that day (`GET /api/v1/ai_usage … group_by=story`) |
| `median_duration_s` | number | sweep | from run summaries |
| `p95_interval_s` | number | sweep | p95 inter-event interval on the entry/scheduled action (`GET /api/v1/events?story_id=&since=&per_page=500`) — the watchdog input |

Read by: `load_baselines` (last 7 days) → the pre-filter thresholds and the triage prompt's baseline block. Proposed thresholds: watchdog = `watchdog_multiplier` × p95 interval; error threshold = max(3, 3 × median error logs per window); credit budget = p95 credits × 1.5.

## `ops_credit_ledger` — credits per team and story per day

| Field | Type | Written by | Notes |
|---|---|---|---|
| `day` | text | sweep `write_credit_ledger` | |
| `team_id` | number | sweep | from `GET /api/v1/ai_usage?group_by=team` |
| `story_id` | number | sweep | from `group_by=story`; `0` on the team row |
| `credits_used` | number | sweep | Tines AI credits (one credit = $0.01 on Tines-provided models) |
| `billed_cost` | number | sweep | custom-provider external cost — kept separate on purpose |
| `budget` | number | sweep | the applicable daily budget from `ops_limits` at the time |
| `pct_of_budget` | number | sweep | |

Read by: the weekly digest (per team and per story vs `policies/cost-ceilings.yml`), the `credit_burn` pre-filter rule (yesterday's trend).

## `ops_dead_letter` — what failed inside the ops stories themselves

| Field | Type | Written by | Notes |
|---|---|---|---|
| `ref` | text | router / sweep `dead_letter` | `<story slug>-<run guid>-<action name>` |
| `story_id` | number | | the ops story that failed (the router or the sweep), not the story being monitored |
| `error_class` | text | | `auth` · `rate_limit` · `upstream_5xx` · `validation` · `lock` · `unknown` |
| `status` | text | | `open` · `replayed` · `discarded` |
| `at` | datetime | | |
| `payload_ref` | text | | the run guid and action name to find the event in Tines — **never the body** |
| `message` | text | | the structured `error.message`, ≤ 300 chars, no secrets |

Read by: the digest (dead-letter depth and age); a person, when replaying.

## Not a Record

| Thing | Where it lives | Why |
|---|---|---|
| The run lock | Resource `ops_lock` (`{"lock": "free"}`), compare-and-swap via `POST /api/v1/global_resources/{id}/replace` with `key`, `value`, `if_value` | Records have no documented atomic semantics; the Resource CAS returns 422 on mismatch (VERIFY #19) |
| Thresholds, budgets, the kill switch | Resource `ops_limits` | Read on every run; mirrored by hand from `policies/cost-ceilings.yml` |
| Who may approve | Resource `ops_responders` | The button is UI; the Resource is the control |
| Channels | Resource `ops_routing` | Per-slug channel and owner; `_approvals` and `_digest` |

## By hand — creation checklist

1. Create the six Record types above in the **dev team** and the **prod team** (the manifest's `dev` and `prod` environments, where the ops trio lives) with the exact names and field names (the export references them by name).
2. Create the four Resources (`ops_limits`, `ops_responders`, `ops_routing`, `ops_lock`) in both teams from `../resources/*.example.json`, replacing placeholders in the tenant — never in the repo. Set `ops_limits.environment` to `dev` or `prod` and `ops_limits.ops_lock_resource_id` to the numeric id of `ops_lock` in that team.
3. Mirror `policies/cost-ceilings.yml: runtime` into `ops_limits` and keep the two equal (the reviewer and the digest compare them).
4. Confirm whether `/mcp` can create Record types (VERIFY #26); until then this whole file is a by-hand step the build skill names explicitly.
