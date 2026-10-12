# Pivot: the Agentic Story Factory → the 3B Workflow Factory

_Branch `pivot/3b-workflow-factory`. Status: plan. Everything not yet confirmed in a 3B tenant is **VERIFY**._

## Why this reuses well
The repository's thesis — *the value is the system around the prompt* — is product-agnostic. Roughly 70% of the kit (lifecycle, gates, crew, policies, evals, tracker, VERIFY discipline, the guide app) carries over; what changes is the **wire** (Tines Stories MCP → 3B MCP/CLI/editor) and the **artifact** (story JSON → a 3B workflow directory, which is already code and git-native).

3B makes several things simpler than Tines Stories:
- Workflows **are** files (`workflow.toml`, step folders, `config.toml`) — no export/normalise step.
- Draft branches + Push live replace import → named draft → change request.
- **Step tests** (pinned input/output, hermetic replay) are a native verify gate.
- **Skills** are first-class in 3B, so `tines-skills/` becomes a 3B skills pack.

## Mapping
| Story Factory today | 3B equivalent | Reuse |
|---|---|---|
| `stories/**/story.json` + normalize.jq | `workflows/<Workflow>/` space clone | Replace |
| Mode 2 Tines Stories MCP | 3B MCP server / 3B CLI / in-product editor | Replace wire |
| `.claude/skills/tines-*` | `3b-build-workflow`, `3b-review`, `3b-ship`, `3b-rollback`, `3b-connect` | Port |
| `tines-skills/` (Skills API) | 3B space skills (SKILL.md) + evals | Port |
| Crew (`.claude/agents`, `.cursor/rules`) | Same roles, 3B vocabulary | Port |
| lint-story + lint-rules.yml | lint_workflow + config.toml / route_auth / secrets rules | Rewrite |
| Change request approval (G5) | Draft branch → step tests → reviewer → Push live by a named person | Simplify |
| Rollback by re-import | Republish an earlier version (listVersions commit) | Simplify |
| ops-error-router / health monitor | Scheduled 3B workflow + agent step that proposes fixes | Port |
| `[KIT] 00 · Launch Storyworks` | `[KIT] 3B Launchpad` workflow (React kickoff + setup report) | Rebuild |
| Records tracker + dashboard | Volume (SQLite) tracker + 3B dashboard route (optional Cases/Records sync) | Rebuild |
| Storyline lifecycle, gates, PRINCIPLES, VERIFY | Same lifecycle, gates re-pointed | Keep |
| Guide app (3B workflow kzAk6fRAGldc) | Same app, new area notes, roles and diagrams | Keep + retarget |

## Target architecture
1. **Editor layer** — Claude Code / Cursor with AGENTS-3B.md, skills and crew; only the builder subagent holds 3B credentials (OAuth via MCP/CLI).
2. **Repo layer** — workflows, skills, policies, evals, tracker; PRs are the unit of change.
3. **Gate layer** — deterministic lint, non-author review, step tests, security gate on route exposure, named approver on Push live.
4. **Platform layer (3B)** — Launchpad, tracker/dashboard, starter catalog, ops pair; skills distributed to spaces.
5. **Adoption layer** — the guide app, study paths per role, migration lane from Tines stories.

## Delivery phases
0 Foundation → 1 Skills → 2 Gates → 3 Kit → 4 Operate → 5 Adoption. Tasks: [`TASKS.md`](TASKS.md) (mirrored as GitHub issues labelled `3b-pivot`).

## Principles kept
Agents propose, people approve. The generator never approves its own work. No secrets in chat, code or volumes — connectors only. Routes default to space auth; wider exposure is a gated decision. Never invent an endpoint.
