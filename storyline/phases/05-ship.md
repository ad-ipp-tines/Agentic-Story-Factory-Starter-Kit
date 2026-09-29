# 05 · ship — reach production only through change control

_Phase `ship` in [`state-machine.yaml`](../lifecycle/state-machine.yaml) · Gate out: [G5a or G5b](../gates/G5-change-request-approval.md) (human) · Spec: REPO-DESIGN.md §4.4 (05 ship), §3.3 row 20._

## Purpose

Move the merged export into the prod team through the scaffold's change-control path, unchanged, and record the human release as evidence the repository can read. No crew member runs: shipping is deterministic.

## Entry criteria

The build PR has merged to `main`. The row on `main` reads `phase: ship, status: awaiting_gate, open_gate: G5a` (a first ship, manifest `new: true`) or `G5b` (every later ship).

## Work

The scaffold's machinery, plus one evidence step (REPO-DESIGN.md §3.3 row 20):

| | First ship (`new: true` — every starter story) | Every later ship |
|---|---|---|
| Path | `ship.yml` imports with `mode: new`, which creates the story in the prod team with **no change request** — dispatched with its logged `new_in_prod_reason` | story version `pre-ship <sha>` → import as draft `git-<sha>` (`mode: versionReplace`) → recipients and `monitor_failures` on the draft → change request → view |
| Human gate | **G5a**: the GitHub `production` environment's required reviewer releases the job before the import | **G5b**: a named approver approves and pushes in Tines, or `promote.yml` promotes a request that is already APPROVED |
| Then | change control is switched on for the new story `[BY HAND]`; the follow-up PR commits its prod id to the manifest | `release <sha>` version after promotion |

**G5 evidence is computed in CI, never in the editor.** The IDE key is dev-only and the scripts refuse prod outside CI. The final step of `ship.yml` and `promote.yml` reads the change request with the prod Viewer key (`TINES_API_KEY_PROD_READ`, environment `prod-read`) through `./scripts/tines cr-view`, and writes `storyline/work/<slug>/ship.md` ([template](../templates/ship-record.md)) plus the `gate_decision` event through a PR (branch `tracker/ship-<slug>-<sha7>`, touch set `tracker`). After an approver pushes in Tines rather than through `promote.yml`, the step is dispatched on its own. What `cr-view` returns after a push and after `delete_draft: true` is **VERIFY K45**; if it returns nothing once the draft is deleted, the step records the live story version instead.

Once `ship.md` is on `main`, `./scripts/storyline advance <slug>` (ask) reads it and:

- on approval: moves the row to `operate` with `status: shadow` when `contract.risk.side_effects` is true, else `live`; writes the git-owned `prod_story_id` (from the manifest) and `live_since` (from the ship evidence);
- on rejection: prepares the revert (below) and returns the row to `build/rework`.

## On rejection

`storyline advance` prepares the revert the way `/tines-rollback` does: branch `rollback/<slug>/<sha>`, a revert of the rejected commit, and a PR, so that `main` returns to what is live. The revert restores **`stories/<slug>/**` only**: lifecycle artifacts under `storyline/work/<slug>/` and the tracker row are never reverted — `events.jsonl` is append-only, so the rejection is a new event. `drift.yml` skips the slug while that PR is open (REPO-DESIGN.md §3.3 row 21), so a nightly drift PR does not fight the rework branch. The approver's note becomes the finding in the rework package.

## Exit criteria

`ship.md` on `main` records the decision, and `storyline advance` has moved the row to `operate` (or back to `build`).

## Artifacts

| Artifact | Path | Written by |
|---|---|---|
| Ship record | `storyline/work/<slug>/ship.md` | the G5 evidence step in `ship.yml` / `promote.yml`, through a PR |
| Events | `storyline/work/<slug>/events.jsonl` | the evidence step (G5 decision), `advance` (transition) |
| Revert | `rollback/<slug>/<sha>` → `stories/<slug>/story.json`, `story.meta.yaml` | `advance` on rejection |

## Templates

[`ship-record.md`](../templates/ship-record.md)

## Crew

None. `ship.yml`, `promote.yml` and `/tines-ship` are deterministic, and no approver key exists in CI.

## Gate

**[G5a / G5b](../gates/G5-change-request-approval.md)**, human. G5a is a GitHub environment review; G5b happens in Tines.

## Failure modes

| Symptom | Cause | What happens |
|---|---|---|
| The import fails on a missing credential | it does not exist in the prod team under the same name | `[BY HAND]` in the prod team, then re-run `ship.yml`; the export never carries a value (scaffold VERIFY #6) |
| `ship.md` never appears | the approver pushed in Tines and nobody dispatched the evidence step | dispatch the evidence step; `storyline next` keeps reporting G5b as open |
| `cr-view` shows nothing after `delete_draft: true` | K45 | the step records the live story version instead |
| Drift PR against a rejected change | the revert PR is still open | `drift.yml` skips the slug until it merges |
