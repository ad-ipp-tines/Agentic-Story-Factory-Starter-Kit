---
name: tines-ship
description: Imports a story's committed export into the target story as a change-control draft and opens a change request for a human approver. Use only after the PR is merged, or to rehearse the ship path against the dev team.
disable-model-invocation: true
argument-hint: <story-slug> [dev|prod]
allowed-tools: Bash(./scripts/tines cr-view *), Bash(./scripts/tines versions-list *), Bash(./scripts/tines live-activity *), Bash(git log *), Bash(git status *), Bash(git rev-parse *), Read
---

<!-- allowed-tools pre-approves READ-ONLY subcommands only. Every tenant write this skill runs
     (version-create, import-draft, recipients-add, story-update, action-update, cr-open, ship)
     falls through to the `ask` list in .claude/settings.json, so the person confirms each one. -->


# /tines-ship — import as a draft, open a change request, stop

The local counterpart of `.github/workflows/ship.yml`, for teaching and for tenants without CI. **It never promotes.** Promotion is a named person approving in Tines (and pushing), or `promote.yml` on a change request whose status is already `APPROVED`. `cr-promote` is denied in the IDE by `.claude/settings.json`.

**Inputs:** `$0` = slug · `$1` = `dev` (rehearsal, default when HEAD is not on `main`) or `prod`.
**Environment:** `TINES_TENANT`, a **team-scoped** `TINES_API_KEY` for the target team (Editor role; never a personal key), `TINES_ENV=<env>`, and for prod `TINES_ALLOW_PROD=1` set deliberately by the person (the scripts refuse prod without it). This skill never reads `.env`.

## Preconditions — refuse if any fails
1. `git status --porcelain` is empty (clean working tree). For `prod`, HEAD is on `main` (`git rev-parse --abbrev-ref HEAD`).
2. `stories/<slug>/story.json` is lint clean and `story.meta.yaml: exported_from.sha` matches a commit on `main`.
3. The manifest has `<env>.story_id` for the slug, or `new: true` (a first ship to a non-prod team with no id yet, such as `staging`, uses `mode: new` and the returned id is committed by a follow-up PR; the dev id is recorded by hand when the builder creates the story). **In prod a `mode: new` import is refused** (`import_story.py`): a person first creates an empty, disabled, change-controlled shell story with the export's exact name in the prod team [BY HAND] and commits its id; only `ship.yml` dispatched with an explicit, logged `new_in_prod_reason` may create it instead. Never pass `--allow-new-in-prod` from the IDE.
4. Every credential and Resource in `story.meta.yaml` exists in the target team **under the same name** — the import fails otherwise (behaviour VERIFY #6). Names must be identical across environments; the import matches the story **by name** (`versionReplace`), and embedded sub-stories are not imported.
5. A story id in `policies/never-touch.yml` (every production id after its first ship) is written only inside this ship's own draft: every write in step 3 carries `--draft <id> --via-draft`, and the scripts refuse it otherwise.

## Steps
1. **Rollback point.** `./scripts/tines version-create <slug> --env <env> --name "pre-ship $(git rev-parse --short HEAD)"` → `POST /api/v1/stories/{id}/versions`.
2. **Import as a draft.** `./scripts/tines import-draft <slug> --env <env> --draft-name "git-$(git rev-parse --short HEAD)"` → `POST /api/v1/stories/import {data, team_id, folder_id, mode: "versionReplace", draft_name}` (or `mode: "new"` + `new_name` only while `<env>.story_id` is still `0` — `new: true` is ignored once the environment has an id; that first import creates the story with no draft and no change request, so steps 3–5 wait for the next ship). Capture the draft id the dispatcher prints (response field name VERIFY #6). A "missing credential or resource" error stops the ship: create it in the target team [BY HAND], never in the export.
3. **Recipients and monitor flags on the draft.** For each recipient of the story — `story.meta.yaml: monitoring.recipients` when it is a list (the ops trio: never the router), else `stories/_manifest.yaml: environments.<env>.recipients` — resolve the `${VAR}` from the environment **without echoing it** (the router URL carries a secret) and run `./scripts/tines recipients-add <slug> --env <env> --address "$ADDR" --draft <id> --via-draft` → `POST /api/v1/stories/{id}/recipients {address, draft_id}` (or let `./scripts/tines story-update <slug> --env <env> --draft <id> --via-draft --from-manifest` pick the same list). Then `./scripts/tines story-update <slug> --env <env> --monitor-failures true --draft <id> --via-draft` → `PUT /api/v1/stories/{id}` (on a change-controlled story this lands in the named draft, or in a draft called `test` if none is given). For `locked_slugs`, add `--locked true`. Watchdogs from `meta.monitoring.no_events_watchdog`: `./scripts/tines action-update <slug> --env <env> --action-id <action_id> --monitor-no-events <seconds> --draft <id> --via-draft` → `PUT /api/v1/actions/{id}`. Whether recipients set on a draft carry to live on promote is VERIFY #7 — say so in the change-request description.
4. **Open the change request.** Save the semantic diff to a file (`./scripts/diff-story.sh stories/<slug>/story.json --against <previous sha> > .tines/ship-<slug>.diff.md`), then `./scripts/tines cr-open <slug> --env <env> --draft <id> --title "<slug> $(git rev-parse --short HEAD)" --pr-url "<PR URL>" --diff .tines/ship-<slug>.diff.md --rollback-ref <previous sha>` (add `--reason "…"` for context an approver needs) → `POST /api/v1/stories/{id}/change_request`. `cr-open` has no `--description` option; it builds the description itself. The dispatcher's description template carries story · environment · commit SHA · PR URL · semantic diff · rollback ref, so audit can join the commit to the story version.
5. **Show the approver's view.** `./scripts/tines cr-view <slug> --env <env> --draft <id>` → `GET /api/v1/stories/{id}/change_request/view?draft_id=` — prints `status` and the live-versus-draft diff (`live_story_export` vs `draft_export`).
6. **Print the change-request URL and stop.** Say: "A named approver reads the live-vs-draft diff and the PR in Tines, then approves and pushes — or runs `promote.yml` once the status is `APPROVED`. Nothing here promotes."
7. **After approval (by the person):** the team change-control webhook posts the approval into the ops thread; `drift.yml` proves prod equals `main` that night; the next sweep baselines the story. If the import used `mode: new`, commit the returned story id to `stories/_manifest.yaml` — for prod, remove `new: true` from the slug in the same edit — and append it to `policies/never-touch.yml: story_ids` in a follow-up PR; after it merges, ship again to open the change request.

## Never
- Pass `bypass_approval` — it exists only in `rollback.yml`'s break-glass job (two reviewers, mandatory reason, a line in `policies/break-glass-log.md`).
- Promote a `PENDING` request, or call `cr-promote` at all from the IDE.
- Ship from a dirty tree, from a branch (prod), or with a personal API key.
- Echo `OPS_ROUTER_URL`; commit a real story id into `_manifest.yaml` without a PR.
- Ship two stories in one run — `sleep 1` between stories if a batch is ever needed, for rate limits.

## Checklist
- [ ] clean tree · `main` (prod) · lint clean · `exported_from.sha` on `main`
- [ ] version created · draft imported · draft id captured
- [ ] recipients + `monitor_failures` (+ `locked`, watchdogs) applied to the draft
- [ ] change request opened with SHA, PR URL, diff and rollback ref · `cr-view` shown
- [ ] URL printed; stopped; promotion left to a person
