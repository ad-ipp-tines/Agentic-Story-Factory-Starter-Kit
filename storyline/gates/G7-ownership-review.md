# G7 · Ownership review — keep, re-scope or retire

| | |
|---|---|
| **Between** | operate → operate (keep) · design (re-scope) · retired |
| **Type** | human |
| **Decided by** | the owner **and** platform (`approvers.yaml` G7 requires both teams) |
| **Evidence** | usage (runs, callers), findings (`ops_findings`), cost vs estimate (`ai_usage` by story, `storyline_events` credit rows), open retros |
| **Instrument** | the `gate_decision` Page when Records are entitled · `/storyline-gate <slug> G7 keep\|rescope\|retire` only on the Community path |
| **Recorded** | a `gate_decision` event (`gate: G7`) |
| **Decisions** | `keep` → operate (status unchanged) · `rescope` → design, a new iteration (attempt resets to 0) · `retire` → retired |

## When it opens

- **Quarterly, per story.** G7 dates are set by week 4 of onboarding (the week-4 milestone); the governance principle is P25 — the tracker is the catalog, and retire is a lifecycle state.
- **When a retro proposes retirement** (`retro.md` `keep_or_change: retire_candidate`): the story returns to operate with G7 open.

## What the deciders check

1. **Is it still used?** Runs and callers in the last quarter. A story nobody calls is a cost and an attack surface.
2. **Is it still right?** High or critical findings, open retros, eval regressions.
3. **Is it still worth it?** Credits against the estimate; `billed_cost` on a custom provider.
4. **Is there an owner?** A role that answers for it. No owner is a reason to retire.

## After the decision

- `keep` — nothing changes; the next review is in a quarter.
- `rescope` — a new design iteration; the live story keeps running and monitored until the new version ships.
- `retire` — the owner disables the story in Tines `[BY HAND]` after the decision (never through a pipeline; a disable is break-glass only in the scaffold), and a PR marks the row `retired` and removes the story from `stories/_manifest.yaml`. Its folder and `storyline/work/<slug>/` stay as history.
