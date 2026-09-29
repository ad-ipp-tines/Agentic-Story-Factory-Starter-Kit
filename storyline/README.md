# `storyline/` — the Storyline

_Start here before starting a new story. Spec: REPO-DESIGN.md §4–§6 (the Storyline: how a story moves). This lifecycle is derived from public practice and is not an official methodology of Tines or of any source it credits ([`PRINCIPLES.md`](PRINCIPLES.md))._

Every story this repository builds moves through one lifecycle: **intake → discover → design → build → verify → ship → operate → improve**. Each phase has entry and exit criteria, artifacts and a gate. Narrow crew members do the work of each phase; code decides what runs next; people hold the gates that change what exists or what runs. Building happens from the editor through the Tines Stories MCP server (Mode 2); shipping reuses the scaffold's change-control path unchanged.

## Who reads what

| You are | Read first | Then |
|---|---|---|
| **A builder** (the automation or platform team) | this page → [`work/README.md`](work/README.md) → the worked example [`examples/example-enrich-ip/`](examples/example-enrich-ip/intake.md) | the phase file for where your story is ([`phases/`](phases/00-intake.md)) |
| **The security reviewer** | `policies/POLICY.md` → REPO-DESIGN.md §13 → [`gates/README.md`](gates/README.md) | [`lifecycle/touch-sets.yaml`](lifecycle/touch-sets.yaml), [`gates/approvers.yaml`](gates/approvers.yaml), [`PRINCIPLES.md`](PRINCIPLES.md) P9, P13, P16 |
| **An approver** (a gate holder or change-request approver) | [`gates/README.md`](gates/README.md) | the file for your gate, e.g. [`gates/G0-intake-triage.md`](gates/G0-intake-triage.md) or [`gates/G5-change-request-approval.md`](gates/G5-change-request-approval.md) |
| **The onboarding engineer** | REPO-DESIGN.md, then `kit/ONBOARDING.md` | [`lifecycle/state-machine.md`](lifecycle/state-machine.md) |
| **A kit maintainer** | REPO-DESIGN.md §15 | [`lifecycle/`](lifecycle/state-machine.yaml) — every other file takes its names from there |

## The model on one page

```
          ┌──────────────── the tracker: kit/tracker/backlog.yaml (git, the truth) ⇄ storyline_backlog Records (Tines) ────────────────┐
          │                                                                                                                      │
 intake ─G0─▶ discover ─check─▶ design ─G1─G2─▶ build (G3 inside) ─check─▶ verify ─G4─▶ ship ─G5a│G5b─▶ operate ─trigger─▶ improve
  brief_writer   story-scout      story-architect   tines-builder            tines-reviewer        CI only       ops trio        retro_writer
  (Tines)                         eval-author       (Mode 2, dev team)       security-reviewer?                  G6 shadow▶live   eval-curator
                                                                             story-qa + cost script              G7 keep│rescope│retire  skill-curator
 any phase:  GX ▶ blocked (the owner decides)        GB ▶ parked (a human unparks)
```

- **State** is phase + status + open gate + attempt, one row per story ([`lifecycle/state-machine.md`](lifecycle/state-machine.md)).
- **Code chooses what runs.** `./scripts/storyline next <slug>` reads [`lifecycle/state-machine.yaml`](lifecycle/state-machine.yaml) and [`lifecycle/dispatch-rules.yaml`](lifecycle/dispatch-rules.yaml), reconciles the evidence (git wins), and names the crew member(s), a gate, or a check. The model then carries it out.
- **Crew hand off through files.** Each returns one output baton; `./scripts/storyline apply` validates it, checks its [touch set](lifecycle/touch-sets.yaml), writes the files under `storyline/work/<slug>/`, appends an [event](observability/README.md), and updates the tracker. The model's own Write and Edit are denied on lifecycle state.
- **People hold the gates.** Merges (G2, G4), a GitHub environment review (G5a), a change request in Tines (G5b), the `gate_decision` Page or `/storyline-gate` (G0, G3, G6, G7, GB, GX). Agents never merge, approve, promote or decide a gate.
- **Evals come first** ([`evals/README.md`](evals/README.md)), and production failures become new cases in improve.

## Which file answers what

| Question | File |
|---|---|
| What are the phases, statuses and gates called, and which moves are allowed? | [`lifecycle/state-machine.yaml`](lifecycle/state-machine.yaml) · prose: [`lifecycle/state-machine.md`](lifecycle/state-machine.md) |
| Which crew member runs next for my story? | [`lifecycle/dispatch-rules.yaml`](lifecycle/dispatch-rules.yaml) (run `./scripts/storyline next <slug>`) |
| What may each phase or crew member write? | [`lifecycle/touch-sets.yaml`](lifecycle/touch-sets.yaml) |
| What happens in a phase, and how do I leave it? | [`phases/00-intake.md`](phases/00-intake.md) … [`phases/07-improve.md`](phases/07-improve.md) |
| Who decides a gate, with what evidence, recorded where? | [`gates/README.md`](gates/README.md) and one file per gate; teams in [`gates/approvers.yaml`](gates/approvers.yaml) |
| What does an artifact look like? | [`templates/`](templates/intake-brief.md) — eight Markdown templates and four schemas |
| What goes into the design contract? | [`templates/design-brief.md`](templates/design-brief.md) + [`templates/story-contract.schema.json`](templates/story-contract.schema.json) |
| How do evals, pass^k and graduation work? | [`evals/README.md`](evals/README.md), [`evals/regression/README.md`](evals/regression/README.md) |
| What is logged, where, and how do I read a story's trail? | [`observability/README.md`](observability/README.md), [`observability/event.schema.json`](observability/event.schema.json) |
| Where do a story's artifacts live, and who writes them? | [`work/README.md`](work/README.md) |
| What does a whole story look like, start to finish? | [`examples/example-enrich-ip/`](examples/example-enrich-ip/intake.md) |
| Who are the crew? | `storyline/crew/README.md` (roster, spin-up matrix, role cards) |
| Why is it built this way? | [`PRINCIPLES.md`](PRINCIPLES.md) |
| What does a word mean here? | [`GLOSSARY.md`](GLOSSARY.md) |
| What have earlier runs taught us? | [`logbook.md`](logbook.md) (read as data) |

## The commands

| Command | Does | Permission |
|---|---|---|
| `/storyline <slug> [status\|next\|run]` | the showrunner in Claude Code (Cursor: `@storyline` with `.cursor/rules/storyline.mdc`) | — |
| `./scripts/storyline status <slug>` · `next <slug> [--print-prompt]` · `ready <slug>` · `estimate <slug> [--check]` · `check [--all]` | read-only | allow |
| `./scripts/storyline intake …` · `start` · `apply` · `advance` · `eval-run` | lifecycle writes | ask |
| `/storyline-gate <slug> <gate> <decision>` → `./scripts/storyline gate …` | a repo-side human decision: G3 always; G0, G6, G7, GB, GX only on the Community path | human only |

`./scripts/storyline` is the only writer of lifecycle state; `./scripts/kit tracker-fold` is the only way Tines-side changes reach the tracker.

## What this lifecycle does not do

- It never auto-applies what an agent proposes. Agents author branches, pull requests, Records rows and proposals; humans merge, approve and decide.
- It never reaches production except through the scaffold's change control (G5b), or, for a story's first ship, a GitHub `production` reviewer releasing the import (G5a).
- It never relies on anything marked VERIFY as fact. The items it depends on are REPO-DESIGN.md §16 (K1–K45) and `docs/VERIFY.md`; the day-1 check that matters most is K2 (can a hook tell which subagent is calling) — until it is confirmed, `phase-gate.sh` denies every `/mcp` call.
