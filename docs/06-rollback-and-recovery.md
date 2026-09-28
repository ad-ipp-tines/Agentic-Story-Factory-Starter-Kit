# 06 · Rollback and recovery — story versions, re-import from git, rejected change requests, silencing the monitor

_Tines Stories as Code · docs v1 (2026-09-24) · Matches `DESIGN.md` §4.5, §3.4 (`rollback.yml`) and §5 · Read this **before** you need it. Every command is `scripts/tines` or a skill; every endpoint is in `DESIGN.md`. The Model Context Protocol (MCP) surfaces are not part of any rollback path — rollback is API and people._

## 1. The rollback points you always have

| Rollback point | Created by | What it gives you | Limits |
|---|---|---|---|
| **The git history of `stories/<slug>/story.json`** | Every merged PR | An exact, normalised export of every shipped state; `git log --oneline -- stories/<slug>/story.json` | Re-import re-creates the story from JSON: MCP connections are dropped, embedded sub-stories are not imported, credentials and resources must exist by name |
| **A story version** (`POST /api/v1/stories/{id}/versions`) | `ship.yml` (`pre-ship <sha>`), `promote.yml` (`release <sha>`), `rollback.yml` (`pre-rollback <sha>`) | A named point in the tenant's own version bar, tied to a commit | The versions API documents create/get/patch/delete — **no export-of-a-version endpoint was found (VERIFY, item 12)**, so the git ref is the source; restoring from the version bar is [BY HAND] |
| **The change-control draft** | `ship.yml`, the monitor's apply sub-story | A change that is not live yet; can be rejected, cancelled or left | Drafts go inactive after 30 minutes and lock on review request (per `DESIGN.md`; confirm on a scratch story) |
| **The previous live story** | Change control itself | Until a change request is promoted, the live story is untouched — the cheapest rollback is *not approving* | Only helps before promotion |

Rule: **the repo is the truth, the tenant is a deployment target.** A rollback is a deployment of an older commit through the same path as a ship — import → draft → change request → human approval — so `main` and production stay equal and `drift.yml` stays quiet.

## 2. Decide in thirty seconds

```
Is production causing harm right now (wrong actions firing, a vendor quota burning, a destructive path)?
├── YES → §4 Emergency containment (break-glass: disable the story) — then §3 to restore a good state
└── NO  → Is the bad state live, or only in a pending change request?
          ├── Only pending → §5 Reject it (nothing to roll back in the tenant; fix `main`)
          └── Live         → §3 Controlled rollback (import the last good export as a draft, open a change request)
```

Then, always: §8 post-incident.

## 3. Controlled rollback (production is wrong but not dangerous)

### 3.1 Pick the target

```
/tines-rollback <slug> <git-sha|previous>
```

The skill shows `git log --oneline -- stories/<slug>/story.json` (for the production state it points at the latest `drift.yml` run — it cannot read prod itself: the scripts refuse `--env prod` outside CI and the editor's key is a dev-team key), picks the sha, and `git revert`s the offending commit(s) on a branch `rollback/<slug>/<sha>`. It opens the PR titled `ROLLBACK <slug> to <sha>` with the incident link, so that **`main` will equal what is about to be live**. Lint and review run as usual — a rollback PR is a PR. The skill never touches the tenant; it says which workflow to run next.

### 3.2 Run `rollback.yml` (a human, GitHub environment `production`)

Inputs: `slug`, `target` (the git ref), `reason`, `emergency: false`. Job `rollback`:

```bash
git checkout <target> -- stories/<slug>/story.json
./scripts/tines version-create <slug> --env prod --name "pre-rollback <current sha7>"
#   POST /api/v1/stories/{id}/versions                                  — a point to come back to if the rollback is wrong
./scripts/tines import-draft <slug> --env prod --file stories/<slug>/story.json --draft-name "rollback-<target>"
#   POST /api/v1/stories/import {data, team_id, folder_id, mode: "versionReplace", draft_name}
./scripts/tines recipients-add <slug> --env prod --address "$OPS_ROUTER_URL" --draft <id>
./scripts/tines recipients-add <slug> --env prod --address "$OPS_EMAIL_DL"   --draft <id>
./scripts/tines story-update <slug> --env prod --monitor-failures true --draft <id>
./scripts/tines cr-open <slug> --env prod --draft <id> --title "ROLLBACK <slug> to <target>" --reason "<reason> <incident link>" \
  --pr-url "<rollback PR url>" --diff <file from ./scripts/diff-story.sh> --rollback-ref <current sha>
#   POST /api/v1/stories/{id}/change_request — cr-open builds the description from these flags (no --description option)
./scripts/tines cr-view <slug> --env prod --draft <id>                  # live-vs-draft diff into the job summary
```

### 3.3 Approve and promote

The approver reads the live-vs-draft diff in Tines and the rollback PR, approves and pushes — or runs `promote.yml` once the status is `APPROVED`. The rollback PR is merged so `main` equals production. The team change-control webhook posts the promotion into the ops thread.

### 3.4 Confirm

```bash
./scripts/tines live-activity --env prod --slug <slug>     # not_working_actions_count, pending_action_runs_count
./scripts/tines runs <slug> --env prod --since <now-1h>     # runs resume; compare against the pre-incident baseline
```

The next sweep re-baselines the story; `drift.yml` proves prod equals `main` that night.

## 4. Emergency containment (production is causing harm now)

Run `rollback.yml` with `emergency: true`. The **`break-glass` job** runs first, under GitHub environment `break-glass` (**two required reviewers**), and only it may do the following:

1. **Disable the story:** `./scripts/tines story-disable <slug> --env prod --want disabled --reason "<at least a sentence>"` → `POST /api/v1/stories/{id}/disable`. The endpoint **toggles**; `--want disabled` reads the state first and does nothing if the story is already disabled. A prod reason of at least 10 characters is required. It bypasses change control by design and is audited. Expect a burst of failure notifications; the router dedupes per story + action + 15 minutes. Where possible disable the entry or schedule action first so in-flight events drain, then the story (the safe-disable order from `story-conventions.md`).
2. Post to the ops channel and the email DL: story, who, reason, expected duration.
3. Then the `rollback` job (§3.2) runs to prepare the good state as a draft + change request.
4. **If promotion cannot wait for the approver** — and only then — the same break-glass job runs:
   ```bash
   BREAK_GLASS=1 ./scripts/tines cr-promote <slug> --env prod --change-request-id <id> --delete-draft --bypass-approval --reason "<reason>"
   #   POST /api/v1/stories/{id}/change_request/promote {change_request_id, delete_draft: true, bypass_approval: true, bypass_approval_reason}
   #   requires STORY_MANAGE on the key; the dispatcher accepts --bypass-approval only with BREAK_GLASS=1 and --reason
   ```
   and **appends a line to `policies/break-glass-log.md` and commits it in the same run** (date · story · who · reason · `change_request_id` · audit-log ids · follow-up PR). The IDE denies `cr-promote` outright; no skill can do this.
5. **Re-enable:** `./scripts/tines story-disable <slug> --env prod --want enabled --reason "<at least a sentence>"` after the approver confirms the restored state (running the disable command again would do nothing — `--want disabled` is the default and the story is already disabled); in CI this is `rollback.yml` with `re_enable: true`. Confirm with `live-activity` and the next sweep.

Never-touch stories (`policies/never-touch.yml`: the `ops-*` trio, the Seeds folder, other teams' stories) can be disabled by the break-glass job like any other — the never-touch rule is about *writes by hooks, skills and pipelines*, and break-glass is a human act with two reviewers. Log it the same way.

## 5. A rejected change request (nothing bad is live — but `main` is ahead of production)

This is the case people forget. `ship.yml` opened a change request; the approver **rejected** it (or cancelled it, or it expired). The live story is untouched. But the PR is already merged, so `main` now describes a state production does not have.

What happens on its own: the team change-control webhook (`rejected`) hits the router → the ops thread shows the rejection. That night `drift.yml` exports prod, finds it differs from `main`, attributes the difference (no tenant-side change — the diff is the unshipped commit) and opens a PR labelled `drift`.

What you do — one of two things, never a third:

- **Withdraw the change.** `/tines-rollback <slug> previous` → a PR that `git revert`s the merged commit so `main` equals production again. Merge it. `ship.yml` will run on the revert, import the (unchanged) export as a draft and open a change request that is a no-op diff; the approver approves it or cancels the draft. Alternatively, close the drift PR with the revert merged and let the next `drift.yml` confirm equality.
- **Fix and re-ship.** A new `/tines-build-story` pass in dev addressing the rejection reason → new PR → merge → `ship.yml` → a **new** draft (`git-<new sha>`) and a **new** change request. Whether importing with a `draft_name` that already exists collides or replaces is VERIFY (item 6); if the rejected draft is still present, the approver deletes it in Tines first [BY HAND].

The third thing — re-opening the rejected request with `bypass_approval` — is not a path. `bypass_approval` exists only in the break-glass job, for containment, never for disagreement.

Record the rejection reason on the original PR so the next reviewer sees it.

## 6. A failed ship

| Failure | Symptom | Recovery |
|---|---|---|
| Missing credential or resource in the prod team | `import-draft` fails; the job names the missing name | Create it in the prod team **by the same name** [BY HAND] (`allowed_hosts`, Workbench access off), re-run `ship.yml` with `workflow_dispatch` for that slug |
| Story name differs between environments | `versionReplace` matches by name → a **new** story appears, or the wrong one is replaced | Names must be identical in every environment (`story.meta.yaml: name`); fix the name in the dev story through `/tines-build-story`, re-export, re-ship; delete the stray story in Tines [BY HAND] |
| `new: true` slug shipped, id not yet committed | The job opened a follow-up PR with the returned id | Merge it before the next ship of that slug, or the next `versionReplace` will not find the story by id |
| Draft already exists with the same `draft_name` | Behaviour VERIFY (item 6) | Delete the stale draft in Tines [BY HAND]; re-run |
| Rate limit (429) mid-run | The dispatcher backs off; `sleep 1` between stories | Re-run; idempotent by name |
| Import succeeded, recipients/monitor step failed | Draft exists without recipients | Re-run the step by hand with `--draft <id>` (`recipients-add`, `story-update`), then `cr-open` |
| The change request was opened twice | Two pending requests for one story | Cancel the older one in Tines [BY HAND]; note it in the PR |

## 7. Silencing or disabling the monitoring agent

The ops pair has a ladder of off-switches, gentlest first. Use the gentlest that solves the problem, and log anything below rung 2 in the ops thread.

| Rung | Switch | Effect | How | Reverses |
|---|---|---|---|---|
| 1 | **Kill switch** `ops_limits.enabled: false` | The sweep exits at its first Trigger on every entry (schedule, router hand-off, approval callback); the router keeps routing; the Mode 4 server keeps answering; **no credits spent** | Edit the `ops_limits` Resource [BY HAND], or `./scripts/tines resource-cas <ops_limits id> --key enabled --value false --if-value true --typed` (`--typed` sends JSON booleans rather than the strings `"false"` / `"true"`; keyed replace on a JSON Resource — CAS semantics VERIFY, item 19) | Set it back to `true` |
| 2 | **Token alert — Disable action** | Tines disables the `triage` (or `critic`) action automatically when `daily_tokens_disable` is crossed; the deterministic branches still run | Already set on the Status tab; lower the threshold if it is not firing soon enough | Re-enable the action on the storyboard [BY HAND] |
| 3 | **Run caps** `agent_runs_per_day_max`, `max_proposals_per_day`, `agent_credits_per_run_max` in `ops_limits` | Fewer agent runs / proposals per day; the pre-filter still logs findings | Edit the Resource [BY HAND]; mirror the change into `policies/cost-ceilings.yml` by PR | Raise them again |
| 4 | **Disable only the agent action** | The sweep runs its deterministic path; `has_anomaly` findings are recorded, none are diagnosed | Disable the `triage` action on the storyboard [BY HAND] — this is a change to a never-touch story, so it lands as a draft + change request under change control; note it in the ops thread | Re-enable in a change request |
| 5 | **Disable the sweep story** | Nothing sweeps; coverage drift and credit burn go unwatched until re-enabled; the router still posts failures to Slack and the DL | `./scripts/tines story-disable ops-story-health-monitor --env prod --want disabled --reason "…"` — a never-touch story, so via the **break-glass job** with two reviewers and a log line | `story-disable … --want enabled --reason "…"` (`rollback.yml` with `re_enable: true`) |
| 6 | **Disable the router** | Production stories still notify the **email DL** (every production story has both recipients) — nobody is blind, but nobody is deduped | Break-glass job, as above | `story-disable ops-error-router … --want enabled --reason "…"` (`re_enable: true`) |

Also:

- **Stale lock** (the sweep says "already running" forever): `./scripts/tines resource-cas <ops_lock id> --key lock --value free --if-value <stuck guid>` — or wait `stale_lock_minutes`, after which the sweep treats it as free.
- **Notification storm** (a burst of failures after a disable or a vendor outage): the router dedupes per story + action + 15 minutes and posts one thread per story per day; if the storm is the router's own Slack credential, the DL still receives everything.
- **A bad proposal was applied in dev** (`auto_apply_in_dev: true` added a recipient or a monitor flag you did not want): `./scripts/tines recipients-remove <slug> --env dev --address <url>` / `story-update --monitor-failures false`; set `auto_apply_in_dev: false` in the dev `ops_limits` if it keeps happening.
- **A proposal PR (`ops-proposal`) is wrong:** close it; mark the proposal `rejected` with a reason in `ops_alert_proposals` — the story feeds rejected proposals back into the next run so the agent does not repeat it.

**Re-enable checklist** after any rung ≥ 4: the lock is `free`; `ops_limits.enabled` is `true`; the token alert thresholds are still set; the first sweep after re-enable is watched in the ops thread; `ops_baselines` may need a day to re-settle (the daily 06:00 branch rewrites them).

## 8. Recovering from drift

`drift.yml` opened a PR labelled `drift` because the tenant differs from `main`. The attribution table (from `GET /api/v1/audit_logs`: `user_email`, `operation_name`, `source`, `request_user_agent`, MCP activity rows flagged) tells you who and how.

- **The tenant change is wanted** (someone fixed something in the UI under change control, an approved monitor proposal changed a flag): merge the drift PR — `main` now equals the tenant, and the export in git carries the change with its attribution.
- **The tenant change is not wanted**: close the drift PR and roll back through §3 to the `main` state. If the change bypassed change control, that is a policy finding — check `policies/break-glass-log.md` and the tenant's audit log for the bypass reason.
- **The drift is a rejected change request** (§5): resolve `main`, not the tenant.

## 9. Rolling back a tenant-side skill

`tines-skills/<name>/SKILL.md` is code: `git revert` the commit, merge, and `skills.yml` runs `PUT /api/v1/skills/<name>` with the previous body (and a new `metadata.git_sha`). A rename rolls back the same way (the API rewrites references). A skill that must disappear is deleted only by `workflow_dispatch` with `confirm_delete=<name>` → `DELETE /api/v1/skills/<name>?team_id=`; removing the folder alone changes nothing in the tenant. Skill versioning on the Tines side is unpublished (VERIFY, item 14), so git is the version history.

## 10. Post-incident (every time)

1. Add the incident to `stories/<slug>/README.md` (change log: sha → what → why).
2. If break-glass was used, the log line is already in `policies/break-glass-log.md`; open the follow-up PR it names.
3. If the monitor proposed the rollback, mark the proposal `applied` in `ops_alert_proposals` (or `rejected` with a reason).
4. Confirm `drift.yml` was quiet the night after.
5. If a VERIFY item was settled by the incident (a draft collision, a version restore, a double notification), record it in `docs/VERIFY.md` with what changed in the repo.

## Verify in your tenant before presenting

Run `rollback.yml` once against the dev team (`env: dev`, a scratch story, `emergency: false`) and once with `emergency: true` on the same scratch story so the two-reviewer environment, the disable toggle, the notification burst and the log-line commit have all been seen. That exercise settles items 6, 7, 12 and 24 for your tenant.
