# Section E — tracker outbox (Records → repo, pulled by GitHub)

_Spec: REPO-DESIGN.md §6.5 (Flow 2, conflicts and provisional state, the nightly snapshot), §7.7 (this section), §8.2 (`kit_state.hash_<name>`, `resources_in_sync`), §13 rows 3 and 5. Part of `[KIT] 00 · Launch Storyworks`. Built through Mode 2 by build prompt **P-K13** (`../build-prompts.md`), with section C. Records calls follow [`B-tracker-sync-in.md`](B-tracker-sync-in.md) ("Records access in sections B–E")._

**What it does.** Decisions made in Tines — a G0 on the Page, a brief or a retro draft, an accepted planner proposal, the D9 move to improve — are written to Records as **pending** (`pending_repo_sync: true`). They become git only when a person merges a tracker PR. Section E is how the repository fetches them: `tracker-pull.yml` POSTs to this section's **response-enabled** Webhook every 30 minutes, and the answer carries every pending change. **The kit story never writes to GitHub after day 1** (§13 row 3): the repository pulls, `./scripts/kit tracker-fold` turns the answer into YAML and files, and the PR is opened with the `tracker-bot` GitHub App token, never `GITHUB_TOKEN`.

## Entry

| Action | Type | Settings |
|---|---|---|
| `tracker_outbox` | **Webhook, response-enabled** | Access control **Secret**; Include headers off. **The answer is the first Exit action's output, within 30 s**; whether ≤ 500 rows fit in 30 s, and the response size limit, are **K15** (chunk the pull if the dev load test shows a limit). Its URL carries the secret and lives only in the GitHub environment `tracker` as `TRACKER_OUTBOX_URL`. **Rotate the secret after import** (K8) |

**The request:** `{op: "pull" | "ack" | "snapshot", items?: [{key, outbox_seq}], open_pr_keys?: [key, …]}` — sent by `./scripts/kit tracker-fold --pull`, `--ack SUMMARY` and `--snapshot --open-pr-keys …` (`tracker-pull.yml`).

## The actions

| # | Action | Type | Does · key options and formulas | Next |
|---|---|---|---|---|
| E1 | `tracker_outbox` | Webhook (response-enabled) | above | → E2 |
| E2 | `route_op_pull` · `route_op_ack` · `route_op_snapshot` · `route_op_unknown` | Trigger ×4 | `tracker_outbox.body.op` equals `pull` / `ack` / `snapshot` / anything else. (§7.7 names the group `route_op`) | pull → E3 · ack → E4 · snapshot → E5 · unknown → `outbox_error` (`validation`) |
| E3a | `list_pending` | HTTP Request (**List**, `storyline_backlog`) | Rows with `pending_repo_sync: true` **and** `outbox_seq > acked_seq` (filtered in `shape_outbox` until K5) | → E3b · failure → `outbox_error` |
| E3b | `list_pending_milestones` | HTTP Request (**List**, `storyline_milestones`) | Rows with `pending_repo_sync: true` | → E3c |
| E3c | `list_outbox_events` | HTTP Request (**List**, `storyline_events`) | The Tines-side events of the pending keys: `actor_kind` `human`, `agent` or `story` (never `ci`: those came from git through B8) | → E3d |
| E3d | `shape_outbox` | Event Transform, message-only, **Exit** | Returns `{items[], milestones[], events[]}` (shape below). Only fields git may take from Tines travel: the Tines-owned fields and, through a Tines-side gate or D9, `phase`/`status`/`open_gate`; a row created in Tines (`rev: 0`) carries every mirrored field so it can be created in git. **Never `actor_ref` and never an email**: events carry the role in `actor` | the Webhook's answer |
| E4a | `list_for_ack` → `ack_plan` | HTTP Request (**List**) → Event Transform | maps each `{key, outbox_seq}` of the request to the row's record id, keeping only items whose stored `outbox_seq` equals the one acked (a newer Tines-side write since the pull is not acked, so it is sent again) | → `has_acks` / `has_no_acks` |
| E4b | `each_ack` → `set_acked` | explode → HTTP Request (**Update**) | `acked_seq = outbox_seq`. **`pending_repo_sync` is not cleared here**: it clears only when Flow 1 brings a `rev` above `pending_base_rev` back (B6) | → `acks_done` (implode) |
| E4c | `ack_exit` | Event Transform, **Exit** | `{status: "ok", acked: [key…]}` (also reached directly from `has_no_acks`) | the answer |
| E5a | `list_snapshot_rows` → `reset_plan` | HTTP Request (**List**) → Event Transform | For every pending row whose key is **not** in `open_pr_keys` **and** whose Tines-side write (`last_transition_at`) is older than `RESOURCE.storyline_limits.pending_reset_hours` (default 24): a reset. These are Tines-side changes whose tracker PR was closed or abandoned | → `has_resets` / `has_no_resets` |
| E5b | `each_reset` → `reset_abandoned` | explode → HTTP Request (**Update**) | `pending_repo_sync: false`. The nightly full Flow 1 run then overwrites the row with git's values wherever they differ — **git wins** | → `resets_done` (implode) → E5c |
| E5c | `list_all` → `list_all_milestones` | HTTP Request ×2 (**List**) | every row (after the resets) and every milestone | → E5d |
| E5d | `snapshot_exit` | Event Transform, **Exit** | `{rows: [...], milestones: [...], hashes: {hash_storyline_state_machine, hash_kit_catalog, hash_kit_config, hash_storyline_limits}, reset: [key…]}` — rows in the same field form as `shape_outbox`'s items, `hashes` from `RESOURCE.kit_state.hash_<name>` (written by `kit-sync.yml`). Used by the nightly drift comparison (`tracker-fold --snapshot`, a `tracker-drift` PR on divergence) and by the `resources_in_sync` check | the answer |
| — | `outbox_error` | Event Transform, **Exit** | `{status: "error", error_category, retryable, message}` — the scaffold's failure shape | the answer |

## The pull answer (`shape_outbox`)

Example: [`../tests/samples/outbox-response.sample.json`](../tests/samples/outbox-response.sample.json).

```json
{
  "items": [
    { "key": "<slug>", "base_rev": 1, "outbox_seq": 2, "source": "kickoff_page | add_use_case_page | app",
      "changes": { "<Record field name>": "<value>" },
      "brief_md": "<the row's brief, when a brief_writer draft is pending>",
      "retro_md": "<the row's retro, when a retro_writer draft is pending>" }
  ],
  "milestones": [ { "milestone_id": "day-1", "base_rev": 1, "changes": { "status": "in_progress" } } ],
  "events": [ { "story_key": "<slug>", "event_type": "gate_decision", "gate": "G0", "decision": "build",
                "actor": "G0-approver", "actor_kind": "human", "created_at": "…", "…": "Record field names" } ]
}
```

| Key | Value |
|---|---|
| `base_rev` | the row's **`pending_base_rev`** (the `rev` when the Tines-side change was written). `tracker-fold` marks a conflict when an item's `base_rev` is below the repo's `rev` **and** the same field changed in git since |
| `outbox_seq` | the row's `outbox_seq`; `tracker-pull.yml` acks it after the PR is opened (E4) |
| `changes{}` | Record field names (`kit/tracker/field-map.yaml`). Tines-owned fields that differ from what git last sent (`owner`, `target_date`), and `phase`/`status`/`open_gate` when a Tines-side gate (G0, G6, G7, GB release, GX) or D9 moved them. A row with `rev: 0` (created in Tines: the kickoff's picks, `add_use_case`, the App) carries every mirrored field |
| `brief_md` · `retro_md` | the `brief` / `retro` ARTIFACT, when present and proposed. `tracker-fold` writes `storyline/work/<slug>/intake.md` or `retro.md` — never over a person's work |
| `source` | where a Tines-created row came from (`intake.md`'s front matter) |
| `events[]` | Record field form, **without `actor_ref`, `input_tokens` or `output_tokens`** (Tines-only). `tracker-fold` accepts a phase change only when an event explains it: a `gate_decision` with `actor_kind: human` for a Tines-side gate, a `specialist_run` of `brief_writer` for G0 opening in intake, or a `transition` with `decision: improve_trigger` for operate → improve |

## Why the repository pulls

The GitHub token is needed only for provisioning, so it can be short-lived and then revoked (§13 row 2); only GitHub-documented endpoints are used; and the step that turns data into YAML runs in the repository (`./scripts/kit tracker-fold`), not in Tines formulas (§6.5). The PR is opened with the `tracker-bot` App's installation token because GitHub starts no `pull_request` workflows for a PR opened with `GITHUB_TOKEN`, and `storyline.yml` — the one required check — would never report.

## Provisional state, stated plainly

A Tines-side transition is **provisional** until its tracker PR merges. A closed or abandoned PR is reset by E5 after `pending_reset_hours`, and the nightly full sync then restores git's values. Two tracker PRs cannot both land a row's change: `storyline.yml` requires every changed row's `rev` to be `main`'s rev + 1, so the second one rebases.

## Test

`../tests/expectations.yaml`, section E: `outbox_pull` (with one pending row and one pending milestone in the dev copy, the answer has `items`, `milestones` and `events` in the sample's shape and no `actor_ref` anywhere), `outbox_ack` (acking `{key, outbox_seq}` sets `acked_seq`, a second pull omits the item, `pending_repo_sync` stays true), `outbox_snapshot` (a pending row with no open PR and an old write is reset; the answer carries `hashes`), `outbox_unknown_op` (answers `status: error`, `error_category: validation`). `./scripts/kit tracker-fold --input ../tests/samples/outbox-response.sample.json --dry-run` folds the sample without writing.

## Verify in your tenant

| Item | What to check |
|---|---|
| K5 | The v2 search body; until then the full Lists and filtering in the transforms |
| K15 | ≤ 500 rows within 30 s; the response size limit (chunking) |
| K8 | The Webhook secret after import (rotate first) |
