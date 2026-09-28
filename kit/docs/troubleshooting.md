# Troubleshooting — setup-report failures and their fixes

_Spec: REPO-DESIGN.md §7.2 (section A and its step keys), §7.3 (the probe), §6.5 (the tracker flows). The authority for the step keys is [`stories/kit-factory/sections/A-kickoff-and-provisioning.md`](../../stories/kit-factory/sections/A-kickoff-and-provisioning.md). When `[KIT] 00` itself pages the ops router after day 1, use the runbook in [`stories/kit-factory/README.md`](../../stories/kit-factory/README.md)._

## How to read the report

`kit/tenant/setup-report.json` (and the `setup_report` Page) has an overall `status`, one entry per step in `steps[]` and the `[BY HAND]` list.

| Overall `status` | Means | Do |
|---|---|---|
| `ok` | Every step is `ok`, `not_needed` or `exists` | Work through the `[BY HAND]` list ([`../ONBOARDING.md`](../ONBOARDING.md)) |
| `partial` | Some steps failed, none fatal | Fix each failed step below; explain any you leave (the day-1 milestone accepts `partial` with every failure explained) |
| `failed` | `step_repo`, `step_bundle` or the ledger failed | Fix it, then **submit the kickoff Page again**: the run resumes from its ledger (`kit_state`), skips every step already recorded, and never seeds Records twice |

Step statuses: `ok` · `failed` · `skipped` (the step did not run, usually because an earlier fatal step failed, or the input was a SKELETON) · `not_needed` (the entitlement is absent) · `exists` (something of that name was already there and was left alone) · `partial`. Each entry's `detail` is a sentence written for a person, never a raw response body.

A run that ends `failed` keeps `kit_state.status: running`, so submitting the Page again resumes it. A run that ended `ok` or `partial` is `complete`, and the Page will not run it again.

## The run stopped before any step (you got an email, no report)

| Email says | Cause | Fix |
|---|---|---|
| `status: error`, `error_category: input` | `is_valid_input` refused an answer. The message names each failed check and never echoes the value | The usual causes: an answer that **looks like a token** (never paste one; the Page asks for credential **names**); a tenant host that is not `<name>.tines.com`; a GitHub organisation or repository name with other characters; a template that is not `<owner>/<repo>`; a missing G0 approver; consent not ticked. Correct the answers and submit again |
| `status: not_supported` | The plan is Community Edition, or fewer than two licensed teams were entered | Follow [`community-path.md`](community-path.md). If the answer was wrong, submit again with the right one |
| `status: complete` | `kit_state.status` is already `complete`: the kit ran before | Nothing to fix. Read the existing `kit/tenant/setup-report.json`. After day 1, change the config by PR and let `kit-sync.yml` update the Resources and skills |
| "import [KIT] 00 into the prod team (the ops team) named on the Page" | The prod team name did not match a team exactly, or the story was imported into another team | Import the story into the prod team, or correct `prod_team_name` (exact match), and submit again. If the key cannot list teams at all, see VERIFY K41 |
| "could not create the kit_state ledger; nothing was provisioned" | Creating the `kit_state` Resource failed | Check that `tines_api_kit` is a valid **team-scoped Editor** key of the ops team and that its `allowed_hosts` includes the tenant host. If reading a missing Resource errors instead of returning null (VERIFY K10), create an empty `kit_state` Resource (`{}`) in the ops team by hand. Submit again |

## Step by step

| Step | Status | Likely cause | Fix |
|---|---|---|---|
| `step_teams` | `failed` | `GET /api/v1/teams` failed: the key is invalid or expired, or `allowed_hosts` blocks the tenant host; or a team-scoped key cannot list the other teams (VERIFY K41) | Fix the credential and submit again |
| `step_teams` | `partial` | The **dev** team name did not match | Builds need the dev team. Correct the name in Tines or add the dev team's name and id to `kit/tenant/config.yaml` by PR; `kit.yml` then fills the manifest |
| `step_providers` | `not_found` · `disabled` · `mismatch` · `unknown` | The provider for your `llm_choice` is not configured, is off, has another type, or the list call failed | Configure or confirm it in Settings → AI settings (no API), with the name you typed as `provider_name` ([`llm-provider-matrix.md`](llm-provider-matrix.md)). Not fatal |
| `step_github` | `failed` — "the token cannot read the template" | `github_factory` is missing, misnamed, expired or not yet approved by the organisation; its `allowed_hosts` is not `api.github.com`; or the template is private to another account | Fix the token ([`github-token.md`](github-token.md)); copy a private template into your organisation. Every GitHub and Tines step after it was skipped: submit again to resume |
| `step_repo` | `failed` — "a repository of that name already exists" | The name is taken, and it is not this run's own repository | Choose another `repo_name` and submit again. Deleting or renaming the existing repository is a person's decision, made in GitHub |
| `step_repo` | `failed` — "the repository did not become readable" | A generated repository is not readable at once (VERIFY K12) | Wait a few minutes and submit again; the run resumes at the repository it recorded |
| `step_repo` | `failed` at `create_org_repo` | `POST …/generate` was refused, and the fallback could not create the repository either: the token lacks the repository-creation permission, or the organisation's policy does not allow it (VERIFY K11) | Fix the token's permissions or the organisation policy; submit again |
| `step_repo` | `ok`, detail "copied with the Contents API" | Generation was refused and the fallback copied every file, one commit per file | Not a failure. Copy by hand every file the report lists as over 1 MB; a workflow file that failed with 403 needs the token's Workflows permission (VERIFY K11, K13, K33). Next time, make the template a template and use the generate path |
| `step_bundle` | `failed` | `kit/bundle/kit-bundle.json` is missing or unreadable in the **new** repository (an incomplete fallback copy; the raw media type, VERIFY K44) | Check that the file exists in the new repository and parses; copy it from the template if the fallback missed it; submit again. Sections B–E cannot be provisioned without it |
| `step_config` | `failed` | The config commit failed (a Contents API detail, VERIFY K13; the base64 formula, VERIFY K14) | Commit `kit/tenant/config.yaml` by hand from the report's values (a conditional `[BY HAND]` item) — never with a tenant host or an email in it |
| `step_skills` | `partial` with names `exists` | A skill of the same name was already in the ops team; the kit never overwrites a customer's skill | Decide per skill: keep yours (and attach it where the kit expects the kit's), or replace it with the kit's version by hand. Then attach the three runtime skills |
| `step_skills` | `partial` with names `failed` | The Skills API refused a skill: the key's scope (VERIFY K41) or a metadata key (VERIFY #14) | Fix, then let `kit-sync.yml` push the skills on the next merge to `main` |
| `step_record_types` | `failed` | The create body or its field keys (VERIFY K16), the key's scope (VERIFY K41), or the Records licence quota | On the **Starter** tier (5 types) the kit skips `sdlc_events` and says so; the ops trio's six types alone already exceed 5. Otherwise fix and submit again: types already created (`kit_state.rt_<name>`) are skipped. Seeding is skipped while this fails |
| `step_record_types` | `not_needed` | Records are not entitled | Expected. The tracker lives in git, with the `kit_tracker_view` Resource mirror |
| `step_resources` | `exists` | A Resource of that name was already in the ops team and was left alone (often one of the ops trio's four) | Compare it with its example in `kit/resources/` or `stories/ops-story-health-monitor/resources/`; fix it by hand if it differs |
| `step_resources` | `failed` | The key's scope (VERIFY K41) or a value over 5 MB | Fix and submit again; Resources already created (`kit_state.res_<name>`) are skipped |
| `step_seed` | `exists` | Another run already seeded the tracker (the `records_seeded` compare-and-swap) | Nothing to fix |
| `step_seed` | `failed` | A Records API create failed (field ids from VERIFY K16; live records in a change-controlled story, VERIFY K39) | The claim stays with this run, so a resume does not seed again. Add the missing use cases with the `add_use_case` Page or `./scripts/sdlc intake`; the two always-seeded rows reach Records from git through the tracker sync |
| `step_dashboard` | `skipped` — "the dashboard ships with the §15.6 release" | The bundle's dashboard export is still the SKELETON | Expected until the maintainer release. Build the Dashboard once by hand over the three Record types ([`../dashboard/README.md`](../dashboard/README.md)) |
| `step_dashboard` | `failed` | The import could not resolve a Record type by name (VERIFY K17) | Build it by hand, as above |
| `step_app` | `failed` | Apps not enabled for the ops team at `/settings/apps`; the plan's App limit (CONFLICT, VERIFY K19); the file push shape (VERIFY K18) | Enable Apps and submit again, or use the Pages dashboard. Publishing the App and wiring its three endpoints are always by hand |
| `step_app` | `not_needed` | Apps not entitled | Expected: the dashboard is the Pages plus the Tines Dashboard |
| `step_probe` | `failed` · `tool_calls_unreliable` · `not_entitled` | See the verdict table in [`llm-provider-matrix.md`](llm-provider-matrix.md); for a local model, [`llm-local-via-tunnel.md`](llm-local-via-tunnel.md) | Fix the provider and re-run the probe (`stories/kit-factory/sections/F-llm-probe.md`). `tool_calls_unreliable` is acceptable when acknowledged: keep tool-using agents on a foundation model |
| `step_report` | `failed` | Committing the report failed (VERIFY K13, K14) | Copy the report from the `setup_report` Page and commit it as `kit/tenant/setup-report.json` by hand; it carries no secrets. Its push runs `kit.yml` and opens the setup-report PR |

## After day 1

| Symptom | Likely cause | Fix |
|---|---|---|
| Every PR fails `bundle_fresh` in `sdlc` | The day-1 config commit changed `kit_config`, and the setup-report PR that regenerates the bundle has not merged | Merge the `kit/config-<run_id>` PR first, then rebase the others |
| No setup-report PR appeared | Actions was not enabled when the report was pushed, or Actions may not create pull requests (VERIFY K12), or the `tracker-bot` App is not installed | Fix the setting, install the App, then run `kit.yml` by hand |
| The `sdlc` check stays Pending on a tracker PR | The PR was opened with `GITHUB_TOKEN`, which starts no `pull_request` workflows | Tracker and kit PRs are opened with the `tracker-bot` App token; check its id and key in the `tracker` environment |
| No tracker PR ever appears | `TRACKER_OUTBOX_URL` is missing from the `tracker` environment, or it still holds the URL from before the secret was rotated | Copy the current `tracker_outbox` URL from the storyboard after rotating its secret |
| Merged changes never reach Records | `sdlc_limits.enabled` is still false (section B's kill switch also holds the sync), `TRACKER_SYNC_URL` is missing, or another sync held the lock | Set the flag once the guards are in place; check the URL; a sync that finds the lock busy skips, and the next push or the nightly run re-sends the full state |
| The runtime specialists never run | `sdlc_limits.enabled` or `guards_confirmed` is false; the daily count fails (VERIFY K35); on the Starter tier there is no `sdlc_events` to count | Check the flags; the specialists fail closed until the count works |
| Every Tines Stories MCP server call is denied | VERIFY K2 is not confirmed (`phase-gate.sh` then denies every call), the story's row on `origin/main` is not in `build`, or the caller is not `tines-builder` | Confirm K2; merge the design PR (G2) and run `./scripts/sdlc start <slug>`; build through `/tines-build-story` in the builder |
| `ship.yml` wants to create a second `[KIT] 00` | The setup-report PR, which records the kit's live id, has not merged | Merge it; `ship.yml` then changes the imported copy through `versionReplace` |

## Verify in your tenant before relying on it

The fixes above lean on these open items (`docs/VERIFY.md`): K8 (identifiers and secrets after import), K10 (a missing Resource reads as null), K11–K14 and K44 (GitHub and formula details), K16–K19 (Record types, Dashboard import, Apps), K33 (explode ordering and loops), K35 (the daily count), K39 (live Records), K41 (the Editor key's scope), and K2 (the phase gate).
