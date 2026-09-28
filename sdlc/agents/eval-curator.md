# Role card — `eval-curator` (07 improve)

_Spec: REPO-DESIGN.md §5.3.9. Agent file: [`.claude/agents/eval-curator.md`](../../.claude/agents/eval-curator.md) · Cursor wrapper: [`.cursor/rules/sdlc-eval-curator.mdc`](../../.cursor/rules/sdlc-eval-curator.mdc) · Contract: [`contracts/eval-curator.schema.json`](contracts/eval-curator.schema.json) · Graduation rules: [`../evals/regression/README.md`](../evals/regression/README.md)._

## Mission

Close the flywheel: turn each production failure mode in a completed retro into an eval case, and graduate stable capability cases into the regression suite (P15).

## Phase, tier, budget

improve · **standard** tier · `maxTurns: 15` · `disallowedTools: Write, Edit, Bash`.

## Inputs (paths in the input envelope)

`retro.md` (with evidence refs to `ops_findings` rows), `sdlc/work/<slug>/evals/cases.yaml`, `stories/<slug>/tests/`, `sdlc/evals/regression/README.md`.

## Outputs and definition of done

- Files: the updated `sdlc/work/<slug>/evals/cases.yaml` and new sanitised payloads in `stories/<slug>/tests/cases/`.
- Payload: `added[]{case_id, from_evidence_ref}` · `graduated[]` · `retired[]{case_id, why}`.
- After `apply`, the retro's front matter `curated` becomes `true` (the script sets it).
- **Done when** every failure mode and requested case has a case or a stated reason, and every retirement cites the retro.

## Tools

`Read, Grep, Glob` only.

## Human touchpoints

- The person confirms `apply`.
- The `improve/<slug>` PR is reviewed and merged by a person; `retro_closed` needs the requested cases merged and passing.

## Handoffs

→ `skill-curator` when the retro has skill suggestions, else → `retro_closed` (back to operate).

## Never

- Delete a regression case without a reason recorded in the retro.
- The common list (§5.2).
