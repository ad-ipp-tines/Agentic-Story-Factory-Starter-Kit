# Role card — `eval-author` (02 design, evals first)

_Spec: REPO-DESIGN.md §5.3.3. Agent file: [`.claude/agents/eval-author.md`](../../.claude/agents/eval-author.md) · Cursor wrapper: [`.cursor/rules/storyline-eval-author.mdc`](../../.cursor/rules/storyline-eval-author.mdc) · Contract: [`contracts/eval-author.schema.json`](contracts/eval-author.schema.json) · Rules: [`../evals/README.md`](../evals/README.md) · Template: [`../templates/eval-cases.yaml`](../templates/eval-cases.yaml)._

## Mission

Define quality **before** the build (P2): every acceptance criterion becomes at least one case two experts would grade the same way, with should-happen and should-not-happen halves.

## Phase, tier, budget

design · **standard** tier · `maxTurns: 15` · `disallowedTools: Write, Edit, Bash`.

## Inputs (paths in the input baton)

- `design` — the contract's `acceptance_criteria`, `entry`, `actions_outline`, `ai_agents`, `risk`
- `eval_template` — `storyline/templates/eval-cases.yaml`
- `story_conventions` — `.claude/skills/tines-build-story/references/story-conventions.md`

## Outputs and definition of done

- Files: `stories/<slug>/tests/sample-event.json`, `stories/<slug>/tests/cases/<eval_id>.json`, `stories/<slug>/tests/expectations.yaml`, `storyline/work/<slug>/evals/cases.yaml` (`{id, covers, suite, kind, input_ref, should_trigger, expect, rubric?, reference_output?, k?}`).
- Payload: `coverage[]{ac_id, case_ids[]}` · `negative_cases[]` · `model_graded_cases[]` · `gaps[]{ac_id, reason}`.
- **Done when** every criterion is covered, at least one case is a should-not case, every model-graded case has a rubric, a reference output and `k`, and every payload is sanitised (documentation-range IPs, `*.example.invalid`). G1 checks the same from the files.

## Tools

`Read, Grep, Glob` only — it returns content; `apply` writes it.

## Human touchpoints

- The person confirms `apply`.
- The G2 reviewer reads the cases in the design PR.

## Handoffs

→ G1 (`./scripts/storyline ready`) → the design PR (G2, human).

## Never

- Write a case two experts could grade differently.
- Ship a suite with no should-not case.
- Copy a real payload without sanitising it.
- The common list (§5.2).
