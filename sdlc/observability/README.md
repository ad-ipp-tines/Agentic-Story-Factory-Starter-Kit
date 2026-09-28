# Observability — what is logged where, and how to read a story's trail

_Spec: REPO-DESIGN.md §6.5 (Events), §4.1 P14 (observe decisions, tool calls, outcomes and cost), §13 row 14 (audit). The event shape is [`event.schema.json`](event.schema.json)._

## What is logged where

| Log | Where | Written by | Holds | Leaves the tenant? |
|---|---|---|---|---|
| **Lifecycle events** | `sdlc/work/<slug>/events.jsonl` (git, append-only) | every write through `./scripts/sdlc` and `./scripts/kit tracker-fold`; the G5 evidence step | transitions, gate decisions, specialist runs, syncs, conflicts, budget parks, escalations | it is in git |
| **`sdlc_events` Records** | Tines, ops team | `[KIT] 00` sections B–E | the same shape; Tines-side runs with `credits_used`, tokens and model; `actor_ref` (the approver's email, in-tenant only) | no — the queryable projection the dashboard reads |
| **MCP activity mirror** | `.tines/mcp-activity.jsonl` (local) | `guard-mcp.sh`, on every `mcp__tines__*` call | one line per Tines Stories MCP server call from this editor | no |
| **Tines audit logs** | Tines (MCP activity rows included) | Tines | every tool use of the Tines Stories MCP server, as the user | via the native audit-log export (POLICY §2 rule 6) |
| **AI Agent event metadata** | Tines, per run | Tines | model, input and output tokens, `credits_used` | copied into `sdlc_events` by section D, and into `.sdlc/out/<slug>/qa-*.json` by `eval-run` |
| **AI usage** | `GET /api/v1/ai_usage` via `./scripts/tines ai-usage` | Tines | credits by story, team, action or day; `billed_cost` on a custom provider | read by `sdlc estimate`, `drift.yml`'s budget job, the App's cost view |
| **Raw specialist outputs** | `.sdlc/out/<slug>/<agent>-<attempt>.json` (local, gitignored) | `./scripts/sdlc apply` | the exact envelope each specialist returned | no |
| **PR history** | GitHub | people and CI | every design, build, tracker, improve and rollback PR; the G2 and G4 merges | it is GitHub |
| **Setup report** | `kit/tenant/setup-report.json` | `[KIT] 00` A29 | the day-1 provisioning result | it is in git |

**Why two event logs.** Git is the system of record; the Records are the projection that dashboards and runtime specialists query, and the inbox for decisions made in Tines (REPO-DESIGN.md §6.5). Transitions reach `sdlc_events` through Flow 1 (section B, B8). **IDE-side specialist runs stay in `events.jsonl` only**: they spend the editor's plan, not Tines credits. **Tines-side runs are logged directly in `sdlc_events`**, with each run's `credits_used`, and reach `events.jsonl` through the tracker PR.

## The rules every event follows

- **Append-only.** Nothing rewrites or deletes a line; `sdlc.yml` fails a PR that changes an existing line of any `events.jsonl`. A mistake is corrected by a new event.
- **UTC**, always with `Z` (Records drop offsets).
- **Roles, never people.** `actor` is a role, a team slug, a specialist's name or a script's name. An email never reaches git; the in-tenant `actor_ref` stays in Tines.
- **No secrets, no URLs with secrets.** `refs` holds repo paths, PR numbers, change-request ids and Record ids.
- **One event per write.** A command that changes the tracker writes exactly one event for that change.
- **`tracker_rev`** is the row's `rev` the event produces (see [`GLOSSARY.md`](../GLOSSARY.md), rev). Several events on one branch share the rev that branch will land as.

## The event catalogue — who writes which event

| Writer | When | `event_type` | Fields that matter |
|---|---|---|---|
| `./scripts/sdlc intake` | a repo-side use case | `transition` | `from_phase: null`, `to_phase: intake`, `actor` = owner role, `actor_kind: human` |
| `./scripts/kit tracker-fold` | a Tines-side change reaches git | the events Tines logged for the story (below), plus one `sync` per story changed | `sync`: `refs` = the pull run; `conflict` when a pending change's `base_rev` is behind and the same field changed in git |
| Tines section D (via tracker-fold) | `brief_writer` / `planner` / `retro_writer` ran | `specialist_run` | `agent`, `actor_kind: agent`, `model_tier: fast`, `model_reported`, `credits_used` |
| Tines section C (via tracker-fold) | a G0, G6, G7, GX decision or an unpark on the Page | `gate_decision` | `gate`, `decision`, `from_phase`, `to_phase`, `actor` = the approver's role, `actor_kind: human` |
| Tines section D, D9 (via tracker-fold) | an improve trigger | `transition` | `from_phase: operate`, `to_phase: improve`, `decision: improve_trigger`, `actor_kind: story`, `summary` names the trigger |
| `./scripts/sdlc apply <slug> <agent>` | a specialist's output is applied | `specialist_run` | `agent`, `decision` = the envelope verdict, `model_tier`, `model_reported`, `turns`, `actor_kind: agent`; an `escalation` (gate GX) instead when it returned `needs_human` or failed its schema twice |
| `./scripts/sdlc start` | the build starts | `specialist_run` | `agent: tines-builder`, `decision: started`, `actor: sdlc start`, `actor_kind: ci` — the "build start event" the check `build_evidence` compares against |
| `./scripts/sdlc apply <slug> tines-builder` | the builder's report is saved | `specialist_run` | `agent: tines-builder`, `decision: finished`, `actor_kind: agent`, `refs: [build-log.md]` |
| `/sdlc-gate` → `./scripts/sdlc gate` | a repo-side human decision | `gate_decision` | `gate`, `decision`, `actor` = the `--by` role, `actor_kind: human`; `from_phase`/`to_phase` when it moves the story |
| `./scripts/sdlc apply <slug> verify-merge` | the verdicts are merged | `specialist_run` | `agent: verify-merge`, `decision: pass \| changes_requested \| blocked`, `actor_kind: ci`; plus a `transition` `verify → build` (gate G4, `changes_requested`) on rework, or an `escalation` at the cap |
| `./scripts/sdlc advance` | a check passes or gate evidence is present | `transition` | `decision` = the check name, or the gate's decision word; a merge-carried transition (G2, G4) has `actor_kind: human` and takes effect when the PR merges |
| `./scripts/sdlc advance` (GB) | a budget or WIP park at a boundary | `budget` | `gate: GB`, `decision: park`, `to_phase: parked`, `summary` = which ceiling |
| the G5 evidence step (`ship.yml`, `promote.yml`) | a release is decided | `gate_decision` | `gate: G5a \| G5b`, `decision`, `actor` = the approver's role, `actor_kind: human`, `refs: [ship.md, <change request id>]`, `sha` |

A human decision that moves the story is one `gate_decision` event carrying `from_phase` and `to_phase`; a check or a merge is a `transition` event.

## Reading a story's trail

```bash
./scripts/sdlc status <slug>                                  # phase, status, gate, attempt, last event, evidence
jq -c '[.ts, .event_type, .from_phase, .to_phase, .gate, .decision, .actor] ' sdlc/work/<slug>/events.jsonl
jq -c 'select(.event_type=="gate_decision")' sdlc/work/<slug>/events.jsonl          # every human decision
jq -c 'select(.event_type=="escalation" or .event_type=="conflict")' sdlc/work/<slug>/events.jsonl
git log --oneline -- sdlc/work/<slug>/ stories/<slug>/                               # which PR carried what
jq -c 'select(.input|test("<dev story id>"))' .tines/mcp-activity.jsonl             # this editor's MCP calls for the story ({ts, tool, session, input})
```

`sdlc next` is resume-aware: a fresh session rebuilds where the story is from the tracker row, these events and the evidence on disk and in git (P19).

## Record fields vs event keys

`sdlc_events` carries the same shape with a few Tines-side names — `model` for `model_reported`, `ref` for `refs`, `source_sha` for `sha` — plus `actor_ref`, `input_tokens` and `output_tokens`, which exist only in Tines. The authoritative mapping is `kit/tracker/field-map.yaml`.
