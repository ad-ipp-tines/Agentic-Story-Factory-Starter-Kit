# `kit/tenant/` — the tenant config commit and the setup report

_Spec: REPO-DESIGN.md §7.1 (import and the setup-report PR), §7.2 A2, A16, A28–A29, §8.2 (`kit_config`), §13 rows 1 and 12._

In the template repository this folder holds only this file and [`config.example.yaml`](config.example.yaml). In a customer's repository `[KIT] 00` adds two files on day 1:

| File | Written by | What it is |
|---|---|---|
| `kit/tenant/config.yaml` | A16 `write_config` — `PUT /repos/{org}/{repo}/contents/kit/tenant/config.yaml`, straight to `main` of the brand-new repository (branch protection comes later, `[BY HAND]`) | **The tenant-specific config commit**: the kickoff Page's answers as A2 normalised them — teams, plan, entitlements, Records tier, the Tines-side model choice, the chat surface, credential **names**, the GitHub organisation and repository. Written as JSON, which a YAML 1.2 parser reads. The shape and every key: [`config.example.yaml`](config.example.yaml) |
| `kit/tenant/setup-report.json` | A29 `write_report` — `PUT …/contents/kit/tenant/setup-report.json` | The day-1 provisioning result (below). The same report is on the `setup_report` Page (per-run link, emailed to the submitter) |

On the **Community path** there is no kit story: copy `config.example.yaml` to `config.yaml`, fill it in by hand, and there is no setup report (`kit/docs/community-path.md`).

## What never lands here

The config commit leaves out **the tenant host and every email address** (§13 row 12). The tenant host lives only in the `kit_config` Resource inside the tenant; approver emails live only in the `storyline_approvers` Resource; the in-tenant `actor_ref` of a gate decision never leaves Tines. Credentials are referenced by **name** (`tines_api_kit`, `github_factory`, `tines_api_readonly`, optionally a Slack credential) and must exist in the ops team before the first run. No token, key or webhook URL is ever written to this folder — the kickoff Page's `is_valid_input` Trigger (A3) rejects token-shaped values in any field, and `./scripts/kit apply-config` refuses a config that carries one.

## What happens after the two commits

Their push to `main` runs `kit.yml` (or run it once by hand — Actions → Run workflow — if Actions was not enabled yet, K12). `./scripts/kit apply-config` then opens two pull requests with the `tracker-bot` GitHub App token:

| PR (branch) | Changes | Why |
|---|---|---|
| `kit/config-<run_id>` | `stories/_manifest.yaml`: `environments.dev.team_id`, `environments.prod.team_id` (the prod team **is** the ops team) and `stories.kit-launch.prod.story_id` = the report's `kit_story_id` · `policies/never-touch.yml`: `kit_story_id` appended to `story_ids`, the prod team id in `teams` · `policies/cost-ceilings.yml`: `teams.ops.team_id`, `teams.dev.team_id`, the kit agents' `provider` | **The setup-report PR** (§7.1 step 5): `ship.yml` changes the imported kit through `versionReplace` instead of creating a second `[KIT] 00`, and `guard-mcp.sh` protects it by id as well as by name |
| `tracker/config-<run_id>` | `kit/tracker/milestones.yaml` due dates and backlog target dates that are still empty (provisioning time + the catalog offsets), and the `provider` of rows whose story runs an AI Agent action; one `sync` event per changed row | On the Records path, Flow 2 usually brought these first and this PR is not needed; on the Community path this is where they come from |

`apply-config` **fills placeholders only**. A value that is already set and differs is reported in the PR body as a conflict and left alone. A CODEOWNER reviews each PR and a person merges it; `kit-sync.yml` then pushes the merged config into the `kit_config` Resource.

**Merge the `kit/config-<run_id>` PR first.** The bundle's `kit_config` value follows `config.yaml` (`kit/bundle/README.md`), and A16 committed `config.yaml` straight to `main`, so `./scripts/storyline check` (`bundle_fresh`) fails on every other PR until that PR — which also carries the regenerated bundle — has merged. Rebase any tracker PR opened before it.

Later changes to `config.yaml` — a new entitlement, the ops trio's Record type ids under `ops_record_types` (a day-1 `[BY HAND]` item, so D6 and D9 can read `ops_findings` and `ops_alerts`), a different provider — go through an ordinary PR; every merge re-syncs `kit_config`.

## The setup report

`kit/tenant/setup-report.json`, built by A28 `compose_report` from the `step_*` keys in `kit_state`:

```json
{
  "status": "ok | partial | failed",
  "repo_url": "https://github.com/<org>/<repo>",
  "kit_story_id": 0,
  "steps": [ { "step": "step_repo", "status": "ok | failed | skipped | not_needed", "detail": "…" } ],
  "provider": { "status": "ok | tool_calls_unreliable | failed", "model": "…", "input_tokens": 0, "output_tokens": 0,
                "credits_used": 0, "tool_calls": 0 },
  "created": {
    "skills": [ "backlog-planning", "…" ],
    "record_types": [ { "name": "storyline_backlog", "id": 0 } ],
    "resources": [ { "name": "kit_state", "id": 0 }, { "name": "storyline_sync_lock", "id": 0 }, { "name": "kit_config", "id": 0 } ],
    "dashboard": { "name": "Storyworks", "id": 0 },
    "app": { "name": "Storyworks", "id": 0 }
  },
  "by_hand": [ { "item": "…", "status": "done | open | not_needed" } ]
}
```

Who reads it:

- `./scripts/kit apply-config` — `kit_story_id` (A28 looks it up with `GET /api/v1/stories`, matched on the story's own name).
- `./scripts/kit sync-resources` (`kit-sync.yml`) — `created.resources[]`: the ids of `kit_state`, `storyline_sync_lock`, `storyline_state_machine`, `kit_catalog`, `kit_config` and `storyline_limits`. A missing id stops the sync with a message; add it by PR.
- People — `steps[]` and `by_hand[]`. `kit/docs/troubleshooting.md` maps each failed step to a fix; `kit/ONBOARDING.md` walks the `[BY HAND]` list (pre-flight `allowed_hosts`, the AI provider, token alerts, skill attachment, credits, Apps, the Tunnel, change control, builders' Tines roles, approvers, the ops trio's Record types, GitHub protection and environments, the tracker webhooks — rotate their secrets first, K8 — revoking the provisioning token, `/tines-connect`, enabling the runtime crew, and running `kit.yml` and `tracker-pull.yml` once).

The report never carries a secret: no token, no webhook URL (the tracker URLs are copied from the storyboard into the GitHub environment `tracker` by hand), no email address.

## Step keys

The step names are section A's (`stories/kit-launch/sections/A-kickoff-and-provisioning.md` is the authority). The kit expects: `step_teams` (A5–A6), `step_providers` (A8–A9), `step_github` (A10), `step_repo` (A11–A14), `step_bundle` (A15), `step_config` (A16), `step_skills` (A17), `step_record_types` (A18), `step_resources` (A19), `step_seed` (A20–A22), `step_dashboard` (A23), `step_app` (A24), `step_probe` (section F), `step_report` (A28–A29).
