# `kit/bundle/` — the one file the kit story reads from the repository

_Spec: REPO-DESIGN.md §2, §7.2 A12, A15, A17–A24, §15.4, §15.6. Built by `scripts/kit_bundle.py`._

[`kit-bundle.json`](kit-bundle.json) is **generated — never edit it by hand.** `[KIT] 00` reads it twice:

- **A15 `read_bundle`** reads the **new repository's own** copy (`GET /repos/{org}/{repo}/contents/kit/bundle/kit-bundle.json`, raw → `JSON_PARSE`), so the tenant is provisioned from exactly what the customer's repository holds. Sections B–E cannot be provisioned without it.
- **A12 `fallback_repo`** reads the **template's** copy for its file manifest when `POST …/generate` is refused, and copies each file with the Contents API.

## What is in it

| Key | Built from | Used by |
|---|---|---|
| `skills[]` | every `tines-skills/<name>/SKILL.md`, parsed and validated exactly as `./scripts/tines skills-push --validate-only` does (`{name, description, body, license, compatibility, metadata, repo_path}`) | A17 — creates each skill in the ops team; never overwrites a customer's skill of the same name (reported as `exists`) unless its `metadata.kit_run` shows the kit created it |
| `record_types[]` | `kit/records/*.record-type.json` (`{name, file, skip_on_records_tier, body}`) | A18 — `POST /api/v1/record_types` with `body` + `team_id`; `sdlc_events` is skipped on the Starter Records tier |
| `resources[]` | the Resources A19 creates (`{name, create, value, read_access, description, built_at_run_time?}`); `create` is `always`, `records_not_entitled` (`kit_tracker_view`) or `when_absent` (the ops trio's four). `kit_config` is `null` in the template (A19 builds it from the Page); in a provisioned repository it is `kit/tenant/config.yaml` in bundle form (placeholder `tenant_host`). Each synced Resource's `value` is also what `kit_state.hash_<name>` fingerprints (`resource_hash`, `kit/resources/README.md`) | A19; `resources_in_sync` |
| `dashboard` + `dashboard_skeleton` | `kit/dashboard/dashboards/story-factory.dashboard.json` | A23 — `POST /api/v1/dashboards/import` (`data: bundle.dashboard`). **A SKELETON until the §15.6 release**; A23's import is expected to fail until then, and the report says so |
| `app_entry` + `app_files[]` | `kit/dashboard/app/**` — tsx, ts, jsx, js and json only (`{path, content}`, paths relative to the App root; `endpoints.md` stays out) | A24 — `PUT /api/v1/apps/{id}/files` `{files: bundle.app_files}` (replaces every draft file; `App.tsx` must be present). The file object's keys and nested paths are **VERIFY K18** |
| `file_manifest[]` + `file_manifest_frozen` | the repository's files (git's list when this is the repository's own git, else a walk that skips local and secret files), one `{path}` per file; `over_1mb: true` marks a `[BY HAND]` copy, `workflow: true` a file that needs the token's Workflows permission (K11), `self: true` this file | A12's fallback copy. In a **provisioned** repository (`kit/tenant/config.yaml` exists) the manifest is carried over unchanged, because the fallback copy is a template-only concern and a customer's new files must not make the bundle stale |
| `state_machine` | the `sdlc_state_machine` Resource value (`kit/resources/sdlc_state_machine.example.json`) | A19; sections B, C, D |
| `catalog` | the `kit_catalog` Resource value (`kit/resources/kit_catalog.example.json`) | A2, A19, A21, A22 |

The bundle carries no timestamp and no commit SHA, so the same sources always give the same bytes, and it refuses to build if any string in it looks like a secret or is a real email address.

## Commands

```bash
./scripts/kit bundle            # rebuild kit-bundle.json and the five generated examples in kit/resources/
./scripts/kit bundle --check    # write nothing; exit 1 and name what is stale (kit.yml on PRs; sdlc check bundle_fresh)
```

**Regenerate it in the same PR** whenever you change one of its sources — the bundle's own `generated_from` list: `tines-skills/*/SKILL.md`, `kit/records/*.record-type.json`, `kit/catalog/*.yaml`, `kit/tracker/milestones.yaml`, `sdlc/lifecycle/state-machine.yaml`, `policies/cost-ceilings.yml`, `stories/ops-story-health-monitor/resources/*.example.json`, `kit/dashboard/app/**` and the dashboard. **In the template repository (no `kit/tenant/config.yaml` yet), adding or removing ANY file, anywhere, also changes the file manifest**, so such a PR needs `./scripts/kit bundle` too, whatever it touches. `sdlc.yml` (the required check, `bundle_fresh`) and `kit.yml` (every PR) both fail while the committed bundle differs from what the sources produce.

## Limits

- A Resource holds at most 5 MB; an App file at most 128 KB and a build at most 5 MB (the builder checks all three).
- The bundle is read raw from GitHub. Keep it well under 1 MB: GitHub's raw media type header string and its behaviour above 1 MB are **K44**; the builder warns above 900 KB.
- **Release check (§15.6):** `kit.yml` job `release` fails while `stories/kit-factory/story.json` or the dashboard still carries the SKELETON label. Run `./scripts/kit bundle` after the release replaces the dashboard with a real export.
