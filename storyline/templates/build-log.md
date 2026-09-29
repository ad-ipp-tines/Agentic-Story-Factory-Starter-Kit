# Build log — `<slug>` · attempt <n>

_Template: `storyline/templates/build-log.md` · Phase: `storyline/phases/03-build.md` · Saved by `./scripts/storyline apply <slug> tines-builder -` from the builder's final report, **verbatim**._

> **This file is never parsed.** Nothing in the lifecycle reads a verdict, a pass or a plan approval from it. The phase exit is the check `build_evidence` (the story branch exists, the export is newer than the build start event, `./scripts/lint-story.sh` passes, and `events.jsonl` holds a human `gate_decision` event for G3 after the build start). G3 is recorded only by `/storyline-gate <slug> G3 approve`. This file is here so a person can read what the builder did.

| | |
|---|---|
| Story | `<slug>` · `[PREFIX] NN · Verb noun` |
| Attempt | <0 for the first build; n for rework n> |
| Branch | `story/<slug>/<short>` |
| Handoff | `/tines-build-story <slug> "<ask rendered from the contract>"` (template `build-from-contract`) |
| Rework package | <none, or `.storyline/out/<slug>/rework-<n>.json` (local)> |
| Build start event | <ts of the `specialist_run` event with `decision: started`> |

## The builder's report (verbatim, below this line)

<!-- apply appends the report here without editing it. The /tines-build-story report usually covers, in order:
     what the builder saw (explore) · the numbered plan it asked the human to approve · what it built, step by step ·
     Validate results · the test event and the expectations it met or missed · the [BY HAND] checklist ·
     the export, lint and semantic diff · the commit. -->
