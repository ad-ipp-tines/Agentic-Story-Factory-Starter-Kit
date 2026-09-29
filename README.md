# Tines Storyworks Starter Kit

A starter kit to set up Storyworks with an LLM to build, manage, and audit Tines stories via agents.

| Part | What it is | Start here |
|---|---|---|
| The repository root | Stories and skills as code: editor skills, hooks, CI, policies, the Tines API dispatcher, the ops monitoring stories | this page |
| [`storyline/`](storyline/README.md) | the Storyline: phases, gates and the crew members that run them | [`storyline/README.md`](storyline/README.md) |
| [`kit/`](kit/README.md) | The starter kit: one importable story that provisions the repository, skills, tracker, dashboard and model provider | [`kit/README.md`](kit/README.md) |

New here? Start with [the visual tour](docs/study-guides/00-visual-tour.md). Contributing as an AI agent, or reviewing one? Read [`HANDOFF.md`](HANDOFF.md).

## Tines Stories as Code

Build, review, ship, monitor and roll back **Tines Stories** from your editor — Cursor or Claude Code — the way a software team ships code.

Stories are authored from the editor through the **Tines Stories MCP server** (Mode 2, `https://<your-tenant>.tines.com/mcp`, OAuth only), exported as JSON into this repository, reviewed like code by an instance that did not write them, and shipped into production only through Tines change control: an import into a named draft, a change request, and a named person approving in Tines. The tenant-side Agent Skills that shape your AI Agent actions and Workbench presets live in the same repository and are pushed through the Skills API. One agentic ops pair watches the tenant and *proposes* — never applies — fixes. Model Context Protocol (MCP) is the wire; the repository is what a security reviewer signs off on.

> **Status: scaffold v1.** The full specification is [`DESIGN.md`](DESIGN.md). Everything marked **VERIFY** is an assumption to confirm in your tenant before you rely on it or present it — the list is at the end of this page and in [`docs/VERIFY.md`](docs/VERIFY.md). Nothing marked VERIFY is a headline claim.

---

## The thesis: the value is the system around the prompt

Anyone can prompt an AI to "build me a phishing triage story". That prompt is the cheapest part. What makes the result **fast, controlled and safe** is everything the prompt sits inside:

| Around the prompt | What it gives you | Where it lives |
|---|---|---|
| A procedure the model follows every time (explore → plan → implement → validate → export → review) | Speed without re-deriving the craft | `.claude/skills/tines-build-story/` |
| One conventions file both editors load | Stories that look alike across builders | `AGENTS.md` (+ `CLAUDE.md` importing it) |
| A stable JSON export in git | A diff on every change, a rollback point for free | `stories/**/story.json`, `scripts/normalize.jq` |
| Deterministic lint | Rules a security team can read without reading prose | `scripts/lint-story.sh`, `policies/lint-rules.yml` |
| A reviewer that is not the author | The generator never approves its own work | `.claude/agents/tines-reviewer.md`, `review.yml` |
| Hooks | Enforcement, not advice — an instruction is a request, a hook is a rule | `.claude/hooks/*` |
| Change control with "Require approval for all changes" | A deterministic gate no prompt can argue past | `ship.yml`, `docs/02-change-control-path.md` |
| The ops pair | Observability that proposes, with evidence, and never acts alone | `stories/ops-error-router/`, `stories/ops-story-health-monitor/` |
| Budgets as files, token alerts, tool caps | A cost ceiling that fires before the platform does | `policies/cost-ceilings.yml`, per-agent Status-tab alerts |
| Team-scoped keys, OAuth, allow-listed credentials | Least privilege by construction | `.env.example`, GitHub environment secrets, Tines credentials |

This is the new way of building: not *prompting harder*, but **prompting inside a system** that makes every output diffable, reviewable, gated, observable and reversible. The prompt is still there — the prompt pack ships with the repo — but the repo is what gets signed off.

---

## The four modes

"Mode" is the only word this repository uses for the four MCP surfaces in Tines.

| Mode | Surface | This repo uses it for |
|---|---|---|
| Mode 1 | Workbench calling MCP tools (Workbench → MCP tab → New MCP connection) | Presets may carry the tenant-side skills; not otherwise required |
| **Mode 2** | **The Tines Stories MCP server** at `https://<your-tenant>.tines.com/mcp` — OAuth only, inherits your own Tines permissions, every tool use logged as MCP activity | **Authoring from the editor — every build** |
| **Mode 3** | **The AI Agent action** calling tools (Task mode, output schema, tools are Send to Story sub-stories) | **The monitoring agent** in `stories/ops-story-health-monitor/` |
| **Mode 4** | **The MCP server action** at `https://<your-tenant>.tines.com/mcp/<mcp-path>` — Streamable HTTP, counts as a flow, spends no AI credits, 30-second tool ceiling | **Exposing the ops lookups and request tools** in `stories/ops-tools-server/`, so the on-call person and the builder's editor can ask what the agent asks |

---

## The tree

```
<repo>/
├── README.md                     # this page
├── DESIGN.md                     # the merged specification every file follows
├── AGENTS.md                     # THE conventions file (< 200 lines); Cursor reads it natively
├── CLAUDE.md                     # "@AGENTS.md" + Claude Code-only notes
├── CLAUDE.local.md.example       # personal, gitignored notes template (never keys)
├── .env.example                  # variable NAMES only
├── .gitignore                    # .env, live MCP configs, local settings, .tines/ scratch
├── .mcp.json.example             # Claude Code shape of the /mcp entry; the live entry is INLINE in tines-builder (Cursor: a build-only worktree)
├── .claude/
│   ├── settings.json             # committed permissions (deny > ask > allow) + the five hooks
│   ├── rules/                    # path-scoped rules: story-json.md, tines-skills.md
│   ├── hooks/                    # guard-mcp.sh · phase-gate.sh · block-secrets.sh · lint-on-write.sh · stop-gate.sh
│   ├── agents/                   # tines-builder.md (the ONLY context holding /mcp) · tines-reviewer.md (no MCP)
│   └── skills/                   # ONE tree serves Claude Code and Cursor
│       ├── tines-connect/        # step 0: connect the editor to /mcp (inline in tines-builder for Claude Code; a build-only worktree for Cursor)
│       ├── tines-build-story/    # the core loop + references/prompt-pack.md, story-conventions.md
│       ├── tines-export/         # export → normalise → lint → stamp meta → diff
│       ├── tines-review/         # fresh-context review → findings JSON (references/findings-schema.json)
│       ├── tines-ship/           # import as draft + change request; NEVER promotes
│       ├── tines-rollback/       # git ref → draft → change request + the PR that keeps main truthful
│       ├── tines-skills-push/    # validate + dry-run the Skills API upsert
│       └── tines-propose-fix/    # headless-only; no MCP; edits stories/** on a branch
├── .cursor/
│   ├── mcp.json.example          # same server, Cursor shape (url only) → a build-only worktree's .cursor/mcp.json, never ~/.cursor/mcp.json
│   └── rules/story-json.mdc      # globs: stories/**/story.json — exports are generated artifacts
├── .github/
│   ├── CODEOWNERS                # security-platform owns policies, hooks, workflows and ops-* stories
│   ├── PULL_REQUEST_TEMPLATE.md  # doubles as the change-request description
│   └── workflows/
│       ├── lint.yml              # deterministic gate — no model, no network, no secrets
│       ├── review.yml            # an independent Claude Code instance runs /tines-review — no MCP, no tenant
│       ├── ship.yml              # merge to main → version → import as draft → recipients → change request. NEVER promotes
│       ├── promote.yml           # workflow_dispatch: promotes ONLY an APPROVED change request; never bypass
│       ├── skills.yml            # merge to main → upsert tines-skills/** via the Skills API
│       ├── drift.yml             # nightly: export prod, diff vs main, attribute via audit logs, open a drift PR; budget check
│       ├── rollback.yml          # workflow_dispatch: git ref → draft → change request; separate break-glass job
│       └── propose-fix.yml       # repository_dispatch from the monitor → headless /tines-propose-fix → PR
├── policies/
│   ├── POLICY.md                 # the governance contract: identities, gates, what never happens
│   ├── cost-ceilings.yml         # machine-readable budgets; mirrored into the ops_limits Resource
│   ├── never-touch.yml           # story ids / name patterns / teams no hook, skill or pipeline may write
│   ├── lint-rules.yml            # the rule set lint-story.sh enforces, with severities
│   └── break-glass-log.md        # append-only human log of every disable or bypass used in anger
├── scripts/
│   ├── tines                     # ONE bash dispatcher over Python scripts (scripts/README.md)
│   ├── normalize.jq              # stable export: drop exported_at, sorted keys, agent order preserved
│   ├── lint-story.sh             # deterministic checks driven by policies/lint-rules.yml
│   └── diff-story.sh             # semantic diff for PRs and change requests
├── stories/
│   ├── README.md                 # how a story folder is laid out; the lifecycle of story.json
│   ├── _manifest.yaml            # environments + slug → story_id map; no secrets
│   ├── _template/                # README, story.meta.yaml, tests/{sample-event.json, expectations.yaml}
│   ├── example-enrich-ip/        # the worked example every builder copies (a Send to Story sub-story)
│   ├── ops-error-router/         # every production story's monitoring recipient (LIVE)
│   ├── ops-story-health-monitor/ # the agentic sweep (Mode 3): health + credits → proposals → human approval
│   ├── ops-get-*/                # [OPS] 11–15: the sweep's five read sub-stories (contract + meta until built)
│   ├── ops-apply-alert-rule/     # [OPS] 16: the only place an approved change reaches production
│   ├── ops-request-approval/     # [OPS] 17: the approval request, shared by the sweep and the Mode 4 server
│   └── ops-tools-server/         # Mode 4: the ops lookups + request tools exposed to editors and Claude clients
├── tines-skills/                 # Tines Agent Skills pushed to the tenant (AI Agent actions + Workbench presets)
│   ├── _manifest.yaml            # per-skill team scope and attachment targets
│   ├── story-health-triage/      # attached to the sweep's triage agent
│   ├── credit-budget-analyst/    # attached to the same agent
│   ├── alert-policy/             # the monitoring policy as a skill: the Ops Workbench preset; optional third skill on triage
│   └── story-build-conventions/  # AGENTS.md distilled for the Workbench for Storyboard preset (VERIFY presets honour skills there)
├── terraform/                    # OPTIONAL alternative deploy path; not on the default pipeline
└── docs/                         # 00 why · 01 decision rules · 02 change-control path · 03 monitoring · 04 cost · 05 security · 06 pros and cons · VERIFY
```

**Repo map in one line:** `AGENTS.md` = rules · `.claude/skills/` = procedures · `scripts/tines` = the API · `stories/` = truth · `tines-skills/` = tenant-side skills · `policies/` = the contract · `.github/workflows/` = gates · `docs/` = why.

---

## The five workflows, in short

1. **Build a story (Mode 2, dev team, one afternoon).** `/tines-connect` completes the OAuth consent for the Tines Stories MCP server — in Claude Code the server is defined inline in the `tines-builder` subagent and consented in a `claude --agent tines-builder` session; in Cursor it goes only in the project `.cursor/mcp.json` of a separate build-only worktree, never the global `~/.cursor/mcp.json`. `/tines-build-story <slug> "<what to build>"` delegates to the `tines-builder` subagent: explore the story → plan → one prompt per action from the prompt pack → **Validate** → a test event → the by-hand steps the server cannot do → `/tines-export`. Hooks mirror every MCP call, block production ids and destructive-looking names, lint every write, and refuse to end the turn with a stale export.
2. **Review and ship.** `/tines-review` runs in a forked context on `tines-reviewer` (no MCP, read-only) and returns findings JSON. Push, open the PR: `lint.yml` (no model) and `review.yml` (an independent Claude Code instance) must pass; a CODEOWNER reviews; a human merges. `ship.yml` tags a story version, imports the export into the production story as a draft named `git-<sha>`, sets recipients and `monitor_failures` on the draft, and opens a change request. **A named approver approves in Tines** and pushes — or `promote.yml` promotes a request whose status is already APPROVED. Nothing ever promotes a PENDING request or sets `bypass_approval`.
3. **Push skills (tenant-side Agent Skills as code).** Edit `tines-skills/<name>/SKILL.md`; `/tines-skills-push <name>` validates and dry-runs the upsert; the PR is reviewed like any other; on merge `skills.yml` does `GET` → `PUT` or `POST /api/v1/skills`. Attaching a skill to a preset or an agent is [BY HAND] (no API found — VERIFY).
4. **Monitor and alert (Mode 3 + Mode 4).** The **router** (`ops-error-router`) is every production story's monitoring recipient: normalise, dedupe, enrich with the last level-4 log, Slack thread, `ops_alerts` Record. The **sweep** (`ops-story-health-monitor`) runs every 15 minutes behind a kill switch and a compare-and-swap lock, reads live activity, AI usage and recent runs, pre-filters deterministically, and hands **only anomalies** to a Task-mode AI Agent action with five read-only tools and an output schema. A Trigger on explicit schema fields routes to: record only · an alert-rule proposal (Slack approval verified against `ops_responders`) · a Case or ticket · a GitHub issue with an exact `/tines-build-story` prompt · a `repository_dispatch` that becomes a PR · a disable request (two approvers in prod). The **Mode 4 server** (`ops-tools-server`) exposes the same lookups and request tools to Claude Desktop, Claude Code or Cursor. **Humans approve anything that changes production.**
5. **Roll back.** `/tines-rollback <slug> <sha|previous>` reverts the export on a branch and opens the PR so `main` equals what will be live; `rollback.yml` imports the ref's `story.json` as a draft named `rollback-<target>` and opens a change request titled `ROLLBACK …`. Emergency containment is three separate break-glass jobs under the GitHub environment `break-glass`: `break-glass` calls `POST /api/v1/stories/{id}/disable` (the kill switch), `break-glass-promote` is the only job that may send `bypass_approval` (and only if the rollback's request is still not APPROVED), and `break-glass-re-enable` turns the story back on. Each needs two reviewers, neither of them the dispatcher — one approves environment `break-glass-2`, a different person approves `break-glass` ("Prevent self-reviews" on both; the job counts the run's approvals and fails closed) — and a mandatory reason, and each disable, bypass or re-enable appends a line to `policies/break-glass-log.md` in the same run.

---

## The Storyworks: `storyline/` and `kit/`

This repository is also the **Tines Storyworks Starter Kit**: the scaffold above, a lifecycle every story follows, and a starter kit that sets a new tenant up from one import. The whole design is [`REPO-DESIGN.md`](REPO-DESIGN.md).

**The lifecycle in one line:** intake → discover → design → build → verify → ship → operate → improve — each phase with entry and exit criteria, artifacts and a gate; narrow crew members do the work, code decides what runs next, and people hold every gate that changes what exists or what runs.

| Part | Where | What it is |
|---|---|---|
| A. The root | `/` | The stories-as-code scaffold this page describes: build through Mode 2, review, ship through change control, monitor, roll back |
| B. The Storyline | [`storyline/`](storyline/README.md) | the **Storyline**: a state machine, phases with entry and exit criteria, gates, templates, and the crew it spins up (`/storyline <slug>`, `./scripts/storyline`) |
| C. The starter kit | [`kit/`](kit/README.md) + `stories/kit-launch/` | One importable Tines story with a kickoff Page that provisions the repository and the tenant; the tracker, the dashboard, the model-provider guides and the ten starter stories |

**The one import.** On Business or Enterprise with two licensed teams, import `stories/kit-launch/story.json` (`[KIT] 00 · Launch Storyworks`) into the prod team, which is the ops team, and submit its `kickoff` Page. It creates a private repository from this template, commits the tenant config, creates the Tines Agent Skills, the tracker's Record types and the kit Resources, checks the model provider with one test call and one tool call, and writes a setup report with a `[BY HAND]` list. Until the maintainer release replaces it, that `story.json` is a labelled **SKELETON**: never import it. On Community Edition, or with one licensed team, follow the manual path in `kit/docs/community-path.md`.

**One change to the build workflow above:** in Claude Code the Tines Stories MCP server is defined inline in the `tines-builder` subagent, not at user scope, so only the builder loads it; `/tines-connect` completes the OAuth consent in a `claude --agent tines-builder` session.

Start with [`storyline/README.md`](storyline/README.md) before a new story, [`kit/README.md`](kit/README.md) to set Storyworks up, and [`docs/08-storyworks.md`](docs/08-storyworks.md) if you are deciding whether to adopt it.

---

## Quick start — from zero to a change request

0. **Prerequisites.** A dedicated Tines **team** per environment (never personal space — the AI Agent action is unavailable there and credentials must be shared). Tenant change-control policies **Enable by default** and **Require approval for all changes** switched on. A **team-scoped** API key (Editor role) for the dev team. `jq`, `yq` and `gh` installed; `python3` ≥ 3.9 and `python3 -m pip install -r scripts/requirements.txt` (`requests`, `PyYAML` — the dispatcher runs Python scripts; see `scripts/README.md`). Your Tines user must be a member of the dev team — the Tines Stories MCP server grants nothing you lack.
1. `cp .env.example .env`, fill `TINES_TENANT` and the dev key, `source .env` (every line in it is `export`ed, so the scripts, Terraform and your editor see the values). Never commit `.env`. Then start `claude` — or Cursor — **from that same shell**, so the session inherits the variables.
2. Run **`/tines-connect`**. Claude Code: do **not** run `claude mcp add` — the server is defined inline in `.claude/agents/tines-builder.md`, so it loads only for the builder (a user-scope entry would put its tools into every session). From the same shell, start `claude --agent tines-builder`, run `/mcp`, select `tines` and complete the consent screen titled **Tines Stories MCP server** — the inline form is VERIFY; prefer the copy-ready snippet at `https://<your-tenant>.tines.com/mcp` (login required). Cursor: in a separate build-only worktree (`git worktree add ../<repo>-build`, opened as its own workspace for the builder chat only), paste `.cursor/mcp.json.example` into that worktree's `.cursor/mcp.json` — never the global `~/.cursor/mcp.json`, which gives every chat the server; saving triggers OAuth. Until K4 is confirmed, the other crew run in Claude Code. An API key will not work here.
3. Smoke test: "Using the Tines MCP server, list the teams I can see and the stories in each." Record the tool names your client shows in `docs/VERIFY.md` (item 1).
4. Add the slug to `stories/_manifest.yaml` (`new: true` if the story does not exist yet in prod); copy `stories/_template/` to `stories/<slug>/`; fill `story.meta.yaml` — credentials by **name** only, and they must already exist in the dev team.
5. **`/tines-build-story <slug> "<what to build>"`**. Say yes to the plan. The skill ends with Validate, a test event, and the by-hand list (Send to Story access, event retention, change control on for a new story, Record types, the AI Agent token alert on the Status tab). **A new story gets its dev id here, not from an import:** the builder creates it in the dev team through `/mcp`, so record that id with `./scripts/tines manifest-set-dev-id <slug> <id>` (it writes only `dev.story_id` under the slug in `stories/_manifest.yaml`; an id is not a secret) before the next step — `/tines-export` stops on a dev id of `0`.
6. **`/tines-export <slug>`** — normalised `story.json`, lint, `exported_from` stamped in meta, semantic diff printed. Commit on `story/<slug>/<short>` with `story(<slug>): <what changed>`.
7. From a **fresh** session, **`/tines-review`**; fix blockers with another `/tines-build-story` pass, never by editing `story.json`. Push, `gh pr create` with the template. `lint.yml` and `review.yml` run.
8. A CODEOWNER reviews; a human merges to `main`. For a story that already exists in prod, `ship.yml` opens the change request and posts its URL to the ops channel. **A new story is never created in prod by a merge:** a `mode: new` import would make a live story with no draft and no change request, so `import_story.py` refuses it. Preferred: before the first ship, a person creates an empty, disabled, change-controlled story with the export's exact name in the prod team [BY HAND] and commits its id as `prod: { story_id: <id> }` (removing `new: true`); the ship is then a `versionReplace` into a draft + change request like any other. The only alternative is an explicit, logged `workflow_dispatch` of `ship.yml` (`slug`, `env: prod`, `new_in_prod_reason: "<one sentence>"`), which creates the story, sets its monitoring and opens a manifest PR that records the prod id and removes `new: true`; merge that PR, then dispatch `ship.yml` again (a merge that touches only `stories/_manifest.yaml` does not ship) to open the change request.
9. The named approver reads the live-vs-draft diff in Tines and the PR, **approves and pushes** (or runs `promote.yml` on the APPROVED request).
10. The ops pair picks the story up: recipients from the manifest, `monitor_failures` on, a baseline captured on the next sweeps; `drift.yml` proves that night that production equals `main`.

---

## Four proofs a security reviewer can check

| Proof | Where |
|---|---|
| **Least privilege** — builders act as themselves through OAuth; CI holds team-scoped keys that cannot approve; the agent holds no write credential | [`policies/POLICY.md`](policies/POLICY.md) |
| **Cost ceiling** — budgets are a file, every AI Agent action needs a budget line, token alerts on every agent, a healthy sweep spends zero credits | [`policies/cost-ceilings.yml`](policies/cost-ceilings.yml) |
| **Auditability** — the commit SHA in every change-request description, a story version per ship, MCP activity in the Tines audit logs, a local mirror in `.tines/mcp-activity.jsonl` | `scripts/tines cr-open`, `.claude/hooks/guard-mcp.sh`, `drift.yml` |
| **Rollback** — any committed export becomes production again through the same draft → change request → approval path; break-glass is separate, two-person and logged | `.github/workflows/rollback.yml`, [`policies/break-glass-log.md`](policies/break-glass-log.md) |

---

## MCP configuration — why nothing live is committed

This repository ships **`.mcp.json.example`** and **`.cursor/mcp.json.example`** only. The live entries are gitignored on purpose: in `claude -p` and SDK sessions a repository `.mcp.json` connects its servers **without a trust prompt** and repository hooks run, so the Tines entry is never a repository `.mcp.json`. In Claude Code it is defined **inline in the `tines-builder` subagent** (never at user scope, which would load it into every session) and consented in a `claude --agent tines-builder` session; in Cursor it lives only in the project `.cursor/mcp.json` (gitignored) of a **separate build-only worktree**, where `/tines-connect` puts it — never the global `~/.cursor/mcp.json`, which would give it to every chat (per-chat scoping is VERIFY K4). Settings files are strict JSON, so the explanations are here rather than in the files.

**Mode 2 — the Tines Stories MCP server (authoring).** The Claude Code shape:

```json
{ "mcpServers": { "tines": { "type": "http", "url": "https://${TINES_TENANT}.tines.com/mcp" } } }
```

- No `headers`: authentication is **OAuth only**; an API key will not work. On first use the client runs OAuth and you approve a consent screen titled **Tines Stories MCP server**.
- The server name must be exactly `tines` — the permission rule `mcp__tines__*` and the hook matcher `mcp__tines__.*` in `.claude/settings.json` depend on it.
- Cursor takes the same entry with `url` only (`.cursor/mcp.json.example`); whether Cursor accepts a `type` key is VERIFY.
- Prefer the copy-ready snippet Tines shows at `https://<your-tenant>.tines.com/mcp` when you are logged in.

**Mode 4 — a server you built (consuming).** The ops tools server in `stories/ops-tools-server/` is reached the same way any Tines-built MCP server is, with a **team-scoped Tines API key** in the `Authorization` header. This is the example the `.mcp.json` cannot carry as a comment — it goes in user scope, never in the repo, because it holds a credential reference:

```json
{
  "mcpServers": {
    "ops-tools": {
      "type": "http",
      "url": "https://${TINES_TENANT}.tines.com/mcp/<mcp-path>",
      "headers": { "Authorization": "Bearer ${OPS_TOOLS_API_KEY}" }
    }
  }
}
```

- `${VAR}` expansion keeps the key out of the file; `OPS_TOOLS_API_KEY` is a team-scoped Tines API key held by a member of the ops team, set in your shell, never in `.env.example` or the manifest.
- The caller's email arrives in the server story as `META.headers.email` and is written to the proposal Record; the `Authorization` header itself is never captured.
- Every lookup on that server carries **Tool hints: Read only**; the two request tools keep the defaults (Destructive on). Tool hints are MCP **annotations** a client *may* use — Tines documents what each hint means and its default, not how any client acts on it, so whether a client prompts before a Destructive tool (or skips a prompt for a Read only one) is **VERIFY** per client and never a control. The control is on the Tines side: the two request tools only *request* — they post an approval and return an `approval_id` — and nothing changes until `[OPS] 17 · Request approval (sub)` has posted it and an approver verified against `ops_responders` has approved.
- Tool responses must return within 30 seconds; Streamable HTTP only. Whether OAuth is available as a Mode 4 access mode is listed both as supported and unsupported in the docs — VERIFY before relying on it.

---

## Pros and cons

| | Pro | Con |
|---|---|---|
| **Diffs and review** | Stories get what code has had for decades: a diff on every change, an independent review, a merge gate, a rollback point and a nightly drift check | Story exports are not designed for hand editing (index-based links, no published option-key schema); import matches by name; embedded sub-stories are not imported; MCP connections drop on import |
| **Speed** | One afternoon from idea to change request; the build skill carries the procedure, hooks lint every write, the stop gate keeps the export fresh | Process overhead for tiny changes (branch, PR, two checks, CODEOWNERS, merge, change request, approval) — use `tier: internal` and a lighter path for low-risk stories |
| **Cost** | The build loop runs on the editor's plan — no Tines AI credits are listed for the Tines Stories MCP server; runtime AI is bounded by schemas, tool caps, token alerts, a daily run cap, a kill switch and file-based budgets | No API for per-team credit allocation, credit-usage alert thresholds or AI Agent token thresholds — those stay by hand and can drift from the policy file |
| **Security** | OAuth-only authoring that inherits the builder's own permissions and is audit-logged; credentials never leave Tines or appear in exports; team-scoped keys that cannot approve; change control as the deterministic gate | Mode 2 runs on the editor's provider, so the organisation's editor data policy — not Tines' foundation guarantees — governs what the model sees |
| **Controls as files** | Permissions, hooks, budgets, never-touch list, lint rules, CODEOWNERS, workflow gates and the governance contract are all diffable text | The Tines Stories MCP server's tool names and count are unpublished, so the hook guard is a regex plus an input-based id check until your client lists them |
| **Two gates** | A GitHub environment with reviewers *and* a Tines change request approved by a person, joined by the commit SHA and a story version | `/mcp` is OAuth only — no headless authoring; CI can lint, review, import and open change requests, but every tenant edit stays interactive |
| **Skills as code** | One skills tree serves Cursor and Claude Code; tenant-side Agent Skills live beside them with a CRUD API, so "how we build" and "how our agents behave" are reviewed in one PR | Cursor reads `.claude/skills/` as a legacy path and does not run Claude Code hooks, so enforcement in Cursor rests on CI and Tines change control |
| **Monitoring** | Tines' own recommendation (send alerts to a story) becomes an evidence-based proposer whose thresholds come from baseline data and whose only outputs are requests | There is no run-status field, so failure is derived from counts and logs; the monitoring webhook payload is undocumented and must be captured by hand once; the monitor is itself a story that can fail |
| **All three modes** | Mode 2 authors, Mode 3 diagnoses, Mode 4 exposes the same sub-stories to humans and editors — no second implementation of the guards | Two teams plus the ops trio cost licences and roughly nine flows; Community tenants cannot run the monitoring agent; some plans lack the AI Agent action, Cases or change control |
| **Change control** | "Require approval for all changes" is a gate no prompt can argue past | How `/mcp` edits interact with change control and drafts is unpublished — the policy is enabled on faith until verified |
| **Bulk edits** | Consistent edits across many stories become an editor task with a reviewable diff instead of a clicking session | LLM-edited JSON proposals can break links; the safer default is an issue with a prompt, which adds a human step |
| **Vendor-neutral** | Plain JSON exports, the public Tines API, an optional Terraform path, Agent Skills as an open standard | The Terraform provider is 0.x, TEXT credentials only, no skills resource, unverified on change-controlled stories — optional, not primary |
| **Simplest first** | The decision doc, the review checklist and the `tools_are_requests` lint rule keep templates before agents, Send to Story before MCP, and no write tool without an approval path | Audit noise grows with MCP activity, drift PRs and proposal PRs; reviewers must be willing to read story JSON |

The long form is [`docs/06-pros-and-cons.md`](docs/06-pros-and-cons.md).

---

## Verify in your tenant before presenting

These are assumptions this scaffold is built *around*, not *on*. Confirm each in a scratch story or the tenant's client first; the full table with "how to confirm" and "what changes when confirmed" is [`docs/VERIFY.md`](docs/VERIFY.md).

| # | Assumed | Why it matters here |
|---|---|---|
| 1 | The `/mcp` tool names and count (observed "dozens"; unpublished) | `guard-mcp.sh` uses a regex and an input-based id check until you record the real list |
| 2 | `/mcp` edits on a change-controlled dev story land as drafts and respect "Require approval for all changes" | The build skill's test step (`?draft=<name>`) and `docs/02` wording |
| 3 | The Claude Code setup (the server inline in `tines-builder`, OAuth via `/mcp` in a `claude --agent tines-builder` session; never `claude mcp add … --scope user`) — inferred from the docs' client list | `/tines-connect`, `.claude/agents/tines-builder.md` and `.mcp.json.example` |
| 4 | Cursor's handling of a `type` key in `mcp.json`, discovery of `.claude/skills/`, and that its IDE agent does not run Claude Code hooks | `.cursor/mcp.json.example`, a possible `.cursor/skills` symlink, the enforcement note in `story-json.mdc` |
| 6 | The `POST /api/v1/stories/import` response field that carries the draft id; behaviour when a referenced credential is missing in the target team | `scripts/tines import-draft`, `ship.yml` failure handling |
| 8 | Export JSON key names for HTTP retry options, `emit_failure_event`, monitor flags, `keep_events_for`, the AI Agent output schema; `Agents::LLMAgent` as the AI Agent action type; the credential/resource reference syntax | `policies/lint-rules.yml` carries `key: VERIFY` on those rules until one real export is read |
| 9 | The monitoring notification webhook payload; AI credit usage alert, event-limit and change-control webhook payloads | The router's `normalize` action and `samples/` |
| 10 | AI credit usage alert defaults (80/100) and the absence of an API for per-team allocation or alert thresholds | `policies/cost-ceilings.yml` comments; the "by hand" list in `docs/03` |
| 11 | Whether the `/mcp` research and listing helpers consume Tines AI credits | The cost claim in `docs/00` and `docs/04` |
| 13 | Flow counting for Send to Story sub-stories used as tools; plan entitlement for the AI Agent action, change control, Cases | The ≈ 9-flow budget for the ops trio |
| 14 | Agent Skills limits, versioning, credit consumption; whether Workbench for Storyboard honours preset skills; whether attaching a skill has an API | `tines-skills/README.md`, `skills.yml` |
| 18 | A Viewer-role team API key is effectively read-only for the monitor's sub-stories and `drift.yml` | The identity table in `policies/POLICY.md` |
| 25 | Mode 4: OAuth as an access-control mode; whether the editor can add the MCP server action through `/mcp` | `stories/ops-tools-server/README.md` |

When you confirm an item, update `docs/VERIFY.md` and state what changed in the repo as a result.

---

## Read next

- [`docs/study-guides/00-visual-tour.md`](docs/study-guides/00-visual-tour.md) — start here if you are new: eleven diagrams, one idea each.
- [`HANDOFF.md`](HANDOFF.md) — for AI contributors and their reviewers: where things stand, the rules for pull requests, the enhancement backlog.
- [`AGENTS.md`](AGENTS.md) — the conventions, before your first build.
- [`docs/01-decision-rules.md`](docs/01-decision-rules.md) — before choosing an agent or MCP for anything.
- [`policies/POLICY.md`](policies/POLICY.md) — before shipping.
- [`docs/00-why-stories-as-code.md`](docs/00-why-stories-as-code.md) — for someone deciding whether to adopt this.
- [`DESIGN.md`](DESIGN.md) — the whole specification, including the agentic monitoring story in §5.
- [`storyline/README.md`](storyline/README.md) — before starting a new story: the lifecycle, its gates and its commands.
- [`kit/README.md`](kit/README.md) — before setting the Storyworks up in a tenant: the plans it supports, the one import, what it creates.

Conventions that hold everywhere in this repository: placeholders (`<your-tenant>`, `<org>`, `0` for ids, `*.example.invalid`, documentation-range IPs) and never real values; no customer names, people or tenant hostnames; product names exactly as Tines writes them; guards live in the story, not in prompts; one story at a time; never hand-edit `story.json`; no secrets, ever.
