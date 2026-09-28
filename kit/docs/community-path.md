# The manual path — Community Edition, or one licensed team

_Spec: REPO-DESIGN.md §1.4 (supported plans), §4.5 and §6.5 (one instrument per gate), §7.1 (why `[KIT] 00` is not imported here), §9.1 (the no-Records dashboard), §10.3 ("Fallback", item 4). Everything marked VERIFY is in `docs/VERIFY.md`._

`[KIT] 00 · Run the story factory` is **not imported** on this path. You set up by hand what the kickoff Page would have provisioned, keep the tracker in git only, and run the same lifecycle from the editor. The repository, its scripts, its gates in git and its CI are the same as on the full path.

## Who is on this path

| Tenant | Why the kit story does not fit |
|---|---|
| **Community Edition** | No Records and no Dashboards; 3 flows and 50 AI credits a month. `[KIT] 00` needs about 5–8 flows (VERIFY K30) and three Record types. Whether the AI Agent action is available on Community is a CONFLICT (VERIFY K7) |
| **Business or Enterprise with one licensed team** | The kit needs a dev team to build in and a prod team (the ops team) to ship to. With one team, the lifecycle's dev/prod split cannot hold. The kit's recommendation is a second licensed team; teams are an add-on |

The kickoff Page sends both to this page (`is_community`: `plan_tier == community_edition`, or fewer than two licensed teams).

## What you get and what you do not

| | Full path | This path |
|---|---|---|
| The lifecycle (`sdlc/`), its specialists and `./scripts/sdlc` | yes | **yes**, unchanged |
| Build through Mode 2, review, ship through change control, roll back | yes | **yes**, where the plan has change control (the scaffold's `ship.yml`, `promote.yml`, `rollback.yml`) |
| The tracker | git + Records, kept in sync | **git only**: `kit/tracker/backlog.yaml` and `milestones.yaml` |
| Tines-side gates (G0, G6, G7, GB release, GX) | the `gate_decision` Page | **`/sdlc-gate <slug> <gate> <decision>`**, run by a person |
| Intake briefs | drafted by `brief_writer` in Tines | the orchestrator fills `sdlc/templates/intake-brief.md` with the owner |
| Planner proposals, retro drafts | `planner`, `retro_writer` in Tines | none; the owner writes the retro from `sdlc/templates/retro.md` |
| Improve triggers | detected by `[KIT] 00` section D | recorded by a person: `./scripts/sdlc advance <slug> --trigger …` |
| Dashboard | App, or Pages, plus a Tines Dashboard | `kit/tracker/*.yaml` in GitHub |
| The ops trio (router and sweep) | yes | **no** on Community Edition: the router needs Records, and the sweep needs Records and the AI Agent action |
| Setup report | yes | none |

## Set it up

### 1. The repository

1. Create a **private** repository in your GitHub organisation from the template repository (GitHub's template feature, or a copy of the template). Keep it private or internal: exports carry Webhook paths and secrets.
2. Copy `kit/tenant/config.example.yaml` to **`kit/tenant/config.yaml`** and fill it in:
   - `plan.tier: community_edition` (or `business` / `enterprise`), `plan.licensed_teams`, `plan.self_hosted`;
   - `entitlements` — what you actually have. On Community Edition, `records: false`;
   - `records_tier: ""` when there are no Records;
   - `teams` — the names (and ids, when known) of your team or teams;
   - `llm` — your Tines-side model choice ([`llm-provider-matrix.md`](llm-provider-matrix.md)), if an AI Agent action is available at all;
   - `github.org` and `github.repo`; `provisioned_at` — now, in UTC with `Z`; `kit_run` — any placeholder, for example `manual`.

   Never put the tenant host, an email address, a token or a webhook URL in it. Commit it to `main` while the repository is still new (branch protection comes next), or by PR.
3. **Run `kit.yml`** on that push (or from Actions → Run workflow). `./scripts/kit apply-config` opens two PRs: team ids into `stories/_manifest.yaml`, `policies/never-touch.yml` and `policies/cost-ceilings.yml`; and the milestones' due dates and the backlog's target dates, counted from `provisioned_at`. It fills placeholders only. The PRs are opened with the `tracker-bot` GitHub App (step 2 below). Merge the first one first.

### 2. GitHub

The same as the full path, minus the kit story's parts:

- Branch protection on `main`: require the one check `sdlc`, a CODEOWNERS review, no self-merge.
- Replace `<org>` in `.github/CODEOWNERS` and the teams in `sdlc/gates/approvers.yaml`.
- The GitHub environments the scaffold's workflows use (`production` with required reviewers, `prod-read`, `break-glass` and `break-glass-2`), and the `tracker` environment holding **only** the `tracker-bot` App's id and private key. There are no tracker webhook URLs on this path: `tracker-sync.yml` validates the tracker and stops with a notice, and `tracker-pull.yml` has nothing to pull.
- The `tracker-bot` GitHub App on this repository only, and "Allow GitHub Actions to create pull requests".
- Optionally `ANTHROPIC_API_KEY`, so `sdlc.yml` calls `review.yml`'s independent reviewer.

### 3. Tines

- Change control on, where the plan has it: tenant policies "Enable by default" and "Require approval for all changes".
- Builders' Tines accounts: where there are two teams, a Viewer, or not a member, in the prod team.
- Credentials and Resources by **name**, in every team a story is deployed to, before its build.
- The Tines Agent Skills matter only where an AI Agent action or Workbench runs; `skills.yml` pushes `tines-skills/**` on merge, as in the scaffold.
- **Watch the flow budget.** On Community Edition every story you build counts against 3 flows (how flows are counted is VERIFY #13 and K30). Pick stories accordingly; the starter stories without an AI Agent action (`kit/catalog/starter-stories.yaml`, estimate 0 credits) are the natural first ones.

### 4. The editor

Each builder runs `/tines-connect` and checks VERIFY K2 before the first build, exactly as on the full path ([`../ONBOARDING.md`](../ONBOARDING.md), day 1 steps 5–6).

## Run the lifecycle

The commands are the full path's, with two differences: every Tines-side gate is recorded with `/sdlc-gate`, and nothing arrives from Tines by tracker PR.

1. **Add a story:** `./scripts/sdlc intake "<title>" --use-case <file> --owner <role> [--seed <id>]` — a new row in intake and `intake.md` from the template, on a `tracker/intake-<slug>` branch. Seed ids come only from `kit/catalog/library-seeds.yaml`.
2. **Write the brief:** `/sdlc <slug> run` stops with the note to fill `sdlc/templates/intake-brief.md` with the owner. The orchestrator drafts it in the chat; the owner writes it into `sdlc/work/<slug>/intake.md` on the same branch (the model's Write and Edit are denied on `sdlc/work/**`). When every field is set, `./scripts/sdlc advance <slug>` opens G0.
3. **Decide G0:** the owner or a G0 approver runs `/sdlc-gate <slug> G0 build` (or `reject`, or `park`). The command asks for a confirmation on the terminal, which a model cannot give, and records the decision with the decider's role on a `tracker/<slug>-G0` branch; that PR needs an approving review from the team `sdlc/gates/approvers.yaml` lists for G0.
4. **Discover, design, build, verify, ship** exactly as on the full path ([`../../docs/09-lifecycle-walkthrough.md`](../../docs/09-lifecycle-walkthrough.md)).
5. **Operate:** without the ops trio on Community Edition, a production story's monitoring is its story-level "Notify when any action fails" to the ops email list. Record an improve trigger yourself: `./scripts/sdlc advance <slug> --trigger high_finding | credit_variance | retro_due | owner_request | eval_regression [--note "…"]`.
6. **Go-live, ownership, budget and escalation gates:** `/sdlc-gate <slug> G6 go_live`, `G7 keep | rescope | retire`, `GB unpark`, `GX resume | park | reject`.

The template's backlog also carries a `kit-factory` row, which the maintainers use to build the kit story itself. On this path there is no kit story to build: leave the row alone.

## Recording the milestones

The day-1, week-1 and week-4 milestones in `kit/tracker/milestones.yaml` apply here too, minus the criteria about Record types, Resources, the provider probe and the ops sweep that your plan does not have. No `./scripts/kit` or `./scripts/sdlc` subcommand sets a milestone's status; keep the checklists in [`../ONBOARDING.md`](../ONBOARDING.md) in the onboarding issue or PR.

## One licensed team with Records: a known gap

`./scripts/sdlc` chooses the gate instrument from `kit/tenant/config.yaml`: the manual path is `plan.tier: community_edition` or `entitlements.records: false`. A Business or Enterprise tenant with **one** licensed team **and** Records is therefore treated as the full path — `/sdlc-gate` refuses G0, G6, G7, GB and GX there — while the `gate_decision` Page does not exist, because `[KIT] 00` is not imported. Until the scripts also read `plan.licensed_teams`, such a tenant has no instrument for those gates. Raise it with the kit's maintainers before starting a story; the kit's own recommendation for this tenant is a second licensed team and the full path.

## A local model

Community Edition has no Tunnel, so there is no private local-model path. A publicly reachable model endpoint is technically possible and not recommended ([`llm-local-via-tunnel.md`](llm-local-via-tunnel.md)).

## Verify in your tenant before relying on it

| Item | What is assumed |
|---|---|
| K7 | Whether the AI Agent action is available on Community (CONFLICT), and whether importing a story with AI Agent actions fails on a plan without them |
| K20 | Whether custom AI providers are available on Community (CONFLICT) |
| K30 · #13 | How flows are counted, for your plan's flow allowance |
| K2 | Whether a hook can tell which subagent is calling; until confirmed, `phase-gate.sh` denies every `/mcp` call |
