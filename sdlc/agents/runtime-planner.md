# Role card — `planner` (Tines-side, backlog level)

_Spec: REPO-DESIGN.md §5.3.11, §6.4, §7.6 D5. Instructions: [`runtime/planner/system-instructions.md`](runtime/planner/system-instructions.md) · Output schema: [`runtime/planner/output-schema.json`](runtime/planner/output-schema.json) · Skill: [`tines-skills/backlog-planning/`](../../tines-skills/backlog-planning/SKILL.md) · Evals: [`../evals/agents/runtime-planner.cases.yaml`](../evals/agents/runtime-planner.cases.yaml), [`../evals/skills/backlog-planning.cases.yaml`](../evals/skills/backlog-planning.cases.yaml)._

## Mission

Keep the backlog pointed at the onboarding milestones: rank the stories, propose owner, target-date, credit-band and mode-hint changes, and flag milestone risk — as proposals a person accepts or rejects one by one.

## Where and how it runs

AI Agent action `planner`, **Task mode**, in `[KIT] 00 · Run the story factory`, section D (D5).

| Setting | Value |
|---|---|
| Tools | **none**; no credentials |
| Model | the **fast** model, **pinned on the action** (its skill counts as an agentic capability; unpinned, the default would be the smart model) and recorded in `stories/kit-factory/story.meta.yaml` |
| Temperature · timeout · retries | 0.2 · 60 s · 2 |
| Skill | `backlog-planning`, attached `[BY HAND]` |
| Token alert | Notify, then Disable action, on the Status tab `[BY HAND]` |
| Budget | `budget_ref: kit-factory/planner`; `sdlc_limits.runtime.planner` (`runs_per_day_max`, `credits_per_run_max`, `debounce_minutes`) |

**Trigger (deterministic):** a backlog change, debounced by `sdlc_limits.runtime.planner.debounce_minutes` (default 60) through a compare-and-swap on `kit_state.planner_last_run`, or the weekly schedule branch (`runtime_dispatch.on_schedule.planner.weekly_day`). Before any model call: the kill switch (`sdlc_limits.enabled` and `guards_confirmed`) and the daily cap (a Records API aggregate count; request body K35).

## Inputs (built by the story, never fetched by the agent)

Backlog snapshot (keys, titles, phases, modes, owners, target dates, estimates, open gates), milestones, entitlements, the team's monthly ceiling, the WIP limit, and previously rejected proposals so they are not repeated.

## Output

`{sequence[]{key, rank, why}, proposals[]{key, field: owner|target_date|credit_band|mode_hint, value, rationale}, milestone_risks[]{milestone_id, risk, evidence}, needs_human, confidence}`.

## After the agent

`planner_ok` (a Trigger on schema fields) → Records API Update per key (`proposal` JSON, `specialist_status: proposed`) → an `sdlc_events` row with the event's model, tokens and `credits_used` → a notification. A person accepts or rejects each proposal on the Page or the App; accepted fields are written with `pending_repo_sync: true` and `pending_base_rev` = the row's `rev`, and reach git only through the tracker PR a person merges (§6.5). A schema failure or `needs_human: true` ends with a person (D8).

## Human touchpoints

Every proposal (accept or reject); the tracker PR merge; the token alert and skill attachment `[BY HAND]`; `sdlc_limits.enabled` and `guards_confirmed`, set by a person after those.

## Never

- Change a phase, status, gate, attempt or link — the schema allows only four proposal fields.
- Hold a tool or a credential.
- Repeat a rejected proposal, invent a key or a number, or name a person as an owner.
- Run when the kill switch is off or the cap is reached (the story enforces both).
