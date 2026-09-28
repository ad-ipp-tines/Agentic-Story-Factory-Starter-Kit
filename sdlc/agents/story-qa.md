# Role card — `story-qa` (04 verify)

_Spec: REPO-DESIGN.md §5.3.8. Agent file: [`.claude/agents/story-qa.md`](../../.claude/agents/story-qa.md) · Cursor wrapper: [`.cursor/rules/sdlc-story-qa.mdc`](../../.cursor/rules/sdlc-story-qa.mdc) · Contract: [`contracts/story-qa.schema.json`](contracts/story-qa.schema.json) · Rules: [`../evals/README.md`](../evals/README.md)._

## Mission

Run the story's eval set against the **dev** story, grade it (pass^k where consistency matters), record observed credits, and hand a person a precise verification prompt (P2, P12, P23).

## Phase, tier, budget

verify, after the reviewers are applied · **standard** tier · `maxTurns: 20` · `disallowedTools: Write, Edit`.

## How cases run

- `./scripts/sdlc eval-run <slug> [--k 3]` refuses `TINES_ENV=prod` and writes `.sdlc/out/<slug>/qa-*.json` locally.
- **Webhook entry:** each case is posted to the story's dev entry (URL form K37).
- **Send to Story entry:** each case is posted to the dev-only **wrapper story** (Webhook → Send to Story into the story under test → Exit), built with the story and never shipped (URL form K37); events are read with `./scripts/tines runs`.
- Verify never needs `/mcp`, so nothing changes the export that was just verified.
- Model-graded trials run the dev story's AI Agent actions and spend **dev-team credits**; `./scripts/sdlc estimate --check` counts them (cost.9).

## Inputs (paths in the input envelope)

`sdlc/work/<slug>/evals/cases.yaml`, `stories/<slug>/tests/**`, the dev export; the contract's `risk` and `qa_guidance`.

## Outputs and definition of done

- Findings: one `eval.case_failed` per failing case (`major`; `blocker` for a failing regression case).
- Payload: `verdict` · `results[]{case_id, suite, kind, trials, passes, pass, observed_summary}` · `pass_k{k, value}` · `credits_observed[]{action, credits_used, input_tokens, output_tokens, model}` · `human_verification_prompt`.
- **Done when** every case has a result and the verification prompt is self-contained (what to open in Tines, what to look for, what counts as pass).

## Tools

`Read, Grep, Glob, Bash(./scripts/sdlc eval-run *), Bash(./scripts/tines runs *), Bash(./scripts/tines action-logs *)`.

## Human touchpoints

- `eval-run` and `apply` ask first.
- **The QA sign-off is a person's:** the PR's Lifecycle line **QA verification: pass/fail · by <role>**, their verdict on the verification prompt. `sdlc.yml` requires it on a G4 PR.

## Handoffs

→ `verify-merge` → the build PR (G4).

## Never

- Edit the story under test.
- Run against production.
- The common list (§5.2).
