# G2 · Design approval — the design PR merge

| | |
|---|---|
| **Between** | design → build (after G1) |
| **Type** | human |
| **Decided by** | a CODEOWNER of the story's prefix who is **not** the PR's author (`/stories/**` → tines-builders; `/stories/ops-*` and `/stories/kit-*` → security-platform; `/storyline/**` → both) |
| **Evidence** | the design PR from `design/<slug>`: `discovery.md`, `design.md` with its contract, `evals/cases.yaml`, `stories/<slug>/{README.md, story.meta.yaml, tests/**}`, the manifest entry, the budget line, the tracker row, and G1's JSON |
| **Instrument** | the merge of the design PR, under branch protection (`storyline` required, a CODEOWNER review, no self-merge) |
| **Recorded** | the merge. The PR carries the tracker change `phase: build, status: active` and a `transition` event, so the state change lands exactly when the human approves it |
| **Decisions** | `merged` → build · `rethink_reuse` → discover |

## What the reviewer checks

1. **The rung is the lowest that works.** Each lower rung has a sentence saying why it fails (P1). "An agent would be nicer" is not a reason.
2. **The contract is self-contained.** A builder in a fresh context could implement it without asking: entry fields, actions, credentials by name, the result shape, the error shape, out of scope (P4).
3. **The evals judge what matters.** Every acceptance criterion has a case; there is a should-not case; model-graded cases have a rubric two experts would grade the same way (P2).
4. **Risk is honest.** A side effect on another system has an approval path, or shadow mode, or both. Destructive tools are `request_` tools.
5. **Cost is designed in.** Every AI Agent action has an output schema, a Trigger after it on a schema field, a token alert and a budget line; the estimate has a basis.
6. **Nothing outside the design touch set changed.**

## Decisions

- **Merge** — the story is in build on `main`. `phase-gate.sh` now lets `tines-builder` reach `/mcp` for this story once `./scripts/storyline start <slug>` runs ([03 build](../phases/03-build.md)).
- **Request changes** — the story stays in design; the architect or eval author runs again on the same branch.
- **`rethink_reuse`** — the reviewer believes something already exists that does most of this, and closes the PR with that reason. Nothing reached `main`, where the row still reads `discover` (the design branch's transitions were provisional). The showrunner starts a fresh `design/<slug>` branch from `main`; `./scripts/storyline advance <slug>` records the reason as its first event (`transition`, `design → discover`, gate G2, decision `rethink_reuse`), and `story-scout` runs again with the reviewer's pointer as an input.
