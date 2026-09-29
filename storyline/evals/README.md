# Evals — define quality before building

_Spec: REPO-DESIGN.md §4.1 (P2, P15, P23, P24), §4.4 (02 design, 04 verify, 07 improve), §5.3.3, §5.3.8–§5.3.10. Graduation and the regression bar: [`regression/README.md`](regression/README.md)._

An eval case is an input plus a check on what the story (or an agent) did with it. Cases are written **before** the build, from the acceptance criteria, and they are the build's definition of done.

## Three kinds of eval, in three places

| What is evaluated | Cases live in | Written by | Run by |
|---|---|---|---|
| **A story** | `storyline/work/<slug>/evals/cases.yaml` (shape: [`templates/eval-cases.yaml`](../templates/eval-cases.yaml)) + payloads in `stories/<slug>/tests/` | `eval-author` (design), `eval-curator` (improve) | `story-qa` through `./scripts/storyline eval-run <slug> [--k 3]`, against the **dev** story, in 04 verify |
| **The IDE crew** (`story-scout`, `story-architect`, `security-reviewer`, …) | `storyline/evals/agents/<agent>.cases.yaml` | the kit maintainers; `skill-curator` proposes additions | `storyline-evals.yml`, headless, on dispatch and on PRs that touch `.claude/agents/**`, `storyline/crew/**` or `tines-skills/**` (K34) |
| **The Tines-side agents and the Tines Agent Skills** | `storyline/evals/agents/runtime-*.cases.yaml`, `storyline/evals/skills/<skill>.cases.yaml` | the kit maintainers; `skill-curator` proposes additions | `./scripts/storyline eval-run` against the dev copy of `kit-launch` (the D10 `specialist_test` Webhook) and the dev AI Agent actions the skills are attached to — a headless Claude Code run exercises a different runtime and certifies nothing about them |

## The rules

1. **Evals first.** G1 fails without them: every acceptance criterion maps to at least one case, and there is at least one should-not case. The builder's acceptance is `tests/expectations.yaml` plus the deterministic cases.
2. **Both halves.** Cases cover what should happen (`should_trigger: true`) and what should not (`should_trigger: false`: the guard refuses, the filter drops, nothing acts). A suite with only happy paths rewards a story that does too much.
3. **Unambiguous.** Each case is one that two experts would grade the same way. A model-graded case carries a rubric stated as observable properties, and a reference output that passes it.
4. **Deterministic where possible.** Grade by code — events fired, actions not fired, result keys and values, error logs — whenever the outcome is observable that way. Model-graded cases are for judgement a rule cannot express (a summary's faithfulness, a proposal's reasoning), and they cost dev-team credits (below).
5. **Real, sanitised data.** Cases come from captured dev payloads with every identifier replaced: documentation-range IPs (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), `*.example.invalid` addresses, placeholder ids. Never a real payload (P23).
6. **Inputs are untrusted.** A case whose input contains an instruction ("ignore previous rules") is a good case: the pass condition is that the story or agent treats it as data (P16).
7. **Never against production.** `eval-run` refuses `TINES_ENV=prod`. A Webhook entry is posted in the dev team; a Send to Story entry is reached through the dev-only wrapper story (URL form VERIFY K37). Verify never needs `/mcp`.

## Capability and regression

- **Capability** cases describe what the story should be able to do. New cases start here, including the ones that fail today because a production failure just revealed a gap.
- **Regression** cases describe what it must never stop doing. A capability case **graduates** once it is stable; after that the bar is nearly 100 % and a failure is a `major` finding at G4 and an improve trigger in operate. See [`regression/README.md`](regression/README.md).

Both suites live in the same file; the `suite` field says which.

## pass^k

A model-graded case runs **k** trials (default 3, `thresholds.eval_k_default`).

- A case **passes pass^k** only when **all k** trials pass. (Its looser cousin, pass@k — at least one of k passes — measures whether something is possible at all; it is useful when exploring a capability and never used as a gate here.)
- The suite's **pass^k value** is the share of model-graded cases whose k trials all passed; `verify-report.json` records it as `qa.pass_k {k, value}`, and `null` when the story has no model-graded case.
- **Where consistency matters — a customer-facing or side-effecting story — pass^k must be 1.** Anything less is a `major` finding and a rework.

Deterministic cases run once and must all pass.

## What evals cost

Model-graded trials run the dev story's AI Agent actions and spend **dev-team credits**: cases × k × credits per run. `./scripts/storyline estimate --check` counts that against the dev team's ceiling (`cost.9`) at G1 and again at G4, and `story-qa` records `credits_used`, tokens and model per case from the AI Agent event metadata, so the next estimate is observed rather than guessed.

## Held-out cases (agents and skills)

A change to a crew member's prompt, a Tines Agent Skill, the prompt pack or the logbook is proposed from evidence (a retro, failing cases). It is **validated on different cases**: the change lists its `held_out_cases[]`, which must not be among its `evidence_refs`, and `storyline-evals.yml` runs those. `storyline.yml` fails a skill PR whose skill has no held-out cases file in `storyline/evals/skills/` (P24).

## Where evals come from after launch

The improve phase: `retro_writer` drafts the failure modes from `ops_findings` → the human completes the retro → `eval-curator` turns each failure mode into a capability case with `from_evidence_ref` → once stable it graduates. Production failures become eval cases (P15).
