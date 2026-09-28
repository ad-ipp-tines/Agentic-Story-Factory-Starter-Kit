# Role card — `retro_writer` (Tines-side, 07 improve)

_Spec: REPO-DESIGN.md §5.3.13, §4.4 (07 improve), §7.6 D6. Instructions: [`runtime/retro-writer/system-instructions.md`](runtime/retro-writer/system-instructions.md) · Output schema: [`runtime/retro-writer/output-schema.json`](runtime/retro-writer/output-schema.json) · Skill: [`tines-skills/story-retrospective/`](../../tines-skills/story-retrospective/SKILL.md) · Evals: [`../evals/agents/runtime-retro-writer.cases.yaml`](../evals/agents/runtime-retro-writer.cases.yaml), [`../evals/skills/story-retrospective.cases.yaml`](../evals/skills/story-retrospective.cases.yaml)._

## Mission

Draft each live story's retro from what actually happened — ops findings and alerts, lifecycle events, credits against the estimate — so failures become eval cases and repeated lessons become skill changes (P15).

## Where and how it runs

AI Agent action `retro_writer`, **Task mode**, `[KIT] 00` section D (D6).

| Setting | Value |
|---|---|
| Tools | **none**; no credentials |
| Model | the **fast** model, pinned on the action and recorded in meta |
| Temperature · timeout · retries | 0.2 · 60 s · 2 |
| Skill | `story-retrospective`, attached `[BY HAND]` |
| Token alert | Notify, then Disable action `[BY HAND]` |
| Budget | `budget_ref: kit-factory/retro_writer`; `sdlc_limits.runtime.retro_writer.runs_per_day_max` |

**Trigger (deterministic):** 7 days after `live_since` (git-owned, written by `sdlc advance` from the ship evidence and brought into Records by Flow 1), then every `retro_cadence_days` (30), or on entering improve (`runtime_dispatch.on_enter.improve`; D9 `improve_check` moves a story to improve on a high or critical finding, credits above 1.5 × the estimate, or a retro due). Kill switch and daily cap first (D2).

## Inputs (built by `ops_evidence`, never fetched by the agent)

The story's `ops_findings` and `ops_alerts` rows for the window (fields only, filtered on the row's git-owned `prod_story_id`, by the type ids in `kit_config`), its `sdlc_events` gate history and credit rows, and the design estimate.

## Output

`{window{from, to}, what_happened[], failure_modes[]{category, count, evidence_refs[]}, eval_case_suggestions[]{title, input_ref, expected}, skill_suggestions[]{skill, change, evidence_refs[]}, cost_variance{estimate, actual, ratio}, keep_or_change: keep|change|retire_candidate, needs_human, confidence}`.

## After the agent

`retro_ok` → `save_retro` (the `retro` ARTIFACT, `specialist_status: proposed`, `pending_repo_sync: true`) → `log_run` → `notify`. The tracker PR writes `sdlc/work/<slug>/retro.md` (front matter: `keep_or_change`, `skill_suggestions`, `cost_variance`, `curated: false`, `closed: false`); a person completes it on `improve/<slug>`; then `eval-curator` and, when there are skill suggestions, `skill-curator` run repo-side.

## Human touchpoints

The person completes the retro, confirms or overrides `keep_or_change`, and sets `closed: true`. `change` opens a new design iteration; `retire_candidate` opens G7 (owner + platform decide).

## Never

- Invent a row, a count, a date or a credit figure.
- Propose a skill change from a single event.
- Copy payloads, IPs, addresses or messages into the draft.
- Hold a tool or a credential.
