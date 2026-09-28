# Story conventions — the long form

_Loaded on demand by `/tines-build-story`, `/tines-review` and `/tines-propose-fix`. `AGENTS.md` holds the short form that is always resident; this file holds the reasons, the exact shapes and the parts that are too long to keep in context. Sections: 1 naming and the Note · 2 sub-story tool contract · 3 HTTP Request hardening · 4 monitoring (recipients, failure paths, the ops pair) · 5 overlap guard · 6 safe-disable order · 7 AI Agent action design · 8 tool design for Mode 3 and Mode 4 · 9 size limits · 10 change control and drafts. Facts come from public MCP research (current to 2026-09-17) and `DESIGN.md`; anything else is marked VERIFY with its `docs/VERIFY.md` number._

---

## 1. Naming and the Note

- Stories: `[PREFIX] NN · Verb noun` — `[SEC] 01 · Enrich IP (sub)`, `[OPS] 10 · Monitor story health and credits`. The prefix names the owning team (`AGENTS.md` §9); the number orders the canvas list; the name is **identical in every environment** because `POST /api/v1/stories/import` with `mode: versionReplace` matches by name.
- Sub-stories end in `(sub)`. Anything used as a Send to Story tool is a sub-story.
- Actions: lowercase `snake_case` verbs or nouns — `normalize`, `is_protected`, `<vendor>_lookup`, `verdict`, `result`, `error`, `acquire_lock`, `release_lock`. Triggers are `is_<condition>` or `has_<thing>`. Every action has a non-empty description; no two actions share a name (lint `unique_action_names`).
- Tool names (Mode 3 tools and Mode 4 server tools): namespaced `snake_case` ≤ 64 characters — `ops_get_error_logs`, `request_disable`. Any tool whose name matches `block|delete|isolate|disable` **must start with `request_`** (lint `tools_are_requests`).
- **One Note per canvas** stating purpose, inputs, outputs (the `result` and `error` shapes), credentials and Resources by name, and the **mode badge**: Mode 1 (Workbench calling MCP tools) · Mode 2 (the Tines Stories MCP server at `/mcp`) · Mode 3 (the AI Agent action calling tools) · Mode 4 (the MCP server action at `/mcp/<mcp-path>`) · or `none`. "Mode" is the only word used for these surfaces.

## 2. The sub-story tool contract

A sub-story is a Tines subagent: it receives only the fields passed to it, returns one output, and can be exposed unchanged as a Send to Story tool (Mode 3), as a Mode 4 server tool, and to Workbench (Mode 1).

| Element | Rule | Why |
|---|---|---|
| Entry | Send to Story action; its expected fields are named in the description | The description is what a caller (a story, an agent, an MCP client) reads |
| `normalize` | First Event Transform; `DEFAULT()` on every field | A missing field never breaks a formula |
| Guard | A Trigger before any lookup or AI step (allow-lists, protected ranges, never-touch) | Guards live in the story, not in prompts |
| `result` | The **last** action on every success branch: a message-only Event Transform emitting **3–5 fields** (for example `{verdict, score, sources, summary}`) | Trim at the tool boundary; intermediate data never reaches a model |
| `error` | The last action on every failure branch: `{status: "error", error_category: "<auth|rate_limit|upstream_5xx|validation|permission|unknown>", retryable: <bool>, message: "<text>"}` | A structured, recoverable error is feedback a model can act on; an empty string for "auth failed" is not |
| Description | States the `result` shape, the `error` shape, when to call it, what it does **not** do, and one example argument | Tool responses are always text and carry no output schema — the description is the only place the output shape lives |
| Timeout Duration | Set wherever the sub-story is used as a tool (lint `sts_timeout_required`) | A caller must never wait indefinitely; Mode 4 tools must answer within 30 seconds |

Distinguish an **access failure** (`error_category: permission`) from a **legitimately empty result** (`{verdict: "unknown", score: 0, sources: [], summary: "no data"}`) — both are `result`-shaped or `error`-shaped, never a bare string.

## 3. HTTP Request hardening (every HTTP Request action)

| Setting | Rule | Why |
|---|---|---|
| Retry on status | `[429, 500-599]` | Transient failures retry; 4xx logic errors do not |
| Retries | **5–8**, never the default 25 (which retries for roughly 3 h 20 min — VERIFY #8 against your export) | Bounded backoff |
| Emit failure event | **Always** — the default "Error response only" misses timeouts and DNS failures (VERIFY #8) | The failure path must fire for every failure class |
| Log error if | Set for vendors that return 200 with an error body | The event looks fine but the body says otherwise |
| Log error on status | **Exclude** expected non-2xx (the lock's 422, an empty lookup's 404) | No false failure notifications; no noise in the router |
| Failure output | Linked to `error`, or to a dead-letter write (`ops_dead_letter` Record: `ref`, `story_id`, `error_class`, `status`, `at`, `payload_ref` — a reference, **never the body**) | Nothing is lost silently |
| Credentials | Referenced by name; `allowed_hosts` set on the credential in the tenant; Workbench access off for pipeline keys | The value never leaves Tines and never appears in an export |

Export key names for these options are **VERIFY (#8)** until one real export has been read; `policies/lint-rules.yml` documents each rule's key and sets its severity, but the key names are hard-coded in `scripts/lint_story.py` (behind the `lint-story.sh` shim), which caps any rule it still tags VERIFY at `warning`.

## 4. Monitoring — recipients, failure paths, and how the ops pair works

### 4.1 What a production story must carry
- **Recipients** = the ops router webhook (`OPS_ROUTER_URL`, carries a secret, lives only in `.env` / GitHub environment secrets) + the email DL (`OPS_EMAIL_DL`). Both are listed as `${VAR}` placeholders in `stories/_manifest.yaml: environments.<env>.recipients` and applied by `ship.yml` — never typed into the story, never committed.
- **Story-level "Notify when any action fails"** (`monitor_failures: true`) on every `tier: production` story (lint `monitoring_required_for_prod`).
- **"Notify if no events emitted"** — the watchdog — on every scheduled or ingress action at ≈ **2× its expected interval** (`monitor_no_events_emitted`, seconds). For a scheduled story: 2× the cron interval. For a webhook-fed story: 2× the p95 inter-event interval, which the sweep proposes from baseline data and a human applies. Recorded in `story.meta.yaml: monitoring.no_events_watchdog`.
- Monitoring notifications fire only on **LIVE** stories, never in TEST mode — the ops stories run LIVE with change control on and `locked: true` in prod.
- Event retention ≥ 30 days for `tier: production` (lint `keep_events_min_days_prod`; key and unit VERIFY #8).

### 4.2 How to add a recipient or a monitor flag (three ways, in order of preference)
1. **Through ship** (the normal path): `ship.yml` runs `./scripts/tines recipients-add <slug> --env prod --address "$ADDR" --draft <id>` for each manifest recipient (`POST /api/v1/stories/{id}/recipients {address, draft_id}`) and `./scripts/tines story-update <slug> --env prod --monitor-failures true --draft <id>` (`PUT /api/v1/stories/{id}`), then opens the change request. Watchdogs: `./scripts/tines action-update … --monitor-no-events <seconds> --draft <id>` (`PUT /api/v1/actions/{id}`). Whether these calls need a draft on a change-controlled story, and whether draft recipients carry to live on promote, is VERIFY (#7).
2. **Through the sweep**: in **dev** the monitor auto-fixes a coverage gap (missing router recipient, `monitor_failures: false`) immediately; in **prod** it writes an `ops_alert_proposals` row and posts a Slack approval; on approval the apply sub-story makes the same calls into a draft + change request.
3. **By hand** in the story's settings — only for a scratch story in dev; anything in prod goes through 1 or 2 so the repo stays the truth.

Never `echo` a recipient that came from `${OPS_ROUTER_URL}`: the URL carries a secret.

### 4.3 Failure paths — the rule
Every HTTP Request action's failure output connects to `error` or to a dead-letter write (§3). A story-level failure notification then reaches the router **as well** (a handled failure-path error may still fire "Notify when action fails" — VERIFY #24; the router dedupes per story + action + 15-minute window, so double signals are safe). Only the final retry notifies. An expected non-2xx (the lock's 422) is excluded from error logging so it never pages anyone.

### 4.4 How the monitoring story works (the ops pair, `DESIGN.md` §5)
- **Router** `[OPS] 01 · Route monitoring alerts` (`stories/ops-error-router/`, Library 1231438 pattern; entry action after import expected to be a Webhook — VERIFY #23): receives every story's failure and no-events notifications plus the tenant's AI-credit, event-limit and change-control webhooks → responds 200 fast → `normalize` (payload shape VERIFY #9 — captured once by deliberately failing an action in a LIVE scratch story with a test recipient) → classifies the source → **dedupes** per story + action + 15-minute window → enriches with the last level-4 log (`GET /api/v1/actions/{id}/logs?level=4`, Viewer-role key `tines_api_readonly`) and a severity class (401/403 → owner; 429 → back off; persistent 5xx → escalate; no-events → silent source) → one Slack thread per story per day (channel from the `ops_routing` Resource) → writes `ops_alerts` → Send to Story into the sweep when severity ≥ medium or count ≥ 3.
- **Sweep** `[OPS] 10 · Monitor story health and credits` (`stories/ops-story-health-monitor/`, cron `*/15`, **Mode 3**): Trigger on the kill switch `ops_limits.enabled` → compare-and-swap lock (§5) → reads live activity (`GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true`), AI usage (`GET /api/v1/ai_usage?relative_date=today&group_by=story`), recent runs (`GET /api/v1/stories/{id}/runs?since=`) → a **deterministic pre-filter** against `ops_baselines` and `ops_limits` → **only anomalous stories reach the AI Agent action** `triage` (Task mode, five read-only Send to Story tools, output schema, skills `story-health-triage` + `credit-budget-analyst`) → a tool-less `critic` re-reads high/critical → a Trigger on `severity` / `proposed_change.kind` / `needs_human` → record only · alert-rule proposal + Slack approval · GitHub issue or `repository_dispatch` → `propose-fix.yml` · request disable (two approvers in prod) → the apply sub-story (the only place the Editor-role key `tines_api_ops` lives) → release the lock. A healthy sweep spends zero credits. The sweep's own watchdog (1,800 s) pages the DL if the monitor goes silent.
- **Mode 4 face** `[OPS] 20 · Ops tools (MCP server)` (`stories/ops-tools-server/`): the same five read sub-stories plus `request_alert_rule` and `request_disable`, exposed at `https://<your-tenant>.tines.com/mcp/<mcp-path>` behind **With a Tines API Key** scoped to the ops team, so an editor or the on-call person asks the monitor's questions and requests the monitor's actions through the same approvals.
- **What stays by hand** (no API): AI Agent token thresholds on the Status tab; per-team AI credit allocation and credit-usage alert thresholds in Admin → AI (defaults reported as 80 % and 100 % — VERIFY #10); Record types (VERIFY #26). The agent can only *propose* these.
- **The boundary:** the story may read anything with the read-only key, write Records, post threads, add recipients and monitor flags in dev, open issues, Cases or tickets, and fire `repository_dispatch` (which only ever yields a PR). A named human approves any alert rule applied to prod, any disable, any PR merge, any change request, and answers every `needs_human` finding.

## 5. Overlap guard — the compare-and-swap lock

Records have no documented atomic semantics, so the lock is a **Resource** (`ops_lock`, `{"lock": "free"}`):
- Acquire: HTTP Request `acquire_lock` → `POST /api/v1/global_resources/<resource_id>/replace {key: "lock", value: "<<STORY_RUN_GUID()>>", if_value: "free"}`. A **422** means another run holds it: exclude 422 from error logging and branch on it with a Trigger to exit quietly. Compare-and-swap via `if_value` and the 422 response are VERIFY (#19; `./scripts/tines resource-cas` tests it).
- A lock older than `ops_limits.stale_lock_minutes` is treated as free (the story stores the acquire time next to the GUID).
- Release: `release_lock` with `if_value` = the run's GUID on the **last action and on every failure branch**.
- `schedule_interval_seconds` in `story.meta.yaml` lets the sweep detect run duration ≥ `overlap_ratio` × interval.

## 6. Safe-disable order

Disable the **entry** first (the schedule action or the ingress action), let in-flight runs drain, then the story (`POST /api/v1/stories/{id}/disable` — toggles, bypasses change control by design, audited; the kill switch, reserved for the break-glass job). Expect a burst of failure notifications from downstream stories; the router dedupes. Re-enable with the same toggle after the approver confirms, entry last. Record every disable in `policies/break-glass-log.md`.

## 7. AI Agent action design (Mode 3, and agents without MCP)

### 7.1 Task mode versus Chat mode
| | Task mode | Chat mode |
|---|---|---|
| Runs | One shot, or a self-directed reasoning loop over tools until done; inside a story | Conversational, hosted on a Tines page; ends when the goal in the system instructions is met; idle timeout emits `meta.outcome = idle_timeout` |
| Options | Prompt, Image (Claude models only), Temperature 0–1 (default 0.2), Timeout (default 30 s), Retries (default 25) | URL identifier, Access control, theming, Initial message, Idle timeout |
| Slack | — | Only Chat-mode agents connect to a Slack app (the "Slack app" section of the build panel) |
| Use it for | Everything that runs in a story: triage, classification, proposals | A person conversing: a help desk, an intake bot |

Rules that follow: **the monitor's agents are Task mode**; raise the Task timeout above 30 s when tools are attached; set Retries low (the HTTP-style default 25 is not a plan); a user-facing bot is Chat mode and its writes go through request tools with approvals (§8.4).

### 7.2 One tool first, at most five
- Every enabled tool's name, description and schema is sent on every model call; more tools mean more reasoning about which to use. **Start with one tool.** Add tools one at a time (a schema fault such as "Unable to determine input type" is then attributable). Cap an agent at the tools its job needs — five here — and **split jobs across agents** rather than growing a list. Anthropic's numbers: 4–5 role-relevant tools per agent; selection degrades past 30–50.
- Tool categories on the action: Templates (public and private), Send to Story (with a Timeout Duration), Custom tools (action Groups in the same story — all actions run, one combined output), MCP (a remote server or a Tines-built one); built-in Think, Code Analysis, Web search. Tools are the sub-stories of §2.
- **At most one MCP connection, and never alongside the Send to Story set** (lint `agent_tool_cap`). Keep the enabled set **fixed per action**: changing any tool definition invalidates the prompt cache on a custom provider.
- No deferred loading or tool search is published for the AI Agent action (VERIFY): assume every enabled tool is sent every turn.
- Tool output truncation stays **on** (50,000 tokens); tools return 3–5 fields, so it is a safety net, not a design.
- **Agents reason, stories fetch.** Deterministic pre-filters, loops and fan-out live in the story (Send to Story, Groups, Event Transforms, Triggers); the agent gets evidence and proposes. A mandatory first call is an action *before* the agent, not a hope in the prompt (`tool_choice` is not exposed on the action — VERIFY).

### 7.3 Output schema — always
- The **Output schema** field validates the structure of the agent's output. Set it on every AI Agent action (lint `agent_output_schema_required`). Make fields nullable where the source may lack them; add an `unknown` / `other` value plus a detail field; never force the model to invent a required value.
- A **Trigger after the agent** branches only on explicit schema fields — `severity`, `proposed_change.kind`, `needs_human` — never on confidence, sentiment or prose (lint `agent_post_trigger_required`). Add the semantic check (allowed values, totals) as a second Trigger and route failures to a person.
- An output-schema validation failure → Record + human, never a retry loop.
- Escalation criteria are explicit and live in the schema (`needs_human: true` when severity is high or critical, confidence < 0.6, category unknown, or the critic disagrees).

### 7.4 Token alerts, credits, budget line
- **Every AI Agent action carries a token-usage alert on the Status tab**: thresholds per Daily / Weekly / Monthly / All time; behaviour **Notify** (story recipients) at `daily_tokens_notify`, **Disable action** at `daily_tokens_disable`. Set by hand; the numbers come from `policies/cost-ceilings.yml: agents.<slug>/<action>` and are recorded in `story.meta.yaml: ai.agents[].token_alert`. The reviewer refuses a story whose meta lacks it.
- **Every new AI Agent action needs a line in `policies/cost-ceilings.yml`** (`budget_ref: "<slug>/<action>"`); `lint.yml` fails the PR without it.
- Every event carries `meta`: model, input/output tokens, `credits_used`, `remaining_credits`, duration; with tools, the full conversation `steps`. Write `credits_used`, tokens and model to the `ops_findings` Record on every run so credits per completed finding can be scored.
- Model choice: in Task mode the action uses the cheaper model until a tool is added, then the smart model — a tool-less `critic` is cheap by construction. A custom provider bypasses Tines AI credits but still bills externally (`billed_cost`); declare the provider in the budget line so the two are never confused.
- Plan gates: the AI Agent action is on Business and Enterprise plans, minimum role Editor, and **not available in personal teams** — the dev team is a real team.
- Attach the relevant `tines-skills/` skill (Agent Skills on AI Agent actions since 2026-08-11; CRUD API since 2026-09-01; attaching is [BY HAND] — VERIFY #14) and record it in meta.

### 7.5 Prompt-injection posture
Error logs, webhook payloads, ticket text and story exports the agent reads are attacker-influenceable data. The agent can only **propose**; `critic` re-checks high/critical; every path to production passes lint, an independent review, a human merge and a human change-request approval. Guards (never-touch, responders, kill switch, run caps) are Triggers and Resources, not sentences in the system instructions.

### 7.6 MCP connections on an agent (when Mode 3 reaches a vendor server)
Transport: Streamable HTTP or Plain HTTP only — an SSE-only or stdio-only vendor endpoint cannot be consumed. Auth: Bearer, generic header, or OAuth 2.1 (authorization code with PKCE; Dynamic Client Registration when the server supports it, otherwise a manually created OAuth app referenced as a Tines credential). Custom headers are supported. Private servers reach Tines through the tunnel (option placement in the dialog VERIFY). **Importing a story drops the MCP connection** — re-create it, never paste a token. Enable tools individually; one tool first.

## 8. Tool design for Mode 3 tools and Mode 4 servers

### 8.1 Descriptions are the API
- When a model decides which tool to invoke, it relies **entirely** on the names and descriptions. Write **3–4 sentences**: what the tool does and returns (field names), when to use it and when not to, what each parameter means, caveats, and **one example argument value** (there is no published way to attach input examples to a Tines tool — VERIFY — so the example lives in the text). "Get customer order history for the last 90 days", never "Get data".
- Describe what the tool does; never instruct the model how to behave, call other tools, or fetch instructions elsewhere — those are prompt-injection shapes and are rejected by Claude's connector review.
- **Document the output shape in the description.** Tool responses are always text with no output schema; a consumer that parses the result needs the field list.
- When the wrong tool gets picked, rewrite the description, not the caller's prompt. Keep a small set of realistic prompts, run them through the MCP Inspector or a real client, and rewrite descriptions from the transcripts.
- The **MCP server action's description is exposed to clients as instructions** — write it as instructions ("You are an ops assistant for Tines stories. Fetch evidence before you recommend. `request_disable` only requests; a human approves."), factual, critical details first.

### 8.2 Naming and hints
- Namespace by domain, `snake_case`, ≤ 64 characters: `ops_get_error_logs`, `ops_get_live_activity`, `request_alert_rule`. Consistent verbs across a server (`<domain>_get_*`, `<domain>_list_*`, `request_*`). Expect an aggregating client to prefix by server again.
- **Tool hints** (expand "Tool hints" under each tool): Read only (default off; overrides Destructive and Idempotent), Destructive (default **on**), Idempotent (default off), Open world (default on). Hints are MCP annotations a client *may* use; whether a client prompts on them is **VERIFY** per client and never a control. **Mark every lookup Read only** (lint `mode4_read_only_hints`); leave request tools on the default Destructive hint — the control is the request tool itself (it only posts an approval) and the verified approver.
- Separate read tools from write tools; never a catch-all "run any story" or "call any API" tool.

### 8.3 Results
- Return **high-signal, trimmed text**: 3–5 fields, stable semantic identifiers, relevant fields only (§2). Consumers cap results anyway — Claude Code warns at 10,000 tokens per MCP result and caps at 25,000 by default; Claude.ai and Claude Desktop near 150,000 characters — and the Tines agent side truncates at 50,000 tokens.
- List tools take `limit` and a cursor with a small default; say in the description that results are truncated and how to page. Prefer identifiers plus a follow-up lookup tool over dumping payloads.
- Errors are structured text (§2): `status`, `error_category`, `retryable`, `message`. Distinguish "no access" from "nothing found".
- Never return free text scraped from a third party — in Mode 4 your results feed someone else's model.

### 8.4 The 30-second rule and request tools
- **Tool response time cannot exceed 30 seconds** on a Mode 4 server; after that the client gets a timeout while the tool may keep running, and the result never reaches the client. Anything slower returns `{status: "started", id}` immediately and exposes a `status` tool (Library 1253511 and 1252707 show the pattern). Sub-stories used as Mode 4 tools carry a Timeout Duration below 30 s.
- **Request tools instead of write tools.** A tool that would change something (`block`, `delete`, `isolate`, `disable`) is named `request_<action>`, posts an approval to a fixed Slack channel with an expiry, verifies the approver against the `ops_responders` Resource (two approvers for `disable` in prod), writes an `ops_alert_proposals` row, and returns `{approval_id, status: "pending", approvers}`. Its description states what it does **not** do: "Does not disable. Posts an approval and returns approval_id." A person clicks; the story executes. The same sub-story serves the Mode 3 agent, the Mode 4 server and Workbench, so the guard is implemented once.
- Any handle you return (`id`, `approval_id`) is a name, not a credential: look it up server-side in a Record and check the caller (`META.headers.email`) before returning status.

### 8.5 Access control, identity, events (Mode 4)
- Access control under **+ Option**: Anyone with the path (public — testing only) · Anyone with the secret (URL `?secret=` or `Authorization: Bearer <secret>`) · **With a Tines API Key** (members of specified teams / any member of the tenant; `Authorization: Bearer <api-key>`) · With OAuth (the connecting user signs in with a Tines account; **CONFLICT**: the same docs page lists OAuth under unsupported protocol features — VERIFY #25 before relying on it). This repo uses **With a Tines API Key** scoped to the ops team.
- **Include headers** (default on) captures request headers as `META.headers.*` (dashes → underscores, downcased); with API key or OAuth the caller's email is `META.headers.email`; the Authorization header is never captured. Write the email into every proposal row.
- **The client never receives the tools' credentials**; downstream calls use Tines credentials referenced by name.
- Every request emits an event: `initialize`, `tools/list`, `tools/call` (the tool result is not in the `tools/call` event; each tool emits its own event on completion). No `initialize` events → the client is not reaching the server. Rate limiting, Match rules and CORS are the webhook-shared options on the action.
- Protocol: Streamable HTTP only (no SSE, no stdio — stdio-only clients use the `mcp-remote` proxy; `Basic` versus `Bearer` in that snippet is a docs CONFLICT, VERIFY E1); tools only, text responses; no Prompts, Resources, Sessions, Notifications, Pagination or JSON-RPC batching; protocol revision 2025-11-25 supported; 100 concurrent tool calls per tenant (1,000 dedicated), counted with response-enabled webhooks.
- A Mode 4 server counts as **one flow**, consumes no AI credits, allows unlimited tools — keep it to **3–8**, one server per use case, several scoped servers per team rather than one omnibus server. Do not add, remove or rename tools while consumers are mid-session.
- Test with `npx @modelcontextprotocol/inspector` and "API Token Authentication" before connecting a real client; the Summary tab's "Remote Server" and "Claude Desktop" snippets go into the README.

### 8.6 Simplest first (`docs/01-decision-rules.md` in one line)
HTTP Request action or template → Send to Story with a Timeout Duration → AI Agent action with Tines tools and no MCP → Mode 3 with one MCP connection → Mode 4. Never MCP for bulk data movement, sub-second latency, or a destructive action without an approval path. Tool results are context, not a data plane.

## 9. Size limits that bite

Source: `DESIGN.md` (platform sweep 2026-09-24); not re-verified in the MCP research — **VERIFY** against your tenant's documentation before quoting: event payload 100 MB · HTTP Request response 30 MB · Loops run for at most 5 minutes · 30,000 events per branch · queues drop above 20,000. Documented in the MCP research: Mode 4 tool response 30 s; agent and Workbench tool output truncation 50,000 tokens; AI Agent action rate limits are rendered client-side on the docs page (spot-check in a browser). Design consequence: fan-out inside a sub-story that returns one summary; page large reads; never pass raw payloads through a model.

## 10. Change control and drafts

- Tenant policies **Enable by default** and **Require approval for all changes** (admins and owners included) are on; story requirements (name, description, owners, tags, event retention) set to required.
- Whether `/mcp` edits on a change-controlled dev story land as drafts is unpublished (VERIFY #2); the policy is on regardless. Test events under change control go to `?draft=<name>`.
- Draft naming: `git-<sha>` (ship), `rollback-<target>` (rollback), `monitor-<finding_id>` (the sweep's apply sub-story). Drafts go inactive after 30 minutes and lock on review request; test-mode credentials apply in drafts (from `DESIGN.md`; VERIFY in-tenant).
- Production is reached only by import → named draft → change request → a named person approving in Tines. `cr-promote` is denied in the IDE; `bypass_approval` exists only in `rollback.yml`'s break-glass job and is logged in `policies/break-glass-log.md`.
