---
# Machine-read keys: ./scripts/sdlc advance reads them from main (ship → operate, or → build with a revert PR).
# Written ONLY by the G5 evidence step in ship.yml / promote.yml, through a PR; never in the editor (the IDE key is
# dev-only and the scripts refuse prod outside CI).
story_key: <slug>
gate: G5b                              # G5a (first ship: manifest new: true) | G5b (change request)
decision: approved_and_pushed          # G5a: approved_and_imported | rejected · G5b: approved_and_pushed | rejected
ship_kind: versionReplace              # new (G5a) | versionReplace (G5b)
sha: "0000000"                         # the merge commit of the build PR that was shipped
version_name: "pre-ship 0000000"      # the story version created before the import
draft_name: "git-0000000"              # "" for a mode: new import (it creates no draft)
change_request_id: "0"                 # "" for a mode: new import (it opens no change request)
change_request_status: ""              # as ./scripts/tines cr-view reports it (VERIFY K45 after a push / delete_draft)
approver_role: <role>                  # a role, never a person
decided_at: "YYYY-MM-DDTHH:MM:SSZ"     # UTC
recorded_at: "YYYY-MM-DDTHH:MM:SSZ"    # UTC, when CI read the evidence
workflow: ship.yml                     # ship.yml | promote.yml
workflow_run: "0"
prod_story_id: 0                       # from stories/_manifest.yaml once known; advance copies it into the tracker
rejection_note: ""                     # G5a/G5b rejected only: the approver's reason, as a role would state it
---

# Ship record — `<slug>`

_Template: `sdlc/templates/ship-record.md` · Phase: `sdlc/phases/05-ship.md` · Gate: G5a or G5b (`sdlc/gates/G5-change-request-approval.md`) · Written by CI through a PR (`sdlc/lifecycle/touch-sets.yaml`, script `ship-evidence`)._

## What shipped

| | |
|---|---|
| Commit | `<sha>` (merge of PR #<n>) |
| Path | first ship — `mode: new` import released by the GitHub `production` environment's required reviewer (G5a) · later ship — `versionReplace` into draft `git-<sha>`, recipients and `monitor_failures` on the draft, change request, approved and pushed in Tines (G5b) |
| Story version | `pre-ship <sha>` (the rollback point) · `release <sha>` after promotion |
| Change request | <id> · status <as read by `cr-view`> |
| Approver | <role> at <UTC time> |

## After a first ship (G5a) — [BY HAND]

- [ ] Change control is switched on for the new story in the prod team (tenant policy "Enable by default" should already do it — check).
- [ ] Its live id is committed to `stories/_manifest.yaml` (`prod.story_id`) by the follow-up PR, and `new: true` is removed.
- [ ] `policies/never-touch.yml` `story_ids` gains the id (production ids are never-touch).

## On rejection

The approver's note becomes the finding in `.sdlc/out/<slug>/rework-<n>.json`. `./scripts/sdlc advance <slug>` prepares the revert on `rollback/<slug>/<sha>` so `main` returns to what is live (only `stories/<slug>/**` is reverted; lifecycle artifacts never are), and `drift.yml` skips the slug until that PR merges. The story then returns to build with `status: rework`.
