# `kit/resources/` — the kit's Resources

_Spec: REPO-DESIGN.md §8.2. Created in the ops team by `[KIT] 00` A19 through `POST /api/v1/global_resources` (`{name, value, team_id, read_access: "TEAM", description}`, each ≤ 5 MB), except `kit_state`, which A7 creates first. Formulas read them by name (`RESOURCE.<name>`). The files here are **examples of the values** — placeholders only; the real values live in the tenant._

| Resource | Example | Contents | Written by | Read by |
|---|---|---|---|---|
| `kit_config` | [`kit_config.example.json`](kit_config.example.json) *(generated)* | `kit/tenant/config.yaml` + `tenant_host` (in-tenant only) + `environment` (`prod` in the ops team; `dev` only in a dev copy) + the ops trio's type ids `rt_ops_findings`, `rt_ops_alerts` | A19; then `kit-sync.yml` on every merge (whole value) | sections B, C, D |
| `kit_state` | [`kit_state.example.json`](kit_state.example.json) *(generated)* | The run ledger, **flat keys** (`…/replace` addresses top-level keys): `status`, `run_guid`, `self_id`, `repo`, `step_*`, `rt_<type>`, `fields_<type>` (field-name → field-id maps), `res_<name>`, `records_seeded`, `app_id`, `dashboard_id`, `planner_last_run`, `hash_<resource>` | A (element replace, compare-and-swap); `kit-sync.yml` (`hash_*` only) | A (resume), B, D, E (snapshot) |
| `kit_catalog` | [`kit_catalog.example.json`](kit_catalog.example.json) *(generated)* | The ten starter stories, the always-seeded rows, the Page's pick options, the verified Library ids and `seed_ids`, the milestone catalog | A19 (from the bundle); `kit-sync.yml` | A2, A21, A22, C (Option lists), D4 (the seed-id filter) |
| `storyline_state_machine` | [`storyline_state_machine.example.json`](storyline_state_machine.example.json) *(generated)* | Phases, statuses, gates, caps, timers, `transitions`, `runtime_dispatch`, and derived lookups: `phase_statuses`, `gate_decisions`, `page_options`, `page_decision_table`, `enums` | A19 (from the bundle); `kit-sync.yml` | B (B3 enum checks), C (C5 `apply_decision`), D (dispatch) |
| `storyline_limits` | [`storyline_limits.example.json`](storyline_limits.example.json) *(generated)* | `{enabled, guards_confirmed, runtime: {planner, brief_writer, retro_writer}, gate_nudge_days, retro_cadence_days, shadow_days, pending_reset_hours}` — created with **`enabled: false` and `guards_confirmed: false`** | A19; `kit-sync.yml` (every key except the two flags, through `…/replace`); **people** (the two flags) | B, D, E |
| `storyline_approvers` | [`storyline_approvers.example.json`](storyline_approvers.example.json) | `{G0: [], G6: [], G7: [], GX: [], unpark: []}` — approver emails, **never committed** | A19 (G0, G6, G7 from the kickoff Page); people | C (`is_approver`) |
| `storyline_sync_lock` | [`storyline_sync_lock.example.json`](storyline_sync_lock.example.json) | `{lock: "free"}` | B and `kit-sync.yml` (compare-and-swap) | B |
| `kit_tracker_view` | [`kit_tracker_view.example.json`](kit_tracker_view.example.json) | The backlog + milestones mirror (counts by phase, open gates, rows, CSV text for the Page Tables) — **only when Records are not entitled** | B10 (whole value, under the lock; the value is `tracker-json`'s `view`) | C (Pages) |
| `ops_limits`, `ops_lock`, `ops_responders`, `ops_routing` | `stories/ops-story-health-monitor/resources/*.example.json` | The scaffold's ops-trio Resources; responders = the Page approvers | A19, **only when absent** | the ops trio |

## Generated vs hand-shaped

`./scripts/kit bundle` writes five of these examples from their sources, and `./scripts/kit bundle --check` (run by `kit.yml` on PRs and by `./scripts/storyline check`, `bundle_fresh`) fails when one is stale:

| Example | Generated from |
|---|---|
| `kit_catalog.example.json` | `kit/catalog/starter-stories.yaml`, `kit/catalog/library-seeds.yaml`, the id/title/criteria/offset of each milestone in `kit/tracker/milestones.yaml` |
| `storyline_state_machine.example.json` | `storyline/lifecycle/state-machine.yaml` and the TEXT_ENUM values in `kit/records/*.record-type.json` |
| `storyline_limits.example.json` | the `kit-launch/*` lines of `policies/cost-ceilings.yml` (else the §8.2 defaults: planner 4 runs/day and 2 credits/run, brief_writer 20 and 2, retro_writer 5 and 3), the planner debounce and the timers in `state-machine.yaml`, `pending_reset_hours: 24` |
| `kit_config.example.json` | `kit/tenant/config.example.yaml` + `tenant_host: <your-tenant>.tines.com` + `environment: prod` |
| `kit_state.example.json` | the field names in `kit/records/*.record-type.json` and the kit's Resource names |

The other three (`storyline_approvers`, `storyline_sync_lock`, `kit_tracker_view`) are shapes written by hand.

## Rules

- **Two flags only people set.** `storyline_limits.enabled` is the kill switch for the runtime crew (and section B's tracker sync); `guards_confirmed` says the token alerts are set and the skills attached. Both start `false`; no AI Agent action runs until a person sets both to `true` after those `[BY HAND]` steps (§7.2). `kit-sync.yml` never writes them.
- **`kit_state` step keys.** Section A records each provisioning step as `step_<name> = {status, http_status, message}` and the report is built from them. The example shows the keys the kit expects (`step_teams`, `step_providers`, `step_github`, `step_repo`, `step_bundle`, `step_config`, `step_skills`, `step_record_types`, `step_resources`, `step_seed`, `step_dashboard`, `step_app`, `step_probe`, `step_report`); `stories/kit-launch/sections/A-kickoff-and-provisioning.md` is the authority for the list, and `kit/docs/troubleshooting.md` maps each failure to a fix.
- **`kit_state` hashes.** `kit-sync.yml` writes `hash_<name>` = the SHA-256 hex of the canonical JSON (sorted keys, no whitespace) of the Resource's **bundle-form value** — exactly `resources[].value` in `kit/bundle/kit-bundle.json`, the definition `storyline_common.resource_hash` holds. Bundle form means `storyline_limits` with its two flags at their created value and `kit_config` with the `<your-tenant>.tines.com` placeholder for `tenant_host`, so the repository can recompute every hash from `main` without the tenant host. A hash is a fingerprint of what `kit-sync.yml` last pushed, not of the tenant's live value: the check shows whether the tenant has the current `main`. The nightly snapshot returns them and `resources_in_sync` compares (`kit/tracker/README.md`).
- **`storyline_approvers`.** The kickoff Page asks for the G0, G6 and G7 approvers only; add the `GX` and `unpark` approvers in the tenant `[BY HAND]` before the first escalation or park, or nobody can decide them on the Page. Because the kickoff submitter fills this Resource and any ops-team Editor can edit it, the `gate_decision` Page is restricted to an approvers SSO group where the tenant supports SSO group-based page access (§4.5 rule 2).
- **Locking** `storyline_approvers` and `storyline_state_machine` (`PUT /api/v1/global_resources/{id}/locked`) is optional and **off by default**: the docs say unlocking through the API is permanent, and what that means is **K40**. Once K40 is resolved, `storyline_approvers` is locked on tenants where the `gate_decision` Page cannot be restricted to an SSO group.
- **Missing Resource.** Whether a formula reading a Resource that does not exist yields null rather than an error is **K10** (A4, A7); if it errors, create an empty `kit_state` `[BY HAND]` before the first run.
- Never put a credential, token or webhook URL in any Resource. Names only.

## Kept current by `kit-sync.yml`

On every merge to `main`, in the GitHub environment `kit-sync` (an ops-team, team-scoped Editor key), `./scripts/kit sync-resources` takes the `storyline_sync_lock`, PUTs the whole value of `storyline_state_machine`, `kit_catalog` and `kit_config` (`PUT /api/v1/global_resources/{id}`; the body key is VERIFY), replaces the `storyline_limits` keys it owns (`…/replace`), writes `kit_state.hash_<name>`, releases the lock, and the workflow then runs `./scripts/tines skills-push --team <ops team id>`. The Resource ids come from the committed setup report (`created.resources[]`, `kit/tenant/README.md`).
