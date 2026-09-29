# Page `kickoff` (root) — start the Storyworks

_Spec: REPO-DESIGN.md §7.8 (`kickoff`), §7.2 A1–A3b (what reads it), §1.4 (plans), §10.2 (the model choice), §13 row 1 (no token on a Page). Section A of `[KIT] 00 · Launch Storyworks`; built through Mode 2 with build prompt P-K2 (`../build-prompts.md`). This file is the specification the builder follows and the reviewer checks the export against; it is never a substitute for the export._

**What it is.** The one form a customer answers on day 1. Its answers drive every step of section A ([`../sections/A-kickoff-and-provisioning.md`](../sections/A-kickoff-and-provisioning.md)): which teams to use, what was purchased, which model provider to probe, where to create the repository, which starter stories to seed, and who decides the Tines-side gates. It asks for the **name** of a credential at most — never a token, key or password — and `is_valid_input` (A3) refuses any answer that looks like one.

## Settings

| Setting | Value | Notes |
|---|---|---|
| Page name (action name) | `kickoff` | answers arrive under `kickoff.body.<field>`; the looping container under `kickoff.body.use_cases` |
| Kind | root Page — an entry point of section A | |
| URL identifier | `storyworks-kickoff` | the root URL is `https://<your-tenant>.tines.com/pages/storyworks-kickoff`. Whether the identifier survives story import is **K8**; if it does not, set it again after import |
| Access | **Only team members** (the default; never "Anyone with the link") | §7.8, §13 row 6 |
| Anonymise submissions | **off** | `normalize` reads the submitter's email from the Page headers (the report is emailed to them) |
| Submission mode | **Show success message**: "Provisioning started. The setup report link will be emailed to you and committed to `kit/tenant/setup-report.json`." | the report arrives later, by email and on the `setup_report` Page |
| Run on | the **LIVE** story | a submission on a change-control draft would write test records (§7.1, K39) |

Element types are the documented set only: Short text, Long text, Email, Option, Date or time, Boolean, Number, Heading, Rich text, Divider, Button, Table, Chart. **Whether an element can be marked required is K31**, so A3 `is_valid_input` is the enforcement, not the Page. **The Password element is not used** (§13 row 1).

## Elements

| # | Container / element | Type | Body key | Default · options · condition |
|---|---|---|---|---|
| 1 | "Start your Tines Storyworks" | Heading | — | — |
| 2 | Intro | Rich text | — | What will be created: a private repository in your GitHub organisation, the Tines Agent Skills, three Record types (the tracker), the kit's Resources, and — when entitled — a Dashboard and an App. Then, in bold: **"Enter the NAME of a Tines credential. Never paste a token, key or password into this page."** |
| 3 | **Organisation** — company name | Short text | `company_name` | — |
| 4 | Tines tenant host | Short text | `tines_tenant_host` | Pre-filled from the `?tines_tenant_host=` query parameter. Used only inside the tenant (the `kit_config` Resource and the Tines API calls); **never committed**. Must be `<your-tenant>.tines.com` (A3) |
| 5 | Dev team | Short text | `dev_team_name` | the dedicated dev team, where every build happens — never a personal team |
| 6 | Prod team (the ops team, where this story lives) | Short text | `prod_team_name` | The ops team **is** the prod team (§7.1); the Page asks for no third team. A6 stops the run if this team does not resolve |
| 7 | **Plan** — plan tier | Option | `plan_tier` | `community_edition \| business \| enterprise` |
| 8 | Licensed standard teams | Number | `licensed_teams` | Teams are an add-on; **fewer than 2 sends the run to the manual path** (A3b) |
| 9 | Self-hosted | Boolean | `self_hosted` | false |
| 10 | Entitlements | Boolean ×7 | `ent_pages`, `ent_apps`, `ent_cases`, `ent_records`, `ent_ai_agent_action`, `ent_change_control`, `ent_tunnel` | `ent_pages` true (Pages are in every edition); the others false. Help text: "Tick only what was purchased — the kit branches on these and never assumes" |
| 11 | Records licence tier | Option | `records_tier` | `starter \| essentials \| standard \| advanced \| enterprise_l1`; shown when `ent_records` is true; read by A18's quota check (Starter holds 5 record types, which the ops trio's six already exceed) |
| 12 | Community note | Rich text | — | Shown when `plan_tier == community_edition`: "Community Edition uses the manual path: follow `kit/docs/community-path.md` in the template repository. Do not submit this Page." |
| 13 | **AI model** — choice | Option | `llm_choice` | `tines_provided \| byo_anthropic \| byo_openai \| byo_bedrock \| byo_azure_openai \| local_ollama_via_tunnel \| local_vllm_via_tunnel \| local_other_openai_compatible_via_tunnel`. Help text: "This is the model Tines' AI Agent actions use (Settings → AI settings), not your editor's model" (`kit/docs/llm-editor-side.md`) |
| 14 | Provider name as shown in Settings → AI settings | Short text | `provider_name` | Hidden when `llm_choice == tines_provided` |
| 15 | Model to probe (display name) | Short text | `model_display_name` | Optional; A9 picks its `api_model_id` |
| 16 | Tunnel warning | Rich text | — | Shown when `llm_choice` starts with `local_` and (`ent_tunnel` is false or `self_hosted` is true): "A local model inside your network needs a Tunnel, which is cloud-only and an add-on enabled through Tines support (§10.2). Self-hosted tenants have no Tunnel." |
| 17 | **GitHub** — organisation | Short text | `github_org` | — |
| 18 | Repository name | Short text | `repo_name` | `tines-storyworks` |
| 19 | Template repository | Short text | `template_repo` | `<template-owner>/<template-repo>` — the kit's published template; it must be readable by the token |
| 20 | GitHub credential note | Rich text | — | "Store the GitHub token in the Tines credential named `github_factory` before you submit. The kit uses that fixed name. Use a fine-grained token that expires within 7 days and revoke it after day 1 (`kit/docs/github-token.md`)." |
| 21 | **Target use cases** | Looping container, **10 iterations** | `use_cases` | Loop formula = an array of 10, evaluated once at page load. 4 elements × 10 = 40 looped elements, within the 100 limit |
| 21a | · pick | Option | `pick` | Options from an array formula: the ten starter stories (`RESOURCE.kit_catalog.page_pick_options`, which already ends in `custom` and `none`); default `none`. Whether Option lists can come from a Resource is **K31**; if not, the ten keys + `custom` + `none` are typed into the Option at build from `kit/catalog/starter-stories.yaml` |
| 21b | · custom title / custom description | Short text / Long text | `custom_title`, `custom_description` | Shown when `pick == custom`. Whether a condition can reference a sibling element in the same iteration is **K31**; if not, both are always shown with the help text "only for custom" |
| 21c | · owner role | Short text | `owner_role` | Defaults to the catalog owner. **A role, never a person** (A3 refuses an `@`) |
| 22 | **Chat surface** | Option | `chat_surface` | `slack \| microsoft_teams \| email \| tines_pages_only`. In v1 notifications go by Email, plus Slack when chosen. Teams-specific delivery is not in the research, so Teams gets email plus a note in the report |
| 23 | Slack credential NAME | Short text | `slack_credential_name` | Shown when `chat_surface == slack`. The kit sends through the credential named `slack_bot` (a name computed at run time is K9); a different name here is reported as a `[BY HAND]` item |
| 24 | **Gate approvers** (G0 / G6 / G7) | Email ×3 | `approver_g0`, `approver_g6`, `approver_g7` | Stored **only** in the `storyline_approvers` Resource (and as `ops_responders` when that Resource is created); **never committed**. GX and unpark approvers are added to the Resource by hand |
| 25 | Consent | Boolean | `consent` | "I understand this creates a private repository in the organisation above and creates, in the ops team, the Skills `alert-policy`, `credit-budget-analyst`, `story-build-conventions`, `story-health-triage`, `backlog-planning`, `story-brief-writing` and `story-retrospective` (an existing skill of the same name is left as it is and reported), Record types, Resources (and, if entitled, a Dashboard and an App)." Must be true (A3) |
| 26 | Provision | Button | `button` | submission value `provision` |

No element carries a credential value, a token or a webhook URL. `tests/sample-event.json` is a submission of this Page with placeholders only.

## What follows the Page (section A)

`kickoff` → A2 `normalize` → A3 `is_valid_input` (or `input_error` → email) → A3b/A3e the plan check (or `community_path` → email) → A4 the resume check → provisioning A5–A24 → section F → A28 `compose_report` → A29 the report commit → A30 → the [`setup_report`](setup-report.md) Page → A32 `email_report` to the submitter.

## Verify in your tenant

| Item | What to check |
|---|---|
| K8 | The `storyworks-kickoff` identifier after import |
| K31 | Required fields; conditions on a sibling inside the looping container; Option lists from a Resource; the header key that carries the submitter's email |
| K9 | A credential referenced by a name computed at run time (the Slack credential) |
