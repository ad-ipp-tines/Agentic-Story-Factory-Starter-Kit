---
# Machine-read keys. Written when G6 is decided: by the human with the gate_decision Page's decision reaching git
# through the tracker PR, or with ./scripts/sdlc gate on the Community path.
story_key: <slug>
shadow_from: "YYYY-MM-DDTHH:MM:SSZ"    # live_since (UTC)
shadow_to: "YYYY-MM-DDTHH:MM:SSZ"      # shadow_from + timers.shadow_days (default 7)
high_or_critical_findings: 0           # ops_findings rows of severity high or critical for this story in the window
eval_bar_met: false                    # the shadow outputs meet the eval bar (sdlc/evals/README.md)
credits_ratio: 0                       # actual credits in the window ÷ the estimate for the window; ≤ 1.5 to go live
decision: pending                      # pending | go_live | stay_shadow
decided_by: <role>                     # the owner and an approver listed for G6 — roles, never people
instrument: gate_decision_page         # gate_decision_page | sdlc_gate (Community path only)
rollout_resource: <slug>_rollout       # the Resource whose value is shadow | live
flipped: false                         # true once the Resource reads live
---

# Go-live review — `<slug>`

_Template: `sdlc/templates/go-live-review.md` · Phase: `sdlc/phases/06-operate.md` · Gate: G6 (human), `sdlc/gates/G6-go-live.md`._

> A story whose contract says `risk.side_effects: true` starts in **shadow**: its side-effecting actions sit behind a Trigger on the Resource `<slug>_rollout`, and in shadow it computes and records but does not act. This review decides whether it may act.

## The three conditions (all must hold)

| Condition | Evidence | Holds? |
|---|---|---|
| The shadow window (default 7 days) has no high or critical finding | `ops_findings` rows for `prod_story_id` in the window: <count, refs> | yes · no |
| The shadow outputs meet the eval bar | <what the story would have done vs the eval set's expectations; pass^k where consistency matters> | yes · no |
| Credits are within 1.5 × the estimate | actual <n> vs estimate <n> for the window (ratio <r>) | yes · no |

## What the shadow run would have done

<Summary of the would-be actions: how many, of which kind, and any that a person would have refused.>

## Decision

`go_live` · `stay_shadow` — <reason in one or two sentences>. Decided by <role> and <role> on <UTC date>.

## [BY HAND] after go_live

- [ ] Flip `<slug>_rollout` from `shadow` to `live` (by hand in Tines, or through the ops apply path).
- [ ] Confirm the next run acts, and that `[OPS] 01` receives its failures.
