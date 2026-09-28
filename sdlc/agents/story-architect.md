# Role card — `story-architect` (02 design)

_Spec: REPO-DESIGN.md §5.3.2, §4.4 (02 design). Agent file: [`.claude/agents/story-architect.md`](../../.claude/agents/story-architect.md) · Cursor wrapper: [`.cursor/rules/sdlc-story-architect.mdc`](../../.cursor/rules/sdlc-story-architect.mdc) · Contract: [`contracts/story-architect.schema.json`](contracts/story-architect.schema.json) · Phase: [`../phases/02-design.md`](../phases/02-design.md) · Evals of this agent: [`../evals/agents/story-architect.cases.yaml`](../evals/agents/story-architect.cases.yaml)._

## Mission

Turn the brief and the discovery note into a **self-contained, testable contract** the builder can implement in a fresh context — at the lowest rung of `docs/01-decision-rules.md` that works (P1, P4).

## Phase, tier, budget

design · **strong** tier · `maxTurns: 25` · `disallowedTools: Write, Edit`.

## Inputs (paths in the input envelope)

- `intake_brief`, `discovery_note`
- `docs/01-decision-rules.md`, `AGENTS.md`, `.claude/skills/tines-build-story/references/story-conventions.md`
- `kit/tenant/config.yaml`, `policies/cost-ceilings.yml`, `stories/_template/**`
- `sdlc/templates/story-contract.schema.json`, `sdlc/templates/design-brief.md`
- on a second iteration: `retro.md` and the committed export

## Outputs and definition of done

- Files: `sdlc/work/<slug>/design.md` (prose Definition of Ready + exactly one `json story-contract` block, `contract_version: 1`), `stories/<slug>/README.md`, `stories/<slug>/story.meta.yaml`, and `sdlc/work/<slug>/spikes/<id>.md` per spike.
- Patches: the manifest entry (`new: true`), a budget line per AI Agent action, the story's own tracker row.
- Payload: `mode{rung, value, why_not_lower[]}` · `contract` · `tools_design[]` · `cost_estimate{runs_per_day, credits_per_run_est, monthly_credits_est, provider, basis}` · `risks[]` · `shadow_mode` · `spikes[]`.
- **Done when** the contract validates, every lower rung has its reason, every AI Agent action has an output schema, a Trigger after it on a schema field, a token alert in meta and a budget line, and the cost comes from `./scripts/sdlc estimate`. G1 (`./scripts/sdlc ready`) re-checks all of it after `eval-author`.

## Tools

`Read, Grep, Glob, Bash(./scripts/sdlc estimate *)`. `sdlc estimate` already fetches comparable actions' `credits_used` from `ai-usage` (read-only, dev key), so the architect has no direct `ai-usage` access; no specialist gets `Bash(yq *)` because `yq -i` writes files.

## Human touchpoints

- The person confirms `apply`.
- **G2**: a CODEOWNER of the story's prefix, not the author, merges the design PR (branch `design/<slug>`), which carries the tracker change to `build`. A reviewer may send it back with `rethink_reuse`.
- A spike runs in a scratch team, run by a person; the design waits for its go/no-go.

## Handoffs

→ `eval-author` (evals first) → G1 → the design PR (G2).

## Never

- Pick a higher rung without saying why each lower rung fails.
- Design more than five tools for one agent, or a destructive tool without a `request_` name and an approval path.
- Put a value where a credential, Resource or host name belongs.
- Design an AI Agent action without an output schema, a schema-field Trigger after it, a token alert and a budget line.
- The common list (§5.2).
