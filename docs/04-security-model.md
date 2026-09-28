# 04 · Security model — threats mapped to controls, least privilege, secrets, change control, audit

_Tines Stories as Code · docs v1 (2026-09-24) · Matches `DESIGN.md` §7 · Threats are taken from Anthropic's published guidance and the Model Context Protocol (MCP) specification's security best practices; controls are named as files in this repository or settings in Tines. Anything unconfirmed is marked VERIFY._

## 1. Two principles, then everything else

Anthropic's containment guidance says to **design containment at the environment layer first and steer the model second**. The MCP specification says the protocol **cannot enforce its own consent, privacy or tool-safety principles — implementers must**. Tines' answer to both, and this repository's, is the same sentence: **the guard is a story element, and every call is an event.** A Trigger, a Condition, a Resource, change control, a hook, a permission rule, a team-scoped key — these enforce. System instructions and `AGENTS.md` request. When the two disagree, the enforcement wins, and that is by design.

## 2. Identities and least privilege

`policies/POLICY.md` is the governance contract; this is its identity table with what each identity can and cannot do.

| Identity | Where it lives | Can | Cannot | Verify |
|---|---|---|---|---|
| **builder** | Their own Tines user, through the OAuth-only Tines Stories MCP server (`/mcp`) | Everything that user can do in the dev team; the server "inherits the permissions of the user prompting it" and grants nothing more | Author in prod (`guard-mcp.sh` refuses any `/mcp` call while `TINES_ENV=prod` and any input naming a production or never-touch id) | Tool names (item 1) |
| **CI-prod** | GitHub environment `production`; a **team-scoped** API key, Editor role, in the prod team | Import into a draft, tag versions, set recipients and monitor flags, open change requests, promote an **APPROVED** request | Approve; bypass (the dispatcher accepts `--bypass-approval` only with `BREAK_GLASS=1`, which only the break-glass job sets) | Import response fields (item 6) |
| **CI-read** | `drift.yml`; a **Viewer-role** team key | Export prod, read audit logs, read AI usage | Write — read-only by role | Item 18 (expect 404 on a write) |
| **monitor-read** (`tines_api_readonly`) | A Text credential in the ops team; `allowed_hosts` = the tenant host; Workbench access off | The five read sub-stories; the router's log enrichment | Write | Item 18 |
| **monitor-apply** (`tines_api_ops`) | An Editor-role team key, only inside the apply sub-story, behind a verified Slack approval | Recipients, monitor flags into a draft, a change request titled `monitor-<finding_id>` | Approve; touch a never-touch story (a Trigger checks first) | Draft semantics (item 7) |
| **approver** | A person, in Tines | Approve and push a change request | — | Never a key in CI |
| **break-glass** | GitHub environment `break-glass`, two required reviewers | `POST /disable`; `cr-promote --bypass-approval --reason`; must append `policies/break-glass-log.md` in the same run | Anything unlogged | — |
| **the monitoring agent** (`triage`, `critic`) | An AI Agent action in the ops team | Read through five tools; propose | **Nothing** — it holds no write credential; every path to production passes a human | — |
| **the reviewer** (`tines-reviewer`, `review.yml`) | A fresh context | Read the diff, the export, the meta; run lint and diff | Write, Edit, MCP, the tenant | — |
| **propose-fix** (headless) | `propose-fix.yml` | `Edit(stories/**)` on a branch; lint; open a PR | MCP; the tenant; merge | — |

Least privilege here means **removing** a capability a role does not need, not logging or guarding it. That is why the agent has no write tool rather than a guarded one, why the reviewer has `disallowedTools: Write, Edit` rather than an instruction not to write, and why `cr-promote` is in the IDE **deny** list rather than the ask list.

## 3. Threats → controls

Each row: the threat as Anthropic or the MCP spec names it, the Tines control, and the control in this repository.

| # | Threat | What Anthropic / the spec says | Tines control | Repository control | Status |
|---|---|---|---|---|---|
| 1 | **Prompt injection through tool results** — an error log, a webhook payload, a story export, a ticket body tries to steer the model | Tool output is an attack surface even for trusted tools; treat retrieved content as data kept apart from instructions; enforce least-privilege guardrails so injected text cannot trigger sensitive tools; a more instruction-following model can be *more* susceptible | Guards are Triggers and Resources, not prompt text; escalation on explicit schema fields, never on sentiment or self-reported confidence; the agent can only propose; `critic` re-reads evidence for high/critical; `Require confirmation to run` on Workbench stories | `tools_are_requests` lint rule (any `block\|delete\|isolate\|disable` tool must start with `request_`); the propose-fix allow-list (three benign kinds; everything else becomes a diagnosis-only issue); every proposal PR passes lint, an independent review, a human merge, `ship.yml` and a human change-request approval; the Mode 4 server returns structured text, never free text scraped from a third party | Confirmed by construction |
| 2 | **Confused deputy** — one powerful credential acts for whoever can call the server | Proxy servers with a static client must obtain per-client consent; exact `redirect_uri` matching | Mode 4 access control **With a Tines API Key** scoped to the ops team; the caller's identity arrives as `META.headers.email` and is written into `ops_alert_proposals.requester`; OAuth passthrough can make a tool use each user's own credential (Mode 4 OAuth is listed both as supported and unsupported — VERIFY, item 25); multiple scoped servers per team rather than one omnibus server | One identity per job (§2); no approver key exists anywhere in CI; request tools post to a fixed channel and every button click is verified against `ops_responders` | Item 25 |
| 3 | **Token passthrough** — a server forwards the client's token upstream | Servers MUST NOT accept tokens not issued for them; upstream calls use upstream-issued tokens | Mode 4: the client never receives the tools' credentials, and the Authorization header is never captured into `headers`; downstream calls use Tines credentials; Mode 3: the agent's Bearer or OAuth credential is stored in Tines and referenced by the connection | `.env`, `.env.*`, `.mcp.json`, `.cursor/mcp.json` are **denied** to `Read` in `.claude/settings.json`; `block-secrets.sh` refuses secret-looking writes; MCP connections are re-created after import, never exported or pasted | Confirmed |
| 4 | **Session or state-handle hijacking** | Never use sessions for authentication; handles are random, bound to the user, verified on every request | Mode 4 has no sessions (listed unsupported); every request is authenticated by the access-control mode | Approval ids and job ids are looked up in `ops_alert_proposals` and checked against `ops_responders` and `META.headers.email`; proposals expire | Confirmed by construction |
| 5 | **Local server compromise** — a malicious startup command | Show the exact command; sandbox; prefer stdio only for local processes | Not applicable to Tines-hosted servers (remote, Streamable HTTP); applies to the `mcp-remote` proxy stdio-only clients need — pin its version | This repo connects only over HTTP (`"type": "http"` in `.mcp.json.example`; `url` in `.cursor/mcp.json.example`); no stdio servers are declared | Confirmed |
| 6 | **SSRF during OAuth discovery** — a malicious server points metadata at internal services | Require HTTPS, block private ranges, validate redirects | Mode 3 OAuth with Dynamic Client Registration means Tines performs discovery; Tines publishes no statement on SSRF mitigations for that flow (VERIFY) | The monitoring agent holds **no external MCP connection by default**; its only permitted MCP connection is the repo's own Mode 4 server; tunnel access (if ever used) restricted to teams | Unverified on the Tines side; not exercised by this repo |
| 7 | **Over-broad scopes and capability bloat** | Least privilege means removing capabilities, not guarding them; no omnibus scopes | Per-preset tool lists in Workbench; individually enabled tools on an MCP connection; a credential's Workbench-access toggle; team-restricted API keys; tenant owners restrict who can create keys; tunnels restricted to teams | Five read tools on the agent, added one at a time; Viewer-role keys where reads suffice; `--allowedTools` explicit on every headless job; `permissions.deny` beats `ask` beats `allow`; subagents carry their own `tools` / `disallowedTools`; `allowed_hosts` on every pipeline credential | Confirmed; item 18 |
| 8 | **Actions without a human in the loop** | A person SHOULD always be able to deny a tool invocation; read-only annotations run without confirmation, destructive ones always prompt | Reason → approve → execute; `Require confirmation to run`; Slack Confirm/Cancel; the **Destructive** hint is on by default so Claude clients prompt unless a tool is marked **Read only** | Change control with **Require approval for all changes**; GitHub environment reviewers; two approvers for `disable` in prod; every lookup on the Mode 4 server carries **Tool hints: Read only**, request tools keep the default Destructive hint | Confirmed |
| 9 | **Unverified servers and plugins** | Anthropic does not security-audit MCP servers; plugins run with the user's privileges; verify trust before connecting | Verify a vendor server before a Mode 3 connection; prefer OAuth 2.1 over a static Bearer; check the transport (Streamable HTTP or Plain HTTP only — no SSE) | This repo connects to exactly two servers: the tenant's first-party `/mcp` and the repo's own Mode 4 server; no third-party MCP server is in the default design; the simplest-first ladder (`01-thesis.md` §6) puts a vendor server on rung 4 with its checks | Confirmed |
| 10 | **Secrets collected through the model** | Servers must not request passwords or tokens through elicitation; use URL mode | Credentials are created in the Tines credential store, never typed into a chat; Mode 2 sign-in is an OAuth consent screen — API keys do not work there | `/tines-connect` reads `TINES_TENANT` from the environment and never reads `.env`; `block-secrets.sh` patterns (`X-User-Token`, `Bearer …`, `xoxb-`, `xapp-`, `AKIA…`, `sk-…`, `"value":` in a credentials-shaped object, `api_key=`); `lint.yml` + gitleaks on every PR | Confirmed |
| 11 | **No audit trail** | Clients SHOULD log tool usage; enterprises name audit trails and SSO-integrated auth as the recurring MCP gaps | Mode 2: each tool use recorded in audit logs as **MCP activity**; Mode 4: `initialize`, `tools/list`, `tools/call` events plus one event per tool completion; Workbench and agent tool uses logged with name, inputs, outputs and status; two-year default retention; S3 export every 15 minutes; the AI overview page lists every MCP server in the tenant | `guard-mcp.sh` mirrors every `/mcp` call to `.tines/mcp-activity.jsonl` and the reviewer reads the audit rows for the story since the session started; the commit SHA in every change-request description plus a story version; `drift.yml` attributes deviations via `GET /api/v1/audit_logs`; the weekly digest counts MCP activity (operation name VERIFY, item 17) | Item 17 |
| 12 | **Transport-level attacks** (DNS rebinding, missing TLS) | Validate Origin; authenticate all connections; HTTPS | Tines hosts Mode 4 behind its own TLS and authentication; Streamable HTTP only | No self-hosted MCP server is required by this repo; if one is ever added, the checklist is trusted TLS, one stateless `/mcp` endpoint, rotated Bearer or OAuth 2.1 | Confirmed |
| 13 | **Sandbox escape when running agent-generated code** | No direct network from the sandbox; credentials held by a host broker; per-call authorization | Tines does not run agent-written code against MCP tools; the deterministic loop is the story, under fair orchestration and per-action credentials | `propose-fix.yml` gives the headless instance `Edit(stories/**)` and `git`, nothing else; it never has tenant credentials | Confirmed |
| 14 | **Headless runs trusting a repository** | In `-p` and SDK runs `.mcp.json` servers connect without asking and repository hooks run; use `--bare` or `--setting-sources user`; gate on `mcp_server_errors` | Change control on the Tines side is the second gate regardless of what the editor did | The `/mcp` entry lives in **user scope** and `.mcp.json` is gitignored (only `.mcp.json.example` is committed). The headless workflows load `--setting-sources project` on purpose and fence it: `propose-fix.yml` runs from the default branch only, with `--strict-mcp-config` and an empty `--mcp-config`, explicit `--allowedTools` and `--disallowedTools`, `--max-turns`, a timeout and no persisted git token; `review.yml` runs on same-repository PRs with a read-only `--allowedTools` list, `--max-turns` and a timeout, and configures no MCP server. Neither expects `/mcp`; fork PRs receive no secrets; `allowed_bots` is empty | Items 20, 21, E8 |

## 4. Secrets — where they live and where they never go

**Where they live:** Tines credentials (with `allowed_hosts`, `expires_at` with expiry notifications, Workbench access **off** for pipeline keys); `.env` locally (gitignored, and `Read(./.env)` denied to the editor); GitHub **environment** secrets (`production`, `break-glass`) for CI keys; the OAuth session in the editor's own store for `/mcp`.

**Where they never go:** story exports (Tines omits credentials, resources and events by design; recipients are cleared by `clear_recipients=true`); `stories/_manifest.yaml` (the router webhook URL carries a secret, so it is `${OPS_ROUTER_URL}` resolved at run time); any MCP connection (connections are re-created after import, never exported); the model (a credential is referenced by name — `{{ .CREDENTIAL.x }}` — and the authoring engine sees names, not values); a URL or query string (no personal data in either); Terraform state (`value_wo` / `value_wo_version` on `tines_credential`).

**The backstops, not the rule:** `block-secrets.sh` (PreToolUse on Write|Edit, exit 2), `lint-story.sh` (`no_inline_secret`: any options value matching token, `xox[bp]-`, `Bearer `, `sk-`, `AKIA` or an email pattern fails), `lint.yml` + gitleaks on every PR, the reviewer's check (e). The credentials API never returns secret values, and an underprivileged key gets a 404 the dispatcher names as such.

**Key hygiene:** keys are created only by `API_KEY_CREATE` holders, are **team**-scoped (never personal), rotated quarterly, one per identity (§2).

## 5. Change control — the deterministic gate

- Tenant policies **Enable by default** and **Require approval for all changes** (admins and owners included; the emergency bypass is audited); story requirements (name, description, owners, tags, event retention) set to required.
- Production changes only via **import → named draft → change request → a named approver**. The pipeline never promotes a PENDING request and never sets `bypass_approval`; `cr-promote` is denied in the IDE; `bypass_approval` exists only in `rollback.yml`'s `break-glass` job (two reviewers, mandatory reason, a log line in `policies/break-glass-log.md` committed in the same run).
- Every promoted change carries the commit SHA in the change-request description and a story version (`POST /api/v1/stories/{id}/versions`), so audit can join GitHub and Tines. `drift.yml` proves prod equals `main` nightly and attributes any deviation via the audit logs; team change-control webhooks post approvals into the ops thread.
- `POST /api/v1/stories/{id}/disable` is the only bypass and is the kill switch: reserved for break-glass, with the safe-disable order documented (entry or schedule action first where possible, then the story).
- `/mcp` edits and change control: how they interact is unpublished (VERIFY, item 2). The repo does not depend on it — **production is never authored through `/mcp`** — but the policy is enabled regardless so that a dev-team mistake is still a draft.

## 6. Least-privilege tool lists

- **The monitoring agent:** no write credential; five read-only tools; a `critic` with no tools at all. Request tools instead of write tools everywhere.
- **Mode 4:** Tool hints Read only on every lookup; team-scoped access; per-tool descriptions state what the tool does *not* do; the server never receives the tools' credentials.
- **Workbench:** per-preset tool lists; the credential Workbench-access toggle disconnects template and MCP tools live; `Require confirmation to run` on stories exposed to Workbench.
- **CI:** `--allowedTools` explicit on every headless job; `Edit(stories/**)` is the only write the propose-fix instance has; job `permissions` minimal; fork PRs receive no secrets; `allowed_bots` empty.
- **Editor:** `permissions.deny` → `ask` → `allow` in `.claude/settings.json` (deny beats ask beats allow; committed allow rules apply after workspace trust; deny and ask apply immediately); `mcp__tines__*` is allowed in dev only because the PreToolUse hook runs first and an exit-2 block wins; deploy subcommands are `ask`; `cr-promote` and `terraform apply` are `deny`; `tines-reviewer` cannot Write or Edit and has no MCP.

## 7. Hooks — enforcement in the editor

| Hook | Event | Enforces | How |
|---|---|---|---|
| `guard-mcp.sh` | PreToolUse `mcp__tines__.*` | No `/mcp` call while `TINES_ENV=prod`; no call whose input references a production or never-touch story id (input-based, so it does not depend on unpublished tool names); no destructive-looking tool name without `TINES_ALLOW_DESTRUCTIVE=1` (regex — VERIFY, item 1, then replace with an explicit deny list); a local audit mirror of every call | exit 2 beats the allow rule |
| `block-secrets.sh` | PreToolUse `Write\|Edit` | No secret-looking content lands on disk | exit 2 |
| `lint-on-write.sh` | PostToolUse `Write\|Edit` | A turn that leaves a `story.json` unlintable is blocked with the findings; `SKILL.md` frontmatter failures are advisory | exit 2 for `story.json`; `additionalContext` for `SKILL.md` |
| `stop-gate.sh` | Stop | The turn cannot end with a failing lint or an export older than the last MCP call | exit 2 with the exact `/tines-export <slug>` to run |

The hooks use exit codes rather than the JSON `permissionDecision` field because the third decision value was reported inconsistently (VERIFY, item 15). **Cursor's IDE agent does not run these hooks** (item 4) — in Cursor the enforcement is CI and Tines change control, and `.cursor/rules/story-json.mdc` says so.

## 8. Review in fresh context

The generator never reviews its own work — a model keeps its generation reasoning and questions it less. `/tines-review` runs with `context: fork` on `tines-reviewer` and refuses if the session built the story; `review.yml` runs a separate Claude Code instance with no MCP, no tenant credentials and a different prompt; CODEOWNERS adds a person; branch protection forbids self-merge. Inside Tines, `critic` re-reads `triage`'s evidence for high/critical before anything leaves the tenant, and a person approves anything that changes production.

## 9. Audit — reconstructing who changed what, when and why

| Question | Answered by |
|---|---|
| Who edited a dev story from an editor, and with which tool? | Tines audit logs (**MCP activity** rows, with the user's identity — OAuth carries their Tines user); `.tines/mcp-activity.jsonl` locally |
| What exactly changed? | `git log -- stories/<slug>/story.json`; `./scripts/diff-story.sh`; `GET …/change_request/view` (`live_story_export` vs `draft_export`) |
| Who reviewed and who merged? | The PR (findings comments from `review.yml`; CODEOWNERS approval; merge author) |
| Who approved in the tenant? | The change request in Tines; the team change-control webhook in the ops thread |
| Which commit is live? | The change-request description (commit SHA) + the story version named `release <sha>` |
| Did the tenant drift from `main`? | `drift.yml` nightly: export → diff → attribution table from `GET /api/v1/audit_logs` (`user_email`, `operation_name`, `source`, `request_user_agent`) → a PR labelled `drift` |
| Who called a Mode 4 tool? | `initialize` / `tools/list` / `tools/call` events on the server action; `META.headers.email`; the tool's own completion event |
| What did the agent read and propose? | The AI Agent action's event payload (full conversation `steps`, `meta` with model, tokens, credits); `ops_findings` and `ops_alert_proposals` Records; audit-log rows for each tool use |
| Was break-glass ever used? | `policies/break-glass-log.md` (date · story · who · reason · `change_request_id` · audit-log ids · follow-up PR), committed in the same run |
| Long-term retention | Audit logs default two years (minimum 30 days); native S3 export every 15 minutes to the SIEM — not through a story |

## 10. Data policy, named

Mode 2 runs on **your editor's provider**, so what the editor sends its provider is governed by your organisation's editor data policy, not Tines' foundation guarantees (private, stateless, geo-bound, tenant-scoped; no networking, training, storage or logging), which cover Modes 1 and 3. Story exports contain configuration only — no credential values, resource contents or events. The AI Agent action's web search is processed by a third-party provider with zero data retention; tenant owners can disable it; egress-restricted tenants cannot use it. The AI overview page lists every MCP server in the tenant.

## 11. Residual risks (honest)

1. **`/mcp` tool names are unpublished**, so the destructive-name guard is a regex until your client lists them (item 1). The input-based ID check does not depend on names and is the real production guard.
2. **Cursor does not run the hooks.** A Cursor builder is protected by CI, change control and the never-touch list — not by the editor.
3. **`/mcp` × change control is unverified** (item 2). Mitigated by never authoring in prod.
4. **Mode 4 OAuth access mode is contradictory in the docs** (item 25). The repo uses a team-scoped API key, which is documented unambiguously.
5. **The monitor is itself a story that can fail** — double signals, notification storms, a stale lock. The router dedupes, the watchdog pages the DL, the lock has a staleness rule.
6. **LLM-edited JSON can break index-based links.** Only three benign fix kinds are auto-applied; lint and review catch the rest; the safer default is an issue with a prompt.
7. **A Viewer-role key being read-only is asserted by role, not tested** until item 18 is confirmed.

## Verify in your tenant before presenting

A security reviewer should ask for four things and get four files: least privilege → `policies/POLICY.md`; cost ceiling → `policies/cost-ceilings.yml`; auditability → the commit SHA in a real change-request description plus a story version plus one audit-log row of MCP activity; rollback → `.github/workflows/rollback.yml` run once against the dev team. Before the meeting, confirm items 1, 2, 18 and 25 in `07-verify-before-you-rely-on-it.md`.
