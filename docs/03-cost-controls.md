# 03 · Cost controls — credits, tokens, models, tools, the sandbox team, the editor and CI

_Tines Stories as Code · docs v1 (2026-09-24) · Matches `DESIGN.md` §6 · "Tenant" = a Tines setting; "repo" = a committed file; "editor" = a Claude Code / Cursor feature; "CI" = a workflow. Prices and limits are the ones Tines and Anthropic publish; anything else is marked VERIFY._

The cost principle of this repository: **cost is a property of the design, not a hope.** The build loop is off the Tines credit meter; runtime AI is bounded by schemas, tool caps, token alerts, a daily run cap, a kill switch and a file of budgets; and the first signal is never the platform stopping a story at 100 %.

## 1. What costs Tines AI credits and what does not

Tines' credits article lists **exactly three** credit-consuming features: the AI Agent action, Workbench, and Workbench for Storyboard. One credit = $0.01. The monthly allocation is set by plan tier and resets on the 1st; purchased top-ups roll over, the monthly allocation does not; Community Edition tenants get 50 credits a month. A custom provider (Admin → AI) bypasses Tines credits but still bills you externally — the AI usage API reports it as `billed_cost`.

| Thing | Tines AI credits? | Counts as a flow? | Where the bill lands | Notes |
|---|---|---|---|---|
| **AI Agent action** (Tines-provided model) | **Yes** — per execution; `meta.credits_used` on every event | Part of its story's flow | Tines credits | Task mode uses the cheaper model until a tool is added, then the smart model; Business/Enterprise only; unavailable in personal teams |
| AI Agent action on a **custom provider** | No | Part of its story's flow | Your provider (`billed_cost`) | Bypasses credits; still money; the ledger records the model per run so the two are never confused |
| **Workbench** (incl. in Slack, for Cases) | **Yes** (Tines model) | — | Tines credits | 20 daily messages on all plans; conversations capped at 200K tokens; Workbench does not consume credits on Community per one Explained page — a May 2026 recap says all Workbench experiences consume credits (CONFLICT; VERIFY for a Community tenant) |
| **Workbench for Storyboard** (build mode in the tenant) | **Yes** — since 2026-05-01, from unallocated credits | — | Tines credits | The in-tenant alternative to Mode 2; smart model |
| **The Tines Stories MCP server (Mode 2)** — building from your editor | **Not listed** as a credit-consuming feature; whether its research and listing helpers consume credits is unpublished (**VERIFY, item 11**) | — | **Your editor plan / your provider** | The model runs in the editor; this is why the build loop is "off the meter" |
| **MCP server action (Mode 4)** | **No** — "does not consume AI run-time credits" | **Yes** — one flow with connected tools | Nothing beyond the flow | No extra charge; all plans including Community |
| **Send to Story sub-stories** (used as tools or otherwise) | No | Their Webhook input is an autonomous trigger, so **yes** on current reading; whether several in one graph count as one is deferred to the account team (**VERIFY, item 13**) | Flow count | Group actions into Custom tools (Groups) on the agent to reduce the count once stable |
| HTTP Request, Event Transform, Trigger, Records, Cases, Resources | No | Part of a flow | — | The deterministic path; "a healthy sweep costs zero credits" |
| Stories enabled **for Workbench only** | No | **No** — they cannot run autonomously and do not count toward licence counts | — | Useful for a Workbench-only lookup |
| **CI `review.yml` / `propose-fix.yml`** | No | — | **Your Anthropic API key** (`ANTHROPIC_API_KEY` secret) | Bounded by `--max-turns` (10 / 15), `timeout-minutes` (15 / 20), a concurrency group; measure the first five PRs before setting a monthly figure |
| The editor session itself | No | — | Your editor plan | Resident context kept small (§6) |
| Terraform (optional) | No | Whatever the stories are | — | Not on the default pipeline |
| Tines tunnel, audit-log S3 export | No | — | Your infrastructure | Not used by this repo's default path |

Two things people get wrong: (1) a **custom provider set as the tenant default** makes credits look like zero while the external bill grows — the sweep checks which provider each agent uses and the ledger records `billed_cost`; (2) adding **one tool** to a tool-less Task-mode agent moves it from the cheaper model to the smart model — `critic` is tool-less on purpose.

## 2. The controls, as a table

| Control | Mechanism | Layer | Enforced by | Verify status |
|---|---|---|---|---|
| The build loop spends no Tines credits | Author through the Tines Stories MCP server; the editor's model does the reasoning | editor | Design choice; `AGENTS.md` | Helpers VERIFY (item 11) |
| Budgets are files | `policies/cost-ceilings.yml` is the single source (tenant budget, per-team credits, per-agent daily tokens / credits per run / runs per day, CI turn caps) | repo | `drift.yml` budget job reads it (`./scripts/tines ai-usage`); the sweep reads the same numbers from the `ops_limits` Resource (mirrored by hand); `lint.yml` fails a PR that adds an AI Agent action without a budget line | Confirmed by construction |
| A healthy sweep costs zero credits | Deterministic pre-filter (an Event Transform) decides which stories reach `triage`; info-level findings are logged, never sent to the model | tenant (story) | A Trigger `has_anomaly` before the agent | Confirmed by construction |
| Per-run and per-day caps on the agent | `agent_runs_per_day_max` (a Records count) and `agent_credits_per_run_max` as Triggers; `max_proposals_per_day` in `ops_limits` | tenant (story) | Triggers before the agent and before a proposal | Confirmed by construction |
| Token alerts on every AI Agent action | Status tab → Monitoring Alerts: token-usage thresholds per Daily / Weekly / Monthly / All time; **Notify** at `daily_tokens_notify`, **Disable action** at `daily_tokens_disable` | tenant | Set [BY HAND]; recorded in `story.meta.yaml: ai.agents[].token_alert`; the reviewer refuses a story whose meta lacks it | Published feature |
| Tenant credit alerts | Admin → AI: AI credit usage alerts tenant-wide, for unallocated credits and per team; email, in-app or webhook → the router | tenant | Set [BY HAND] — no API | Defaults 80/100 VERIFY (item 10) |
| Per-team credit allocation | Admin → AI | tenant | [BY HAND]; mirrored in `cost-ceilings.yml` | No API on current evidence |
| Tool output stays small | Tools return 3–5 fields via a `result` Event Transform; Tool output truncation stays on (50,000 tokens) | tenant | `AGENTS.md`; lint rule `substory_result_et`; the reviewer | Published default |
| Cheap model where possible | Task mode without tools = fast model; `critic` has no tools; `triage` is the only smart-model call and runs only on anomalies | tenant | Design; the reviewer checks tool counts | Published behaviour |
| Fixed tool sets | One tool first, at most five per agent; 3–8 per Mode 4 server; never change a tool definition mid-session | tenant | `AGENTS.md`; the reviewer | Anthropic guidance; Tines "one tool first" |
| The sandbox team | Every build in the dev team with test-mode credentials; `ship.yml` touches prod once per merge | tenant + CI | `TINES_ENV=dev` + `guard-mcp.sh`; the dispatcher refuses prod without `TINES_ALLOW_PROD=1` | Confirmed by construction |
| Vendor free-tier pacing | Throttle mode on paced templates; verdicts cached in an `ioc_cache` Record with a TTL | tenant | The worked example `stories/example-enrich-ip/` | — |
| Flow budget | The ops trio ≈ 9 flows; sub-stories reused, never duplicated; Custom tools (Groups) consolidation once stable | tenant | `stories/_manifest.yaml`; Settings → Access & security → Story allocation | Sub-story counting VERIFY (item 13) |
| Small resident context | `AGENTS.md` < 200 lines; skills ≈ 100 tokens each until invoked; references on demand; `/mcp` declared only on `tines-builder` | editor | File sizes; subagent frontmatter | Claude Code defers MCP schemas by default |
| Bounded CI | `--max-turns`, `timeout-minutes`, concurrency per PR, path filters, `lint.yml` first, **no MCP in CI** | CI | Workflow files | Confirmed by construction |
| Headless caps | `--setting-sources project` (the repository's settings, loaded on purpose) fenced by explicit `--allowedTools`, `--max-turns` and a timeout in both workflows; `propose-fix.yml` (default branch only) adds `--strict-mcp-config` with an empty config, `--disallowedTools` and no persisted git token; `review.yml` adds `--json-schema`; proposals capped by `max_proposals_per_day` | CI + tenant | Workflow files; `ops_limits` | CLI flags VERIFY (items 21, E8) |
| Event and rate-limit hygiene | One event per notification; router dedupe; retention raised only on ops stories; backoff on 429 | tenant + repo | The router; `scripts/tines` | API limits per `DESIGN.md` §6.6 |

## 3. Credits (tenant + story)

**Budgets as a file.** `policies/cost-ceilings.yml` carries the tenant's monthly credit budget and alert percentages (a mirror of Admin → AI, where the alerts are actually set), per-team monthly credits (`ops: 300`, `dev: 500` in the committed example — replace with yours), per-agent lines (`daily_tokens_notify`, `daily_tokens_disable`, `credits_per_run_max`, `runs_per_day_max`), CI caps and the rule `new_ai_agent_action_requires_budget_line: true`. It is read by `drift.yml`'s budget job and mirrored by hand into the `ops_limits` Resource the sweep reads (`credit_budget_daily.default`, `credit_budget_daily.per_story`, `credit_alert_pct: [80, 95]`, `agent_runs_per_day_max`, `agent_credits_per_run_max`).

**Visibility.** `GET /api/v1/ai_usage` grouped by story, team, action or day, with `credits_used`, `billed_cost`, input/output/cached tokens and `usage_count`. Every AI Agent action event carries `meta` with the model, tokens, `credits_used`, `remaining_credits` and duration; the sweep writes those to `ops_findings` per run, and the daily branch writes `ops_credit_ledger`, so **credits per completed finding** can be scored.

**The 80 / 95 / 100 rule.** At 80 % (of a story's daily budget or a team's monthly credits) the sweep posts the digest by team and story with the costliest agents (`GET /api/v1/ai_usage?story_id=&group_by=action`). At 95 % it proposes pausing the costliest agent or routing it to a custom provider (`credit_action`, human-approved). At 100 % the platform stops the story — so 80 % is the actionable alert and 100 % is the backstop, not the plan.

**Provider check.** A custom provider is a deliberate choice for a named agent, never a tenant default set by accident; the sweep records the model and provider per run.

## 4. Token alerts (per agent)

Every AI Agent action in this repo carries a token-usage alert on its **Status tab**: **Notify** (to the story's recipients — the router) at `daily_tokens_notify`, **Disable action** at `daily_tokens_disable`. The committed example for the sweep: `triage` 150,000 / 300,000 tokens per day; `critic` 50,000 / 100,000. The alert is set [BY HAND] (no API), recorded in `story.meta.yaml`, and the reviewer refuses a `tier: production` story whose meta lacks it. Tool output truncation stays on at 50,000 tokens as the safety net; the design rule is that tools return 3–5 fields, never raw data, so intermediate data never passes through the model.

## 5. Model routing

- **Task mode without tools runs on the tenant's fast model**; adding a tool switches to the smart model. So `critic` (no tools, re-reads `evidence[]`) is cheap by construction, and `triage` (five tools) is the only smart-model call — and it runs only on anomalies.
- **The reviewer subagent** uses `model: inherit` in the committed file; a smaller model is acceptable for review and chosen per tenant. No model ids are hard-coded anywhere in the repo.
- **Prompt caching** (relevant on a custom provider that caches): the cached prefix is tools → system → messages, so changing any tool definition invalidates all of it; cache writes cost 1.25× (5-minute) or 2× (1-hour) of base input price and reads 0.1×. Keep each agent's enabled tool set fixed per action.
- **Mode 2 has no model choice on the Tines side** — it is your editor's model, on your editor's plan.

## 6. Tool counts and definitions

Anthropic's numbers: every enabled tool's name, description and input schema is sent on every model call; a typical five-server setup costs about 55k tokens of definitions before any work; tool-selection accuracy degrades once 30–50 tools are available. Tines publishes no deferred loading or tool search for the AI Agent action or Workbench (VERIFY) — assume every enabled tool is sent on every call.

The repo's rules: **one tool first, at most five per agent**; tools added one at a time so a schema fault is attributable; split jobs across agents rather than growing one agent's list; **3–8 tools per Mode 4 server**; fan-out happens inside a Send to Story sub-story that returns one summary — the loop lives in the story, not in the model. Never rename or reorder tools on the Mode 4 server while consumers are mid-session.

On the editor side the same idea: the `/mcp` server's dozens of authoring tools are declared only on the `tines-builder` subagent, and Claude Code defers MCP tool schemas by default (only names and server instructions load at session start), warns at 10,000 tokens per MCP result and caps at 25,000.

## 7. The sandbox team (dev)

- Every build happens in the **dev team** with test-mode credentials and resources on change-controlled stories; production credentials never spend during a build.
- Free-tier vendor limits are paced (throttle mode) or cached (`ioc_cache` Record with a TTL) so a rehearsal never burns a quota.
- The dev team has its own credit line (`dev: 500` in the example) for test runs of AI Agent actions and dev sweeps; the AI Agent action is unavailable in personal teams precisely "to avoid depleting your tenant-wide credits" — another reason the dev team is a real team.
- Flows: Workbench-only stories do not count; sub-stories are reused; the ops trio is budgeted at about 9 flows (VERIFY, item 13).

## 8. IDE-side limits (editor + CI)

- **Resident context:** `AGENTS.md` under 200 lines; each skill costs about 100 tokens until invoked; references (`prompt-pack.md`, `story-conventions.md`) load on demand; path-scoped rules load only for matching paths.
- **Subagents:** `tines-builder` holds the `/mcp` server so its tool descriptions never enter the main conversation; `tines-reviewer` holds nothing but read tools.
- **CI:** `review.yml` `--max-turns 10`, `timeout-minutes: 15`; `propose-fix.yml` `--max-turns 15`, `timeout-minutes: 20`, `concurrency: proposals`; a concurrency group per PR with cancel-in-progress; path filters (`stories/**`, `tines-skills/**`, `policies/**`, `.claude/skills/**`); `lint.yml` (no model) runs first so obvious failures never reach the model; **no MCP in CI** (OAuth only anyway).
- **Headless:** both workflows run with `--setting-sources project` (the repository's skills, agents, permission rules and hooks load on purpose), an explicit `--allowedTools` list, `--max-turns` and a timeout. `propose-fix.yml` runs from the default branch only and adds `--strict-mcp-config` with an empty `--mcp-config`, a `--disallowedTools` list and a checkout with no persisted git token; `review.yml` runs on same-repository PRs and adds `--json-schema` output. The propose-fix path is capped by `ops_limits.max_proposals_per_day`.
- **Rate limits the scripts respect** (per `DESIGN.md` §6.6): API 5,000 requests/min default, actions 100/min, audit_logs 1,000/min, records 400/min, with backoff on 429. AI Agent action limits (published, table rendered client-side — spot-check): input tokens per minute per tenant 900,000 (eu-west-1) or 1,500,000 (other regions); runs per minute per tenant 40 or 100; AI provider 500 runs/min. Workbench: 200 messages and tool runs/min, 2,000,000 input tokens/min.
- **Events:** one event per notification, never per log line; the router dedupes per story + action + 15 minutes; retention is raised only on the ops stories; the 80 % event-limit alert is the actionable one because at 100 % Tines stops the story.

## 9. A worked month (illustrative)

Every number below is a **placeholder to show the arithmetic**. Credits per run are read from `meta.credits_used` on your own events; replace the assumptions with a week of your tenant's `GET /api/v1/ai_usage` before quoting any figure.

**Assumptions:** 40 published production stories · sweep every 15 minutes (96 runs/day) plus the 06:00 daily branch · an average of 3 anomalous stories/day reach `triage` · `triage` ≈ 2 credits/run (capped by `agent_credits_per_run_max: 3`) · `critic` runs for about 1 high/critical finding/day at ≈ 0.5 credit (fast model, no tools) · 12 stories built or changed through Mode 2 · 15 PRs · 20 test events against AI Agent actions in dev at ≈ 1 credit each · 30 days.

| Line | Arithmetic | Tines credits | Other cost |
|---|---|---|---|
| Router (`ops-error-router`) | deterministic | 0 | 1 flow |
| Sweep, deterministic path | 96 × 30 = 2,880 runs; 0 credits each | 0 | API calls; 1 flow |
| `triage` | 3 runs/day × 2 credits × 30 | **180** | — |
| `critic` | 1 run/day × 0.5 credit × 30 | **15** | — |
| Mode 4 ops server | no model | 0 | 1 flow |
| Five read sub-stories + apply sub-story | no model | 0 | ≈ 6 flows (VERIFY, item 13) |
| Builds via the Tines Stories MCP server | 12 stories | **0** listed (helpers VERIFY, item 11) | Editor plan |
| CI review + proposals | 15 PRs × ≤ 10 turns; a few proposal runs × ≤ 15 turns | 0 | Anthropic API key — measure |
| Dev test events on AI Agent actions | 20 × 1 | **20** (dev team) | — |
| **Ops team total** | | **≈ 195** of `ops: 300` (65 %) — below the 80 % alert | |
| **Dev team total** | | **≈ 20** of `dev: 500` | |
| Rough money | 215 credits × $0.01 | ≈ **$2.15** in credits | plus the editor plan and the CI API spend |

**What would blow the same month:**

| Failure | Arithmetic | Credits |
|---|---|---|
| No deterministic pre-filter — `triage` runs every sweep | 96 × 2 × 30 | **5,760** (≈ 19× the ops ceiling) |
| A tool added to `critic` | it moves to the smart model; every high/critical costs like `triage` | + ~45 |
| The sweep's daily run cap removed and a noisy tenant | 96 × 3 (the per-run cap) × 30 | up to **8,640** |
| A Chat-mode agent left running with tools | per-message credits with no run cap | unbounded until the token alert's Disable action fires |
| A custom provider set as tenant default | credits read as **0** | the external bill grows unseen — `billed_cost` is the only signal |
| Workbench for Storyboard used for the 12 builds instead of Mode 2 | smart-model credits per build — amount unpublished | non-zero; from unallocated credits |

This is the whole argument for the pre-filter, the run cap, the token alerts and the ledger: the healthy month costs about the price of a coffee in credits, and each control removes one way for it to become the price of a laptop.

## 10. What to measure, from day one

- `credits_used` per story per day (`GET /api/v1/ai_usage?relative_date=today&group_by=story`) → `ops_credit_ledger`.
- **Credits per completed finding** (from `ops_findings.credits_used` ÷ findings with `outcome` set) — the ROI figure that survives a skeptic.
- Approvals requested that a person rejected (`ops_alert_proposals.status = rejected`) — the agent's precision.
- `billed_cost` alongside `credits_used` so a custom provider never hides.
- CI minutes and API spend for `review.yml` over the first five PRs.

## Verify in your tenant before presenting

Before quoting a cost: (1) confirm whether `/mcp` helpers consume credits — `GET /api/v1/ai_usage?group_by=feature` after an editor session (item 11); (2) read the credit-alert defaults and the per-team allocation page in Admin → AI (item 10); (3) settle sub-story flow counting with the account team (item 13); (4) replace every number in §9 with a week of your own `ai_usage` rows. Never quote plan-gated limits (dedicated-tenant concurrency, Enterprise custom roles) without the tenant's plan mapping.
