# `kit/` — the Tines Storyworks Starter Kit

_Spec: REPO-DESIGN.md §1 (purpose, plans), §7 (the kit story), §8 (Record types and Resources), §9 (dashboards), §10 (model providers), §11 (starter stories). The kit's one importable story lives in [`stories/kit-launch/`](../stories/kit-launch/README.md), so the scaffold's build, export, lint, review, ship, drift and rollback all apply to it unchanged; this folder holds everything around it._

The starter kit gets a new Tines Stories customer to three things fast:

1. **Storyworks on day 1.** Import one story, `[KIT] 00 · Launch Storyworks`, and answer its `kickoff` Page. The story creates your private repository from this template, commits a tenant-specific config, creates the Tines Agent Skills, the tracker's Record types and the kit's Resources, seeds the tracker, checks your model provider with one test call and one tool call, and writes a setup report.
2. **A repeatable way to build.** Every story you plan then moves through one lifecycle ([`storyline/`](../storyline/README.md)): intake → discover → design → build → verify → ship → operate → improve.
3. **Visibility.** A tracker of the stories you plan to build and the onboarding milestones, kept in git and in Records, with a dashboard on top of it.

Nothing the kit's agents produce is applied without a person. Agents author branches, pull requests, Records rows and proposals; people merge, approve and decide.

## Is your plan supported?

The kit branches on what was purchased and never assumes. The kickoff Page asks; `[KIT] 00` reads the answers.

| Tenant | What the kit does | Why |
|---|---|---|
| **Business or Enterprise, cloud, two licensed teams** | Everything below | Records, Dashboards and Workflow as API sit under Advanced Workflows on Business and above. The kit needs two standard teams, **dev** and **prod**; the ops team **is** the prod team |
| Business or Enterprise, **one licensed team** | The manual path, [`docs/community-path.md`](docs/community-path.md) | There is no separate dev team to build in, so the lifecycle's dev/prod split cannot hold. Teams are an add-on, and licensed teams start at 1 |
| Business or Enterprise **without Apps** | Everything except the App; the dashboard is a Page plus a Tines Dashboard | Apps is an add-on (its per-plan limits are a CONFLICT, VERIFY K19) |
| Cloud **without a Tunnel** | Everything except a local model inside a private network | The Tunnel is a cloud-only paid add-on, enabled through Tines support |
| **Self-hosted** | Everything except the Tunnel; a custom model provider is required | The Tunnel is not supported on self-hosted, and self-hosted tenants need a custom provider |
| **Community Edition** | The manual path, [`docs/community-path.md`](docs/community-path.md): generate the repository by hand, fill in `kit/tenant/config.yaml` by hand, keep the tracker in git only | No Records or Dashboards, 3 flows and 50 AI credits a month. `[KIT] 00` needs about 5–8 flows (VERIFY K30). AI Agent availability on Community is a CONFLICT (VERIFY K7) |

## The one import

Do this once, in the order given. [`ONBOARDING.md`](ONBOARDING.md) is the full day-1 runbook; [`../stories/kit-launch/README.md`](../stories/kit-launch/README.md) is the story's own page.

1. **Check the plan** (above). On Community Edition or with one licensed team, stop here and follow the manual path.
2. **In the prod team, which is the ops team**, create the credentials the kit uses — by **name**, never pasted anywhere else:
   - `tines_api_kit` — a team-scoped **Editor** API key of the ops team; `allowed_hosts` = your tenant host; Workbench access off.
   - `github_factory` — a short-lived, fine-grained GitHub token ([`docs/github-token.md`](docs/github-token.md)); `allowed_hosts` = `api.github.com`; Workbench access off. The name is fixed; the Page never chooses it.
   - `tines_api_readonly` — the scaffold's **Viewer** team key (the App's cost view reads AI usage with it).
   - `slack_bot` — only if your chat surface is Slack.
3. **Create the ops trio's six Record types** in the ops team, by hand, as `stories/ops-story-health-monitor/records/record-types.md` says. The monitoring sweep and the retros depend on them.
4. **Configure the model provider** in Settings → AI settings, if it is not the Tines-provided default ([`docs/llm-provider-matrix.md`](docs/llm-provider-matrix.md)). There is no API for this; the kit only reads it.
5. **Import** `stories/kit-launch/story.json` from the published template into the ops team — through the UI's story import, or `POST /api/v1/stories/import` with `new_name`, `data`, `team_id` and `mode: new`. **Only the maintainer release of that file is importable.** Until the release replaces it, the file is a labelled **SKELETON** with no actions: never import the SKELETON.
6. **Open the `kickoff` Page** on the **LIVE** story — `https://<your-tenant>.tines.com/pages/storyworks-kickoff` (whether the identifier survives import is VERIFY K8) — answer it and submit. A kickoff submitted in a change-control draft would write test records, not live ones (VERIFY K39).
7. **Read the setup report** — emailed to you, and committed to `kit/tenant/setup-report.json` in the new repository. `ok` or `partial` with every failure explained is day 1 done; [`docs/troubleshooting.md`](docs/troubleshooting.md) maps each failed step to a fix.
8. **Merge the setup-report PR first.** The report's push runs `kit.yml`, which opens a PR from `kit/config-<run_id>` that commits the kit's live story id into `stories/_manifest.yaml` and `policies/never-touch.yml`. Until it merges, `ship.yml` cannot change the imported kit and the bundle check fails on every other PR.
9. **Work through the `[BY HAND]` list** (below), then turn the runtime crew on.

## What the kickoff creates

| Where | What | When | Step in the report |
|---|---|---|---|
| GitHub | A **private** repository in your organisation, from this template (or, if generation is refused, created and copied file by file through the Contents API — slow, one commit per file) | always | `step_github`, `step_repo` |
| GitHub | `kit/tenant/config.yaml` — the tenant config commit: teams, plan, entitlements, the Tines-side model choice, the chat surface, credential **names**. Never the tenant host or an email ([`tenant/README.md`](tenant/README.md)) | always | `step_config` |
| GitHub | `kit/tenant/setup-report.json` — what happened, step by step, and the `[BY HAND]` list | always | `step_report` |
| Tines, ops team | Seven Tines Agent Skills from `tines-skills/` — created, never overwriting a skill of yours with the same name (that one is reported `exists`) | always | `step_skills` |
| Tines, ops team | The Record types `storyline_backlog`, `storyline_events` (skipped on the Starter Records tier) and `storyline_milestones` ([`records/README.md`](records/README.md)) | Records entitled | `step_record_types` |
| Tines, ops team | The kit's Resources: `kit_config`, `kit_state`, `kit_catalog`, `storyline_state_machine`, `storyline_limits`, `storyline_approvers`, `storyline_sync_lock`; `kit_tracker_view` only without Records; the ops trio's four Resources only when absent ([`resources/README.md`](resources/README.md)) | always | `step_resources` |
| Tines, ops team | The tracker, seeded: one `storyline_backlog` row per use case you picked, plus `example-enrich-ip` and `ops-story-health-monitor`, and the three onboarding milestones | Records entitled | `step_seed` |
| Tines, ops team | The Tines Dashboard "Storyworks" over the three Record types ([`dashboard/README.md`](dashboard/README.md)). Skipped while the dashboard export is the SKELETON | Records entitled | `step_dashboard` |
| Tines, ops team | The App "Storyworks": created and its draft files pushed; publishing and wiring its three endpoints are by hand | Apps entitled | `step_app` |
| Tines | A provider check: one tool-less call and one call with one tool, with a verdict of `ok`, `tool_calls_unreliable` or `failed` | AI Agent action entitled | `step_probe` |

`storyline_limits` is created with `enabled: false` and `guards_confirmed: false`, so **no AI Agent action in the kit runs** until a person has set the token alerts, attached the skills and switched both flags on.

## The `[BY HAND]` list

No API or Mode 2 session can do these. The setup report carries the same list and marks each item `done`, `open` or `not_needed`; [`ONBOARDING.md`](ONBOARDING.md) says how to do each one.

1. **Pre-flight:** `allowed_hosts` on `tines_api_kit` (your tenant host) and `github_factory` (`api.github.com`).
2. **AI provider:** configure or confirm it in Settings → AI settings.
3. **Token alerts:** a token-usage alert (Notify, then Disable action) on the Status tab of all five kit AI Agent actions — `llm_probe`, `llm_tool_probe`, `planner`, `brief_writer`, `retro_writer` — at the numbers in `policies/cost-ceilings.yml`.
4. **Skills:** attach `backlog-planning` to `planner`, `story-brief-writing` to `brief_writer`, `story-retrospective` to `retro_writer`, and pin the tenant's fast model on those three actions. Resolve every skill the report lists as `exists`.
5. **Credits:** per-team AI credit allocation and credit-alert thresholds.
6. **Apps** (if entitled): enable Apps for the ops team at `/settings/apps`; publish the App; wire its three endpoints.
7. **Tunnel:** for a local model, a Tunnel that all teams can access ([`docs/llm-local-via-tunnel.md`](docs/llm-local-via-tunnel.md)).
8. **Change control:** tenant policies "Enable by default" and "Require approval for all changes" on.
9. **Builders' Tines roles:** every builder's Tines account is a Viewer, or not a member, in the prod (ops) team. The Tines Stories MCP server acts with the user's own permissions, so this is what stops a Mode 2 session writing there.
10. **Approvers:** where the tenant has SSO group-based page access, turn it on and set the `gate_decision` Page's access to **Via SSO**, restricted to the approvers group; add the GX and unpark approvers to `storyline_approvers`.
11. **Ops trio:** its six Record types exist; add the `ops_findings` and `ops_alerts` type ids to `kit/tenant/config.yaml` by PR.
12. **GitHub:** branch protection on `main` (the one required check `storyline`, a CODEOWNERS review, no self-merge); `<org>` in `.github/CODEOWNERS` and the teams in `storyline/gates/approvers.yaml`; the `tracker-bot` GitHub App on this repository only; the environments `production` (with required reviewers: the G5a team in `storyline/gates/approvers.yaml`, no individuals), `break-glass`, `tracker` and `kit-sync` and their secrets, always as environment secrets, never repository secrets; Actions allowed to create pull requests; the pull-request labels `tracker`, `tracker-drift` and `kit-config` (`tracker-pull.yml` and `kit.yml` apply them but never create them); Actions enabled on the new repository (VERIFY K12).
13. **Tracker webhooks:** first **rotate the secrets** of `tracker_sync_in`, `tracker_outbox` and the three App endpoint Webhooks (VERIFY K8), then copy the two tracker URLs into `TRACKER_SYNC_URL` and `TRACKER_OUTBOX_URL` in the `tracker` environment.
14. **Revoke the provisioning token,** or let it expire.
15. **Editor:** `/tines-connect` in each builder's editor.
16. **Enable the runtime crew:** after items 3 and 4, set `storyline_limits.guards_confirmed` and `storyline_limits.enabled` to true.
17. **Last:** run `kit.yml` and `tracker-pull.yml` once (Actions → Run workflow).

## What is in this folder

| Folder | What it holds | Read |
|---|---|---|
| [`tenant/`](tenant/README.md) | The shape of `kit/tenant/config.yaml` and the setup report; what the day-1 PRs change | when the report arrives |
| [`catalog/`](catalog/starter-stories.yaml) | The ten starter stories the Page offers, and the verified Story Library ids — the only ids any agent or Page may cite | before picking use cases |
| [`tracker/`](tracker/README.md) | `backlog.yaml` and `milestones.yaml` — the tracker in git, the system of record — with their schemas, the field map and the sync contract | before the first tracker PR |
| [`records/`](records/README.md) | The three Record type bodies section A creates | if A18 fails |
| [`resources/`](resources/README.md) | Example values of every kit Resource (placeholders only) | if a Resource looks wrong |
| [`bundle/`](bundle/README.md) | `kit-bundle.json`, generated by `./scripts/kit bundle` — the one file the kit story reads from the repository | never by hand |
| [`dashboard/`](dashboard/README.md) | The App source and the Tines Dashboard export, and what each dashboard can and cannot render | when choosing a dashboard |
| [`docs/`](docs/llm-provider-matrix.md) | The model-provider matrix, the local-model path, the editor-side model, the GitHub token, the Community path, troubleshooting | as needed |
| [`ONBOARDING.md`](ONBOARDING.md) | The day-1, week-1 and week-4 runbook | on day 1 |

## After day 1

- **The tracker keeps git and Records in step.** On every merge to `main`, `tracker-sync.yml` pushes the tracker into Records (section B). Every 30 minutes `tracker-pull.yml` pulls decisions made in Tines and opens a tracker PR; nothing made in Tines is true in git until a person merges that PR ([`tracker/README.md`](tracker/README.md)).
- **The generated Resources and the skills follow `main`.** `kit-sync.yml` re-pushes `storyline_state_machine`, `kit_catalog`, `kit_config`, the `storyline_limits` keys it owns and the Tines Agent Skills on every merge; `enabled` and `guards_confirmed` stay under people's control.
- **Three tool-less runtime crew** run in `[KIT] 00` section D when the tracker changes state: `brief_writer` drafts intake briefs, `planner` proposes sequencing, `retro_writer` drafts retros. Code decides when each runs, behind a kill switch and daily caps; their outputs are proposals.
- **The kit story is monitored like any other story** by the ops trio, and changed only through its own change request. Kill switch: `storyline_limits.enabled`.

## Verify in your tenant before relying on it

None of these is a headline claim. Each is a row in [`../docs/VERIFY.md`](../docs/VERIFY.md), with the method in REPO-DESIGN.md §16.

| Item | What is assumed | Why it matters here |
|---|---|---|
| **K8** | Import keeps Page URL identifiers and Webhook paths and secrets | The kickoff link, the report links, and why secrets are rotated after import. **The template is not published until K8 is confirmed** |
| K2 | A hook can tell which subagent is calling | Until confirmed, `phase-gate.sh` denies every Tines Stories MCP server call, so no build can start |
| K7 · K19 · K20 · K28 | Plan conflicts: the AI Agent action on Community; Apps limits; custom providers by plan; Workbench as an add-on | Which path and which dashboard you get |
| K11 · K12 · K13 · K44 | GitHub token permissions, readiness of a generated repository, Contents API details, the raw media type | Repository creation and the config commit |
| K16 · K17 · K18 | The Record type create body; Dashboard import by type name; App file pushes and publishing | Record types, the Dashboard, the App |
| K30 | How flows are counted for one story with several entry points | Whether `[KIT] 00` fits your flow allowance |
| K39 · K41 | API-created Records are live in a change-controlled story; what a team-scoped Editor key may call | Seeding; every Tines API call the kit makes |
