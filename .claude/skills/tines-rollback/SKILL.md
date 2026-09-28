---
name: tines-rollback
description: Prepares a production rollback of a story to a previous committed export through a draft and change request, and the PR that keeps main truthful. Use when a shipped change misbehaves or the monitor proposes a rollback.
disable-model-invocation: true
argument-hint: <story-slug> <git-sha|previous>
allowed-tools: Bash(./scripts/tines versions-list *), Bash(./scripts/tines live-activity *), Bash(git log *), Bash(git show *), Bash(git revert *), Bash(git checkout -b *), Bash(jq *), Read
---

# /tines-rollback — back to a committed export, through the same controlled path

Rolling back is shipping an older export. The git ref is the source of truth (the versions API documents create / get / patch / delete — no export-of-a-version endpoint was found, VERIFY #12), the path is the same draft + change request + human approval, and `main` must end up equal to what is live.

**Inputs:** `$0` = slug · `$1` = a git sha, or `previous` (the commit before the current one that touched `stories/<slug>/story.json`).
**This skill never touches the tenant.** It prepares the PR and says which workflow to run. Emergency containment is the **break-glass job** in `rollback.yml`, run by a human with two reviewers — never by this skill.

## Steps
1. **Pick the target.** `git log --oneline -- stories/<slug>/story.json` — list the commits; resolve `previous`. `git show <sha>:stories/<slug>/story.json | jq '.name, (.agents | length)'` to confirm it is the right story and a sane size. The git history is the comparison this skill makes. **Optional, and not run by this skill:** a look at production itself. The scripts refuse `--env prod` without `TINES_ALLOW_PROD=1`, which the editor never sets, and the `.env` key is scoped to the dev team, so `versions-list <slug> --env prod` (`GET /api/v1/stories/{id}/versions`, metadata only) and `live-activity --slug <slug> --env prod` (`not_working_actions_count`, `pending_action_runs_count`, `monitor_failures`, recipients) would fail here. Point the person at the latest `drift.yml` run for the slug instead (or its `workflow_dispatch` with `slug=<slug>`: it exports prod with the Viewer-role read key), or ask someone who holds a prod read key to run those two reads.
2. **Branch and revert.** `git checkout -b rollback/<slug>/<sha>`; `git revert --no-edit <offending commit(s)>` so `stories/<slug>/story.json` and `story.meta.yaml` equal the target (a revert, not a hand edit — the export is never typed). If the revert leaves anything in `stories/<slug>/` that differs from `<sha>`, stop and say so.
3. **Open the PR** titled `ROLLBACK <slug> to <sha>` with the incident link, the reason, `./scripts/diff-story.sh stories/<slug>/story.json --against <current main>` output, and the rollback ref of the rollback (the sha being rolled back from). `git push` and `gh pr create` ask for permission; `lint.yml` and `review.yml` run as usual; a CODEOWNER reviews; a human merges.
4. **Say which workflow to run and with what:** `rollback.yml` with `slug=<slug>`, `target=<sha>`, `reason="<reason>"`, `emergency=false`. The workflow (GitHub environment `production`) creates a `pre-rollback` version, imports the ref's `story.json` as draft `rollback-<target>` (`POST /api/v1/stories/import`, `versionReplace`), applies recipients and `monitor_failures` to the draft, opens the change request `ROLLBACK <slug> to <target>` (`POST /api/v1/stories/{id}/change_request`) and shows `cr-view`. A named approver approves and pushes, or `promote.yml` runs on `APPROVED`.
5. **If production is misbehaving now**, say so explicitly and hand over: a human runs `rollback.yml` with `emergency=true` → the `break-glass` job (environment `break-glass`, two required reviewers) calls `POST /api/v1/stories/{id}/disable` (toggles; bypasses change control by design; audited), in the safe-disable order (entry or schedule action first where possible), expecting a burst of failure notifications the router dedupes; only that job may run `BREAK_GLASS=1 ./scripts/tines cr-promote … --bypass-approval --reason "<reason>"`, and it appends `policies/break-glass-log.md` in the same run.
6. **After approval and re-enable** (`POST /disable` toggles back; confirm with `./scripts/tines live-activity` and the next sweep; `drift.yml` proves prod equals `main` that night): add the incident to `stories/<slug>/README.md` (change log: sha → what), and if the monitor proposed the rollback, mark the proposal `applied` in the `ops_alert_proposals` Record [BY HAND or through the ops tools server's request tool].

UI alternative for a person: restore a story version from the version bar in Tines [BY HAND] — then export it with `/tines-export` so `main` catches up, or the nightly drift PR will do it for you and attribute the change through the audit logs.

## Never
- Edit `story.json` by hand to "roll back" — revert the commit.
- Call `story-disable`, `cr-promote` or `import-draft` from this skill; it prepares, the workflows act.
- Roll back an `ops-*` story without the ops team, or anything in `policies/never-touch.yml` outside its own change request.
- Skip the PR: production and `main` must never disagree for longer than one night.

## Checklist
- [ ] target sha chosen and shown; story name and agent count confirmed
- [ ] branch `rollback/<slug>/<sha>` with a clean revert; PR `ROLLBACK <slug> to <sha>` opened with incident link and diff
- [ ] the exact `rollback.yml` inputs printed; emergency path described only as a human act
- [ ] post-approval steps listed (re-enable, README change log, proposal marked applied)
