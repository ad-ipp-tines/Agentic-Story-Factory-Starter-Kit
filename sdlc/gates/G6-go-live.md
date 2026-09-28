# G6 · Go-live — shadow → live

| | |
|---|---|
| **Between** | operate `shadow` → operate `live` |
| **Type** | human |
| **Decided by** | the owner **and** an approver listed for G6 (`approvers.yaml` G6 requires both teams) |
| **Evidence** | `sdlc/work/<slug>/go-live-review.md` ([template](../templates/go-live-review.md)) |
| **Instrument** | the `gate_decision` Page when Records are entitled · `/sdlc-gate <slug> G6 go_live\|stay_shadow` only on the Community path |
| **Recorded** | `go-live-review.md` + a `gate_decision` event (`gate: G6`) |
| **Decisions** | `go_live` → `status: live` · `stay_shadow` → `status: shadow` |

## When it opens

Only stories whose contract says `risk.side_effects: true` start in shadow; every other story enters operate `live` and never meets G6. A shadow story's side-effecting actions sit behind a Trigger on the Resource `<slug>_rollout` (`shadow | live`): in shadow it computes and records but does not act.

G6 is ready to decide once the shadow window has passed (`timers.shadow_days`, default 7, counted from `live_since`).

## The three conditions (all must hold for `go_live`)

1. **No high or critical finding** in the shadow window — `ops_findings` rows for the story's `prod_story_id`.
2. **The shadow outputs meet the eval bar** — what the story would have done matches the eval set's expectations; pass^k = 1 where consistency matters (side-effecting stories always qualify).
3. **Credits within 1.5 × the estimate** — actual vs `contract.cost_estimate` for the window.

If any fails, the answer is `stay_shadow`, and usually a retro (improve) to find out why.

## After `go_live`

- Flip `<slug>_rollout` from `shadow` to `live` — `[BY HAND]` in Tines, or through the ops apply path. The decision does not flip it by itself.
- Confirm the next run acts, and that its failures reach the router.
- On a Records tenant the decision is provisional until the tracker PR merges; `sdlc.yml` requires approving reviews from both G6 teams.
