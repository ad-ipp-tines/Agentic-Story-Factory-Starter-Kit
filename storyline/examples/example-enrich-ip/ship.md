---
story_key: example-enrich-ip
gate: G5a
decision: approved_and_imported
ship_kind: new
sha: "0000000"
version_name: ""
draft_name: ""
change_request_id: ""
change_request_status: ""
approver_role: security-platform
decided_at: "2026-10-06T10:10:00Z"
recorded_at: "2026-10-06T10:15:00Z"
workflow: ship.yml
workflow_run: "0"
prod_story_id: 0
rejection_note: ""
---

# Ship record — `example-enrich-ip`

> **Worked example — illustrative.** Placeholders only; see the note at the top of `intake.md`. In a customer repository CI writes this file; nobody types it.

_Template: `storyline/templates/ship-record.md` · Phase: 05 ship · Gate: **G5a** (first ship — the manifest said `new: true`) · Written by the G5 evidence step at the end of `ship.yml`, through the PR `tracker/ship-example-enrich-ip-0000000`, which needed an approving review from security-platform (`storyline/gates/approvers.yaml`)._

## What shipped

| | |
|---|---|
| Commit | `0000000` — the merge of the build PR (attempt 1) |
| Path | **first ship**: `ship.yml` (dispatched with its logged `new_in_prod_reason`) imported the export with `mode: new`, creating `[SEC] 01 · Enrich IP (sub)` in the prod team. A `mode: new` import opens no draft and no change request, so the human gate was the GitHub `production` environment's required reviewer releasing the job |
| Story version | none: the story did not exist in prod before the import, so there was no `pre-ship` rollback point |
| Change request | none (a `mode: new` import) |
| Approver | security-platform (the `production` environment's required reviewer) at 2026-10-06T10:10:00Z |

## After a first ship (G5a) — [BY HAND]

- [x] Change control switched on for the new story in the prod team (tenant policy "Enable by default" — checked).
- [x] Its live id committed to `stories/_manifest.yaml` (`prod.story_id`) by `ship.yml`'s follow-up PR, and `new: true` removed. (In this illustration the id stays `0`.)
- [x] `policies/never-touch.yml` `story_ids` gained the id.

Every later ship of this story is a `versionReplace` draft and a change request: **G5b**.

## Next

`./scripts/storyline advance example-enrich-ip` read this file on `main` and moved the story to **operate** with `status: live` (the contract says `risk.side_effects: false`, so no shadow and no G6), writing `prod_story_id` and `live_since: 2026-10-06T11:00:00Z` into the tracker row.
