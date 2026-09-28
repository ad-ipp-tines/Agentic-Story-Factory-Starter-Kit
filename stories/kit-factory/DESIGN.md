# `[KIT] 00 · Run the story factory` — design

_This is **§7 of [`REPO-DESIGN.md`](../../REPO-DESIGN.md), carried in full with the story** (the scaffold's convention: `stories/ops-story-health-monitor/DESIGN.md` is §5 of the root design). It is the design the kit story's own lifecycle gates on: **G1 and G2 are decided on this file and on [`sections/`](sections/)** before the §15.6 maintainer release builds the story (REPO-DESIGN.md §15.6 step 1). Mode badge: **none**._

**How to read this folder.**

| Want | Read |
|---|---|
| What the story is and what it does, at design level | this file — §7 below, unchanged from REPO-DESIGN.md |
| Every action with its type, key options, formulas, branches and failure path | [`sections/A-kickoff-and-provisioning.md`](sections/A-kickoff-and-provisioning.md) · [`sections/F-llm-probe.md`](sections/F-llm-probe.md) · [`sections/B-tracker-sync-in.md`](sections/B-tracker-sync-in.md) · [`sections/C-tracker-pages-and-endpoints.md`](sections/C-tracker-pages-and-endpoints.md) · [`sections/D-dispatch-specialists.md`](sections/D-dispatch-specialists.md) · [`sections/E-tracker-outbox.md`](sections/E-tracker-outbox.md) |
| Each Page, element by element | [`pages/kickoff.md`](pages/kickoff.md) · [`pages/setup-report.md`](pages/setup-report.md) · [`pages/tracker-home.md`](pages/tracker-home.md) · [`pages/tracker-view.md`](pages/tracker-view.md) · [`pages/add-use-case.md`](pages/add-use-case.md) · [`pages/gate-decision.md`](pages/gate-decision.md) |
| How the story is built (Mode 2, section by section) | [`build-prompts.md`](build-prompts.md) — P-K1 to P-K14 |
| Credentials, Resources, Records, agents and budgets by name | [`story.meta.yaml`](story.meta.yaml), `policies/cost-ceilings.yml` (`kit-factory/*`) |
| What a run must produce | [`tests/expectations.yaml`](tests/expectations.yaml), [`tests/sample-event.json`](tests/sample-event.json), [`tests/samples/`](tests/samples/) |
| Import, the `[BY HAND]` list and the runbook | [`README.md`](README.md) |

**Precedence.** §7 below is the design. The section files refine it to build level without changing what it decides; every place where a name or a split differs is listed in Appendix B. If a section file and §7 disagree on anything else, §7 wins and the section file is fixed.

`story.json` in this folder is a **labelled SKELETON** until the §15.6 release replaces it with a real export made with `randomize_urls=true`. It is never hand-written.

---

## 7. The starter kit story, action by action, and its Page specs

### 7.1 Shape

| Property | Value |
|---|---|
| Name · slug | `[KIT] 00 · Run the story factory` · `kit-factory` (source `stories/kit-factory/`) |
| Team | The customer's **ops team**, which is dedicated and never a personal team (the AI Agent action is unavailable in personal teams). **Topology: the ops team is the manifest's prod team** (`environments.prod.team_id`). Everywhere in this document, "the ops team" means that team. The scaffold's ops trio already lives there (its `records/record-types.md` creates the trio's Record types in the manifest's dev and prod teams), so the kit story, the trio's stories, their Record types and their Resources share one team, and `ship.yml`, `drift.yml` and `rollback.yml` reach the kit through the manifest's prod environment |
| Tier · owner | `tier: ops` · owner `platform` (a role). The story is listed in `never-touch.yml` by the pattern `^\[KIT\]`, has change control on, and is `locked` in prod after ship |
| Mode badge | **none**, meaning no MCP surface. Its AI Agent actions are tool-less, except the one-tool provider probe, which is a check and not a runtime tool path |
| Sections (storyboard Sections) | **A** kickoff and provisioning · **F** provider probe · **B** tracker sync in · **C** tracker Pages and App endpoints · **D** specialist dispatch · **E** tracker outbox |
| Entry points | A: root Page `kickoff`, plus the dev-only Webhook `kickoff_test` · B: Webhook `tracker_sync_in` · C: root Page `tracker_home` + three App endpoint Webhooks · D: a schedule (`*/15`) plus internal links from B and C, plus the dev-only Webhook `specialist_test` · E: response-enabled Webhook `tracker_outbox`. The two dev-only Webhooks stop at a Trigger on `RESOURCE.kit_config.environment == "dev"`, so they do nothing in the ops (prod) team. Roughly 5–8 flows; how Tines counts flows for a multi-entry story is K30 |
| Why one story with Sections, not sub-stories | Story import does not bring embedded sub-stories along, and a cross-story Send to Story reference built in one tenant would not resolve in another. Reusable blocks are therefore Sections inside the one story, and v1 has **no** Send to Story sub-stories |
| Credentials, by name, created `[BY HAND]` in the ops team before the first run | `tines_api_kit`: team-scoped Editor API key; `allowed_hosts` = the tenant host; Workbench access off. **`github_factory`** (a fixed name; the Page does not choose it): a fine-grained token (§13); `allowed_hosts` = `api.github.com`; Workbench access off; used only by section A. `tines_api_readonly`, the scaffold's Viewer key, for the App's cost endpoint. Optional `slack_bot` |
| Resources | Created by section A (§8.2). Formulas read them by name (`RESOURCE.<name>`) |
| Records | `sdlc_backlog`, `sdlc_events` and `sdlc_milestones`, created by section A through the API (§8.1). Sections B–E read and write them **only through the Records API** in HTTP Request actions, using the type and field ids in `kit_state`, never through Record actions (§7.4), so nothing depends on how an import resolves record types (K6) |
| AI Agent actions | `llm_probe`, `llm_tool_probe` (F); `planner`, `brief_writer`, `retro_writer` (D). Each needs an output schema, a Trigger after it on a schema field, a token alert on the Status tab `[BY HAND]`, and a budget line in `policies/cost-ceilings.yml`. `planner`, `brief_writer` and `retro_writer` also need their skill attached `[BY HAND]` and the fast model pinned on the action (§5.2); the two probes stay skill-less |
| Monitoring | Recipients = the ops router + the email distribution list (manifest). `monitor_failures` on. Watchdog on the `dispatch_sweep` schedule at 1,800 s (2 × 15 min). Events kept 30 days |
| Change control | **Submit the kickoff on the LIVE story.** A Record action inside a change-control draft writes *test* records. Section A creates records through the API with `test_mode` off, so they are live; K39 |

**Import (`[BY HAND]`, once).**
1. The ops team is the prod team (above); it and the dev team must exist, which needs two licensed teams (§1.4). Create the credentials above in the ops team. Create the ops trio's six Record types there too, by hand, as the scaffold's `records/record-types.md` says (§11).
2. **On Community Edition, stop here: do not import `[KIT] 00`.** It needs 5–8 flows (K30) and Community has 3; follow `kit/docs/community-path.md` instead.
3. Import `stories/kit-factory/story.json` from the template repository into the ops team, through the UI's story import or `POST /api/v1/stories/import` (`new_name`, `data`, `team_id`, `mode: new`). The file is the §15.6 release, never the SKELETON.
4. Open the `kickoff` Page. Its root URL is `https://<your-tenant>.tines.com/pages/<url-identifier>`; whether the identifier survives import is K8.
5. After provisioning, the **setup-report PR** — `kit.yml`'s apply-config PR, which runs on the push of `kit/tenant/setup-report.json` (A29) — commits the kit's live story id (`kit_story_id` in the report) into `stories/_manifest.yaml` (`kit-factory.prod.story_id`) and into `policies/never-touch.yml` `story_ids`, so `ship.yml` changes this copy through `versionReplace` and `guard-mcp.sh` protects it by id.

### 7.2 Section A — kickoff and provisioning (deterministic)

Every HTTP Request action carries the scaffold hardening: `retry_on_status [429, 500-599]`, 6 retries, emit failure event **Always**, and a failure path. A failure never stops the section silently. The failure path goes to `step_failed` (an Event Transform), which records `step_<name> = {status: failed, http_status, message}` in `kit_state` (replace element) and **continues to the report**. Tines API calls use `https://<<kickoff.body.tines_tenant_host>>/api/v1/…` with the `tines_api_kit` credential; A3 rejects any host that does not match `^[a-z0-9-]+\.tines\.com$`. GitHub calls use `https://api.github.com/…` with the credential of the **fixed name `github_factory`**. The Page names no credential that section A uses, so no Page answer can point a credential at another host; `allowed_hosts` on both credentials is the report's first pre-flight item.

| # | Action (type) | Does | Endpoint / formula | On failure / branch |
|---|---|---|---|---|
| A1 | `kickoff` (Page, root) | §7.8 | — | — |
| A1b | `kickoff_test` (Webhook, dev only) | Takes a kickoff submission as JSON (`tests/sample-event.json`) and feeds `normalize`, so the kit's own acceptance can be tested by `eval-run` and the build skill's test step. A Trigger on `RESOURCE.kit_config.environment == "dev"` stops it in the ops (prod) team | — | not dev → stop |
| A2 | `normalize` (Event Transform, message-only) | Applies `DEFAULT()` to every field and trims values. Builds `use_cases[]` from the looping container, dropping `none`. Starter picks copy key, title, seed id, mode and owner from the catalog. `custom` rows get `key` = the title lowercased and hyphenated (≤ 48 characters, `-2`… on collision). Computes `target_date` = provisioned_at + the catalog offset, in UTC. Builds `config` = the future `kit/tenant/config.yaml`, **without** the tenant host or any email | formulas only | — |
| A3 | `is_valid_input` (Trigger) | Required fields present · tenant host `^[a-z0-9-]+\.tines\.com$` · org `^[A-Za-z0-9][A-Za-z0-9-]{0,38}$` · repo `^[A-Za-z0-9._-]{1,100}$` · credential names `^[a-z0-9_]{1,64}$` · consent true · **no field matches a token pattern** (`ghp_`, `github_pat_`, `gho_`, `ghs_`, `xox[bp]-`, `sk-`, `AKIA`, `Bearer `) | — | → `input_error` (Event Transform `{status: error, error_category: input, retryable: false, message}`) → A32 email → stop |
| A3b | `is_community` (Trigger) | `plan_tier == community_edition`, or `licensed_teams < 2` (the kit needs a dev and a prod team, §1.4) | — | → `community_path` (Event Transform) → email linking `kit/docs/community-path.md` → stop |
| A4 | `already_provisioned` (Trigger) | `RESOURCE.kit_state.status == "complete"` (reading a Resource that does not exist yet: K10) | — | → email linking the existing report → stop |
| A5 | `lookup_teams` (HTTP Request) | Resolves team ids by name | `GET /api/v1/teams?scope=standard&per_page=100` | → report |
| A6 | `resolve_teams` (Event Transform) | Matches the dev and prod team names exactly; the prod team is the ops team | — | The prod (ops) team must resolve (Trigger `has_ops_team`), else stop with "import into the prod team". A missing dev team is reported and the run continues |
| A7 | `create_kit_state` (HTTP Request) | Creates the run ledger, **only when `RESOURCE.kit_state` is null**. A partial earlier run resumes with its existing ledger, whose id sits in its own `self_id` key (written by a `…/replace` right after creation). It uses **flat keys**, because `/replace` addresses top-level keys | `POST /api/v1/global_resources` `{name: "kit_state", team_id, read_access: "TEAM", value: {status: "running", run_guid, repo: "", records_seeded: false, planner_last_run: ""}}` | → stop with an email; no ledger means no safe re-run |
| A8 | `list_ai_providers` (HTTP Request) | Reads which providers are enabled | `GET /api/v1/ai_providers` | → report |
| A9 | `check_provider` (Event Transform) | `tines_provided` ⇔ `provisioning_type: tines_provisioned`. `byo_anthropic`, `byo_openai`, `byo_bedrock` ⇔ `customer_provisioned` + `provider_type` `ANTHROPIC`, `OPEN_AI`, `AWS_BEDROCK`. `byo_azure_openai` and `local_*` ⇔ `customer_provisioned`, with a presumed `provider_type` of `OPEN_AI` (K23, K24). Picks `api_model_id` for `model_display_name` if given | — | sets `provider_status: ok \| not_found \| disabled \| mismatch` |
| A10 | `probe_template` (HTTP Request, GitHub) | Proves the token can read the template | `GET /repos/{template_owner}/{template_repo}/contents/README.md` with the raw media type (K44) | 401/403/404 → `step_github = failed: token cannot read template` → skip to F |
| A11 | `generate_repo` (HTTP Request, GitHub) | Creates the customer's repository from this template. The template repository must be marked as a template (`is_template: true`, set once by its owner, and only after the §15.6 release check passes) | `POST /repos/{template_owner}/{template_repo}/generate` `{owner: <org>, name: <repo>, description, private: true, include_all_branches: false}` → 201 | 422 → `repo_exists` Trigger: resume if `kit_state.repo == org/repo`, else fail "name taken". 403/404 → A12 |
| A12 | `fallback_repo` (group of actions) | **Contents-API fallback.** `POST /orgs/{org}/repos` `{name, private: true, description}` → read the file manifest from the template's `kit/bundle/kit-bundle.json` → explode → for each file, `GET …/contents/{path}` (raw) from the template → `PUT /repos/{org}/{repo}/contents/{path}` `{message: "kit: copy <path>", content: <base64>}`. Retries also on 409 (concurrent commits to the branch head) with retries 8 (K13, K33). Files over 1 MB are listed as `[BY HAND]` copies | as listed | Slow (one commit per file); the report says so and recommends the template path |
| A13 | `wait_for_repo` (HTTP Request) | Waits until the generated repository is readable | `GET /repos/{org}/{repo}/contents/README.md`, `retry_on_status [404, 429, 500-599]`, retries 6 (K12) | → report |
| A14 | `store_repo` (HTTP Request) | Records the repository in the ledger | `POST /api/v1/global_resources/{kit_state}/replace` `{key: "repo", value: "<org>/<repo>"}` | — |
| A15 | `read_bundle` (HTTP Request, GitHub) | Reads **the new repository's own** bundle, so the tenant and repository stay consistent: `{skills[], record_types[], resources[], dashboard, app_files[], file_manifest[], state_machine, catalog}` | `GET /repos/{org}/{repo}/contents/kit/bundle/kit-bundle.json` (raw) → `JSON_PARSE` | → report; B–E cannot be provisioned without it |
| A16 | `write_config` (HTTP Request, GitHub) | **The tenant-specific config commit** on `main` (the repository is brand new; branch protection comes later, `[BY HAND]`). The content is JSON, which a YAML 1.2 parser reads, so no YAML serialiser is needed in formulas | `PUT /repos/{org}/{repo}/contents/kit/tenant/config.yaml` `{message: "kit: tenant config (<run guid>)", content: <base64 of JSON>}` (the base64 formula name is K14) | → report |
| A17 | `push_skills` (explode → 3 actions) | **Creates** every Tines Agent Skill from the bundle in the ops team, and never overwrites a customer's skill: `GET` → 404 ⇒ `POST`; 200 ⇒ skip and report `exists`, unless the existing skill's `metadata.kit_run` shows the kit created it (a re-run), in which case `PUT`. Every skipped name is listed in `by_hand` as a conflict to resolve. `metadata` gains `kit_run` and `git_sha` (a flat string map). A 404 on the `GET` is excluded from `log_error_on_status` | `GET /api/v1/skills/{name}?team_id=` · `PUT /api/v1/skills/{name}` `{team_id, description, body, license, compatibility, metadata}` · `POST /api/v1/skills` `{team_id, name, description, body, license, compatibility, metadata}` | per skill → report. Attaching skills to actions is `[BY HAND]` (no API) |
| A18 | `create_record_types` (Trigger `ent_records` → explode) | First checks the quota: the Page's Records licence tier (`records_tier`) against the types the kit knows of, its own three plus the ops trio's six (no list endpoint for record types is in the research). On **Starter** (5 types) it does not create `sdlc_events`, keeps events in `events.jsonl` only, and reports it; the report also says that the ops trio's six types alone exceed Starter's 5. Then it creates `sdlc_backlog`, `sdlc_events`, `sdlc_milestones` unless `kit_state.rt_<name>` is set. Stores the id and the field name → field id map (`fields_<name>`) in `kit_state` (the response shape is K16) | `POST /api/v1/record_types` with the body from `kit/records/*.record-type.json` + `team_id` → `…/replace` into `kit_state` | → report |
| A19 | `create_resources` (explode) | Creates the §8.2 Resources that `kit_state` does not list yet. `kit_config` = config + `tenant_host` + `environment: "prod"`. `sdlc_limits` is created with **`enabled: false` and `guards_confirmed: false`**, so no AI Agent action runs before its token alert and skill exist. `sdlc_approvers` = the Page emails. `kit_tracker_view` only when Records are not entitled. The ops trio's `ops_limits`, `ops_lock`, `ops_responders` and `ops_routing` come from the scaffold's example files, with responders = the Page approvers, when absent. Stores the ids | `POST /api/v1/global_resources` `{name, value, team_id, read_access: "TEAM", description}` → `…/replace` | → report |
| A20 | `claim_seed` (HTTP Request) | Compare-and-swap so only one run seeds Records (creation is not idempotent) | `POST /api/v1/global_resources/{kit_state}/replace` `{key: "records_seeded", value: <run guid>, if_value: false}`. A 422 is excluded from errors and means already seeded | 422 → skip A21–A22 |
| A21 | `seed_backlog` (explode → HTTP Request) | One `sdlc_backlog` row per use case, plus `example-enrich-ip` and `ops-story-health-monitor` if absent: `phase intake`, `status active`, `specialist_due brief-writer` (when the AI Agent action is entitled), `rev 0`, **`pending_repo_sync: true`, `pending_base_rev: 0`, `outbox_seq: 1`** (so `tracker-pull.yml` brings the rows picked on the Page into git), timestamps in UTC | `POST /api/v1/records` `{record_type_id, field_values: [{field_id, value}]}` | → report |
| A22 | `seed_milestones` (explode → HTTP Request) | Three `sdlc_milestones` rows from the catalog (§11.1), with `pending_repo_sync: true` (the milestone type has no `outbox_seq` field; E3 returns pending milestones in `milestones[]`) | `POST /api/v1/records` | → report |
| A23 | `import_dashboard` (Trigger `ent_records`) | Imports the Dashboard over the three Record types (K17) | `POST /api/v1/dashboards/import` `{team_id, data: bundle.dashboard, mode: "new", new_name: "Story factory"}` | → report |
| A24 | `create_app` (Trigger `ent_apps`) | Creates the App and pushes its draft files (§9). **Publishing is `[BY HAND]` in the UI, or through Mode 2** (the Tines MCP server gained App tools on 2026-07-31, which the MCP docs page does not list yet: K18). App endpoints are wired `[BY HAND]` (Interfaces → App endpoints) | `POST /api/v1/apps` `{team_id, name, description}` → `PUT /api/v1/apps/{id}/files` `{files: bundle.app_files}` (it replaces every draft file, and `App.tsx` must be present) | → report |
| F1–F3 (A25–A27 on the canvas) | Provider probe | §7.3 | | |
| A28 | `compose_report` (Event Transform) | Builds `{status: ok\|partial\|failed, repo_url, kit_story_id, steps[{step, status, detail}], provider{status, model, input_tokens, output_tokens, credits_used, tool_calls}, created{skills[], record_types[], resources[{name, id}], dashboard, app}, by_hand[]}` from the `step_*` keys. `kit_story_id` comes from a `lookup_kit_story` HTTP Request just before it: the team's stories through `GET /api/v1/stories` (the scaffold's list call), matched on `META.story.name` | `GET /api/v1/stories` | — |
| A29 | `write_report` (HTTP Request, GitHub) | Commits the report to the repository | `PUT /repos/{org}/{repo}/contents/kit/tenant/setup-report.json` | report the failure on the Page |
| A30 | `finish_kit_state` (HTTP Request) | Marks the run complete | `…/replace` `{key: "status", value: "complete", if_value: "running"}` | — |
| A31 | `setup_report` (Page, mid-story) | §7.8 | per-run URL `PAGE.setup_report` | — |
| A32 | `email_report` (Email) | Sends the submitter (`kickoff.headers` email) the summary and the `PAGE.setup_report` link. No secret appears in the email | — | — |

**The `[BY HAND]` list the report always carries** (item by item, each marked done or not needed):
- **Pre-flight:** `allowed_hosts` is set on both credentials — `tines_api_kit` (the tenant host) and `github_factory` (`api.github.com`).
- **AI provider:** configure or confirm the provider in Settings → AI settings. There is no API; the kit can only check it with `GET /api/v1/ai_providers`.
- **Token alerts:** set a token-usage alert (Notify, then Disable action) on each AI Agent action's Status tab.
- **Skills:** attach them to `planner`, `brief_writer` and `retro_writer`. Resolve every skill the report lists as `exists` (A17 never overwrites a customer's skill).
- **Credits:** per-team AI credit allocation and credit-alert thresholds. There is no API.
- **Apps:** enable Apps for the ops team at `/settings/apps` (if entitled); publish the App; wire its three endpoints.
- **Tunnel:** for a local model, a Tunnel that all teams can access (§10.2).
- **Change control:** tenant policies "Enable by default" and "Require approval for all changes" on.
- **Builders' Tines roles:** every builder's Tines account is a Viewer, or not a member, in the prod team (which is the ops team). The Tines Stories MCP server acts with the user's own permissions, so this is what stops a Mode 2 session from writing there (§6.3).
- **Approvers:** where the tenant has SSO group-based page access, an admin turns it on in the Authentication settings, and the `gate_decision` Page's access is set to **Via SSO**, restricted to the approvers SSO group (§4.5 rule 2).
- **Ops trio:** its six Record types exist in the ops team (Import step 1); add the `ops_findings` and `ops_alerts` type ids to `kit/tenant/config.yaml` by PR, so `kit-sync.yml` puts them in `kit_config` for D6 and D9.
- **GitHub:**
  - branch protection on `main` (require the one check `sdlc`, which calls lint and review, and a CODEOWNERS review; no self-merge)
  - replace `<org>` in CODEOWNERS and the teams in `sdlc/gates/approvers.yaml`
  - create the `tracker-bot` GitHub App on this repository only, with write access to contents and pull requests (exact permission headings as for K11), and install it
  - create the GitHub environments `production` (with required reviewers: G5a depends on them — one team, the G5a team in `sdlc/gates/approvers.yaml`, and no individual reviewers, because `ship.yml` records that team as the G5a approver and fails without it), `break-glass`, `tracker` (the two webhook URLs and the `tracker-bot` App id and private key) and `kit-sync` (an ops-team Editor key) with their secrets. GitHub Actions secrets need a libsodium sealed box, which an HTTP Request action cannot produce, so this is always by hand.
  - allow GitHub Actions to create pull requests (K12)
  - create the pull-request labels `tracker`, `tracker-drift` and `kit-config` (Issues → Labels); `tracker-pull.yml` and `kit.yml` apply them but never create them, and open the PR unlabelled when one is missing
  - check that Actions is enabled on the new repository (K12)
- **Tracker webhooks:** first **rotate the secret on `tracker_sync_in`, `tracker_outbox` and every app-endpoint Webhook** (an import may keep the published template's values, K8), then copy the `tracker_sync_in` and `tracker_outbox` URLs from the storyboard into `TRACKER_SYNC_URL` and `TRACKER_OUTBOX_URL` in the `tracker` environment. They carry secrets, so they never appear in the report.
- **Revoke the provisioning token,** or let it expire (§13).
- **Editor:** run `/tines-connect` in each builder's editor.
- **Enable the runtime specialists:** after the token alerts are set and the skills are attached, set `sdlc_limits.guards_confirmed` and `sdlc_limits.enabled` to true. Until then no AI Agent action runs, and section B's kill switch also holds the tracker sync.
- **Last: run `kit.yml` and `tracker-pull.yml` once** (Actions → Run workflow), so the config PR and the rows picked on the Page reach git.

### 7.3 Section F — the provider probe (one test call, plus a tool check)

Gated by the Trigger `ent_ai_agent_action`. On Community, AI Agent availability is a CONFLICT (K7).

| # | Action | Configuration | Checks |
|---|---|---|---|
| F1 | `llm_probe` (AI Agent action, Task mode) | No tools, so it uses the tenant's **fast** model. A per-action model cannot be chosen per run, so the probe checks the tenant defaults (K26). Temperature 0 · timeout 60 s · retries 1. Prompt: return `{"ok": true, "nonce": "<run guid>"}`. Output schema `{ok: boolean, nonce: string}` | `ok` and the nonce match. Records `meta.model`, input and output tokens, `credits_used` (expect 0 on a custom or local provider) and the duration |
| F2 | `llm_tool_probe` (AI Agent action, Task mode, **one tool**) | Tool = a Custom tool (an action Group inside this story, `probe_constant`, an Event Transform returning `{value: 42}`). Adding the tool moves the action to the tenant's **smart** model. Output schema `{value: number, tool_called: boolean}` | `value == 42`. This tests streaming tool use, which a custom provider must support |
| F3 | `probe_verdict` (Event Transform) | — | `ok` · `tool_calls_unreliable` (F1 passes, F2 fails, so the report recommends running only **tool-less** agents on this model; §10.2) · `failed`. Both probes have budget lines (`runs_per_day_max: 5`) |

### 7.4 Section B — tracker sync in (repo → Records)

**Records access in sections B–E.** Every Records read and write in B–E is an **HTTP Request action** with `tines_api_kit`, never a Record action, and addresses types and fields by the ids section A stored in `kit_state.rt_<type>` and `kit_state.fields_<type>` (for the ops trio's types, by the ids in `kit_config`). The record types do not exist when the story is imported (A18 creates them afterwards), so a Record action could not resolve them, and re-pointing it would be a Mode 2 edit of the live, change-controlled kit story; the API needs neither. The calls: create `POST /api/v1/records`; update `PUT /api/v1/records/{id}`; read `POST /api/v2/records/search` and count `POST /api/v2/records/aggregate`, the documented successors of `GET /api/v1/records` and `POST /api/v1/records/query`. The v2 request bodies are K5 and K35; the v1 forms, whose `filters` are documented, are the fallback. In the tables below, "List", "Query", "Create" and "Update" name these calls.

| # | Action | Does |
|---|---|---|
| B1 | `tracker_sync_in` (Webhook, Secret access control, Include headers off) | Receives `{schema_version: 1, source_sha, entries[], milestones[]}` from `tracker-sync.yml` |
| B2 | `kill_switch` (Trigger) | `RESOURCE.sdlc_limits.enabled` |
| B3 | `normalize_payload` + `is_valid_payload` | `DEFAULT()`s; schema version 1; at most 500 entries; keys match `^[a-z0-9-]{1,64}$`; enum values in `RESOURCE.sdlc_state_machine` |
| B4 | `acquire_sync_lock` (HTTP Request) | `POST /api/v1/global_resources/<<RESOURCE.kit_state.res_sdlc_sync_lock>>/replace` `{key: "lock", value: STORY_RUN_GUID(), if_value: "free"}`. A 422 is excluded from errors → `is_locked` → exit; the next push or the nightly run re-sends the full state |
| B5 | `list_backlog` (HTTP Request, List, `sdlc_backlog`) | Up to 500 rows (server-side filtering is K5; this action lists everything and filters in B6) |
| B6 | `plan_upserts` (Event Transform) | Per entry, chooses `create`, `update` (repo rev above the row's rev), `update_repo_fields_only` (repo rev above, and the row has Tines-owned pending fields), `noop`, or `conflict`. Sets `transition` when the phase changes. Clears `pending_repo_sync` **only when the repo rev is above the row's `pending_base_rev`**, and then overwrites the Tines-owned fields with git's values. On a nightly full sync (`full: true`) it also overwrites any row that is not pending with git's values wherever they differ, whatever the revs (§6.5) |
| B7 | `create_row` / `update_row` (HTTP Request, Create / Update, after an explode) | Writes the row by type and field id, so no record-type reference needs re-pointing after import (K6 no longer applies to B–E) |
| B8 | `log_transition` (HTTP Request, Create, `sdlc_events`) → **section D** | `event_type: transition`, `actor_kind: ci`, `source_sha` |
| B9 | milestones | The same pattern for `sdlc_milestones` |
| B10 | `update_tracker_view` (only without Records) | `PUT /api/v1/global_resources/{kit_tracker_view}` with the whole value. This is safe only under the lock, because whole-value writes lose concurrent updates |
| B11 | `release_sync_lock` | `…/replace` `{key: "lock", value: "free", if_value: <run guid>}`. Also runs on every failure branch |

### 7.5 Section C — tracker Pages and App endpoints

| # | Action | Does |
|---|---|---|
| C1 | `tracker_home` (Page, root; §7.8) | Buttons: View backlog · Add a use case · Decide a gate · Milestones |
| C2 | `route_button` (Triggers on `tracker_home.body.button`) | Chooses the branch |
| C3 | `list_rows` (HTTP Request, List) → `to_table` (Event Transform: CSV text for the Table element, counts by phase for the Chart; K32) → `tracker_view` (Page, mid-story) | The Page fallback dashboard (§9) |
| C4 | `add_use_case` (Page, mid-story) → `normalize_use_case` → `create_row` (HTTP Request, Create: `phase intake`, `specialist_due brief-writer`, `pending_repo_sync true`, `pending_base_rev 0`, `rev 0`) → `log_event` → **D** | Intake from Tines |
| C5 | `list_open_gates` (HTTP Request, List: `open_gate` in G0, G6, G7, GX, or `phase parked`) → `gate_decision` (Page, mid-story) → `is_approver` (Trigger: the submitter email from the Page headers is in `RESOURCE.sdlc_approvers[<gate>]`) → `is_gate_open` (Trigger: the row's `open_gate` equals the gate chosen) → `apply_decision` (Event Transform: next phase and status from `RESOURCE.sdlc_state_machine.transitions`) → `update_row` (HTTP Request, Update: `pending_repo_sync true`, `pending_base_rev` = the row's `rev`, `outbox_seq + 1`) → `log_event` (`actor` = role; the Record keeps the approver's email for in-tenant audit, and git receives the role) → **D** | Tines-side human gates. G2, G4, G5a and G5b are **not** decidable here: they are a merge, a GitHub environment review and a change request |
| C6 | App endpoints (Apps only): `app_gate_decision`, `app_add_use_case`, `app_costs` (each a Webhook entry → … → a message-only Event Transform exit) | The same chains as C4 and C5. `app_costs` calls `GET /api/v1/ai_usage?relative_date=…&group_by=story` with `tines_api_readonly`, which sees only what that key may see (K38). Whether an App endpoint receives the viewer's identity is K18; until confirmed, **the App deep-links to the `gate_decision` Page for decisions** |

### 7.6 Section D — specialist dispatch (deterministic routing, tool-less agents)

| # | Action | Does |
|---|---|---|
| D1 | `dispatch_in` (from B8, C4, C5) and `dispatch_sweep` (a schedule, cron `*/15 * * * *`, with its watchdog) | Two ways in: state-change events, and a backstop that finds `specialist_status: pending` rows older than 15 minutes, planner or retro runs that are due, and gates to nudge (`gate_nudge_days`) |
| D2 | `kill_switch` (Trigger: `RESOURCE.sdlc_limits.enabled` **and** `RESOURCE.sdlc_limits.guards_confirmed`) · `count_runs_today` (HTTP Request, Query: count of `sdlc_events` where `event_type = specialist_run`, `agent = <x>`, today; K35) · `under_cap` (Trigger vs `RESOURCE.sdlc_limits.runtime.<x>.runs_per_day_max`) | Caps before any model call |
| D3 | `route_agent` (Triggers on `specialist_due` and the dispatch table) | brief-writer · planner · retro-writer · nudge |
| D4 | **brief-writer block:** `mark_running` (HTTP Request, Update) → `brief_context` (Event Transform: use case, entitlements from `RESOURCE.kit_config`, catalog names and ids from `RESOURCE.kit_catalog`) → **`brief_writer`** (AI Agent, §5.3.12) → `brief_ok` (Trigger on schema fields) → `filter_seed_ids` (Event Transform: keeps only ids in `kit_catalog`) → `render_brief` (Event Transform → Markdown) → `save_brief` (HTTP Request, Update: `brief`, `open_gate G0`, `specialist_status proposed`, `pending_repo_sync true`, `pending_base_rev` = the row's `rev`) → `log_run` (`sdlc_events` with `meta.model`, tokens, `credits_used`) → `notify_g0` (Email, or Slack when the chat surface is Slack) | |
| D5 | **planner block:** `claim_planner` (CAS on `kit_state.planner_last_run`, which is the debounce) → `backlog_snapshot` (HTTP Request, List) → **`planner`** (§5.3.11) → `planner_ok` → `save_proposals` (HTTP Request, Update per key: `proposal`, `specialist_status proposed`) → `log_run` → `notify` | |
| D6 | **retro-writer block:** `ops_evidence` (HTTP Request, List on `ops_findings` and `ops_alerts`, by the type ids in `kit_config`, filtered on the row's git-owned `prod_story_id`) → **`retro_writer`** (§5.3.13) → `retro_ok` → `save_retro` (HTTP Request, Update: `retro`, `specialist_status proposed`, `pending_repo_sync true`, `pending_base_rev` = the row's `rev`) → `log_run` → `notify` | |
| D7 | `nudge` | Re-notifies the decider of a gate that has been open longer than `gate_nudge_days` |
| D8 | Failure path of any block | `specialist_status: failed` → `sdlc_events` (`escalation`) → notify. A schema failure or `needs_human: true` always ends with a human |
| D9 | `improve_check` (on the `dispatch_sweep` schedule) | Evaluates the Tines-side `improve_trigger` conditions for every row in `operate` (§4.2): a high or critical `ops_findings` row for its `prod_story_id`, credits above 1.5 × `credit_estimate_monthly`, or a retro due from `live_since`. On a match it writes `phase: improve`, `status: active`, `pending_repo_sync true`, `pending_base_rev` = the row's `rev`, and logs a transition, which reaches git through the tracker PR |
| D10 | `specialist_test` (Webhook, dev only) | Feeds a test case straight into one agent block (brief-writer, planner or retro-writer) so `eval-run` can run `sdlc/evals/agents/runtime-*.cases.yaml` against the dev copy of `kit-factory`. A Trigger on `RESOURCE.kit_config.environment == "dev"` stops it in the ops (prod) team |

### 7.7 Section E — tracker outbox (Records → repo, pulled by GitHub)

| # | Action | Does |
|---|---|---|
| E1 | `tracker_outbox` (Webhook, Secret access control, **response-enabled**: the response comes from the first Exit action within 30 s; K15) | Receives `{op: pull \| ack \| snapshot, items?, open_pr_keys?}` |
| E2 | `route_op` (Triggers) | — |
| E3 | pull: `list_pending` (HTTP Request, List: `pending_repo_sync` true and `outbox_seq > acked_seq`) → `shape_outbox` (message-only Event Transform, **Exit**) | Returns `{items[{key, base_rev, outbox_seq, changes{}, brief_md?, retro_md?}], milestones[], events[]}`; `base_rev` is the row's `pending_base_rev` |
| E4 | ack: explode → `set_acked` (HTTP Request, Update `acked_seq = outbox_seq`) → `ack_exit` (Exit) | Stops re-sending items that already have an open PR. `pending_repo_sync` clears only when Flow 1 brings a rev above `pending_base_rev` back |
| E5 | snapshot: `reset_abandoned` (for every pending row whose key is not in `open_pr_keys` and whose Tines-side write is older than `sdlc_limits.pending_reset_hours`: Update `pending_repo_sync false`) → `list_all` → `snapshot_exit` (Exit, with every row and the `kit_state.hash_<name>` values) | Used by the nightly drift comparison and the `resources_in_sync` check (§6.5, §8.2) |

### 7.8 Page specs

All Pages use access **Only team members** (the default; never "Anyone with the link"), except `gate_decision`, which uses **Via SSO**, restricted to the approvers SSO group, where the tenant has SSO group-based page access (§4.5 rule 2). Submissions are **not anonymised**: downstream actions read the submitter email from the headers. Element types are the documented set: Short text, Long text, Email, Option, Date or time, Boolean, Number, Heading, Rich text, Divider, Button, Table, Chart. Whether each element can be marked required is K31, so the `is_valid_input` Trigger is the enforcement. Answers arrive under `<page_name>.body.<field>`; looping-container answers are grouped under the container's snake_case name.

**`kickoff` (root Page; URL identifier `story-factory-kickoff`; submission mode *Show success message*: "Provisioning started. The setup report link will be emailed to you and committed to `kit/tenant/setup-report.json`.")**

| Container / element | Type | Body key | Default · options · condition |
|---|---|---|---|
| Heading "Start your agentic story factory" | Heading | — | — |
| Intro | Rich text | — | What will be created (a private repository, Skills, Record types, Resources, and when entitled a Dashboard and an App). **"Enter the NAME of a Tines credential. Never paste a token, key or password into this page."** |
| **Organisation** · company name | Short text | `company_name` | — |
| Tines tenant host | Short text | `tines_tenant_host` | Pre-filled from the `?tines_tenant_host=` query parameter. Used only inside the tenant; never committed |
| Dev team · prod team (the ops team, where this story lives) | Short text ×2 | `dev_team_name`, `prod_team_name` | The ops team **is** the prod team (§7.1); the Page asks for no third team |
| **Plan** · plan tier | Option | `plan_tier` | `community_edition \| business \| enterprise` |
| Licensed standard teams | Number | `licensed_teams` | Teams are an add-on; fewer than 2 sends the run to the manual path (A3b) |
| Self-hosted | Boolean | `self_hosted` | false |
| Entitlements | Boolean ×7 | `ent_pages`, `ent_apps`, `ent_cases`, `ent_records`, `ent_ai_agent_action`, `ent_change_control`, `ent_tunnel` | `ent_pages` true (Pages are in every edition); the others false |
| Records licence tier | Option | `records_tier` | `starter \| essentials \| standard \| advanced \| enterprise_l1`; shown when `ent_records` is true; read by A18's quota check |
| Community note | Rich text | — | Shown when `plan_tier == community_edition`: the manual path |
| **AI model** · choice | Option | `llm_choice` | `tines_provided \| byo_anthropic \| byo_openai \| byo_bedrock \| byo_azure_openai \| local_ollama_via_tunnel \| local_vllm_via_tunnel \| local_other_openai_compatible_via_tunnel` |
| Provider name as shown in Settings → AI settings | Short text | `provider_name` | Hidden when `llm_choice == tines_provided` |
| Model to probe (display name) | Short text | `model_display_name` | Optional |
| Tunnel warning | Rich text | — | Shown when `llm_choice` starts with `local_` and (`ent_tunnel` is false or `self_hosted` is true): a local model inside the network needs a Tunnel, which is cloud-only and an add-on (§10.2) |
| **GitHub** · organisation | Short text | `github_org` | — |
| Repository name | Short text | `repo_name` | `tines-story-factory` |
| Template repository | Short text | `template_repo` | `<template-owner>/<template-repo>` (the kit's published template; it must be readable by the token) |
| GitHub credential note | Rich text | — | "Store the GitHub token in the Tines credential named `github_factory` before you submit. The kit uses that fixed name." |
| **Target use cases** (looping container, 10 iterations; 4 elements × 10 = 40 ≤ the 100 looped-element limit) | Looping container | `use_cases` | Loop formula = an array of 10, evaluated once at page load |
| · pick | Option | `pick` | Options from an array formula: the ten starter stories (§11) + `custom` + `none` (default `none`) |
| · custom title / custom description | Short text / Long text | `custom_title`, `custom_description` | Shown when `pick == custom`. Whether a condition can reference a sibling element in the same iteration is K31 |
| · owner role | Short text | `owner_role` | Defaults to the catalog owner |
| **Chat surface** | Option | `chat_surface` | `slack \| microsoft_teams \| email \| tines_pages_only`. In v1 notifications go by Email, plus Slack when chosen. Teams-specific delivery is not in the research, so Teams gets email plus a note |
| Slack credential NAME | Short text | `slack_credential_name` | Shown when `chat_surface == slack` |
| **Gate approvers** (G0 / G6 / G7) | Email ×3 | `approver_g0`, `approver_g6`, `approver_g7` | Stored only in the `sdlc_approvers` Resource; never committed |
| Consent | Boolean | `consent` | "I understand this creates a private repository in the organisation above and creates, in the ops team, the Skills `alert-policy`, `credit-budget-analyst`, `story-build-conventions`, `story-health-triage`, `backlog-planning`, `story-brief-writing` and `story-retrospective` (an existing skill of the same name is left as it is and reported), Record types, Resources (and, if entitled, a Dashboard and an App)." |
| Provision | Button | `button` | Submission value `provision` |

**`setup_report` (mid-story; per-run link `PAGE.setup_report`)**
- Heading.
- Rich text: overall status; repository link; App link (if published) or "publish the App `[BY HAND]`"; Dashboard name.
- **Table** (from `CSV_PARSE` of `step,status,detail`).
- Rich text: the `[BY HAND]` checklist from §7.2.
- Button "Open the tracker", *Redirect to URL*: the App URL `https://<your-tenant>.tines.com/apps/<url-identifier>` if it exists, otherwise the `tracker_home` root Page.

**`tracker_home` (root)**
- Heading.
- Rich text. When Records are not entitled, it shows counts from `RESOURCE.kit_tracker_view`; whether root-page formulas read Resources is K31.
- Four Buttons with submission values `view`, `add`, `gate`, `milestones`.
- Submission mode *Move to next page*. How this behaves with actions between Pages is K31.

**`tracker_view` (mid-story)**
- Heading.
- **Chart** (bar: stories per phase).
- **Table** (key · title · phase · status · open gate · owner · target date · monthly credit estimate).
- **Table** (milestones: id · title · status · due).
- Rich text: open gates and who decides each.
- Button "Back".

**`add_use_case` (mid-story)**
- `title` (Short text).
- `use_case` (Long text).
- `owner_role` (Short text).
- `target_date` (Date or time).
- `library_seed_id` (Option: catalog ids + `none`).
- `mode_hint` (Option: `none | sub-story | mode-1-preset | mode-3-agent | mode-4-server | unknown`).
- Button.

**`gate_decision` (mid-story)**
- `story_key` (Option, from the upstream List array).
- `gate` (Option: `G0 | G6 | G7 | GX | unpark`).
- `decision` (Option, filtered by gate: G0 `build | reject | park` · G6 `go_live | stay_shadow` · G7 `keep | rescope | retire` · GX `resume | park | reject` · `unpark`).
- `note` (Long text).
- Button.
- The success message names the resulting phase and says the change reaches git through the next tracker PR.

### 7.9 Build prompts (`stories/kit-factory/build-prompts.md`)

The kit story is built through Mode 2, by `tines-builder`, one section at a time, ending each step with Validate. It is then exported and committed. That build is the §15.6 maintainer release: its G1 and G2 are reviewed by hand and the build session runs with `SDLC_ENFORCE=0`, because its backlog row cannot pass G1 as the lifecycle checks it (REPO-DESIGN.md §15.6 step 1). **`story.json` is never hand-written.** Every prompt follows the scaffold's pattern: story name + action type + action name + field names + "then validate".

| Prompt | Builds |
|---|---|
| P-K1 | The story, its six Sections and the canvas Note (purpose, entry points, mode badge "none") |
| P-K2 | The `kickoff` Page |
| P-K3 | `kickoff_test` (dev only), `normalize`, `is_valid_input`, `is_community`, `already_provisioned` |
| P-K4 | The `kit_state`, teams and providers actions |
| P-K5 | The GitHub template path and the fallback |
| P-K6 | The bundle read and the config commit |
| P-K7 | The skills upsert |
| P-K8 | Record types, Resources and seeding |
| P-K9 | The Dashboard import and the App create and push |
| P-K10 | Section F |
| P-K11 | The report, the `setup_report` Page and the email |
| P-K12 | Section B, with every Records read and write as an HTTP Request action to the Records API by type and field id (§7.4); no Record actions |
| P-K13 | Sections C and E and the four tracker Pages |
| P-K14 | Section D (including D9 `improve_check` and the dev-only D10 `specialist_test`), with the three agents' system instructions and output schemas pasted from `sdlc/agents/runtime/*` and the fast model pinned on each |


---

## Appendix A — build patterns the section files use

| Pattern | Rule | Why |
|---|---|---|
| **Two-way branch** | A Trigger passes or emits nothing, so every either/or is a **pair of Triggers** (the scaffold's `lock_acquired` / `lock_busy`). The section tables name both | a branch that is not built is a silent stop |
| **Fan-out and join** | Where §7 says "explode": an Event Transform in explode mode, then the per-item actions, then an Event Transform in **implode** mode (keyed on the run guid, sized by the list) before the section continues. Every explode is preceded by a `has_<items>` / `has_no_<items>` pair, so an empty list never stalls a join. Branches that end on their own (section D's `each_dispatch`) have no join | ordering, pacing and the implode options (the guid and size it keys on) are VERIFY K33 |
| **Step results** | Section A writes `step_<name> = {status, http_status, message}` into `kit_state` after each step (`record_<name>`), and on a fatal failure through the shared `step_failed` → `record_step_failed` → `compose_report` | the report is built only from the ledger, so it survives a failure half way |
| **Ledger writes** | `kit_state` has flat keys; every write is `POST /api/v1/global_resources/{id}/replace` `{key, value[, if_value]}` | `…/replace` addresses top-level keys; `if_value` makes it a compare-and-swap |
| **Records through the API** | Sections B–E use HTTP Request actions on the Records API by type and field id from `kit_state` — **never a Record action** (§7.4). "List", "Query", "Create" and "Update" name the calls in [`sections/B-tracker-sync-in.md`](sections/B-tracker-sync-in.md) | the record types do not exist at import time; K6 |
| **Provisional writes** | Every Tines-side change to a row sets `pending_repo_sync: true`, `pending_base_rev` = the row's `rev`, and `outbox_seq` + 1; nothing in Tines ever changes `rev` | Flow 2 brings it to git; Flow 1 clears it only after a later merge (§6.5) |
| **Test paths** | The two dev-only Webhooks (`kickoff_test`, `specialist_test`) stop at a Trigger on `RESOURCE.kit_config.environment == "dev"`. A `specialist_test` run stops after the agent and the Trigger after it: the blocks' `is_test_*` Triggers end it before any Records write | tests never write to the tracker |
| **Error shapes** | Guards refuse with `{status: "refused", reason}`; failures end on the scaffold's `{status: "error", error_category, retryable, message}` (`error_category` one of `auth \| rate_limit \| upstream_5xx \| validation \| permission \| unknown`, plus `input` for A3). A story with several sections cannot have several actions named `error`, so each carries its section's name (`input_error`, `sync_failed`, `outbox_error`, `app_*_error`, `specialist_failed`) | lint `unique_agent_names` |
| **Formulas** | Only `DEFAULT()`, `STORY_RUN_GUID()`, `JSON_PARSE`, `CSV_PARSE`, `META.story.name`, `PAGE.<name>` and `RESOURCE.<name>` are named in the kit's sources. Base64 is K14; date arithmetic, list filtering and string functions follow the tenant's formula reference (confirmed alongside K14) | no formula name is invented |

## Appendix B — where the section files refine §7's names

Action names must be unique in one story (lint `unique_agent_names`, severity error). Where §7 uses one name in two sections, or names a group, the build uses these:

| §7 says | Built as | Why |
|---|---|---|
| B2 `kill_switch`, D2 `kill_switch` | `sync_kill_switch`, `dispatch_kill_switch` | two actions, one name |
| B7 `create_row` / `update_row`; C4 `create_row`; C5 `update_row` | `sync_create_row` / `sync_update_row`; `use_case_create_row`; `gate_update_row` | the same |
| C4 `log_event`, C5 `log_event` | `use_case_log_event`, `gate_log_event` | the same |
| D4, D5, D6 `log_run`; D5, D6 `notify` | `brief_log_run`, `planner_log_run`, `retro_log_run`; `planner_notify`, `retro_notify` | the same |
| C2 `route_button`, D3 `route_agent`, E2 `route_op` (each "Triggers") | `route_button_<value>`, `route_agent_<agent>` (+ `route_agent_nudge`), `route_op_<op>` | one Trigger per branch |
| A18 "Trigger `ent_records`" and A23 "Trigger `ent_records`" | `ent_records` (A18), `ent_records_dashboard` (A23) | two Triggers, one name |
| D5 `backlog_snapshot` (List) | `list_planner_rows` + `list_planner_milestones` (List) → `backlog_snapshot` (Event Transform) | the planner's prompt reads `backlog_snapshot.*` (`sdlc/agents/runtime/planner/system-instructions.md`) |
| D6 `ops_evidence` (List) | `list_ops_findings` + `list_ops_alerts` + `list_story_events` (List) → `ops_evidence` (Event Transform) | the retro_writer's prompt reads `ops_evidence.*` |
| A7 `create_kit_state` | `has_no_ledger` → `create_kit_state` → `store_self_id`, or `has_ledger` → `resume_ledger`, then `ledger` | the `self_id` key §7.2 describes, and the resume path |
| A16 `write_config`, A29 `write_report` | `read_config_sha` → `write_config`; `read_report_sha` → `write_report` | a re-run updates an existing file, which the Contents API does with the file's `sha` (K13) |
| D7 `nudge` (on the Email) | `nudge` (the notice) → the shared `send_notice_email` / `send_notice_slack` | one delivery pair for every notice |
| A12 `fallback_repo`, A17 `push_skills`, A18 `create_record_types`, A19 `create_resources` | step labels over the actions listed in the section A tables; no single action carries them | each step is several actions (a fan-out, its calls and its join) |

## Appendix C — action index

Every action of the story, by section — about 340 in all. The count is far above REPO-DESIGN.md §14's "roughly 80", which counts §7's numbered rows; the index spells out every Trigger pair, join and ledger write. It stays **one story** — flows are counted by entry points (K30) — and the size is the reason the ops trio monitors it like any other story (§14 con 12).

| Section | Type | Actions |
|---|---|---|
| **A** | Page | `kickoff`, `setup_report` |
| A | Webhook | `kickoff_test` |
| A | Trigger | `is_dev_kickoff_test`, `is_valid_input`, `is_invalid_input`, `is_community`, `is_standard_plan`, `already_provisioned`, `is_new_run`, `has_ops_team`, `is_missing_ops_team`, `has_no_ledger`, `has_ledger`, `is_template_readable`, `is_template_unreadable`, `is_generated`, `repo_exists`, `is_resumed_repo`, `is_name_taken`, `is_generate_refused`, `has_template_files`, `has_no_template_files`, `has_skills`, `has_no_skills`, `is_new_skill`, `is_kit_skill`, `is_customer_skill`, `ent_records`, `has_no_records`, `has_resources_to_create`, `has_no_resources_to_create`, `is_seed_claimed`, `is_already_seeded`, `ent_records_dashboard`, `has_no_records_for_dashboard`, `has_real_dashboard`, `is_dashboard_skeleton`, `ent_apps`, `has_no_apps` |
| A | Event Transform | `normalize`, `input_error`, `community_path`, `already_provisioned_notice`, `resolve_teams`, `missing_team_notice`, `ledger`, `ledger_error`, `check_provider`, `copy_plan`, `each_template_file` (explode), `copied_files` (implode), `fallback_result`, `parse_bundle`, `each_skill` (explode), `skill_conflict`, `skill_outcome`, `skills_done` (implode), `records_quota`, `each_record_type` (explode), `record_types_done` (implode), `resource_plan`, `each_resource` (explode), `resources_done` (implode), `seed_rows`, `each_seed_row` (explode), `backlog_seeded` (implode), `each_milestone` (explode), `milestones_seeded` (implode), `compose_report`, `step_failed` |
| A | HTTP Request | `lookup_teams`, `create_kit_state`, `store_self_id`, `resume_ledger`, `record_teams`, `list_ai_providers`, `record_providers`, `probe_template`, `generate_repo`, `create_org_repo`, `read_template_bundle`, `read_template_file`, `put_repo_file`, `wait_for_repo`, `store_repo`, `record_repo`, `read_bundle`, `record_bundle`, `read_config_sha`, `write_config`, `record_config`, `get_skill`, `create_skill`, `update_skill`, `record_skills`, `create_record_type`, `store_record_type_id`, `store_record_type_fields`, `record_record_types`, `create_resource`, `store_resource_id`, `record_resources`, `claim_seed`, `seed_backlog`, `seed_milestones`, `record_seed`, `import_dashboard`, `store_dashboard_id`, `record_dashboard`, `create_app`, `store_app_id`, `push_app_files`, `record_app`, `lookup_kit_story`, `read_report_sha`, `write_report`, `record_report`, `finish_kit_state`, `record_step_failed` |
| A | Email | `email_report` |
| **F** | Trigger | `ent_ai_agent_action`, `has_no_ai_agent_action`, `llm_probe_ok`, `llm_probe_failed`, `tool_probe_ok`, `tool_probe_failed` |
| F | AI Agent action | `llm_probe`, `llm_tool_probe` |
| F | Group (Custom tool) | `probe_constant` (containing the Event Transform `probe_constant_value`) |
| F | Event Transform | `probe_not_entitled`, `probe_verdict` |
| F | HTTP Request | `record_probe` |
| **B** | Webhook | `tracker_sync_in` |
| B | Trigger | `sync_kill_switch`, `is_valid_payload`, `is_invalid_payload`, `has_sync_lock`, `is_locked`, `has_records_sync`, `has_mirror_sync`, `has_upserts`, `has_no_upserts`, `is_create_row`, `is_update_row`, `is_conflict_row`, `has_transition`, `has_milestone_upserts`, `has_no_milestone_upserts`, `is_create_milestone`, `is_update_milestone` |
| B | Event Transform | `normalize_payload`, `sync_rejected`, `sync_busy`, `plan_upserts`, `each_upsert` (explode), `upserts_done` (implode), `plan_milestone_upserts`, `each_milestone_upsert` (explode), `milestones_done` (implode), `sync_failed` |
| B | HTTP Request | `log_sync_rejected`, `acquire_sync_lock`, `list_backlog`, `sync_create_row`, `sync_update_row`, `log_sync_conflict`, `log_transition`, `sync_list_milestones`, `sync_create_milestone`, `sync_update_milestone`, `update_tracker_view`, `release_sync_lock` |
| **C** | Page | `tracker_home`, `tracker_view`, `add_use_case`, `gate_decision` |
| C | Webhook (App endpoint) | `app_add_use_case`, `app_gate_decision`, `app_costs` |
| C | Trigger | `route_button_view`, `route_button_add`, `route_button_gate`, `route_button_milestones`, `has_records_view`, `has_mirror_view`, `is_valid_use_case`, `is_invalid_use_case`, `is_app_use_case`, `is_approver`, `is_not_approver`, `is_gate_open`, `is_gate_closed`, `has_valid_transition`, `has_no_valid_transition`, `is_app_gate` |
| C | Event Transform | `to_table`, `normalize_use_case`, `use_case_refused`, `assign_use_case_key`, `open_gate_options`, `gate_identity`, `apply_decision`, `gate_refused`, `costs_window`; exits `app_add_use_case_result`, `app_add_use_case_error`, `app_gate_decision_result`, `app_gate_decision_error`, `app_costs_result`, `app_costs_error` |
| C | HTTP Request | `list_rows`, `list_view_milestones`, `list_keys_for_use_case`, `use_case_create_row`, `use_case_log_event`, `list_open_gates`, `app_gate_rows`, `list_gate_history`, `gate_update_row`, `gate_log_event`, `get_app_costs` |
| **D** | Webhook | `specialist_test` |
| D | Event Transform (schedule) | `dispatch_sweep` (cron `*/15 * * * *`, watchdog 1,800 s) |
| D | Trigger | `sweep_enabled`, `has_sweep_items`, `has_no_sweep_items`, `dispatch_kill_switch`, `route_agent_nudge`, `is_agent_dispatch`, `under_cap`, `over_cap`, `is_cap_news`, `route_agent_brief_writer`, `route_agent_planner`, `route_agent_retro_writer`, `brief_ok`, `brief_failed`, `is_live_brief`, `is_test_brief`, `is_planner_due`, `planner_claimed`, `planner_claim_lost`, `planner_ok`, `planner_failed`, `is_live_plan`, `is_test_plan`, `has_proposals`, `has_no_proposals`, `has_ops_evidence_types`, `has_no_ops_evidence_types`, `retro_ok`, `retro_failed`, `is_live_retro`, `is_test_retro`, `has_ops_types_for_improve`, `has_improve_candidates`, `has_no_improve_candidates`, `is_dev_specialist_test`, `is_brief_writer_test`, `is_planner_test`, `is_retro_writer_test`, `is_slack_surface` |
| D | AI Agent action | `brief_writer`, `planner`, `retro_writer` |
| D | Event Transform | `dispatch_in`, `each_dispatch` (explode), `sweep_plan`, `each_sweep_item` (explode), `brief_context`, `filter_seed_ids`, `render_brief`, `notify_g0`, `backlog_snapshot`, `plan_by_key`, `each_proposal_row` (explode), `proposals_saved` (implode), `planner_notify`, `ops_evidence`, `render_retro`, `retro_notify`, `nudge`, `specialist_failed`, `escalation_notify`, `improve_check`, `each_improve` (explode) |
| D | HTTP Request | `list_dispatch_rows`, `count_runs_today`, `log_cap_reached`, `mark_running`, `save_brief`, `brief_log_run`, `claim_planner`, `list_planner_rows`, `list_planner_milestones`, `save_proposals`, `planner_log_run`, `retro_mark_running`, `list_ops_findings`, `list_ops_alerts`, `list_story_events`, `save_retro`, `retro_log_run`, `mark_failed`, `log_escalation`, `list_recent_findings`, `get_story_credits`, `write_improve`, `log_improve`, `send_notice_slack` |
| D | Email | `send_notice_email` |
| **E** | Webhook (response-enabled) | `tracker_outbox` |
| E | Trigger | `route_op_pull`, `route_op_ack`, `route_op_snapshot`, `route_op_unknown`, `has_acks`, `has_no_acks`, `has_resets`, `has_no_resets` |
| E | Event Transform | `ack_plan`, `each_ack` (explode), `acks_done` (implode), `reset_plan`, `each_reset` (explode), `resets_done` (implode); exits `shape_outbox`, `ack_exit`, `snapshot_exit`, `outbox_error` |
| E | HTTP Request | `list_pending`, `list_pending_milestones`, `list_outbox_events`, `list_for_ack`, `set_acked`, `list_snapshot_rows`, `reset_abandoned`, `list_all`, `list_all_milestones` |
| — | Note | one canvas Note (P-K1): purpose, entry points, mode badge "none" |

## Appendix D — what this design depends on that is not confirmed

Everything below is VERIFY (REPO-DESIGN.md §16; `docs/VERIFY.md`) and nothing in this folder states it as fact: **K5** and **K35** (the Records API v2 bodies), **K6** (not relied on: B–E use the API), **K7** (AI Agent on Community), **K8** (import keeps Page identifiers and Webhook paths and secrets — the template is not published until it is confirmed), **K9** (credentials by computed name), **K10** (a missing Resource reads as null), **K11–K13**, **K44** (GitHub token scopes, generated-repository readiness, Contents PUT, the raw media type), **K14** (the base64 formula), **K15** (response-enabled Webhook sizing), **K16** (record-type create body and response), **K17** (Dashboard import by type name), **K18** (Apps: file pushes, publishing through Mode 2, endpoint identity), **K22–K26** (provider details and per-run model choice), **K27** (skill attachments in exports), **K29** (ARTIFACT size), **K30** (flow counting), **K31** (Page behaviour), **K32** (CSV for Tables), **K33** (explode ordering and loops), **K36** (the Tunnel), **K37** (the Webhook URL `eval-run` builds), **K38** (what `tines_api_readonly` sees), **K39** (API-created Records are live), **K40** (Resource locking), **K41** (what a team-scoped Editor key may call); and the scaffold's **#1**, **#2**, **#5**, **#8**, **#11**, **#13**, **#14**.
