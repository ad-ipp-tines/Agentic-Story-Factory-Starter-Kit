# 01 · The thesis — the value is the system around the prompt

_Tines Stories as Code · docs v1 (2026-09-24) · Matches `DESIGN.md` §1 · Facts from public Tines documentation (current to 2026-09-17) and Anthropic's published guidance; anything else is marked VERIFY and listed in `07-verify-before-you-rely-on-it.md`._

## 1. The claim in one paragraph

Anyone can open an AI assistant and type "build me a phishing triage story". Since 2026-06-02 that prompt can go straight into a Tines tenant through the **Tines Stories MCP server** — a first-party Model Context Protocol (MCP) endpoint at `https://<your-tenant>.tines.com/mcp` that lets Cursor, Claude Code, Claude Desktop, ChatGPT, Codex or Microsoft Copilot read, create, change and validate stories with the same authoring capabilities Workbench for Storyboard uses in build mode. The prompt is the cheapest part of that sentence. What makes the result **fast, controlled and safe** is everything the prompt sits inside: a procedure the editor follows every time, an export in git that gives you a diff on every change, deterministic lint, a reviewer that is not the author, hooks that enforce instead of ask, change control that no prompt can argue past, an ops pair that watches production and proposes with evidence, budgets that are files, and keys that cannot approve. This repository is that system. The prompt still ships with it — literally, as a prompt pack — but the repository is what a security reviewer signs off on.

The "new way of building" is therefore **not prompting harder. It is prompting inside a system** that makes every output diffable, reviewable, gated, observable and reversible.

## 2. What changed (dated)

The pieces below are what makes an editor-driven, git-backed, agent-monitored loop possible today. Every date is a published Tines "What's new" entry or documentation page unless marked otherwise.

| Date | What shipped | What it makes possible in this repository |
|---|---|---|
| 2025-08-05 | **MCP server action** (template picker label "MCP Server") — your stories, templates and Custom tools exposed as MCP tools at `https://<your-tenant>.tines.com/mcp/<mcp-path>`; all plans including Community Edition; consumes no AI credits; counts as a flow | **Mode 4:** `stories/ops-tools-server/` exposes the ops lookups and request tools to editors, Claude clients and the on-call person |
| 2025-11-07 | **AI Agent action** can call tools from remote MCP servers, including ones built in Tines | **Mode 3:** the monitoring agent may attach the repo's own Mode 4 server as its single MCP connection once stable |
| 2026-03-10 | `META.headers.*` — header values such as the authenticated user's email available inside a story and in MCP tool inputs | The Mode 4 server writes the caller's email into `ops_alert_proposals.requester` |
| 2026-03-25 · 2026-05-20 · 2026-06-04 | OAuth as a Mode 4 access-control mode · multi-team access control · OAuth passthrough (per-user credentials per tool) | Team-scoped access on the ops server (this repo uses **With a Tines API Key**; the OAuth mode is listed both as supported and unsupported on the same docs page — VERIFY, item 25) |
| 2026-05-01 | **Workbench** MCP connections (Mode 1); Workbench for Storyboard starts consuming AI credits | Explains why Mode 2 from an editor is the credit-neutral authoring path |
| **2026-06-02** | **The Tines Stories MCP server** at `/mcp` — OAuth only; "your client uses the same story authoring capabilities as Workbench for Stories in build mode"; every tool use recorded in audit logs as MCP activity | **Mode 2:** every build in this repository (`02-workflows.md` §1) |
| 2026-06-29 · 2026-08-26 | Story change-control requirements · change-control comments; tenant policies **Enable by default** and **Require approval for all changes** | The deterministic gate on every production change (`02-workflows.md` §2.9) |
| 2026-07-31 · 2026-09-02 | `/mcp` works with Apps · a full set of Cases tools in the Tines MCP | Out of scope for this repository (stories only), but the same OAuth connection carries them |
| 2026-08-10 | A credential's **Workbench access** toggle disconnects templates and MCP tools using it from Workbench; storyboard use continues | Pipeline keys are created with Workbench access **off** |
| **2026-08-11 · 2026-09-01** | **Agent Skills** attach to AI Agent actions (the same `SKILL.md` files as Workbench) · skills have full CRUD API endpoints | **Skills as code:** `tines-skills/` is pushed by `skills.yml` through `POST`/`PUT /api/v1/skills` |
| 2026-08-13 | Custom AI credit usage alerts — thresholds tenant-wide, for unallocated credits and per team; email, in-app or webhook | The router receives the credit alert; defaults reported as 80 % / 100 % (VERIFY, item 10) |
| 2026-04-17 | Tool output truncation controls (50,000-token default) on agents and Workbench | A safety net under the 3–5-field tool contract |
| Editor side (Claude Code, Cursor, Agent Skills spec) | Skills (`SKILL.md`), path-scoped rules, subagents with their own MCP servers, PreToolUse/PostToolUse/Stop hooks, headless runs with `--json-schema`, MCP tool schemas deferred by default; Cursor reads `AGENTS.md` natively and `.claude/skills/` as a legacy path (VERIFY, item 4) | One skills tree, one conventions file, four hooks, one reviewer subagent, CI review with structured findings |
| 2025-08-01 | Terraform provider `tines` 0.3.0 (0.x — breaking changes possible in minors) | The optional `terraform/` path; not on the default pipeline |

## 3. What did not change

The runtime is the same Tines. That is the point: this repository adds a build system around the product, not a new product.

- **Stories, actions, events, credentials and resources** are what they were. Exports still carry **no credential values, no resource contents and no events**; import still matches an existing story **by name**; embedded sub-stories are not imported; MCP connections are dropped on import and re-created by hand. The authoring engine behind `/mcp` sees what Workbench for Storyboard sees — all actions in the current story, configurations, formulas, connections, recent execution logs, referenced credential and resource **names** — and cannot see other stories, data in flight, credential values or resource contents.
- **Credits are consumed by exactly three features** — the AI Agent action, Workbench and Workbench for Storyboard. The Tines Stories MCP server is not on that list (whether its research and listing helpers cost credits is unpublished — VERIFY, item 11). One credit is $0.01; the monthly allocation resets on the 1st; a custom provider bypasses credits but still bills externally.
- **The AI Agent action's economics** are unchanged: in Task mode it uses the cheaper model until a tool is added, then the smart model; the Status tab carries token-usage alerts (Notify or Disable action, per Daily/Weekly/Monthly/All time); it is Business/Enterprise only and unavailable in personal teams.
- **Guards live in the story.** A Trigger, a Condition, a Resource, change control, `Require confirmation to run` — these enforce. Prompt text requests. Anthropic's own guidance says the same for editors: an instruction is a request, a hook is enforcement.
- **A person approves.** Change control with **Require approval for all changes** is the deterministic gate, and no key in CI can approve.
- **The simplest-first ladder** still applies (§6). An HTTP Request action is still cheaper, faster and more predictable than an agent; an agent is still cheaper than an agent with MCP tools.
- **Plan gating** still applies: the AI Agent action, Cases, Apps, change control and dedicated-tenant limits depend on the plan. A Community Edition tenant can run a Mode 4 server (documented: all plans) but cannot run the monitoring agent; the docs describe `/mcp` as "built into your Tines Stories tenant" and state no plan gating either way, so confirm it on a Community tenant before saying so (item 13).

## 4. The system around the prompt

| Around the prompt | What it gives you | Without it | Where it lives |
|---|---|---|---|
| A procedure the editor follows every time — explore → plan → implement → validate → export → review | Speed without re-deriving the craft; a junior builder ships like a senior one | Each build starts from a blank prompt; the quality depends on who typed it | `.claude/skills/tines-build-story/` (+ `references/prompt-pack.md`) |
| One conventions file both editors load | Stories that look alike across builders; a reviewer knows what "normal" is | Ten builders, ten naming schemes, ten error-handling habits | `AGENTS.md` (Cursor reads it natively; `CLAUDE.md` imports it) |
| A stable JSON export in git | A diff on every change and a rollback point for free | "What changed?" is answered by clicking through a canvas; rollback is memory | `stories/**/story.json`, `scripts/normalize.jq` |
| Deterministic lint | Rules a security team can read without reading prose; the same check in the hook, the skill and CI | Conventions are advice; drift is discovered in an incident | `scripts/lint-story.sh`, `policies/lint-rules.yml` |
| A reviewer that is not the author | The generator never approves its own work | The model keeps its generation reasoning and questions it less | `.claude/agents/tines-reviewer.md`, `.github/workflows/review.yml` |
| Hooks | Enforcement, not advice | The prompt says "never touch production"; the prompt is a request | `.claude/hooks/*` (guard-mcp, block-secrets, lint-on-write, stop-gate) |
| Change control with **Require approval for all changes** | A gate no prompt can argue past; a live-vs-draft diff for the approver | An editor with a builder's permissions can change production directly | `ship.yml`, `02-workflows.md` §2.9 |
| The ops pair (router + sweep) | Observability that proposes with evidence and never acts alone | Failures go to an inbox; thresholds are guesses; nobody watches credits | `stories/ops-error-router/`, `stories/ops-story-health-monitor/` |
| Budgets as files, token alerts, tool caps | A cost ceiling that fires before the platform does | The first signal is the platform stopping the story at 100 % | `policies/cost-ceilings.yml`, per-agent Status-tab alerts |
| Team-scoped keys, OAuth, allow-listed credentials | Least privilege by construction | One personal key in CI that can do everything, including approve | `.env.example`, GitHub environment secrets, Tines credentials |

## 5. Three ways to build a story today

Where the same authoring engine sits under two of the three, the choice is deliberate.

| | **Workbench for Storyboard** (in the tenant) | **Mode 2** — the Tines Stories MCP server from an editor | **API / Terraform** |
|---|---|---|---|
| How it knows the tenant | Built in — it is inside the story | Learns it through tools, on request, one story at a time | You tell it: `story.json` + `team_id` + `folder_id` |
| Where the model runs | Tines' foundation (private, stateless, tenant-scoped; default provider Anthropic Claude via AWS Bedrock) or a custom provider | **Your editor's provider** — governed by your organisation's editor data policy, not Tines' guarantees | No model |
| Credits | Consumes AI credits (from unallocated credits, since 2026-05-01) or a custom provider | **No Tines credits listed**; the "research and listing helpers" are unconfirmed (VERIFY, item 11) | None |
| Authentication | Your Tines login | **OAuth only** — an API key will not work; consent screen titled **Tines Stories MCP server** | Team, personal or service API key (Bearer) |
| Review model | Propose → preview → accept or undo in the chat; an undo reverts to the version saved before the change | Export → **diff in git** → independent review → merge → change request | `terraform plan` / a PR on the JSON |
| Bulk, consistent edits across many stories | One story at a time, by hand | Natural — the editor holds the repo; but the server works one story at a time, so bulk means a loop of single-story sessions | Natural (`for_each` over files) |
| Change control | Same engine; whether `/mcp` edits always land as drafts is unpublished (VERIFY, item 2) | Same VERIFY; **this repo never authors in prod** — production changes go through import → draft → change request | `change_control_enabled = true` exists on `tines_story`; draft-vs-live behaviour on apply is VERIFY (item 22) |
| Headless / CI | No | **No** — OAuth only; a headless session reusing an interactive OAuth session is unverified on both sides (VERIFY, item 20) | Yes — this is why `ship.yml` uses the API, never `/mcp` |
| Audit | Workbench actions in audit logs | Each tool use recorded as **MCP activity**; the repo adds a local mirror | Standard API audit rows |
| Skills | Skills on presets | Editor skills (`.claude/skills/`) + tenant skills via the API | No `tines_skill` resource; skills stay on the API path |
| Status | Shipped; renamed from Story copilot 2026-06-02 | Shipped 2026-06-02; tool names unpublished (VERIFY, item 1) | Provider 0.3.0 (2025-08-01); TEXT credentials only |

**This repository's choice:** author in **Mode 2** (diffs, review, your provider, no Tines credits listed), ship through the **API** (headless, team-scoped key, change control), and keep Workbench for Storyboard as the in-tenant alternative a builder chooses on purpose — with `tines-skills/story-build-conventions` attached to its preset so answers given inside Tines match the repo (whether Workbench for Storyboard honours preset skills is VERIFY, item 14).

## 6. The simplest-first ladder (decision rules)

Read this before choosing an agent or MCP for anything. The rungs are ordered by cost, latency and blast radius; climb only when the rung below cannot do the job.

1. **An HTTP Request action or a template.** Known API, known sequence, no judgment. Deterministic, no credits, fastest, easiest to lint.
2. **A Send to Story sub-story with a Timeout Duration.** Reuse inside the tenant; the sub-story is the Tines subagent: it receives only the fields you pass and returns one `result` of 3–5 fields.
3. **An AI Agent action with Tines tools and no MCP.** Judgment over Tines data, or chat. Output schema always; one tool first, at most five; a Trigger after the agent on an explicit schema field; a token alert on the Status tab; a budget line in `policies/cost-ceilings.yml`.
4. **Mode 3 — an AI Agent action with an MCP connection.** A vendor already hosts a server, or you built one in Tines (Mode 4). One tool first; enable tools individually; Streamable HTTP or Plain HTTP only (no SSE, no stdio); Bearer/header or OAuth 2.1; Business or Enterprise plan. Importing a story drops the connection — re-create it, never paste a token.
5. **Mode 4 — an MCP server action.** An AI client outside Tines must trigger a workflow or read data. Read tools plus **request** tools (a request tool posts an approval and returns `{approval_id, status: pending}` — it never executes the destructive thing); **Tool hints: Read only** on every lookup; team-scoped access; 30-second tool ceiling, so long work returns `{status: started, id}` and a status tool.

And orthogonally: **Mode 2 whenever the builder lives in an editor and wants diffs.**

Never use MCP for bulk data movement, sub-second latency, or a destructive action with no approval path. Tool results are context, not a data plane — fan out inside a sub-story and return the summary. A typed, gate-able, auditable request tool beats a generic "run anything" tool every time (a single catch-all tool that accepts both safe and unsafe methods is also what Claude's connector directory rejects).

## 7. The loop, mapped

Anthropic teaches one loop for editor-driven work: **explore → plan → implement → verify → commit**, with a fresh-context review before calling it done, a check the model can run, and "after two failed corrections on the same issue, clear and restart". Tines documents a five-step flow for `/mcp`: add the URL, approve the consent screen, prompt in the context of one story, the client reads/creates/updates/validates, you review in Tines. This repository is the two laid on top of each other, with names:

| Step | In this repository | The check |
|---|---|---|
| Explore | `tines-builder` reads the story named in `stories/_manifest.yaml` through the Tines Stories MCP server: actions, connections, recent logs, referenced credential and resource names | — |
| Plan | Anything bigger than a sentence becomes a numbered list of actions with type, name and field names; wait for a yes | The person |
| Implement | One prompt per action from `prompt-pack.md`; `DEFAULT()` fallbacks; failure path and HTTP hardening as you go | `guard-mcp.sh` blocks production ids and destructive-looking names; `block-secrets.sh` blocks secret-looking writes |
| Verify | End with **Validate**; post `tests/sample-event.json` to the entry action; compare with `tests/expectations.yaml` | A validation pass plus a test event is the Tines equivalent of a test suite |
| Commit | `/tines-export` → `normalize.jq` → `lint-story.sh` → `diff-story.sh` → `story(<slug>): …` on `story/<slug>/<short>` | `lint-on-write.sh` (blocking) and `stop-gate.sh` (no stale export) |
| Review in fresh context | `/tines-review` on `tines-reviewer` (no MCP, read-only tools); `review.yml` in CI with a different prompt and no tenant | Findings JSON; CODEOWNERS; no self-merge |
| Ship | `ship.yml`: version → import as draft → recipients + `monitor_failures` → change request | A person approves in Tines after reading the live-vs-draft diff |
| Observe | The ops pair: router dedupes and enriches; the sweep pre-filters deterministically; only anomalies reach `triage` | Schema, not sentiment; a critic for high/critical |
| Roll back | `/tines-rollback` + `rollback.yml`; break-glass is a separate two-reviewer job | `drift.yml` proves prod equals `main` that night |

## 8. Same prompt, two outcomes

**The prompt alone.** "Build me a phishing triage story." An editor connected to `/mcp` will do it — in whatever team the builder happens to be in, with whatever naming the model picked, with the default 25 HTTP retries (about 3 h 20 min of retrying), `emit_failure_event` on "Error response only" (which misses timeouts and DNS failures), no watchdog, no output schema on the agent if it added one, no token alert, no budget line, and no record of what it did beyond the audit log. The next person opens the canvas and reads.

**The prompt inside the system.** `/tines-build-story sec-phish-triage "Build me a phishing triage story"` in the dev team: the skill reads the manifest, asks for a plan, applies the prompt pack (entry → `normalize` → guard Trigger → integrations by credential **name** → `verdict` → `result` → `error` → hardening → Note), ends with Validate and a test event, exports, lints, and refuses to end the turn with a stale export. The PR shows a semantic diff; a reviewer that did not write it lists findings against `AGENTS.md`; a human merges; `ship.yml` opens a change request whose description carries the commit SHA; an approver reads the live-vs-draft diff; the router becomes the story's monitoring recipient; the sweep baselines it. Six weeks later the monitor notices the vendor started returning 429s, proposes a throttle with the evidence rows, and a person clicks approve.

Same prompt. The second one is the product.

## 9. What this thesis does not claim

- It does not claim to know the `/mcp` tool names or count ("dozens" is an observation). The hook guard is a regex plus an input-based ID check until your tenant's client lists them (item 1).
- It does not claim that `/mcp` edits land as change-control drafts (item 2). The repo never authors in production, so the claim is not load-bearing — but it is unverified.
- It does not claim the Tines Stories MCP server is credit-free — only that it is not on the list of credit-consuming features and that the helpers are unconfirmed (item 11).
- It does not claim a headless session can reuse an interactive OAuth session (item 20). CI never touches `/mcp`.
- It does not claim Cursor runs this repo's hooks. It does not (item 4); in Cursor the enforcement is CI and Tines change control.
- It does not claim a per-team credit allocation, a credit-alert threshold or an agent token threshold can be set through the API. They cannot on current evidence; those stay by hand, and the agent can only propose them.

The full list is `07-verify-before-you-rely-on-it.md`; the ledger of what your tenant has confirmed is `VERIFY.md`.

## Verify in your tenant before presenting

Do not put any of the following on a slide until the ledger says confirmed: the `/mcp` tool list, `/mcp` × change control, credit consumption by `/mcp` helpers, the Mode 4 OAuth access mode, flow counting for sub-stories used as tools, the credit-alert defaults. Everything else in this file is either a documented Tines fact (dated in §2) or a property of this repository you can read in the files named in §4.
