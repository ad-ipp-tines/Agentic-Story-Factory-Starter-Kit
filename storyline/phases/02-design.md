# 02 · design — a self-contained, testable contract, with evals written first

_Phase `design` in [`state-machine.yaml`](../lifecycle/state-machine.yaml) · Gates out: [G1](../gates/G1-readiness.md) (deterministic), then [G2](../gates/G2-design-approval.md) (human) · Spec: REPO-DESIGN.md §4.4 (02 design)._

## Purpose

Turn the brief and the discovery note into a contract the builder can implement in a fresh context without asking anything (P4), with the evals that will judge it written **before** any build (P2).

## Entry criteria

`discovery_complete` has passed and `storyline advance` has written `discover → design` on `design/<slug>`.

## Work

Two crew, one after the other (never at once: both write).

1. **`story-architect`** ([role card](../crew/story-architect.md)) writes `storyline/work/<slug>/design.md` from [`design-brief.md`](../templates/design-brief.md): a prose Definition of Ready plus **exactly one** fenced JSON block with the info string `json story-contract`, which validates against [`story-contract.schema.json`](../templates/story-contract.schema.json). The contract's top-level keys:
   - `contract_version`, `story_key`, `title` (`[PREFIX] NN · Verb noun`), `summary`, `tier`
   - `mode` — `{rung, value, why_not_lower[]}`, value one of `none | sub-story | mode-1-preset | mode-3-agent | mode-4-server`
   - `acceptance_criteria[]` — `{id, given, when, then}`
   - `entry` — `{type: webhook | send_to_story | schedule | page | mcp_server, fields[]}`
   - `actions_outline[]`
   - `credentials[]`, `resources[]` (names only), `records[]`, `egress_hosts[]`
   - `ai_agents[]` — `{name, task_or_chat, tools ≤ 5, output_schema_ref, model_tier, skills[], budget_ref}`
   - `tools_design[]` for Mode 3 and Mode 4 — any name matching `block|delete|isolate|disable`, and any destructive tool, starts with `request_`
   - `access` (Page, Webhook and MCP server levels), `risk` (`{side_effects, shadow_mode, data_sensitivity}`), `out_of_scope[]`, `touch_set`
   - `cost_estimate` — from `./scripts/storyline estimate <slug>` — and `qa_guidance`

   It also drafts `stories/<slug>/README.md` and `story.meta.yaml` from `stories/_template/`, and the allow-listed patches: the manifest entry (`new: true`), the budget line for every AI Agent action, and the tracker row.

2. **`eval-author`** ([role card](../crew/eval-author.md)) writes the tests — `stories/<slug>/tests/sample-event.json`, `tests/cases/<eval_id>.json`, `tests/expectations.yaml` — and `storyline/work/<slug>/evals/cases.yaml` from [`eval-cases.yaml`](../templates/eval-cases.yaml), mapping every acceptance criterion to at least one case and including at least one should-not case. Rules: [`storyline/evals/README.md`](../evals/README.md).

**Spikes.** If a VERIFY item blocks a design decision, the architect proposes a spike (`storyline/work/<slug>/spikes/<id>.md` from [`spike.md`](../templates/spike.md): questions, a hypothesis to falsify, non-goals, go/no-go) that runs in a scratch team before the design is final.

**Readiness, then the PR.**

1. `./scripts/storyline ready <slug>` runs G1 (and GB, including `estimate --check`) and exits 0 or 1 with JSON reasons.
2. On exit 0, `./scripts/storyline advance <slug>` (ask) writes the tracker change `phase: build, status: active` **on the branch**.
3. The design PR opens from `design/<slug>`. `storyline.yml` runs `storyline ready` again on it.
4. A CODEOWNER who is not the author reviews and merges: **that merge is G2**, and the state change lands on `main` exactly when the human approves it.

Until the merge, `main` still shows the row as `discover`; `./scripts/storyline status <slug>` shows both the branch and `main`, and `storyline next` reports G2 as open while the design PR is open.

## Exit criteria

- G1 passes (the checks in [G1-readiness.md](../gates/G1-readiness.md)).
- The design PR (branch `design/<slug>`, touch set `design`) is merged by a CODEOWNER who is not its author.

## Artifacts

| Artifact | Path | Written by |
|---|---|---|
| Design + contract | `storyline/work/<slug>/design.md` | `apply` ← `story-architect` |
| Spikes | `storyline/work/<slug>/spikes/<id>.md` | `apply` ← `story-architect` |
| Eval cases | `storyline/work/<slug>/evals/cases.yaml`, `stories/<slug>/tests/**` | `apply` ← `eval-author` |
| Story folder | `stories/<slug>/README.md`, `story.meta.yaml` | `apply` ← `story-architect` |
| Patches | `stories/_manifest.yaml` (`.stories.<slug>`), `policies/cost-ceilings.yml` (`.agents."<slug>/*"`), the tracker row | `apply` (allow-listed yq paths only) |

## Templates

[`design-brief.md`](../templates/design-brief.md) · [`story-contract.schema.json`](../templates/story-contract.schema.json) · [`eval-cases.yaml`](../templates/eval-cases.yaml) · [`spike.md`](../templates/spike.md)

## Crew

| Crew member | Tier | maxTurns | Tools |
|---|---|---|---|
| `story-architect` | strong | 25 | `Read, Grep, Glob, Bash(./scripts/storyline estimate *)` |
| `eval-author` | standard | 15 | `Read, Grep, Glob` |

The cost checks are a script, not an agent: `./scripts/storyline estimate --check` (REPO-DESIGN.md §5.3.7).

## Gates

- **[G1 — readiness](../gates/G1-readiness.md)**, deterministic.
- **[G2 — design approval](../gates/G2-design-approval.md)**, human: the merge. `rethink_reuse` sends the story back to discover.

## Failure modes

| Symptom | Cause | What happens |
|---|---|---|
| G1 fails: an acceptance criterion has no case | the eval author missed one | `storyline next` dispatches `eval-author` again with the gap |
| G1 fails: no budget line | a new AI Agent action | the architect's patch adds it; `lint.yml` would fail the build PR anyway |
| G1 fails: GB | the estimate plus committed estimates exceed the team's ceiling | the story parks (GB); a human releases it or the design gets cheaper |
| A higher rung without `why_not_lower` | the architect skipped the ladder | the contract schema refuses it (rung ≥ 2 needs at least one reason) |
| A VERIFY item decides the design | the docs do not say | a spike; the design waits for its go/no-go |
| The reviewer disagrees with the reuse decision | discovery missed a candidate | G2 `rethink_reuse` → discover |
