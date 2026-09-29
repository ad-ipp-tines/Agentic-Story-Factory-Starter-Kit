# Section C — tracker Pages and App endpoints

_Spec: REPO-DESIGN.md §7.5 (this section), §7.8 (the Page specs), §9 (dashboard by entitlement), §4.5 (gates and their instruments), §13 row 6. Part of `[KIT] 00 · Launch Storyworks`. Built through Mode 2 by build prompt **P-K13** (`../build-prompts.md`), together with section E and the four tracker Pages. Records calls follow the rules in [`B-tracker-sync-in.md`](B-tracker-sync-in.md) ("Records access in sections B–E")._

**What it does.** It is the tracker's human surface inside Tines. A root Page (`tracker_home`) leads to a snapshot view of the backlog (the Page dashboard), a form to add a use case, and a form to decide the **Tines-side gates** — G0, G6, G7, GX and an unpark (GB release). Every decision is checked against the approvers list in the `storyline_approvers` Resource, written to the row as a **provisional** change (`pending_repo_sync: true`), logged, and handed to section D; it reaches git only through the next tracker PR a person merges (§6.5, Flow 2). When Apps are entitled, three **App endpoints** expose the same chains to the App.

**What it never does.** It never decides G1, G2, G3, G4, G5a or G5b — they are a script, merges, a build-session command, a GitHub environment review and a change request (§4.5). It never writes to GitHub. It never shows an approver's email outside the tenant: `storyline_events.actor` is a role, and the email stays in `actor_ref`, which the outbox never returns.

## Entry points

| Entry | Action | Type | Settings |
|---|---|---|---|
| The tracker | `tracker_home` | **Page, root** | URL identifier `storyworks-tracker`; access **Only team members**; submissions not anonymised; submission mode **Move to next page** (K31 for actions between Pages). Spec: [`../pages/tracker-home.md`](../pages/tracker-home.md) |
| App: add a use case | `app_add_use_case` | Webhook (App endpoint) | Apps only. Wired to the App `[BY HAND]` (Interfaces → App endpoints); secret rotated after import (K8). Contract: `kit/dashboard/app/endpoints.md` |
| App: decide a gate | `app_gate_decision` | Webhook (App endpoint) | Apps only; **refuses every call until K18 confirms the endpoint receives the viewer's identity** (below) |
| App: costs | `app_costs` | Webhook (App endpoint) | Apps only |

App endpoints answer within **30 s** (under 1 s is recommended) through a **message-only Event Transform exit**; each endpoint below has a success exit and an error exit, and the first exit reached answers. How an App calls an endpoint, and how exits are wired, are **K18**.

## The actions

| # | Action | Type | Does · key options and formulas | Next |
|---|---|---|---|---|
| C1 | `tracker_home` | Page (root) | Heading, intro, counts (no Records only), four Buttons with submission values `view`, `add`, `gate`, `milestones` | → C2 |
| C2 | `route_button_view` · `route_button_add` · `route_button_gate` · `route_button_milestones` | Trigger ×4 | `tracker_home.body.button` equals `view` / `add` / `gate` / `milestones`. (§7.5 names the group `route_button`; each Trigger carries its value.) No match → the run ends | view, milestones → C3 · add → C4 · gate → C5 |
| C3 | `has_records_view` / `has_mirror_view` | Trigger ×2 | `RESOURCE.kit_config.entitlements.records` true / false | Records → `list_rows` · no Records → `tracker_view` (renders `RESOURCE.kit_tracker_view`) |
| C3a | `list_rows` | HTTP Request (**List**, `storyline_backlog`) | Up to 500 rows (K5: no server-side filter yet) | → C3b |
| C3b | `list_view_milestones` | HTTP Request (**List**, `storyline_milestones`) | three rows | → C3c |
| C3c | `to_table` | Event Transform, message-only | Emits `stories_csv` (header `key,title,phase,status,open_gate,owner,target_date,credit_estimate_monthly`; one row per story, sorted by phase order then key; `target_date` as `YYYY-MM-DD`; values quoted), `milestones_csv` (header `id,title,status,due_date`; day-1, week-1, week-4), `counts_by_phase` (one number per phase in `RESOURCE.storyline_state_machine.all_phases` order, zeros included), `open_gates_md` (`<key> — <gate>: decided by <RESOURCE.storyline_state_machine.gate_decided_by[gate]>`). The formula functions that build CSV text are **K32** | → C3d |
| C3d | `tracker_view` | Page (mid-story) | Chart (bar: stories per phase), Table (`CSV_PARSE(to_table.stories_csv)`), Table (milestones), open gates and who decides each, Back. Per-run URL `PAGE.tracker_view`. Spec: [`../pages/tracker-view.md`](../pages/tracker-view.md) | end (Back redirects to `tracker_home`) |
| C4 | `add_use_case` | Page (mid-story) | `title`, `use_case`, `owner_role`, `target_date`, `library_seed_id` (catalog ids + `none`), `mode_hint`. Spec: [`../pages/add-use-case.md`](../pages/add-use-case.md) | → C4a |
| C4a | `normalize_use_case` | Event Transform | Reads `DEFAULT(add_use_case.body.<f>, app_add_use_case.body.<f>)`; trims; `source` = `add_use_case_page` or `app`; `submitter_email` from the Page headers (Page path only); `mode` = `mode_hint`, with `unknown` stored as `none` (the tracker has no `unknown` mode; design sets the real one); `target_date` as UTC `Z` or empty; `library_seed_id` null for `none`; `key_candidate` = the title lowercased and hyphenated, ≤ 48 characters | → C4b / C4c |
| C4b | `is_valid_use_case` | Trigger (all rules) | `title`, `use_case` and `owner_role` present · `owner_role` contains no `@` (owners are roles) · no field matches a token pattern (`ghp_`, `github_pat_`, `gho_`, `ghs_`, `xox[bp]-`, `sk-`, `AKIA`, `Bearer ` — the same list as A3) · `library_seed_id` is null or in `RESOURCE.kit_catalog.seed_ids` · `mode` is one of `RESOURCE.storyline_state_machine.enums.mode` | → C4d |
| C4c | `is_invalid_use_case` → `use_case_refused` | Trigger → Event Transform | `{status: "refused", reason}` — which rule failed, never the offending value | Page → `send_notice_email` to the submitter (section D's shared delivery) · App → `app_add_use_case_error` |
| C4d | `list_keys_for_use_case` | HTTP Request (**List**, `storyline_backlog`) | the existing keys, for the collision check | → C4e |
| C4e | `assign_use_case_key` | Event Transform | `story_key` = the candidate, or `-2`, `-3`… on a collision (the rule A2 uses for custom rows) | → C4f |
| C4f | `use_case_create_row` | HTTP Request (**Create**, `storyline_backlog`) | `story_key`, `title`, `use_case` (untrusted text, stored only), `owner`, `mode`, `library_seed_id`, `target_date`, `tier: production`, `phase: intake`, `status: active`, `open_gate: none`, `attempt: 0`, **`specialist_due: brief-writer`** (when `RESOURCE.kit_config.entitlements.ai_agent_action`) else `none`, `specialist_status: pending` / `idle`, **`pending_repo_sync: true`, `pending_base_rev: 0`, `rev: 0`**, `outbox_seq: 1`, `acked_seq: 0`, `last_actor` = the owner role, `last_transition_at` now (UTC). (§7.5 names this `create_row`; section B has its own) | → C4g · failure → Page: `use_case_refused` path with `reason: "the tracker could not be written; try again"` · App: `app_add_use_case_error` |
| C4g | `use_case_log_event` | HTTP Request (**Create**, `storyline_events`) | `event_type: transition`, `from_phase: none`, `to_phase: intake`, `actor` = the owner role, `actor_kind: human`, `actor_ref` = the submitter's email (in-tenant audit only; never sent to git), `summary: "use case added from <source>"` | → D1 `dispatch_in` (`source: "page"` or `"app"`) and → `is_app_use_case` |
| C4h | `is_app_use_case` → `app_add_use_case_result` | Trigger → Event Transform (**exit**, message-only) | `normalize_use_case.source == "app"` → `{status: "ok", story_key, phase: "intake", provisional: true}` | App answer |
| C5 | `list_open_gates` | HTTP Request (**List**, `storyline_backlog`) | Rows with `open_gate` in G0, G6, G7, GX, or `phase: parked` — filtered in `open_gate_options` until K5 | → C5a |
| C5a | `open_gate_options` | Event Transform | `{rows: [{story_key, record_id, title, phase, status, open_gate, rev, outbox_seq}], keys: [story_key…]}` — the Option list for the Page's `story_key` | → C5b |
| C5b | `gate_decision` | Page (mid-story) | `story_key`, `gate` (`G0 \| G6 \| G7 \| GX \| unpark`), `decision` (filtered by gate), `note`. Access **Via SSO**, restricted to the approvers SSO group where the tenant supports it. Spec: [`../pages/gate-decision.md`](../pages/gate-decision.md) | → C5c |
| C5c | `gate_identity` | Event Transform | `{caller_email, story_key, gate, decision, note, source}`. **Page path:** `caller_email` = the submitter's email from the `gate_decision` Page headers. **App path:** the viewer's identity from the endpoint, **if** it receives one (**K18**); otherwise null — and the App path first lists the row with `app_gate_rows` (HTTP Request, **List**, `storyline_backlog`), since it has no `open_gate_options`. `gate` `unpark` is recorded as gate `GB`, decision `unpark` | → C5d / `is_not_approver` |
| C5d | `is_approver` / `is_not_approver` | Trigger ×2 | `caller_email` is not null **and** is in `RESOURCE.storyline_approvers[<gate>]` (`unpark` uses `storyline_approvers.unpark`). **Authority comes from the Resource, never from chat or a request body** (§4.5 rule 2) | → C5e |
| C5e | `is_gate_open` / `is_gate_closed` | Trigger ×2 | the chosen row's `open_gate` equals `gate` (for `unpark`: the row's `phase` is `parked`) — read from `open_gate_options.rows` (Page) or a fresh **List** filtered by key (App) | → C5f |
| C5f | `list_gate_history` → `apply_decision` | HTTP Request (**List**, `storyline_events` by `story_key`) → Event Transform | `list_gate_history` gives the transitions `$previous` needs. `apply_decision` looks up `RESOURCE.storyline_state_machine.page_decision_table["<gate>:<decision>"]` (or `["unpark"]`) and picks the entry whose `from` matches the row's phase (`*` matches any non-terminal phase; `$previous` for unpark reads the last `to_phase` before `parked` from `list_gate_history`). Emits `{found, to_phase, to_status, to_open_gate, reset_attempt}`; `to_open_gate` is `none` except where the table's `then` opens the next gate | → C5g · the complements `is_not_approver`, `is_gate_closed`, `has_no_valid_transition` → C5k |
| C5g | `has_valid_transition` / `has_no_valid_transition` | Trigger ×2 | `apply_decision.found` is true and the decision is in `RESOURCE.storyline_state_machine.gate_decisions[<gate>]` | → C5h |
| C5h | `gate_update_row` | HTTP Request (**Update**, the row's id) | `phase`, `status`, `open_gate` (and `attempt: 0` when `reset_attempt`), **`pending_repo_sync: true`**, **`pending_base_rev` = the row's `rev`**, **`outbox_seq` = the row's `outbox_seq` + 1**, `last_actor` = `<gate>-approver` (a role), `last_transition_at` now. `rev` is **never** changed here: only git bumps it. (§7.5 names this `update_row`; section B has its own) | → C5i · failure → C5k |
| C5i | `gate_log_event` | HTTP Request (**Create**, `storyline_events`) | `event_type: gate_decision`, `gate`, `decision`, `from_phase`, `to_phase`, `actor` = `<gate>-approver` (**a role**), `actor_ref` = `caller_email` (in-tenant audit only), `actor_kind: human`, `summary` (the note, trimmed to 512 characters; a note is untrusted text) | → D1 `dispatch_in` (`source: "gate"`) and → `is_app_gate` |
| C5j | `is_app_gate` → `app_gate_decision_result` | Trigger → Event Transform (**exit**) | `{status: "ok", story_key, from_phase, to_phase, provisional: true}` | App answer |
| C5k | `gate_refused` | Event Transform | `{status: "refused", reason}` for: no identity (App, until K18), not an approver, gate not open, no valid transition, or a failed write. Page path → `send_notice_email` to the submitter · App path → `app_gate_decision_error` | end |
| C6 | App endpoints | Webhook entries → the chains above → exits | `app_add_use_case` → C4a … → `app_add_use_case_result` / `app_add_use_case_error`. `app_gate_decision` → C5c … → `app_gate_decision_result` / `app_gate_decision_error`. **`app_costs`** → `costs_window` (Event Transform: `start_date` = the 1st of this month, `end_date` = today, tenant time) → `get_app_costs` (HTTP Request: `GET /api/v1/ai_usage?start_date=…&end_date=…&group_by=story` — the `relative_date=…` form also exists — with **`tines_api_readonly`**, which sees only what that key may see, **K38**) → `app_costs_result` (exit: `{status: "ok", from, to, rows: [{story_id, story_key, credits_used, billed_cost}]}`) · failure → `app_costs_error` | App answers |

`app_add_use_case_error`, `app_gate_decision_error` and `app_costs_error` are message-only Event Transform exits returning the scaffold's failure shape `{status: "error", error_category, retryable, message}` (or `{status: "refused", reason}` from a guard). `credits_used` and `billed_cost` are **never summed** (AGENTS.md §8).

## Why the App does not decide gates in v1

`is_approver` needs the caller's email. A Page submission carries it in the headers; whether an App endpoint receives the viewer's identity is **K18**. Until it is confirmed, `gate_identity` sets `caller_email` to null for every App call, `is_approver` never passes, and the endpoint answers `{status: "refused", reason: "caller identity unavailable"}` — it **never** falls back to trusting a field in the request body. The App's "Decide" button deep-links to `tracker_home` → **Decide a gate** instead (`kit/dashboard/app/lib/tracker.ts`).

## What a decision changes (the page decision table)

The table is `RESOURCE.storyline_state_machine.page_decision_table`, generated from `storyline/lifecycle/state-machine.yaml` by `./scripts/kit bundle` and kept current by `kit-sync.yml` — never typed here. The Page's options are `page_options`:

| Gate | Decisions | Typical effect |
|---|---|---|
| G0 | `build` · `reject` · `park` | intake → discover · rejected · parked |
| G6 | `go_live` · `stay_shadow` | operate/shadow → operate/live · stays shadow |
| G7 | `keep` · `rescope` · `retire` | stays operate · → design (attempt 0) · → retired |
| GX | `resume` · `park` · `reject` | back to the status before `blocked` (at the rework cap: build/rework, attempt 0) · parked · rejected |
| `unpark` (GB release) | `unpark` | parked → the phase and status held before |

## Test

`../tests/expectations.yaml`, section C: the Pages cannot be posted, so they are checked by hand in the dev copy (the listed manual checks); the App endpoints can: `app_add_use_case_happy` (creates one intake row with `pending_repo_sync: true`, answers `status: ok`, dispatches to D), `app_add_use_case_token` (refused, no Records write), `app_gate_decision_refused` (refused until K18), `app_costs` (answers `status: ok` with `rows[]`). The Page chains are exercised through the same actions.

## Verify in your tenant

| Item | What to check |
|---|---|
| K5 | Server-side filters for `list_rows`, `list_open_gates`, `list_keys_for_use_case` |
| K8 | `storyworks-tracker` after import; every endpoint Webhook's secret (rotate) |
| K18 | App endpoint calls, exits and the viewer's identity |
| K31 | Page element conditions; Option lists from upstream data and Resources; "Move to next page" with actions between Pages; the submitter header key |
| K32 | CSV text for the Table element |
| K38 | Which `ai_usage` rows `tines_api_readonly` sees |
| K40 | Locking `storyline_approvers` where the `gate_decision` Page cannot be restricted to an SSO group |
