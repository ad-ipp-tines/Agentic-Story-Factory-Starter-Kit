# G4 · Verify and merge — layered checks, then a human merge

| | |
|---|---|
| **Between** | verify → ship |
| **Type** | deterministic + model + human (layered) |
| **Decided by** | `storyline.yml` (which calls `lint.yml` and `review.yml`), `verify-report.json`, the human QA verification line, a CODEOWNER, and a human merge — never the author |
| **Evidence** | PR checks, findings, QA results, the cost projection, the semantic diff |
| **Instrument** | the merge of the build PR from `story/<slug>/<short>` |
| **Recorded** | the merge. The PR carries the tracker change `phase: ship, status: awaiting_gate, open_gate: G5a\|G5b` and the `transition` event |
| **Decisions** | `merged` → ship · `changes_requested` → build (`status: rework`, attempt + 1) while attempt < 3; at the cap → GX |

## The layers (each catches what the others miss, P12)

| Layer | What it is | Blocks when |
|---|---|---|
| `lint.yml` | the scaffold's deterministic lint of the export and meta | any error-level rule fails |
| `storyline.yml` | the one required check: `storyline check --all`, touch set by branch prefix, the tracker `rev` rule, `estimate --check`, the QA verification line, `approvers.yaml` for any `gate_decision` event | any check fails |
| `tines-reviewer` (in the editor) and `review.yml` (headless, on the PR) | the conventions review, in a fresh context, with no MCP and no tenant | a `blocker` or `major` finding |
| `security-reviewer` (conditional) | the threat-model checks `sec.1`–`sec.10` | a `blocker` or `major` finding |
| `story-qa` | the eval set against the **dev** story; pass^k where consistency matters | a failing deterministic case; pass^k < 1 where required |
| cost checks | `./scripts/storyline estimate --check`, a script | a `FAIL` (a `major` finding, `cost.N`) |
| `verify-merge` | the deterministic merge into `verify-report.json` | any `blocker` or `major` → `changes_requested` |
| **QA verification line** | the human's verdict on `story-qa`'s verification prompt: **QA verification: pass/fail · by <role>** in the PR's Lifecycle section | missing or `fail` (`storyline.yml`) |
| CODEOWNER | a person who owns the story's prefix | they request changes |
| **the merge** | a person who is not the author | — |

**Model checks are never a gate on their own.** Their findings feed `verify-merge`; a person merges.

## The merge rule (`./scripts/storyline apply <slug> verify-merge`)

Deterministic and total:

1. Every source's output is validated against its schema. A source that failed its schema twice, or returned `needs_human` or `blocked` → verdict **`blocked`** → GX.
2. Otherwise any finding of severity `blocker` or `major` — from a reviewer, from a failing case (`eval.case_failed`), from a `FAIL` cost check (`cost.N`) — → verdict **`changes_requested`**, and a rework package.
3. Otherwise → **`pass`**.

## Rework

`changes_requested` writes `.storyline/out/<slug>/rework-<n>.json` ([schema](../templates/rework-package.schema.json)) and returns the story to `build/rework` with attempt + 1. The builder and reviewers share one cap of **3** cycles (`caps.rework_cap`); at the cap the story opens [GX](GX-escalation.md). A human "request changes" on the PR resets the cap.
