# `terraform/` — the optional Terraform path (not wired to CI)

_Scaffold `tines-stories-as-code` · builder `ci` · spec `../DESIGN.md` §3.8 · created 2026-09-25 · platform **Tines Stories** (Tines Classic)._

**Status: optional, off the default pipeline, dev team only.** No workflow in `.github/workflows/` runs Terraform. `terraform apply` is **denied** in the editor (`.claude/settings.json`), so a person runs it in their own terminal, deliberately. Production is reached through `ship.yml` — import into a named draft → change request → a named person approving in Tines — and nothing in this directory changes that.

## Why it exists

Tines publishes a Terraform provider as its official way to keep stories as code in Git. This repository keeps that path available — for teams whose platform standard is Terraform, for bulk *deployment* of already-reviewed exports into a sandbox, and as a vendor-neutral fallback — without letting it become a second way into production. The review still happens on `stories/<slug>/story.json`: `lint.yml`, `review.yml`, a CODEOWNER and a human merge. Terraform is an alternative **deploy** path, never an alternative **review** path.

## The provider

| | |
|---|---|
| Source | `tines/tines` on the Terraform registry |
| Version | **0.3.0** (published 2025-08-01), pinned `~> 0.3.0` in `main.tf` |
| Stability | 0.x — breaking changes are allowed in minor releases. Read the changelog before any bump; a bump is its own PR |
| Configuration | from the environment: `TINES_TENANT` and `TINES_API_KEY` (`../DESIGN.md` §3.8) — never in a `.tf` or `.tfvars` file |
| Terraform | ≥ 1.11 (ephemeral variables and write-only arguments) |

Still 0.3.0? That is **VERIFY #22** (`../docs/VERIFY.md`) — check the registry before the first plan, and update this table and the pin in the same PR if it moved.

## The VERIFY that keeps it out of production

**How `tines_story` applies to a change-controlled story is unverified (VERIFY #22).** It may land in a draft, or it may write the live story directly. If it writes live, a `terraform apply` against production would skip the draft, the change request and the named approver — the one path into production this repository allows. So:

- `main.tf` refuses any `environment` other than `dev` until `verify_22_confirmed = true` is set **in a reviewed PR** that also records the outcome in `../docs/VERIFY.md`.
- Even after #22 is confirmed, production stays on `ship.yml` unless this README is changed, in a PR reviewed by security-platform. `.github/CODEOWNERS` has no line for `/terraform/` today; if you adopt this path, add `/terraform/** @<org>/security-platform` in the same PR, because a deploy path is a gate.
- Choose **one** deploy path per environment. `ship.yml` and Terraform against the same team fight each other, and `drift.yml` would report every Terraform apply as drift attributed to the Terraform key.

How to confirm #22: in the dev team, create a scratch story with change control on, `terraform apply` a small change to it, then look for a new draft and a pending change request versus a changed live story. Record what you saw, with the provider version, in `../docs/VERIFY.md`.

## What it manages — and what it cannot

| Thing | In Terraform? | How |
|---|---|---|
| Stories | yes — `tines_story` (`stories.tf`) | `data = file("../stories/<slug>/story.json")`, `team_id` / `folder_id` from `../stories/_manifest.yaml`, `change_control_enabled = true`, `keep_events_for` from `story.meta.yaml`, `tags` = `stories-as-code` + tier. Only the slugs in `managed_slugs`; `prevent_destroy` on every one |
| The `ops_limits` Resource | optional — `tines_resource` (`main.tf`) | `manage_ops_limits = true`; the value comes from a **gitignored** `*.tfvars` file, never committed |
| TEXT credentials | optional — `tines_credential` (`main.tf`) | `value_wo` / `value_wo_version`: the value arrives as an **ephemeral** variable for one run and is never stored in state or shown in a plan. The provider manages **TEXT credentials only** |
| `allowed_hosts`, Workbench access on credentials | not assumed | set in the tenant [BY HAND] unless the pinned provider exposes them (VERIFY #22) |
| Tines Agent Skills (`../tines-skills/`) | **no** — no `tines_skill` resource exists | `skills.yml` and the Skills API (`/api/v1/skills`) |
| Record types | **no** — no record-type resource exists | [BY HAND] (`../stories/ops-story-health-monitor/records/record-types.md`) |
| Recipients, `monitor_failures`, watchdogs | **no** | `ship.yml` from the manifest; whether `tines_story` overwrites them on apply is part of VERIFY #22 |
| Change requests, approvals, promotion | **no** | Tines, a named person, and optionally `promote.yml` on an APPROVED request |
| MCP connections on AI Agent actions | **no** | dropped on import; re-created by hand, never with a pasted token |

Argument names beyond those `../DESIGN.md` §3.8 names (`data`, `team_id`, `folder_id`, `change_control_enabled`, `keep_events_for`, `tags`, `value_wo`, `value_wo_version`) carry a `VERIFY #22` comment in the `.tf` files: read the registry page for the pinned version before the first plan.

## Guards built into the configuration

- **Dev only** until #22: a validation on `environment`.
- **No skeletons:** a precondition refuses any `story.json` whose description starts with `SKELETON` — the committed skeletons in `../stories/` are not importable, so nothing is planned until a real `/tines-export` has replaced them.
- **Names match:** a precondition requires `story.meta.yaml` `name` == `story.json` `name` (import matches by name).
- **No zero ids:** preconditions refuse `team_id` / `folder_id` still `0` in the manifest.
- **Locked ops stories:** a precondition refuses any slug in the environment's `locked_slugs` outside dev (`policies/never-touch.yml`).
- **Nothing is ever deleted:** `prevent_destroy` on every managed story; removing a slug from `managed_slugs` fails the plan instead of deleting the story.
- **Explicit scope:** `managed_slugs` is a list you write, never "every folder under `stories/`".

## Running it — dev team only

```bash
source ../.env                                # TINES_TENANT (host prefix) and a TEAM-scoped dev key (Editor role)
# VERIFY #22: if the provider wants a full URL, export it for this shell only:
#   export TINES_TENANT="https://${TINES_TENANT}.tines.com"
terraform init                                # downloads tines/tines ~> 0.3.0 from the registry
terraform plan -var-file=dev.tfvars           # dev.tfvars is gitignored (terraform/*.tfvars); never commit it
# a person reads the plan, then — outside the editor, where apply is denied —
terraform apply -var-file=dev.tfvars
```

`dev.tfvars` (gitignored; the shape only):

```hcl
environment       = "dev"
managed_slugs     = ["example-enrich-ip"]
manage_ops_limits = false
# ops_limits_json = "<the dev tenant's ops_limits JSON — from the tenant, never from the repo>"
# text_credential_versions = { tines_api_readonly = 1 }
```

A credential value, when you opt in, is passed for one run only and never written down:

```bash
read -rs VALUE && TF_VAR_text_credential_values="{\"tines_api_readonly\":\"$VALUE\"}" terraform apply -var-file=dev.tfvars; unset VALUE
```

After an apply that created stories, commit the `story_ids` output to `../stories/_manifest.yaml` through a PR — the same follow-up `ship.yml` opens for `new: true` slugs.

## State, lock file and secrets

- State contains story JSON (configuration only — exports carry no credential values, Resource contents or events) and never a credential value (`value_wo`). Keep it in a remote, encrypted, access-controlled backend anyway; configure the `backend` block per organisation. `.gitignore` excludes `terraform/*.tfstate*`, `terraform/*.tfvars` (except `*.example.tfvars`) and `.terraform/`.
- `.gitignore` also excludes `.terraform.lock.hcl`. If you adopt this path, consider committing the lock file so every run uses the same provider build — a deliberate change to `.gitignore` in its own PR.
- The router's webhook URL, API keys and Resource values never appear here. `block-secrets.sh` and `lint.yml`'s secret scan cover `.tf` files like any other.

## Verify in your tenant before presenting

Nothing below is a headline claim.

- **#22** How `tines_story` applies to a change-controlled story (draft vs live), and whether it overwrites recipients and monitor flags; the provider is still 0.3.0; the argument names marked VERIFY in `main.tf` and `stories.tf`; whether the provider expects the host prefix or a full URL in `TINES_TENANT`.
- **#8** The export key names — Terraform deploys the same export `lint-story.sh` reads, so the same unknowns apply.
- Whether the provider accepts a normalised export (`exported_at` removed, keys sorted) as `data` unchanged.
