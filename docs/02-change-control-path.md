# 02 · The change-control path → read `02-workflows.md` §2 and `06-rollback-and-recovery.md`

_This path is the name `DESIGN.md` §2.2 gives this document (also linked from `policies/POLICY.md`). The content lives in `02-workflows.md`; this file exists so that link resolves and gives the path in one line._

## The path in one line

builder in the editor → `/mcp` edits the **dev** story (whether these land as drafts is VERIFY, item 2; the policy is on regardless) → `/tines-export` → branch → PR → `lint.yml` + `review.yml` → CODEOWNERS review → human merge → `ship.yml`: `POST /api/v1/stories/{id}/versions` → `POST /api/v1/stories/import` (`mode: versionReplace`, `draft_name: git-<sha>`) → recipients + `monitor_failures` on the draft → `POST /api/v1/stories/{id}/change_request` → the approver reads `GET …/change_request/view` (`live_story_export` vs `draft_export`) and the PR → **approves in Tines** → pushes (or `promote.yml` on `APPROVED`) → live → `drift.yml` proves it that night.

## Where each part is written out

| Part | Where |
|---|---|
| Steps 2.1–2.8 with the exact files, subcommands and endpoints | `02-workflows.md` §2 |
| The tenant policies required (**Enable by default**, **Require approval for all changes** — admins and owners included; story requirements set to required; team change-control webhooks pointed at the router), draft naming (`git-<sha>`, `rollback-<target>`, `monitor-<finding_id>`), draft behaviour (inactive after 30 minutes, locked on review request, test-mode credentials apply) | `02-workflows.md` §2.9 |
| Rollback and break-glass | `02-workflows.md` §5 and `06-rollback-and-recovery.md` |
| The identities that may act at each step, and what none of them may do | `02-workflows.md` Appendix B; `04-security-model.md` §2; `policies/POLICY.md` |

## Verify in your tenant before presenting

Walk `ship.yml` once against the dev team (`workflow_dispatch` with `env: dev`) before pointing it at prod; that settles items 6 and 7 of `07-verify-before-you-rely-on-it.md`.
