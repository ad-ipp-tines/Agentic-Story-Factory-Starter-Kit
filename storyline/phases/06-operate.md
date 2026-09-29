# 06 · operate — observe, and stage the rollout

_Phase `operate` in [`state-machine.yaml`](../lifecycle/state-machine.yaml) · Gates: [G6](../gates/G6-go-live.md) (human, shadow → live) and [G7](../gates/G7-ownership-review.md) (human, quarterly) · Spec: REPO-DESIGN.md §4.4 (06 operate)._

## Purpose

Run the story in production under the scaffold's monitoring, stage risky stories through shadow mode before they act (P22), and collect the evidence that the improve phase turns into eval cases.

## Entry criteria

G5a or G5b has released the story and `storyline advance` has moved it here. The status it enters with comes from the contract:

- `risk.side_effects: true` → **`shadow`**. Its side-effecting actions sit behind a Trigger on the Resource `<slug>_rollout` (`shadow | live`); in shadow the story computes and records but does not act.
- otherwise → **`live`**.

Phase is where the lifecycle work is, not whether the story runs: a live story whose next iteration is in design is still running here and still monitored.

## Work

The scaffold's ops trio runs unchanged:

- `[OPS] 01` (the router) is every production story's recipient.
- `[OPS] 10`, the sweep, runs its Mode 3 `triage` agent (five read-only Send to Story tools) and its tool-less `critic`; they **propose**, humans approve. Findings land in `ops_findings`, alerts in `ops_alerts`, and baselines accumulate in `ops_baselines`.
- `[OPS] 20` (Mode 4) serves the same read tools to an AI client outside Tines.

Reuse card: [`runtime-ops-triage-critic.md`](../crew/runtime-ops-triage-critic.md).

**G6 — shadow → live (human).** It opens once three things hold, and is recorded in `go-live-review.md` ([template](../templates/go-live-review.md)):

1. the shadow window (`timers.shadow_days`, default 7) has no high or critical finding;
2. the shadow outputs meet the eval bar;
3. credits are within 1.5 × the estimate.

`go_live` → `status: live`, and the Resource `<slug>_rollout` is flipped `[BY HAND]` or through the ops apply path. `stay_shadow` keeps it in shadow.

**G7 — ownership review (human, quarterly per story):** keep, re-scope or retire. `retire` means the owner disables the story in Tines `[BY HAND]` after the decision, and a PR marks it `retired` and removes it from the manifest. `rescope` opens a new design iteration.

## Leaving operate

On `improve_trigger` (the check in `state-machine.yaml`), any of:

| Trigger | Evaluated where |
|---|---|
| an ops finding of severity high or critical on the story | `[KIT] 00` section D (D9), which reads `ops_findings` for the row's `prod_story_id` |
| credits above 1.5 × the estimate | section D (D9) |
| retro due: 7 days after live, then every `retro_cadence_days` (30) | section D (D9), from `live_since` |
| an eval regression | repo-side |
| an owner request | repo-side |

Section D writes `phase: improve` with `pending_repo_sync`, and the change reaches git through the tracker PR. Without Records (the Community path) every trigger is recorded repo-side with `./scripts/storyline advance`.

Or on G7 `retire` → `retired`.

## Exit criteria

Continuous. The story leaves only on an improve trigger or on G7.

## Artifacts

| Artifact | Path | Written by |
|---|---|---|
| Go-live review | `storyline/work/<slug>/go-live-review.md` | the human, with the G6 decision (Page → tracker PR, or `/storyline-gate` on the Community path) |
| Ops Records | `ops_findings`, `ops_alerts`, `ops_baselines` (in Tines) | the ops trio |
| Events | `storyline/work/<slug>/events.jsonl` | tracker-fold, `storyline gate`, `advance` |

## Templates

[`go-live-review.md`](../templates/go-live-review.md)

## Crew

The reused Tines-side `triage` and `critic` of `[OPS] 10`. No IDE crew member runs in operate.

## Gates

- **[G6 — go-live](../gates/G6-go-live.md)**: owner + an approver listed for G6.
- **[G7 — ownership review](../gates/G7-ownership-review.md)**: owner + platform.

Both are decided on the `gate_decision` Page when Records are entitled, and through `/storyline-gate` only on the Community path.

## Failure modes

| Symptom | Cause | What happens |
|---|---|---|
| The router pages for the story | a run failed | the story's runbook in `stories/<slug>/README.md`; a fix goes through the lifecycle as a new iteration, a rollback through `/tines-rollback` |
| A shadow story never gets a G6 | the window keeps producing findings | it stays in shadow; the retro (improve) decides whether to change or retire it |
| The ops sweep is not live | `[OPS] 10` has not shipped yet | no findings reach the retro: the week-1 milestone requires it live |
| Credits spike | a loop or a bigger model | Tines alerts at 80 % and 100 % by default; the stops are the per-action Disable-action token alert and the kit's `storyline_limits` caps and kill switch, with the improve trigger at 1.5 × |
