# 09 · One story through the lifecycle — intake to improve

_Tines Storyworks Starter Kit · docs v1 (2026-09-27) · Matches `REPO-DESIGN.md` §4 (phases and gates), §5 (crew), §6 (orchestration and state) · The worked example is [`../storyline/examples/example-enrich-ip/`](../storyline/examples/example-enrich-ip/intake.md). Anything not confirmed is marked VERIFY and listed in [`VERIFY.md`](VERIFY.md)._

This page follows one story — the scaffold's example, `[SEC] 01 · Enrich IP (sub)` — through every phase and every gate, with the commands a person runs, what the crew and the scripts do, and the file each step leaves behind. The worked example is **illustrative**: every id is `0`, every commit is `0000000`, and every time, count and credit figure is a placeholder; it shows the shape of a real run, not a claim about how a tenant behaved. In a customer repository the same files land in `storyline/work/example-enrich-ip/`; the example lives in `storyline/examples/` so a real story #1 starts from clean templates.

## The story

| | |
|---|---|
| Key (slug) | `example-enrich-ip` |
| Title | `[SEC] 01 · Enrich IP (sub)` |
| What it does | Takes one IPv4 address, refuses protected ranges before any lookup, answers from a 24-hour cache when it can, otherwise asks two reputation services, and returns one verdict |
| Mode | `sub-story` (a Send to Story sub-story; no AI Agent action) |
| Owner · tier | security-automation · production |
| Library seed | 87626, from `kit/catalog/library-seeds.yaml` |

## The map

| # | Phase | Who does the work | Gate out | Instrument | File it leaves | Example |
|---|---|---|---|---|---|---|
| 00 | intake | `brief_writer` in Tines | **G0** (human) | the `gate_decision` Page | [`intake.md`](../storyline/examples/example-enrich-ip/intake.md) | G0 `build`, 2026-10-01 |
| 01 | discover | `story-scout` | check `discovery_complete` | `./scripts/storyline advance` | [`discovery.md`](../storyline/examples/example-enrich-ip/discovery.md) | reuse seed 87626 |
| 02 | design | `story-architect`, `eval-author` | **G1** (code), then **G2** (human) | `./scripts/storyline ready`; the design PR's merge | [`design.md`](../storyline/examples/example-enrich-ip/design.md), [`evals/cases.yaml`](../storyline/examples/example-enrich-ip/evals/cases.yaml) | merged 2026-10-02 |
| 03 | build | `tines-builder` (Mode 2, dev team) | **G3** inside (human); check `build_evidence` out | `/storyline-gate … G3 approve` | [`build-log.md`](../storyline/examples/example-enrich-ip/build-log.md) | two attempts |
| 04 | verify | `tines-reviewer`, `security-reviewer`, `story-qa`, the cost script | **G4** (code + model + human) | the build PR's merge | [`verify-report.json`](../storyline/examples/example-enrich-ip/verify-report.json) | rework once, then pass |
| 05 | ship | CI only | **G5a** (first ship, human in GitHub) | the `production` environment's reviewer | [`ship.md`](../storyline/examples/example-enrich-ip/ship.md) | live 2026-10-06 |
| 06 | operate | the ops trio | G6 (not needed here) · G7 (quarterly) | the `gate_decision` Page | — | no shadow |
| 07 | improve | `retro_writer` in Tines, `eval-curator` | check `change_needed` | `./scripts/storyline advance` | [`retro.md`](../storyline/examples/example-enrich-ip/retro.md) | iteration 2 opens |

Beside them all: [`events.jsonl`](../storyline/examples/example-enrich-ip/events.jsonl) — 32 typed, append-only events, one per write. Read it alongside this page.

## Before you start

- The kit has provisioned the tenant and the day-1 `[BY HAND]` list is done ([`../kit/ONBOARDING.md`](../kit/ONBOARDING.md)). On Community Edition or with one licensed team, read [`../kit/docs/community-path.md`](../kit/docs/community-path.md) first; the differences are called out below.
- `/tines-connect` works for the builder. **VERIFY K2 is confirmed** — until a hook can tell which subagent is calling, `phase-gate.sh` denies every Tines Stories MCP server call, so no build can start.
- You know the three permission levels: `./scripts/storyline status | next | ready | estimate | check` run freely; `start | intake | apply | advance | eval-run` **ask you first**; `gate` runs only through the human-only `/storyline-gate` and asks for a confirmation on your terminal.
- At any point, `./scripts/storyline status example-enrich-ip` prints the phase, status, open gate, attempt and last event, and `./scripts/storyline next example-enrich-ip` prints what runs next. In Claude Code, `/storyline example-enrich-ip run` loops through `next` for you and stops at every human gate. In Cursor, run `./scripts/storyline next example-enrich-ip --print-prompt`, open a new chat per crew member, @-mention its `storyline-<name>.mdc` rule and paste the prompt.

## 00 · intake → G0

**What happens.** The kickoff Page offered starter story #1, and `[KIT] 00` seeded its `storyline_backlog` row in **intake** with `specialist_due: brief-writer` (event 1, `actor_kind: story`). Once a person has switched the runtime crew on, section D's dispatch runs **`brief_writer`** — a tool-less AI Agent action — on the use case, the entitlements and the catalog. A Trigger drops any seed id not in the catalog (87626 is kept), the brief is rendered to Markdown, the row's open gate becomes **G0**, and the G0 approver is notified (event 2). The next `tracker-pull.yml` run opens a tracker PR that writes `intake.md`; a person merges it.

**G0 — intake triage (human).** The story owner opens the `gate_decision` Page, picks the story, the gate `G0` and the decision `build` (the other choices are `reject` and `park`), and notes that IPv6 is out of scope for iteration 1. The Page checks the submitter's email against the `storyline_approvers` Resource, writes the decision to the row as provisional, and logs it. The next tracker PR carries the `gate_decision` event into git (event 3, `actor_kind: human`); merging it is what makes G0 true in git.

**You run:** nothing in the editor. Merge the two tracker PRs.

**Community path.** No Records, so no `brief_writer` and no Page. `./scripts/storyline intake "Enrich IP" --use-case <file> --owner security-automation --seed 87626` opens the row on a `tracker/intake-<slug>` branch; the showrunner drafts the brief with the owner from `storyline/templates/intake-brief.md`, the owner writes it into `intake.md`, `./scripts/storyline advance example-enrich-ip` opens G0, and the owner runs `/storyline-gate example-enrich-ip G0 build`. Each Tines-side gate has exactly one instrument: the Page with Records, `/storyline-gate` without.

## 01 · discover → `discovery_complete`

**You run:**

```bash
git switch -c design/example-enrich-ip        # discover and design share this branch
/storyline example-enrich-ip run                   # Claude Code; or ./scripts/storyline next … --print-prompt in Cursor
```

**What happens.** `./scripts/storyline next` reads the state machine and `storyline/lifecycle/dispatch-rules.yaml` and names **`story-scout`**. The showrunner renders its handoff prompt (the input baton with paths, the touch set, `max_turns`) and spawns it in a fresh context. The scout checks three places — the Story Library (only ids in the catalog; the catalog ids' own pages confirmed with WebFetch, VERIFY K43), the stories in this repository, and the published stories in the dev team — and returns one output baton. The showrunner pipes it into `./scripts/storyline apply example-enrich-ip story-scout -` (it asks), which validates the baton and payload, checks that every file is inside the discover touch set, writes `discovery.md`, appends the event and bumps the tracker row (event 4).

The result: three candidates (seed 87626 high, the repository's own design high, seed 1252750 medium) and `reuse_decision: import_seed 87626` — read the seed, build from the repository's design. The `[BY HAND]` list says to import 87626 into the dev team's Seeds folder (the Tines Stories MCP server cannot import from the Library) and to create `virustotal_api`, `abuseipdb_api`, the `never_block` Resource and the `ioc_cache` Record type in both teams.

**Exit.** `/storyline` proposes `./scripts/storyline advance example-enrich-ip` (it asks). The check `discovery_complete` passes — `discovery.md` exists, a reuse decision is set, every cited id is in the catalog — and the story moves to **design** (event 5). There is no human gate: discovery only informs design, which has one.

## 02 · design → G1, then G2

**What happens.** `next` names **`story-architect`**. It writes `design.md` from the template: the rung it chose (2, a Send to Story sub-story) and why rung 1 fails, the risks, the cost (0 credits: no AI Agent action) and **one fenced JSON contract block** — five acceptance criteria, the entry, the action outline, credentials and Resources by name, egress hosts, access levels, `risk.side_effects: false`, out-of-scope items, the touch set, the cost estimate from `./scripts/storyline estimate`, and guidance for QA. It also drafts `stories/example-enrich-ip/README.md` and `story.meta.yaml`, and allow-listed patches: the manifest entry with `new: true`, and the tracker row. `apply` writes them (event 6). Then `next` names **`eval-author`**, which maps every acceptance criterion to at least one case — four deterministic cases, two of them should-not cases — in `evals/cases.yaml` and the story's `tests/` (event 7). **Evals are written before anything is built.**

**G1 — readiness (code).** With every design artifact present, `next` returns the gate G1, and `/storyline` runs:

```bash
./scripts/storyline ready example-enrich-ip        # one PASS/FAIL line per check; exit 0 or 1
./scripts/storyline advance example-enrich-ip      # design → build, written on this branch (it asks)
gh pr create                                  # the design PR, with the template's Lifecycle section (it asks)
```

`ready` checks that the contract validates, every criterion has a case and there is a should-not case, credentials and Resources are named in the meta, every AI Agent action has a budget line (none here), the manifest has the entry, the needs fit the tenant's entitlements, the touch set is respected, the cost checks pass (`./scripts/storyline estimate --check`), and the budget gate passes.

**G2 — design approval (human).** The design PR's Lifecycle section says: phase `design`, gate `G2 design approval`, rework attempt `0/3`. `storyline.yml`, the one required check, runs `storyline ready` again, the touch set for a `design/` branch, the tracker row's `rev` (main's + 1) and the append-only event log. A CODEOWNER of the story's prefix who is **not** the author reviews the contract, the evals, the meta and the budget line, and merges. **That merge is G2**: the tracker change to `build` rode in the PR, so the state changes exactly when a person approves it (event 8, tracker rev 3).

If a VERIFY item had blocked a design decision, the architect would have proposed a **spike** (`storyline/templates/spike.md`) in a scratch team first. None did here.

## 03 · build → G3 inside, `build_evidence` out

**You run:**

```bash
git switch main && git pull
./scripts/storyline start example-enrich-ip        # writes .storyline/active and the build start event (it asks)
/storyline example-enrich-ip run
```

**What happens.** `phase-gate.sh` now lets the Tines Stories MCP server through — but only for `tines-builder`, only for this story's dev id, and only because the row on `origin/main` is in `build` (it reads `main`, never the working tree, and the model's Write and Edit are denied on the tracker). `next` names **`tines-builder`** with the `build-from-contract` handoff, and the lead invokes the scaffold's own skill in the builder:

```text
/tines-build-story example-enrich-ip "Implement the contract in storyline/work/example-enrich-ip/design.md (contract v1). Acceptance = stories/example-enrich-ip/tests/expectations.yaml and the deterministic cases in storyline/work/example-enrich-ip/evals/cases.yaml. Out of scope: … Credentials by name: virustotal_api, abuseipdb_api."
```

The builder runs its unchanged loop in the **dev team**: explore → **plan** → implement → Validate → test event → `[BY HAND]` list → `/tines-export` → commit on `story/example-enrich-ip/<short>`. The story is new, so it gets its dev id here, recorded in `stories/_manifest.yaml`.

**G3 — plan approval (human, inside build).** The builder stops with a numbered plan: 16 actions (type, name, fields) and the canvas Note. The person driving the session reads it and records the approval themselves:

```text
/storyline-gate example-enrich-ip G3 approve
```

`./scripts/storyline gate` asks for a confirmation on the terminal, which a model's Bash call cannot supply, and appends a `gate_decision` event with `actor_kind: human` (event 10). The builder's own report never counts as G3.

**Exit.** `./scripts/storyline apply example-enrich-ip tines-builder -` saves the builder's report **verbatim** as `build-log.md` — it is never parsed (event 11). `./scripts/storyline advance example-enrich-ip` then checks `build_evidence`: the `story/` branch exists, the export's `exported_from.at` is later than the build start, `./scripts/lint-story.sh` passes, and a human G3 event follows the build start. The story moves to **verify** (event 12).

**Stop rule.** Two failed corrections on one issue stop the build and open **GX**, the escalation gate the owner decides.

## 04 · verify → G4 (and one round of rework)

**What happens, attempt 0.** `next` returns a **parallel** step: `tines-reviewer` (conventions, through the scaffold's `/tines-review` in a fresh context) and `security-reviewer`, which is dispatched because the contract names egress hosts and credentials; the cost checks run beside them as a script (`./scripts/storyline estimate example-enrich-ip --check`). Each reviewer's output is applied (events 13–14). Then `next` names **`story-qa`**, which runs the eval cases against the **dev** story — never production — and grades them:

```bash
./scripts/storyline eval-run example-enrich-ip --entry-story-id <dev wrapper story id>   # it asks
```

The entry is a Send to Story sub-story, so each case is posted to a dev-only **wrapper story** (a Webhook → Send to Story into the story under test → Exit) that the builder built alongside it and never ships; the exact Webhook URL form is VERIFY K37. Verify never needs the Tines Stories MCP server, so nothing changes the export that was just verified. Four of four deterministic cases pass (event 15).

Then the merge — code, not a model:

```bash
./scripts/storyline apply example-enrich-ip verify-merge     # it asks
```

The rule is deterministic: any `blocker` or `major` finding means `changes_requested`. The reviewer found one **major**: `lookup_abuseipdb` still had the default retry count (`http_retry_bounds`). So the result is `changes_requested`, a **rework package** (`.storyline/out/example-enrich-ip/rework-1.json`, local) lists the finding with a `suggested_prompt`, and the story returns to **build** with `status: rework`, attempt 1 (events 16–17). The builder and reviewers share one cap of three rework cycles; at the cap the story opens GX.

**Attempt 1.** `./scripts/storyline start example-enrich-ip` again; the builder's handoff now begins "First read `.storyline/out/example-enrich-ip/rework-1.json`; fix only the listed findings." A one-step plan (retries 6 on `lookup_abuseipdb`) is approved with `/storyline-gate example-enrich-ip G3 approve`, built, validated, tested, exported and committed; `build_evidence` passes again (events 18–21). Verify runs again: the reviewer passes with one minor finding, the security reviewer notes one info item, QA passes four of four, the cost checks `cost.4`–`cost.9` all PASS, and `verify-merge` says **pass** (events 22–25). `./scripts/storyline advance example-enrich-ip` writes `ship` with the open gate G5a on the branch.

**G4 — verify and merge (code + model + human).** The build PR's Lifecycle section names gate `G4 verify and merge`, rework attempt `1/3`, and the human's verdict on `story-qa`'s verification prompt — the person opened the dev runs in Tines and checked what the prompt asked:

```text
- QA verification: pass · by security-automation
```

`storyline.yml` refuses a G4 PR without that line, and checks that the row on `main` was in build, the touch set for a `story/` branch, the tracker `rev`, the event log and `storyline estimate --check`; it calls `lint.yml` and `review.yml` (an independent reviewer instance), because the PR touches `stories/**`. A CODEOWNER reviews, and a person who is not the author merges. **That merge is G4** (event 26). A person's "request changes" on the PR also resets the rework cap.

## 05 · ship → G5a (a first ship)

**What happens.** The manifest says `new: true`, so this is a **first ship**. A merge never creates a story in production; a person dispatches `ship.yml` for `example-enrich-ip` with `env: prod` and a logged `new_in_prod_reason`. The job waits for a **required reviewer of the GitHub `production` environment** — security-platform — who reads the PR and the export and releases it. `ship.yml` then imports the export with `mode: new`, creating the story in the prod team with no draft and no change request. **That release is G5a.** Afterwards, by hand: change control is switched on for the new story, and `ship.yml`'s follow-up PR records its prod id in `stories/_manifest.yaml` (removing `new: true`) and in `policies/never-touch.yml`.

The preferred alternative, from the scaffold: before the first ship, a person creates an empty, disabled, change-controlled story with the exact name in the prod team and commits its id. The ship is then an ordinary change request — G5b.

**The evidence.** `ship.yml`'s final **G5 evidence** step reads the result with the prod Viewer key and writes `ship.md` through a PR on `tracker/ship-example-enrich-ip-0000000`, which needs an approving review from the team `storyline/gates/approvers.yaml` lists for G5a (event 27). The editor never reads production: its key is dev-only.

**You run,** once that PR has merged:

```bash
./scripts/storyline advance example-enrich-ip      # reads ship.md on origin/main (it asks)
```

The story moves to **operate** with `status: live` — the contract says `risk.side_effects: false`, so it does not start in shadow — and the row gains `prod_story_id` and `live_since` (event 28).

**Every later ship** of this story is a `versionReplace` import into a draft named `git-<sha>` and a change request, and **G5b** is a named approver approving and pushing in Tines after reading the live-vs-draft diff (or `promote.yml` promoting a request that is already APPROVED). What `./scripts/tines cr-view` returns after a push is VERIFY K45. If an approver **rejects**, `advance` prepares the revert of the rejected commit on `rollback/example-enrich-ip/<sha7>` so `main` matches what is live, `drift.yml` skips the story until that PR merges, and the story returns to build.

## 06 · operate → G6 (not needed here), G7 (quarterly)

**What happens.** The scaffold's ops trio runs unchanged. `ship.yml` set the ops router and the ops email list as the story's recipients and turned on "Notify when any action fails"; the sweep builds the story's baseline and proposes, with evidence, what a person approves. Findings land in `ops_findings`, the retro's evidence.

**G6 — go-live (human)** applies only to a story that starts in **shadow** (`risk.side_effects: true`): its side-effecting actions sit behind a Trigger on a `<slug>_rollout` Resource, and after a shadow window with no high or critical finding, outputs that meet the eval bar and credits within 1.5 × the estimate, the owner and a G6 approver decide `go_live` on the `gate_decision` Page, recorded in `go-live-review.md`. This story has no side effects, so there is no G6.

**G7 — ownership review (human, quarterly):** the owner and platform decide `keep`, `rescope` or `retire` on the `gate_decision` Page. Retiring means the owner disables the story in Tines by hand after the decision, and a PR marks it `retired`.

## 07 · improve → back to design (iteration 2)

**What happens.** Every 15 minutes, `[KIT] 00` section D's `improve_check` (D9) looks at every story in operate for an improve trigger: a high or critical finding, credits above 1.5 × the estimate, or a retro due. Seven days after `live_since`, the retro is due: D9 writes `phase: improve` as provisional, and the transition reaches git by tracker PR (event 29, `actor_kind: story`). Section D then runs **`retro_writer`** — tool-less — on the story's `ops_findings` and `ops_alerts` rows for the window, its `storyline_events` and the credit ledger. Its draft reached git by the next tracker PR (event 30): four validation failures that the pattern check let through (an octet above 255, reported as `unknown`), two 429 bursts absorbed by retries and the cache, cost 0 against an estimate of 0, and the proposal **`keep_or_change: change`**.

**You run,** on `improve/example-enrich-ip`: the owner completes `retro.md` — confirms `change`, checks every evidence reference, sets `closed: true` — and then:

```bash
/storyline example-enrich-ip run
```

`next` names **`eval-curator`**, which turns the failure mode into a new capability case, `out-of-range-octet-is-validation-error`, that **fails on the live design**, and graduates the three cases that passed in both verify runs to **regression** (event 31; [`../storyline/evals/regression/README.md`](../storyline/evals/regression/README.md)). `skill-curator` is not dispatched: the retro has no skill suggestion, and a skill never changes in response to a single event — if a second story shows the same lesson, it becomes a logbook entry or a prompt-pack line. The PR from `improve/example-enrich-ip` is reviewed and merged like any other.

**Exit.** `./scripts/storyline advance example-enrich-ip` reads `retro.md`: `keep_or_change: change` means the check `change_needed`, and the story opens **iteration 2 in design** with the retro as input and the attempt reset to 0 (event 32). The live story keeps running, monitored, while iteration 2 is designed and built. Had the retro said `keep`, `retro_closed` would have returned it to operate; `retire_candidate` would have opened G7.

## Gates that did not fire here

| Gate | When it fires | Who decides, and how |
|---|---|---|
| **GB** budget | At a dispatch boundary, when a new estimate would take a team past its ceiling (warn at 80 %, park at 100 %) | Opened by code (`storyline ready`, `storyline_limits`, the ops sweep); a person releases it with `unpark` on the Page (or `/storyline-gate … GB unpark` on the Community path) |
| **GX** escalation | The rework cap reached, two failed corrections, `needs_human`, a schema failure twice, a critic disagreement — in any phase | The owner, `resume`, `park` or `reject`, on the Page (or `/storyline-gate` on the Community path) |
| **G5b** change request | Every ship after the first | A named approver, in Tines |
| **G6** go-live | A story that started in shadow | Owner + a G6 approver, on the Page |

## Reading the trail

- `./scripts/storyline status example-enrich-ip` — where the story is, and whether the evidence contradicts the tracker (`drift`, printed with a proposed correction, never fixed silently).
- `storyline/work/example-enrich-ip/events.jsonl` — every transition, gate decision and crew member run, with the actor's role, the actor kind (`human`, `agent`, `ci`, `story`) and the tracker `rev`. Tines-side runs also log `credits_used` and the model in the `storyline_events` Record type.
- `.tines/mcp-activity.jsonl` and the tenant's audit logs — every Tines Stories MCP server call the build made.
- The PR history — who approved each design and each merge.

The lifecycle files behind every step: [`../storyline/README.md`](../storyline/README.md) (the model), [`../storyline/phases/`](../storyline/phases/00-intake.md) (one file per phase), [`../storyline/gates/README.md`](../storyline/gates/README.md) (who decides each gate), [`../storyline/lifecycle/state-machine.yaml`](../storyline/lifecycle/state-machine.yaml) (the machine itself).

## Verify in your tenant before presenting

This walkthrough leans on open items: **K2** (the phase gate identifies the builder), **K37** (the eval-run Webhook URL and the wrapper story), **K43** (the catalog ids still resolve), **K45** (what the change-request view returns after a push), and scaffold items **#1** (the `/mcp` tool names), **#2** (how `/mcp` edits interact with change control) and **#8** (the export key names lint reads). Until each is confirmed in your tenant, treat the matching step as the design, not as observed behaviour. The ledger is [`VERIFY.md`](VERIFY.md).
