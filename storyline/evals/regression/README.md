# Regression — how a capability case graduates, and the nearly-100 % bar

_Spec: REPO-DESIGN.md §4.4 (07 improve), §5.3.9. The case shape is [`storyline/templates/eval-cases.yaml`](../../templates/eval-cases.yaml); the wider rules are [`storyline/evals/README.md`](../README.md)._

There is no separate folder of regression cases. A case is a regression case when its `suite` field says `regression`, in the same file it was written in (`storyline/work/<slug>/evals/cases.yaml`, or an agent or skill cases file under `storyline/evals/`). This folder holds the rules.

## What regression means

A **capability** case asks "can it do this?" and is allowed to fail while the story is being improved. A **regression** case asks "does it still do this?" and is not allowed to fail. Regression cases are the story's memory of every mistake it has already been cured of.

## When a capability case graduates

`eval-curator` proposes the graduation (`graduated[]` in its output) in an improve PR; a person merges it. A case graduates when **all** of these hold:

1. **It passed in at least two separate verify runs** — two rework attempts, or two design iterations — and in the latest one.
2. **Model-graded:** it reached pass^k = 1 at k ≥ 3 in each of those runs.
3. **Its rubric and reference output did not change** between those runs. A case whose expectation keeps moving is still being designed.
4. **It is not flaky.** A case that passed only after a re-run in either of those runs waits another run.
5. **It still matters.** The behaviour it checks is still in the contract (not in `out_of_scope`).

## The bar: nearly 100 %

| Case kind | Bar | "Nearly" means |
|---|---|---|
| deterministic | **100 %** — every run | nothing: a deterministic regression failure is real |
| model-graded | **pass^k = 1** at the case's k | one automatic re-run of k trials is allowed for a model-graded regression case before it counts as failed; the re-run is logged in the QA output, and a case that needs it twice in a row is flagged for the retro |

A regression failure is:

- at **G4** (verify): a `major` finding (`eval.case_failed`) → `changes_requested` → rework;
- in **operate**: an improve trigger ("an eval regression", recorded repo-side) → a retro.

## Retiring a regression case

Only with a reason recorded in the retro (the "Eval cases" section) — `eval-curator` never deletes one otherwise. Good reasons: the behaviour moved out of scope in a new design iteration; the case duplicates a stronger one; the input can no longer occur (the entry changed). "It fails a lot" is not a reason: that is a regression. The removal happens in the improve PR, its reason is in the event summary, and the case id is never reused.

## Agents and skills

The same two suites and the same bar apply to `storyline/evals/agents/*.cases.yaml` and `storyline/evals/skills/*.cases.yaml`. A skill or prompt change must keep every regression case passing **and** pass its held-out cases (see [`storyline/evals/README.md`](../README.md), "Held-out cases").
