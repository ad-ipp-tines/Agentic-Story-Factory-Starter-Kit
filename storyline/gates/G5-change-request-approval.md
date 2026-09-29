# G5 · Production release — G5a (first ship) and G5b (change request)

Two gates, one purpose: production changes only when a named person releases it. Which one applies depends on whether the story already exists in the prod team.

| | **G5a — first ship** | **G5b — change request** |
|---|---|---|
| **When** | the manifest says `new: true` (every starter story's first ship) | every later ship |
| **Between** | ship → operate | ship → operate |
| **Type** | human, **in GitHub** | human, **in Tines** |
| **Decided by** | a required reviewer of the GitHub `production` environment, before `ship.yml`'s `mode: new` import | the named approver (no approver key exists in CI) |
| **Evidence** | the merged PR, the story's export, `ship.yml`'s plan (with its logged `new_in_prod_reason`) | the live-vs-draft diff (`./scripts/tines cr-view`) and the PR |
| **Instrument** | the environment review that releases the `ship.yml` job | approve and push the change request in Tines — or `promote.yml` promotes a request that is already APPROVED |
| **Recorded** | `storyline/work/<slug>/ship.md` + a `gate_decision` event, written by CI through a PR | the same |
| **Decisions** | `approved_and_imported` · `rejected` | `approved_and_pushed` · `rejected` |

## Why two

A `mode: new` import creates the story in the prod team with **no change request**, so there is nothing for a Tines approver to approve. The human gate moves one step earlier, to the GitHub environment's required reviewer who releases the import job. Straight after, change control is switched on for the new story `[BY HAND]` (tenant policy "Enable by default" should already do it — check), its prod id is committed to the manifest by the follow-up PR, and every later ship goes through G5b.

## What the decider checks

- **G5a:** the PR is merged by a human who is not its author; the export is the one `main` holds; the reason is logged; the credentials and Resources in `story.meta.yaml` exist in the prod team under the same names.
- **G5b:** the live-vs-draft diff matches the PR's semantic diff; the draft carries recipients and `monitor_failures`; the change-request description names the commit SHA, the PR and the rollback ref (POLICY §2 rule 4).

## How the evidence reaches git

G5 evidence is **computed in CI, never in the editor** (the IDE key is dev-only, and the scripts refuse prod outside CI). The final step of `ship.yml` and `promote.yml`:

1. reads the change request with the prod Viewer key `TINES_API_KEY_PROD_READ` (environment `prod-read`) through `./scripts/tines cr-view`;
2. writes `storyline/work/<slug>/ship.md` ([template](../templates/ship-record.md)) — version, draft name, change request id, approver role, time — and the `gate_decision` event;
3. opens a PR (branch `tracker/ship-<slug>-<sha7>`), which needs an approving review from the G5 team in [`approvers.yaml`](approvers.yaml).

`ship.yml` records the opened request, or for a first ship the `mode: new` import the reviewer released. `promote.yml` records the approved and pushed request. After an approver pushes in Tines instead, the step is dispatched on its own. What `cr-view` returns after a push and after `delete_draft: true` is **VERIFY K45**; if it returns nothing once the draft is deleted, the step records the live story version instead.

Then `./scripts/storyline advance <slug>` (ask) reads `ship.md` on `main` and moves the story to operate (`shadow` or `live`, from `contract.risk.side_effects`), writing `prod_story_id` and `live_since`.

## On rejection (either gate)

`storyline advance` prepares the revert the way `/tines-rollback` does — branch `rollback/<slug>/<sha>`, a revert of the rejected commit restricted to `stories/<slug>/**`, a PR — so `main` returns to what is live. `drift.yml` skips the slug while that PR is open. The story returns to build with `status: rework`, and the approver's reason becomes the finding in the rework package (`failing_gate: G5a` or `G5b`).

## Never

- A pipeline approves a change request, or promotes one that is not APPROVED.
- `bypass_approval` outside `rollback.yml`'s `break-glass-promote` job (POLICY §2 rule 3).
- The editor reads production to write `ship.md`.
