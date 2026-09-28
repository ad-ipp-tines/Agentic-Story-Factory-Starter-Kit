# VERIFY.md — the ledger

_Tines Stories as Code · Append-only status ledger for every VERIFY item in `DESIGN.md` §10 and `07-verify-before-you-rely-on-it.md`. **This file is referenced by name** from `README.md`, `AGENTS.md`, `/tines-connect` (step 4) and the hooks' comments; keep the path._

## How to use this file

- The **method** (how to check each item) is in `07-verify-before-you-rely-on-it.md`. This file records **outcomes**.
- When you confirm an item: change its status, add the date, the role that checked it (never a name), what you saw in one line, and the commit that changed the repo as a result. If nothing changed in the repo, say "no change" — but think twice: every confirmation should tighten something.
- If an item turns out **false**, the status is `refuted`, and the "what changed" column must name the design change (`DESIGN.md` §9 rule 15).
- Never delete a row. A re-check after a Tines release is a new line under **History**, not an edit.
- Nothing with status `open` may appear as a fact on a slide, in a README's opening paragraph, or in a customer conversation.

Statuses: `open` · `confirmed` · `refuted` · `partial` (say which part) · `n/a` (this tenant's plan makes it moot — say why).

## Ledger

| # | Item (short) | Status | Confirmed on | By (role) | What was seen | What changed in the repo (commit) |
|---|---|---|---|---|---|---|
| 1 | `/mcp` tool names and count | open | — | — | — | — |
| 2 | `/mcp` edits on a change-controlled dev story land as drafts | open | — | — | — | — |
| 3 | Claude Code `claude mcp add … --scope user` + OAuth via `/mcp` | open | — | — | — | — |
| 4 | Cursor: `type` key; `.claude/skills/` discovery and comma-separated `allowed-tools`; no Claude Code hooks | open | — | — | — | — |
| 5 | Subagent `mcpServers: [tines]` references a user-scope server by name | open | — | — | — | — |
| 6 | Import response exposes the draft id; duplicate `draft_name`; missing credential behaviour | open | — | — | — | — |
| 7 | `PUT /actions/{id}` monitor flags need a draft; `POST /recipients` without `draft_id` is live; draft recipients carry on promote | open | — | — | — | — |
| 8 | Export key names (retry, `emit_failure_event`, monitor flags, `keep_events_for`, output schema); `Agents::LLMAgent`; credential/resource reference syntax | open | — | — | — | — |
| 9 | Monitoring, credit-alert, event-limit and change-control webhook payload shapes | open | — | — | — | — |
| 10 | Credit alert defaults 80/100; role; per-team granularity; no API for allocation/thresholds | open | — | — | — | — |
| 11 | `/mcp` research and listing helpers consume credits? | open | — | — | — | — |
| 12 | Restoring a story version via API | open | — | — | — | — |
| 13 | Flow counting for sub-stories as tools and the ops trio; plan entitlements | open | — | — | — | — |
| 14 | Agent Skills limits, versioning, credits; Workbench for Storyboard honours preset skills; attach API; `metadata.git_sha` | open | — | — | — | — |
| 15 | Hook JSON `permissionDecision` third value | open | — | — | — | — |
| 16 | Runs: `end_time` null mid-run; `not_working_actions_count` semantics | open | — | — | — | — |
| 17 | Audit-log `operation_name` for MCP activity; server-side `story_id` filter | open | — | — | — | — |
| 18 | Viewer-role team key is read-only for the monitor and `drift.yml` | open | — | — | — | — |
| 19 | CAS on the `ops_lock` Resource (`if_value`, 422); Deduplicate time gate | open | — | — | — | — |
| 20 | Headless `claude -p` cannot reuse the `/mcp` OAuth session | open | — | — | — | — |
| 21 | `npx skills-ref validate` in CI; `claude-code-action@v1` inputs; `--json-schema @file` | open | — | — | — | — |
| 22 | Terraform `tines_story` on a change-controlled story; provider 0.3.0 | open | — | — | — | — |
| 23 | Library 1231438 entry action after import; 87626 as the example seed | open | — | — | — | — |
| 24 | HTTP Request max timeout; failure-path errors still notify | open | — | — | — | — |
| 25 | Mode 4 OAuth access mode (docs CONFLICT); editor adds the MCP server action via `/mcp`; event retention; protocol revisions | open | — | — | — | — |
| 26 | `/mcp` can create Record types | open | — | — | — | — |
| 27 | Rate-limit headroom for the 15-minute sweep on a large tenant | open | — | — | — | — |
| 28 | Plan-gated claims and moved click paths before any demo | open | — | — | — | — |
| E1 | `mcp-remote` header scheme (`Basic` vs `Bearer`) | open | — | — | — | — |
| E2 | `tools/call` event includes the tool result? | open | — | — | — | — |
| E3 | Self-hosted release-note version mapping | open | — | — | — | — |
| E4 | `GET /api/v1/stories/{id}` exposes `disabled` (so `story-disable --want` can skip a toggle); `POST …/disable` takes no body | open | — | — | — | — |
| E5 | `GET /api/v1/ai_usage` envelope and row keys (story/team/action identity, token key names), `YYYY-MM-DD` dates, the time zone of `today` | open | — | — | — | — |
| E6 | `GET /api/v1/audit_logs` envelope; `created_at` on rows; where a row carries the story id (the client-side filter matches any `story_id` key) | open | — | — | — | — |
| E7 | Change-request view: location of `status` and the request id; `…/change_request/promote` response; `bypass_approval` needs STORY_MANAGE | open | — | — | — | — |
| E8 | Claude Code CLI headless flags in `propose-fix.yml`: `--strict-mcp-config` + empty `--mcp-config`, `--setting-sources project`, path-scoped `Edit(stories/**)` / `Write(.tines/**)`, `--output-format json` fields | open | — | — | — | — |
| E9 | The MCP server action carries the "Notify if no events emitted" monitor (`ops-tools-server` watchdog) | open | — | — | — | — |
| E10 | Fixed inputs on a Send to Story tool, set on the tool and never by the model (`ops-tools-server` request tools) | open | — | — | — | — |
| K1 | Subagent `tools` accepts `Bash(<pattern>)` and `WebFetch`; the settings rule `WebFetch(domain:www.tines.com)` | open | — | — | — | — |
| K2 | A PreToolUse hook can tell which subagent is calling (until confirmed, `phase-gate.sh` denies every `mcp__tines__*` call) | open | — | — | — | — |
| K3 | Subagents spawning subagents in Claude Code; the SDK's default nesting depth | open | — | — | — | — |
| K4 | Cursor: per-agent tool limits or custom subagent files; per-chat MCP enablement; agent-requested `.mdc` attachment by description | open | — | — | — | — |
| K5 | Request body of `POST /api/v2/records/search`, including filters by field id | open | — | — | — | — |
| K6 | Story import keeps Record actions pointed at record types by name | open | — | — | — | — |
| K7 | CONFLICT: the AI Agent action on Community; whether importing a story with AI Agent actions fails on a plan without them | open | — | — | — | — |
| K8 | Import preserves Page URL identifiers and Webhook paths and secrets (the template is not published until confirmed) | open | — | — | — | — |
| K9 | A credential referenced by a name computed at run time | open | — | — | — | — |
| K10 | A formula reading a Resource that does not exist yields null, not an error | open | — | — | — | — |
| K11 | Fine-grained token permissions for `/generate` and org repository creation; reaching a repository created after the token; reading a template owned by another account | open | — | — | — | — |
| K12 | Readiness delay of a generated repository; Actions enabled on it; the setting that lets `GITHUB_TOKEN` open PRs | open | — | — | — | — |
| K13 | Contents PUT into a repository with no commits; the conflict status code; the maximum PUT size | open | — | — | — | — |
| K14 | The Tines base64-encoding formula name | open | — | — | — | — |
| K15 | A response-enabled Webhook returns ≤ 500 rows within 30 s; response size limits | open | — | — | — | — |
| K16 | `POST /api/v1/record_types` returns field ids; the exact key names in `fields[]` | open | — | — | — | — |
| K17 | Dashboard import resolves `record_type_name` against types that already exist in the team | open | — | — | — | — |
| K18 | Apps: nested paths in `PUT …/files`; publishing through the Tines MCP server; credits for API file pushes; viewer identity at an app endpoint; available packages | open | — | — | — | — |
| K19 | CONFLICT: Apps limits per plan | open | — | — | — | — |
| K20 | CONFLICT: custom AI providers on all tenants vs Business and Enterprise only | open | — | — | — | — |
| K21 | CONFLICT: external-provider limit of 500 runs a minute per tenant vs "no limit" | open | — | — | — | — |
| K22 | vLLM behind Tines: streamed tool-call deltas; server flags | open | — | — | — | — |
| K23 | A local provider accepts a plain `http://` base URL and a blank API key; the `provider_type` it reports | open | — | — | — | — |
| K24 | Azure OpenAI's `provider_type`; the full list of API type values | open | — | — | — | — |
| K25 | `billed_cost` for custom and local providers; whether Status-tab token alerts act on custom providers | open | — | — | — | — |
| K26 | The AI Agent action's model field accepts a formula (per-run model) | open | — | — | — | — |
| K27 | How a skill attachment appears in story JSON, and whether import keeps it | open | — | — | — | — |
| K28 | CONFLICT: Workbench as a paid add-on vs included in every edition | open | — | — | — | — |
| K29 | CONFLICT: a Records ARTIFACT field holds 15,000 vs 100k characters | open | — | — | — | — |
| K30 | How flows are counted for one story with several entry points | open | — | — | — | — |
| K31 | Pages: required fields; root-page formulas reading Resources; Option lists from Resources; sibling conditions in a looping container; "Move to next page" with actions between Pages | open | — | — | — | — |
| K32 | A Table element fed from a CSV string built by formula (the function names) | open | — | — | — | — |
| K33 | Explode + HTTP Request ordering for sequential PUTs; the Loops 5-minute limit vs a ~200-file copy; pacing | open | — | — | — | — |
| K34 | `claude-code-action` inputs for running a named subagent headless | open | — | — | — | — |
| K35 | Request body of `POST /api/v2/records/aggregate`: a count with filters | open | — | — | — | — |
| K36 | The Tunnel on the customer's plan: bought, support-enabled, accessible by all teams | open | — | — | — | — |
| K37 | The Webhook URL built from export options, and draft addressing for `eval-run` (incl. the dev-only wrapper story) | open | — | — | — | — |
| K38 | Which `ai_usage` rows a team-scoped, non-admin key sees | open | — | — | — | — |
| K39 | Records created through `POST /api/v1/records` (test mode off) are live in a change-controlled story | open | — | — | — | — |
| K40 | What "unlocking through the API is permanent" means for Resource locks | open | — | — | — | — |
| K41 | A team-scoped Editor key can call the Skills, Record types, Resources, Dashboards and Apps APIs, and sees other teams' names | open | — | — | — | — |
| K42 | Editor-side local or gateway models with `/mcp`'s many tools | open | — | — | — | — |
| K43 | The ten starter seed ids still resolve with the recorded names and expected entry actions | open | — | — | — | — |
| K44 | GitHub's raw media type header string for contents GET; behaviour above 1 MB | open | — | — | — | — |
| K45 | What `./scripts/tines cr-view` returns after an approve-and-push in Tines, and after `promote.yml`'s promote with `delete_draft: true` | open | — | — | — | — |

## Recorded `/mcp` tool names (item 1)

Paste the tool names your client lists, one per line, with the date and the client. This block is what `guard-mcp.sh`'s explicit deny list is built from, and what lets a skill reference `tines:<tool>`.

```
# date · client · tool names
# (none recorded yet)
```

## History

Append one line per check, newest first: `YYYY-MM-DD · item # · role · outcome · note`.

- 2026-09-27 · K1–K45 · kit-docs-and-root builder · rows added · the story factory's items (REPO-DESIGN.md §16, whose "How to confirm" and "What changes when confirmed" columns are the method for each); the kit also relies on #1, #2, #4, #5, #8, #11, #13, #14 and #26
- 2026-09-25 · E9–E10 · docs builder · rows added · assumptions `stories/ops-tools-server/story.meta.yaml` carried without a ledger entry; method in `07-verify-before-you-rely-on-it.md` §F
- 2026-09-25 · E4–E8 · ci builder · rows added · assumptions made by `story-disable`, `ai-usage`, `audit`, `cr-promote` and `propose-fix.yml`; how to confirm each is in `scripts/README.md` ("VERIFY items these scripts depend on")
- 2026-09-24 · all · docs builder · ledger created · every item open; method in `07-verify-before-you-rely-on-it.md`

## Verify in your tenant before presenting

If this table is all `open`, nothing marked VERIFY in the repository may be presented as fact. The first afternoon's check order is in `07-verify-before-you-rely-on-it.md`.
