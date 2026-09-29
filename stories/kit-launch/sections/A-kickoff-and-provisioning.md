# Section A — kickoff and provisioning (deterministic)

_Spec: REPO-DESIGN.md §7.1 (shape, import), §7.2 (this section), §8 (Record types and Resources), §13 rows 1, 2, 12 and 17. Part of `[KIT] 00 · Launch Storyworks` (`../story.json`, a SKELETON until the §15.6 release). Built through Mode 2 by build prompts **P-K2 to P-K9 and P-K11** (`../build-prompts.md`); section F (the provider probe) sits between A24 and A28 on the canvas and has its own file, [`F-llm-probe.md`](F-llm-probe.md). This file is the specification the builder follows and the reviewer checks the export against — never a substitute for the export._

**What it does.** One submission of the `kickoff` Page provisions everything Storyworks needs, in order: it checks the answers, resolves the teams, opens a run ledger (`kit_state`), checks the model provider, creates the customer's private repository from the template (or copies it file by file), commits the tenant config, creates the Tines Agent Skills, the three Record types and the kit Resources, seeds the tracker, imports the Dashboard, creates the App, probes the model (section F), writes the setup report to the repository and the `setup_report` Page, and emails the submitter the link. **No model runs in this section** (the probe is section F). Nothing is overwritten that the customer already has.

It is **resumable**: a partial run leaves `kit_state.status: running`; submitting the Page again resumes with the same ledger, skips every step whose result is already recorded, and never seeds Records twice (A20). A run that reached `status: complete` stops at A4.

## Conventions for every action in this section

| Rule | Detail |
|---|---|
| **HTTP hardening** (`AGENTS.md` §5) | Every HTTP Request: `retry_on_status [429, 500-599]`, retries **6**, emit failure event **Always**, `log_error_if` for 200-with-error bodies, expected non-2xx excluded from `log_error_on_status` (named per action below), and a failure path. Export key names for these options are scaffold VERIFY #8 |
| **Tines API calls** | `https://<<normalize.tines_tenant_host>>/api/v1/…` with the header `Authorization: Bearer <<CREDENTIAL.tines_api_kit>>`. A3 rejects any host that does not match `^[a-z0-9-]+\.tines\.com$`, so no Page answer can send the key elsewhere; `allowed_hosts` on the credential is the second guard (the report's first pre-flight item) |
| **GitHub calls** | `https://api.github.com/…` with `Authorization: Bearer <<CREDENTIAL.github_factory>>` — the **fixed** credential name. The Page names no credential that this section uses. Raw reads send GitHub's raw media type in `Accept` (the exact header string, and behaviour above 1 MB, are **K44**) |
| **The ledger** | `kit_state` has **flat keys**, because `POST /api/v1/global_resources/{id}/replace` addresses top-level keys. Every ledger write below is `POST https://<host>/api/v1/global_resources/<<ledger.ledger_id>>/replace` with `{key, value}` (and `if_value` for a compare-and-swap) |
| **Step results** | Each step writes `step_<name> = {status, http_status, message}` into the ledger (`record_<name>`, a `…/replace`), and `compose_report` (A28) builds the report from those keys. `status` is one of `ok`, `failed`, `skipped`, `not_needed`, `exists`, `partial` |
| **Failure path** | A step whose failure makes the following steps meaningless goes to **`step_failed`** (Event Transform: `{key: "step_<name>", value: {status: "failed", http_status, message}}`, where `message` is a sentence a person can act on and never a raw body) → **`record_step_failed`** (`…/replace`) → **`compose_report`** (A28). The report, the Page and the email still happen: a failure never stops the section silently. Non-fatal failures (one skill, the Dashboard, the App) are recorded in their own `record_<name>` and the section continues |
| **Two-way branches** | A Trigger passes or emits nothing, so every either/or is a **pair of Triggers** (the scaffold's pattern, e.g. `lock_acquired` / `lock_busy`). The table names both |
| **Fan-out** | Where §7.2 says "explode", an Event Transform in explode mode fans out, and an Event Transform in **implode** mode (keyed on the run guid, sized by the list length) joins the branches before the section continues. Every explode is preceded by a `has_<items>` / `has_no_<items>` Trigger pair so an empty list never stalls an implode. The ordering of explode + HTTP Request, pacing, and the implode mode's options (the guid and size it keys on) are **K33** — confirmed with its scratch run before P-K5 |
| **Formulas** | Only `DEFAULT()`, `STORY_RUN_GUID()`, `JSON_PARSE`, `CSV_PARSE`, `META.story.name`, `PAGE.<name>` and `RESOURCE.<name>` are named in the kit's sources. The base64-encoding formula is **K14**; date arithmetic, list filtering and string functions use whatever the tenant's formula reference documents (confirm alongside K14) — no other formula name is assumed here |
| **Names** | lowercase snake_case, unique in the whole story (lint `unique_agent_names`); Triggers `is_<condition>` / `has_<thing>`, except where REPO-DESIGN.md already named the action |
| **No secrets out** | The report, the Page and the email carry no token, no key, no webhook URL and no email address; the config commit leaves out the tenant host and every email (§13 row 12) |

## Entry points

| Entry | Action | Type | Notes |
|---|---|---|---|
| The kickoff | `kickoff` | **Page, root** (URL identifier `storyworks-kickoff`) | The specification is [`../pages/kickoff.md`](../pages/kickoff.md). Access **Only team members**; submissions **not anonymised** (`normalize` reads the submitter's email from the Page headers). Submit it on the **LIVE** story (§7.1, K39) |
| The kit's own acceptance test | `kickoff_test` | **Webhook, dev only** | Takes a kickoff submission as JSON (`../tests/sample-event.json`) so `eval-run` and the build skill's test step can drive section A. `is_dev_kickoff_test` stops it unless `RESOURCE.kit_config.environment == "dev"`, so it does nothing in the ops (prod) team |

## The actions

`#` keeps REPO-DESIGN.md's numbering; letters are the actions the design implies between two numbered ones.

| # | Action | Type | Does · key options and formulas | Next · on failure |
|---|---|---|---|---|
| A1 | `kickoff` | Page (root) | [`../pages/kickoff.md`](../pages/kickoff.md). Answers arrive under `kickoff.body.<field>`; the looping container under `kickoff.body.use_cases` | → A2 |
| A1b | `kickoff_test` | Webhook (dev only) | Same body keys as the Page, plus the test-only `submitter_email` (a `*.example.invalid` address) | → A1c |
| A1c | `is_dev_kickoff_test` | Trigger | `RESOURCE.kit_config.environment` equals `dev` | pass → A2 · no pass → the run ends (prod) |
| A2 | `normalize` | Event Transform, message-only | Reads every answer as `DEFAULT(kickoff.body.<f>, DEFAULT(kickoff_test.body.<f>, <default>))` and trims it. **On the test path only**, an answer of the placeholder form `<…>` is replaced by the dev team's own `kit_config` value for the same key (`tenant_host`, `teams.dev.name`, `teams.prod.name`, `github.org`, `github.template_repo`), so the committed sample stays placeholder-only. Emits the shape in "normalize's output" below: `use_cases[]` built from the looping container with `none` dropped; starter picks copy `key`, `title`, `library_seed_id`, `mode`, `tier`, `owner` and `target_offset_days` from `RESOURCE.kit_catalog.starter_stories`; `custom` rows get `key` = the title lowercased and hyphenated (≤ 48 characters; `-2`, `-3`… on a collision with a catalog key or an earlier row); `target_date` = `provisioned_at` + the catalog offset in UTC (custom rows: empty — the planner proposes one); `config` = the future `kit/tenant/config.yaml`, **without** the tenant host or any email; `run_guid` = `STORY_RUN_GUID()`; `submitter_email` from the Page headers (the header key is read from the first dev run, with K31's scratch Pages) or `kickoff_test.body.submitter_email` | → A3 / A3a |
| A3 | `is_valid_input` | Trigger (all rules must hold) | Required fields present (`company_name`, `tines_tenant_host`, `dev_team_name`, `prod_team_name`, `plan_tier`, `licensed_teams`, `llm_choice`, `github_org`, `repo_name`, `template_repo`, `chat_surface`, `approver_g0`) · `tines_tenant_host` matches `^[a-z0-9-]+\.tines\.com$` · `github_org` matches `^[A-Za-z0-9][A-Za-z0-9-]{0,38}$` · `repo_name` matches `^[A-Za-z0-9._-]{1,100}$` · `template_repo` is `<owner>/<repo>` with both parts matching those two patterns · `slack_credential_name`, when given, matches `^[a-z0-9_]{1,64}$` · `consent` is true · **no field matches a token pattern**: `normalize.all_answers` (every answer joined) does not match `(ghp_|github_pat_|gho_|ghs_|xox[bp]-|sk-|AKIA|Bearer )` | pass → A3e / A3b |
| A3a | `is_invalid_input` | Trigger | The complement of A3: any one of its rules fails. Built as a Trigger whose rules are the negations with "any rule" matching; if the tenant's Trigger offers no "any" mode, `normalize` also emits `input_problems[]` and both Triggers test it empty / non-empty (the negated-regex rule type and the match mode are confirmed at build) | → A3c |
| A3c | `input_error` | Event Transform, message-only | `{status: "error", error_category: "input", retryable: false, message}` — `message` names each failed check, **never echoes the offending value** (it may be a token) | → A32 `email_report` → end |
| A3b | `is_community` | Trigger | `normalize.plan_tier == "community_edition"`, **or** `normalize.licensed_teams < 2` (the kit needs a dev and a prod team, §1.4) | → A3d |
| A3d | `community_path` | Event Transform | `{status: "not_supported", message: "…follow kit/docs/community-path.md in your repository…"}`. The template repository's path is named, never a URL with a host | → A32 → end |
| A3e | `is_standard_plan` | Trigger | `plan_tier` is `business` or `enterprise` and `licensed_teams ≥ 2` | → A4 / A4b |
| A4 | `already_provisioned` | Trigger | `RESOURCE.kit_state.status == "complete"`. Reading a Resource that does not exist yet must yield null, not an error — **K10**; if it errors, create an empty `kit_state` Resource (`{}`) in the ops team `[BY HAND]` before the first run | → A4a |
| A4a | `already_provisioned_notice` | Event Transform | `{status: "complete", message}` naming the repository in `RESOURCE.kit_state.repo` and `kit/tenant/setup-report.json` | → A32 → end |
| A4b | `is_new_run` | Trigger | `RESOURCE.kit_state.status` is not `complete` (null or `running`) | → A5 |
| A5 | `lookup_teams` | HTTP Request | `GET /api/v1/teams?scope=standard&per_page=100`. Whether a team-scoped Editor key lists the other teams' names is **K41** | → A6 · failure → `step_failed` (`step_teams`) |
| A6 | `resolve_teams` | Event Transform | Matches `dev_team_name` and `prod_team_name` **exactly** against the list; emits `{prod: {id, name}, dev: {id, name}, dev_found: bool}`. The prod team **is** the ops team, and the story must be running in it: `prod.id` is also compared with the team the story runs in (the story-level formula for the current team id is confirmed at build; if none exists, the name match stands) | → A6a / A6b |
| A6a | `has_ops_team` | Trigger | `resolve_teams.prod.id` is not null. A missing **dev** team is reported (`step_teams: partial`) and the run continues | → A7 / A7c |
| A6b | `is_missing_ops_team` | Trigger | `resolve_teams.prod.id` is null | → A6c |
| A6c | `missing_team_notice` | Event Transform | `{status: "error", error_category: "validation", retryable: true, message: "import [KIT] 00 into the prod team (the ops team) named on the Page, then submit again"}` | → A32 → end |
| A7 | `has_no_ledger` | Trigger | `RESOURCE.kit_state` is null (K10) | → A7a |
| A7a | `create_kit_state` | HTTP Request | `POST /api/v1/global_resources` `{name: "kit_state", team_id: <<resolve_teams.prod.id>>, read_access: "TEAM", value: {status: "running", run_guid: <<normalize.run_guid>>, repo: "", records_seeded: false, planner_last_run: ""}}` | → A7b · failure → A7f |
| A7b | `store_self_id` | HTTP Request | `…/global_resources/<<create_kit_state.body.id>>/replace` `{key: "self_id", value: <<create_kit_state.body.id>>}`, so a later run finds the ledger's own id inside it (the id key of the create response is confirmed at build) | → A7e |
| A7c | `has_ledger` | Trigger | `RESOURCE.kit_state.self_id` is set (a partial earlier run) | → A7d |
| A7d | `resume_ledger` | HTTP Request | `…/global_resources/<<RESOURCE.kit_state.self_id>>/replace` `{key: "run_guid", value: <<normalize.run_guid>>}`; the ledger keeps `status: running` | → A7e |
| A7e | `ledger` | Event Transform | `{ledger_id: DEFAULT(create_kit_state.body.id, RESOURCE.kit_state.self_id), resumed: <A7d ran>}` — every later ledger write addresses `<<ledger.ledger_id>>` | → `record_teams` (`step_teams`) → A8 |
| A7f | `ledger_error` | Event Transform | `{status: "error", error_category: <from the status>, retryable: true, message: "could not create the kit_state ledger; nothing was provisioned — check tines_api_kit and its allowed_hosts"}`. **No ledger means no safe re-run**, so the run stops here | → A32 → end |
| A8 | `list_ai_providers` | HTTP Request | `GET /api/v1/ai_providers` — the only provider call the API offers; configuring a provider is `[BY HAND]` (Settings → AI settings) | → A9 · failure → A9 with `provider_status: unknown` |
| A9 | `check_provider` | Event Transform | The mapping table under "check_provider" below. Picks the `api_model_id` whose display name equals `model_display_name` when one is given. Emits `{provider_status: ok \| not_found \| disabled \| mismatch \| unknown, provider_type, provisioning_type, api_model_id}` | → `record_providers` (`step_providers`) → A10 |
| A10 | `probe_template` | HTTP Request (GitHub) | Proves the token can read the template: `GET /repos/{template_owner}/{template_repo}/contents/README.md`, raw media type (K44). 401, 403 and 404 are excluded from `log_error_on_status` and branched on | 200 → `is_template_readable` → A11 · 401/403/404 → `is_template_unreadable` → `step_failed` (`step_github`: "the token cannot read the template") → **skip to section F**, then A28 |
| A11 | `generate_repo` | HTTP Request (GitHub) | `POST /repos/{template_owner}/{template_repo}/generate` `{owner: <<normalize.github.org>>, name: <<normalize.github.repo>>, description: "Tines Storyworks (provisioned by [KIT] 00)", private: true, include_all_branches: false}` → 201. The template must be marked as a template (`is_template: true`, set once by its owner and only after the §15.6 release check passes). 403, 404 and 422 are excluded and branched on | 201 → `is_generated` → A13 · 422 → `repo_exists` → `is_resumed_repo` (`RESOURCE.kit_state.repo == "<org>/<repo>"`) → A13, or `is_name_taken` → `step_failed` (`step_repo`: "a repository of that name already exists") · 403/404 → `is_generate_refused` → A12 |
| A12 | `fallback_repo` (a group of actions) | see "The Contents-API fallback" below | **Contents-API fallback**: `create_org_repo` → `read_template_bundle` → `copy_plan` → `each_template_file` (explode) → `read_template_file` → `put_repo_file` → `copied_files` (implode) → `fallback_result`. Slow — one commit per file — and the report says so and recommends the template path | → A13 · `create_org_repo` failure → `step_failed` (`step_repo`) |
| A13 | `wait_for_repo` | HTTP Request (GitHub) | `GET /repos/{org}/{repo}/contents/README.md`, **`retry_on_status [404, 429, 500-599]`, retries 6** — a generated repository is not readable at once (**K12**) | → A14 · failure → `step_failed` (`step_repo`: "the repository did not become readable") |
| A14 | `store_repo` | HTTP Request | Ledger `…/replace` `{key: "repo", value: "<<normalize.github.org>>/<<normalize.github.repo>>"}` | → `record_repo` (`step_repo`) → A15 |
| A15 | `read_bundle` → `parse_bundle` | HTTP Request (GitHub) → Event Transform | `GET /repos/{org}/{repo}/contents/kit/bundle/kit-bundle.json` (raw) — **the new repository's own** bundle, so the tenant and the repository stay consistent → `parse_bundle`: `JSON_PARSE(read_bundle.body)` → `{skills[], record_types[], resources[], dashboard, dashboard_skeleton, app_files[], file_manifest[], state_machine, catalog}` (`kit/bundle/README.md`) | → `record_bundle` (`step_bundle`) → A16 · failure → `step_failed` (`step_bundle`: sections B–E cannot be provisioned without it) |
| A16 | `read_config_sha` → `write_config` | HTTP Request ×2 (GitHub) | **The tenant-specific config commit**, on `main` of the brand-new repository (branch protection comes later, `[BY HAND]`). `read_config_sha`: `GET /repos/{org}/{repo}/contents/kit/tenant/config.yaml` (404 excluded: a first run has no file). `write_config`: `PUT /repos/{org}/{repo}/contents/kit/tenant/config.yaml` `{message: "kit: tenant config (<<normalize.run_guid>>)", content: <base64 of the JSON config>}` — on a re-run with an existing file, the body also carries the file's current blob `sha` from `read_config_sha` (GitHub's rule for updating a file; confirm with **K13**). The content is **JSON**, which a YAML 1.2 parser reads, so no YAML serialiser is needed in formulas. The config is `normalize.config` with `teams.dev.id` and `teams.prod.id` from `resolve_teams`; the base64 formula name is **K14** | → `record_config` (`step_config`) → A17 · failure → `record_config` (`failed`) → A17 (the config can be committed by hand from the report) |
| A17 | `push_skills` | explode → 3 actions | See "Skills (A17)". **Creates** every Tines Agent Skill in the bundle in the ops team and **never overwrites a customer's skill** | → A18 |
| A18 | `create_record_types` | Trigger `ent_records` → explode | See "Record types (A18)" | → A19 |
| A19 | `create_resources` | explode | See "Resources (A19)" | → A20 |
| A20 | `claim_seed` | HTTP Request | Compare-and-swap so only one run seeds Records (creation is not idempotent): ledger `…/replace` `{key: "records_seeded", value: <<normalize.run_guid>>, if_value: false}`. **422 is excluded from errors** and means already seeded | 200 → `is_seed_claimed` → A21 · 422 → `is_already_seeded` → `record_seed` (`exists`) → A23 · no Records → `record_seed` (`not_needed`) → A23 |
| A21 | `seed_backlog` | explode → HTTP Request | See "Seeding (A21–A22)" | → A22 |
| A22 | `seed_milestones` | explode → HTTP Request | See "Seeding (A21–A22)" | → `record_seed` → A23 |
| A23 | `import_dashboard` | Trigger `ent_records_dashboard` (complement `has_no_records_for_dashboard`) → Trigger `has_real_dashboard` (complement `is_dashboard_skeleton`) → HTTP Request | `POST /api/v1/dashboards/import` `{team_id: <<resolve_teams.prod.id>>, data: <<parse_bundle.dashboard>>, mode: "new", new_name: "Storyworks"}`. Record charts refer to types by `record_type_name`, resolved against the three types A18 just created (**K17**). **While the bundle's dashboard is the SKELETON** (`parse_bundle.dashboard_skeleton` true) the import is skipped and reported `skipped: the dashboard ships with the §15.6 release`. Then `store_dashboard_id` (ledger `{key: "dashboard_id"}`) | → `record_dashboard` (`step_dashboard`) → A24 · failure → `record_dashboard` (`failed`; build by hand, §9.4) → A24 |
| A24 | `create_app` | Trigger `ent_apps` (complement `has_no_apps`) → HTTP Request ×3 | `POST /api/v1/apps` `{team_id, name: "Storyworks", description}` → `store_app_id` (ledger `{key: "app_id"}`) → `push_app_files`: `PUT /api/v1/apps/<<create_app.body.id>>/files` `{files: <<parse_bundle.app_files>>}` — it **replaces every draft file**, and `App.tsx` must be present. The file object's keys and nested paths are **K18**. **Publishing is `[BY HAND]`** in the UI, or through Mode 2 (the Tines MCP server gained App tools on 2026-07-31, which the MCP docs page does not list yet: K18). The three App endpoints are wired `[BY HAND]` (Interfaces → App endpoints) | → `record_app` (`step_app`) → section F · no Apps → `record_app` (`not_needed`) → F · failure → `record_app` (`failed`) → F |
| F1–F3 (A25–A27 on the canvas) | provider probe | see [`F-llm-probe.md`](F-llm-probe.md) | `ent_ai_agent_action` → `llm_probe` → `llm_tool_probe` → `probe_verdict` → `record_probe` (`step_probe`) | → A28 |
| A28 | `lookup_kit_story` → `compose_report` | HTTP Request → Event Transform | `lookup_kit_story`: `GET /api/v1/stories` (the scaffold's list call) for the ops team; the entry whose name equals `META.story.name` gives `kit_story_id`. `compose_report`: builds the report (shape below) from the `step_*` keys in `RESOURCE.kit_state`, `probe_verdict`, and the created ids; a step with no key is `skipped` | → A29 |
| A29 | `read_report_sha` → `write_report` | HTTP Request ×2 (GitHub) | `PUT /repos/{org}/{repo}/contents/kit/tenant/setup-report.json` `{message: "kit: setup report (<run guid>)", content: <base64 of compose_report.report>}` — with the existing file's `sha` on a re-run, as A16 (K13). Its push to `main` runs `kit.yml`, whose apply-config PR — **the setup-report PR** — commits `kit_story_id` into `stories/_manifest.yaml` (`kit-launch.prod.story_id`) and `policies/never-touch.yml` (`story_ids`) | → `record_report` (`step_report`) → A30 · failure → `record_report` (`failed`: shown on the Page, where the report is copied from) → A30 |
| A30 | `finish_kit_state` | HTTP Request | Ledger `…/replace` `{key: "status", value: "complete", if_value: "running"}` (422 excluded: another run finished first). Only when `compose_report.status` is `ok` or `partial`; a `failed` run stays `running`, so submitting again resumes | → A31 |
| A31 | `setup_report` | Page (mid-story) | [`../pages/setup-report.md`](../pages/setup-report.md); per-run URL `PAGE.setup_report` | → A32 |
| A32 | `email_report` | Email | To the submitter (`normalize.submitter_email`). Subject and body are `DEFAULT()` chains over the notices that can reach it (`compose_report`, `input_error`, `community_path`, `already_provisioned_notice`, `missing_team_notice`, `ledger_error`), so exactly one is present in a run. The report path adds the `PAGE.setup_report` link. **No secret, token, webhook URL or approver email appears in it** | end |
| — | `step_failed` → `record_step_failed` | Event Transform → HTTP Request | The shared failure pair (see "Conventions") | → A28 |

## normalize's output (A2)

```json
{
  "run_guid": "<STORY_RUN_GUID()>",
  "provisioned_at": "2026-10-01T09:00:00Z",
  "is_test": false,
  "submitter_email": "<from the Page headers; never committed>",
  "company_name": "…",
  "tines_tenant_host": "<your-tenant>.tines.com",
  "teams": { "dev": { "name": "…" }, "prod": { "name": "…" } },
  "plan": { "tier": "business", "licensed_teams": 2, "self_hosted": false },
  "entitlements": { "pages": true, "apps": false, "cases": false, "records": true, "ai_agent_action": true, "change_control": true, "tunnel": false },
  "records_tier": "essentials",
  "llm": { "choice": "tines_provided", "provider_name": "", "model_display_name": "" },
  "github": { "org": "<org>", "repo": "tines-storyworks", "template_repo": "<template-owner>/<template-repo>", "template_owner": "…", "template_name": "…" },
  "chat_surface": "email",
  "slack_credential_name": "",
  "approvers": { "G0": ["…"], "G6": ["…"], "G7": ["…"] },
  "use_cases": [
    { "key": "example-enrich-ip", "title": "[SEC] 01 · Enrich IP (sub)", "use_case": "…", "library_seed_id": 87626,
      "mode": "sub-story", "tier": "production", "owner": "security-automation", "target_date": "2026-10-08T09:00:00Z", "source": "kickoff_page" }
  ],
  "config": { "…": "exactly the keys of kit/tenant/config.example.yaml; no tenant host, no email" },
  "all_answers": "every answer joined, for A3's token check only",
  "input_problems": []
}
```

- `use_cases[].owner` for a custom row is the row's `owner_role`, or `platform` when empty; an `owner_role` containing `@` is refused by A3 (owners are roles).
- `use_cases[].use_case` is **untrusted text** (§13 row 13); it is stored, never interpreted.
- `approvers` never reaches git: it goes only into the `storyline_approvers` Resource (A19) and `ops_responders` when that is created.
- `config` carries `schema_version: 1`, `kit_run`, `provisioned_at`, `company_name`, `teams` (ids filled from A6 at A16), `plan`, `entitlements`, `records_tier`, `llm`, `chat_surface`, `slack_credential_name`, `credentials` (`tines_api: tines_api_kit`, `github: github_factory`, `tines_readonly: tines_api_readonly`), `github`, `ops_record_types` (`0`, filled by PR after day 1).

## check_provider (A9)

| `llm_choice` | Matches a provider with | `provider_type` |
|---|---|---|
| `tines_provided` | `provisioning_type: tines_provisioned` | — |
| `byo_anthropic` | `provisioning_type: customer_provisioned` | `ANTHROPIC` |
| `byo_openai` | `customer_provisioned` | `OPEN_AI` |
| `byo_bedrock` | `customer_provisioned` | `AWS_BEDROCK` |
| `byo_azure_openai` | `customer_provisioned` | presumed `OPEN_AI` (**K24**: Azure's reported type) |
| `local_ollama_via_tunnel` · `local_vllm_via_tunnel` · `local_other_openai_compatible_via_tunnel` | `customer_provisioned` | presumed `OPEN_AI` (**K23**) |

For a custom or local choice, the provider must also carry the name given in `provider_name`. `provider_status`: `ok` (found and enabled) · `not_found` · `disabled` · `mismatch` (a provider of that name with another type) · `unknown` (A8 failed). Anything but `ok` adds the `[BY HAND]` item "configure or confirm the provider in Settings → AI settings".

## The Contents-API fallback (A12)

| Action | Type | Does |
|---|---|---|
| `create_org_repo` | HTTP Request | `POST /orgs/{org}/repos` `{name, private: true, description}`. Creating organisation repositories without an org policy, and a token reaching a repository created after it, are **K11** |
| `read_template_bundle` | HTTP Request | `GET /repos/{template_owner}/{template_repo}/contents/kit/bundle/kit-bundle.json` (raw, K44) |
| `copy_plan` | Event Transform | `JSON_PARSE` the template bundle; the file list = `file_manifest[]` minus `over_1mb` entries (listed as `[BY HAND]` copies) and minus the bundle's own `self` entry (copied last, so the new repository's bundle is complete when A15 reads it). Files marked `workflow` need the token's Workflows permission (K11); they are copied and a 403 on one of them is reported per file |
| `has_template_files` / `has_no_template_files` | Trigger ×2 | the plan is non-empty / empty |
| `each_template_file` | Event Transform, explode | one event per path, in manifest order |
| `read_template_file` | HTTP Request | `GET /repos/{template_owner}/{template_repo}/contents/{path}` (raw) |
| `put_repo_file` | HTTP Request | `PUT /repos/{org}/{repo}/contents/{path}` `{message: "kit: copy <path>", content: <base64>}`. `retry_on_status [409, 429, 500-599]` (409: concurrent commits to the branch head), **retries 8**. A PUT into a repository with no commits, the conflict status code and the maximum content size are **K13**; sequential ordering, the Loops 5-minute limit against a ~200-file copy, and pacing are **K33** — chunk the list if the dev run shows a limit |
| `copied_files` | Event Transform, implode | joins the file branches (keyed on `run_guid`, sized by the plan) |
| `fallback_result` | Event Transform | `{copied, failed[], by_hand[]}` → `step_repo` detail: "copied with the Contents API (slow: one commit per file) — the template path is recommended" |

## Skills (A17)

| Action | Type | Does |
|---|---|---|
| `has_skills` / `has_no_skills` | Trigger ×2 | `parse_bundle.skills` non-empty / empty |
| `each_skill` | Event Transform, explode | one event per bundle skill `{name, description, body, license, compatibility, metadata, repo_path}` |
| `get_skill` | HTTP Request | `GET /api/v1/skills/{name}?team_id=<ops team id>`. **404 is excluded from `log_error_on_status`** (a new skill is expected) |
| `is_new_skill` | Trigger | 404 |
| `create_skill` | HTTP Request | `POST /api/v1/skills` `{team_id, name, description, body, license, compatibility, metadata}` |
| `is_kit_skill` | Trigger | 200 **and** the existing skill's `metadata.kit_run` is set — the kit created it in an earlier run |
| `update_skill` | HTTP Request | `PUT /api/v1/skills/{name}` `{team_id, description, body, license, compatibility, metadata}` |
| `is_customer_skill` | Trigger | 200 and no `metadata.kit_run` — the customer's own skill of the same name |
| `skill_conflict` | Event Transform | `{name, status: "exists"}` — **left as it is**, listed in `by_hand` as a conflict to resolve |
| `skill_outcome` | Event Transform | `{name, status: created \| updated \| exists \| failed, http_status}` from whichever branch reached it |
| `skills_done` | Event Transform, implode | joins the skill branches |
| `record_skills` | HTTP Request | ledger `step_skills` = `ok` when every skill is `created`/`updated`, `partial` when any is `exists` or `failed`, with the names in `message` |

`metadata` is a **flat string map**: the bundle's metadata plus `kit_run` (the run guid) and `git_sha` — empty at provisioning, because the bundle is read raw and carries no commit SHA; `kit-sync.yml`'s `skills-push` stamps the real one on the next merge to `main`. Which metadata keys the API accepts is scaffold VERIFY #14. **Attaching a skill to an AI Agent action is `[BY HAND]`** (no API): `backlog-planning` → `planner`, `story-brief-writing` → `brief_writer`, `story-retrospective` → `retro_writer`.

## Record types (A18)

| Action | Type | Does |
|---|---|---|
| `ent_records` / `has_no_records` | Trigger ×2 | `normalize.entitlements.records` true / false. `has_no_records` → `record_record_types` (`not_needed`) → A19 |
| `records_quota` | Event Transform | No list endpoint for record types is in the research, so the quota check counts the types the kit knows of: its own three plus the ops trio's six. On **Starter** (5 types) it drops `storyline_events` (the bundle marks it `skip_on_records_tier: ["starter"]`), keeps events in `events.jsonl` only, and adds a report line that the ops trio's six types alone exceed Starter's 5. It also drops any type whose `RESOURCE.kit_state.rt_<name>` is already set (a resumed run) |
| `each_record_type` | Event Transform, explode | one event per remaining bundle `record_types[]` entry |
| `create_record_type` | HTTP Request | `POST /api/v1/record_types` with the entry's `body` (from `kit/records/*.record-type.json`) and `team_id` = the ops team. The exact field-name key and whether the response returns field ids are **K16** |
| `store_record_type_id` | HTTP Request | ledger `{key: "rt_<name>", value: <created id>}` |
| `store_record_type_fields` | HTTP Request | ledger `{key: "fields_<name>", value: {<field name>: <field id>, …}}` from the create response (K16) |
| `record_types_done` | Event Transform, implode | joins the branches |
| `record_record_types` | HTTP Request | ledger `step_record_types` |

The ops trio's six Record types are **not** created here: they are created by hand as `stories/ops-story-health-monitor/records/record-types.md` says (Import step 1), and their ids reach `kit_config` through `kit/tenant/config.yaml` (`ops_record_types`) by PR.

## Resources (A19)

| Action | Type | Does |
|---|---|---|
| `resource_plan` | Event Transform | From `parse_bundle.resources[]`: keeps each Resource whose `RESOURCE.kit_state.res_<name>` is not set **and** — on a first run — whose `RESOURCE.<name>` reads as null (a Resource that already exists is reported `exists` and never overwritten; K10). `create: records_not_entitled` (`kit_tracker_view`) only when Records are not entitled; `create: when_absent` (the ops trio's `ops_limits`, `ops_lock`, `ops_responders`, `ops_routing`) only when absent. Fills the values built at run time: **`kit_config`** = `normalize.config` + team ids + `tenant_host` (in-tenant only) + `environment: "prod"` + `rt_ops_findings: 0`, `rt_ops_alerts: 0`; **`storyline_approvers`** = `{G0, G6, G7}` from the Page, `GX: []`, `unpark: []`; **`ops_responders`** = the example with the Page approvers as responders; **`storyline_limits`** keeps `enabled: false` and `guards_confirmed: false` from the bundle, so **no AI Agent action in section D runs before its token alert and skill exist** |
| `has_resources_to_create` / `has_no_resources_to_create` | Trigger ×2 | plan non-empty / empty |
| `each_resource` | Event Transform, explode | one event per planned Resource |
| `create_resource` | HTTP Request | `POST /api/v1/global_resources` `{name, value, team_id, read_access: "TEAM", description}` (≤ 5 MB each) |
| `store_resource_id` | HTTP Request | ledger `{key: "res_<name>", value: <created id>}` |
| `resources_done` | Event Transform, implode | joins the branches |
| `record_resources` | HTTP Request | ledger `step_resources`, listing `exists` names |

Locking `storyline_approvers` and `storyline_state_machine` (`PUT /api/v1/global_resources/{id}/locked`) is optional and **off by default**: the docs say unlocking through the API is permanent, and what that means is **K40**.

## Seeding (A21–A22)

After `is_seed_claimed`:

| Action | Type | Does |
|---|---|---|
| `seed_rows` | Event Transform | One `storyline_backlog` row per `normalize.use_cases[]`, plus `example-enrich-ip` and `ops-story-health-monitor` (`RESOURCE.kit_catalog.always_seeded`) when not already picked. Field values below |
| `each_seed_row` | Event Transform, explode | one event per row |
| `seed_backlog` | HTTP Request | `POST /api/v1/records` `{record_type_id: <<RESOURCE.kit_state.rt_storyline_backlog>>, field_values: [{field_id: <<RESOURCE.kit_state.fields_storyline_backlog.<field>>>, value}, …]}` with `test_mode` off — records created this way are live even in a change-controlled story (**K39**) |
| `backlog_seeded` | Event Transform, implode | joins |
| `each_milestone` | Event Transform, explode | one event per `RESOURCE.kit_catalog.milestones[]` (day-1, week-1, week-4) |
| `seed_milestones` | HTTP Request | `POST /api/v1/records` on `storyline_milestones`: `milestone_id`, `title`, `criteria` (the list as Markdown bullets), `status: not_started`, `due_date` = `provisioned_at` + `due_offset_days` (UTC), `evidence_ref: ""`, `owner: platform`, `rev: 1`, **`pending_repo_sync: true`** (the milestone type has no `outbox_seq`; E3 returns pending milestones in `milestones[]`) |
| `milestones_seeded` | Event Transform, implode | joins → `record_seed` |

Each seeded `storyline_backlog` row:

| Field | Value |
|---|---|
| `story_key`, `title`, `use_case`, `library_seed_id`, `mode`, `owner`, `tier` | from the row (`library_seed_id` only from `kit_catalog.seed_ids`; custom rows: `mode: none`, `tier: production`, no seed) |
| `phase` · `status` · `open_gate` · `attempt` | `intake` · `active` · `none` · `0` |
| `target_date` | the row's, UTC with `Z` (Records drop offsets) |
| `credit_estimate_monthly` · `credit_estimate_basis` · `provider` | from the catalog (`none` provider until `apply-config` sets it on AI rows) |
| `specialist_due` · `specialist_status` | `brief-writer` · `pending` when the AI Agent action is entitled; otherwise `none` · `idle` |
| `rev` · `pending_base_rev` | `0` · `0` for a row the repository does not have yet. **The two always-seeded rows already exist in the template's `kit/tracker/backlog.yaml` at rev 1**, so they are seeded with `rev: 1` and `pending_base_rev: 1`: Flow 1 then clears their pending flag only after the tracker PR (rev 2) merges (§6.5, B6) |
| `pending_repo_sync` · `outbox_seq` · `acked_seq` | **`true`** · **`1`** · `0` — so `tracker-pull.yml` brings the rows picked on the Page into git |
| `last_actor` · `last_transition_at` | `kit` · now (UTC) |

Seeding does not dispatch section D directly: the D1 sweep picks up `specialist_status: pending` rows (its 15-minute backstop), and nothing in D runs until a person sets `storyline_limits.enabled` and `guards_confirmed`.

## The setup report (A28)

`compose_report.report`, committed as `kit/tenant/setup-report.json` and rendered on the `setup_report` Page:

```json
{
  "status": "ok | partial | failed",
  "repo_url": "https://github.com/<org>/<repo>",
  "kit_story_id": 0,
  "steps": [ { "step": "step_repo", "status": "ok | failed | skipped | not_needed | exists | partial", "detail": "…" } ],
  "provider": { "status": "ok | tool_calls_unreliable | failed | not_entitled", "model": "…", "input_tokens": 0, "output_tokens": 0, "credits_used": 0, "tool_calls": 0 },
  "created": {
    "skills": ["backlog-planning"],
    "record_types": [ { "name": "storyline_backlog", "id": 0 } ],
    "resources": [ { "name": "kit_state", "id": 0 } ],
    "dashboard": { "name": "Storyworks", "id": 0 },
    "app": { "name": "Storyworks", "id": 0 }
  },
  "by_hand": [ { "item": "…", "status": "done | open | not_needed" } ]
}
```

- `status`: `ok` when every step is `ok`, `not_needed` or `exists`; `failed` when `step_repo`, `step_bundle` or the ledger failed; otherwise `partial`.
- `created.resources[]` must include `kit_state`, `storyline_sync_lock`, `storyline_state_machine`, `kit_catalog`, `kit_config` and `storyline_limits` with their ids: `./scripts/kit sync-resources` (`kit-sync.yml`) reads them from the committed report.
- `kit_story_id` feeds the setup-report PR (§7.1 step 5).
- `provider.credits_used` is expected to be 0 on a custom or local provider; `billed_cost` for those is K25.

### Step keys

| Key | Written by | Fatal? |
|---|---|---|
| `step_teams` | `record_teams` after A7e (A5–A6) | yes, when the ops team is missing (the run stops before a ledger exists) |
| `step_providers` | `record_providers` (A8–A9) | no |
| `step_github` | A10 | yes for A11–A24 (skips to F) |
| `step_repo` | `record_repo` (A11–A14) | yes |
| `step_bundle` | `record_bundle` (A15) | yes |
| `step_config` | `record_config` (A16) | no |
| `step_skills` | `record_skills` (A17) | no |
| `step_record_types` | `record_record_types` (A18) | no (seeding is then skipped) |
| `step_resources` | `record_resources` (A19) | no |
| `step_seed` | `record_seed` (A20–A22) | no |
| `step_dashboard` | `record_dashboard` (A23) | no |
| `step_app` | `record_app` (A24) | no |
| `step_probe` | `record_probe` (section F) | no |
| `step_report` | `record_report` (A29) | no |

`kit/docs/troubleshooting.md` maps each failed step to a fix.

### The `[BY HAND]` list the report always carries

Item by item, each marked `done`, `open` or `not_needed` (the report can mark only what it can observe; everything else is `open` until a person checks it):

1. **Pre-flight:** `allowed_hosts` is set on both credentials — `tines_api_kit` (the tenant host) and `github_factory` (`api.github.com`).
2. **AI provider:** configure or confirm the provider in Settings → AI settings. There is no API; the kit can only check it with `GET /api/v1/ai_providers` (A8–A9).
3. **Token alerts:** set a token-usage alert (Notify, then Disable action) on each AI Agent action's Status tab — `llm_probe`, `llm_tool_probe`, `planner`, `brief_writer`, `retro_writer` — at the numbers in `policies/cost-ceilings.yml`.
4. **Skills:** attach `backlog-planning` to `planner`, `story-brief-writing` to `brief_writer`, `story-retrospective` to `retro_writer`, and pin the tenant's fast model on those three actions. Resolve every skill the report lists as `exists` (A17 never overwrites a customer's skill).
5. **Credits:** per-team AI credit allocation and credit-alert thresholds (no API).
6. **Apps:** enable Apps for the ops team at `/settings/apps` (if entitled); publish the App; wire its three endpoints (`app_add_use_case`, `app_gate_decision`, `app_costs`).
7. **Tunnel:** for a local model, a Tunnel that all teams can access (§10.2).
8. **Change control:** tenant policies "Enable by default" and "Require approval for all changes" on.
9. **Builders' Tines roles:** every builder's Tines account is a Viewer, or not a member, in the prod team (which is the ops team). The Tines Stories MCP server acts with the user's own permissions, so this is what stops a Mode 2 session from writing there (§6.3).
10. **Approvers:** where the tenant has SSO group-based page access, an admin turns it on in the Authentication settings, and the `gate_decision` Page's access is set to **Via SSO**, restricted to the approvers SSO group (§4.5 rule 2). Add the `GX` and `unpark` approvers to `storyline_approvers`.
11. **Ops trio:** its six Record types exist in the ops team (Import step 1); add the `ops_findings` and `ops_alerts` type ids to `kit/tenant/config.yaml` by PR, so `kit-sync.yml` puts them in `kit_config` for D6 and D9.
12. **GitHub:** branch protection on `main` (require the one check `storyline`, which calls lint and review, and a CODEOWNERS review; no self-merge) · replace `<org>` in CODEOWNERS and the teams in `storyline/gates/approvers.yaml` · create the `tracker-bot` GitHub App on this repository only, with write access to contents and pull requests (exact permission headings as for K11), and install it · create the GitHub environments `production` (with required reviewers: G5a depends on them — one team, the G5a team in `storyline/gates/approvers.yaml`, and no individual reviewers), `break-glass`, `tracker` (the two webhook URLs and the `tracker-bot` App id and private key) and `kit-sync` (an ops-team Editor key) with their secrets — GitHub Actions secrets need a libsodium sealed box, which an HTTP Request action cannot produce, so this is always by hand · allow GitHub Actions to create pull requests (K12) · create the pull-request labels `tracker`, `tracker-drift` and `kit-config` (`tracker-pull.yml` and `kit.yml` apply them but never create them) · check that Actions is enabled on the new repository (K12).
13. **Tracker webhooks:** first **rotate the secret on `tracker_sync_in`, `tracker_outbox` and every app-endpoint Webhook** (an import may keep the published template's values, K8), then copy the `tracker_sync_in` and `tracker_outbox` URLs from the storyboard into `TRACKER_SYNC_URL` and `TRACKER_OUTBOX_URL` in the `tracker` environment. They carry secrets, so they never appear in the report.
14. **Clear the `github_factory` credential's value in Tines the same day, then revoke the provisioning token,** or let it expire (§13 row 2; `kit/docs/github-token.md`).
15. **Editor:** run `/tines-connect` in each builder's editor.
16. **Enable the runtime crew:** after the token alerts are set and the skills attached (items 3–4), set `storyline_limits.guards_confirmed` and `storyline_limits.enabled` to true. Until then no runtime crew member runs, and section B's kill switch also holds the tracker sync.
17. **Last: run `kit.yml` and `tracker-pull.yml` once** (Actions → Run workflow), so the config PR and the rows picked on the Page reach git.

Conditional items the report adds: the config commit by hand (when `step_config` failed); every `over_1mb` file of the fallback copy; each skill reported `exists`; the Dashboard built by hand (when A23 was skipped or failed, §9.4); a Slack credential named `slack_bot` when `chat_surface` is `slack` and `slack_credential_name` differs (K9).

## Test

`../tests/expectations.yaml` carries the section A expectations: the happy path through `kickoff_test` (a maintainer or customer **dev team**, a **scratch GitHub organisation**, a dev `kit_config` with `environment: "dev"`), and the refusal variants (`input_with_token`, `community_edition`, `one_licensed_team`, `already_provisioned`), which make no GitHub or Records call and are safe to run anywhere in dev. The happy path creates a real private repository in the scratch organisation; deleting it afterwards is a person's decision, made in GitHub.

## Verify in your tenant

| Item | What to check | Where it matters |
|---|---|---|
| K8 | The Page URL identifier and every Webhook path and secret after import | A1, the report links, rotation (item 13) |
| K10 | A formula reading a missing Resource yields null | A4, A7, A19 |
| K11 · K12 · K13 · K44 | Token permissions for `/generate` and org repository creation; readiness delay and Actions on generated repositories; Contents PUT semantics; the raw media type header | A10–A16, A29 |
| K14 | The base64 formula name (and the date, filter and string functions used) | A2, A12, A16, A29 |
| K16 · K17 · K18 | The record-type create body and response; Dashboard import by type name; App file pushes | A18, A23, A24 |
| K23 · K24 | Local and Azure providers' reported `provider_type` | A9 |
| K31 | Page behaviour: required fields, conditions inside the looping container, the submitter header | A1, A2 |
| K33 | Explode ordering, loops, pacing | A12, A17–A22 |
| K39 | API-created Records are live in a change-controlled story | A21–A22 |
| K41 | What a team-scoped Editor key may call | every Tines API call |
