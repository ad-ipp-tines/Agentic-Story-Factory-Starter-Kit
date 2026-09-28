# Reuse card — `triage` + `critic` (06 operate, Tines-side)

_Spec: REPO-DESIGN.md §5.3.14, §4.4 (06 operate). **The instructions and schemas live in [`stories/ops-story-health-monitor/agent/`](../../stories/ops-story-health-monitor/agent/system-instructions.md), unchanged, and are not copied here:** `system-instructions.md` (both agents), `output-schema.json` (`triage`), `critic-output-schema.json` (`critic`), `tools.md` (the five read-only tools). Story: `[OPS] 10 · Monitor story health and credits` (`stories/ops-story-health-monitor/`)._

## What is reused

The scaffold's operate-phase runtime. The kit adds no second monitor.

| Agent | Mode | Model | Tools | Skills | Output |
|---|---|---|---|---|---|
| `triage` | Task | smart (tools attached) | five read-only Send to Story tools (Mode 3) | `story-health-triage`, `credit-budget-analyst` | an `ops_findings` row: severity, category, evidence, proposed change, `needs_human` |
| `critic` | Task | fast (tool-less, no skill) | none | none | confirms or lowers the triage severity; never raises it |

Both have Output schemas, Triggers after them on schema fields, token alerts and budget lines (`policies/cost-ceilings.yml`: `ops-story-health-monitor/triage`, `…/critic`).

## How the lifecycle uses it

- **Operate.** The ops trio (`ops-error-router`, `ops-story-health-monitor`, `ops-tools-server`) is every production story's monitoring. The sweep's `triage` and `critic` **propose**; humans approve.
- **Improve triggers.** `[KIT] 00` section D (D9 `improve_check`) reads `ops_findings` for each story in operate: a high or critical finding for its `prod_story_id` moves the story to improve (provisional until the tracker PR merges).
- **Retro evidence.** `retro_writer` drafts each retro from the story's `ops_findings` and `ops_alerts` rows. Their categories are the retro's failure-mode categories.
- **Skills.** `story-health-triage` and `credit-budget-analyst` have held-out cases in [`../evals/skills/`](../evals/skills/); changes to them follow the `skill-curator` path.

## Never (in lifecycle terms)

- Apply a change: its proposals go through approval Pages and the scaffold's change control.
- Change a never-touch story (`[OPS]`, `[KIT]`, production ids) — it may only report on one.
