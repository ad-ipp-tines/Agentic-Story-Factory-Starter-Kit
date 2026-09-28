# `kit/tracker/` — the tracker and its sync contract

_Spec: REPO-DESIGN.md §6.5 (state, field ownership, Flow 1, Flow 2, conflicts, events), §7.4 (section B), §7.7 (section E), §8.1 (the Record types), §8.3 (these files), §11.1 (milestones)._

**Git is the system of record.** `backlog.yaml`, `milestones.yaml` and `sdlc/work/<slug>/events.jsonl` are the truth. The `sdlc_backlog`, `sdlc_milestones` and `sdlc_events` Record types in the ops team are the **queryable projection** that the dashboards and the runtime specialists read, and the **inbox** for decisions made in Tines. Nothing in Tines becomes true in git until a person merges a pull request.

| File | What it is | Validated by |
|---|---|---|
| [`backlog.yaml`](backlog.yaml) | One row per story: phase, status, open gate, attempt, owner, dates, credit estimate, links, `rev` | [`backlog.schema.json`](backlog.schema.json) |
| [`milestones.yaml`](milestones.yaml) | The day-1, week-1 and week-4 milestones (§11.1) | [`milestones.schema.json`](milestones.schema.json) |
| [`field-map.yaml`](field-map.yaml) | YAML key ↔ Record field ↔ `result_type` ↔ owner side, for all three Record types | `./scripts/sdlc check` (`field_map_complete`) |

## Who may write here

Nobody by hand. The editor's Write and Edit tools are denied on `kit/tracker/**` (`.claude/settings.json`), and the only writers are:

| Writer | Writes | When |
|---|---|---|
| `./scripts/sdlc` (`intake`, `apply`, `advance`, `gate`) | the story's own row, and its events | every repo-side lifecycle step |
| `./scripts/kit tracker-fold` | rows and milestones changed in Tines, `intake.md` / `retro.md` drafts, the events Tines logged | `tracker-pull.yml` (Flow 2) |
| `./scripts/kit apply-config --targets tracker` | empty due dates and target dates, the `provider` of AI rows | `kit.yml`, after the day-1 config commit |

Every change reaches `main` through a PR on a lifecycle branch (`design/`, `story/`, `improve/`, `tracker/`, `rollback/`; `sdlc/lifecycle/touch-sets.yaml` `branches`). A branch outside those prefixes may not touch `kit/tracker/**` at all.

## `rev` — the rule that keeps two writers from colliding

- Every row and every milestone carries `rev`. **A PR that changes a row sets its `rev` to `main`'s rev + 1.** The scripts compute it from `origin/main` (`git show origin/main:kit/tracker/backlog.yaml`), so several writes on one branch still land as one bump. `sdlc.yml` rejects any other value, so two branches cannot land the same bump: the second one rebases.
- **A Tines-side write never bumps `rev`.** It marks the Record `pending_repo_sync: true` with `pending_base_rev` = the row's `rev` at the time of the write.
- Section B clears `pending_repo_sync` **only when git's `rev` is greater than `pending_base_rev`** — once a merge after the Tines-side write has reached `main` — and then overwrites the Tines-owned fields with git's values. Equal revs never clear a pending change.

## Field ownership

Each field has one author side (`field-map.yaml`, column `owner`):

| Owner side | Fields (sdlc_backlog) | Reaches the other side by |
|---|---|---|
| **git** | `title, use_case, mode, tier, library_seed_id, credit_estimate, links, prod_story_id, live_since, attempt, rev`; `phase / status / open_gate` for repo-side gates (G1, G2, G3, G4, G5a, G5b) | Flow 1 |
| **tines** | `owner`, `target_date`; `phase / status / open_gate` for Tines-side gates (G0, G6, G7, the GB release, GX) and the D9 improve trigger; accepted planner proposals; the `brief` and `retro` drafts (→ `sdlc/work/<slug>/intake.md`, `retro.md`) | Flow 2 (a PR a human merges) |
| **tines-only** | `specialist_due, specialist_status, proposal, outbox_seq, acked_seq, pending_repo_sync, pending_base_rev, last_actor, last_transition_at` | never mirrored to git |

`tracker-fold` takes from Tines only the fields whose owner side is `tines`. A Tines value for a git-owned field is ignored and listed in the PR body. A new row (a use case added on a Page or through the App) is the one exception: all of its mirrored fields come from Tines, and the design phase names it properly later (`title`'s `[PREFIX] NN · Verb noun` rule is enforced by the contract schema at G1, not here).

**One instrument per gate.** A Tines-side gate is decided on the `gate_decision` Page when Records are entitled, and through `/sdlc-gate` only on the Community path. The two sides never decide the same gate, so they never write the same fields. `tracker-fold` accepts a Tines-side `phase / status / open_gate` change only when the pull carries the matching event (a human `gate_decision` for G0, G6, G7 or GX; a `budget` event for GB; an `escalation` for GX; the D9 `transition` with `decision: improve_trigger`; or `brief_writer` opening G0 inside intake) **and** `sdlc/lifecycle/state-machine.yaml` allows the move from the row's current phase.

## Flow 1 — repo → Records (`tracker-sync.yml`, on merge)

```
push to main touching kit/tracker/**  (and a nightly full run with full: true)
  → ./scripts/kit tracker-json --push [--full]      refuses unless GITHUB_ACTIONS=true and GITHUB_REF=refs/heads/main
  → POST $TRACKER_SYNC_URL                          the tracker_sync_in Webhook, Secret access control (section B)
```

The payload, in Record field names (`field-map.yaml`), empty values as `null`, timestamps UTC with `Z`:

```json
{
  "schema_version": 1,
  "source_sha": "<commit sha>",
  "full": false,
  "entries":    [ { "story_key": "example-enrich-ip", "title": "[SEC] 01 · Enrich IP (sub)", "phase": "intake", "rev": 1, "…": "…" } ],
  "milestones": [ { "milestone_id": "day-1", "criteria": "- …\n- …", "status": "not_started", "rev": 1, "…": "…" } ],
  "view": { "counts_by_phase": {}, "stories_csv": "…", "milestones_csv": "…", "…": "…" }
}
```

Section B takes the `sdlc_sync_lock` compare-and-swap (a 422 means another sync is running: skip; the next push or the nightly run re-sends the full state), lists `sdlc_backlog` (up to 500 rows), then creates, updates or records a conflict per entry, logs a `transition` event for every phase change (→ section D), does the same for milestones, and releases the lock. B3 refuses more than 500 entries, keys that are not slugs, and enum values not in the `sdlc_state_machine` Resource. `view` is the `kit_tracker_view` value that B10 writes **only when Records are not entitled** (`kit/resources/README.md`). On the nightly run (`full: true`) B6 also overwrites every row that is not pending with git's values wherever they differ, whatever the revs: git wins.

## Flow 2 — Records → repo (`tracker-pull.yml`, every 30 minutes)

```
POST $TRACKER_OUTBOX_URL {op: "pull"}              the tracker_outbox Webhook, response-enabled (section E, E3; K15)
  → ./scripts/kit tracker-fold --pull              folds the answer into the tracker (CI on main only)
  → branch tracker/pull-<run_id> → PR labelled tracker, opened with the tracker-bot GitHub App token
  → POST {op: "ack", items[{key, outbox_seq}]}     ./scripts/kit tracker-fold --ack (E4 stops re-sending them)
  → a person merges → Flow 1 brings the merged state back into Records
```

The pull answer section E returns (E3):

```json
{
  "items": [
    { "key": "example-enrich-ip", "base_rev": 1, "outbox_seq": 2,
      "changes": { "status": "awaiting_gate", "open_gate": "G0" },
      "brief_md": "# Intake brief …" }
  ],
  "milestones": [ { "milestone_id": "day-1", "rev": 1, "status": "in_progress" } ],
  "events": [ { "story_key": "example-enrich-ip", "event_type": "specialist_run", "agent": "brief_writer",
                "model": "…", "credits_used": 0.5, "summary": "…", "created_at": "2026-10-01T09:20:00Z" } ]
}
```

- `changes{}` is keyed by **Record field names**; `base_rev` is the row's `pending_base_rev`.
- `events[]` are `sdlc_events` rows; `tracker-fold` converts them to `events.jsonl` lines (`model` → `model_reported`, `ref` → `refs`, `source_sha` → `sha`, `created_at` → `ts`), validates each against `sdlc/observability/event.schema.json`, and drops duplicates. **The outbox returns roles, never emails**: `actor_ref` is in-tenant only, and if it arrives anyway it is dropped before anything is written.
- An item whose text looks like a secret, or carries a real email address, is **refused and not acknowledged**; it stays in the outbox and shows in every PR body until it is fixed in Tines.
- Drafts: `brief_md` becomes `sdlc/work/<slug>/intake.md` unless a person has already edited it or the story has left intake; `retro_md` becomes `retro.md` only when there is none. The PR body says when a draft was kept out.
- When a fold changes nothing, the workflow still acknowledges the items (they are already true in git).

### Conflicts

A field is a **conflict** when the item's `base_rev` is below the row's current `rev` **and** the same field changed in git since `base_rev` (read from `main`'s history of this file). Git wins: the field keeps git's value, a `conflict` event is appended, and the PR body lists both values so the reviewer can take the Tines value by editing the PR before merging. A Tines-side phase change that `state-machine.yaml` does not allow is handled the same way.

### Closed or abandoned tracker PRs

Every Tines-side transition is **provisional** until its tracker PR merges. The nightly `tracker-pull.yml` run sends `{op: "snapshot", open_pr_keys[]}` — the keys of open PRs from `tracker/*` branches, read from each PR body's `<!-- tracker-keys: … -->` line — and section E (E5) clears `pending_repo_sync` on every pending row whose key has no open PR and whose Tines-side write is older than `sdlc_limits.pending_reset_hours` (24). It returns every row and the `kit_state.hash_<name>` values, and `./scripts/kit tracker-fold --snapshot` compares them with git:

- **rows that differ** (and are not pending) → a `tracker-drift` PR (branch `tracker/drift-<run_id>`) that proposes the Records values. Merge it to accept the tenant's state; close it and the nightly full Flow 1 sync (which runs after the snapshot) restores git's values.
- **Resources that differ** from the ones generated from `main` (`resources_in_sync`: `sdlc_state_machine`, `kit_catalog`, `kit_config`, `sdlc_limits`) → the run fails with the list; re-run `kit-sync.yml`. The snapshot carries the hashes as `kit_state`'s own `hash_<name>` keys (`{rows[], milestones[], kit_state: {hash_sdlc_state_machine: "<sha256 hex>", …}}`); both `tracker-fold --snapshot` and `./scripts/sdlc check resources_in_sync --snapshot FILE` read every `hash_<name>` key they find and compare it with `resource_hash` of the bundle's `resources[].value` (`kit/resources/README.md`).

## Commands

```bash
./scripts/kit tracker-json --check                    # validate backlog, milestones, field map and enums (no network)
./scripts/kit tracker-json --out /tmp/payload.json    # what Flow 1 would send (no network)
./scripts/kit tracker-fold --input saved-pull.json --dry-run --pr-body /tmp/body.md   # fold a saved outbox answer
./scripts/kit tracker-fold --snapshot-input saved-snapshot.json --report /tmp/report.json
```

The network forms (`tracker-json --push`, `tracker-fold --pull | --ack | --snapshot`) run only in GitHub Actions on `main`: the two webhook URLs carry secrets, live only in the GitHub environment `tracker` (`TRACKER_SYNC_URL`, `TRACKER_OUTBOX_URL`), are never in `.env`, and are never printed.

## Without Records (the Community path)

There is no kit story, no Flow 1 and no Flow 2: the tracker lives in git only. `./scripts/sdlc` writes it, Tines-side gates are decided with `/sdlc-gate` (the Page does not exist), and `./scripts/kit apply-config --targets tracker` fills the milestone due dates and story target dates from `kit/tenant/config.yaml` (`kit/docs/community-path.md`).
