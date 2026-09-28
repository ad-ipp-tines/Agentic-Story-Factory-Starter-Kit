# Section D — specialist dispatch (deterministic routing, tool-less agents)

_Spec: REPO-DESIGN.md §6.4 (spinning specialists up in Tines), §7.6 (this section), §5.3.11–§5.3.13 (the three runtime specialists), §4.2 (`improve_trigger`), §12 rows 2–5, §13 row 7. Part of `[KIT] 00 · Run the story factory`. Built through Mode 2 by build prompt **P-K14** (`../build-prompts.md`), with the three agents' system instructions and Output schemas pasted from `sdlc/agents/runtime/*` and the fast model pinned on each. Records calls follow [`B-tracker-sync-in.md`](B-tracker-sync-in.md) ("Records access in sections B–E")._

**What it does.** It runs the three Tines-side specialists — `brief_writer` (00 intake), `planner` (backlog level) and `retro_writer` (07 improve) — when the tracker's state changes, and nudges people about gates left open. **No model decides whether a model runs**: Triggers read the dispatch table `runtime_dispatch` in the `sdlc_state_machine` Resource (generated from `sdlc/lifecycle/state-machine.yaml`), the kill switch and the caps come before any model call, and every agent is **tool-less and holds no credential**. Its outputs are **proposals**: a brief for the G0 decider, planner proposals a person accepts or rejects, a retro draft a person completes. Git changes only through a tracker PR a person merges.

**The dispatch table** (`RESOURCE.sdlc_state_machine.runtime_dispatch`):

```json
{ "on_enter":          { "intake": "brief_writer", "improve": "retro_writer" },
  "on_backlog_change": { "agent": "planner", "debounce_minutes": 60 },
  "on_schedule":       { "retro_writer": { "after_live_days": 7, "every_days": 30 }, "planner": { "weekly_day": "MON" } } }
```

## How state changes reach this section

| Way in | From | Carries |
|---|---|---|
| Repo → Records sync | B8 `log_transition` (a row created, or its phase changed by a merge) | `source: "sync"` |
| Tines-side decisions | C4 `use_case_log_event` (a use case added), C5 `gate_log_event` (G0, G6, G7, GX, unpark) | `source: "page" \| "app" \| "gate"` |
| The schedule backstop | D1 `dispatch_sweep` every 15 minutes | `source: "sweep"` — rows with `specialist_status: pending` older than 15 minutes, a weekly planner run, gates to nudge |
| The improve check | D9 `improve_check` on the same schedule | `source: "improve"` |
| Tests (dev only) | D10 `specialist_test` | straight into one agent block; nothing is written |

## Every dispatch runs the same steps (§6.4)

1. **Kill switch:** `sdlc_limits.enabled` **and** `sdlc_limits.guards_confirmed` — both false until the setup report's last guards are done (token alerts set, skills attached; §7.2 items 3, 4 and 16).
2. **Caps:** a count of today's `sdlc_events` rows for that agent (the Records API aggregate endpoint; filter semantics **K35**) must be below `sdlc_limits.runtime.<agent>.runs_per_day_max`.
3. `specialist_status: running`.
4. The agent's block: fetch context (Records API reads, Resources) → AI Agent action → a Trigger on schema fields.
5. A Records API update (`specialist_status: proposed`), plus an `sdlc_events` row with the event's `meta` model, tokens and `credits_used`.
6. Notify through the chat surface.

## The actions

### D1 — ways in

| # | Action | Type | Does · key options and formulas | Next |
|---|---|---|---|---|
| D1 | `dispatch_in` | Event Transform, message-only | Receives from B8, C4, C5, D1c and D9. Emits `{source, story_key, record_id, rev, phase, status, open_gate, specialist_due, row, agents[]}` where `row` = `{title, use_case, owner, prod_story_id, live_since, credit_estimate_monthly, provider, outbox_seq, retro}`. **`agents[]`** (deterministic): the row agent — `runtime_dispatch.on_enter[phase]` on entering `intake` or `improve`, or the row's `specialist_due` (`brief-writer` → `brief_writer`, `retro-writer` → `retro_writer`) for a pending row from the sweep — plus **`planner`** whenever the event is a backlog change (`source` is `sync`, `page`, `app`, `gate` or `improve`) or the sweep's weekly branch, plus **`nudge`** for a sweep nudge item | → D1a |
| D1a | `each_dispatch` | Event Transform, explode | one event per entry of `agents[]` with `agent` set (no implode: each branch ends on its own) | → D2 |
| D1b | `dispatch_sweep` | Event Transform with a **schedule**: cron `*/15 * * * *` (tenant time zone) | Emits `{trigger: "sweep", at}`. **Watchdog:** "Notify if no events emitted" at **1,800 s** (2 × 15 min) — a dead dispatcher is itself an alert. A scheduled action never sits inside a Group | → `sweep_enabled` |
| D1c | `sweep_enabled` → `list_dispatch_rows` → `sweep_plan` → `has_sweep_items` / `has_no_sweep_items` → `each_sweep_item` | Trigger → HTTP Request (**List**, `sdlc_backlog`) → Event Transform → Trigger ×2 → explode | `sweep_enabled`: `RESOURCE.kit_config.entitlements.records` **and** `RESOURCE.sdlc_limits.enabled` (no List while the specialists are off). `sweep_plan` emits items: **pending** — rows with `specialist_status: pending` whose `last_transition_at` is older than 15 minutes; **weekly planner** — when today (tenant time) is `runtime_dispatch.on_schedule.planner.weekly_day` and `RESOURCE.kit_state.planner_last_run` is not today; **nudges** — rows whose `open_gate` is G0, G6, G7 or GX (or whose phase is `parked`) and whose gate has been open at least `sdlc_limits.gate_nudge_days` whole days, emitted only in the first 15-minute slot after each whole day, so a gate is nudged at most once a day with no stored state | each item → D1 `dispatch_in` (`source: "sweep"`); the same schedule also feeds D9 |

### D2 — kill switch and caps (before any model call)

| # | Action | Type | Does | Next |
|---|---|---|---|---|
| D2 | `dispatch_kill_switch` | Trigger | `RESOURCE.sdlc_limits.enabled` **and** `RESOURCE.sdlc_limits.guards_confirmed` **and** `RESOURCE.kit_config.entitlements.records`. (§7.6 names this `kill_switch`; section B has its own) | → D2a (nudge) / D2b (agents) |
| D2a | `route_agent_nudge` | Trigger | `each_dispatch.agent == "nudge"` — a nudge calls no model, so it is not counted | → D7 |
| D2b | `is_agent_dispatch` | Trigger | `agent` is `brief_writer`, `planner` or `retro_writer`, **and** `RESOURCE.kit_config.entitlements.ai_agent_action` | → D2c |
| D2c | `count_runs_today` | HTTP Request (**Query**, `sdlc_events`) | Count where `event_type = specialist_run`, `agent = <<each_dispatch.agent>>`, created today (UTC). `POST /api/v2/records/aggregate` — body **K35**; fallback `POST /api/v1/records/query`, or a per-agent counter in `kit_state` (compare-and-swap) | → D2d / D2e · failure → D2e (**fail closed**) |
| D2d | `under_cap` | Trigger | the count is below `RESOURCE.sdlc_limits.runtime.<agent>.runs_per_day_max` | → D3 |
| D2e | `over_cap` → `is_cap_news` → `log_cap_reached` | Trigger → Trigger → HTTP Request (**Create**, `sdlc_events`) | `over_cap`: the count is at or above the cap, or the count failed. `is_cap_news`: `each_dispatch.source` is not `sweep`, so the sweep's 15-minute retries of a still-pending row do not flood the log. `log_cap_reached`: `event_type: budget`, `agent`, `actor: dispatch`, `actor_kind: story`, `summary: "daily cap reached; the sweep retries after midnight UTC"`. The row stays `pending`. On the **Starter** Records tier there is no `sdlc_events` type (A18), so the count fails and the runtime specialists stay held: fail closed (P17) | end |

### D3 — routing

| # | Action | Type | Does | Next |
|---|---|---|---|---|
| D3 | `route_agent_brief_writer` · `route_agent_planner` · `route_agent_retro_writer` | Trigger ×3 | `each_dispatch.agent` equals `brief_writer` / `planner` / `retro_writer`. (§7.6 names the group `route_agent`; the nudge route is D2a) | → D4 · D5 · D6 |

### D4 — the brief-writer block (`brief_writer`, §5.3.12)

| # | Action | Type | Does · key options and formulas | Next |
|---|---|---|---|---|
| D4a | `mark_running` | HTTP Request (**Update**, the row) | `specialist_status: running` | → D4b · failure → D8 |
| D4b | `brief_context` | Event Transform | The agent's whole input, built by the story: `story_key`, `owner_role`, `prefix` (from the owner role: `security-automation` → `SEC`, `ops` → `OPS`, `platform` → `PLT`, else `PREFIX` for the G0 decider to replace), `use_case` (untrusted, quoted as submitted), `entitlements` (`RESOURCE.kit_config.entitlements`), `catalog` (`[{id, name}]` from `RESOURCE.kit_catalog.library_seeds`), `test_run`. **On the D10 path** every key is read from `specialist_test.body.context` instead: `DEFAULT(specialist_test.body.context.<k>, <live value>)` | → D4c |
| D4c | **`brief_writer`** | **AI Agent action, Task mode** | **No tools.** Instructions: the fenced block in `sdlc/agents/runtime/brief-writer/system-instructions.md`, pasted verbatim. Prompt: that file's "Prompt" block, reading `brief_context`. **Output schema:** `sdlc/agents/runtime/brief-writer/output-schema.json`. **Model: the tenant's fast model, pinned on the action** (the skill below is an agentic capability; unpinned, the default would be the smart model). Temperature 0.2 · timeout 60 s · retries 2. Skill `story-brief-writing`, attached `[BY HAND]`. Token alert Notify 100,000 / Disable 200,000 daily `[BY HAND]`. Budget line `kit-factory/brief_writer` | → D4d / D4e |
| D4d | `brief_ok` | Trigger (**directly after the agent**) | the output carries every required schema field (`suggested_title`, `problem`, `data_sensitivity`, `simplest_rung.rung`, `needs_human`, …) — schema fields only, **never `confidence` or prose**. `needs_human: true` does **not** stop the brief: G0 is a human gate either way, and the notice says why the draft needs extra attention | → D4f |
| D4e | `brief_failed` | Trigger | the complement (an action error, a timeout, an output-schema failure) | → D8 |
| D4f | `filter_seed_ids` | Event Transform | keeps only the ids of `brief_writer.output.candidate_seed_ids` that are in `RESOURCE.kit_catalog.seed_ids`; the dropped ones become an open question "unverified Library id offered by the draft" — **the agent cannot introduce an id** | → D4g |
| D4g | `render_brief` | Event Transform | Markdown in the shape of `sdlc/templates/intake-brief.md`: front matter `story_key`, `title` (the suggested title), `owner`, `source` (`kickoff_page`, `add_use_case_page` or `app`), `drafted_by: brief_writer`, `data_sensitivity`, `simplest_rung`, `candidate_seed_ids` (filtered); the use case quoted; `unknown` values rendered as `[TBD — <the open question>]`. Only schema fields are rendered, never raw model text. Truncated to the ARTIFACT limit (**CONFLICT K29**: plan for 15,000 characters) | → D4h |
| D4h | `is_live_brief` / `is_test_brief` | Trigger ×2 | `brief_context.test_run` false / true. **A D10 test stops here**: nothing is written | live → D4i · test → end |
| D4i | `save_brief` | HTTP Request (**Update**, the row) | `brief` = the Markdown, `status: awaiting_gate`, **`open_gate: G0`**, `specialist_status: proposed`, **`pending_repo_sync: true`**, **`pending_base_rev` = the row's `rev`**, `outbox_seq` = the row's + 1, `last_actor: brief_writer`, `last_transition_at` now | → D4j · failure → D8 |
| D4j | `brief_log_run` | HTTP Request (**Create**, `sdlc_events`) | `event_type: specialist_run`, `agent: brief_writer`, `actor: brief_writer`, `actor_kind: agent`, `model` = `brief_writer.meta.model`, `credits_used` = `brief_writer.meta.credits_used`, `input_tokens` / `output_tokens` from the event's `meta` (key names read from the first dev run, scaffold VERIFY #8), `summary` = the suggested title + `needs_human` | → D4k |
| D4k | `notify_g0` | Event Transform | the notice `{recipients: RESOURCE.sdlc_approvers.G0, subject: "G0: <story_key> needs a triage decision", body}` — the body names the story, links `https://<<RESOURCE.kit_config.tenant_host>>/pages/story-factory-tracker` (Decide a gate), says the brief is a draft and why `needs_human` is set; **no use-case text** | → shared delivery |

The brief reaches git as `sdlc/work/<slug>/intake.md` through `./scripts/kit tracker-fold` and a tracker PR a person merges.

### D5 — the planner block (`planner`, §5.3.11)

| # | Action | Type | Does · key options and formulas | Next |
|---|---|---|---|---|
| D5a | `is_planner_due` | Trigger | the weekly branch, **or** `RESOURCE.kit_state.planner_last_run` is empty, **or** now − `planner_last_run` ≥ `RESOURCE.sdlc_limits.runtime.planner.debounce_minutes` (default 60). Date arithmetic per the formula reference (confirmed alongside K14) | → D5b |
| D5b | `claim_planner` | HTTP Request | **the debounce**: a compare-and-swap on the ledger: `POST …/global_resources/<<RESOURCE.kit_state.self_id>>/replace` `{key: "planner_last_run", value: <now, UTC>, if_value: <<RESOURCE.kit_state.planner_last_run>>}`. **422 excluded**: another dispatch claimed it first | 200 → `planner_claimed` → D5c · 422 → `planner_claim_lost` → end |
| D5c | `list_planner_rows` → `list_planner_milestones` | HTTP Request ×2 (**List**) | `sdlc_backlog` (up to 500) and `sdlc_milestones` | → D5d |
| D5d | `backlog_snapshot` | Event Transform | The input, built by the story (§7.6 lists `backlog_snapshot` as the List; the build splits it into the two List calls above and this shaping step, which is what the planner's prompt reads — `sdlc/agents/runtime/planner/system-instructions.md`): `rows` (key, title, phase, status, open_gate, mode, owner, tier, target_date, credit_estimate_monthly, provider, attempt — **no use-case text**), `milestones`, `wip_limit_per_owner` (`RESOURCE.sdlc_state_machine.caps.wip_limit_per_owner`), `team_monthly_credit_ceiling` (**null**: no kit Resource carries it yet — the planner then skips the budget check and says so), `credits_committed_monthly` (the sum of `credit_estimate_monthly` over non-terminal rows), `entitlements`, `rejected_proposals` (every item marked `rejected` inside the rows' `proposal` JSON), `today_utc`. On the D10 path each key comes from `specialist_test.body.context` | → D5e |
| D5e | **`planner`** | **AI Agent action, Task mode** | **No tools.** Instructions: `sdlc/agents/runtime/planner/system-instructions.md` (fenced block, verbatim). **Output schema:** `sdlc/agents/runtime/planner/output-schema.json`. **Fast model pinned on the action.** Temperature 0.2 · timeout 60 s · retries 2. Skill `backlog-planning` `[BY HAND]`. Token alert Notify 60,000 / Disable 120,000 daily `[BY HAND]`. Budget line `kit-factory/planner` | → D5f / D5g |
| D5f | `planner_ok` | Trigger (directly after the agent) | `sequence`, `proposals`, `milestone_risks` and `needs_human` are present — never `confidence` | → D5h |
| D5g | `planner_failed` | Trigger | the complement | → D8 |
| D5h | `is_live_plan` / `is_test_plan` | Trigger ×2 | not a D10 test / a D10 test (stops here) | → D5i |
| D5i | `plan_by_key` → `has_proposals` / `has_no_proposals` → `each_proposal_row` | Event Transform → Trigger ×2 → explode | groups `proposals[]` and `sequence[]` by key, keeping only keys present in the snapshot (the agent cannot invent a row) | → D5j |
| D5j | `save_proposals` | HTTP Request (**Update** per key) | `proposal` (JSON) = `{proposed_at, rank, why, items: [{field, value, rationale, status: "proposed"}]}`, `specialist_status: proposed`. **No field the proposal names is changed** | → `proposals_saved` (implode) → D5k |
| D5k | `planner_log_run` | HTTP Request (**Create**, `sdlc_events`) | `event_type: specialist_run`, `agent: planner`, `actor: planner`, `actor_kind: agent`, **`story_key: "backlog"`** (the run is backlog-level, not a story's; the outbox never returns it, so it stays in Tines, where the Dashboard's credit chart and D2's count read it), `summary` = the counts of proposals and milestone risks; `model`, tokens, `credits_used` from `planner.meta` | → D5l |
| D5l | `planner_notify` | Event Transform | notice to `RESOURCE.sdlc_approvers.G0` (the people who triage the backlog): the rank-1 to rank-3 keys, each proposal as "key · field → value", the milestone risks, and `needs_human` with its reason | → shared delivery |

**Accepting a proposal (v1).** A person accepts or rejects each proposal. REPO-DESIGN.md §7.8 specifies no Page for it and the App shows proposals read-only (`routes/StoryDetail.tsx`), so in v1 the decision is made **on the row in the Records UI** `[BY HAND]`: set the item's `status` to `accepted` or `rejected` inside `proposal`; for an accepted `owner` or `target_date`, also set that field, `pending_repo_sync: true`, `pending_base_rev` = the row's `rev` and `outbox_seq` + 1, so the change reaches git through the tracker PR (§6.5). `credit_band` and `mode_hint` are hints for design: marking them is enough. A rejected item is never proposed again (the planner reads it back as `rejected_proposals`).

### D6 — the retro-writer block (`retro_writer`, §5.3.13)

| # | Action | Type | Does · key options and formulas | Next |
|---|---|---|---|---|
| D6a | `has_ops_evidence_types` / `has_no_ops_evidence_types` | Trigger ×2 | `RESOURCE.kit_config.rt_ops_findings` and `rt_ops_alerts` are not 0 (their ids reach `kit_config` from `kit/tenant/config.yaml` by PR — a day-1 `[BY HAND]` item). Otherwise → D8 with `reason: "the ops trio's Record type ids are not in kit_config yet"` | → D6b |
| D6b | `retro_mark_running` | HTTP Request (**Update**, the row) | `specialist_status: running` | → D6c |
| D6c | `list_ops_findings` → `list_ops_alerts` → `list_story_events` | HTTP Request ×3 (**List**) | `ops_findings` and `ops_alerts` by the type ids in `kit_config`, filtered on the row's **git-owned `prod_story_id`** and the window; `sdlc_events` filtered on `story_key` (gate history and credit rows). Until K5, filtering happens in D6d | → D6d |
| D6d | `ops_evidence` | Event Transform | §7.6 names `ops_evidence` as the List; the build splits it into the three List calls above and this shaping step, which is what the retro_writer's prompt reads (`sdlc/agents/runtime/retro-writer/system-instructions.md`). Emits `story_key`, `window_from` (the row's `last_transition_at` into operate, else `live_since`) and `window_to` (now), `findings` (fields only: id, severity, category, root_cause_hypothesis, proposed_change_kind, needs_human, created_at), `alerts` (fields only), `events`, `credit_estimate_monthly`, `provider`, `test_run`. **Never an event payload.** On the D10 path each key comes from `specialist_test.body.context` | → D6e |
| D6e | **`retro_writer`** | **AI Agent action, Task mode** | **No tools.** Instructions: `sdlc/agents/runtime/retro-writer/system-instructions.md`. **Output schema:** `sdlc/agents/runtime/retro-writer/output-schema.json`. **Fast model pinned.** Temperature 0.2 · timeout 60 s · retries 2. Skill `story-retrospective` `[BY HAND]`. Token alert Notify 75,000 / Disable 150,000 daily `[BY HAND]`. Budget line `kit-factory/retro_writer` | → D6f / D6g |
| D6f | `retro_ok` | Trigger (directly after the agent) | `window`, `failure_modes`, `keep_or_change` and `needs_human` are present | → D6h |
| D6g | `retro_failed` | Trigger | the complement | → D8 |
| D6h | `is_live_retro` / `is_test_retro` | Trigger ×2 | not a D10 test / a D10 test (stops here) | → D6i |
| D6i | `render_retro` | Event Transform | Markdown in the shape of `sdlc/templates/retro.md`, **with its front matter** (`story_key`, `window`, `trigger`, `keep_or_change` from the draft, `eval_cases_requested: []`, `skill_suggestions`, `cost_variance`, `curated: false`, `closed: false`), so `./scripts/kit tracker-fold` keeps the draft's proposal. Truncated to the ARTIFACT limit (K29) | → D6j |
| D6j | `save_retro` | HTTP Request (**Update**, the row) | `retro` = the Markdown, `specialist_status: proposed`, **`pending_repo_sync: true`**, **`pending_base_rev` = the row's `rev`**, `outbox_seq` + 1, `last_actor: retro_writer` | → D6k · failure → D8 |
| D6k | `retro_log_run` | HTTP Request (**Create**, `sdlc_events`) | `specialist_run`, `agent: retro_writer`, model, tokens, `credits_used`, `summary` = `keep_or_change` + the cost ratio | → D6l |
| D6l | `retro_notify` | Event Transform | notice to `RESOURCE.sdlc_approvers.G7` (owner and platform decide keep, re-scope or retire): the story, `keep_or_change`, the failure-mode counts, the cost ratio, `needs_human` | → shared delivery |

The tracker PR writes `sdlc/work/<slug>/retro.md`; the person completes it on `improve/<slug>`; `eval-curator` and `skill-curator` run repo-side from there.

### D7 — nudge

| # | Action | Type | Does | Next |
|---|---|---|---|---|
| D7 | `nudge` | Event Transform | notice to `RESOURCE.sdlc_approvers[<open gate>]` (GX falls back to G0 when empty; a parked row to `unpark`): "`<story_key>` has waited <n> days at <gate>; decide it on the tracker Page". Gates never expire (§4.5 rule 1); this only re-notifies | → shared delivery |

### D8 — the failure path of any block

| # | Action | Type | Does | Next |
|---|---|---|---|---|
| D8 | `specialist_failed` | Event Transform | `{story_key, agent, error_category, message}` from whichever block failed (schema failure, action error, timeout, a failed write, missing ops type ids) | → D8a (live) / end (a D10 test) |
| D8a | `mark_failed` | HTTP Request (**Update**, the row; skipped for the planner, which has no row) | `specialist_status: failed` | → D8b |
| D8b | `log_escalation` | HTTP Request (**Create**, `sdlc_events`) | `event_type: escalation`, `agent`, `actor: dispatch`, `actor_kind: story`, `summary` = the message | → D8c |
| D8c | `escalation_notify` | Event Transform | notice to `RESOURCE.sdlc_approvers.GX` (else G0): which agent failed on which story, and that a person must look. **A schema failure or `needs_human: true` always ends with a person** | → shared delivery |

A failed row is not retried automatically (`failed` is not `pending`); a person re-dispatches it by setting `specialist_status: pending` on the row, or opens GX on the Page.

### D9 — the improve check

| # | Action | Type | Does · key options and formulas | Next |
|---|---|---|---|---|
| D9a | `has_ops_types_for_improve` | Trigger | after `sweep_enabled`: `RESOURCE.kit_config.rt_ops_findings` is not 0 | → D9b |
| D9b | `list_recent_findings` | HTTP Request (**List**, `ops_findings` by type id) | findings of severity `high` or `critical` (filtered in D9d until K5) | → D9c |
| D9c | `get_story_credits` | HTTP Request | `GET /api/v1/ai_usage?start_date=<1st of the month>&end_date=<today>&group_by=story` with **`tines_api_readonly`** (K38 for which rows it sees) | → D9d · failure → D9d without the credit condition |
| D9d | `improve_check` | Event Transform | For every row in `operate` (from `list_dispatch_rows`), the Tines-side `improve_trigger` conditions (§4.2): a high or critical `ops_findings` row for its **`prod_story_id`** created after the row's `last_transition_at`; month-to-date credits above **1.5 ×** `credit_estimate_monthly` (`RESOURCE.sdlc_state_machine.thresholds.credit_variance_improve`; custom and local providers are not metered in credits and are skipped); or **a retro due** — first at `live_since` + `retro_after_live_days` (7) while the row's `retro` is empty, then every `retro_cadence_days` (30) after its `last_transition_at`. Emits `candidates[{record_id, story_key, rev, outbox_seq, reason}]`. An eval regression or an owner request is recorded repo-side, not here | → `has_improve_candidates` / `has_no_improve_candidates` |
| D9e | `each_improve` → `write_improve` | explode → HTTP Request (**Update**) | `phase: improve`, `status: active`, `open_gate: none`, `specialist_due: retro-writer`, `specialist_status: pending`, **`pending_repo_sync: true`**, **`pending_base_rev` = the row's `rev`**, `outbox_seq` + 1, `last_actor: improve_check`, `last_transition_at` now | → D9f |
| D9f | `log_improve` | HTTP Request (**Create**, `sdlc_events`) | `event_type: transition`, `from_phase: operate`, `to_phase: improve`, **`decision: improve_trigger`** (what `./scripts/kit tracker-fold` accepts as the explanation of an operate → improve move), `actor: improve_check`, `actor_kind: story`, `summary` = the reason | → D1 `dispatch_in` (`source: "improve"`: `on_enter.improve` → `retro_writer`, and a backlog change → `planner`) |

The move reaches git through the tracker PR; until it merges it is provisional (§6.5).

### D10 — the dev-only test entry

| # | Action | Type | Does | Next |
|---|---|---|---|---|
| D10 | `specialist_test` | **Webhook, dev only** | Body `{agent: "planner" \| "brief_writer" \| "retro_writer", context: {…}}` — `context` carries the same keys as the agent's prompt (the keys `brief_context`, `backlog_snapshot` and `ops_evidence` emit), as the runtime eval cases in `sdlc/evals/agents/runtime-*.cases.yaml` send them. Posted by `./scripts/sdlc eval-run kit-factory --cases … --entry-action specialist_test` (the URL form is **K37**) | → D10a |
| D10a | `is_dev_specialist_test` | Trigger | `RESOURCE.kit_config.environment == "dev"` — it stops in the ops (prod) team | → D10b |
| D10b | `is_brief_writer_test` · `is_planner_test` · `is_retro_writer_test` | Trigger ×3 | `specialist_test.body.agent` equals the agent | → `brief_context` · `backlog_snapshot` · `ops_evidence` |

A test bypasses D2 (it spends dev-team credits, counted by `./scripts/sdlc estimate` as cases × k × credits per run — cost.9) and **stops after the agent and the Trigger after it**: the blocks' `is_test_*` Triggers end the run before any Records write, and D8 writes nothing for a test.

### Shared delivery (the end of every notice)

| Action | Type | Does |
|---|---|---|
| `send_notice_email` | Email | To the notice's `recipients` (approver emails from `sdlc_approvers`, or a submitter for a refusal from section C); subject and body from the notice. Receives from `notify_g0`, `planner_notify`, `retro_notify`, `nudge`, `escalation_notify`, `use_case_refused`, `gate_refused`. **In v1 notifications go by Email**, plus Slack when chosen. No secret, no use-case text, no approver list in the body |
| `is_slack_surface` | Trigger | `RESOURCE.kit_config.chat_surface == "slack"` (and the notice is not a refusal to one submitter) |
| `send_notice_slack` | HTTP Request | Built from the Tines Slack send-message template (the URL comes from the template), `Authorization: Bearer <<CREDENTIAL.slack_bot>>` — the fixed name (K9). Channel: the ops routing channel from `RESOURCE.ops_routing` (the ops trio's Resource). Teams-specific delivery is not in the research: `microsoft_teams` gets email plus a note in the report |

## Cost and safety, restated

- **Tool-less, credential-less agents** (§13 row 7): inputs are data, outputs are proposals, a Trigger on schema fields follows each agent, and a filter removes any Library id outside the catalog.
- **Fast model pinned** on all three (cost.4); the pin is recorded in `../story.meta.yaml` (`model: fast`, `model_pinned: true`).
- **Caps before calls** (D2), a **kill switch** a person sets, a **debounce** for the planner, and **token alerts** (Notify, then Disable action) on each action's Status tab `[BY HAND]`.
- **No model decides whether a model runs** (§12 row 3): only a state change, the weekly planner branch or a scheduled retro starts one.

## Test

The runtime eval cases are the section's tests: `sdlc/evals/agents/runtime-planner.cases.yaml`, `runtime-brief-writer.cases.yaml` and `runtime-retro-writer.cases.yaml`, run with `./scripts/sdlc eval-run kit-factory --cases <file> --entry-action specialist_test` against the dev copy (`sdlc-evals.yml`). `../tests/expectations.yaml` adds the deterministic checks: a D10 post fires the block up to its `*_ok` Trigger and never `save_*`, `*_log_run` or `mark_running`; with `sdlc_limits.enabled: false` a sweep lists nothing; with the cap at 0 a dispatch ends at `log_cap_reached`.

## Verify in your tenant

| Item | What to check |
|---|---|
| K5 · K35 | The v2 search and aggregate bodies (Lists and the daily count) |
| K26 | Whether the model field accepts a formula (per-run model choice) |
| K27 | How a skill attachment appears in the export and whether import keeps it |
| K29 | ARTIFACT capacity for `brief` and `retro` |
| K37 | The Webhook URL form `eval-run` builds for `specialist_test` |
| K38 | Which `ai_usage` rows `tines_api_readonly` sees (D9) |
| scaffold #8 · #14 | The event `meta` token keys; skill attachment |
