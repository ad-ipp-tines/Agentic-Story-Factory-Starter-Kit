# 04 · verify — layered, independent verification

_Phase `verify` in [`state-machine.yaml`](../lifecycle/state-machine.yaml) · Gate out: [G4](../gates/G4-verify-and-merge.md) (deterministic + model + human) · Spec: REPO-DESIGN.md §4.4 (04 verify), §5.3.5–§5.3.8, §6.2._

## Purpose

Check the build with layers that each catch what the others miss (P12), none of them the builder (P11): lint → `storyline.yml` → reviewers in fresh contexts → QA evals against the dev story → a CODEOWNER → a human merge → the change request later.

## Entry criteria

`build_evidence` has passed and `storyline advance` has written `build → verify` on `story/<slug>/<short>`.

## Work

1. **In the editor, before the PR**, the showrunner fans out in fresh contexts, in one turn (`storyline next` returns `parallel: true`):
   - `tines-reviewer` — conventions, through the reused `/tines-review` (`context: fork`); its output is the reused `findings-schema.json`, which `apply` accepts as-is (`--schema findings`).
   - `security-reviewer` — the threat model (checks `sec.1`–`sec.10`), **only when** the dispatch condition holds: the contract names egress hosts, credentials or AI agents, is a Mode 4 server, or opens any access wider than the team ([`dispatch-rules.yaml`](../lifecycle/dispatch-rules.yaml), `conditional`).

   Beside them, **not an agent**: `./scripts/storyline estimate <slug> --check` runs the cost checks `cost.4`–`cost.9` deterministically (REPO-DESIGN.md §5.3.7).
2. **Then `story-qa`** runs the eval set against the **dev** story with `./scripts/storyline eval-run <slug> [--k 3]`, which refuses `TINES_ENV=prod`:
   - a Webhook entry: each case is posted to the story's dev entry and the resulting runs and logs are read (URL form VERIFY K37);
   - a Send to Story entry: each case is posted to the dev-only wrapper story's Webhook, and the resulting events are read through `./scripts/tines runs`.

   Deterministic cases must all pass. Model-graded cases run *k* trials (default 3) and must reach pass^k = 1 where consistency matters (customer-facing or side-effecting). QA also records `credits_used`, tokens and model per case from the AI Agent event metadata, and writes a self-contained **human verification prompt**: what to open in Tines and what to look for.
3. **`./scripts/storyline apply <slug> verify-merge`** (ask) merges the verdicts **deterministically** into `verify-report.json` ([schema](../templates/verify-report.schema.json)): any `blocker` or `major` finding — including a failing case (`eval.case_failed`) or a cost check that fails (`cost.N`) — makes the result `changes_requested`; a crew member that returned `needs_human` or `blocked`, or failed its schema twice, makes it `blocked` (GX).
4. **On `pass`**, `./scripts/storyline advance <slug>` writes the tracker change `phase: ship, status: awaiting_gate, open_gate: G5a|G5b` on the branch, and the **build PR** opens: the scaffold's template plus the **Lifecycle** section (story key · phase · gate · rework attempt n/3 · **QA verification: pass/fail · by <role>** · link to `storyline/work/<slug>/`). The QA verification line is the human's verdict on `story-qa`'s verification prompt, and `storyline.yml` requires it.
5. `storyline.yml` (the one required check) runs `storyline check --all`, the touch set by branch prefix, the tracker `rev` rule, `estimate --check`, the QA line, and calls `lint.yml` and `review.yml` when their path filters match. A CODEOWNER reviews and a human who is not the author merges: **G4**.

## Rework

`changes_requested` makes `apply` write a **rework package** to `.storyline/out/<slug>/rework-<n>.json` ([schema](../templates/rework-package.schema.json)): the failing gate, attempt n, every finding with its path, rule, severity and `suggested_prompt`, the failing cases, and the prior attempts. The row goes to `build/rework` and the builder reads the package first.

The builder and the reviewers share **one cap of 3 rework cycles** (`caps.rework_cap`). At the cap the story opens **GX** (`status: blocked`). A human "request changes" on the PR resets the cap.

## Exit criteria

- `verify-report.json` for the current attempt says `pass`.
- The build PR is merged by a human who is not its author, with `storyline.yml` green and a CODEOWNER review.

## Artifacts

| Artifact | Path | Written by |
|---|---|---|
| Verify report | `storyline/work/<slug>/verify-report.json` | `apply verify-merge` (code, not a model) |
| Raw verdicts | `.storyline/out/<slug>/<agent>-<attempt>.json` (local) | `apply` |
| QA results | `.storyline/out/<slug>/qa-*.json` (local) | `eval-run` |
| Rework package | `.storyline/out/<slug>/rework-<n>.json` (local) | `apply verify-merge` |

## Templates

[`verify-report.schema.json`](../templates/verify-report.schema.json) · [`rework-package.schema.json`](../templates/rework-package.schema.json)

## Crew

| Crew member | Tier | maxTurns | Runs |
|---|---|---|---|
| `tines-reviewer` (reused, unchanged) | inherit | — | always, via `/tines-review`; `review.yml` runs the same reviewer headless on the PR |
| `security-reviewer` | strong | 15 | only when its dispatch condition holds |
| `story-qa` | standard | 20 | always, after the reviewers are applied |
| cost checks (a script) | — | — | always: `./scripts/storyline estimate --check` |

Role cards: [`storyline/crew/`](../crew/README.md).

## Gate

**[G4 — verify and merge](../gates/G4-verify-and-merge.md)**: CI green + CODEOWNER review + human merge. Model checks are never a gate on their own.

## Failure modes

| Symptom | Cause | What happens |
|---|---|---|
| A reviewer's output is not a valid baton | format drift | the showrunner asks once more; a second invalid output opens GX |
| QA cannot reach the dev entry | the Webhook URL form or the wrapper story is missing (K37) | `eval-run` fails; the builder adds the wrapper story or the URL is fixed; QA re-runs |
| A model-graded case passes 2 of 3 trials | the prompt or schema is not tight enough | pass^k < 1 → a `major` finding where consistency matters → rework |
| `storyline.yml` rejects the PR's `rev` | another tracker PR merged first | rebase; the script re-computes `rev` as `main`'s rev + 1 |
| The QA verification line is missing | the human did not do the check | `storyline.yml` fails the PR until the line is filled in |
