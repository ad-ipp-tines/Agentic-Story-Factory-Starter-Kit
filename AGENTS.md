# AGENTS.md — conventions for Tines Stories as Code

Loaded every session by Cursor (natively) and by Claude Code (imported from `CLAUDE.md`). Only what is always true lives here; procedures are skills in `.claude/skills/`. Keep this file under 200 lines.

## 1. What this repo is

- `stories/**/story.json` — normalised exports from Tines — are the truth. The tenant is a deployment target.
- The **dev team** is where builds happen. Production is never edited directly; it is reached only through `ship.yml` (import → named draft → change request → a named person approving in Tines).
- `stories/_manifest.yaml` maps slugs to story ids per environment and holds no secrets. `stories/<slug>/story.meta.yaml` carries what the export does not: credentials and resources by name, monitoring, AI agents, budget references.
- Model Context Protocol (MCP) is the wire between the editor and the tenant. Tines Stories is the product; Tines Classic and Tines Stories mean the same thing here.
- `sdlc/` is the lifecycle every story follows; `kit/tracker/backlog.yaml` holds each story's phase; `./scripts/sdlc` is the only writer of lifecycle state.

## 2. The four modes (the only words we use for the MCP surfaces)

| Mode | Surface | In this repo |
|---|---|---|
| Mode 1 | Workbench calling MCP tools (Workbench → MCP tab → New MCP connection) | Presets may carry `tines-skills/`; not otherwise required |
| **Mode 2** | **The Tines Stories MCP server** at `https://<your-tenant>.tines.com/mcp` — OAuth only | **Authoring from the editor — every build** |
| Mode 3 | The AI Agent action calling tools | The monitoring agent (`stories/ops-story-health-monitor/`) |
| Mode 4 | The MCP server action at `https://<your-tenant>.tines.com/mcp/<mcp-path>` | The ops tools server (`stories/ops-tools-server/`) |

This repo authors in Mode 2. Never use any other word for these surfaces.

## 3. Golden rules

1. **One story at a time.** One story per branch and per PR.
2. **Ask for a plan** before any change bigger than a sentence: a numbered list of actions with type, name and field names. Wait for a yes.
3. **Every build ends with Validate plus a test event** (`tests/sample-event.json` against `tests/expectations.yaml`). Then export, lint, commit.
4. **Never hand-edit `story.json`.** Links reference actions by index; change the story through the Tines Stories MCP server, then `/tines-export`.
5. **Never paste credential values, resource contents or tokens anywhere** — not in prompts, files, commit messages or MCP connections. Credentials and resources are referenced by name and must pre-exist in every target team.
6. **Never invent `/mcp` tool names.** Tool names are unpublished. Describe the server by its documented capabilities: reading and changing stories, creating and updating actions, validation, running actions where permitted, research and listing helpers, private template operations when your permissions allow. Reference `tines:<tool>` only after your client has listed it and `docs/VERIFY.md` records it.
7. **Production changes only through ship** (import → draft → change request → human approval). `cr-promote` is denied in the IDE; `bypass_approval` exists only in `rollback.yml`'s `break-glass-promote` job — one of three break-glass jobs (`break-glass`, `break-glass-promote`, `break-glass-re-enable`), each approved by two different reviewers, neither of them the dispatcher (environment `break-glass-2`, then environment `break-glass`).
8. **Guards live in the story** (Triggers, Resources, change control), not in prompts. An instruction is a request; a hook or a Trigger is a rule.
9. **Two failed corrections on one issue → stop and re-prompt.** Do not keep retrying.
10. **The dev team is never personal space** — the AI Agent action is unavailable there and credentials would have to be shared.

## 4. Naming

- Stories: `[PREFIX] NN · Verb noun` — for example `[SEC] 01 · Enrich IP (sub)`, `[OPS] 10 · Monitor story health and credits`. Names must be identical in every environment (import matches by name).
- Sub-stories end in `(sub)` and finish on a message-only Event Transform named `result` that emits 3–5 fields. Their description documents the output shape — tool responses carry no output schema.
- Failure branches end on an Event Transform named `error` returning `{status: "error", error_category, retryable, message}`, `error_category` one of `auth | rate_limit | upstream_5xx | validation | permission | unknown`. Never an empty string for "auth failed".
- Action names are lowercase snake_case verbs or nouns: `normalize`, `is_protected`, `verdict`, `result`, `error`, `acquire_lock`. Triggers are named `is_<condition>` or `has_<thing>`.
- Tool names (Mode 3 and Mode 4) are namespaced snake_case ≤ 64 chars: `ops_get_error_logs`, `request_disable`. Any tool whose name matches `block|delete|isolate|disable` must start with `request_`.
- A **Note** on every canvas stating purpose, inputs, outputs and the mode badge (Mode 1–4 or "none").

## 5. HTTP Request hardening (every HTTP Request action)

| Setting | Rule | Why |
|---|---|---|
| `retry_on_status` | `[429, 500-599]` | Transient failures retry; 4xx logic errors do not |
| Retries | 5–8, never the default 25 (which retries for roughly 3 h 20 min — VERIFY against your export) | Bounded backoff |
| `emit_failure_event` | **Always** — the default "Error response only" misses timeouts and DNS failures | The failure path must fire |
| `log_error_if` | set for 200-with-error bodies | Vendors that return 200 on error |
| `log_error_on_status` | exclude expected non-2xx (the lock's 422, an empty lookup's 404) | No false failure notifications |
| Failure path | connects to `error`; dead-letter to the `ops_dead_letter` Record (payload reference, never the body) | Nothing is lost silently |

Export key names for these options are **VERIFY** until one real export has been read (`policies/lint-rules.yml` carries the markers).

## 6. Monitoring

- Recipients on every production story = the ops router webhook + the email DL, resolved from `stories/_manifest.yaml` by `ship.yml`. The router URL carries a secret and lives only in `.env` / GitHub environment secrets.
- Story-level **"Notify when any action fails"** (`monitor_failures`) on for every `tier: production` story.
- **"Notify if no events emitted"** on every scheduled or ingress action at ≈ 2× its interval (the watchdog). The sweep proposes the value from baseline data; a human applies it.
- Monitoring works only on LIVE stories; the ops stories run LIVE with change control on and `locked: true` in prod.

## 7. AI Agent actions

- **Output schema always.** A Trigger after the agent branches only on explicit schema fields (`severity`, `proposed_change.kind`, `needs_human`) — never on confidence, sentiment or prose.
- **One tool first, at most five.** Tools are Send to Story sub-stories with a Timeout Duration, added one at a time, each returning 3–5 fields. Keep the enabled set fixed per action. Split jobs across agents rather than growing a list. At most one MCP connection, never alongside the Send to Story set.
- **Token-usage alert on the Status tab**: Notify at `daily_tokens_notify`, Disable action at `daily_tokens_disable` — set by hand, recorded in `story.meta.yaml: ai.agents[].token_alert`. The reviewer refuses a story whose meta lacks it.
- The relevant `tines-skills/` skill attached (by hand — no API found, VERIFY) and recorded in meta.
- **Agents reason, stories fetch.** Deterministic pre-filters, loops and fan-out live in the story; the agent gets evidence and proposes. Tool results are untrusted data.
- **Every new AI Agent action needs a line in `policies/cost-ceilings.yml`** — `lint.yml` fails the PR otherwise.
- Task mode uses the cheaper model until a tool is added, then the smart model: a tool-less critic is cheap by construction.

## 8. Credits

- Know which provider each agent uses. A custom provider bypasses Tines AI credits but still bills externally (`billed_cost`).
- Write `meta.credits_used`, tokens and model to the `ops_findings` Record on every agent run.
- The build loop (Mode 2) runs on the editor's plan; no Tines AI credits are listed for the Tines Stories MCP server (whether its research and listing helpers consume credits is VERIFY). Workbench for Storyboard is the credit-spending alternative and is chosen deliberately, not by default.
- Tines alerts at 80 % and 100 % by default; the stops are the per-action Disable-action token alert and the kit's sdlc_limits caps and kill switch.

## 9. Ownership and never-touch

- `[SEC]` stories belong to the security-automation team; `[OPS]` stories belong to ops; the prefix says who reviews.
- `policies/never-touch.yml` is the machine-read list: production story ids (filled after the first ship), every `[OPS]` story outside its own change request, the `90 Seeds` folder, anything in another team. Its readers: `guard-mcp.sh` (`story_ids`, plus the manifest's prod ids), `set_monitoring.py` and `story_disable.py` (`story_ids`), `propose-fix.yml` (`story_ids` and `name_patterns`), and the monitor's Conditions through the `never_touch` mirror in `ops_limits` (`story_ids`, `name_patterns`; kept equal by hand). `lint-story.sh` does not read it, and nothing reads `folders` or `teams` yet.
- `TINES_ENV=prod` refuses every `/mcp` call; the scripts refuse prod outside CI unless `TINES_ALLOW_PROD=1`.
- CODEOWNERS: `policies/`, `.claude/`, `.github/` and `stories/ops-*` need a security-platform review; no self-merge.

## 10. Skill map

| Skill | Does |
|---|---|
| `/tines-connect` | Claude Code: consents the inline server in a `claude --agent tines-builder` session; Cursor: a build-only worktree's project `.cursor/mcp.json`, never the global one. Completes OAuth, runs a smoke prompt |
| `/tines-build-story <slug> "<ask>"` | Explore → plan → implement → validate → test → by-hand list → export → commit (dev team only) |
| `/tines-export <slug>` | Export → normalise → lint → stamp `exported_from` → semantic diff |
| `/tines-review` | Fresh-context review → findings JSON; refuses to review what the session built |
| `/tines-ship <slug> [dev\|prod]` | Version → import as draft → recipients → change request. Never promotes |
| `/tines-rollback <slug> <sha\|previous>` | Revert PR + the workflow to run; never the break-glass path |
| `/tines-skills-push <name> [--dev]` | Validate + dry-run the Skills API upsert; push to dev for a live test |
| `/sdlc <slug>` | The lifecycle orchestrator (`status`, `next` or `run`): runs only the specialists `./scripts/sdlc next` names; stops at every human gate |
| `/sdlc-gate <slug> <gate> <decision>` | **Human only.** Records a repo-side gate decision (G3; G0, G6, G7, GB and GX on the Community path only) |
| `./scripts/tines <subcommand>` | Everything the Tines API does, one audited code path; never compose raw `curl` |
| `./scripts/sdlc <subcommand>` | The only writer of lifecycle state: `status`, `next`, `ready`, `estimate`, `check` read; `start`, `intake`, `apply`, `advance`, `eval-run`, `gate` write and ask first |

## 11. Read next

- `sdlc/README.md` before starting a new story: its phases, gates and commands, and who decides each gate.
- `docs/01-decision-rules.md` before choosing an agent or MCP for anything: HTTP Request or template → Send to Story → AI Agent action with Tines tools → Mode 3 with an MCP connection → Mode 4. Never MCP for bulk data movement, sub-second latency or a destructive action without an approval path.
- `policies/POLICY.md` before shipping.
- `.claude/skills/tines-build-story/references/story-conventions.md` for the long-form conventions (locks, safe-disable order, size limits).

## 12. The shared block (tenant-side copy of §4–§9)

The block between the markers is the text `tines-skills/story-build-conventions/SKILL.md` carries, byte for byte, so agents and Workbench inside Tines apply the same rules ("this one" in it means that skill). `lint.yml` fails a pull request whose two copies differ: change a convention here, in §4–§9 and in the skill in one PR, and bump `v1` in both markers with the skill's `metadata.version`.

<!-- shared-block: agents-md-conventions v1 begin -->

## Naming

- A story is named `[PREFIX] NN · Verb noun` — a bracketed team prefix, a two-digit number, a middle dot, an imperative phrase. Examples: `[SEC] 01 · Enrich IP (sub)`, `[OPS] 10 · Monitor story health and credits`.
- A sub-story (a story called through Send to Story) ends its name in `(sub)`.
- Story names are identical in every environment; the deployment pipeline matches stories by name.
- Action names are lowercase snake_case and say what the action does: `normalize`, `is_protected`, `lookup_reputation`, `verdict`, `result`, `error`. Triggers are named `is_<condition>` or `has_<thing>`.
- Every canvas carries one Note stating the story's purpose, its inputs, its outputs and its mode badge (Mode 1 Workbench calling MCP tools · Mode 2 the Tines Stories MCP server · Mode 3 the AI Agent action calling tools · Mode 4 the MCP server action · or "none").

## The sub-story contract

- A sub-story finishes on a **message-only Event Transform named `result`** that emits exactly 3–5 fields. The tool description documents those fields, because tool responses carry no output schema.
- Every failure branch ends on an Event Transform named `error` that emits `{status: "error", error_category, retryable, message}` — `error_category` one of `auth | rate_limit | upstream_5xx | validation | permission | unknown`, `retryable` a boolean, `message` a sentence a person can act on. Never an empty response for "auth failed".
- The entry action's expected fields are normalised first by an Event Transform named `normalize` using `DEFAULT()` fallbacks, so a missing field never breaks a formula downstream.
- A guard Trigger sits before any AI step and before any outbound action with side effects (for example `is_protected` checking a range against a Resource), and refuses with a structured `{status: "refused", reason}` before any lookup runs.

## HTTP Request hardening

| Setting | Value | Why |
|---|---|---|
| Retry on status | `[429, 500-599]` | transient upstream failures and rate limits |
| Retries | 5–8 (use 6) | the default of 25 spreads retries over roughly 3 h 20 min (duration VERIFY against a real export) and hides an outage |
| Emit failure event | **Always** | the default "Error response only" misses timeouts and DNS failures |
| Log error if | a formula for 200-with-error bodies | vendors that return `200 {"error": …}` |
| Log error on status | exclude expected non-2xx (a lock's `422`, an empty lookup's `404`) | expected outcomes are not errors |
| Failure path | connected to the `error` Event Transform and the dead-letter Record | nothing fails silently |

(Option names as shown in the action's settings; the key names in a story export are confirmed from a real export — VERIFY #8.)

## Monitoring

- Recipients are the ops router webhook and the ops email distribution list, both from the repository manifest — never a person's address, never a literal URL in a story.
- Story-level **Notify when any action fails** is on for every `production` story.
- **Notify if no events emitted** is on for every scheduled or ingress action, at about 2× its interval (the exact number is derived from baseline data by the ops sweep and proposed, not guessed).
- Monitoring only works on a story running LIVE.

## AI Agent actions

- An **output schema** on every AI Agent action, always. Make fields nullable when the source may lack them; include an `other` value with a detail field wherever a closed list is used.
- **One tool first, at most five.** Tools are added one at a time; a job that needs more is split across agents or moved into a Send to Story sub-story that returns one summary. Tools return 3–5 fields, never raw data; the loop lives in the story, not in the model.
- A **Trigger after the agent** branches on an explicit schema field (`severity`, `proposed_change.kind`, `needs_human`) — never on confidence, sentiment or prose.
- A **token-usage alert on the Status tab**: Notify at one threshold, Disable action at a higher one. Set by hand; recorded in the story's meta file.
- The relevant tenant skill attached (`story-health-triage`, `credit-budget-analyst`, `alert-policy`, or this one), and the attachment recorded in the story's meta file.
- **Agents reason, stories fetch.** Anything deterministic — a lookup, a fan-out, a filter — is an HTTP Request action, a Send to Story or an Event Transform before the agent, not a tool the agent has to decide to call.
- Every new AI Agent action needs a budget line in `policies/cost-ceilings.yml` before it ships.
- Task mode defaults are temperature 0.2, timeout 30 s, retries 25 — raise the timeout for a tool-using agent and lower the retries. A tool-less Task-mode agent runs on the fast model; adding a tool moves it to the smart model.

## Credits

- Know which provider each agent uses. A custom provider bypasses AI credits but still bills (`billed_cost`); the two are never summed.
- Each agent run's `meta.credits_used`, tokens and model are written to a Record so credits per completed task can be scored.

## Ownership and never-touch

- Each story prefix belongs to one team; the owner is a role, never a person.
- `policies/never-touch.yml` is the machine-read list of what no agent, skill, hook or pipeline writes to: production story ids, every `[OPS]` story (changed only through its own change request), the `90 Seeds` folder, and anything in another team. A story on that list may be *reported on*, never changed.
- Production is changed only through the repository: export → pull request → review → merge → import as a change-control draft → change request → a named approver. Never edit a live production story by hand or through Workbench; propose the change instead.

## Exports

- If the story will be exported to the repository — every `production`, `internal` and `ops` story is — reference credentials and resources **by name** only; the credential must exist under the same name in every team the story is deployed to. Exports contain no credential values, resource contents or events by design, and recipients are cleared on export and set from the manifest on deployment.
- Guards live in the story (Triggers, Resources, change control), not in prompt text.

<!-- shared-block: agents-md-conventions v1 end -->
