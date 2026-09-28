# Section B — tracker sync in (repo → Records)

_Spec: REPO-DESIGN.md §6.5 (Flow 1, field ownership, conflicts), §7.4 (this section), §8.1 (Record types), §13 row 5. Part of `[KIT] 00 · Run the story factory`. Built through Mode 2 by build prompt **P-K12** (`../build-prompts.md`), with **every Records read and write as an HTTP Request action to the Records API** — no Record actions anywhere in sections B–E._

**What it does.** Git is the system of record. When a merge to `main` changes `kit/tracker/**` (and once a night in full), `tracker-sync.yml` runs `./scripts/kit tracker-json --push`, which POSTs the tracker as JSON to this section's Webhook. Section B takes a compare-and-swap lock, lists the `sdlc_backlog` rows, and for each entry creates the row, updates it, or records a conflict. It clears a Tines-side pending change only once a merge after that change has reached `main`, logs every phase change as an `sdlc_events` transition, and passes it to section D. Without Records it writes the `kit_tracker_view` mirror instead.

## Records access in sections B–E (applies to every file B–E)

- **Only HTTP Request actions** with `tines_api_kit` (`Authorization: Bearer <<CREDENTIAL.tines_api_kit>>`) to `https://<<RESOURCE.kit_config.tenant_host>>/api/…`. The record types do not exist when the story is imported (A18 creates them afterwards), so a Record action could not resolve them, and re-pointing one would be a Mode 2 edit of the live, change-controlled kit story; the API needs neither (K6 does not apply to B–E).
- **Types and fields by id:** `RESOURCE.kit_state.rt_<type>` and `RESOURCE.kit_state.fields_<type>.<field>` (written by A18). The ops trio's types by the ids in `RESOURCE.kit_config` (`rt_ops_findings`, `rt_ops_alerts`).
- **The calls**, named as in §7.4:

| Name in the tables | Call | Body |
|---|---|---|
| **List** | `POST /api/v2/records/search` | request body **K5** (only the path is in the research), including filters by field id. **Fallback:** `GET /api/v1/records`, whose `filters` are documented |
| **Query** (count) | `POST /api/v2/records/aggregate` | request body **K35**. **Fallback:** `POST /api/v1/records/query`, or a counter in `kit_state` (compare-and-swap) |
| **Create** | `POST /api/v1/records` | `{record_type_id, field_values: [{field_id, value}, …]}`, `test_mode` off (K39) |
| **Update** | `PUT /api/v1/records/{id}` | `{field_values: [{field_id, value}, …]}` — only the fields that change (the exact update body is confirmed with K16's scratch type) |

- **Until K5 is confirmed, every List lists without a server-side filter** (page size 500, the Records API maximum) and the next Event Transform filters. The tracker holds at most 1,000 rows (`max_records_limit`), and the Records API allows 400 requests a minute (Query 200).
- **Timestamps** are sent in UTC with `Z` (Records drop offsets). `JSON` fields are not filterable.
- **HTTP hardening** as section A (`retry_on_status [429, 500-599]`, retries 6, emit failure event Always, a failure path).

## Entry

| Action | Type | Settings |
|---|---|---|
| `tracker_sync_in` | **Webhook** | Access control **Secret** (the Webhook levels are Public, Secret, Team and Tenant); **Include headers off**. Its URL carries the secret and lives only in the GitHub environment `tracker` as `TRACKER_SYNC_URL` — never in `.env`, never in the report. **Rotate the secret after import** (K8), then copy the URL (setup report, item 13) |

**The body** (`./scripts/kit tracker-json`; example: `../tests/samples/tracker-sync.sample.json`):

```json
{ "schema_version": 1, "source_sha": "<40-hex commit on main>", "full": false,
  "entries": [ { "story_key": "…", "title": "…", "phase": "…", "rev": 3, "…": "Record field names, UTC timestamps, empty values as null" } ],
  "milestones": [ { "milestone_id": "day-1", "status": "…", "rev": 1, "…": "…" } ],
  "view": { "…": "the kit_tracker_view value (used only without Records)" } }
```

`full: true` on the nightly run. Entry keys are **Record field names** (`kit/tracker/field-map.yaml`); only git-owned and Tines-owned fields travel, never the Tines-only ones (`pending_repo_sync`, `outbox_seq`, `specialist_status`, …).

## The actions

| # | Action | Type | Does · key options and formulas | Next · on failure |
|---|---|---|---|---|
| B1 | `tracker_sync_in` | Webhook | above | → B2 |
| B2 | `sync_kill_switch` | Trigger | `RESOURCE.sdlc_limits.enabled` is true. (§7.4 names this `kill_switch`; section D has the other one, so each carries its section's prefix — action names are unique in a story.) Until a person enables the runtime specialists, the tracker sync is held too (§7.2) | pass → B3 · no pass → the run ends; the next push or the nightly full run re-sends the whole state |
| B3 | `normalize_payload` → `is_valid_payload` / `is_invalid_payload` | Event Transform → Trigger ×2 | `normalize_payload`: `DEFAULT()` on every key; `lock_value = STORY_RUN_GUID()`; `full = DEFAULT(tracker_sync_in.body.full, false)`. `is_valid_payload`: `schema_version == 1` · at most **500** entries · every `story_key` matches `^[a-z0-9-]{1,64}$` · every `phase`, `status`, `open_gate`, `mode`, `tier`, `provider` value is in `RESOURCE.sdlc_state_machine` (`all_phases`, `statuses`, `open_gate_values`, `enums`) · `source_sha` is 7–40 hex characters | valid → B4 · invalid → `sync_rejected` (Event Transform: which rule failed, no values) → `log_sync_rejected` (Create `sdlc_events`: `event_type: sync`, `decision: rejected`, `actor: tracker-sync`, `actor_kind: ci`) → end |
| B4 | `acquire_sync_lock` | HTTP Request | `POST /api/v1/global_resources/<<RESOURCE.kit_state.res_sdlc_sync_lock>>/replace` `{key: "lock", value: <<normalize_payload.lock_value>>, if_value: "free"}`. **422 is excluded from `log_error_on_status`** (another sync or `kit-sync.yml` holds it) | 200 → `has_sync_lock` → B4a · 422 → `is_locked` → `sync_busy` (Event Transform, `{status: "busy"}`) → end: the next push or the nightly run re-sends the full state |
| B4a | `has_records_sync` / `has_mirror_sync` | Trigger ×2 | `RESOURCE.kit_config.entitlements.records` true / false | Records → B5 · no Records → B10 |
| B5 | `list_backlog` | HTTP Request (**List**, `sdlc_backlog`) | Up to 500 rows. Server-side filtering is K5; this action lists everything and B6 filters | → B6 · failure → `sync_failed` |
| B6 | `plan_upserts` | Event Transform | Per entry, matched on `story_key`, chooses one action (table below), sets `transition: {from_phase, to_phase}` when the phase changes (a new row is a transition from `none`), and builds the `field_values` by field id. Emits `{upserts: [{story_key, action, record_id, field_values, transition, row}], conflicts: [...]}` (a `noop` is left out) | → `has_upserts` → B7 · `has_no_upserts` → B9 |
| B7 | `each_upsert` → `is_create_row` → `sync_create_row` · `is_update_row` → `sync_update_row` | Event Transform (explode) → Triggers → HTTP Request (**Create** / **Update**) | Writes the row by type and field id, so no record-type reference needs re-pointing after import. (§7.4 names these `create_row` / `update_row`; section C has its own, so B's carry the `sync_` prefix.) `update_repo_fields_only` is an Update whose `field_values` hold only git-owned fields | → B8 · failure → `sync_failed` |
| B7a | `is_conflict_row` → `log_sync_conflict` | Trigger → HTTP Request (**Create**, `sdlc_events`) | `event_type: conflict`, `decision: kept_tines_pending` or `kept_git`, `actor: tracker-sync`, `actor_kind: ci`, `summary` naming the fields, `source_sha` | end of that branch |
| B8 | `has_transition` → `log_transition` | Trigger → HTTP Request (**Create**, `sdlc_events`) → **section D** | `event_type: transition`, `from_phase`, `to_phase`, `actor: tracker-sync`, `actor_kind: ci`, `tracker_rev` = the entry's `rev`, `source_sha`, `summary`. After the log, the event goes to D1 `dispatch_in` as `{source: "sync", story_key, record_id, rev, phase, status, open_gate, specialist_due, row}` | → D1 · the log failing does not stop the dispatch (the dispatch link leaves from `has_transition`) |
| B8a | `upserts_done` | Event Transform (implode) | joins the upsert branches (keyed on the run guid, sized by `upserts[]`) | → B9 |
| B9 | milestones: `sync_list_milestones` → `plan_milestone_upserts` → `has_milestone_upserts` / `has_no_milestone_upserts` → `each_milestone_upsert` → `is_create_milestone` → `sync_create_milestone` · `is_update_milestone` → `sync_update_milestone` → `milestones_done` | HTTP Request (**List**, `sdlc_milestones`) → Event Transform → Trigger ×2 → explode → Trigger ×2 → HTTP Request (**Create** / **Update**) → implode | The same pattern for `sdlc_milestones`, keyed on `milestone_id`. `status`, `due_date`, `evidence_ref` and `owner` are Tines-owned; `title`, `criteria` and `rev` are git-owned. The milestone type has no `pending_base_rev`: a pending milestone clears when git's `rev` is above the Record's `rev` (a Tines-side write never bumps `rev`) | → B11 · failure → `sync_failed` |
| B10 | `update_tracker_view` | HTTP Request | **Only without Records.** `PUT /api/v1/global_resources/<<RESOURCE.kit_state.res_kit_tracker_view>>` with the whole value `<<normalize_payload.view>>` (the body key for a whole-value PUT is confirmed at build). Safe **only under the lock**, because whole-value writes lose concurrent updates | → B11 · failure → `sync_failed` |
| B11 | `release_sync_lock` | HTTP Request | `…/<<RESOURCE.kit_state.res_sdlc_sync_lock>>/replace` `{key: "lock", value: "free", if_value: <<normalize_payload.lock_value>>}` (422 excluded: already released). **Also runs on every failure branch** | end |
| — | `sync_failed` | Event Transform | `{status: "error", error_category, retryable, message}` (the scaffold's failure shape; `error_category` from the status: `auth` 401, `permission` 403, `rate_limit` 429, `upstream_5xx`, `validation` 4xx, `unknown`) | → B11 → end. `monitor_failures` pages the ops router with the failed action |

## B6 — the upsert decision

For each entry (repo row `R`, stored row `S`, both with `rev`):

| Case | Action | What is written |
|---|---|---|
| no `S` | `create` | every mirrored field of `R`; `pending_repo_sync: false`, `pending_base_rev: R.rev`, `outbox_seq: 0`, `acked_seq: 0`, `specialist_due` from `runtime_dispatch.on_enter[R.phase]` (`brief-writer` for intake, `retro-writer` for improve, else `none`), `specialist_status: pending` when due else `idle`, `last_actor: tracker-sync`, `last_transition_at` now |
| `R.rev > S.rev` and `S.pending_repo_sync` is false | `update` | every git-owned field that differs, and every Tines-owned field that differs (git wins once the row is not pending) |
| `R.rev > S.rev` and `S.pending_repo_sync` is true and `R.rev > S.pending_base_rev` | `update` | as above, **and** `pending_repo_sync: false` — a merge made after the Tines-side write has reached `main`, so git's values now include (or have deliberately replaced) it. Tines-owned fields are overwritten with git's values |
| `R.rev > S.rev` and `S.pending_repo_sync` is true and `R.rev ≤ S.pending_base_rev` | `update_repo_fields_only` | only the git-owned fields that are not state fields; the Tines-side pending change (phase/status/open_gate from a Tines gate, owner, target_date) is kept until its tracker PR merges |
| `R.rev == S.rev`, same values | `noop` | — (equal revs never clear a pending change) |
| `R.rev < S.rev`, or `R.rev == S.rev` with different git-owned values | `conflict` | nothing; B7a logs it. The nightly snapshot (E5) and `sdlc check` surface it as a `tracker-drift` PR |
| **nightly** (`full: true`) and `S.pending_repo_sync` is false and any value differs | `update` | git's values, **whatever the revs** — git wins (§6.5) |

Field ownership is `kit/tracker/field-map.yaml` (`git` · `tines` · `tines-only`); `plan_upserts` never writes a Tines-only field except the bookkeeping above.

## Why the lock, and why here

Record creation is not idempotent, so list-then-create must not run twice at once. The same `sdlc_sync_lock` is taken by `kit-sync.yml` when it pushes the generated Resources. A 422 is never an error: the losing run exits quietly, and the state is re-sent in full by the next push or the nightly run.

## Test

`../tests/expectations.yaml`, variant `tracker_sync_create`: post `../tests/samples/tracker-sync.sample.json` to `tracker_sync_in` in the dev copy (with `sdlc_limits.enabled: true` in the dev team) — `acquire_sync_lock`, `list_backlog`, `plan_upserts`, `sync_create_row` ×3, `log_transition` ×3, `release_sync_lock` fire; the lock reads `free` afterwards. Posting the same body again creates nothing (`noop`). Variants `tracker_sync_locked` (lock held → `sync_busy`, no List) and `tracker_sync_invalid` (a key with a capital letter → `sync_rejected`, no lock taken).

## Verify in your tenant

| Item | What to check |
|---|---|
| K5 | The v2 search body and filters; until then the full List + B6 filter |
| K16 | Field-id maps from A18; the Update body |
| K39 | API-created Records are live in the change-controlled story |
| K8 | The Webhook secret after import (rotate first) |
