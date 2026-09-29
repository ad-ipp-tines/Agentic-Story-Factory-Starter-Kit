# Onboarding runbook — day 1, week 1, week 4

_Spec: REPO-DESIGN.md §11.1 (the milestones), §7.1–§7.2 (the import and the `[BY HAND]` list), §4 (the lifecycle). This runbook mirrors [`tracker/milestones.yaml`](tracker/milestones.yaml) criterion by criterion; change the two together, by PR. Owners are roles, never people._

Three milestones, counted from the moment the kit provisions the tenant:

| Milestone | Due | In one line |
|---|---|---|
| **day-1** | provisioned + 1 day | Storyworks is provisioned and safe to build in |
| **week-1** | provisioned + 7 days | The first stories are live and the tracker round trip works |
| **week-4** | provisioned + 28 days | The lifecycle runs end to end, including improve |

On the manual path (Community Edition, or one licensed team) there is no kit story: follow [`docs/community-path.md`](docs/community-path.md) for day 1, then use the week-1 and week-4 sections below without the Tines-side steps.

## Who does what

| Role | Owns in this runbook |
|---|---|
| **onboarding engineer** (vendor or partner side) | Runs day 1 with the customer; owns the template repository and its maintainer release |
| **platform** (customer) | The kit story, the tracker, the milestones; the Tines-side `[BY HAND]` items; the two runtime-crew-member flags |
| **security-platform** (customer) | Reviews identities, gates and data paths before the first build (`policies/POLICY.md`); CODEOWNER of `policies/`, `.claude/`, `.github/`, `kit/`, `stories/kit-*`; a required reviewer of the GitHub `production` environment (G5a) |
| **story owners** (for example security-automation, ops) | Decide G0 for their stories; drive their builds; complete their retros |
| **gate approvers** | Decide G0, G6 and G7 on the `gate_decision` Page (emails held only in the `storyline_approvers` Resource) |
| **builders** | Build through Mode 2 in the dev team; a Viewer, or not a member, in the prod (ops) team |

## Before day 1

Settle these before anyone submits the kickoff Page.

- [ ] **Plan and path.** Business or Enterprise with two licensed teams → this runbook. Community Edition, or one licensed team → [`docs/community-path.md`](docs/community-path.md). Note which of Records, Apps, the AI Agent action, change control and the Tunnel were purchased, and the Records licence tier; the Page asks for each and the kit never assumes one.
- [ ] **Two standard teams**, dev and prod, never personal teams (the AI Agent action is unavailable in personal teams). The prod team is the ops team: `[KIT] 00`, the ops trio, their Record types and Resources all live there.
- [ ] **The template is published** — the maintainer release has replaced the SKELETON `stories/kit-launch/story.json` and passed the release check, and the template repository is marked as a template. If the template is private, copy it into your organisation first; the provisioning token must be able to read it.
- [ ] **The provisioning token** is created and stored in the ops team as the credential `github_factory` ([`docs/github-token.md`](docs/github-token.md)).
- [ ] **The other credentials** exist in the ops team: `tines_api_kit` (team-scoped Editor key), `tines_api_readonly` (Viewer key), and `slack_bot` if the chat surface is Slack. Each has `allowed_hosts` set and Workbench access off.
- [ ] **The ops trio's six Record types** exist in the ops team (`stories/ops-story-health-monitor/records/record-types.md`).
- [ ] **The model provider** is configured in Settings → AI settings if it is not the Tines-provided default ([`docs/llm-provider-matrix.md`](docs/llm-provider-matrix.md)); for a local model, the Tunnel is enabled and accessible by all teams ([`docs/llm-local-via-tunnel.md`](docs/llm-local-via-tunnel.md)).
- [ ] **The answers for the Page:** the company name, the tenant host, the two team names, the GitHub organisation and the repository name, the chat surface, the gate approvers for G0, G6 and G7, and up to ten use cases — starter stories from [`catalog/starter-stories.yaml`](catalog/starter-stories.yaml) or your own.

## Day 1 — Storyworks is provisioned and safe to build in

### Steps

1. **Import and submit.** Follow "The one import" in [`README.md`](README.md): import `[KIT] 00` into the ops team, open the `kickoff` Page on the **LIVE** story, submit it.
2. **Read the setup report** (the emailed link, and `kit/tenant/setup-report.json` in the new repository). For each failed step, [`docs/troubleshooting.md`](docs/troubleshooting.md). Submitting the Page again resumes a partial run from its ledger and never seeds Records twice.
3. **Merge the setup-report PR first** — the PR from `kit/config-<run_id>`, which records the kit's live story id in `stories/_manifest.yaml` and `policies/never-touch.yml`. Until it merges, every other PR fails the bundle check. If Actions was not enabled when the report was pushed, run `kit.yml` by hand (Actions → Run workflow), then merge.
4. **Work through the `[BY HAND]` list** in the report, in this order:
   1. **Tines side:** `allowed_hosts` on both credentials · confirm the AI provider · token alerts on the five kit AI Agent actions (Status tab: Notify, then Disable action, at the numbers in `policies/cost-ceilings.yml`) · attach the three skills to `planner`, `brief_writer` and `retro_writer` and pin the fast model on each · resolve any skill reported `exists` · the ops team's AI credit allocation and credit alerts · change-control policies "Enable by default" and "Require approval for all changes" · Apps (enable, publish, wire the three endpoints), if entitled.
   2. **People and access:** every builder is a Viewer, or not a member, in the prod (ops) team · SSO group-based page access for the `gate_decision` Page where the tenant has it · the GX and unpark approvers added to `storyline_approvers`.
   3. **GitHub:** branch protection on `main` (require the one check `storyline`, a CODEOWNERS review, no self-merge) · replace `<org>` in `.github/CODEOWNERS` and the teams in `storyline/gates/approvers.yaml`, by PR · the `tracker-bot` GitHub App on this repository only (contents and pull requests, write) · the environments `production` (required reviewers — G5a depends on them: the G5a team in `storyline/gates/approvers.yaml`, no individuals), `prod-read`, `break-glass` and `break-glass-2`, `tracker` (the two webhook URLs and the `tracker-bot` App id and private key), `kit-sync` (an ops-team Editor key), `review` (`ANTHROPIC_API_KEY`) if you run the headless review, and `storyline-evals` (a dev-team key) with `storyline-evals-ide` (`ANTHROPIC_API_KEY`, required reviewers) if you run the crew's evals — every secret as an environment secret, never a repository secret · Actions allowed to create pull requests · the pull-request labels `tracker`, `tracker-drift` and `kit-config` (`tracker-pull.yml` and `kit.yml` apply them but never create them) · Actions enabled on the repository. `scripts/README.md` ("GitHub configuration checklist") lists each environment's secrets by name.
   4. **Tracker webhooks:** rotate the secrets of `tracker_sync_in`, `tracker_outbox` and the three App endpoint Webhooks first (an import may keep the template's values, VERIFY K8), then copy the two tracker URLs into the `tracker` environment.
   5. **The ops trio's type ids:** add `ops_findings` and `ops_alerts` under `ops_record_types` in `kit/tenant/config.yaml`, by PR.
   6. **Revoke the provisioning token** in GitHub, or confirm it expires within days.
5. **Connect the editors.** Each builder runs `/tines-connect`. In Claude Code that completes the OAuth consent in a `claude --agent tines-builder` session; in Cursor it adds the server to the project `.cursor/mcp.json` of a separate build-only worktree that opens only the builder chat, never to the global MCP configuration.
6. **Check K2 before the first build.** Whether a PreToolUse hook can tell which subagent is calling is VERIFY K2. Until it is confirmed, `phase-gate.sh` denies every Tines Stories MCP server call, which is safe and stops every build. Log the hook input once in a test session and record the result in `docs/VERIFY.md`.
7. **Turn the runtime crew on.** Only after the token alerts are set and the skills attached: set `storyline_limits.guards_confirmed` and then `storyline_limits.enabled` to true on the Resource. Until then no AI Agent action in the kit runs, and section B's kill switch also holds the tracker sync.
8. **Bring the Page's picks into git.** Run `tracker-pull.yml` once (Actions → Run workflow) and merge the tracker PR it opens: the seeded rows and milestones reach `kit/tracker/`.
9. **Take story #1 through G0 and discovery.** `brief_writer` drafts the intake brief for `example-enrich-ip` (or, without the AI Agent action, the showrunner fills `storyline/templates/intake-brief.md` with the owner); the brief reaches git by tracker PR; the owner decides G0 on the `gate_decision` Page; that decision reaches git by the next tracker PR. Then `/storyline example-enrich-ip run` dispatches `story-scout`, and `discovery_complete` moves the story to design. [`../docs/09-lifecycle-walkthrough.md`](../docs/09-lifecycle-walkthrough.md) walks every command.

### Day-1 exit criteria

| Criterion (`milestones.yaml`) | Evidence to link |
|---|---|
| The setup report is ok, or partial with every failure explained | `kit/tenant/setup-report.json` on `main`; a note per failed step |
| The repository and the tenant config commit exist | the repository; `kit/tenant/config.yaml` on `main` |
| The Tines Agent Skills are pushed | the report's `created.skills[]`; no `exists` left unresolved |
| The Record types and Resources exist, including the ops trio's six Record types | the report's `created.record_types[]` and `created.resources[]`; the six ops types in the ops team |
| The provider probe is ok, or `tool_calls_unreliable` is acknowledged | the report's `provider.status`; for `tool_calls_unreliable`, a note that tool-using agents stay on a foundation model |
| `/tines-connect` works in at least one editor | the smoke prompt's answer in a builder session |
| K2 is confirmed, or `phase-gate.sh` is known to deny all `/mcp` calls until it is | the K2 row in `docs/VERIFY.md` |
| Team memberships are checked: no builder account holds an Editor or Admin role in the prod (ops) team | the prod team's member list, checked by security-platform |
| Story #1 has passed G0 and discovery | `storyline/work/example-enrich-ip/discovery.md` on `main`; the G0 `gate_decision` event |
| Branch protection, CODEOWNERS and the GitHub environments are set | the branch protection settings; the CODEOWNERS PR |
| The provisioning token is revoked or expiring | the token's expiry date or revocation in GitHub |

## Week 1 — the first stories are live and the tracker round trip works

### Steps

1. **Ship story #1** (`example-enrich-ip`) through design (G1, G2), build (G3), verify (G4) and its first ship (G5a), exactly as [`../docs/09-lifecycle-walkthrough.md`](../docs/09-lifecycle-walkthrough.md) shows. Create its credentials (`virustotal_api`, `abuseipdb_api`), the `never_block` Resource and the `ioc_cache` Record type in the dev and prod teams under the same names before its build and before its ship.
2. **Ship story #2** (`ops-error-router`) through the same lifecycle. Once it is live, put its webhook URL in the `OPS_ROUTER_URL` secret of the GitHub environments that ship, so `ship.yml` makes it every production story's monitoring recipient.
3. **Ship `[OPS] 10`** (`ops-story-health-monitor`), the ops sweep, through the lifecycle. It was seeded in every backlog because operate and improve depend on it: its `ops_findings` rows are the retros' evidence.
4. **Prove the tracker round trip:** a G0 decided on the `gate_decision` Page reached `main` through a tracker PR a person merged — story #1's G0 is the proof.
5. **Enable `review.yml`**: the secret `ANTHROPIC_API_KEY` in the GitHub environment `review` (never a repository secret), so `storyline.yml` calls the independent reviewer on story PRs.
6. **Check the kit's token alerts** are set on all five AI Agent actions (a week-1 criterion even if you set them on day 1: record where).
7. **Start the next two or three stories** from the backlog; the `planner`'s proposals on the Page or in the App suggest an order, which a person accepts or rejects.

### Week-1 exit criteria

| Criterion (`milestones.yaml`) | Evidence to link |
|---|---|
| Story #1 is live through G5 | `storyline/work/example-enrich-ip/ship.md` on `main`; the row in `operate` |
| Story #2 is live and is every production story's recipient | its `ship.md`; `OPS_ROUTER_URL` set; a production story's recipients |
| `[OPS] 10`, the ops sweep, is live | its `ship.md`; its first sweep runs |
| The tracker round trip is proven: a Tines-side G0 reached `main` by PR | the merged tracker PR carrying the G0 `gate_decision` event |
| `review.yml` runs (called by `storyline.yml`) | a story PR's checks |
| Token alerts are set on the kit's agents | the five actions' Status tabs; `stories/kit-launch/story.meta.yaml` `token_alert` values |
| Two or three more stories are in design or build | `kit/tracker/backlog.yaml` |

## Week 4 — the lifecycle runs end to end, including improve

### Steps

1. **Ship at least one `mode-3-agent` story** (for example starter story #7) with an output schema, a Trigger on schema fields after the agent, a token alert, an attached skill and a budget line in `policies/cost-ceilings.yml`. The lifecycle's checks refuse it without them: G1 and `lint.yml` want the budget line, the cost checks the pinned or smart-model estimate, and the reviewers the schema, the Trigger and the token alert.
2. **Let the ops sweep build baselines** for every production story. It proposes each story's watchdog value from that baseline; a person approves the proposal, and only then is it applied.
3. **Close the first retro.** When a story's improve trigger fires (a retro is due seven days after it went live), `retro_writer` drafts `retro.md`, the owner completes it, `eval-curator` turns the failure modes into eval cases, and at least one stable capability case graduates to regression ([`../storyline/evals/regression/README.md`](../storyline/evals/regression/README.md)).
4. **Ship one skill change through `skills.yml`**: a `skill-curator` proposal or a person's edit to `tines-skills/**`, with its held-out cases file in `storyline/evals/skills/`, reviewed and merged.
5. **Use the dashboard** — the App, the Pages or the Tines Dashboard, by entitlement ([`dashboard/README.md`](dashboard/README.md)). While the dashboard export is still the SKELETON, A23 skipped the import: build it once by hand over the three Record types.
6. **Review credits against estimates:** `./scripts/storyline estimate <slug>` per story against actual AI usage (the scaffold's `drift.yml` budget job, the App's Costs view); an improve trigger fires above 1.5 × the estimate.
7. **Set the G7 dates:** a quarterly ownership review per live story.

### Week-4 exit criteria

| Criterion (`milestones.yaml`) | Evidence to link |
|---|---|
| At least 3 stories are live, including one mode-3-agent with an output schema, a Trigger, a token alert, a skill and a budget line | the rows in `operate`; that story's `design.md` contract and `story.meta.yaml` |
| The ops sweep is running with baselines | `ops_baselines` Records for the live stories |
| The first retro is closed and at least one eval case has graduated to regression | `storyline/work/<slug>/retro.md` (`closed: true`); `evals/cases.yaml` |
| One skill change has shipped via `skills.yml` | the merged skill PR and its `skills.yml` run |
| The dashboard is in use | the App, Page or Dashboard in the ops team |
| Credits have been reviewed against estimates | a note with each story's estimate and actual |
| G7 dates are set | the owners' calendar entries or the tracker's target dates |

## Recording progress

- **With Records:** edit the milestone's `storyline_milestones` Record in the ops team — `status` (`not_started`, `in_progress`, `done`, `blocked`), `evidence_ref`, and `pending_repo_sync` set to true so the outbox includes it. The change reaches `kit/tracker/milestones.yaml` through the next tracker PR. `title` and `criteria` change only in git, by PR, together with this runbook.
- **On the manual path:** the milestones live in git only, and no `./scripts/kit` or `./scripts/storyline` subcommand sets a milestone's status. Keep this runbook's checklists in the onboarding issue or PR until one exists.

## When something goes wrong

- A setup-report step failed: [`docs/troubleshooting.md`](docs/troubleshooting.md).
- The router pages for `[KIT] 00`: the runbook in [`../stories/kit-launch/README.md`](../stories/kit-launch/README.md).
- A story is stuck at a gate or in rework: `./scripts/storyline status <slug>` and `./scripts/storyline next <slug>`; the gate's own file in [`../storyline/gates/`](../storyline/gates/README.md).
- Stop the runtime crew at once: set `storyline_limits.enabled` to false. Stop the ops sweep: `ops_limits.enabled`.
