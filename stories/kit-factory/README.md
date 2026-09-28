# `[KIT] 00 · Run the story factory` — the one importable kit story

**Slug:** `kit-factory` · **Mode badge:** **none** — no MCP surface; its AI Agent actions are tool-less, except the one-tool provider probe, which is a check and not a runtime tool path · **Tier:** ops · **Owner:** platform (a role; CODEOWNERS `/stories/kit-*` → security-platform) · **Team:** the **ops team, which is the manifest's prod team** · **Descends from:** — (built from [`DESIGN.md`](DESIGN.md), which is §7 of [`REPO-DESIGN.md`](../../REPO-DESIGN.md)) · **Never-touch:** by the name pattern `^\[KIT\]`, and by id after the setup-report PR

> `story.json` in this folder is a **labelled SKELETON** with no actions. The real story — about 340 actions in six storyboard Sections — is specified action by action in [`sections/`](sections/) and [`pages/`](pages/), and is built through Mode 2 with [`build-prompts.md`](build-prompts.md) by the §15.6 maintainer release, which replaces `story.json` with an export made with `randomize_urls=true`. **Never import the SKELETON, and never hand-edit `story.json`.**

## Purpose

One import and one Page give a new customer a working story factory on day 1. Submitting the `kickoff` Page creates the customer's private repository from this template, commits a tenant-specific config, creates the Tines Agent Skills, the tracker's three Record types and the kit's Resources, seeds the tracker, imports a Dashboard and creates an App when entitled, checks the chosen model provider with one test call and one tool call, and writes a setup report to the repository and to a Page. After day 1 the same story keeps the tracker in sync between git and Records, lets people add use cases and decide the Tines-side gates, runs three tool-less runtime specialists on state changes, and lets the repository pull Tines-side changes as pull requests. It never writes to GitHub after day 1, never auto-applies a proposal, and never decides a gate. (This paragraph, with the mode badge and the entry points, is the on-canvas Note.)

## Sections

| Section | What it does | Spec | Built by |
|---|---|---|---|
| **A** kickoff and provisioning | The kickoff Page → validation → teams → the `kit_state` ledger → provider check → repository (template or Contents-API fallback) → config commit → Skills → Record types → Resources → seeding → Dashboard → App → report, `setup_report` Page, email | [`sections/A-kickoff-and-provisioning.md`](sections/A-kickoff-and-provisioning.md) | P-K2 – P-K9, P-K11 |
| **F** provider probe | `llm_probe` (tool-less) and `llm_tool_probe` (one Custom tool) → a verdict for the report | [`sections/F-llm-probe.md`](sections/F-llm-probe.md) | P-K10 |
| **B** tracker sync in | repo → Records on every merge touching `kit/tracker/**` and nightly in full, under a compare-and-swap lock | [`sections/B-tracker-sync-in.md`](sections/B-tracker-sync-in.md) | P-K12 |
| **C** tracker Pages and App endpoints | `tracker_home` → the Page dashboard, add a use case, decide G0 / G6 / G7 / GX / unpark; three App endpoints | [`sections/C-tracker-pages-and-endpoints.md`](sections/C-tracker-pages-and-endpoints.md) | P-K13 |
| **D** specialist dispatch | deterministic routing to `brief_writer`, `planner`, `retro_writer` behind a kill switch and daily caps; nudges; the improve check | [`sections/D-dispatch-specialists.md`](sections/D-dispatch-specialists.md) | P-K14 |
| **E** tracker outbox | Records → repo: a response-enabled Webhook `tracker-pull.yml` calls (`pull`, `ack`, `snapshot`) | [`sections/E-tracker-outbox.md`](sections/E-tracker-outbox.md) | P-K13 |

Why one story with Sections and no sub-stories: story import does not bring embedded sub-stories along, and a cross-story Send to Story reference built in one tenant would not resolve in another (§7.1).

## Entry points

| Section | Entry | Type | Access | Notes |
|---|---|---|---|---|
| A | `kickoff` | root Page | Only team members | URL identifier `story-factory-kickoff` (K8 after import). Submit on the **LIVE** story |
| A | `kickoff_test` | Webhook | — | **dev only**: stops at `is_dev_kickoff_test` unless `RESOURCE.kit_config.environment == "dev"` |
| B | `tracker_sync_in` | Webhook | Secret | called by `tracker-sync.yml` (`TRACKER_SYNC_URL`, environment `tracker`) |
| C | `tracker_home` | root Page | Only team members | URL identifier `story-factory-tracker` |
| C | `app_add_use_case`, `app_gate_decision`, `app_costs` | Webhooks (App endpoints) | — | Apps only; wired `[BY HAND]`; `app_gate_decision` refuses every call until K18 |
| D | `dispatch_sweep` | schedule `*/15 * * * *` | — | watchdog 1,800 s |
| D | `specialist_test` | Webhook | — | **dev only**: the runtime eval cases (`./scripts/sdlc eval-run kit-factory --entry-action specialist_test`) |
| E | `tracker_outbox` | Webhook, response-enabled | Secret | called by `tracker-pull.yml` (`TRACKER_OUTBOX_URL`, environment `tracker`) |

How Tines counts flows for one story with several entry points is **K30** (estimate: about 5–8).

## The import (`[BY HAND]`, once)

1. **Plan check.** The kit needs Business or Enterprise with **two licensed teams** (a dev team and a prod team); the ops team **is** the prod team. On **Community Edition** (3 flows), or with one licensed team, **do not import** — follow `kit/docs/community-path.md`.
2. **In the ops (prod) team**, create the credentials below, and the ops trio's six Record types as `stories/ops-story-health-monitor/records/record-types.md` says.
3. **Import** `stories/kit-factory/story.json` **from the §15.6 release of the template** — never the SKELETON — into the ops team, through the UI's story import or `POST /api/v1/stories/import` (`new_name`, `data`, `team_id`, `mode: new`).
4. **Open the `kickoff` Page** (`https://<your-tenant>.tines.com/pages/story-factory-kickoff`; whether the identifier survives import is K8) on the LIVE story and submit it.
5. Read the **setup report** (emailed link, and `kit/tenant/setup-report.json` in the new repository). Its push opens **the setup-report PR** (`kit.yml` → `./scripts/kit apply-config`), which commits the kit's live id into `stories/_manifest.yaml` (`kit-factory.prod.story_id`) and `policies/never-touch.yml` (`story_ids`), so `ship.yml` changes this copy through `versionReplace` and `guard-mcp.sh` protects it by id. Merge it first.
6. Work through the `[BY HAND]` list below, in order.

## Credentials — by name only

| Name | What | `allowed_hosts` | Used by |
|---|---|---|---|
| `tines_api_kit` | team-scoped **Editor** API key of the ops team; Workbench access off | the tenant host | every Tines API call in sections A–E (provisioning, Records, Resources) — the story's only Tines API credential (K41) |
| `github_factory` | a **fine-grained** GitHub token — a fixed name the Page never chooses; all repositories of the one organisation; expiry ≤ 7 days; **revoked after day 1** (`kit/docs/github-token.md`, K11); Workbench access off | `api.github.com` | section A only (A10–A16, A29) |
| `tines_api_readonly` | the scaffold's **Viewer** team key | the tenant host | `app_costs` (C6) and `get_story_credits` (D9): `GET /api/v1/ai_usage` (K38) |
| `slack_bot` | optional; only when the chat surface is Slack (a fixed name: K9) | the Slack API host | `send_notice_slack` (D) |

No token, key or webhook URL is ever typed into a Page, committed, emailed or shown in the report.

## Resources and Records

- **Resources** (created by A7 and A19, read by name): `kit_config`, `kit_state`, `kit_catalog`, `sdlc_state_machine`, `sdlc_limits`, `sdlc_approvers`, `sdlc_sync_lock`, and `kit_tracker_view` only without Records; the ops trio's `ops_limits`, `ops_lock`, `ops_responders`, `ops_routing` when absent. Shapes: `kit/resources/*.example.json`. **`sdlc_limits.enabled` and `guards_confirmed` start false and only a person sets them.**
- **Record types** (created by A18): `sdlc_backlog`, `sdlc_events` (skipped on the Starter tier), `sdlc_milestones` (`kit/records/`). Sections B–E read and write them **only through the Records API** by the ids in `kit_state` — never Record actions.

## AI Agent actions

| Action | Section | Tools | Model | Skill (`[BY HAND]`) | Token alert (Notify / Disable, daily, `[BY HAND]`) | Budget line |
|---|---|---|---|---|---|---|
| `llm_probe` | F | none | tenant fast default (not pinned) | — | 5,000 / 10,000 | `kit-factory/llm_probe` |
| `llm_tool_probe` | F | one Custom tool (`probe_constant`) | tenant smart default (not pinned) | — | 10,000 / 20,000 | `kit-factory/llm_tool_probe` |
| `brief_writer` | D | none | **fast, pinned** | `story-brief-writing` | 100,000 / 200,000 | `kit-factory/brief_writer` |
| `planner` | D | none | **fast, pinned** | `backlog-planning` | 60,000 / 120,000 | `kit-factory/planner` |
| `retro_writer` | D | none | **fast, pinned** | `story-retrospective` | 75,000 / 150,000 | `kit-factory/retro_writer` |

Each has an Output schema and a Trigger directly after it on schema fields only. The runtime specialists' instructions and schemas live in `sdlc/agents/runtime/*` and are pasted by P-K14; their evals are `sdlc/evals/agents/runtime-*.cases.yaml`.

## The `[BY HAND]` list

The setup report carries this list and marks each item `done`, `open` or `not_needed` (full text: [`sections/A-kickoff-and-provisioning.md`](sections/A-kickoff-and-provisioning.md)):

1. **Pre-flight:** `allowed_hosts` on `tines_api_kit` (the tenant host) and `github_factory` (`api.github.com`).
2. **AI provider:** configure or confirm it in Settings → AI settings (no API; the kit only reads `GET /api/v1/ai_providers`).
3. **Token alerts** on all five AI Agent actions' Status tabs (Notify, then Disable action).
4. **Skills:** attach the three runtime skills; pin the fast model on `planner`, `brief_writer`, `retro_writer`; resolve every skill reported `exists`.
5. **Credits:** per-team AI credit allocation and credit-alert thresholds.
6. **Apps:** enable at `/settings/apps` (if entitled); publish the App; wire its three endpoints.
7. **Tunnel:** for a local model, a Tunnel accessible by all teams.
8. **Change control:** tenant policies "Enable by default" and "Require approval for all changes" on.
9. **Builders' Tines roles:** Viewer, or not a member, in the prod (ops) team — this is what stops a Mode 2 session writing there.
10. **Approvers:** SSO group-based page access and the `gate_decision` Page restricted to the approvers group; add the GX and unpark approvers to `sdlc_approvers`.
11. **Ops trio:** its six Record types exist; add the `ops_findings` and `ops_alerts` type ids to `kit/tenant/config.yaml` by PR.
12. **GitHub:** branch protection on `main` (the one required check `sdlc`, a CODEOWNERS review, no self-merge); `<org>` in CODEOWNERS and the teams in `sdlc/gates/approvers.yaml`; the `tracker-bot` GitHub App on this repository only; the environments `production` (required reviewers — G5a: the G5a team in `sdlc/gates/approvers.yaml`, no individuals), `break-glass`, `tracker`, `kit-sync` and their secrets (a libsodium sealed box, so always by hand); Actions allowed to create pull requests; the pull-request labels `tracker`, `tracker-drift` and `kit-config` (`tracker-pull.yml` and `kit.yml` apply them but never create them); Actions enabled (K12).
13. **Tracker webhooks:** **rotate the secrets** of `tracker_sync_in`, `tracker_outbox` and the three App endpoints first (K8), then copy the two tracker URLs into `TRACKER_SYNC_URL` and `TRACKER_OUTBOX_URL` in the `tracker` environment.
14. **Revoke the provisioning token** (or let it expire).
15. **Editor:** `/tines-connect` in each builder's editor.
16. **Enable the runtime specialists:** set `sdlc_limits.guards_confirmed` and `sdlc_limits.enabled` to true — only after items 3 and 4.
17. **Last:** run `kit.yml` and `tracker-pull.yml` once (Actions → Run workflow).

## Monitoring

- Story-level **Notify when any action fails** (`monitor_failures`) on; recipients = the ops router + the ops email DL, from the manifest (set by `ship.yml`).
- **Notify if no events emitted** on `dispatch_sweep` at **1,800 s** (2 × 15 minutes).
- Events kept **30 days** (raised by hand above the default).
- The ops trio monitors this story like any other: it is large, and it can fail (§14 con 12).

## Runbook — when the router pages for this story

| Signal | Likely cause | First check | Fix path |
|---|---|---|---|
| `acquire_sync_lock` or `release_sync_lock` failing; the lock reads a run guid for hours | a sync died holding the lock | `sdlc_sync_lock` value; the last B run | set `{lock: "free"}` on the Resource by hand; the next push or the nightly run re-sends the full state |
| `list_backlog` / `sync_create_row` failing with 4xx | a record type or field id changed; K5/K16 body shapes | `kit_state.rt_*` and `fields_*`; the action's logs | re-run A18's stores, or fix the ids in `kit_state`; a story change goes through `/tines-build-story kit-factory` and a PR |
| `dispatch_sweep` silent for 30 minutes (watchdog) | the story is disabled, or the schedule broke | the story's status; the last event | re-enable through the change-control path; never edit the live story by hand |
| `count_runs_today` failing | K35 aggregate body; the Starter tier (no `sdlc_events`) | the action's logs; `records_tier` | the runtime specialists stay held (fail closed) until fixed |
| `brief_writer` / `planner` / `retro_writer` failing (schema, timeout) | the provider, the pinned model, a changed instruction | `step_probe`; the action's Status tab; the last `sdlc_events` escalation | re-run the probe (re-emit `ent_ai_agent_action`, VERIFY — `sections/F-llm-probe.md`); run the runtime eval cases in dev; fix by PR |
| a token alert fired (Notify) | an unusual volume of state changes | `sdlc_events` `specialist_run` rows today | caps in `sdlc_limits.runtime`; set `sdlc_limits.enabled` to false to stop all runtime specialists |
| `tracker_outbox` answering errors or timing out | too many pending rows for 30 s (K15) | the answer; the count of pending rows | merge or close the open tracker PRs; chunk the pull (a story change by PR) |
| the story itself is wrong | a shipped change | `git log --oneline -- stories/kit-factory/story.json` | `/tines-rollback kit-factory previous` |

**Kill switches:** `sdlc_limits.enabled` (runtime specialists and the tracker sync) · `ops_limits.enabled` (the ops sweep). Disabling the story is break-glass only.

## Verify in your tenant before relying on it

Nothing below is stated as fact anywhere in this folder; each is in `docs/VERIFY.md`.

| Item | What | Where it matters |
|---|---|---|
| **K8** | Import keeps Page URL identifiers and Webhook paths and secrets — **the template is not published until this is confirmed** | the Page links; secret rotation |
| K5 · K35 | Records API v2 search and aggregate bodies | B–E Lists; D2's daily cap |
| K7 | AI Agent action on Community | section F; the Community path |
| K9 · K10 | Credentials by computed name; a missing Resource reads as null | A4, A7, A19; `slack_bot` |
| K11 · K12 · K13 · K44 | GitHub token scopes, readiness, Contents PUT, raw media type | A10–A16, A29 |
| K14 | The base64 formula name | A12, A16, A29 |
| K15 | Response-enabled Webhook sizing | section E |
| K16 · K17 · K18 | Record-type body; Dashboard import by name; Apps (file pushes, publishing through Mode 2, endpoint identity) | A18, A23, A24, C6 |
| K22 – K26 | Provider details; per-run model choice | section F |
| K27 | Skill attachments in exports and imports | P-K14; the `[BY HAND]` list |
| K29 · K31 · K32 · K33 | ARTIFACT size; Page behaviour; CSV Tables; explode ordering and loops | D4, D6; the Pages; A12–A22 |
| K30 | Flow counting for a multi-entry story | the plan |
| K36 · K37 · K38 · K39 · K40 · K41 | Tunnel; eval-run URL; `ai_usage` scope; live API Records; Resource locking; Editor key scope | §10; D10; C6/D9; A21; `sdlc_approvers`; every call |

## Change log

| Short sha | Date | What changed | Change request |
|---|---|---|---|
| — | 2026-09-27 | SKELETON `story.json`, meta, design, section and Page specs, build prompts and tests (REPO-DESIGN.md §15.3) | — (not built yet; the §15.6 release builds and exports it) |
