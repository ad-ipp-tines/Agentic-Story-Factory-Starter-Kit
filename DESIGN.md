# Tines Stories as Code — the scaffold design (DESIGN.md)

_Context: the stories-as-code layer of the Agentic Story Factory Starter Kit (`REPO-DESIGN.md`) · Created 2026-09-24._

**What this is:** the single design for a repository that lets a builder create, review, ship, monitor and roll back Tines Stories from an editor (Cursor or Claude Code) the way a software team ships code. It merges two earlier designs — one written developer-experience-first, one governance-first — into one. Where they disagreed, the resolution is stated in §2.3 and nowhere else is the losing option carried forward.

**What this is not:** product documentation (that is Tines' own documentation), or a claim that any unverified behaviour exists. Everything the scaffold designs *around* rather than *on* is marked **VERIFY** in place and collected in §10.

**Builders named in this spec:** `root` (repo front matter, conventions, policies, editor config) · `ide-skills` (everything under `.claude/` and `.cursor/`) · `agent-skills` (`tines-skills/`) · `stories` (`stories/`) · `ci` (`.github/`, `scripts/`, `terraform/`) · `docs` (`docs/`). Each file in §3 names exactly one builder.

**Facts come from:** the Tines API/platform sweep of 2026-09-24, the IDE-format sweep of the same date (Claude Code, Cursor, the Agent Skills specification), and public MCP research current to 2026-09-17. Only endpoints, fields, frontmatter keys and UI labels that appear in that research are used. If a builder needs something outside it, the builder adds a VERIFY marker and an entry in `docs/VERIFY.md` rather than inventing it.

---

## Table of contents

1. Purpose and thesis
2. The directory tree (final) — with the conflict resolutions
3. File-by-file spec
4. Workflows (build · review and ship · push skills · monitor and alert · roll back)
5. The agentic monitoring story
6. Cost controls
7. Security controls
8. Pros and cons
9. Conventions every builder must follow
10. VERIFY list

---

## 1. Purpose and thesis

### 1.1 Purpose

Give a Tines builder the same loop a software engineer has: **change → diff → independent review → gate → deploy → observe → roll back**, with Tines Stories as the artifact. Concretely:

- **Author from the editor.** A builder in Cursor or Claude Code talks to the **Tines Stories MCP server** (Mode 2, `https://<your-tenant>.tines.com/mcp`, OAuth only) to read, create, change and validate one story at a time in a dedicated dev team. The editor's own model does the reasoning; the repo's skills carry the procedure.
- **Stories are JSON in git.** Every story is exported (`GET /api/v1/stories/{id}/export`) into `stories/<slug>/story.json`, normalised so diffs are stable, and reviewed like code by an instance that did not write it.
- **Production is never edited directly.** The only path into production is an import into a change-control **draft** (`POST /api/v1/stories/import` with `mode: versionReplace` and `draft_name`), a **change request** (`POST /api/v1/stories/{id}/change_request`), and a **named person approving in Tines**. The pipeline never sets `bypass_approval`.
- **Tines Agent Skills are code too.** The `SKILL.md` files that shape the tenant's AI Agent actions and Workbench presets live in the same repo and are pushed with the Skills API (`POST`/`PUT /api/v1/skills`), so "how we build" and "how our agents behave" are reviewed in one PR.
- **One agentic ops pair watches the tenant.** A router story receives every monitoring notification; a scheduled sweep story reads live activity, error logs, runs and AI usage, and — only for anomalies — hands the evidence to an AI Agent action (Mode 3, Task mode, read-only tools, output schema) that *proposes*: a missing monitoring recipient, an alert threshold derived from baseline data, a Case or ticket, a Slack post, or a PR with a fix. **Humans approve anything that changes production.**
- **Cost and security are properties of the design,** not hopes: budgets are files, agents carry token alerts and tool caps, keys are team-scoped and role-bound, `/mcp` is OAuth and audit-logged, hooks enforce what prose only requests.

### 1.2 The thesis: the value is the system around the prompt

Anyone can prompt an AI to "build me a phishing triage story". That prompt is the cheapest part. What makes the result **fast, controlled and safe** is everything the prompt sits inside:

| Around the prompt | What it gives you | Where it lives in this repo |
|---|---|---|
| A procedure the model follows every time (explore → plan → implement → validate → export → review) | Speed without re-deriving the craft | `.claude/skills/tines-build-story/` |
| A conventions file both editors load | Stories that look alike across builders | `AGENTS.md` (+ `CLAUDE.md` importing it) |
| A stable JSON export in git | A diff on every change, a rollback point for free | `stories/**/story.json`, `scripts/normalize.jq` |
| Deterministic lint | The rules a security team can read without reading prose | `scripts/lint-story.sh`, `policies/lint-rules.yml` |
| A reviewer that is not the author | The generator never approves its own work | `.claude/agents/tines-reviewer.md`, `review.yml` |
| Hooks | Enforcement, not advice (an instruction is a request; a hook is a rule) | `.claude/hooks/*` |
| Change control with "Require approval for all changes" | A deterministic gate no prompt can argue past | `ship.yml`, `docs/02-change-control-path.md` |
| The ops pair | Observability that proposes, with evidence, and never acts alone | `stories/ops-error-router/`, `stories/ops-story-health-monitor/` |
| Budgets as files, token alerts, tool caps | A cost ceiling that fires before the platform does | `policies/cost-ceilings.yml`, per-agent Status-tab alerts |
| Team-scoped keys, OAuth, allow-listed credentials | Least privilege by construction | `.env.example`, GitHub environment secrets, Tines credentials |

This is the "new way of building": not *prompting harder*, but **prompting inside a system** that makes every output diffable, reviewable, gated, observable and reversible. The prompt is still there — the prompt-pack literally ships with the repo — but the repo is what a security reviewer signs off on.

### 1.3 The four modes (the only words we use for the MCP surfaces)

| Mode | Surface | This repo uses it for |
|---|---|---|
| Mode 1 | Workbench calling MCP tools (Workbench → MCP tab → New MCP connection) | The tenant-side skills are enabled on presets; not otherwise required |
| **Mode 2** | **The Tines Stories MCP server** at `https://<your-tenant>.tines.com/mcp` (OAuth only) | **Authoring from the editor** — every build |
| **Mode 3** | **The AI Agent action** calling tools | **The monitoring agent** (tools are Tines tools — Send to Story sub-stories — with at most one MCP connection, see §5) |
| **Mode 4** | **The MCP server action** at `https://<your-tenant>.tines.com/mcp/<mcp-path>` | **Exposing tools** — the ops read-only lookups and request tools, so the builder's editor and the on-call person can ask what the agent asks |

Only the word "mode" is used for these surfaces; the older intake-surface metaphor is retired (see §9).

---

## 2. The directory tree (final)

### 2.1 Design stance of the merge

- **Keep the developer speed of Design A:** one small conventions file, one skills tree shared by both IDEs, one API dispatcher script, a prompt pack, `mcp__tines__*` pre-approved in dev so the build loop never stalls on prompts, a worked example the builder copies, and a one-afternoon path from idea to change request.
- **Keep the controls of Design B:** a `policies/` folder a security reviewer can read and diff (never-touch list, cost ceilings, lint rules, break-glass log, the governance contract), four hooks (MCP guard with an input-based production check, secret block, lint-on-write, stop gate), CODEOWNERS, a `promote` job that only ever promotes an *already approved* change request, a separate break-glass job with two reviewers and a mandatory log line, per-environment team-scoped keys, and an agent that holds no write credential.
- **Add what the task requires and neither design fully had:** an explicit **Mode 4** story that exposes the ops lookups as tools, so all three modes named in the brief are exercised (Mode 2 authoring, Mode 3 the monitor, Mode 4 exposing tools).

### 2.2 The tree (exact paths)

```
tines-stories-as-code/
├── README.md                              # front page: the afternoon, the four modes, the verify block
├── AGENTS.md                              # THE conventions file (< 200 lines); Cursor reads it natively
├── CLAUDE.md                              # "@AGENTS.md" + Claude Code-only notes
├── CLAUDE.local.md.example                # personal, gitignored notes template (never keys)
├── .env.example                           # variable NAMES only
├── .gitignore
├── .mcp.json.example                      # /mcp entry shape (Claude Code); the live entry is USER scope
├── .claude/
│   ├── settings.json                      # committed permissions (deny > ask > allow) + the four hooks
│   ├── rules/
│   │   ├── story-json.md                  # paths: stories/**/story.json — generated artifact rules
│   │   └── tines-skills.md                # paths: tines-skills/** — Agent Skills frontmatter rules
│   ├── hooks/
│   │   ├── guard-mcp.sh                   # PreToolUse mcp__tines__.* — audit mirror, prod-ID block, destructive-name block (VERIFY), prod-env refusal
│   │   ├── block-secrets.sh               # PreToolUse Write|Edit — exit 2 on secret patterns
│   │   ├── lint-on-write.sh               # PostToolUse Write|Edit — lint stories/**/story.json (blocking) and tines-skills/**/SKILL.md (advisory)
│   │   └── stop-gate.sh                   # Stop — refuse to end a turn with failing lint or a stale export
│   ├── agents/
│   │   ├── tines-builder.md               # the ONLY context that holds the /mcp server
│   │   └── tines-reviewer.md              # fresh context, no MCP, read-only tools
│   └── skills/                            # ONE tree serves Claude Code and Cursor (Cursor reads legacy .claude/skills/)
│       ├── tines-connect/SKILL.md
│       ├── tines-build-story/
│       │   ├── SKILL.md
│       │   └── references/
│       │       ├── prompt-pack.md
│       │       └── story-conventions.md
│       ├── tines-export/SKILL.md
│       ├── tines-review/
│       │   ├── SKILL.md
│       │   └── references/findings-schema.json
│       ├── tines-ship/SKILL.md
│       ├── tines-rollback/SKILL.md
│       ├── tines-skills-push/SKILL.md
│       └── tines-propose-fix/SKILL.md     # headless-only; no MCP; edits stories/** on a branch
├── .cursor/
│   ├── mcp.json.example                   # same server, Cursor shape (url only) → goes to ~/.cursor/mcp.json
│   └── rules/
│       └── story-json.mdc                 # globs: stories/**/story.json
├── .github/
│   ├── CODEOWNERS
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       ├── lint.yml                       # deterministic gate: jq, lint-story, skills frontmatter, manifest, secret scan — no model, no network
│       ├── review.yml                     # independent Claude Code instance runs /tines-review — no MCP, no tenant
│       ├── ship.yml                       # merge to main → version tag → import as draft → recipients/monitor flags → change request. NEVER promotes
│       ├── promote.yml                    # workflow_dispatch: promotes ONLY a change request whose status is APPROVED; never bypass
│       ├── skills.yml                     # merge to main → upsert tines-skills/** via /api/v1/skills
│       ├── drift.yml                      # nightly: export prod, diff vs main, attribute via audit logs, open drift PR; plus a budget check
│       ├── rollback.yml                   # workflow_dispatch: git ref → draft → change request; separate break-glass job (two reviewers, logged)
│       └── propose-fix.yml                # repository_dispatch from the monitor → headless /tines-propose-fix → PR
├── policies/
│   ├── POLICY.md                          # the governance contract in prose (identities, gates, what never happens)
│   ├── cost-ceilings.yml                  # machine-readable budgets; mirrored into the ops_limits Resource
│   ├── never-touch.yml                    # production story ids / name patterns / teams no hook, skill or pipeline may write
│   ├── lint-rules.yml                     # the rule set lint-story.sh enforces, with severities
│   └── break-glass-log.md                 # append-only human log of every disable or bypass used in anger
├── scripts/
│   ├── tines                              # ONE bash+jq dispatcher over the Tines API (all subcommands in §3)
│   ├── normalize.jq                       # stable export: drop exported_at, sorted keys, agent order preserved
│   ├── lint-story.sh                      # deterministic checks over story.json + story.meta.yaml, driven by policies/lint-rules.yml
│   └── diff-story.sh                      # semantic diff (actions added/removed/changed, links, schedules, monitor flags) for PRs and change requests
├── stories/
│   ├── README.md                          # how a story folder is laid out; the lifecycle of story.json
│   ├── _manifest.yaml                     # environments (team_id, folder_id, secret names) + slug → story_id map; no secrets
│   ├── _template/
│   │   ├── README.md
│   │   ├── story.meta.yaml
│   │   └── tests/
│   │       ├── sample-event.json
│   │       └── expectations.yaml
│   ├── example-enrich-ip/                 # the worked example every builder copies (a Send to Story sub-story)
│   │   ├── README.md
│   │   ├── story.json
│   │   ├── story.meta.yaml
│   │   └── tests/{sample-event.json, expectations.yaml}
│   ├── ops-error-router/                  # Library 1231438 pattern: every production story's monitoring recipient
│   │   ├── README.md
│   │   ├── story.json
│   │   ├── story.meta.yaml
│   │   ├── samples/monitoring-payload.sample.json   # captured once by a deliberate LIVE failure (VERIFY shape)
│   │   └── tests/{sample-event.json, expectations.yaml}
│   ├── ops-story-health-monitor/          # the agentic sweep (Mode 3): health + credits → proposals → human approval
│   │   ├── README.md
│   │   ├── DESIGN.md                      # §5 of this document, kept in the repo so it is self-contained
│   │   ├── story.json
│   │   ├── story.meta.yaml
│   │   ├── agent/
│   │   │   ├── system-instructions.md
│   │   │   ├── output-schema.json
│   │   │   └── tools.md                   # the exact read-only tool set and descriptions
│   │   ├── resources/
│   │   │   ├── ops_limits.example.json
│   │   │   ├── ops_responders.example.json
│   │   │   └── ops_routing.example.json
│   │   ├── records/record-types.md
│   │   └── tests/{sample-event.json, expectations.yaml}
│   ├── ops-get-error-logs/ … ops-get-ai-usage/   # [OPS] 11–15: the five read sub-stories (README.md + story.meta.yaml until built)
│   ├── ops-apply-alert-rule/              # [OPS] 16: the only place tines_api_ops writes to production (README.md + story.meta.yaml until built)
│   ├── ops-request-approval/              # [OPS] 17: the approval request shared by the sweep and the Mode 4 server
│   └── ops-tools-server/                  # Mode 4: the ops lookups + request tools exposed to editors and Claude clients
│       ├── README.md
│       ├── story.json
│       └── story.meta.yaml
├── tines-skills/                          # Tines Agent Skills pushed to the tenant (AI Agent actions + Workbench presets)
│   ├── README.md
│   ├── _manifest.yaml                     # per-skill team scope and attachment targets (amended — §2.3 #12)
│   ├── story-health-triage/SKILL.md
│   ├── credit-budget-analyst/SKILL.md
│   ├── alert-policy/SKILL.md              # the monitoring policy as a skill (amended — §2.3 #12)
│   └── story-build-conventions/SKILL.md
├── terraform/                             # OPTIONAL alternative deploy path; not on the default pipeline
│   ├── README.md
│   ├── main.tf
│   └── stories.tf
└── docs/
    ├── 00-why-stories-as-code.md
    ├── 01-decision-rules.md
    ├── 02-change-control-path.md
    ├── 03-monitoring-story.md
    ├── 04-cost-controls.md
    ├── 05-security-controls.md
    ├── 06-pros-and-cons.md
    └── VERIFY.md
```

### 2.3 Conflicts between the two designs and how each is resolved

| # | Topic | Design A (speed) | Design B (controls) | **Resolution** |
|---|---|---|---|---|
| 1 | Environments | dev + prod | dev + staging + prod | **Two required: a dev team and a prod team.** `stories/_manifest.yaml` accepts any number of environments, so a `staging` entry is optional. Rationale: change-control drafts with test-mode credentials already give a staging surface inside prod; a third team costs flows and licences most tenants do not have. |
| 2 | Promotion | Human clicks in Tines; CI never calls promote | CI promotes only an APPROVED change request; never bypass | **Both, in order.** `ship.yml` opens the change request and stops. Default: the approver approves *and pushes* in Tines. Optional: `promote.yml` (workflow_dispatch, GitHub `production` environment) reads `GET …/change_request/view`, requires `status == APPROVED`, then calls promote with `delete_draft: true` and no bypass. A PENDING request is never promoted by any pipeline. |
| 3 | Skill names | `tines-connect`, `tines-build-story`, `tines-review`, `tines-ship`, `tines-rollback`, `tines-propose-fix` | `tines-story-build`, `-review`, `-export`, `-ship`, `tines-skill-push`, `tines-story-rollback`, `tines-monitor-triage` | **A's shorter names, plus B's two gaps:** `tines-export` (standalone export, also called by the build skill) and `tines-skills-push` (dry run). B's `tines-monitor-triage` is covered by `tines-propose-fix` (headless) plus a `/tines-build-story` prompt in the issue for the interactive case. |
| 4 | Scripts | one bash+jq dispatcher `scripts/tines` | twelve bash/python scripts | **One dispatcher** (`scripts/tines`) + `normalize.jq` + `lint-story.sh` + `diff-story.sh`. Rationale: skills, hooks and CI share one audited code path; permission rules are per subcommand prefix. **Deviation as built:** the dispatcher is a bash wrapper over Python scripts, so a Python runtime *is* needed — `python3` ≥ 3.9 and `python3 -m pip install -r scripts/requirements.txt` (`requests`; `PyYAML` for the manifest, meta and policy files); `lint-story.sh` and `diff-story.sh` are shims over `lint_story.py` and `diff_story.py` (`scripts/README.md`). B's `audit_attribution` and `ai_usage_report` become `tines audit` and `tines ai-usage` subcommands. |
| 5 | Policies folder | none (manifest + docs) | `policies/` with eight files | **Keep `policies/`** with five files: `POLICY.md`, `cost-ceilings.yml`, `never-touch.yml`, `lint-rules.yml`, `break-glass-log.md`. B's `team-map.yml` merges into `stories/_manifest.yaml` (one environment map); `change-control.md` and `credentials.md` become `docs/02` and `docs/05`. |
| 6 | Hooks | 2 (`guard-mcp`, `lint-on-write`) | 4 (`block-secrets`, `guard-prod-story`, `lint-on-write`, `stop-gate`) | **Four hooks.** `guard-mcp.sh` = A's audit mirror + destructive-name regex (VERIFY) + B's input-based production-ID check + A's `TINES_ENV=prod` refusal. `block-secrets.sh`, `lint-on-write.sh`, `stop-gate.sh` as in B. `lint-on-write` is **blocking (exit 2)** for `story.json` and advisory for `SKILL.md`. |
| 7 | MCP permission | `allow: mcp__tines__*` | `ask: mcp__tines__*` | **Allow in the IDE** — speed in dev — because the PreToolUse hook (exit 2) runs before allow rules and blocks production IDs, destructive-looking names and any call while `TINES_ENV=prod`. Deploy subcommands are `ask`; `cr-promote` is `deny` in the IDE. |
| 8 | Reviewer model | a named smaller model | `inherit` | **`model: inherit`** in the committed file with a comment that a smaller model is acceptable for review; model ids are chosen per tenant and never hard-coded in this spec. |
| 9 | Agent output schema | severity 4 levels, 9 categories, `proposed_change.kind`, typed `alert_rule_proposal` | severity 3 levels, 7 categories incl. `runtime_drift`, `lock_stale`, `mcp_health`; structured `proposed_alert_rule` | **Union** (§5.5): severity `low|medium|high|critical`; categories from both; `proposed_change.kind` from A; `alert_rule_proposal` typed as in A with B's structured fields. |
| 10 | Story slugs | `ops-error-router`, `ops-story-health-monitor` | `error-router`, `monitor-story-health` | **A's slugs** — the `ops-` prefix makes the never-touch rule obvious in every path. |
| 11 | Records | `ops_alerts`, `ops_findings`, `ops_alert_proposals`, `story_health_baseline`, `ops_dead_letter` | `monitor_findings`, `monitor_baselines`, `credit_ledger`, `seen_alerts`, `locks` | **Six types:** `ops_alerts` (also the dedupe store), `ops_findings`, `ops_alert_proposals`, `ops_baselines`, `ops_credit_ledger`, `ops_dead_letter`. The lock is a **Resource** (`ops_lock`, compare-and-swap), not a Record — Records have no documented atomic semantics. |
| 12 | Tenant-side skills | `story-health-triage`, `story-build-conventions` | `story-health-triage`, `credit-budget-analyst`, `change-request-writer` | **Four (amended; first drafted as three):** `story-health-triage`, `credit-budget-analyst` (both attached to the sweep's agent), `alert-policy` (which monitoring options, recipients and thresholds each story tier carries, and how each number is derived from baseline data; enabled on the Ops Workbench preset; attaching it to `triage` as a third skill is optional and recorded in `story.meta.yaml`), `story-build-conventions` (Workbench for Storyboard preset; whether presets honour skills there is VERIFY). `tines-skills/_manifest.yaml` records each skill's team scope and attachment targets. `change-request-writer` becomes a deterministic template inside `scripts/tines cr-open`. |
| 13 | Tenant-skills path | `tines-skills/` | `skills/tines/` | **`tines-skills/`** — visibly distinct from `.claude/skills/`. |
| 14 | Terraform | docs mention only | `terraform/` optional | **Optional `terraform/`**, three files, not wired to CI, README states the VERIFY on change-controlled stories and that the provider is 0.3.0 (2025-08-01). |
| 15 | Test files | `test-event.json` | `tests/{sample-event.json, expectations.yml}` | **B's shape**, `.yaml` extension (repo YAML is `.yaml`; GitHub workflows keep `.yml`). |
| 16 | Cursor rules | `story-json.mdc` only | + `tines-conventions.mdc` (alwaysApply) | **`story-json.mdc` only.** Cursor reads `AGENTS.md` natively, so an always-on rule would duplicate it. |
| 17 | Rules folder | none | `.claude/rules/{never-touch, story-json, tines-skills}.md` | **Two path-scoped rules** (`story-json.md`, `tines-skills.md`). Never-touch is summarised in `AGENTS.md` and machine-read from `policies/never-touch.yml`; an always-loaded rule file would duplicate `AGENTS.md`. |
| 18 | Prod story protection | `TINES_ENV=prod` refusal in the hook | production story IDs from meta + never-touch | **Both** in `guard-mcp.sh`. |
| 19 | Break-glass | `cr-promote --bypass-approval --reason` in the script, "audited" | separate GitHub environment `break-glass` with two reviewers + `policies/break-glass-log.md` | **B's shape.** The dispatcher accepts `--bypass-approval` only when `BREAK_GLASS=1` and `--reason` are set; only `rollback.yml`'s `break-glass` job sets them; it appends the log line in the same run; the IDE denies `cr-promote` outright. |
| 20 | Mode 4 | "not required" | mentioned only as a health signal | **Added:** `stories/ops-tools-server/` (see §3, §4.4, §5.9). |

---

## 3. File-by-file spec

Format per file: **Builder** · **Purpose** · **Key content**. Frontmatter keys, endpoints and flags are the ones in the research; anything else is marked VERIFY.

### 3.1 Root

#### `README.md`
**Builder:** root. **Purpose:** front page — the one-afternoon path, the repo map, the four modes in one table, the four proofs, and the mandatory "verify in your tenant before presenting" block.
**Key content:**
- Opening paragraph: Tines Stories are built from your editor through the Tines Stories MCP server (Mode 2, `https://<your-tenant>.tines.com/mcp`, OAuth only), exported as JSON, reviewed like code, and shipped into production only through change control. The value is the system around the prompt.
- **The afternoon (six steps):** (0) prerequisites — a dedicated Tines **team** per environment (never personal space: the AI Agent action is unavailable there and credentials must be shared), tenant change-control policies **Enable by default** and **Require approval for all changes** on, a **team-scoped** API key for the dev team in `.env`, `jq`, `yq` and `gh` installed; (1) `cp .env.example .env`, `source .env`, `/tines-connect`; (2) `/tines-build-story <slug> "<what to build>"`; (3) `/tines-review`, push, open the PR — `lint.yml` and `review.yml` run; (4) a human merges → `ship.yml` tags a version, imports the export into the prod story as a draft and opens a change request; (5) a named approver reads the live-vs-draft diff in Tines and approves (and pushes, or runs `promote.yml`); (6) the ops pair picks the story up: recipients from the manifest, `monitor_failures` on, a baseline captured on the next sweeps.
- **Four proofs** a security reviewer can check: least privilege (`policies/POLICY.md`), cost ceiling (`policies/cost-ceilings.yml`), auditability (commit SHA in every change-request description + a story version + audit logs), rollback (`rollback.yml`).
- Four-modes table (one line each, as §1.3).
- Repo map: `AGENTS.md` = rules · `.claude/skills/` = procedures · `scripts/tines` = the API · `stories/` = truth · `tines-skills/` = tenant-side skills · `policies/` = the contract · `.github/workflows/` = gates · `docs/` = why.
- **"Verify in your tenant before presenting"** block: `/mcp` tool names are unpublished; `/mcp` × change-control behaviour is unpublished; export key names for retry/monitor/output-schema options must be read from a real export first; import response fields; credit-alert defaults; flow counting for sub-stories used as tools; see `docs/VERIFY.md`. Nothing marked VERIFY is a headline claim.

#### `AGENTS.md`
**Builder:** root. **Purpose:** the single conventions file both IDEs load every session (Cursor reads it natively; Claude Code imports it from `CLAUDE.md`). Under 200 lines. Only what is always true; everything else is a skill.
**Key content (sections):**
1. *What this repo is* — `stories/**/story.json` exports are the truth; the tenant is a deployment target; the dev team is where builds happen.
2. *The four modes* — one line each (Mode 1 Workbench calling MCP tools · Mode 2 the Tines Stories MCP server at `/mcp` · Mode 3 the AI Agent action calling tools · Mode 4 the MCP server action at `/mcp/<mcp-path>`). This repo authors in Mode 2.
3. *Golden rules* — one story at a time; ask for a plan before any change bigger than a sentence; every build ends with **Validate** plus a test event; then export, lint, commit; never hand-edit `story.json` (links are index-based); never paste credential values, resource contents or tokens anywhere; never invent `/mcp` tool names — describe the server by its capabilities (reading and changing stories, creating and updating actions, validation, running actions where permitted, research and listing helpers, private template operations); production changes only through ship (import → draft → change request → human approval); guards live in the story (Triggers, Resources), not in prompts.
4. *Naming* — stories `[PREFIX] NN · Verb noun`; sub-stories end in `(sub)`; a sub-story finishes on a message-only Event Transform named `result` that emits 3–5 fields; failure branches return `{status, error_category, retryable, message}`; a Note on every canvas stating purpose and mode.
5. *HTTP Request hardening* — `retry_on_status` `[429, 500-599]`; retries 5–8 (not the default 25 ≈ 3 h 20 min); `emit_failure_event` **Always** (the default "Error response only" misses timeouts and DNS failures); `log_error_if` for 200-with-error bodies; failure path to the dead-letter Record; exclude expected non-2xx (the lock's 422, an empty lookup's 404) from `log_error_on_status`.
6. *Monitoring* — recipients = the ops router webhook + the email DL (from the manifest); story-level "Notify when any action fails" on; "notify if no events emitted" on every scheduled or ingress action at ≈ 2× its interval.
7. *AI Agent actions* — output schema always; one tool first, at most five; a Trigger after the agent on an explicit schema field, never on confidence or sentiment; token-usage alert on the Status tab (Notify, then Disable action at a higher threshold); the relevant `tines-skills/` skill attached; agents reason, stories fetch; every new agent needs a line in `policies/cost-ceilings.yml`.
8. *Credits* — know which provider each agent uses (a custom provider bypasses credits but still bills); write `meta.credits_used`, tokens and model to a Record per run.
9. *Ownership and never-touch* — which team owns which prefix; `policies/never-touch.yml` is the machine-read list (production story ids, `ops-*` stories without ops approval, the 90 Seeds folder, anything in another team).
10. *Skill map* — `/tines-connect` · `/tines-build-story` · `/tines-export` · `/tines-review` · `/tines-ship` · `/tines-rollback` · `/tines-skills-push`; `./scripts/tines` for everything the API does.
11. *Read next* — `docs/01-decision-rules.md` before choosing an agent or MCP for anything; `policies/POLICY.md` before shipping.

#### `CLAUDE.md`
**Builder:** root. **Purpose:** Claude Code entry point; imports `AGENTS.md` so there is one source of truth, then adds only what is Claude-specific.
**Key content:** `@AGENTS.md` on its own line, outside backticks (so it imports). Then four notes: (a) the `/mcp` entry lives in **user scope** — run `/tines-connect`; this repo commits no `.mcp.json` because `claude -p` connects repository servers without a trust prompt; (b) story edits are delegated to the `tines-builder` subagent (it holds the server so dozens of authoring tool descriptions never enter the main conversation); review is delegated to `tines-reviewer`, never the same context that built; (c) hooks are enforcement, this file is advice — `guard-mcp.sh` mirrors every Tines MCP call to `.tines/mcp-activity.jsonl` and blocks production ids and destructive-looking names; `block-secrets.sh` refuses secret-looking writes; `lint-on-write.sh` fails a turn that leaves a `story.json` unlintable; `stop-gate.sh` will not let a turn end with a failing lint or a stale export; (d) anything headless uses `--bare` or `--setting-sources user` and never expects `/mcp` to be available (OAuth only).

#### `CLAUDE.local.md.example`
**Builder:** root. **Purpose:** template for the builder's personal, gitignored notes. **Key content:** `TINES_TENANT=<your-tenant>` (host prefix), `MY_DEV_TEAM_ID=`, a scratch-story list. Never keys.

#### `.env.example`
**Builder:** root. **Purpose:** names every variable the scripts expect; never holds values.
**Key content:**
```
TINES_TENANT=<your-tenant>      # host prefix only
TINES_API_KEY=                  # TEAM-scoped key (Editor role) for the dev team; never a personal key
TINES_TEAM_ID=                  # dev team id
TINES_ENV=dev                   # dev | prod ; scripts refuse prod outside CI unless TINES_ALLOW_PROD=1
OPS_ROUTER_URL=                 # the ops-error-router webhook URL (carries a secret → env only, never the manifest)
OPS_EMAIL_DL=                   # ops distribution list address
```

#### `.gitignore`
**Builder:** root. **Key content:** `.env`, `.env.*`, `.mcp.json`, `.cursor/mcp.json`, `.claude/settings.local.json`, `CLAUDE.local.md`, `.tines/` (local mcp-activity log, export scratch, proposal files), `*.export.tmp.json`, `terraform/*.tfstate*`, `.terraform/`.

#### `.mcp.json.example`
**Builder:** root. **Purpose:** the Claude Code shape of the `/mcp` entry, for reference; the live entry is added at user scope by `/tines-connect` and never committed.
**Key content:**
```json
{ "mcpServers": { "tines": { "type": "http", "url": "https://${TINES_TENANT}.tines.com/mcp" } } }
```
Comment (in `README.md`, not in the JSON — settings files are strict JSON): no `headers` — authentication is OAuth only; an API key will not work. Prefer the copy-ready snippet shown at `https://<your-tenant>.tines.com/mcp` (login required).

### 3.2 Policies (`policies/`)

#### `policies/POLICY.md`
**Builder:** root. **Purpose:** the governance contract a security reviewer reads first: who may do what, where, with which identity.
**Key content:** *Identities* — **builder** (own Tines user through the OAuth-only `/mcp`; inherits own permissions, nothing more); **CI-prod** (team-scoped key in the prod team: can import, tag versions, set recipients and monitor flags, open change requests, promote an APPROVED request; cannot approve); **CI-read** (Viewer-role team key for `drift.yml` and the monitor's read sub-stories — effectively read-only by role, VERIFY); **monitor-apply** (Editor-role team key used only inside the apply sub-story, behind a verified approval); **approver** (a person, in Tines, never a key in CI). *Rules* — change control on every story; "Require approval for all changes" at tenant level (admins and owners included); no bypass outside the break-glass job; every promoted change carries the commit SHA in the change-request description and a story version; nightly drift check; audit logs exported to S3 every 15 minutes and drained to the SIEM; MCP activity rows are part of every review.

#### `policies/cost-ceilings.yml`
**Builder:** root. **Purpose:** the single source of budgets; read by `drift.yml`'s budget job (`./scripts/tines ai-usage`) and mirrored by hand into the `ops_limits` Resource.
**Key content:**
```yaml
tenant: { monthly_credit_budget: 0, alert_pct: [80, 100] }     # mirror of Admin → AI; alerts are set by hand (no API)
teams:
  ops:     { monthly_credits: 300 }
  dev:     { monthly_credits: 500 }
agents:
  ops-story-health-monitor/triage: { daily_tokens_notify: 150000, daily_tokens_disable: 300000, credits_per_run_max: 3, runs_per_day_max: 96 }
  ops-story-health-monitor/critic: { daily_tokens_notify: 50000,  daily_tokens_disable: 100000 }
ci: { review_max_turns: 10, review_timeout_min: 15, propose_fix_max_turns: 15, headless_concurrency: 1 }
rules: { new_ai_agent_action_requires_budget_line: true }
```

#### `policies/never-touch.yml`
**Builder:** root. **Purpose:** write-protected story ids, name patterns, folders and teams consumed by `guard-mcp.sh` (all four), `set_monitoring.py`, `story_disable.py`, `propose-fix.yml` and the monitor's Conditions; `lint-story.sh` does not enforce it (`never_touch_targets` is not implemented).
**Key content:** `story_ids: []` (prod ids, filled after first ship), `name_patterns: ['^\[OPS\]']`, `folders: ['90 Seeds']`, `teams: [<prod team id>]`, `reason` per entry.

#### `policies/lint-rules.yml`
**Builder:** root. **Purpose:** the rule set `lint-story.sh` enforces, with severities, so the gates can be read without reading bash.
**Key content:** `naming` · `substory_result_et` · `http_retry_bounds` (retries ≤ 8, `retry_on_status` present) · `http_emit_failure_event_always` · `expected_status_excluded` · `agent_output_schema_required` · `agent_post_trigger_required` · `sts_timeout_required` · `no_inline_secret` · `note_required` · `monitoring_required_for_prod` (`monitor_failures` + recipients + watchdog on entry/scheduled actions) · `schedule_sanity` (≥ 1 min; none inside Groups) · `keep_events_min_days_prod: 30` · `tools_are_requests` (a tool name matching `block|delete|isolate|disable` must start with `request_`) · `ai_agent_budget_line_present`. Each rule carries `severity: error|warning` and, where the export key is unconfirmed, `key: VERIFY` so the first real export tunes it.

#### `policies/break-glass-log.md`
**Builder:** root. **Purpose:** append-only human log of every `POST /disable` or `bypass_approval` used in anger. **Key content:** table — date · story · who · reason · `change_request_id` · audit-log ids · follow-up PR. `rollback.yml`'s break-glass job appends a line in the same run.

### 3.3 Claude Code and Cursor configuration (`.claude/`, `.cursor/`)

**`allowed-tools` format (amended):** the skill specs below write `allowed-tools` space-delimited, the Agent Skills form. The committed `.claude/skills/*/SKILL.md` files use the comma-separated form (`Bash(claude mcp *), Bash(jq *), Read`), which is the Claude Code form in use in this repository. Whether Cursor parses the comma form when it reads this tree is VERIFY #4; `lint.yml`'s `skills-ref validate` over `.claude/skills/*` is advisory.

#### `.claude/settings.json`
**Builder:** ide-skills. **Purpose:** committed permissions and hooks. Strict JSON. Deny beats ask beats allow; committed allow rules apply after workspace trust; deny and ask apply immediately.
**Key content:**
```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "deny": [
      "Read(./.env)", "Read(./.env.*)", "Read(./.mcp.json)", "Read(./.cursor/mcp.json)",
      "Bash(rm -rf *)", "Bash(git push --force *)", "Bash(git push -f *)",
      "Bash(./scripts/tines cr-promote *)", "Bash(terraform apply *)"
    ],
    "ask": [
      "Bash(git push *)", "Bash(gh pr create *)", "Bash(curl *)",
      "Bash(./scripts/tines import-draft *)", "Bash(./scripts/tines cr-open *)",
      "Bash(./scripts/tines version-create *)", "Bash(./scripts/tines recipients-add *)",
      "Bash(./scripts/tines recipients-remove *)", "Bash(./scripts/tines story-update *)",
      "Bash(./scripts/tines action-update *)", "Bash(./scripts/tines story-disable *)",
      "Bash(./scripts/tines skills-push *)"
    ],
    "allow": [
      "Read", "Glob", "Grep", "Bash(jq *)", "Bash(yq *)",
      "Bash(./scripts/tines export *)", "Bash(./scripts/tines live-activity *)",
      "Bash(./scripts/tines action-logs *)", "Bash(./scripts/tines runs *)",
      "Bash(./scripts/tines ai-usage *)", "Bash(./scripts/tines cr-view *)",
      "Bash(./scripts/tines versions-list *)", "Bash(./scripts/tines audit *)",
      "Bash(./scripts/lint-story.sh *)", "Bash(./scripts/diff-story.sh *)",
      "Bash(git status *)", "Bash(git diff *)", "Bash(git log *)", "Bash(git show *)",
      "Bash(git add *)", "Bash(git commit *)", "Bash(git checkout -b *)",
      "mcp__tines__*"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "mcp__tines__.*", "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard-mcp.sh", "timeout": 10 } ] },
      { "matcher": "Write|Edit",      "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-secrets.sh", "timeout": 10 } ] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit",      "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/lint-on-write.sh", "timeout": 60 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop-gate.sh", "timeout": 60 } ] }
    ]
  }
}
```
Notes: `mcp__tines__*` is the only honest allow rule because tool names are unpublished; `mcp__` rules with parentheses are skipped in settings files, so the glob form is used. The PreToolUse hook runs before allow rules and an exit-2 block wins. No `defaultMode` (auto/bypass are ignored from project files). `tines` is the user-scope server name `/tines-connect` must use, otherwise the matcher and the allow rule miss.

#### `.claude/rules/story-json.md`
**Builder:** ide-skills. **Purpose:** path-scoped rule for exported story JSON. **Key content:** frontmatter `paths: ["stories/**/story.json"]`. Body: this file is an export, not hand-written; change the story through the Tines Stories MCP server with `/tines-build-story`, then `/tines-export`; never edit `guid`, `links`, `diagram_layout` or agent order by hand (links reference agents by index); recipients are cleared on export (`clear_recipients=true`) and set from the manifest on ship; credentials and resources are referenced by name only — if a value appears here, stop and report.

#### `.claude/rules/tines-skills.md`
**Builder:** ide-skills. **Purpose:** path-scoped rule for Tines Agent Skills. **Key content:** frontmatter `paths: ["tines-skills/**"]`. Body: `name` lowercase-hyphen ≤ 64 chars, equal to the folder, unique per team, no "anthropic"/"claude"; `description` ≤ 1024 chars, third person, says what *and* when (agents see only name and description); body under 500 lines / ~5,000 tokens; `metadata` is a flat string map and CI stamps `git_sha`; a rename is safe (the API rewrites references) but still needs a PR; never install a skill from an untrusted source.

#### `.claude/hooks/guard-mcp.sh`
**Builder:** ide-skills. **Purpose:** deterministic guard on every Tines MCP call: audit mirror, production refusal, input-based never-touch block (story, prod team and prod folder ids as numbers or digits-only strings; never-touch folder names; any string matching a never-touch name pattern — the ops owner builds `[OPS]` stories in dev with `TINES_ALLOW_OPS_BUILD=1`), destructive-name block; fails closed (exit 2) without `jq`, `yq` or either policy file. Designed around the fact that tool names are unpublished. The sketch below is the original shape; `.claude/hooks/guard-mcp.sh` is the full logic.
**Key content (logic):**
```bash
#!/usr/bin/env bash
set -euo pipefail
input=$(cat); tool=$(jq -r '.tool_name' <<<"$input")
mkdir -p "$CLAUDE_PROJECT_DIR/.tines"
jq -c --arg ts "$(date -u +%FT%TZ)" '{ts:$ts, tool:.tool_name, session:.session_id, input:(.tool_input|tostring|.[0:400])}' <<<"$input" \
  >> "$CLAUDE_PROJECT_DIR/.tines/mcp-activity.jsonl"
# 1 · production is changed only through ship
if [[ "${TINES_ENV:-dev}" == "prod" ]]; then echo "guard-mcp: TINES_ENV=prod — authoring via /mcp is dev-only; use /tines-ship" >&2; exit 2; fi
# 2 · input-based production-ID block (does not depend on tool names)
ids=$(jq -r '[.tool_input | .. | ((numbers | tostring), (strings | select(test("^[0-9]+$"))))] | unique | .[]' <<<"$input")
prot=$( { yq '(.story_ids // [])[]' policies/never-touch.yml; yq '(.teams // [])[]' policies/never-touch.yml
          yq '.stories[].prod.story_id, .environments.prod.team_id, .environments.prod.folder_id' stories/_manifest.yaml; } \
        | grep -E '^[0-9]+$' | grep -vx 0 | sort -u )
for id in $ids; do grep -qx "$id" <<<"$prot" && { echo "guard-mcp: id $id is write-protected; build in the dev team" >&2; exit 2; }; done
# + never-touch `folders` (exact) and `name_patterns` (regex) against every string in tool_input; exit 2 without jq, yq or the files
# 3 · destructive-looking names — VERIFY against the real tool list; replace with an explicit deny list once known
if [[ "$tool" =~ (delete|destroy|remove|purge|batch_delete) ]] && [[ "${TINES_ALLOW_DESTRUCTIVE:-}" != "1" ]]; then
  echo "guard-mcp: '$tool' looks destructive; re-run with TINES_ALLOW_DESTRUCTIVE=1 after confirming with the story owner" >&2; exit 2; fi
exit 0
```
Design note: exit 2 is used instead of the JSON `permissionDecision` field because the third decision value was reported inconsistently (`ask` vs `request`) — VERIFY before switching.

#### `.claude/hooks/block-secrets.sh`
**Builder:** ide-skills. **Purpose:** PreToolUse on `Write|Edit`: refuse any write whose content looks like a secret. **Key content:** read `tool_input.content // tool_input.new_string`; grep for `X-User-Token`, `Bearer [A-Za-z0-9._-]{16,}`, `xoxb-`, `xapp-`, `AKIA[0-9A-Z]{16}`, `sk-[A-Za-z0-9]{16,}`, `"value"\s*:\s*"` inside a `user_credentials`-shaped object, `api[_-]?key\s*[=:]\s*["'][^"']{8,}`; on match print the pattern name and `exit 2`.

#### `.claude/hooks/lint-on-write.sh`
**Builder:** ide-skills. **Purpose:** PostToolUse on `Write|Edit`: give the model a check it can run. **Key content:** if `tool_input.file_path` matches `stories/**/story.json` → `./scripts/lint-story.sh <file>`; failure prints the findings to stderr and `exit 2` (blocking). If it matches `tines-skills/**/SKILL.md` → `npx skills-ref validate <dir>` (VERIFY availability); failure is returned as `additionalContext` on exit 0 (advisory) so the model fixes it in the same turn.

#### `.claude/hooks/stop-gate.sh`
**Builder:** ide-skills. **Purpose:** Stop hook: the turn cannot end while lint fails or an edited story has no fresh export. **Key content:** `git status --porcelain stories/` → for each changed `story.json` run lint; for each story whose slug appears in `.tines/mcp-activity.jsonl` this session (matched by story id in the logged input), require `story.meta.yaml: exported_from.at` newer than the last logged MCP call; on failure `exit 2` with the exact list ("run /tines-export <slug>"). Claude Code overrides after 8 consecutive blocks, so the message says precisely what to fix.

#### `.claude/agents/tines-builder.md`
**Builder:** ide-skills. **Purpose:** the only context that talks to `/mcp`; keeps the authoring tool descriptions out of the main conversation; carries the build skill.
**Key content:**
```yaml
---
name: tines-builder
description: Builds or changes exactly one Tines story through the Tines Stories MCP server, then validates, runs the test event and exports. Use for any task that says build, add an action, wire, fix, validate or export a story.
tools: Read, Glob, Grep, Bash
model: inherit
maxTurns: 40
skills: [tines-build-story, tines-export]
mcpServers: [tines]      # VERIFY exact form: name reference to the user-scope server vs an inline http definition
memory: project
---
```
Body: "You work on one story at a time in the dev team. Read the story first (you can see actions, configurations, formulas, connections, recent execution logs and referenced credential and resource names — never values, never other stories, never data in flight). Propose a plan before any change bigger than a sentence. Name the story, the action type and the field names in every step. End with Validate and a test event. Then `/tines-export <slug>`. Never create credential values, never import Library stories through `/mcp` (it cannot), never touch anything in `policies/never-touch.yml`. If a correction fails twice, stop and report instead of retrying."

#### `.claude/agents/tines-reviewer.md`
**Builder:** ide-skills. **Purpose:** fresh-context reviewer with no MCP and read-only tools. The generator never reviews its own work.
**Key content:**
```yaml
---
name: tines-reviewer
description: Reviews a story JSON diff and story.meta.yaml against AGENTS.md conventions in a fresh context and returns machine-parseable findings. Use after a build, before a PR, or when asked to review a story.
tools: Read, Grep, Glob, Bash(jq *), Bash(git diff *), Bash(./scripts/lint-story.sh *), Bash(./scripts/diff-story.sh *)
disallowedTools: Write, Edit
model: inherit          # a smaller model is acceptable for review; choose per tenant
maxTurns: 15
skills: [tines-review]
---
```
Body: "You have no access to the tenant. Judge only the diff, the export and the meta file. Output findings in `references/findings-schema.json`. Never approve a story that references a credential or resource not listed in `story.meta.yaml`, contains a string that looks like a token, has an AI Agent action without an output schema, has an HTTP Request action without hardening, or has no monitoring configuration in meta for `tier: production`."

#### `.claude/skills/tines-connect/SKILL.md`
**Builder:** ide-skills. **Purpose:** step 0 — connect the editor to `/mcp` in user scope and prove it works.
**Key content:** frontmatter `name: tines-connect`, `description: Connects this editor to the Tines Stories MCP server in user scope, completes the OAuth consent and runs a smoke prompt. Use on first setup, after an 'unauthorized' or empty-tool-list error, or when switching tenants.`, `disable-model-invocation: true`, `allowed-tools: Bash(claude mcp *) Bash(jq *) Read`. Steps: (1) read `TINES_TENANT` from the environment (ask the person to `source .env`; the skill never reads `.env`); (2) Claude Code: `claude mcp add --transport http tines --scope user https://$TINES_TENANT.tines.com/mcp`, then `/mcp` in-session (or `claude mcp login tines`) to complete the consent screen titled **Tines Stories MCP server** — setup inferred, VERIFY; prefer the copy-ready snippet at `https://<your-tenant>.tines.com/mcp`. Cursor: Settings → Customize → MCP → New MCP Server → paste `.cursor/mcp.json.example` into `~/.cursor/mcp.json` (global, not the project file); saving triggers OAuth; (3) smoke prompt: "Using the Tines MCP server, list the teams I can see and the stories in each" — an auth error means redo OAuth; a missing team means your Tines user is not a member (the server grants nothing you lack); (4) record the tool names the client shows in `docs/VERIFY.md` (the count is in the dozens — an observation, not a published number) so `guard-mcp.sh` can move from a regex to an explicit deny list; (5) remind: an API key will not work here; production authoring is blocked by the hook.

#### `.claude/skills/tines-build-story/SKILL.md`
**Builder:** ide-skills. **Purpose:** the core procedure — "build me X" → validated, exported, linted, committed story in the dev team.
**Key content:** frontmatter `name: tines-build-story`, `description: Builds or changes one Tines story through the Tines Stories MCP server using the explore-plan-implement-validate-export loop, then lints and commits the export. Use when the user wants to create, extend or fix a story, or says build, add an action, wire, validate or export.`, `argument-hint: <story-slug> "<what to build>"`, `allowed-tools: Bash(./scripts/tines export *) Bash(./scripts/lint-story.sh *) Bash(jq *) Bash(yq *) Bash(git checkout -b *) Bash(git add *) Bash(git commit *)`. Inputs `$0` = slug, `$1` = the ask. Preconditions: `TINES_ENV=dev`; the slug exists in `stories/_manifest.yaml` (or add it with `new: true`); credentials the story needs already exist in the dev team by name (check `story.meta.yaml`). **Loop:** 1 *Explore* — through the Tines MCP server read the story named in the manifest (or create it in the dev team, folder from the manifest); report actions, connections, recent logs, referenced credential and resource names. 2 *Plan* — anything bigger than a sentence becomes a numbered list of actions with type, name and field names; wait for a yes. 3 *Implement* — one prompt per action from `references/prompt-pack.md`; every prompt names the story, the action type and the fields; `DEFAULT()` so a missing field never breaks a formula; add the failure path and retry settings from `references/story-conventions.md` as you go. 4 *Validate* — end with "Validate"; fix what it reports; after two failed corrections on one issue stop and ask. 5 *Test* — send `tests/sample-event.json` to the entry action (draft webhooks accept `?draft=<name>` when change control is on); read the events; compare with `tests/expectations.yaml`. 6 *By hand* (the skill says so explicitly — these cannot be done through `/mcp`): enable Send to Story access for the team if it is a sub-story; raise event retention above 7 days; turn change control on if the story is new; create Record types; set the AI Agent token alert on the Status tab. 7 *Export* — `/tines-export <slug>`; update `story.meta.yaml` (credentials, resources, agents, monitoring, budget ref). 8 *Commit* — branch `story/<slug>/<short>`, message `story(<slug>): <what changed>`; hand off with "Run `/tines-review` from a fresh session before opening the PR." **Never:** hand-edit `story.json`; paste values; name `/mcp` tools; work in prod; touch more than one story per branch.

#### `.claude/skills/tines-build-story/references/prompt-pack.md`
**Builder:** ide-skills. **Purpose:** literal prompts that work against `/mcp`, one per action, in build order. **Key content:** shape of every prompt = story name + action type + action name + field names + "then validate". P1 create (`In the Tines team <team>, create a new story named "[<PREFIX>] <NN> · <Verb noun> (sub)". Add a Send to Story entry action that expects a payload with the fields <a>, <b>. Then add an Event Transform in message-only mode named normalize that outputs {a: DEFAULT(<path>.a, ""), …}`) · P2 integrate (the `<vendor>` template using the credential named `<credential_name>` from this team) · P3 verdict (`DEFAULT()` fallbacks) · P4 branch (a Trigger named `is_<condition>` on an explicit field; a Slack send-message template on the matching path) · P5 finish (a final Event Transform named `result` emitting exactly `{verdict, score, sources, summary}`; an `error` Event Transform on the failure path emitting `{status: "error", error_category, retryable, message}`; then validate) · P6 hardening (on every HTTP Request action set `retry_on_status` `[429, 500-599]`, retries 6, `emit_failure_event` Always, connect the failure path to `error`) · P7 note (a Note explaining purpose, inputs, outputs and mode) · P8 export is the script, not the editor. Correction habits: wrong reference → "the payload arrives at the Send to Story action's body; fix the reference"; "credential not found" → wrong team or different name, fix by hand once; two failures on one issue → clear and restart with a better prompt.

#### `.claude/skills/tines-build-story/references/story-conventions.md`
**Builder:** ide-skills. **Purpose:** the long-form conventions the skill points at (kept out of `AGENTS.md` to save resident tokens). **Key content:** sub-story tool contract (result ET with 3–5 fields; structured error shape; the description documents the output because tool responses carry no output schema) · HTTP hardening table · watchdog rule (no-events X ≈ 2× schedule) · overlap guard (compare-and-swap lock via `POST /api/v1/global_resources/<id>/replace` with `key=lock`, `value=STORY_RUN_GUID()`, `if_value=free`; 422 = already running, excluded from errors and branched on in a Trigger; release with `if_value` = the run's GUID on the last action and every failure branch; a lock older than N minutes is treated as free) · safe-disable order (schedule or entry action first, then the story) · AI Agent action rules · naming and Note rules · size limits that bite (event 100 MB, HTTP 30 MB, Loops 5 minutes, 30,000 events per branch, queues drop above 20,000).

#### `.claude/skills/tines-export/SKILL.md`
**Builder:** ide-skills. **Purpose:** export one story to the repo, normalise, lint, stamp meta, show the semantic diff. **Key content:** frontmatter `name: tines-export`, `description: Exports one Tines story's JSON from the dev team into stories/<slug>/story.json, normalises it, lints it and stamps story.meta.yaml. Use after every build and before every commit.`, `disable-model-invocation: true`, `argument-hint: <story-slug> [--draft <id>]`, `allowed-tools: Bash(./scripts/tines export *) Bash(./scripts/lint-story.sh *) Bash(./scripts/diff-story.sh *) Bash(yq *)`. Steps: `./scripts/tines export <slug> [--draft <id>]` (`GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true[&draft_id=]` → `normalize.jq`) → `./scripts/lint-story.sh stories/<slug>/story.json` → `yq -i '.exported_from = {env, story_id, draft_id, at, sha}' stories/<slug>/story.meta.yaml` → `./scripts/diff-story.sh stories/<slug>/story.json` against `HEAD` and print it.

#### `.claude/skills/tines-review/SKILL.md`
**Builder:** ide-skills. **Purpose:** fresh-context review producing machine-parseable findings; used locally and by `review.yml`. **Key content:** frontmatter `name: tines-review`, `description: Reviews the changed story JSON exports and meta files against AGENTS.md conventions in a fresh context and returns findings as JSON. Use before opening a PR, in CI, or when asked to review a story change.`, `context: fork`, `agent: tines-reviewer`, `argument-hint: [pr-number | branch]`, `allowed-tools: Read Grep Glob Bash(jq *) Bash(git diff *) Bash(./scripts/lint-story.sh *) Bash(./scripts/diff-story.sh *)`. Procedure: `git diff --name-only origin/main...HEAD -- stories tines-skills` → per story: lint; read `story.json` + `story.meta.yaml`; check (a) naming and `(sub)` suffix; (b) `result` ET on sub-stories and an error shape on the failure path; (c) every HTTP Request action carries `retry_on_status`, retries ≤ 8, `emit_failure_event` Always (key names VERIFY from a real export); (d) every AI Agent action (`Agents::LLMAgent` in exports — VERIFY) has an output schema, a Trigger after it, a `tines-skills/` attachment noted, a budget line in `policies/cost-ceilings.yml` and a token alert noted in meta; (e) no options value matches token/secret/`xox[bp]-`/`Bearer `/`sk-` patterns or an email address; (f) credentials and resources referenced by name are listed in meta; (g) `meta.tier: production` ⇒ `monitoring.monitor_failures: true` and recipients `manifest`; (h) diff sanity — agent count change explained in the PR body, no links removed silently; (i) `tines-skills/*/SKILL.md` frontmatter valid. Output only the JSON in `references/findings-schema.json`, `verdict: pass | changes_requested`. Never self-review: if this session built the story, refuse and say so.

#### `.claude/skills/tines-review/references/findings-schema.json`
**Builder:** ide-skills. **Purpose:** the contract `review.yml` passes to `--json-schema`. **Key content:** `{verdict: pass|changes_requested, findings: [{path, rule, severity: blocker|major|minor|info, message, suggested_fix?, suggested_prompt?  // a /tines-build-story prompt that would fix it}], cost_notes?: string}`.

#### `.claude/skills/tines-ship/SKILL.md`
**Builder:** ide-skills. **Purpose:** local counterpart of `ship.yml` for teaching and for tenants without CI: import into the prod (or dev) story as a draft and open a change request. **Never promotes.** **Key content:** frontmatter `name: tines-ship`, `description: Imports a story's committed export into the target story as a change-control draft and opens a change request for a human approver. Use only after the PR is merged, or to rehearse the ship path against the dev team.`, `disable-model-invocation: true`, `argument-hint: <story-slug> [dev|prod]`, `allowed-tools: Bash(./scripts/tines *) Bash(jq *) Bash(git log *) Read`. Steps: (1) refuse unless the working tree is clean and HEAD is on `main` (or `--env dev`); (2) `./scripts/tines version-create <slug> --env <env> --name "pre-ship $(git rev-parse --short HEAD)"` — the rollback point (`POST /api/v1/stories/{id}/versions`); (3) `./scripts/tines import-draft <slug> --env <env> --draft-name "git-<sha>"` (`POST /api/v1/stories/import` with `data`, `team_id`, `folder_id`, `mode: versionReplace`, `draft_name`; matches the existing story by **name**, so names must be identical across environments; embedded sub-stories are not imported; the draft id comes from the response — field name VERIFY); (4) `./scripts/tines recipients-add … --draft <id>` for each manifest recipient and `./scripts/tines story-update <slug> --monitor-failures true --draft <id>` (`PUT /api/v1/stories/{id}` — on a change-controlled story this lands in the named draft, or in a draft called `test` if none is given); (5) `./scripts/tines cr-open <slug> --env <env> --draft <id> --title "<slug> <sha>" --description "<PR url + semantic diff>"` (`POST /api/v1/stories/{id}/change_request`); (6) `./scripts/tines cr-view` prints the live-vs-draft diff (`GET …/change_request/view?draft_id=`) for the approver; (7) print the change-request URL and stop. Promotion is a human act in Tines or `promote.yml` on an APPROVED request; `cr-promote` is denied in the IDE.

#### `.claude/skills/tines-rollback/SKILL.md`
**Builder:** ide-skills. **Purpose:** roll production back to any committed export through the same controlled path; prepare the PR that keeps `main` equal to what will be live. **Key content:** frontmatter `name: tines-rollback`, `description: Prepares a production rollback of a story to a previous committed export through a draft and change request, and the PR that keeps main truthful. Use when a shipped change misbehaves or the monitor proposes a rollback.`, `disable-model-invocation: true`, `argument-hint: <story-slug> <git-sha|previous>`, `allowed-tools: Bash(./scripts/tines versions-list *) Bash(./scripts/tines live-activity *) Bash(git log *) Bash(git show *) Bash(git revert *) Bash(git checkout -b *) Bash(jq *) Read`. Steps: (1) `git log --oneline -- stories/<slug>/story.json`, pick the sha; `./scripts/tines versions-list <slug> --env prod` for comparison (versions expose metadata only — no export-of-a-version endpoint was found, VERIFY — so the git ref is the source); (2) `git revert` the offending commit(s) on branch `rollback/<slug>/<sha>` and open the PR titled `ROLLBACK <slug> to <sha>` with the incident link; (3) say which workflow to run: `rollback.yml` with `slug`, `target=<sha>`, `reason`; emergency containment is the break-glass job, run by a human, never by this skill; (4) after approval and re-enable, add the incident to `stories/<slug>/README.md` and mark any monitor proposal `applied` in `ops_alert_proposals`. UI alternative: restore a story version from the version bar [BY HAND].

#### `.claude/skills/tines-skills-push/SKILL.md`
**Builder:** ide-skills. **Purpose:** preview what `skills.yml` will do for a Tines Agent Skill; push to the dev team for a live test. **Key content:** frontmatter `name: tines-skills-push`, `description: Validates tines-skills/<name>/SKILL.md and dry-runs the Skills API upsert against a team, showing create vs update. Use before opening a PR that adds or changes a tenant-side skill, or to push to the dev team for testing.`, `disable-model-invocation: true`, `argument-hint: <skill-name> [--dev]`, `allowed-tools: Bash(./scripts/tines skills-push *) Read`. Steps: `./scripts/tines skills-push --validate-only --only <name>` (the Agent Skills validator `skills-ref` only once its package is confirmed and pinned, then with `npx --no` — never `npx --yes`; VERIFY #21) → `./scripts/tines skills-push --team $TINES_TEAM_ID --dry-run --only <name>` → with `--dev`, the real push to the dev team → remind that production push happens only in `skills.yml` after merge and that attaching a skill to a preset or an agent is [BY HAND].

#### `.claude/skills/tines-propose-fix/SKILL.md`
**Builder:** ide-skills. **Purpose:** headless-only skill run by `propose-fix.yml`: turn the monitor agent's diagnosis into a lint-clean PR against the export, with no tenant access. **Key content:** frontmatter `name: tines-propose-fix`, `description: Applies a monitor-story fix proposal to the committed story export on a branch, lints it and opens a labelled PR. Runs headless only; no MCP; never touches the tenant.`, `disable-model-invocation: true`, `argument-hint: <proposal.json path>`, `allowed-tools: Read Grep Glob Edit(stories/**) Bash(jq *) Bash(./scripts/lint-story.sh *) Bash(./scripts/diff-story.sh *) Bash(git checkout -b *) Bash(git add *) Bash(git commit *)`. Body: read the proposal (the agent's schema output). Only kinds on the allow-list are applied automatically: add `retry_on_status`/`emit_failure_event` to a named HTTP Request action; change a schedule; adjust a `DEFAULT()` fallback. Anything else → the PR body carries the diagnosis, the evidence and a ready-to-run `/tines-build-story` prompt, and no JSON is edited. Never reorder agents or change links (index-based). Run lint; if it fails, revert and open the PR as diagnosis-only. Branch `ops/proposal-<id>`, label `ops-proposal`, body includes `evidence[]`, `confidence` and "requires human approval in Tines after merge".

#### `.cursor/mcp.json.example`
**Builder:** ide-skills. **Purpose:** Cursor shape of the same `/mcp` entry, for `~/.cursor/mcp.json` (global) so it never lands in the repo. **Key content:** `{ "mcpServers": { "tines": { "url": "https://<your-tenant>.tines.com/mcp" } } }` — no `headers` (OAuth only); no `type` key is documented for Cursor (VERIFY whether one is accepted); saving triggers the OAuth flow; prefer the copy-ready snippet from `https://<your-tenant>.tines.com/mcp`.

#### `.cursor/rules/story-json.mdc`
**Builder:** ide-skills. **Purpose:** path-scoped Cursor rule that stops hand edits of exports and points at the skills; Cursor reads `AGENTS.md` for the rest. **Key content:** frontmatter `description: Exported Tines story JSON files are generated artifacts`, `globs: stories/**/story.json`, `alwaysApply: false`. Body = the same five bullets as `.claude/rules/story-json.md`, plus: skills live in `.claude/skills/` (Cursor reads that tree as a legacy path — documented; if it stops, symlink `.cursor/skills → ../.claude/skills`); Cursor's IDE agent does not run this repo's Claude Code hooks, so enforcement in Cursor is CI and Tines change control.

### 3.4 CI (`.github/`)

#### `.github/CODEOWNERS`
**Builder:** ci. **Key content:** `/stories/** @<org>/tines-builders` · `/stories/ops-* @<org>/security-platform` · `/policies/** @<org>/security-platform` · `/.claude/** @<org>/security-platform` · `/.github/** @<org>/security-platform` · `/tines-skills/** @<org>/tines-builders @<org>/security-platform`. Placeholders; branch protection requires a CODEOWNERS review and forbids self-merge.

#### `.github/PULL_REQUEST_TEMPLATE.md`
**Builder:** ci. **Purpose:** makes the reviewer's and the approver's jobs explicit; doubles as the change-request description. **Key content:** sections — *Story and environment* · *What changed* (paste `./scripts/diff-story.sh` output) · *Why* · *Test event and observed events* (run guid, `action_count`, `event_count` from `GET /runs`) · *Cost impact* (new AI Agent action? tool count? schedule interval? budget line added?) · *Monitoring* (recipients, watchdog seconds) · *Risk and blast radius* · *Rollback ref* (previous sha) · *Approver in Tines* (a role, not a person). Checklist: built in the dev team with `/tines-build-story` (one story per PR) · validated and test event passed · exported with `clear_recipients` · lint passes · `story.meta.yaml` updated · credentials and resources exist in the prod team by the same names · `/tines-review` run from a fresh session, findings addressed.

#### `.github/workflows/lint.yml`
**Builder:** ci. **Purpose:** fast, deterministic gate on every PR. No model, no network, no secrets. **Key content:** `on: pull_request` (paths `stories/**`, `tines-skills/**`, `policies/**`, `.claude/skills/**`). Steps: `actions/checkout@v6` → `jq empty` on every `stories/*/story.json` → fail if any `story.json` contains `exported_at` (not normalised) → `./scripts/lint-story.sh` on changed exports only (driven by `policies/lint-rules.yml`; a committed file whose description starts with `SKELETON` is a labelled placeholder and is skipped) → `tines-skills/*/SKILL.md` frontmatter (name = directory, `^[a-z0-9]+(-[a-z0-9]+)*$`, ≤ 64 chars, description ≤ 1024, no "anthropic"/"claude"); the Agent Skills validator `skills-ref` is not run until its package is confirmed and pinned (never `npx --yes`; VERIFY #21) → manifest consistency (every `stories/<slug>` has an entry with `prod.story_id` or `new: true`; `story.json.name == meta.name`) → secret patterns (same list as `block-secrets.sh`, plus gitleaks — the image pinned by digest — with a custom rule for a Tines ingress `path`/`secret` in an export) → `meta.tier: production` ⇒ `monitor_failures` and recipients → every AI Agent action has a line in `policies/cost-ceilings.yml` → post the `diff-story.sh` summary as a PR comment.

#### `.github/workflows/review.yml`
**Builder:** ci. **Purpose:** an independent Claude Code instance reviews the change with the repo's own skill; findings become PR comments. No MCP, no tenant. **Key content:** same trigger and paths. `permissions: contents: read, pull-requests: write, issues: read, id-token: write`. `concurrency: review-${{ github.event.pull_request.number }}` (cancel-in-progress). `timeout-minutes: 15`. Steps: `actions/checkout@v6` (`fetch-depth: 0`) → `uses: anthropics/claude-code-action@v1` with `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}`, `prompt: "/tines-review ${{ github.event.pull_request.number }}"`, `claude_args: "--max-turns 10 --allowedTools Read,Glob,Grep,Bash(jq *),Bash(git diff *),Bash(./scripts/lint-story.sh *),Bash(./scripts/diff-story.sh *) --json-schema @.claude/skills/tines-review/references/findings-schema.json --output-format json"` (the `@file` form for `--json-schema` is VERIFY; inline the schema otherwise) → parse `structured_output`; post each finding as a review comment; fail the check on `changes_requested`. Secrets are not exposed to fork PRs; `allowed_bots` left empty so bots cannot trigger loops.

#### `.github/workflows/ship.yml`
**Builder:** ci. **Purpose:** the only path into production: version tag → import as draft → recipients and monitor flags on the draft → change request. **It never promotes.** **Key content:** `on: push` (`branches: [main]`, paths `stories/**`) and `workflow_dispatch` (inputs `slug`, `env`). Job `open-change-request`, `environment: production` (GitHub required reviewers = an optional second human gate before the tenant is touched). Env from environment secrets: `TINES_TENANT`, `TINES_API_KEY` (a prod **team-scoped** key, Editor role, never personal), `TINES_ENV=prod`, `TINES_ALLOW_PROD=1`. Steps: checkout (`fetch-depth: 2`) → changed slugs = `git diff --name-only HEAD~1 -- stories | cut -d/ -f2 | sort -u` (skip `_manifest.yaml`, `_template`) → per slug: `./scripts/tines version-create` → `./scripts/tines import-draft <slug> --env prod --draft-name git-${GITHUB_SHA::7}` → `recipients-add` for each manifest recipient and `story-update --monitor-failures true` on the draft → `cr-open --title "<slug> ${GITHUB_SHA::7}" --description "<commit url> + diff-story output"` → `cr-view` into the job summary → post the change-request URL as a commit comment and to the ops channel via `OPS_ROUTER_URL`. Fails if the import reports a missing credential or resource (names must pre-exist in the prod team). `sleep 1` between stories for rate limits. Prod runs from `main` only (the plan job fails any other ref, as `promote.yml` and `rollback.yml` do). A slug with `new: true` and no prod id is **refused in prod** — `mode: new` would create a live story with no draft and no change request; preferably a person creates an empty, disabled, change-controlled shell story in the prod team [BY HAND] and commits its id, so the first ship is a `versionReplace` into a draft + change request. Only a `workflow_dispatch` with the explicit, logged input `new_in_prod_reason` lets `import_story.py --allow-new-in-prod` create it, and the returned id is then committed to the manifest by a follow-up PR (the job opens it).

#### `.github/workflows/promote.yml`
**Builder:** ci. **Purpose:** optional: promote a change request **only after a human approved it in Tines**; never bypass. **Key content:** `on: workflow_dispatch` (inputs `slug`, `change_request_id`, `draft_id`). `environment: production`. Steps: `./scripts/tines cr-view <slug> --env prod --draft <id>` → assert `change_request.status == "APPROVED"` (else fail with "approve in Tines first") → `./scripts/tines cr-promote <slug> --env prod --change-request-id <id> --delete-draft` (`POST /api/v1/stories/{id}/change_request/promote` with `delete_draft: true`; `bypass_approval` is never passed here) → `./scripts/tines version-create --name "release <sha>"` → job summary. The workflow cannot approve: no approver key exists in CI.

#### `.github/workflows/skills.yml`
**Builder:** ci. **Purpose:** tenant-side Agent Skills are code: reviewed in the PR, pushed on merge. **Key content:** `on: push` (`main`, paths `tines-skills/**`). `environment: production` (keep required reviewers on it). Refuses any ref other than `main`; the `workflow_dispatch` inputs `only` and `confirm_delete` are validated against `^[a-z0-9]+(-[a-z0-9]+)*$` and reach the script through an env var, quoted — never interpolated into shell. `./scripts/tines skills-push --team $TINES_TEAM_ID_PROD`: per `tines-skills/<name>/SKILL.md` → `GET /api/v1/skills/<name>?team_id=` → 200 ⇒ `PUT /api/v1/skills/<name>` (`team_id`, `description`, `body`, `license`, `compatibility`, `metadata` incl. `git_sha`, `repo_path`) ; 404 ⇒ `POST /api/v1/skills`. Renames: change directory and frontmatter in one PR; the API rewrites the name in every AI Agent action that references it. Deletion only via `workflow_dispatch` with `confirm_delete: <name>` → `DELETE /api/v1/skills/<name>?team_id=`. Attaching a skill to a preset or an agent is [BY HAND] (no API found — VERIFY) and recorded in `story.meta.yaml`.

#### `.github/workflows/drift.yml`
**Builder:** ci. **Purpose:** keep the repo truthful and the budget visible. **Key content:** `on: schedule` (`cron: '0 3 * * *'`) and `workflow_dispatch`. Job `drift` (Viewer-role team key — read-only by role, VERIFY): per manifest slug with `prod.story_id` → `./scripts/tines export <slug> --env prod --out .tines/drift/<slug>.json` → both sides through `normalize.jq`, every action's ingress `path`/`secret` excluded by key name (any action type — a Webhook, an MCP server action) → if changed: copy over with those identifiers as `<assigned-on-import>` (production values never reach git), scan the file with the `SECRET_PATTERNS` list and gitleaks before any push, `./scripts/tines audit --after <last run> --story-id <id>` (`GET /api/v1/audit_logs?after=&per_page=&page=`, filtered client-side by `story_id`; columns `user_email`, `operation_name`, `source`, `request_user_agent`; MCP activity rows flagged), `gh pr create --title "drift: <slug> changed in the tenant" --label drift --body <attribution table>`, POST a summary to `OPS_ROUTER_URL`. Job `budget`: `./scripts/tines ai-usage --relative_date today --group_by team` and `--group_by story` vs `policies/cost-ceilings.yml`; open or update an issue labelled `budget` on any team or story ≥ 80 %. Paginates and sleeps to stay under 5,000 req/min (audit_logs 1,000/min).

#### `.github/workflows/rollback.yml`
**Builder:** ci. **Purpose:** roll production back through the same change-control path; break-glass is a separate, logged job. **Key content:** `on: workflow_dispatch` (inputs `slug`, `target` = git ref, `reason`, `emergency: boolean`). Job `rollback`, `environment: production`: checkout `target` → `./scripts/tines version-create --name "pre-rollback <sha>"` → `import-draft <slug> --env prod --file <ref's story.json> --draft-name rollback-<target>` → `recipients-add` + `story-update` on the draft → `cr-open --title "ROLLBACK <slug> to <target>" --description "<reason> <incident link>"` → summary. A human approves in Tines; `promote.yml` or the approver pushes. Job `break-glass` (runs only when `emergency: true`), `environment: break-glass` (two required reviewers): `./scripts/tines story-disable <slug> --env prod` (`POST /api/v1/stories/{id}/disable` — toggles, bypasses change control by design, audited; expect a burst of failure notifications, the router dedupes; safe-disable order noted in the summary) → then the `rollback` job → if promotion cannot wait: `BREAK_GLASS=1 ./scripts/tines cr-promote … --bypass-approval --reason "<reason>"` (`bypass_approval: true`, `bypass_approval_reason`; STORY_MANAGE) → append a line to `policies/break-glass-log.md` and commit it in the same run → re-enable via `story-disable` (toggle) after the approver confirms.

#### `.github/workflows/propose-fix.yml`
**Builder:** ci. **Purpose:** close the loop from the monitor story to a PR without giving the pipeline tenant access. **Key content:** `on: repository_dispatch` (`types: [tines-fix-proposal]`) and `workflow_dispatch` (input: proposal JSON). `concurrency: proposals` (one at a time). `timeout-minutes: 20`. Steps: checkout → write `${{ toJson(github.event.client_payload) }}` to `.tines/proposal.json` → `uses: anthropics/claude-code-action@v1` with `prompt: "/tines-propose-fix .tines/proposal.json"`, `claude_args: "--max-turns 15 --allowedTools Read,Grep,Glob,Edit(stories/**),Bash(jq *),Bash(./scripts/lint-story.sh *),Bash(./scripts/diff-story.sh *),Bash(git *)"` → the skill opens a PR labelled `ops-proposal` (or diagnosis-only). The daily cap is enforced by the story (`ops_limits.max_proposals_per_day`), not here. The PR then goes through `lint.yml`, `review.yml`, a human merge, `ship.yml` and a human change-request approval.

### 3.5 Scripts (`scripts/`)

#### `scripts/tines`
**Builder:** ci. **Purpose:** one bash+jq dispatcher for every Tines API call the repo needs, so skills, hooks and CI share one audited code path and the model never composes raw `curl` against the key. **Key content:** base `https://$TINES_TENANT.tines.com`; header `Authorization: Bearer $TINES_API_KEY`; `--env dev|prod` resolves `team_id`, `folder_id`, `story_id` from `stories/_manifest.yaml` (via `yq`); prod refused unless `TINES_ALLOW_PROD=1` (CI sets it); retry on 429 with backoff; never prints the key; non-2xx exits non-zero with the body's error; a 404 on a write means an underprivileged key, say so. Subcommands → endpoints:
- `export <slug> [--env] [--draft <id>] [--out]` → `GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true[&draft_id=]` | `jq -S -f scripts/normalize.jq`
- `import-draft <slug> --env [--file] [--draft-name]` → `POST /api/v1/stories/import {data, team_id, folder_id, mode: "versionReplace", draft_name}` (or `mode: "new"` + `new_name` for `new: true` — refused in prod unless `--allow-new-in-prod "<reason>"`, which only `ship.yml`'s logged `new_in_prod_reason` dispatch input passes); prints the draft id (response field VERIFY)
- `cr-open <slug> --env --draft <id> --title --pr-url <url> --diff <file> --rollback-ref <sha> [--reason "…"]` → `POST /api/v1/stories/{id}/change_request` (description from a fixed template: story · environment · commit SHA · PR URL · semantic diff · rollback ref; as built there is no `--description` option — `change_request.py open` builds the description from these flags)
- `cr-view <slug> --env --draft <id>` → `GET /api/v1/stories/{id}/change_request/view?draft_id=` → prints `status` and a jq diff of `live_story_export` vs `draft_export`
- `cr-promote <slug> --env --change-request-id [--delete-draft] [--bypass-approval --reason "…"]` → `POST /api/v1/stories/{id}/change_request/promote`; `--bypass-approval` accepted only when `BREAK_GLASS=1` and `--reason` are set
- `version-create <slug> --env --name` → `POST /api/v1/stories/{id}/versions`; `versions-list` → `GET`
- `recipients-add | recipients-remove <slug> --env --address <email|url> [--draft <id>]` → `POST | DELETE /api/v1/stories/{id}/recipients {address, draft_id?}`
- `story-update <slug> --env --monitor-failures true|false [--draft <id>] [--locked true|false]` → `PUT /api/v1/stories/{id}`
- `action-update <slug> --env <env> --action-id <id> [--monitor-no-events <seconds>] [--action-monitor-failures true|false] [--action-monitor-all-events true|false] [--draft <id>]` → `PUT /api/v1/actions/{id}` (as built: the dispatcher hands it to `set_monitoring.py`, where `--monitor-failures` is the *story*-level flag)
- `story-disable <slug> --env` → `POST /api/v1/stories/{id}/disable` (toggles; bypasses change control; the kill switch)
- `live-activity [--env] [--slug]` → `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true&per_page=100` (or `GET /api/v1/stories/{id}?include_live_activity=true`) → table of `not_working_actions_count`, `pending_action_runs_count`, `monitor_failures`, `actions_with_monitoring`, `recipients`
- `action-logs <action_id> [--level 4]` → `GET /api/v1/actions/{id}/logs?level=4`
- `runs <slug> --env [--since <ts>]` → `GET /api/v1/stories/{id}/runs?since=` (+ `/runs/{guid}/summary` with `--summary <guid>`)
- `ai-usage [--relative_date today | --start_date --end_date] [--group_by story|team|action|day] [--story-id]` → `GET /api/v1/ai_usage` → `credits_used`, `billed_cost`, tokens
- `audit --after <ts> [--story-id <id>] [--operation-name <name>]` → `GET /api/v1/audit_logs?after=&per_page=&page=` (client-side `story_id` filter; server-side `operation_name[]` once the MCP operation name is known — VERIFY)
- `skills-push --team <id> [--dry-run] [--only <name>] [--delete <name> --confirm <name>]` → `GET/PUT/POST/DELETE /api/v1/skills…` as in `skills.yml`
- `resource-cas <resource_id> --key <k> --value <v> --if-value <expected>` → `POST /api/v1/global_resources/{id}/replace` (used by tests of the lock; 422 = mismatch, printed with the current value)

#### `scripts/normalize.jq`
**Builder:** ci. **Purpose:** make exports diff-stable and safe to commit without changing meaning. **Key content:** `del(.exported_at)`; every action's ingress `options.path` / `options.secret` replaced by key name (never by action type; formulas and placeholders kept) with `<assigned-on-import>`, so no Webhook or MCP server URL component reaches git (lint `webhook_secret_in_export`, severity error); keys sorted by `jq -S` at call time; **agent order preserved** on purpose (links reference agents by index); `guid` kept; `diagram_layout` kept (noisy but harmless — reviewers use `diff-story.sh` and `cr-view` for the semantic diff).

#### `scripts/lint-story.sh`
**Builder:** ci. **Purpose:** deterministic convention checks a hook, a skill and CI all share; rules driven by `policies/lint-rules.yml`. **Key content (jq checks):** valid JSON with `schema_version`, `name`, `description`, `agents[]`, `links[]`; name matches `^\[[A-Z]+\] [0-9]{2} · .+`; `(sub)` names contain an `Agents::EventTransformationAgent` named `result`; every agent has a name and description; no duplicate agent names; every `Agents::HTTPRequestAgent` has retry/emit-failure options (KEY NAMES VERIFY — read one real export first and set them at the top of the script); every `Agents::LLMAgent` has an output-schema option (KEY NAME VERIFY) and appears in `story.meta.yaml: ai.agents` with a `budget_ref`; no options value matches secret/token/email patterns; every credential/resource referenced in options (`{{ .CREDENTIAL.x }}` / `{{ .RESOURCE.y }}` forms — exact formula syntax in exports VERIFY) is listed in meta; `meta.tier: production` ⇒ `monitoring.monitor_failures: true`, recipients non-empty, watchdog on the entry or scheduled action; no schedule inside a Group; `keep_events_for` ≥ 30 days for prod (key VERIFY). Exit 1 with one line per failure: `<path>: <rule>: <detail>`; `--format json` emits `{findings: [...]}` for CI.

#### `scripts/diff-story.sh`
**Builder:** ci. **Purpose:** semantic diff for PR bodies and change-request descriptions. **Key content:** jq over two exports; match actions by `guid` then by name; report added/removed/renamed actions, changed option keys per action (values redacted to lengths for anything matching a secret pattern), links added/removed, schedule changes, `monitor_*` flag changes, `disabled` flag changes; Markdown output; `--against HEAD|<sha>|<file>`.

### 3.6 Stories (`stories/`)

#### `stories/README.md`
**Builder:** stories. **Purpose:** how a story folder is laid out and the lifecycle of `story.json`. **Key content:** `story.json` = normalised export (credentials, resources and events are excluded by Tines; recipients cleared on export); `story.meta.yaml` = environment-independent facts the export does not carry; `tests/` = one sample event + expectations; `README.md` = purpose, mode badge, Library IDs it descends from, runbook, change log. Lifecycle: build in dev via `/mcp` → `/tines-export` → PR → merge → `ship.yml` → draft → change request → approved → live → `drift.yml` proves prod equals main every night.

#### `stories/_manifest.yaml`
**Builder:** stories. **Purpose:** the environment map and the slug → story-id map. The only place environment differences live; no secrets.
**Key content:**
```yaml
environments:
  dev:  { team_id: 0, folder_id: 0, api_key_secret: TINES_API_KEY,      recipients: ["${OPS_ROUTER_URL}"] }
  prod: { team_id: 0, folder_id: 0, api_key_secret: TINES_API_KEY_PROD, recipients: ["${OPS_ROUTER_URL}", "${OPS_EMAIL_DL}"],
          read_key_secret: TINES_API_KEY_PROD_READ, locked_slugs: [ops-error-router, ops-story-health-monitor, ops-tools-server] }
  # staging: optional third environment, same shape
stories:
  example-enrich-ip:        { dev: { story_id: 0 }, prod: { story_id: 0 }, tier: production, owner: security-automation }
  ops-error-router:         { dev: { story_id: 0 }, prod: { story_id: 0 }, tier: ops,        owner: ops }
  ops-story-health-monitor: { dev: { story_id: 0 }, prod: { story_id: 0 }, tier: ops,        owner: ops }
  ops-tools-server:         { dev: { story_id: 0 }, prod: { story_id: 0 }, tier: ops,        owner: ops }
```
Rules: story names must be identical in every environment (`versionReplace` matches by name); a new story's dev id is recorded by hand once the builder creates it through `/mcp` (nothing else writes it); a slug with `new: true` has no prod id yet — preferably a by-hand, disabled, change-controlled shell story whose id is committed first, since `import_story.py` refuses `mode: new` in prod unless `ship.yml` is dispatched with the logged `new_in_prod_reason` (the returned id is then committed afterwards); `tier: production` ⇒ change control required and monitoring enforced by `ship.yml`; `locked_slugs` get `locked: true` via `story-update` after ship.

#### `stories/_template/README.md`
**Builder:** stories. **Key content:** sections — Purpose (one paragraph, matches the on-canvas Note) · Mode badge (which of the four modes it serves, or none) · Entry (Webhook / Send to Story / schedule) and expected input fields · Output (the `result` shape) · Failure shape · Credentials and Resources by name · Monitoring (recipients, watchdog) · Test event · Runbook (what to do when the router pages for it) · Change log (sha → what).

#### `stories/_template/story.meta.yaml`
**Builder:** stories. **Purpose:** the per-story control file lint, ship, the reviewer and the sweep read.
**Key content:**
```yaml
slug: <slug>
name: "[PREFIX] NN · Verb noun (sub)"       # must equal story.json name
mode: none | sub-story | mode-3-agent | mode-4-server
owner_team: <team-prefix>
tier: production | internal | ops | seed
change_control: required
monitoring:
  monitor_failures: true
  recipients: manifest                        # resolved by ship.yml
  no_events_watchdog: { action: "<entry or poll action name>", seconds: 7200 }
keep_events_for_days: 30
credentials: []                               # names only; must exist in each target team
resources: []
ai:
  agents: []                                  # [{name, output_schema: true, token_alert: {notify, disable}, skills: [], budget_ref: "<slug>/<agent>"}]
schedule_interval_seconds: 0                  # 0 = event-driven; used by the sweep's overlap check
exported_from: { env: dev, story_id: 0, draft_id: "", at: "", sha: "" }
```

#### `stories/_template/tests/sample-event.json` and `tests/expectations.yaml`
**Builder:** stories. **Key content:** sample: `{ "ip": "203.0.113.10", "requester": "builder@example.invalid", "source": "test" }` — documentation-range values only. Expectations: `entry_action: <name>`, `expected_actions_fired_min: N`, `no_error_logs_on: [<action names>]`, `result_fields: [verdict, score, sources, summary]`; the build skill posts the sample to the entry action (`?draft=<name>` under change control) and asserts these against the run's events.

#### `stories/example-enrich-ip/` (`README.md`, `story.json`, `story.meta.yaml`, `tests/`)
**Builder:** stories. **Purpose:** the worked example every builder clones: a Send to Story sub-story that enriches an IP and returns a verdict; shows the full contract. **Key content:** built from Library **87626** (Analyze an IP in many services at once) via the build skill. Name `[SEC] 01 · Enrich IP (sub)`. Entry: Send to Story expecting `{ip}`. Actions: `normalize` (`DEFAULT` fallbacks) → Trigger `is_protected` (`IN_CIDR` against the `never_block` Resource → returns `{status: refused, reason: protected range}` before any lookup) → vendor templates paced to free-tier limits (verdicts cached in an `ioc_cache` Record with a TTL) → `verdict` → `result` `{verdict, score, sources[], summary}` → `error` shape on the failure path; HTTP hardening on every request. Mode badge: sub-story (callable from stories, from the Mode 3 agent as a Send to Story tool, and exposed through the Mode 4 server). Meta: `tier: production`, `credentials: [virustotal_api, abuseipdb_api]`, `resources: [never_block]`, `ai.agents: []`. `story.json` is produced by `/tines-export`, never typed; it contains no credential values, resource contents or events (exports omit them by design).

#### `stories/ops-error-router/` (`README.md`, `story.json`, `story.meta.yaml`, `samples/monitoring-payload.sample.json`, `tests/`)
**Builder:** stories. **Purpose:** the single monitoring recipient for every production story; the intake for tenant AI-credit, event-limit and change-control webhooks. **Key content:** name `[OPS] 01 · Route monitoring alerts`. Start from Library **1231438** (Monitor action failures in Tines and notify via Slack); confirm the entry action after import (expected: Webhook). Flow: Webhook (`+ Option` → respond 200 fast) → `normalize` (payload shape VERIFY — captured once by deliberately failing an action in a LIVE scratch story with a test recipient; the captured sample lives in `samples/`) → Trigger `classify_source` (story monitoring | AI credit usage alert | event-limit alert | change-control webhook) → dedupe per story+action+15-minute window (Deduplicate mode, or a Records check on `ops_alerts`) → enrich (story link, action name/type, last error log via `GET /api/v1/actions/{id}/logs?level=4` with credential `tines_api_readonly`, `allowed_hosts` = the tenant host, Workbench access off; severity class: 401/403 → owner, 429 → back off, 5xx persistent → escalate, no-events → silent source) → Slack thread per story per day (channel from `ops_routing`) → write `ops_alerts` → Send to Story into the sweep for severity ≥ medium or count ≥ 3. Runs **LIVE** (monitoring is unavailable in TEST mode). Its own recipients = the email DL only (a second channel). Meta: `tier: ops`, `credentials: [tines_api_readonly, slack_bot]`, `resources: [ops_routing, ops_limits]`, `schedule_interval_seconds: 0`. Costs one flow.

#### `stories/ops-story-health-monitor/README.md`
**Builder:** stories. **Purpose:** operator-facing summary of the sweep. **Key content:** watches action failures (via router), silent sources, failing runs without a status field (derived), coverage drift, credit burn vs budgets, overlap, dead-letter depth, Mode 4 server health. May do alone: write Records, post threads, add missing recipients **in dev**, open GitHub issues with a diagnosis and an exact `/tines-build-story` prompt. Needs a human (Slack approval verified against `ops_responders`): apply an alert rule to prod, disable a story or action, trigger a proposal PR, anything that lands as a change request. Never holds a write credential in the agent. Kill switch: `ops_limits.enabled`. Mode badge: **Mode 3** (AI Agent action, Task mode; tools are Tines tools — Send to Story sub-stories; optional single MCP connection to the Mode 4 ops server).

#### `stories/ops-story-health-monitor/DESIGN.md`
**Builder:** stories. **Purpose:** §5 of this document copied into the repo so it is self-contained. **Key content:** exactly §5 below, plus the flow budget and the decision table.

#### `stories/ops-story-health-monitor/story.json` and `story.meta.yaml`
**Builder:** stories. **Key content (story.json, as exported after building from DESIGN.md in dev):** name `[OPS] 10 · Monitor story health and credits`. Schedule entry `{"cron": "*/15 * * * *"}` + a Webhook entry (approval callbacks; the Slack request signature and a 5-minute timestamp window are verified in-story, with the credential `slack_signing_secret`, before the callback is parsed) + Send to Story input from the router → Trigger `kill_switch` (`ops_limits.enabled`) → HTTP Request `acquire_lock` (CAS on `ops_lock`; 422 excluded from errors) → HTTP Request `live_activity` (`GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true`) → HTTP Request `ai_usage_today` (`GET /api/v1/ai_usage?relative_date=today&group_by=story`) → HTTP Request `recent_runs` for scheduled stories (`GET /api/v1/stories/{id}/runs?since=`) → Event Transform `findings` (deterministic anomaly pre-filter vs `ops_baselines` and `ops_limits`) → Trigger `coverage_gap` → (dev only) `recipients_add` with the credential `tines_api_dev_autofix`, which holds a real key only in the dev team, so the write fails closed in prod whatever `ops_limits` says; prod → proposal → Trigger `has_anomaly` → **`Agents::LLMAgent` `triage`** (Task mode; skills `story-health-triage`, `credit-budget-analyst`; five read-only Send to Story tools; output schema) → **`Agents::LLMAgent` `critic`** (tool-less, fast model, high/critical only) → Trigger on `severity` / `proposed_change.kind` → branches: `record_only` · `propose_alert_rule` (Record + Slack approval) · `propose_fix` (HTTP Request to GitHub `repository_dispatch`, credential `github_dispatch`, `allowed_hosts` `api.github.com`) · `request_disable` (Slack approval; two approvers in prod) → `apply` (Send to Story into the apply sub-story, credential `tines_api_ops` lives only there; a disable is dispatched to `rollback.yml`'s break-glass job, never called directly) → HTTP Request `release_lock` (also on every failure branch; the lock actions use their own lock-only key `tines_api_ops_lock`). Meta: `tier: ops`, `schedule_interval_seconds: 900`, `credentials: [tines_api_readonly, tines_api_ops_lock, tines_api_dev_autofix, slack_bot, slack_signing_secret, github_dispatch]` (never `tines_api_ops`), `resources: [ops_limits, ops_responders, ops_routing, ops_lock]`, `ai.agents: [triage, critic]` each with `budget_ref` and `token_alert`, monitoring: recipients = email DL + a second Slack channel; watchdog on the schedule action at 1,800 s.

#### `stories/ops-story-health-monitor/agent/system-instructions.md`
**Builder:** stories. **Key content:** "You diagnose one Tines story's health from evidence the story fetched or you fetch with the lookup tools. Fetch before you conclude. You cannot change anything; you only propose. Never claim a fix was applied. Return only the schema. If evidence is insufficient, set `needs_human` true and say what is missing. Rejected proposals listed in the prompt must not be repeated."

#### `stories/ops-story-health-monitor/agent/output-schema.json`
**Builder:** stories. **Key content:** the schema in §5.5.

#### `stories/ops-story-health-monitor/agent/tools.md`
**Builder:** stories. **Key content:** the tool set in §5.4, each with its 3–4-sentence description and one example argument value (descriptions are the API; tool responses carry no output schema).

#### `stories/ops-story-health-monitor/resources/*.example.json`
**Builder:** stories. **Key content:** `ops_limits.example.json` — `{"enabled": true, "environment": "prod", "sweep_minutes": 15, "error_threshold_per_window": 3, "overlap_ratio": 0.8, "credit_budget_daily": {"default": 200, "per_story": {}}, "credit_alert_pct": [80, 95], "auto_apply_in_dev": false, "auto_apply_in_prod": false, "max_proposals_per_day": 5, "agent_runs_per_day_max": 96, "agent_credits_per_run_max": 3, "stale_lock_minutes": 30}` (mirrors `policies/cost-ceilings.yml`; the lock lives in the separate `ops_lock` Resource `{"lock": "free"}`; the committed example defaults to the safe values — a copied example never auto-applies anything — and only the dev team's `ops_limits` sets `"environment": "dev"` and `"auto_apply_in_dev": true`). `ops_responders.example.json` — `{"alert_rule": ["ops-role-1@example.invalid"], "credit_action": ["ops-role-1@example.invalid", "ops-role-2@example.invalid"], "disable": ["ops-role-1@example.invalid", "ops-role-2@example.invalid"], "two_required_for": ["disable", "credit_action"], "proposal_pr": ["ops-role-1@example.invalid"]}` (placeholders; real values set in the tenant, never committed). `ops_routing.example.json` — `{"default": {"channel": "#ops-tines", "owner_team": "ops"}, "example-enrich-ip": {"channel": "#sec-automation", "owner_team": "security-automation"}}`.

#### `stories/ops-story-health-monitor/records/record-types.md`
**Builder:** stories. **Purpose:** the Record types the ops pair needs (Record-type creation is [BY HAND]; whether `/mcp` can create them is VERIFY). **Key content:** `ops_alerts` (alert_id, story_id, action_id, category, severity, first_seen, last_seen, count, status — also the dedupe store) · `ops_findings` (run_id, story_id, severity, category, hypothesis, recommended_fix, confidence, model, credits_used, tokens, outcome) · `ops_alert_proposals` (proposal_id, story_id, target_id, type, value, rationale, status `pending|approved|rejected|applied|expired`, approver, at, rejection_reason, change_request_id, pr_url) · `ops_baselines` (story_id, action_id, day, runs, error_logs, credits, median_duration_s, p95_interval_s) · `ops_credit_ledger` (day, team_id, story_id, credits_used, billed_cost) · `ops_dead_letter` (ref, story_id, error_class, status, at, payload_ref — never the body). Dashboards chart Records and Cases only, so these are also the digest's data source.

#### `stories/ops-tools-server/` (`README.md`, `story.json`, `story.meta.yaml`)
**Builder:** stories. **Purpose:** **Mode 4** — expose the ops read-only lookups and the two request tools as an MCP server so the builder's editor, a Claude client or the on-call person can ask the same questions the agent asks, and request the same actions through the same approval path. **Key content:** name `[OPS] 20 · Ops tools (MCP server)`. One **MCP server action** (template picker label "MCP Server") at `https://<your-tenant>.tines.com/mcp/<mcp-path>`. Tools (all Send to Story, each pointing at the corresponding sub-story, each with a one-line description the model can choose by): `ops_get_live_activity`, `ops_get_error_logs`, `ops_get_recent_runs`, `ops_get_story_export`, `ops_get_ai_usage` — **Tool hints: Read only ON** on every lookup; `request_alert_rule` and `request_disable` — request tools that post to the same Slack approval and return `{approval_id, status: pending, approvers}`; their descriptions state what they do *not* do ("Does not disable. Posts an approval and returns approval_id."). Server description written as instructions ("You are an ops assistant for Tines stories. Fetch evidence before you recommend. `request_disable` only requests; a human approves."). Access control: **With a Tines API Key** scoped to members of the ops team (the caller's email lands in `META.headers.email` and is written to the Record); `Include headers` on. `+ Option` → Summary tab → copy the Remote Server snippet for the README. Counts as one flow; consumes no AI credits; tool responses must return within 30 seconds. Meta: `tier: ops`, `mode: mode-4-server`. Whether the editor can add the MCP server action itself through `/mcp` is VERIFY — if not, drag it on by hand and let the editor wire the tools.

### 3.7 Tenant-side Agent Skills (`tines-skills/`)

#### `tines-skills/README.md`
**Builder:** agent-skills. **Key content:** the two skill families — IDE skills (`.claude/skills/`) teach the editor; Tines Agent Skills (`tines-skills/`) teach AI Agent actions and Workbench presets in the tenant; both follow the Agent Skills standard (`SKILL.md`), both are reviewed in the same PR; the tenant ones are pushed by `skills.yml` through `POST`/`PUT /api/v1/skills`; attaching to a preset or an agent is [BY HAND]; size/count limits, versioning and credit consumption of skills are VERIFY.

#### `tines-skills/story-health-triage/SKILL.md`
**Builder:** agent-skills. **Purpose:** attached to the sweep's `triage` agent and to an Ops Workbench preset. **Key content:** frontmatter `name: story-health-triage`, `description: Triages a failing or silent Tines story from error logs, live activity, recent runs and AI usage, and proposes the smallest safe fix with evidence. Used when a story or action is unhealthy, silent, over budget or overlapping.`, `license: Proprietary`, `compatibility: Tines AI Agent action (Task mode) and Workbench presets`, `metadata: { owner: ops, version: "1" }`. Body (under 5,000 tokens): classification rules (401/403 → credential or permission, owner action; 429 → pacing, propose throttle or cache; 5xx persistent → upstream, escalate and propose longer retry; no events in 2× interval → silent source, check feed and key; schema failure → agent output, propose schema fix; credit burn → provider and tool count; overlap → lock or schedule change; expected 422 from locks is not a failure; only the final retry notifies) · evidence rules (cite log id, run guid, usage row; never infer from one event) · never propose (disabling a production story without a human; editing credentials; anything outside the story named in the task; anything in never-touch without `needs_human`) · output shape = the story's output schema · `needs_human` must be true when severity is high or critical, confidence < 0.6, or category unknown.

#### `tines-skills/credit-budget-analyst/SKILL.md`
**Builder:** agent-skills. **Purpose:** attached to the same agent; how to read AI-usage rows against budgets. **Key content:** frontmatter `name: credit-budget-analyst`, `description: Interprets Tines AI usage rows against team and story budgets and names the costliest story or action with the evidence row. Used when credits or billed cost approach a threshold.` Body: compare `credits_used` by story/day to the budget in the prompt; a custom-provider action bypasses credits but still bills (`billed_cost`); propose disable or reroute as `credit_action`, never apply; at 80 % summarise, at 95 % name one action to pause; the platform's own 100 % stop is the backstop, not the plan.

#### `tines-skills/story-build-conventions/SKILL.md`
**Builder:** agent-skills. **Purpose:** the same conventions as `AGENTS.md`, distilled for the builders' Workbench for Storyboard preset so answers given inside Tines match the repo (whether Workbench for Storyboard honours preset skills is VERIFY). **Key content:** frontmatter `name: story-build-conventions`, `description: States this tenant's story conventions (naming, sub-story result contract, HTTP hardening, monitoring, AI Agent rules) so Workbench answers and agent-drafted configurations match the repository. Used whenever a story is being designed, reviewed or extended inside Tines.`, `metadata: { owner: platform, source: "AGENTS.md", version: "1" }`. Body: the naming rule, the result/error contract, the HTTP hardening table, the watchdog rule, the AI Agent rules, the never-touch list, and "if the story will be exported to the repository, keep credentials and resources referenced by name". `lint.yml` compares a checksum of the shared block with `AGENTS.md`.

### 3.8 Terraform (`terraform/`, optional)

#### `terraform/README.md`, `terraform/main.tf`, `terraform/stories.tf`
**Builder:** ci. **Purpose:** the official "store your stories as code in Git" path, kept as an optional alternative that is **not** on the default pipeline. **Key content:** provider `tines` configured from `TINES_TENANT`/`TINES_API_KEY`; registry version 0.3.0 (2025-08-01; 0.x may break in minors); `tines_story { data = file("../stories/<slug>/story.json"), team_id, folder_id, change_control_enabled = true, keep_events_for, tags }`; `tines_resource` for `ops_limits` (value from a tfvar, never committed); `tines_credential` (TEXT only) with `value_wo`/`value_wo_version` so secrets never land in state. README: VERIFY how `tines_story` applies to a change-controlled story (draft vs live) before using it for prod; no `tines_skill` or record-type resource exists, so skills stay on the API path; `terraform apply` is denied in the IDE.

### 3.9 Docs (`docs/`)

#### `docs/00-why-stories-as-code.md`
**Builder:** docs. **Key content:** the thesis of §1.2 written for someone deciding whether to adopt the repo; the three ways to build compared — Workbench for Storyboard (knows the tenant; spends credits or a custom provider), Mode 2 from an editor (your provider, diffs, bulk edits, no Tines credits listed — helpers VERIFY), the API/Terraform path (official; provider 0.3.0; TEXT credentials only; no skills resource; change-control behaviour VERIFY); ends with §8.

#### `docs/01-decision-rules.md`
**Builder:** docs. **Key content:** the simplest-first ladder, visibly ordered: 1 HTTP Request action or template (known API, known sequence, no judgment) → 2 Send to Story with a Timeout Duration (reuse inside the tenant) → 3 AI Agent action with Tines tools and no MCP (judgment over Tines data or chat) → 4 Mode 3 with an MCP connection (a vendor already hosts a server; one tool first; output schema; token alert; Streamable HTTP or Plain HTTP; Business or Enterprise plan) → 5 Mode 4 (an AI client outside Tines must trigger a workflow or read data; read tools plus request tools; Tool hints set; team-scoped key) — and Mode 2 whenever the builder lives in an editor and wants diffs. Never MCP for bulk data movement, sub-second latency, or a destructive action with no approval path. Tool results are context, not a data plane. A typed, gate-able, auditable request tool beats a generic "run anything" tool.

#### `docs/02-change-control-path.md`
**Builder:** docs. **Key content:** the exact path in text: builder in editor → `/mcp` edits the DEV story (whether these land as drafts is VERIFY; policy on regardless) → export → branch → PR → `lint.yml` + `review.yml` → CODEOWNERS review → human merge → `ship.yml`: `POST /versions` → `POST /stories/import` (`versionReplace`, `draft_name git-<sha>`) → recipients + `monitor_failures` on the draft → `POST /change_request` → approver reads `GET /change_request/view` (`live_story_export` vs `draft_export`) and the PR → approves in Tines → pushes (or `promote.yml` on APPROVED) → live → `drift.yml` proves it that night. Rollback and break-glass as §4.5. Tenant policies required: "Enable by default", "Require approval for all changes" (admins and owners included), story requirements (name, description, owners, tags, event retention) set to required; team change-control webhooks (created/cancelled/approved/rejected/pushed) pointed at the router so approvals appear in the ops thread. Draft naming: `git-<sha>`, `rollback-<target>`, `monitor-<finding_id>`. Drafts go inactive after 30 minutes and lock on review request; test-mode credentials apply in drafts.

#### `docs/03-monitoring-story.md`
**Builder:** docs. **Key content:** §5 in prose for operators: signals table (source → direct or derived → owner action), the agent's role (read-only, propose only), the approval flow, the "what stays by hand" list (AI Agent token thresholds on the Status tab; per-team credit allocation in Admin → AI; credit-usage alert thresholds; Record types), the weekly digest, and the runbook for when the monitor itself is silent (its own watchdog pages the DL).

#### `docs/04-cost-controls.md` and `docs/05-security-controls.md`
**Builder:** docs. **Key content:** §6 and §7 as tables: control · mechanism (editor / repo / CI / tenant) · enforced by (hook, permission rule, workflow, policy, Resource, Tines setting) · verify status.

#### `docs/06-pros-and-cons.md`
**Builder:** docs. **Key content:** §8 verbatim.

#### `docs/VERIFY.md`
**Builder:** docs. **Key content:** §10 as a table with columns *what we assumed* · *how to confirm in-tenant* (page, API call or client) · *what changes in the repo when confirmed*. Nothing here is a headline claim.

---

## 4. Workflows

Each workflow names the exact files, the MCP surface (Mode 2 `/mcp` for authoring; Mode 4 for exposing tools; Mode 3 for the monitoring agent), the Tines API endpoints (only those in the research) and the IDE features used.

### 4.1 Build a story (one afternoon, dev team) — **Mode 2**

IDE features: user-scope MCP server (`claude mcp add … --scope user`, `~/.cursor/mcp.json`), skills (`/tines-connect`, `/tines-build-story`, `/tines-export`), the `tines-builder` subagent (isolated context holding the server), PreToolUse/PostToolUse/Stop hooks, permission rules.

1. `cp .env.example .env`; fill `TINES_TENANT` and a **team-scoped** dev key; `source .env`. Run **`/tines-connect`** — adds `https://<your-tenant>.tines.com/mcp` at user scope (Claude Code: `claude mcp add --transport http tines --scope user …` then `/mcp` for the consent screen "Tines Stories MCP server" — inferred, VERIFY; Cursor: `~/.cursor/mcp.json`), runs the smoke prompt (list teams and stories). An API key will not work here.
2. Add the slug to `stories/_manifest.yaml` (`new: true` if the story does not exist); copy `stories/_template/` to `stories/<slug>/`; fill `story.meta.yaml` (credentials by name — they must already exist in the dev team, created [BY HAND] with `allowed_hosts`).
3. **`/tines-build-story <slug> "<what to build>"`** — delegated to `tines-builder`. *Explore:* through the Tines Stories MCP server, read the story named in the manifest or create it in the dev team (folder from the manifest); a story created here gets its dev id recorded as `dev: { story_id: <id> }` in the manifest at once — nothing else writes it, and `/tines-export` stops on a dev id of `0`. *Plan:* for anything bigger than a sentence, a numbered plan of actions with type, name and field names; wait for a yes.
4. *Implement:* one prompt per action from `.claude/skills/tines-build-story/references/prompt-pack.md` — entry → `normalize` (`DEFAULT` fallbacks) → a guard Trigger before any AI step → integrations with named credentials → `verdict` → `result` (3–5 fields) → `error` shape on the failure path → HTTP hardening (`retry_on_status [429, 500-599]`, retries 6, `emit_failure_event` Always) → a Note on the canvas. `guard-mcp.sh` mirrors every call to `.tines/mcp-activity.jsonl` and blocks any production id or destructive-looking name.
5. *Validate:* end with "Validate"; fix what it reports; after two failed corrections on one issue, stop and re-prompt.
6. *Test:* post `stories/<slug>/tests/sample-event.json` to the entry action (`?draft=<name>` when change control is on); read the events (`GET /api/v1/stories/{id}/runs` + `/runs/{guid}` if needed); compare with `tests/expectations.yaml`.
7. *By hand* (the skill says so explicitly): Send to Story access for the team (sub-stories); event retention above 7 days; change control on for a new story; Record types; the AI Agent token alert on the Status tab.
8. **`/tines-export <slug>`** — `./scripts/tines export` (`GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true`) → `normalize.jq` → `./scripts/lint-story.sh` (the PostToolUse hook runs it again on every write) → stamps `exported_from` in `story.meta.yaml` → `./scripts/diff-story.sh`.
9. Commit on branch `story/<slug>/<short>` (`story(<slug>): <what changed>`). `stop-gate.sh` refuses to end the turn while lint fails or the export is older than the last MCP call. The skill ends with "Run `/tines-review` from a fresh session before opening the PR."

### 4.2 Review and ship (repo → production)

IDE features: `context: fork` skill on the `tines-reviewer` subagent (no MCP, read-only tools), `claude-code-action@v1` with `--max-turns`, `--allowedTools`, `--json-schema`; GitHub environments with required reviewers.

1. **`/tines-review`** runs in a forked context on `tines-reviewer` and returns findings JSON (`references/findings-schema.json`). Fix blockers with another `/tines-build-story` pass and re-export — never by editing `story.json`.
2. `git push` (ask) and `gh pr create` (ask) with `.github/PULL_REQUEST_TEMPLATE.md`. **`lint.yml`** (jq validity, `lint-story.sh`, skill frontmatter, manifest consistency, secret patterns, budget line) and **`review.yml`** (an independent Claude Code instance running `/tines-review`, findings as review comments) must pass.
3. A CODEOWNER reviews; a human merges to `main` (branch protection: both checks required; no self-merge).
4. **`ship.yml`** (GitHub environment `production`, optional required reviewers) per changed slug: `POST /api/v1/stories/{id}/versions` (rollback point) → `POST /api/v1/stories/import {data, team_id, folder_id, mode: versionReplace, draft_name: git-<sha>}` → `POST /api/v1/stories/{id}/recipients {address, draft_id}` for each manifest recipient and `PUT /api/v1/stories/{id} {monitor_failures: true, draft_id}` → `POST /api/v1/stories/{id}/change_request {draft_id, title, description}` → `GET …/change_request/view?draft_id=` into the job summary → the change-request URL to the ops channel.
5. The named approver opens the change request in Tines, reads the live-vs-draft diff and the PR, **approves and pushes**. Optionally, **`promote.yml`** (workflow_dispatch) reads `GET …/change_request/view`, requires `status: APPROVED`, and calls `POST …/change_request/promote {change_request_id, delete_draft: true}` — never with `bypass_approval`. The pipeline never promotes a PENDING request.
6. The team change-control webhook (approved/pushed) hits the router → the ops thread shows the deployment. `drift.yml` confirms that night that the tenant equals `main`; the next sweep baselines the story.

### 4.3 Push skills (tenant-side Agent Skills as code)

IDE features: `/tines-skills-push` (dry run), path-scoped rule `.claude/rules/tines-skills.md`, `lint-on-write.sh` advisory validation.

1. Edit or add `tines-skills/<name>/SKILL.md` (frontmatter: `name` = directory, lowercase-hyphen ≤ 64, `description` ≤ 1024 in third person, `license`, `compatibility`, `metadata` flat strings; body under 5,000 tokens).
2. **`/tines-skills-push <name>`** — `./scripts/tines skills-push --validate-only --only <name>` (the `skills-ref` validator only once confirmed and pinned — VERIFY #21) and `./scripts/tines skills-push --team $TINES_TEAM_ID --dry-run --only <name>`; with `--dev`, push to the dev team and run the dev sweep on a deliberately failing scratch story.
3. Open a PR; `lint.yml` validates the frontmatter; `review.yml` checks the body against `AGENTS.md`; CODEOWNERS for `tines-skills/` includes the security-platform group because a skill changes agent behaviour in production; a human merges.
4. **`skills.yml`** (environment `production`) runs `./scripts/tines skills-push --team <prod team>`: `GET /api/v1/skills/<name>?team_id=` → 200 ⇒ `PUT /api/v1/skills/<name>` ; 404 ⇒ `POST /api/v1/skills {team_id, name, description, body, license, compatibility, metadata}`; `metadata.git_sha` stamped.
5. Renames: change directory and frontmatter in one PR; the API rewrites the name in every AI Agent action that references the skill.
6. [BY HAND, once — no API found, VERIFY]: enable the skill on the Ops Workbench preset and attach it to the sweep's `triage` agent; record the attachment in `stories/ops-story-health-monitor/story.meta.yaml: ai.agents[].skills`.
7. Delete only by `workflow_dispatch` with `confirm_delete=<name>` → `DELETE /api/v1/skills/<name>?team_id=`; removing the folder alone is not enough.

### 4.4 Monitor and alert — **Mode 3** (the agent) and **Mode 4** (the exposed tools)

IDE features: none in the loop by design (the pipeline never holds `/mcp`); the Mode 4 server is what an editor or Claude client connects to when a human wants to ask the same questions.

1. Every production story's monitoring recipients = the router webhook (`OPS_ROUTER_URL`) + the email DL, set by `ship.yml` from the manifest (`POST /api/v1/stories/{id}/recipients`); story-level `monitor_failures` on (`PUT /api/v1/stories/{id}`); "notify if no events emitted" on scheduled and ingress actions at ≈ 2× the interval (`PUT /api/v1/actions/{id} {monitor_no_events_emitted}`); tenant AI credit usage alerts and event-limit alerts also target the router (defaults 80/100 VERIFY; set by hand — no API).
2. **Router** (`stories/ops-error-router/`, LIVE): normalize (payload shape captured once by a deliberate LIVE failure, VERIFY) → dedupe per story+action+15 min → enrich with the last level-4 log (`GET /api/v1/actions/{id}/logs?level=4`) and a severity class → Slack thread per story per day → `ops_alerts` Record → Send to Story into the sweep when severity ≥ medium or count ≥ 3.
3. **Sweep** (`stories/ops-story-health-monitor/`, cron `*/15`): Trigger on `ops_limits.enabled` → compare-and-swap lock on `ops_lock` (`POST /api/v1/global_resources/{id}/replace {key: lock, value: STORY_RUN_GUID(), if_value: free}`; 422 = already running, exit quietly) → `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true` → `GET /api/v1/ai_usage?relative_date=today&group_by=story` → `GET /api/v1/stories/{id}/runs?since=` for scheduled stories → deterministic pre-filter against `ops_baselines` and `ops_limits` (§5.6).
4. **Coverage drift:** a published production story with `monitor_failures: false` or empty recipients → in **dev** auto-fix (`POST /recipients`, `PUT /stories/{id}`); in **prod** → a proposal (step 6).
5. Only anomalous stories reach the **AI Agent action** `triage` (Task mode; skills `story-health-triage` + `credit-budget-analyst`; five read-only Send to Story tools wrapping the API with a Viewer-role key; output schema enforced). A tool-less `critic` agent re-reads the evidence for high/critical and may only confirm or downgrade; disagreement → `needs_human`.
6. A Trigger on explicit schema fields: `record_only` → `ops_findings` + thread reply; `alert_rule` → `ops_alert_proposals` (pending) + Slack Block Kit approval verified against `ops_responders` → the **apply sub-story** (the only place `tines_api_ops` lives): recipient → `POST /api/v1/stories/{id}/recipients` (draft semantics VERIFY); `monitor_*` flags → `PUT /api/v1/actions/{id}` / `PUT /api/v1/stories/{id}` into a draft → `POST /change_request` titled `monitor-<finding_id>` for the same approver; token thresholds and per-team credit allocation have no API → a Case task (if Cases is entitled) or a Record + thread [BY HAND]; `story_config` → a GitHub issue with the diagnosis and an exact `/tines-build-story` prompt; when the kind is on the auto-PR allow-list also `repository_dispatch` (`tines-fix-proposal`) → **`propose-fix.yml`** → `/tines-propose-fix` → PR labelled `ops-proposal` → lint, review, human merge, `ship.yml`, human approval in Tines; `disable_action` → Slack approval (two approvers in prod) → the apply sub-story dispatches `rollback.yml` with `emergency: true`, whose break-glass job (two GitHub reviewers, a line in `policies/break-glass-log.md`) calls `POST /api/v1/stories/{id}/disable` — nothing in the tenant calls it directly.
7. **Credits:** at 80 % post credits by story and team with the costliest agents (`GET /api/v1/ai_usage?group_by=action`); at 95 % propose disabling the costliest agent or routing it to a custom provider (`credit_action`: two different approvers, landed only as a draft + change request, never a live write); at 100 % the platform stops the story, so 80 % is the actionable alert. Every agent run writes `meta.credits_used`, tokens and model to `ops_findings`; the daily sweep writes `ops_credit_ledger`.
8. **Mode 4 — the same questions from outside:** `stories/ops-tools-server/` exposes `ops_get_*` (Tool hints Read only) and `request_alert_rule` / `request_disable` at `https://<your-tenant>.tines.com/mcp/<mcp-path>` behind a team-scoped Tines API key. The on-call person connects Claude Desktop, Claude Code or Cursor to it (`{"mcpServers":{"ops-tools":{"url":"https://<your-tenant>.tines.com/mcp/<mcp-path>","headers":{"Authorization":"Bearer <api-key>"}}}}`) and asks "why is `[SEC] 01` failing"; a request tool posts to the same approval channel. The sweep's agent may attach this server as its **one** MCP connection (Mode 3 → Mode 4) instead of the five Send to Story tools once stable; never both.
9. **Monday branch:** compliance digest (coverage, credits per team vs `policies/cost-ceilings.yml`, top failing actions, dead-letter depth, pending change requests via `GET …/change_request/view`, MCP activity count from `GET /api/v1/audit_logs` — operation name VERIFY, drift PRs) to Slack and a Dashboard over Records. Release the lock on the last action and on every failure branch; the sweep's own watchdog (1,800 s) pages the DL if it goes silent.

### 4.5 Roll back

IDE features: `/tines-rollback` (prepares the PR); `rollback.yml` with GitHub environments `production` and `break-glass`.

1. If production is misbehaving **now**: a human runs `rollback.yml` with `emergency: true` → the `break-glass` job (two reviewers) calls `POST /api/v1/stories/{id}/disable` (bypasses change control by design; expect a burst of failure notifications, the router dedupes; safe-disable order: entry or schedule action first where possible) and posts to the ops channel.
2. Pick the last good export: **`/tines-rollback <slug> <sha|previous>`** shows `git log --oneline -- stories/<slug>/story.json` and `./scripts/tines versions-list` (metadata only; no export-of-a-version endpoint found — VERIFY — so the git ref is the source), `git revert`s the offending commit(s) on `rollback/<slug>/<sha>` and opens the PR so `main` equals what will be live; lint and review run as usual.
3. `rollback.yml` job `rollback` (environment `production`): `POST /versions` (pre-rollback point) → `POST /api/v1/stories/import` with the ref's `story.json`, `mode: versionReplace`, `draft_name: rollback-<target>` → recipients and `monitor_failures` on the draft → `POST /change_request` titled `ROLLBACK <slug> to <target>` with the reason and incident link → `cr-view` for the approver.
4. The approver approves in Tines and pushes (or `promote.yml` on APPROVED). If promotion cannot wait: the same break-glass job, and only it, runs `BREAK_GLASS=1 ./scripts/tines cr-promote … --bypass-approval --reason` (`bypass_approval: true`, `bypass_approval_reason`, STORY_MANAGE), appends `policies/break-glass-log.md` and commits it in the same run.
5. Re-enable the story (`POST /disable` toggles); confirm with `./scripts/tines live-activity` and the next sweep; `drift.yml` proves prod equals `main` that night.
6. Record the incident in `stories/<slug>/README.md`; if the monitor proposed the rollback, mark the proposal `applied` in `ops_alert_proposals`. UI alternative: restore a story version from the version bar [BY HAND].

---

## 5. The agentic monitoring story

This section is copied verbatim into `stories/ops-story-health-monitor/DESIGN.md`.

### 5.1 Name, place, mode

`[OPS] 10 · Monitor story health and credits` (slug `ops-story-health-monitor`), with `[OPS] 01 · Route monitoring alerts` (`ops-error-router`) as its intake and `[OPS] 20 · Ops tools (MCP server)` (`ops-tools-server`) as its external face. All three are built in the **dev team** and shipped to the **prod team**, like every other story (amended: `stories/_manifest.yaml` maps the `ops-*` slugs to the same `dev` and `prod` environments, so `resolve_target`, `/tines-build-story` and `ship.yml` target those teams; a separate ops team would need its own manifest environment and key, which is not built). They are owned by the ops role (`owner: ops`, the `[OPS]` prefix), never personal space (the AI Agent action is unavailable there), run **LIVE** (monitoring is not available in TEST mode), have change control on, are `locked: true` in prod, and are listed in `policies/never-touch.yml` so no hook, skill or pipeline writes to them outside their own change requests. Their own recipients point at the email DL and a second Slack channel so the monitor is monitored.

**Mode badge: Mode 3** — one AI Agent action in **Task mode** whose tools are Tines tools (Send to Story sub-stories). No external MCP connection is attached by default; the only MCP connection it may ever hold is the repo's own Mode 4 `ops-tools-server`, as a single tool, and never alongside the Send to Story set.

### 5.2 Trigger

Three entries into one story:
1. **Schedule** — `{"cron": "*/15 * * * *"}` (the 15-minute sweep) and a second schedule action at `06:00` tenant time (the daily credits/coverage/baseline sweep, `{"cron": "0 6 * * *", "timezone": "<tenant tz>"}`). Each schedule action carries `monitor_no_events_emitted: 1800` so a dead monitor is itself an alert.
2. **Send to Story** from the router — any failure notification with severity ≥ medium or ≥ 3 occurrences in a window; the router also forwards the tenant AI credit usage alert, event-limit alert and change-control webhooks it receives.
3. **Webhook** — Slack interactivity callbacks for the approval buttons (`JSON_PARSE(webhook.body.payload)` → `actions[0].action_id`, `user.id`, `message.ts`, `channel.id`).

First action after any entry: a **Trigger** on `ops_limits.enabled == true` (the kill switch). Second: the **compare-and-swap lock** — `POST /api/v1/global_resources/<ops_lock>/replace {key: "lock", value: "<<STORY_RUN_GUID()>>", if_value: "free"}`; a 422 (already running) is excluded from `log_error_on_status` and branched on in a Trigger to exit; a lock older than `stale_lock_minutes` is treated as free. Released with `if_value` = the run's GUID on the last action and on every failure branch.

### 5.3 Inputs

All reads use a **Viewer-role team API key** stored as a Text credential (`tines_api_readonly`) with `allowed_hosts` = the tenant host and Workbench access off (read-only by role — VERIFY).

| Input | Endpoint / source | What it gives |
|---|---|---|
| **Story runs** | `GET /api/v1/stories/{id}/runs?since=` · `GET /api/v1/stories/{id}/runs/{guid}/summary` · `GET /api/v1/stories/{id}/runs/{guid}` | `guid`, `duration`, `start_time`, `end_time`, `action_count`, `event_count` — **no status field**, so failure is derived |
| **Action events and logs** | `GET /api/v1/actions/{id}/logs?level=4` · `GET /api/v1/actions/{id}?include_live_activity=true` · `GET /api/v1/actions/{id}/events?per_page=` · `GET /api/v1/events?story_id=&since=&per_page=500` | error logs (`id`, `message`, `created_at`, `inbound_event`), `last_error_log_at`, `pending_action_runs_count`, `monitor_*` flags, event cadence for baselines |
| **Live activity** | `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true&per_page=100` · `GET /api/v1/stories/{id}?include_live_activity=true` | `not_working_actions_count`, `pending_action_runs_count`, `monitor_failures`, `actions_with_monitoring`, `recipients`, `change_control_enabled`, `locked`, `mode` |
| **Credit usage** | `GET /api/v1/ai_usage?relative_date=today&group_by=story` · `…&group_by=team` · `…&story_id=&group_by=action` · `…&start_date=&end_date=&group_by=day` | `credits_used`, `billed_cost`, input/output/cached tokens, `usage_count` |
| **Monitoring notifications** | the router's Webhook (payload shape VERIFY — captured once) | story, action, action type, failure/no-events, timestamps |
| **Audit** | `GET /api/v1/audit_logs?after=&per_page=` (client-side `story_id` filter; `operation_name[]` once the MCP operation name is known — VERIFY) | `user_email`, `operation_name`, `source`, `request_user_agent` for the digest and drift attribution |
| **Repo state** | `ops_baselines`, `ops_alerts`, `ops_alert_proposals`, `ops_dead_letter` Records; `ops_limits`, `ops_routing`, `ops_responders` Resources | thresholds, budgets, kill switch, who may approve, what was already proposed or rejected |

### 5.4 The AI Agent action's tools

One AI Agent action, **`triage`**, Task mode, temperature 0.2, timeout raised above the 30 s default, retries low, system instructions from `agent/system-instructions.md`, skills `story-health-triage` and `credit-budget-analyst` attached, output schema from `agent/output-schema.json`. Tools are **five read-only Send to Story sub-stories**, added one at a time, each with a **Timeout Duration**, each ending on a `result` Event Transform returning 3–5 fields, each returning a structured error on its failure branch, each description 3–4 sentences with one example argument:

| Tool (sub-story) | Wraps | Returns |
|---|---|---|
| `ops_get_error_logs(action_id, limit)` | `GET /api/v1/actions/{id}/logs?level=4` | `{count, last_at, categories[], log_ids[], sample_messages[]}` — messages secret-scrubbed in the sub-story; the Mode 4 copy fixes `include_messages: false` and returns `{count, last_at, categories[], log_ids[]}` only (third-party free text never feeds another client's model) |
| `ops_get_story_export(story_id)` | `GET /api/v1/stories/{id}/export?clear_recipients=true` | `{action_count, http_actions_without_retry[], agents_without_schema[], schedules[]}` — configuration only, never values |
| `ops_get_live_activity(story_id)` | `GET /api/v1/stories/{id}?include_live_activity=true` | `{not_working_actions_count, pending_action_runs_count, monitor_failures, recipients_count}` |
| `ops_get_recent_runs(story_id, since)` | `GET /api/v1/stories/{id}/runs?since=` + `/summary` | `{runs, median_duration_s, max_duration_s, last_start}` |
| `ops_get_ai_usage(story_id, relative_date)` | `GET /api/v1/ai_usage?story_id=&group_by=action` | `{credits_used, billed_cost, top_actions[]}` |

Rejected proposals from `ops_alert_proposals` are injected into the prompt **by the story**, not as a sixth tool, so the agent does not repeat them. **No write tool exists on this agent.** The same five sub-stories are what `ops-tools-server` exposes in Mode 4 (§5.9). A second, tool-less AI Agent action, **`critic`** (fast model), runs only for `high`/`critical`: it re-reads `evidence[]` and may only confirm or downgrade; disagreement sets `needs_human`.

### 5.5 Output schema (validated by the action; the Trigger after it branches only on these fields)

```json
{
  "story_id": "integer",
  "story_name": "string",
  "severity": "low | medium | high | critical",
  "category": "auth | rate_limit | upstream_5xx | silent_source | schema_failure | credit_burn | overlap | coverage_gap | lock_stale | mcp_health | unknown",
  "root_cause_hypothesis": "string",
  "evidence": [ { "source": "string", "ref": "string", "excerpt": "string" } ],
  "recommended_fix": "string",
  "proposed_change": { "kind": "none | story_config | alert_rule | disable_action | credit_action", "target": "string", "summary": "string" },
  "alert_rule_proposal": {
    "type": "monitor_failures | monitor_no_events_emitted | monitor_all_events | recipient | token_threshold | credit_budget | none",
    "story_id": "integer", "action_id": "integer | null", "value": "string", "rationale": "string"
  },
  "needs_human": "boolean",
  "confidence": "number"
}
```

### 5.6 Guards (story elements, never prompt text)

- **Kill switch** `ops_limits.enabled` and the **CAS lock** on `ops_lock` (§5.2).
- **Deterministic pre-filter before any AI** (an Event Transform): error count vs `error_threshold_per_window`; `not_working_actions_count > 0`; `pending_action_runs_count` > baseline × 3; `monitor_failures: false` or empty recipients (coverage gap); credits today ≥ 80 % or 95 % of `credit_budget_daily` (per story or default); run duration ≥ `overlap_ratio` × schedule interval; no events beyond 2× interval on a scheduled story; a lock older than `stale_lock_minutes`; for Mode 4 stories no `initialize` events over a window or tools nearing the 30-second ceiling. **Only anomalous stories reach the agent; a healthy sweep costs zero credits.** Info-level findings are logged, never sent to the model.
- **Rate and run caps:** agent runs today < `agent_runs_per_day_max` (a Records count) and the ops team's own credits below `credit_alert_pct[1]` — both Triggers; `max_proposals_per_day` from `ops_limits`.
- **Dedupe** per story+action+window in the router (Deduplicate mode or an `ops_alerts` check); one event per notification, never per log line.
- **No write credential on the agent.** `tines_api_ops` (Editor-role team key) lives only inside the apply sub-story, behind a verified approval. The sweep story itself holds only `tines_api_readonly`, the lock-only `tines_api_ops_lock` (the `ops_lock` compare-and-swap, nothing else) and `tines_api_dev_autofix` (the dev coverage auto-fix — a real key only in the dev team, so it fails closed in prod even if `ops_limits` is mis-set; the committed example defaults to `environment: prod`, `auto_apply_in_dev: false`).
- **Approvals:** the Slack request signature and a 5-minute timestamp window are verified before any callback is parsed (credential `slack_signing_secret`); then every button click is verified against `ops_responders` (the button is UI, the Resource is the control); two approvers for `disable` and `credit_action` in prod; proposals expire.
- **Never-touch:** a Trigger checks the target story against the never-touch mirror before any proposal that would change it; `ops-*` stories can only be *reported on*.
- **Schema, not sentiment:** Triggers fire on `severity`, `proposed_change.kind`, `needs_human` — never on confidence or prose. An output-schema validation failure → Record + human.
- **Expected non-2xx** (the lock's 422, an empty lookup's 404) excluded from `log_error_on_status`.
- **Tool outputs are data:** error logs and webhook payloads can contain attacker-influenced strings; the agent can only propose, the critic re-checks, and every path to production passes lint, an independent review, a human merge and a human change-request approval.
- **Token alerts** on both agents' Status tabs (Notify at `daily_tokens_notify`, Disable action at `daily_tokens_disable`); event retention raised on all three ops stories; the sweep's own watchdog at 1,800 s → the DL.

### 5.7 Actions — what the story does with a finding

| `proposed_change.kind` / signal | What happens | Endpoint(s) | Human? |
|---|---|---|---|
| `none` (record_only) | `ops_findings` Record with `meta.credits_used`, tokens, model; thread reply | Records API | no |
| **coverage gap in dev** | recipients added and `monitor_failures` set immediately (`environment: dev` and `auto_apply_in_dev: true` in the dev team's `ops_limits`; credential `tines_api_dev_autofix`, a real key only in the dev team) | `POST /stories/{id}/recipients`, `PUT /stories/{id}` | no |
| **coverage gap in prod** / `alert_rule` | `ops_alert_proposals` (pending) → Slack Block Kit approval → on approve, the apply sub-story: `recipient` → `POST /recipients` (live vs draft semantics VERIFY); `monitor_*` → `PUT /actions/{id}` or `PUT /stories/{id}` with `draft_id` → `POST /change_request` `monitor-<finding_id>` for the same approver; `token_threshold` / `credit_budget` → no API → Case task (if Cases is entitled) or Record + thread [BY HAND]; status → `applied` | as listed | **yes** (verified approver) |
| **open a Case or ticket** | severity ≥ high, or any `credit_burn` at warn: a Case with priority so SLA timers run (if Cases is entitled; Case notifications allow up to 5 webhooks per team), else a ticket through an `open_ticket` sub-story, else a GitHub issue | Cases / ticket API / GitHub | no (creation); yes (resolution) |
| **Slack post** | every finding ≥ medium: thread per story per day, channel from `ops_routing`; approvals as Block Kit buttons; the credit digest at 80 % | Slack API (credential `slack_bot`) | no |
| `story_config` | GitHub issue with diagnosis, `evidence[]` and an exact `/tines-build-story` prompt; if the kind is on the auto-PR allow-list (add `retry_on_status`/`emit_failure_event`, change a schedule, adjust a `DEFAULT()`), also `repository_dispatch` `tines-fix-proposal` → `propose-fix.yml` → `/tines-propose-fix` → PR `ops-proposal` | GitHub (credential `github_dispatch`, `allowed_hosts` `api.github.com`) | **yes** (merge + change-request approval) |
| `disable_action` | Slack approval (two approvers in prod) → the apply sub-story dispatches `rollback.yml` with `emergency: true`: its break-glass job (two GitHub reviewers, neither the dispatcher) disables the named story only, never a never-touch entry, and appends `policies/break-glass-log.md` in the same run; safe-disable note in the thread | `POST /api/v1/stories/{id}/disable` (inside `rollback.yml` only) | **yes** (two approvers + two break-glass reviewers) |
| `credit_action` | at 80 %: summary by team/story with the costliest agents; at 95 %: proposal to pause the costliest agent or route it to a custom provider — two different approvers (`ops_responders.two_required_for`), landed by the apply sub-story only as a draft + change request, never a live write; the platform's 100 % stop is the backstop | `GET /api/v1/ai_usage` | **yes** (two approvers + change-request approval) |

### 5.8 Alert-setting behaviour (agentic, human-approved)

The story learns each story's normal from data rather than fixed numbers, and the agent fills `alert_rule_proposal`; it never sets a threshold itself:
- **Watchdog** `monitor_no_events_emitted` = `watchdog_multiplier` (2) × the p95 inter-event interval of the entry or scheduled action, from `GET /api/v1/events?story_id=` and the runs list, stored daily in `ops_baselines`.
- **Per-story credit budget** = p95 of the last 7 days' `credits_used` × 1.5, proposed into `ops_limits.credit_budget_daily.per_story`.
- **Error threshold** = max(3, 3 × median level-4 logs per window).
- **Recipient proposals** whenever a new published story appears without the router.
- Every proposal carries `rationale` and the evidence rows; rejected proposals record a reason and are fed back next run; approved ones are applied deterministically by the apply sub-story (into a draft + change request) and mirrored into `story.meta.yaml` by the next `drift.yml` PR so the repo stays the truth. In dev (the dev team's `ops_limits` sets `environment: dev` and `auto_apply_in_dev: true`; the committed example defaults to `prod` / `false`) recipient and monitor-flag proposals apply without a click so builders see the behaviour, through `tines_api_dev_autofix`, which holds a real key only in the dev team; in prod nothing applies without a verified approver.

### 5.9 The Mode 4 face (`ops-tools-server`)

The five read sub-stories plus `request_alert_rule` and `request_disable` are exposed by one MCP server action. Lookups carry **Tool hints: Read only**; request tools keep the default hints (Destructive on). Hints are MCP annotations a client may use — whether a client prompts on them is VERIFY per client and never a control; the control is that the request tools only post an approval through `[OPS] 17` and nothing changes until a verified approver approves. Access control **With a Tines API Key**, members of the ops team; the caller's email (`META.headers.email`) is written into `ops_alert_proposals.requester`. This is how a human — or the builder's editor — asks the monitor's questions and requests the monitor's actions without a second implementation of the guards: the request tools run the same sub-stories that post the same approvals to the same channel. One flow; no AI credits; 30-second tool ceiling (the lookups return in well under that; anything slower returns `{status: started, id}` and a status tool).

### 5.10 What needs a human — the boundary

**The story may do alone:** read anything with the read-only key; write Records; post threads and digests; add recipients and monitor flags **in dev**; open GitHub issues; open Cases or tickets; fire `repository_dispatch` (which only ever yields a PR).
**A named human must:** approve any alert rule applied to prod (verified against `ops_responders`); approve any disable (two people in prod, then two break-glass reviewers in GitHub) and any `credit_action` pause or reroute (two people, then the change request); merge any PR; approve any change request in Tines; set token thresholds on the Status tab, per-team credit allocation and credit-usage alert thresholds in Admin → AI (no API); create Record types; answer `needs_human` findings (severity high/critical, confidence < 0.6, category unknown, critic disagreement, schema validation failure).

### 5.11 Weekly digest (Monday branch)

Monitoring coverage (stories with `monitor_failures: false` / empty recipients / `actions_with_monitoring: 0`), credits per team and per story vs `policies/cost-ceilings.yml` (from `ops_credit_ledger`), credits per completed finding, top failing actions, dead-letter depth and age, pending change requests (`GET …/change_request/view` per production story), MCP activity count from `GET /api/v1/audit_logs` (operation name VERIFY), drift PRs opened — to Slack and to Records for a Dashboard. Audit logs themselves reach the SIEM through the native S3 export every 15 minutes, not through a story.

### 5.12 Flows and cost

Router 1 + sweep 1 + Mode 4 server 1 + five read sub-stories + apply sub-story ≈ **9 flows** (whether Send to Story sub-stories used as tools count as flows is VERIFY with the account team); consolidate the read tools into **Custom tools (Groups)** on the agent once stable to reduce the count. Credits are spent only on anomalous stories and only by `triage` (smart model, tools attached) and `critic` (fast model, no tools); a healthy tenant costs the API calls and nothing else.

---

## 6. Cost controls

Each control names the mechanism and where it is enforced. "Tenant" means a Tines setting; "repo" a committed file; "editor" a Claude Code / Cursor feature; "CI" a workflow.

### 6.1 AI credits (tenant + story)
- **The build loop is off the credit meter.** Mode 2 runs on the editor's own model plan; no Tines AI credits are listed for the Tines Stories MCP server (whether its research and listing helpers consume credits is VERIFY). Workbench for Storyboard is the credit-spending alternative and is chosen deliberately, not by default.
- **Budgets are files.** `policies/cost-ceilings.yml` is the single source; `drift.yml`'s budget job (`./scripts/tines ai-usage`) and the sweep (`ops_limits` Resource, mirrored by hand) read the same numbers; `lint.yml` fails a PR that adds an AI Agent action without a budget line.
- **Visibility:** `GET /api/v1/ai_usage` daily per story, team and action; tenant AI credit usage alerts (tenant / unallocated / per team; webhook to the router; defaults 80/100 VERIFY; no API — set by hand); per-team AI credit allocation in Admin → AI (no API — by hand, mirrored in policy); `meta.credits_used`, tokens and model written to `ops_findings` per run so credits per completed finding can be scored.
- **The sweep pays only for anomalies:** the deterministic pre-filter decides which stories reach the agent; a healthy sweep spends zero credits; `agent_runs_per_day_max` and `agent_credits_per_run_max` are Triggers.
- **Provider check:** an agent on a custom provider bypasses credits but still bills externally (`billed_cost`); the ledger records the model per run so the two are never confused.

### 6.2 Token alerts (tenant, per agent)
- Every AI Agent action carries a **token-usage alert on the Status tab**: **Notify** (story recipients) at `daily_tokens_notify`, **Disable action** at `daily_tokens_disable` (per Daily/Weekly/Monthly/All-time). Set by hand; recorded in `story.meta.yaml: ai.agents[].token_alert`; the reviewer refuses a story whose meta lacks it.
- Tool output truncation stays on (50,000 tokens); tools return 3–5 fields, never raw data, so intermediate data never passes through the model.

### 6.3 Model choice
- **Task mode uses the cheaper model until a tool is added**, then the smart model — so `critic` (no tools) is cheap by construction, and `triage` is the only smart-model call, run only on anomalies.
- The reviewer subagent uses `model: inherit` in the committed file; a smaller model is acceptable for review and chosen per tenant. No model ids are hard-coded in this spec.
- A custom provider (Admin → AI) is a deliberate choice for a named agent, never a tenant default set by accident — the sweep checks which provider each agent uses.

### 6.4 Tool counts and definitions
- One tool first, at most five per agent; tools added one at a time; split jobs across agents rather than growing a list; a house rule of 3–8 tools per Mode 4 server.
- **Keep each agent's enabled tool set fixed** (changing any tool definition invalidates the prompt cache on a custom provider); never rename or reorder tools on the Mode 4 server while consumers are mid-session.
- Fan-out happens inside a Send to Story sub-story that returns one summary; the loop lives in the story, not in the model.

### 6.5 The sandbox team (dev)
- Every build happens in the **dev team** with test-mode credentials and resources on change-controlled stories; production credentials never spend during a build; `ship.yml` touches prod once per merge.
- Free-tier vendor limits are paced (throttle mode) or cached (`ioc_cache` Record with a TTL) so a rehearsal never burns a quota.
- Flows are budgeted: the ops trio ≈ 9 flows (sub-story counting VERIFY); Workbench-only stories do not count; sub-stories are reused, never duplicated.

### 6.6 IDE-side limits (editor + CI)
- **Resident context stays small:** `AGENTS.md` under 200 lines; skills cost ~100 tokens each until invoked; references load on demand; the `/mcp` server is declared only on the `tines-builder` subagent so its dozens of authoring tool descriptions never enter the main conversation; Claude Code additionally defers MCP tool schemas by default and warns at 10,000 tokens per MCP result.
- **CI is bounded:** `--max-turns` on every `claude-code-action` job (review 10, propose-fix 15), `timeout-minutes` on every job, a concurrency group per PR with cancel-in-progress, path filters so review runs only when `stories/**`, `tines-skills/**` or `policies/**` change, `lint.yml` (no model) runs first so obvious failures never reach the model, and **no MCP in CI**.
- **Headless runs** use `--bare` or `--setting-sources user`, explicit `--allowedTools`, `--json-schema` output, and the propose-fix path is capped by `max_proposals_per_day` in `ops_limits`.
- **Events and rate limits:** one event per notification, never per log line; dedupe in the router; retention raised only on the ops stories; scripts and `drift.yml` respect API limits (5,000/min default, actions 100/min, audit_logs 1,000/min, records 400/min) with backoff on 429; the 80 % event-limit alert is the actionable one because at 100 % Tines stops the story.

---

## 7. Security controls

### 7.1 OAuth on `/mcp`
- The Tines Stories MCP server is **OAuth only**, inherits the prompting user's Tines permissions and grants nothing more; every tool use is recorded in the audit logs as **MCP activity**; the repo adds a local mirror (`.tines/mcp-activity.jsonl`) via `guard-mcp.sh`, and the reviewer reads the audit rows for the story since the session started.
- **No committed MCP config:** `.mcp.json` and `.cursor/mcp.json` are gitignored and shipped only as `.example` files; the entry lives in **user scope** because `claude -p` connects repository servers and runs repository hooks without a trust prompt; headless runs use `--bare` or `--setting-sources user` and fail on `mcp_server_errors`.
- The Mode 4 server uses **With a Tines API Key** scoped to the ops team (OAuth as a Mode 4 access mode is listed both as supported and unsupported in the docs — VERIFY before relying on it).

### 7.2 No secrets in the repo
- Exports carry no credentials, resources or events by design; export uses `clear_recipients=true`; `block-secrets.sh` refuses secret-looking writes; `lint.yml` and gitleaks scan every PR; `lint-story.sh` fails on any options value matching token, `xox[bp]-`, `Bearer `, `sk-`, `AKIA` or email patterns; credentials and resources are referenced by name and validated against `story.meta.yaml`.
- The router webhook URL carries a secret → it lives in `.env` / GitHub environment secrets, never in the manifest (`${OPS_ROUTER_URL}` is resolved at run time).
- The credentials API never returns secret values; in-tenant credentials carry `allowed_hosts`, `expires_at` with expiry notifications, and Workbench access **off** for pipeline keys; Terraform uses `value_wo`; MCP connections are re-created after import, never exported.
- `Read(./.env)`, `Read(./.env.*)`, `Read(./.mcp.json)`, `Read(./.cursor/mcp.json)` are denied to the editor.

### 7.3 Team-scoped API keys for CI (and everywhere else)
- Identity per job (`policies/POLICY.md`): builders act as themselves through OAuth; **CI-prod** holds a team-scoped key (Editor role) in the prod team that can import, tag versions, set recipients, open change requests and promote an APPROVED request — and cannot approve; **CI-read** and the monitor's lookups hold a **Viewer-role** team key (read-only by role — VERIFY); **monitor-apply** (Editor) lives only inside the apply sub-story behind a verified approval; **no approver key exists in CI**, so approval can only happen in Tines by a person.
- Keys are created only by `API_KEY_CREATE` holders, stored as GitHub **environment** secrets (`production`, `break-glass`), rotated quarterly, never personal; an underprivileged key gets 404, which the dispatcher names as such.

### 7.4 Hooks (deterministic enforcement in the editor)
- `guard-mcp.sh` (PreToolUse, exit 2 beats allow): refuses any `/mcp` call while `TINES_ENV=prod`; blocks any call whose input references a production or never-touch story id (input-based — independent of unpublished tool names); blocks destructive-looking names (VERIFY names, then replace the regex with an explicit deny list); mirrors every call for audit.
- `block-secrets.sh` (PreToolUse `Write|Edit`): no secret-looking write lands on disk.
- `lint-on-write.sh` (PostToolUse): a turn that leaves a `story.json` unlintable is blocked with the findings.
- `stop-gate.sh` (Stop): the turn cannot end with a failing lint or an export older than the last MCP call.
- Cursor's IDE agent does not run these hooks; in Cursor the enforcement is CI and Tines change control (stated in `.cursor/rules/story-json.mdc`).

### 7.5 Change control (the deterministic gate)
- Tenant policies **Enable by default** and **Require approval for all changes** (admins and owners included; emergency bypass audited); story requirements (name, description, owners, tags, event retention) set to required.
- Production changes only via **import → named draft → change request → a named approver**; the pipeline never calls promote on a PENDING request and never sets `bypass_approval`; `cr-promote` is denied in the IDE; `bypass_approval` exists only in `rollback.yml`'s `break-glass` job (two reviewers, mandatory reason, log line in `policies/break-glass-log.md` committed in the same run).
- Every promoted change carries the commit SHA in the change-request description and a story version; `drift.yml` proves prod equals `main` nightly and attributes any deviation via the audit logs; change-control team webhooks post approvals into the ops thread.
- `POST /disable` is the only bypass and is the kill switch; reserved for break-glass; safe-disable order documented.

### 7.6 Least-privilege tool lists
- The monitoring agent holds **no write credential** and five read-only tools; request tools instead of write tools everywhere (`tools_are_requests` lint rule: any `block|delete|isolate|disable` tool name must start with `request_`).
- Mode 4: Tool hints Read only on every lookup; access control team-scoped; per-tool descriptions state what the tool does *not* do; the server never receives the tools' credentials.
- Workbench: per-preset tool lists; the credential Workbench-access toggle disconnects template and MCP tools live; `Require confirmation to run` on stories exposed to Workbench.
- CI: `--allowedTools` explicit on every headless job; `Edit(stories/**)` is the only write the propose-fix instance has; job `permissions` minimal; fork PRs receive no secrets; `allowed_bots` empty.
- Editor: subagents carry their own `tools`/`disallowedTools`; `tines-reviewer` cannot Write or Edit and has no MCP.

### 7.7 Review in fresh context
- `/tines-review` runs with `context: fork` on `tines-reviewer` — never the conversation that built the story; the skill refuses if the session built the story.
- `review.yml` runs a separate Claude Code instance with no MCP, no tenant credentials and a different prompt; CODEOWNERS adds a person; branch protection forbids self-merge.
- Inside Tines, `critic` re-reads `triage`'s evidence for high/critical before anything leaves the tenant, and a person approves anything that changes production.
- **Prompt-injection posture:** error logs, webhook payloads and story exports the agents read are attacker-influenceable data; the agents can only propose; every path to production passes lint, an independent review, a human merge and a human change-request approval.

### 7.8 Data policy, named
- Mode 2 runs on the editor's provider, so what the editor sends is governed by the organisation's editor data policy, not Tines' foundation guarantees; the docs say so; story exports contain configuration only.
- Audit logs export to S3 every 15 minutes for the SIEM (not through a story); the AI overview page lists every MCP server in the tenant; the weekly digest counts MCP activity.

---

## 8. Pros and cons (honest)

### Pros
1. **Stories get what code has had for decades:** a diff on every change, an independent review, a merge gate, a rollback point, and a nightly drift check — the repo is the truth and the tenant is a deployment target.
2. **Speed with control:** one afternoon from idea to a change request, because the build skill carries the procedure and the prompt pack, the hook lints every write, the stop gate keeps the export fresh, and the only manual steps are the ones `/mcp` cannot do — named explicitly by the skill.
3. **Cost is a design property:** the build loop runs on the editor's plan with no Tines credits listed for the Tines Stories MCP server; runtime AI is bounded by schemas, tool caps, token alerts, a daily run cap, a kill switch and file-based budgets; the sweep spends nothing on a healthy tenant.
4. **Security posture is inherited, not invented:** OAuth-only authoring that carries the builder's own permissions and is audit-logged as MCP activity; credentials that never leave Tines and never appear in exports; team-scoped keys that cannot approve; change control with "Require approval for all changes" as the deterministic gate; hooks that enforce rather than request.
5. **Every control is a file a security reviewer can read and diff:** permissions, hooks, budgets, never-touch list, lint rules, CODEOWNERS, workflow gates and the governance contract.
6. **Two independent gates on every production change** (a GitHub environment with reviewers and a Tines change request approved by a person), joined by the commit SHA and a story version, so audit can reconstruct who changed what, when and why.
7. **One skills tree serves Cursor and Claude Code,** and the tenant-side Agent Skills live in the same repo with a CRUD API behind them, so "how we build" and "how our agents behave" are reviewed together and renames are safe.
8. **The monitoring story turns Tines' own recommendation** (send monitoring alerts to a Tines story) into an evidence-based proposer whose alert thresholds come from baseline data and whose only outputs are requests — a recipient, a rule, a Case, a Slack thread, a PR — that a human approves.
9. **All three modes named in the brief are exercised** without a second implementation of the guards: Mode 2 authors, Mode 3 diagnoses, Mode 4 exposes the same sub-stories to humans and editors.
10. **Bulk, consistent edits** across many stories become an editor task with a reviewable diff instead of a clicking session; the dispatcher and the manifest make the same change repeatable per environment.
11. **Vendor-neutral foundations:** plain JSON exports, the public Tines API, an optional Terraform path, and Agent Skills as an open standard — nothing depends on unpublished behaviour except where marked VERIFY.
12. **Simplest-first is enforced,** not just recommended: the decision doc, the review checklist and the `tools_are_requests` lint rule keep templates before agents, Send to Story before MCP, and no write tool without an approval path.

### Cons
1. **The Tines Stories MCP server's tool names and count are unpublished,** so the hook guard is a regex plus an input-based ID check, and skills cannot reference tools precisely until the tenant's client lists them.
2. **`/mcp` is OAuth only:** no headless authoring, so CI can lint, review, import and open change requests but every tenant edit stays interactive; whether a headless session can reuse an interactive OAuth session is unknown on both sides.
3. **How `/mcp` edits interact with change control and drafts is unpublished;** dev-team edits may be live in dev, and the policy is enabled on faith until verified.
4. **Story exports are not designed for hand editing** (index-based links, no published schema for option keys); import matches by name, embedded sub-stories are not imported, MCP connections are dropped on import, and credentials and resources must pre-exist by name in every environment — the lint rules for retry, monitor and output-schema keys need a real export before they are exact.
5. **Two teams plus the ops trio cost licences and roughly nine flows;** some tenants will not have the AI Agent action, Cases or change control on their plan; Community tenants cannot run the monitoring agent at all.
6. **No API exists for per-team credit allocation, credit-usage alert thresholds or AI Agent token thresholds,** so those stay by hand, can drift from the policy file, and the "agentic" part can only propose them.
7. **Cursor picks up `.claude/skills/` as a legacy path and does not run Claude Code hooks in the IDE agent,** so enforcement in Cursor rests on CI and Tines rather than the editor.
8. **There is no run-status field,** so failure detection is derived from counts and error logs; the monitoring webhook payload is undocumented and must be captured by hand once; a handled failure-path error may also fire the notification (double signals until verified).
9. **LLM-edited JSON proposals can break links;** lint and review mitigate it, but the safer default is an issue with a prompt, which adds a human step.
10. **Process overhead for tiny changes** (branch, PR, two checks, CODEOWNERS, merge, change request, approval) and reviewers who must read story JSON; audit noise grows with MCP activity, drift PRs and proposal PRs. Small teams may find the ceremony heavy for low-risk stories — use `tier: internal` and a lighter path for those.
11. **The Terraform provider is 0.x** (breaking changes in minors), TEXT credentials only, no skills resource, behaviour on change-controlled stories unverified — optional, not primary.
12. **Mode 2 runs on the editor's provider,** so the organisation's editor data policy, not Tines' foundation guarantees, governs what the model sees; some organisations will need that reviewed before the first build.
13. **The monitor is itself a story that can fail** and adds its own failure modes (double signals, notification storms, a stale lock) that the router and the watchdog must catch.

---

## 9. Conventions every builder must follow

1. **Placeholders, never real values.** `<your-tenant>` for the host prefix; `<org>` for GitHub owners; `0` for ids in committed manifests and meta until the first ship; `*.example.invalid` addresses; documentation-range IPs (`203.0.113.0/24`) in tests. Real ids, hosts, channels and addresses are set in the tenant or in secrets and never committed.
2. **VERIFY markers.** Any claim not confirmed in the research carries `VERIFY` inline and an entry in `docs/VERIFY.md`. Nothing marked VERIFY appears as a headline claim, in a README's opening paragraph, or on a slide. Both sides of any `CONFLICT` are kept. `[BY HAND]` marks steps the editor cannot do through `/mcp`.
3. **No customer names, people, codenames or tenant hostnames** anywhere in the scaffold — not in READMEs, samples, comments, commit messages or test data. Research is cited generically ("failure-alerting research, September 2026"). Owner lines carry a role, never a name.
4. **"Mode" is the only word for the four MCP surfaces** (the older intake-surface metaphor is retired). The four MCP surfaces are Mode 1 (Workbench calling MCP tools), Mode 2 (the Tines Stories MCP server at `/mcp`), Mode 3 (the AI Agent action calling tools), Mode 4 (the MCP server action at `/mcp/<mcp-path>`). Every story README and every canvas Note carries a mode badge (or "none").
5. **No invented `/mcp` tool names or endpoints.** Describe the Tines Stories MCP server by its documented capabilities. Reference an MCP tool as `tines:<tool>` only after the tenant's client has listed it and `docs/VERIFY.md` records it. Use only the Tines API endpoints the research lists: an endpoint does not exist for this repo unless it is listed in §3.5 / §4 / §5 or in REPO-DESIGN.md §7–§9.
6. **Product names exactly as Tines writes them:** Tines Stories, the Tines Stories MCP server (also "the Tines MCP server"), MCP server action ("MCP Server" in the template picker), AI Agent action, Task mode, Chat mode, Workbench, Workbench for Storyboard, presets, Send to Story, Custom tools, Tool hints, `+ Add tool`, `+ Option`, Summary tab, Status tab, AI credits, flow, Community Edition, Tines tunnel, Streamable HTTP, Plain HTTP, `META.headers.*`. "Model Context Protocol (MCP)" on first use.
7. **No secrets, ever.** Credentials never leave Tines and never appear in exports; the `/mcp` entry lives in user scope; tokens are never pasted into MCP connections; no personal data in URLs or query strings; `block-secrets.sh` and `lint.yml` are the backstop, not the rule.
8. **Guards live in the story,** not in prompts: Triggers and Resources for kill switches, locks, allow-lists and responders; change control with "Require approval for all changes"; request tools instead of write tools; approvals to a fixed channel with an expiry; escalation on explicit schema fields, never on sentiment or self-reported confidence.
9. **One story at a time,** a plan for anything bigger than a sentence, "Validate" plus a test event at the end, then export, lint, fresh-context review. Never hand-edit `story.json`. One story per branch and PR.
10. **Naming and shape:** `[PREFIX] NN · Verb noun`; sub-stories end in `(sub)` and finish on a `result` Event Transform (3–5 fields) with a structured error on the failure path; a Note on every canvas; HTTP hardening on every request; a watchdog on every scheduled or ingress action; an output schema, a post-agent Trigger, a token alert, a skill and a budget line on every AI Agent action.
11. **Simplest first, visibly:** HTTP Request action or template → Send to Story → AI Agent action with Tines tools → Mode 3 with an MCP connection → Mode 4; Mode 2 for editor-driven building. Never MCP for bulk data movement, sub-second latency or a destructive action without an approval path.
12. **Library story IDs only from the verified list** (this scaffold uses 87626, 1231438; 1324549 may be imported into a Seeds folder for reference only); never demo from the Seeds folder; the dev team is never personal space.
13. **Frontmatter and file formats as documented:** Claude Code `SKILL.md` keys as on the skills page (`allowed-tools` in `.claude/skills/*/SKILL.md` is comma-separated, the Claude Code form in use here — see the §3.3 note; Cursor's parsing of it is VERIFY #4); `.claude/rules/*.md` with `paths:` only; Cursor rules are `.mdc` with `description`/`globs`/`alwaysApply`; settings files are strict JSON; repo YAML is `.yaml`, GitHub workflows `.yml`; Agent Skills names ≤ 64 chars lowercase-hyphen equal to the folder, no "anthropic"/"claude", descriptions ≤ 1024 in third person, bodies under 500 lines.
14. **Plan-gated claims are never quoted without the tenant's plan mapping** (AI Agent action on Business/Enterprise; Cases, Apps, change control, dedicated-tenant limits); free-tier vendor limits are paced or cached; caps you cannot see in-tenant are not stated.
15. **Every README carries a "verify in your tenant before presenting" block,** and every builder updates `docs/VERIFY.md` when a VERIFY item is confirmed, stating what changed in the repo as a result.

---

## 10. VERIFY list

Each item: what we assumed · how to confirm in-tenant · what changes in the repo when confirmed. Nothing here is a headline claim.

| # | Assumed | How to confirm | What changes when confirmed |
|---|---|---|---|
| 1 | `/mcp` tool names and count (observed "dozens") | The tenant's client tool list after `/tines-connect`; record in `docs/VERIFY.md` | `guard-mcp.sh` regex → explicit deny list; skills may reference `tines:<tool>`; confirm `mcp__tines__*` and the matcher `mcp__tines__.*` behave on real names |
| 2 | `/mcp` edits on a change-controlled dev story land as drafts and respect "Require approval for all changes" | Edit a scratch story in the dev team via the editor; inspect drafts and the change-request list | The build skill's step 6 and `docs/02` wording; whether `?draft=` is needed for test events after `/mcp` edits |
| 3 | Claude Code setup: `claude mcp add --transport http … --scope user` + OAuth via `/mcp` or `claude mcp login` | Run it; compare with the snippet at `https://<your-tenant>.tines.com/mcp` | `/tines-connect` steps and `.mcp.json.example` |
| 4 | Cursor accepts (or needs) a `type` key in `mcp.json`; Cursor discovers `.claude/skills/` (legacy path) and parses the comma-separated `allowed-tools` those skills use; the Cursor IDE agent does not run Claude Code hooks | Cursor MCP settings and the skills picker; a deliberate hook trigger in Cursor | `.cursor/mcp.json.example`; a `.cursor/skills` symlink; the `allowed-tools` format of `.claude/skills/*/SKILL.md` (§3.3 note); `.cursor/rules/story-json.mdc` enforcement note |
| 5 | Subagent frontmatter `mcpServers: [tines]` references a user-scope server by name | The sub-agents page and a test run of `tines-builder` | Inline http definition on the subagent if the name form fails |
| 6 | `POST /api/v1/stories/import` response exposes the draft id; behaviour when the draft already exists; credential/resource references survive by name; behaviour when a referenced credential is missing in the target team | Import a scratch export into a change-controlled story with `draft_name`; read the response; repeat with a missing credential | `scripts/tines import-draft` field parsing; `ship.yml` failure handling |
| 7 | `PUT /api/v1/actions/{id}` with `monitor_*` on a change-controlled story requires a draft and a change request; `POST /recipients` without `draft_id` applies to the live story; recipients set on a draft carry to live on promote | Apply each on a scratch story with change control on | The apply sub-story's branches; `ship.yml` step order |
| 8 | Export JSON key names for HTTP retry options, `emit_failure_event`, monitor flags, `keep_events_for`, the AI Agent output schema; `Agents::LLMAgent` is the AI Agent action type in exports; the `{{ .CREDENTIAL.x }}` / `{{ .RESOURCE.y }}` reference syntax | Read one real export (sample-first) | `scripts/lint-story.sh` rule keys, `policies/lint-rules.yml`, the reviewer checklist |
| 9 | Monitoring notification webhook payload shape; AI credit usage alert webhook payload; event-limit alert payload; change-control team webhook payload | Deliberately fail an action in a LIVE scratch story with a test recipient; trigger each alert once | `stories/ops-error-router/samples/`, the router's `normalize` |
| 10 | AI credit usage alert defaults (80/100), the configuring role and per-team granularity; no API for per-team allocation or alert thresholds | Admin → AI pages | `policies/cost-ceilings.yml` comments; `docs/03` "by hand" list |
| 11 | Whether the `/mcp` research and listing helpers consume Tines AI credits | `GET /api/v1/ai_usage?group_by=feature` after an editor session | `docs/00`, §6.1 wording |
| 12 | Restoring a story version via API (versions API documents create/get/patch/delete only) | Versions API on a scratch story | `rollback.yml` target options; `/tines-rollback` |
| 13 | Flow counting for Send to Story sub-stories used as tools and for the ops trio; plan entitlement for the AI Agent action, change control, Cases, Apps in the target tenant | Account team; Settings → Access & security → Story allocation | §5.12 flow budget; Custom tools (Groups) consolidation; Cases branches enabled or not |
| 14 | Agent Skills: size and count limits, versioning, credit consumption, whether Workbench for Storyboard honours preset skills, whether attaching a skill to a preset or agent has an API; `metadata` accepts `git_sha` | Skills page and API on a scratch team | `tines-skills/README.md`; `skills.yml` attach step; `story-build-conventions` placement |
| 15 | Hook JSON `permissionDecision` third value (`ask` vs `request`) | The hooks reference page | Hooks may switch from exit 2 to JSON decisions |
| 16 | Story runs: whether `end_time` is null mid-run; semantics of `not_working_actions_count` and `NOT_WORKING_ACTIONS_COUNT_DESC` for derived failure detection | Observe a running scratch story via the runs and stories list endpoints | The pre-filter's overlap and failure rules |
| 17 | The audit-log `operation_name` for MCP activity; whether `audit_logs` accepts a `story_id` filter server-side | `GET /api/v1/audit_logs` after an editor session | `scripts/tines audit` filters; the weekly digest count |
| 18 | A Viewer-role team API key is effectively read-only for the monitor's sub-stories and `drift.yml` | Attempt a write with it (expect 404) | `policies/POLICY.md` identity table |
| 19 | Compare-and-swap on the `ops_lock` Resource (`if_value` on `/replace`, 422 with the current value) and the Deduplicate constant-path time gate if used | `scripts/tines resource-cas` on a scratch Resource | The lock sub-story; the router's dedupe mode |
| 20 | A headless `claude -p` session cannot reuse the `/mcp` OAuth session (assumed not; never relied on) | Run `claude -p` after an interactive consent and read the init event | Whether any headless bulk-edit path is ever added |
| 21 | `npx skills-ref validate` availability in CI; current `anthropics/claude-code-action@v1` inputs; `--json-schema @file` form | The Agent Skills spec page and the GitHub Actions docs; a dry run | `lint.yml`, `review.yml`, `propose-fix.yml` |
| 22 | Terraform `tines_story` on a change-controlled story (draft vs live); provider still 0.3.0 | Registry and a scratch apply | `terraform/README.md`; whether Terraform is ever promoted from optional |
| 23 | Library story 1231438's entry action after import (expected Webhook); 87626 as the example seed | Import into the Seeds folder and read the canvas | `stories/ops-error-router/README.md`, `stories/example-enrich-ip/README.md` |
| 24 | HTTP Request maximum timeout; whether an error routed down a failure path still fires "Notify when action fails" | A scratch story with a failure path and a test recipient | Router dedupe expectations; `story-conventions.md` |
| 25 | Mode 4: OAuth as an access-control mode (listed both as supported and unsupported); whether the editor can add the MCP server action through `/mcp`; MCP server action event retention; protocol revision support beyond 2025-11-25 | The MCP server action docs and a scratch server tested with the MCP Inspector | `stories/ops-tools-server/README.md`; the build skill's by-hand list |
| 26 | Whether `/mcp` can create Record types | Ask the editor to create one on a scratch team | The build skill's by-hand list; `records/record-types.md` |
| 27 | Rate-limit headroom for the 15-minute sweep on large tenants (stories list pagination, events 500/page, audit_logs 1,000/min) | Run the sweep in dev against the full tenant list | `sweep_minutes`, pagination in the sweep's HTTP Request actions |
| 28 | Plan-gated claims before any demo: dedicated-tenant limits, Enterprise custom roles, Cases SLAs and case webhooks; UI click paths moved on 2026-06-12, 2026-07-13 and 2026-08-17 | The tenant's plan mapping; a click-through the day before | Presenter notes only; never a slide |

---

_End of DESIGN.md. Builders: the tree in §2.2 is final; the file specs in §3 are the contract; §4–§5 are the behaviour; §6–§7 are what a reviewer signs off on; §9 is non-negotiable; §10 is where honesty lives._
