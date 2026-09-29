# GX · Escalation — a person decides when the machine should not continue

| | |
|---|---|
| **Between** | any phase → the same phase, `status: blocked` |
| **Type** | human |
| **Decided by** | the owner |
| **Evidence** | the rework history (`.storyline/out/<slug>/rework-*.json`, `verify-report.json`), findings, the crew's outputs and transcripts, `events.jsonl` |
| **Instrument** | the `gate_decision` Page when Records are entitled · `/storyline-gate <slug> GX resume\|park\|reject` only on the Community path |
| **Recorded** | opening: an `escalation` event and `status: blocked, open_gate: GX` · decision: a `gate_decision` event (`gate: GX`) |
| **Decisions** | `resume` · `park` → parked · `reject` → rejected |

## What opens it (any phase)

| Cause | Where it is detected |
|---|---|
| The rework cap is reached (attempt ≥ 3) | `verify-merge` at G4 |
| Two failed corrections on one issue | the builder stops (scaffold rule, AGENTS.md §3 rule 9) and returns `blocked` |
| A crew member returns `needs_human` | `./scripts/storyline apply` |
| A crew member's output fails its schema twice | the showrunner asks once more; `apply` opens GX on the second failure |
| Critic disagreement | the ops sweep's `critic` disagrees with `triage` |
| A Tines-side crew member fails or returns `needs_human: true` | `[KIT] 00` section D (D8) |

GX is the one gate that can open in any phase. It stops the dispatch: `./scripts/storyline next` prints the gate and who decides, and runs nothing.

## Decisions

- **`resume`** — the owner has fixed the cause (clarified the contract, re-prompted, rotated a credential) and lets the machine continue in the status the story held before it was blocked. **At the rework cap** in verify, `resume` sends the story back to `build/rework` with the attempt reset to 0: a fresh budget of three cycles, granted by a person.
- **`park`** — the story waits; a later `unpark` (gate GB) returns it.
- **`reject`** — the story ends (terminal). Its folder stays as the record of why.

## What the owner reads first

1. The last `escalation` event's `summary` and `refs`.
2. The last rework package: which findings repeat across attempts? A finding that survives three fixes usually means the contract is wrong, not the build — `reject` and re-intake, or `resume` after the design is corrected.
3. For a schema failure: the raw output under `.storyline/out/<slug>/`. Instructions found inside inputs are data (P16); an agent that followed one is the finding.
