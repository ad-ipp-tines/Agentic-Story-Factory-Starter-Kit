---
# Machine-read keys. The contract itself is the fenced block below, not this front matter.
story_key: <slug>
iteration: 1                           # 1 for the first design; +1 for each design after improve or a G7 re-scope
---

# Design brief — `<slug>` · [PREFIX] NN · Verb noun

_Template: `storyline/templates/design-brief.md` · Phase: `storyline/phases/02-design.md` · Written by `story-architect` through `./scripts/storyline apply` · Gates out: G1 (deterministic, `storyline/gates/G1-readiness.md`), then G2 (human: the design PR merge, `storyline/gates/G2-design-approval.md`)._

> This file has two parts. The **prose** is the Definition of Ready a person reads at G2. The **contract** is exactly one fenced block with the info string `json story-contract`, validated against `storyline/templates/story-contract.schema.json` by `./scripts/storyline apply` and by G1. The builder implements the contract; anything not in it is out of scope. A second fenced block with that info string is an error.

## 1. What we are building and why

<Two or three sentences from the intake brief and the discovery note: the problem, the reuse decision, the outcome.>

## 2. The rung, and why not lower

Rung <n> of `docs/01-decision-rules.md`. For each lower rung, one sentence on why it cannot do the job. A higher rung without that sentence fails review (P1).

## 3. Shape

<The storyboard in words: entry → normalize → guard → work → result / refused / error. Name every action as the contract's `actions_outline` does. For an AI Agent action: its task, its output schema, the Trigger after it and the schema field it branches on.>

## 4. Risks, shadow mode, data

<Side effects and their approval path; whether the story starts in shadow (it must if it acts on another system); the data class and where it flows.>

## 5. Cost

<From `./scripts/storyline estimate <slug>`: runs per day × credits per run × 30, the comparables used, the provider. "0 — no AI Agent action" is a valid answer and the cheapest one.>

## 6. Spikes (only if a VERIFY item blocks a decision)

<Each spike is its own file under `storyline/work/<slug>/spikes/`, from `storyline/templates/spike.md`. The design is not final until each spike's go/no-go is recorded.>

## 7. Definition of Ready (what G1 checks, and what the G2 reviewer confirms)

- [ ] The contract block below validates.
- [ ] At least one acceptance criterion is testable from a run's events, logs or result.
- [ ] Every criterion maps to at least one case in `evals/cases.yaml`, and at least one case is a should-not case.
- [ ] Credentials and Resources are named in `stories/<slug>/story.meta.yaml` (names only).
- [ ] Every AI Agent action has a `budget_ref`, and that line exists in `policies/cost-ceilings.yml`.
- [ ] `stories/_manifest.yaml` has an entry for the slug (`new: true`).
- [ ] The contract's needs fit the tenant's entitlements (`kit/tenant/config.yaml`).
- [ ] Every changed path is inside the design touch set (`storyline/lifecycle/touch-sets.yaml`).
- [ ] `./scripts/storyline estimate <slug> --check` passes.
- [ ] The GB check passes, counting the verify-phase eval-run cost (cases × k × credits per run) against the dev team's ceiling.
- [ ] (G2, human) The rung is the lowest that works; out-of-scope is explicit; nothing here needs a production write without an approval path.

## 8. Contract

```json story-contract
{
  "contract_version": 1,
  "story_key": "<slug>",
  "title": "[PREFIX] NN · Verb noun",
  "summary": "<one or two sentences a reviewer can hold the build to>",
  "tier": "production",
  "mode": { "rung": 1, "value": "none", "why_not_lower": [] },
  "acceptance_criteria": [
    { "id": "AC-1", "given": "<state>", "when": "<event arrives>", "then": "<observable outcome>" }
  ],
  "entry": { "type": "webhook", "action": "<entry_action>", "fields": [ { "name": "<field>", "required": true } ] },
  "actions_outline": [
    { "name": "normalize", "type": "Event Transform", "does": "DEFAULT() on every entry field" },
    { "name": "result", "type": "Event Transform", "does": "message-only exit with 3-5 fields" },
    { "name": "error", "type": "Event Transform", "does": "{status, error_category, retryable, message}" }
  ],
  "credentials": [],
  "resources": [],
  "records": [],
  "egress_hosts": [],
  "ai_agents": [],
  "tools_design": [],
  "access": { "page": { "level": "none" }, "webhook": { "level": "secret" }, "mcp_server": { "level": "none" } },
  "risk": { "side_effects": false, "shadow_mode": false, "data_sensitivity": "internal" },
  "out_of_scope": ["<what this story will not do>"],
  "touch_set": ["storyline/work/<slug>/**", "stories/<slug>/**"],
  "cost_estimate": { "runs_per_day": 0, "credits_per_run_est": 0, "monthly_credits_est": 0, "provider": "none", "basis": "no AI Agent action" },
  "qa_guidance": "<what to open in Tines after the eval run, and what to look for beyond the cases>"
}
```
