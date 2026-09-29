# `storyline/work/` — per-story lifecycle artifacts

_Spec: REPO-DESIGN.md §4.6 (artifact index), §2 ("Local, never committed"), §3.3 row 6. One folder per story key; in the template repository this folder holds only this file. The worked example lives outside it, in [`storyline/examples/example-enrich-ip/`](../examples/example-enrich-ip/intake.md), so a customer's real story #1 starts from clean templates._

## Layout

```
storyline/work/<slug>/
├── intake.md            00 intake     from templates/intake-brief.md
├── discovery.md         01 discover   from templates/discovery-note.md
├── design.md            02 design     from templates/design-brief.md (+ the one `json story-contract` block)
├── spikes/<id>.md       02 design     from templates/spike.md — only when a VERIFY item blocks a decision
├── evals/cases.yaml     02 design     from templates/eval-cases.yaml; extended in 07 improve
├── build-log.md         03 build      the builder's report, verbatim (never parsed)
├── verify-report.json   04 verify     templates/verify-report.schema.json
├── ship.md              05 ship       templates/ship-record.md — written by CI only
├── go-live-review.md    06 operate    templates/go-live-review.md — only for a story that starts in shadow
├── retro.md             07 improve    templates/retro.md
└── events.jsonl         every phase   observability/event.schema.json — append-only
```

Local and never committed (`.storyline/` is gitignored, and the editor's Write and Edit are denied on it):

```
.storyline/active                              the story the showrunner is working on (written by storyline start; read by phase-gate.sh)
.storyline/out/<slug>/<agent>-<attempt>.json   each crew member's raw output baton, saved by storyline apply from stdin
.storyline/out/<slug>/qa-*.json                eval-run results
.storyline/out/<slug>/rework-<n>.json          the rework package the builder reads first
```

## Who writes here

| Writer | Writes |
|---|---|
| `./scripts/storyline apply` | a crew member's files (inside its touch set), the event, the tracker row |
| `./scripts/storyline intake` · `start` · `advance` · `gate` | the rows and files their subcommand names (REPO-DESIGN.md §6.1) |
| `./scripts/kit tracker-fold` | `intake.md` and `retro.md` drafted in Tines, and the events Tines logged |
| CI (the G5 evidence step) | `ship.md` and its event, through a PR |
| **a person** | the human parts of `retro.md` (confirming `keep_or_change`, `closed: true`) and `go-live-review.md`; the fields of `intake.md` on the Community path, from the showrunner's draft in the chat |
| **the model** | **nothing directly.** Write and Edit are denied on `storyline/work/**`, `kit/tracker/**` and `.storyline/**` (`.claude/settings.json`); every model-authored artifact arrives as a baton piped into `./scripts/storyline apply`, which checks its schema and touch set. `.claude/rules/storyline-work.md` says the same to the editor |

**Nobody hand-edits `events.jsonl`.** It is append-only; `storyline.yml` fails a PR that changes an existing line.

## Conventions the scripts rely on

- **Front matter.** Every artifact a check reads carries YAML front matter with its machine-read keys (`intake.md`, `discovery.md`, `design.md`, `ship.md`, `go-live-review.md`, `retro.md`, `spikes/*.md`). The prose below it is for people. `build-log.md` has none, on purpose.
- **The contract block.** `design.md` holds exactly one fenced block whose info string is `json story-contract`; that block, and nothing else, is the contract.
- **Artifacts are created by their own phase.** No command pre-creates a later phase's file as a blank template, because the dispatch rules read file existence (`exists(design.md)`, `exists(retro.md)`). `./scripts/storyline start` creates the folder when it is missing and copies a template only for an artifact of a phase the story has already reached (REPO-DESIGN.md §6.1: "from templates if missing") — never `verify-report.json`, `ship.md`, `go-live-review.md` or `retro.md`.
- **UTC** timestamps with `Z`; **roles**, never names or emails; **names**, never values, for credentials and Resources; placeholders (`<your-tenant>`, `*.example.invalid`, documentation-range IPs, id `0`) in anything that could be shared.
- **One story per branch and per PR.** A PR that touches two `storyline/work/<slug>/` folders is a tracker PR (branch `tracker/*`) or it is wrong.

## Branches that carry this folder to `main`

| Branch | Carries | Touch set (`storyline/lifecycle/touch-sets.yaml`) |
|---|---|---|
| `design/<slug>` | `discovery.md`, `design.md`, `spikes/`, `evals/`, events; the tracker row set to `build` | `discover` + `design` |
| `story/<slug>/<short>` | `build-log.md`, `verify-report.json`, events; the tracker row set to `ship` | `build` + `verify` |
| `improve/<slug>` | `retro.md` completed, new cases, events; the tracker row | `improve` |
| `tracker/*` | Tines-side changes (Flow 2), repo-side intake, Community-path gate decisions, `ship.md` from CI, `advance` in ship and operate | set `tracker` |
| `rollback/<slug>/<sha>` | the revert of `stories/<slug>/**` after a G5 rejection, and its event | set `rollback` |

A branch that matches none of these may not touch `storyline/work/**` or `kit/tracker/**` at all.

## Starting and resuming

```bash
./scripts/storyline intake "<title>" --use-case <file> --owner <role>   # a new row in intake (ask) — or the kickoff / add_use_case Page
/storyline <slug>                                                         # status + the next action (Claude Code)
./scripts/storyline next <slug> --print-prompt                            # the same, rendered for a Cursor chat
```

A fresh session resumes from the tracker row, `events.jsonl` and the evidence (git wins). If they disagree, `storyline next` prints `drift` with a proposed correction and never fixes it silently. Read the worked example before your first story: [`storyline/examples/example-enrich-ip/`](../examples/example-enrich-ip/intake.md).
