# Verdict merge — how parallel verify verdicts become one result, and the rework package

_Implemented by `./scripts/storyline apply <slug> verify-merge` (ask) — **code, never a model**. The showrunner only runs the command when `./scripts/storyline next` names it. Spec: REPO-DESIGN.md §4.4 (04 verify), §5.3.7; the gate: `storyline/gates/G4-verify-and-merge.md`; the output: `storyline/templates/verify-report.schema.json`; the package: `storyline/templates/rework-package.schema.json`._

Model checks are never a gate on their own. Their findings feed this merge; a person still merges the PR (G4).

## 1. The sources

For the tracker row's current `attempt` = *n*:

| Source | Read from | Shape | When absent |
|---|---|---|---|
| `tines-reviewer` | `.storyline/out/<slug>/tines-reviewer-<n>.json` | the reused `findings-schema.json` (`verdict`, `findings[]`, `cost_notes`) | the merge refuses to run (`reviews_applied` is false) |
| `security-reviewer` | `.storyline/out/<slug>/security-reviewer-<n>.json` | output baton + `security-reviewer.schema.json` payload | `skipped` when `conditional.security-reviewer?` in `dispatch-rules.yaml` does not hold for the contract; otherwise the merge refuses to run |
| `story-qa` | `.storyline/out/<slug>/story-qa-<n>.json` (and `qa-*.json` from `eval-run`) | output baton + `story-qa.schema.json` payload | the merge refuses to run (`qa_applied` is false) |
| `cost-checks` | `./scripts/storyline estimate <slug> --check`, run by the merge itself | one `PASS`/`FAIL` line per `cost.N` + `projection` + `budget_fit` | never absent |

Every file is validated against its schema before anything is read from it.

## 2. Each source's status

Evaluated per source, first match wins:

1. The output failed its schema **twice** (the showrunner asked once more, and `apply` recorded both) → `schema_failed`.
2. The baton verdict is `needs_human` → `needs_human`; `blocked` → `blocked`.
3. The source was not dispatched → `skipped`.
4. Any finding of severity `blocker` or `major`, or its own verdict is `changes_requested` → `changes_requested`.
5. Otherwise → `pass`.

A source whose own `verdict` says `pass` while it lists a `blocker` or `major` finding is treated as `changes_requested` — the findings win over the word.

## 3. The findings

Collected into one list, each tagged with its `source`:

- **tines-reviewer** — its `findings[]` as they are.
- **security-reviewer** — the baton's `findings[]` (rule ids `sec.N`).
- **story-qa** — the baton's `findings[]` (`eval.case_failed`, one per failing case). The merge also checks the QA numbers itself: every deterministic case must have `pass: true`; and where consistency matters — the contract's `risk.side_effects` is true, or its `tier` is `production` (the closest contract field to "customer-facing") — `pass_k.value` must be 1. A shortfall that story-qa did not already report becomes a `major` finding, `rule: eval.pass_k`, `path: storyline/work/<slug>/evals/cases.yaml`.
- **cost-checks** — every `FAIL` line becomes a `major` finding: `rule: cost.N`, `path: stories/<slug>/story.meta.yaml` (or `storyline/work/<slug>/design.md` for cost.5, cost.6 and cost.9, which compare against the contract estimate), `message` = the check's detail line.

Ordering: severity (`blocker`, `major`, `minor`, `info`), then source (`tines-reviewer`, `security-reviewer`, `story-qa`, `cost-checks`), then `path`. Nothing is dropped from `verify-report.json`: two sources reporting the same `path` and `rule` both stay, so the reader sees the agreement.

## 4. The merged verdict — deterministic and total

```
if any source status in {needs_human, blocked, schema_failed}      → verdict = blocked            (GX)
elif any finding severity in {blocker, major}:
    if attempt + 1 > rework_cap (3)                                → verdict = blocked            (GX at the cap)
    else                                                           → verdict = changes_requested  (rework package n+1)
else                                                               → verdict = pass
```

`rework_cap` is `caps.rework_cap` in `storyline/lifecycle/state-machine.yaml`. The builder and the reviewers share it. A person's "request changes" on the PR resets it (the state machine's rule, applied by `./scripts/storyline advance`).

## 5. What the merge writes

| Verdict | `storyline/work/<slug>/verify-report.json` | Local | Tracker row (rev + 1) | Events (`events.jsonl`) |
|---|---|---|---|---|
| `pass` | `verdict: pass`, `rework_package_ref: null`; only `minor`/`info` findings remain | — | unchanged phase; `next` then returns `advance` (verify → ship on the branch) | `specialist_run` (`agent: verify-merge`, `decision: pass`, `actor_kind: ci`) |
| `changes_requested` | `verdict: changes_requested`, `rework_package_ref: .storyline/out/<slug>/rework-<n+1>.json` | the rework package | `phase: build`, `status: rework`, `attempt: n+1` | `specialist_run` + a `transition` verify → build (gate G4, decision `changes_requested`) |
| `blocked` | `verdict: blocked`, `rework_package_ref: null`; `sources[].reason` says why | — | `status: blocked`, `open_gate: GX` | `specialist_run` + an `escalation` (gate GX) |

`verify-report.json` also carries `sources[]` (status, `out_ref`, `findings_count`, reason), `cost_checks` (results, `projection`, `budget_fit`), and `qa` (`cases_total`, `cases_passed`, `pass_k`, `failing_cases`, `credits_observed`), all copied, never re-derived by a model.

## 6. The rework package (`.storyline/out/<slug>/rework-<n+1>.json`)

Local and never committed; the builder's handoff tells it to read this file first. Shape: `storyline/templates/rework-package.schema.json`.

| Field | Built from |
|---|---|
| `failing_gate` | `G4` (a G5a/G5b rejection builds its package in `./scripts/storyline advance`, from `ship.md`, with the approver's note as a finding, `source: approver`) |
| `attempt` | *n* + 1 |
| `source_ref` | `storyline/work/<slug>/verify-report.json` |
| `findings` | only the `blocker` and `major` findings — the must-fix list. De-duplicated by (`path`, `rule`): the highest severity wins, and the first `suggested_prompt` in source order is kept |
| `findings[].suggested_prompt` | the source's own when present; otherwise written by the merge from the finding: `/tines-build-story <slug> "Fix <rule> on <path>: <message> Then validate."` |
| `failing_cases` | from story-qa's `results[]` where `pass` is false: `eval_id`, `kind`, `input_ref` and `expected` (a one-line rendering of the case's `expect`) from `evals/cases.yaml`, `observed_summary` from the result |
| `prior_attempts` | one line per earlier package of this iteration, oldest first (attempt, failing gate, findings count, summary, sha), so a fix that already failed is not repeated |
| `instructions` | the schema's constant: fix only the listed findings and failing cases; each carries a `suggested_prompt`; two failed corrections on one issue — stop (GX); validate, test, export, commit on the same branch |

`minor` and `info` findings stay in `verify-report.json` for the PR reader; they never enter the package, so a rework stays small.

## 7. Worked example

Attempt 0. `tines-reviewer`: `changes_requested`, one `major` — `http_retry_bounds` on `stories/<slug>/story.json#lookup_b` (retries left at the default). `security-reviewer`: `done`, one `info` (`sec.3`: the contract's egress hosts are placeholders). `story-qa`: `done`, 4 of 4 deterministic cases passed, no model-graded case (`pass_k.value: null`). Cost checks: all `PASS`.

- Statuses: tines-reviewer `changes_requested` · security-reviewer `pass` · story-qa `pass` · cost-checks `pass`.
- A `major` finding exists and 0 + 1 ≤ 3 → **`changes_requested`**.
- `verify-report.json`: two findings (the major first); `rework_package_ref: .storyline/out/<slug>/rework-1.json`.
- The package: one finding, with the reviewer's `suggested_prompt` (set `lookup_b`'s retries to 6 with retry on `[429, 500-599]`, then validate); no failing cases; no prior attempts.
- Tracker: `build/rework`, attempt 1. Events: `specialist_run` (verify-merge, `changes_requested`) and `transition` verify → build (G4, `changes_requested`).

`storyline/examples/example-enrich-ip/` shows this sequence end to end.

## 8. What the showrunner must not do here

- Run the merge before `next` names it, or merge verdicts in its head.
- Re-grade a case, soften a finding, or drop a source.
- Write `verify-report.json` or a rework package itself (Write and Edit are denied on `storyline/work/**` and `.storyline/**`).
