# GB · Budget — parks a story at a dispatch boundary; a human releases it

| | |
|---|---|
| **Between** | any phase → parked, at a dispatch boundary; parked → the phase it left |
| **Type** | budget: **deterministic** to open, **human** to release |
| **Opened by** | `./scripts/sdlc ready` (design, as part of G1) · the `sdlc_limits` caps in `[KIT] 00` section D (Tines) · the ops sweep (operate) |
| **Evidence** | the ceilings in `policies/cost-ceilings.yml` and the `sdlc_limits` Resource; committed estimates in `kit/tracker/backlog.yaml`; `ai_usage` actuals |
| **Instrument (release)** | the `gate_decision` Page option `unpark` when Records are entitled · `/sdlc-gate <slug> GB unpark` only on the Community path |
| **Recorded** | opening: tracker `phase: parked, status: awaiting_gate, open_gate: GB` + a `budget` event · release: a `gate_decision` event (`gate: GB`, `decision: unpark`) |
| **Decisions** | `park` (written by the script that detects it) · `unpark` (a human) |

## When it fires

**Only at dispatch boundaries, never in the middle of a phase** (REPO-DESIGN.md §4.5 rule 5):

| Boundary | Check | Warn | Park |
|---|---|---|---|
| design → build (G1, `sdlc ready`) | this story's `cost_estimate.monthly_credits_est` + every committed estimate on the team vs the team's `monthly_credits`; plus the verify-phase eval-run cost (cases × k × credits per run) vs the dev team's remaining ceiling (cost.9) | 80 % | 100 % |
| design → build (G1, `sdlc ready`) | the owner already has `wip_limit_per_owner` (1) stories in build or verify | — | at the limit |
| a Tines-side specialist run (section D) | today's runs for that agent vs `sdlc_limits.runtime.<agent>.runs_per_day_max`; `sdlc_limits.enabled` and `guards_confirmed` | — | the run is skipped, and the row is not parked |
| operate (the ops sweep) | credits against `ops_limits` (mirrored from `policies/cost-ceilings.yml` `runtime.credit_alert_pct`) | 80 %: a summary by team and story | 95 %: a proposal to pause the costliest agent, which a human approves — the sweep never parks by itself |

`budget_warn_pct` (80) and `budget_park_pct` (100) are in `state-machine.yaml` `thresholds`. **Tines alerts at 80 % and 100 % by default; the stops are the per-action Disable-action token alert and the kit's `sdlc_limits` caps and kill switch.**

Parking at the repo boundary is written by `./scripts/sdlc advance <slug>` (ask) when `sdlc ready` reports GB: the row goes to `parked` with a `budget` event, and reaches `main` by PR like any tracker change.

## Releasing it

`unpark` returns the story to the phase and status it held before (`$previous` in the state machine). Release when one of these is true:

- the ceiling was raised (a `policies/cost-ceilings.yml` PR, reviewed by security-platform, and the allocation in Tines `[BY HAND]` — there is no API for credit allocation);
- another story's estimate went down, or a story was retired;
- the design got cheaper (a smaller model pinned, fewer runs, a deterministic pre-filter before the agent);
- for WIP: the owner's story in build or verify has shipped.

The same `unpark` releases a story parked by G0 or GX: a park is always released as gate GB.
