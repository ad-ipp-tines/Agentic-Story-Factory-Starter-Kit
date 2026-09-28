# 02 · The five workflows — step by step, with the exact files and commands

_Tines Stories as Code · docs v1 (2026-09-24) · Matches `DESIGN.md` §4 · Every endpoint named here is in `DESIGN.md` §3.5/§4/§5; every skill is in `.claude/skills/`; every subcommand is `scripts/tines`. The Tines Stories MCP server (Model Context Protocol, MCP) is described by capability only — its tool names are unpublished (VERIFY, item 1)._

Five workflows, one identity each (see `04-security-model.md` §2):

| # | Workflow | MCP surface | Who acts | Where it runs |
|---|---|---|---|---|
| 1 | Build a story | **Mode 2** (`/mcp`, OAuth) | The builder, as their own Tines user | Editor → dev team |
| 2 | Review and ship | none | An independent reviewer, then CI-prod (team-scoped key), then a named approver in Tines | Editor → GitHub → prod team |
| 3 | Push skills | none | CI-prod via the Skills API | GitHub → prod team |
| 4 | Monitor and alert | **Mode 3** (the agent) and **Mode 4** (the exposed tools) | The ops pair, with a read-only key; a verified approver for anything that changes prod | Tenant (ops team) |
| 5 | Roll back | none | A human runs a workflow; break-glass needs two reviewers | GitHub → prod team |

---

## 1. Build a story (one afternoon, dev team) — Mode 2

**Files:** `.env` (from `.env.example`, gitignored) · `stories/_manifest.yaml` · `stories/<slug>/README.md` · `stories/<slug>/story.meta.yaml` · `stories/<slug>/tests/sample-event.json` · `stories/<slug>/tests/expectations.yaml` · `stories/<slug>/story.json` (generated, never typed) · `.tines/mcp-activity.jsonl` (local audit mirror, gitignored).
**Skills:** `/tines-connect` · `/tines-build-story` · `/tines-export`. **Subagent:** `tines-builder` (the only context that holds the `/mcp` server). **Hooks:** `guard-mcp.sh`, `block-secrets.sh`, `lint-on-write.sh`, `stop-gate.sh`.

### 1.0 Prerequisites (once per tenant, [BY HAND])

- A dedicated Tines **team** per environment — a dev team and a prod team. Never personal space: the AI Agent action is unavailable there, and credentials must be shared.
- Tenant change-control policies **Enable by default** and **Require approval for all changes** on (admins and owners included).
- A **team-scoped** API key (Editor role) for the dev team. Never a personal key.
- The credentials the story will reference already exist in the dev team **by name**, with `allowed_hosts` set and Workbench access off for pipeline keys.
- `jq`, `yq`, `gh` installed; `python3` ≥ 3.9 and `python3 -m pip install -r scripts/requirements.txt` (`requests`, `PyYAML` — `scripts/tines` is a bash dispatcher over Python scripts, `scripts/README.md`); Claude Code or Cursor.

### 1.1 Connect the editor

```bash
cp .env.example .env          # fill TINES_TENANT (host prefix only), TINES_API_KEY (dev team key), TINES_TEAM_ID, TINES_ENV=dev
source .env
```

Then run **`/tines-connect`**. It reads `TINES_TENANT` from the environment (the skill never reads `.env` — `Read(./.env)` is denied), and:

- **Claude Code:** never `claude mcp add` — the server is defined inline in `.claude/agents/tines-builder.md` (`mcpServers`), so it loads only for the builder, and a user-scope entry would put its tools into every session. From the same shell, start `claude --agent tines-builder`, run `/mcp`, select `tines` and complete the consent screen titled **Tines Stories MCP server**. The inline form is inferred from Claude Code conventions, not a Tines page — VERIFY (items 3 and 5); prefer the copy-ready snippet shown at `https://<your-tenant>.tines.com/mcp` (login required).
- **Cursor:** in a separate build-only worktree (`git worktree add ../<repo>-build`, opened as its own workspace for the builder chat only), Settings → Customize → MCP → New MCP Server → paste `.cursor/mcp.json.example` into that worktree's project `.cursor/mcp.json` — never the global `~/.cursor/mcp.json`, which gives every chat the server (per-chat scoping is VERIFY K4); saving triggers the OAuth flow.
- The server name must be `tines` — the settings matcher `mcp__tines__.*` and the allow rule `mcp__tines__*` depend on it.
- **An API key will not work here.** Authentication is OAuth only. A lapsed session shows as "unauthorized" or a server with no tools: complete the consent screen again (`/mcp` → `tines` in a `claude --agent tines-builder` session, or re-save the build worktree's entry in Cursor).
- Smoke prompt: *"Using the Tines MCP server, list the teams I can see and the stories in each."* An auth error means redo OAuth; a missing team means your Tines user is not a member — the server grants nothing you lack.
- Record the tool names the client lists in `docs/VERIFY.md` (item 1) so `guard-mcp.sh` can move from a regex to an explicit deny list.

### 1.2 Register the story

1. Add the slug to `stories/_manifest.yaml` under `stories:` — `dev: { story_id: <id> }` when the story already exists in the dev team. For a **new** story add it with `dev: { story_id: 0 }` and `new: true` (`new` concerns only the prod id); the builder creates the story in the dev team through `/mcp` during `/tines-build-story`, and its dev id must then be recorded here as `dev: { story_id: <id> }` (an id is not a secret) **before** `/tines-export` — nothing else writes it, and the export stops on a dev id of `0`.
2. `cp -r stories/_template stories/<slug>` and fill `story.meta.yaml`: `name` (must equal the story name — `[PREFIX] NN · Verb noun`, `(sub)` suffix for sub-stories), `mode`, `owner_team`, `tier`, `credentials: []` and `resources: []` **by name**, `monitoring`, `ai.agents` (empty unless the story has an AI Agent action — then each entry needs `output_schema: true`, `token_alert`, `skills`, `budget_ref`), `schedule_interval_seconds`.
3. Write `tests/sample-event.json` with documentation-range values only (`203.0.113.10`, `builder@example.invalid`) and `tests/expectations.yaml` (`entry_action`, `expected_actions_fired_min`, `no_error_logs_on`, `result_fields`).
4. If the story has an AI Agent action, add its budget line to `policies/cost-ceilings.yml` now — `lint.yml` fails a PR without it.

### 1.3 Build

```
/tines-build-story <slug> "<what to build>"
```

Delegated to `tines-builder`. Preconditions the skill checks: `TINES_ENV=dev`; the slug is in the manifest; the credentials in `story.meta.yaml` exist in the dev team by name. The loop:

1. **Explore.** Through the Tines Stories MCP server, read the story named in the manifest (or create it in the dev team, in the manifest's folder). Report actions, connections, recent logs, referenced credential and resource names — never values, never other stories, never data in flight (that is what the authoring engine can see).
2. **Plan.** Anything bigger than a sentence becomes a numbered list of actions with type, name and field names. Wait for a yes.
3. **Implement.** One prompt per action from `.claude/skills/tines-build-story/references/prompt-pack.md`, in build order: entry → `normalize` (`DEFAULT()` fallbacks) → a guard Trigger before any AI step → integrations with **named** credentials → `verdict` → `result` (3–5 fields) → `error` shape `{status, error_category, retryable, message}` on the failure path → HTTP hardening (`retry_on_status [429, 500-599]`, retries 6, `emit_failure_event` **Always**) → a Note on the canvas stating purpose and mode. Every prompt names the story, the action type and the fields, and ends with "then validate". `guard-mcp.sh` mirrors every call to `.tines/mcp-activity.jsonl` and blocks any production or never-touch id, any call while `TINES_ENV=prod`, and destructive-looking tool names (regex — VERIFY, item 1).
4. **Validate.** End with "Validate"; fix what it reports; after two failed corrections on one issue, stop and re-prompt.
5. **Test.** Post `stories/<slug>/tests/sample-event.json` to the entry action (`?draft=<name>` on the webhook when change control is on and the edits sit in a draft — whether `/mcp` edits land as drafts is VERIFY, item 2). Read the events (`GET /api/v1/stories/{id}/runs`, then `/runs/{guid}` if needed) and compare with `tests/expectations.yaml`.
6. **[BY HAND]** — the skill says so explicitly; these cannot be done through `/mcp`: enable **Send to Story** access for the team if the story is a sub-story; raise **event retention** above 7 days; turn **change control on** if the story is new; create **Record types** (whether `/mcp` can — VERIFY, item 26); set the AI Agent **token alert** on the Status tab.
7. **Export** — §1.4.
8. **Commit** — §1.5.

**Never:** hand-edit `story.json` (links are index-based); paste values; name `/mcp` tools; work in prod; touch more than one story per branch.

### 1.4 Export

```
/tines-export <slug>            # or with a draft: /tines-export <slug> --draft <id>
```

What it runs:

```bash
./scripts/tines export <slug> [--draft <id>]            # GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true[&draft_id=]  | jq -S -f scripts/normalize.jq
./scripts/lint-story.sh stories/<slug>/story.json        # driven by policies/lint-rules.yml; the PostToolUse hook runs it again on every write
yq -i '.exported_from = {env: "dev", story_id: <id>, draft_id: "<id or empty>", at: "<iso>", sha: "<git sha>"}' stories/<slug>/story.meta.yaml
./scripts/diff-story.sh stories/<slug>/story.json --against HEAD
```

`normalize.jq` drops `exported_at`, sorts keys, and **preserves agent order** (links reference agents by index). Exports contain no credentials, resources or events by design; recipients are cleared by `clear_recipients=true` and set from the manifest on ship.

### 1.5 Commit

```bash
git checkout -b story/<slug>/<short>
git add stories/<slug>
git commit -m "story(<slug>): <what changed>"
```

`stop-gate.sh` refuses to end the turn while lint fails or while a story touched through `/mcp` this session has an `exported_from.at` older than the last logged MCP call — the message names the exact `/tines-export <slug>` to run. The skill ends with: *"Run `/tines-review` from a fresh session before opening the PR."*

---

## 2. Review and ship (repo → production)

**Files:** `.claude/skills/tines-review/` (+ `references/findings-schema.json`) · `.claude/agents/tines-reviewer.md` · `.github/PULL_REQUEST_TEMPLATE.md` · `.github/CODEOWNERS` · `.github/workflows/lint.yml` · `review.yml` · `ship.yml` · `promote.yml` · `drift.yml` · `policies/POLICY.md`.

### 2.1 Independent review, locally

```
/tines-review
```

Runs with `context: fork` on `tines-reviewer` — a fresh context with **no MCP and no write tools** (`disallowedTools: Write, Edit`). It refuses if the current session built the story. Checks: naming and `(sub)` suffix; `result` Event Transform and error shape on sub-stories; HTTP hardening on every HTTP Request action (key names VERIFY, item 8); every AI Agent action has an output schema, a Trigger after it, a `tines-skills/` attachment noted, a budget line and a token alert in meta; no options value looks like a token, a `Bearer `, `xox[bp]-`, `sk-` or an email; credentials and resources referenced are listed in meta; `tier: production` ⇒ `monitor_failures: true` and recipients `manifest`; diff sanity (agent count changes explained; no links removed silently). Output is the JSON in `references/findings-schema.json` with `verdict: pass | changes_requested`. Fix blockers with another `/tines-build-story` pass and re-export — never by editing `story.json`.

### 2.2 Open the PR

```bash
git push -u origin story/<slug>/<short>        # permission: ask
gh pr create --fill                             # permission: ask; the template is .github/PULL_REQUEST_TEMPLATE.md
```

Fill the template: story and environment · what changed (paste `./scripts/diff-story.sh` output) · why · test event and observed events (run guid, `action_count`, `event_count`) · cost impact (new AI Agent action? tool count? schedule? budget line?) · monitoring (recipients, watchdog seconds) · risk and blast radius · rollback ref (previous sha) · approver in Tines (a role, not a person).

### 2.3 CI gates

- **`lint.yml`** — deterministic, no model, no network, no secrets: `jq empty` on every `story.json`; fail if any export still contains `exported_at`; `./scripts/lint-story.sh` on changed exports; `tines-skills/*/SKILL.md` frontmatter (name = directory, `^[a-z0-9]+(-[a-z0-9]+)*$`, ≤ 64 chars, description ≤ 1024, no "anthropic"/"claude"); manifest consistency (`prod.story_id` or `new: true`; `story.json.name == meta.name`); secret patterns plus gitleaks; `tier: production` ⇒ monitoring; every AI Agent action has a line in `policies/cost-ceilings.yml`; posts the `diff-story.sh` summary as a PR comment.
- **`review.yml`** — an independent Claude Code instance runs `/tines-review <pr>` with `--max-turns 10`, an explicit `--allowedTools` list, `--json-schema` against `findings-schema.json` (the `@file` form is VERIFY, item 21), `timeout-minutes: 15`, a concurrency group per PR. **No MCP, no tenant credentials.** Findings become review comments; `changes_requested` fails the check. Fork PRs receive no secrets; `allowed_bots` is empty.
- **CODEOWNERS** review; branch protection requires both checks and forbids self-merge.

### 2.4 Merge

A human merges to `main`. Nothing has touched the tenant yet.

### 2.5 `ship.yml` — the only path into production

Trigger: push to `main` with changes under `stories/**` (or `workflow_dispatch` with `slug`, `env`). Jobs `plan` → `staging` (only when the manifest defines `staging`) → `production`, the last under GitHub environment **`production`** (optional required reviewers = a second human gate before the tenant is touched). Environment secrets: `TINES_TENANT`, the key **named in the manifest** (`environments.prod.api_key_secret` — `TINES_API_KEY_PROD`, the **prod team-scoped key, Editor role**), which the job exports to the scripts as `TINES_API_KEY`, `OPS_ROUTER_URL`, `OPS_EMAIL_DL`. The job itself sets `TINES_ENV=prod` and `TINES_ALLOW_PROD=1`.

Per changed slug (skipping `_manifest.yaml` and `_template`):

```bash
./scripts/tines version-create <slug> --env prod --name "pre-ship <sha7>"
#   POST /api/v1/stories/{id}/versions                         — the rollback point
./scripts/tines import-draft <slug> --env prod --draft-name "git-<sha7>"
#   POST /api/v1/stories/import {data, team_id, folder_id, mode: "versionReplace", draft_name}
#   matches the existing story BY NAME; embedded sub-stories are not imported; MCP connections are dropped;
#   credentials and resources must already exist in the prod team by the same names (the job fails otherwise);
#   the draft id comes from the response — field name VERIFY (item 6)
./scripts/tines recipients-add <slug> --env prod --address "$OPS_ROUTER_URL" --draft <id> --via-draft
./scripts/tines recipients-add <slug> --env prod --address "$OPS_EMAIL_DL"   --draft <id> --via-draft
#   POST /api/v1/stories/{id}/recipients {address, draft_id}   — draft semantics VERIFY (item 7)
#   --via-draft: every prod id is in policies/never-touch.yml after its first ship; the write lands only in this draft.
#   The ops-* stories get their story.meta.yaml monitoring.recipients list instead (the DL, never the router).
./scripts/tines story-update <slug> --env prod --monitor-failures true --draft <id> --via-draft
#   PUT /api/v1/stories/{id} {monitor_failures: true, draft_id}
./scripts/tines cr-open <slug> --env prod --draft <id> --title "<slug> <sha7>" \
  --pr-url "<commit url>" --diff <file from ./scripts/diff-story.sh> --rollback-ref <previous sha>
#   POST /api/v1/stories/{id}/change_request {draft_id, title, description} — cr-open builds the description itself
#   (story · environment · commit SHA · PR URL · semantic diff · rollback ref; [--reason "…"] adds a line)
./scripts/tines cr-view <slug> --env prod --draft <id>
#   GET /api/v1/stories/{id}/change_request/view?draft_id=     — status + live_story_export vs draft_export → job summary
```

Then the change-request URL is posted as a commit comment and to the ops channel via `OPS_ROUTER_URL`. `sleep 1` between stories. A slug whose `prod.story_id` is still `0` (`new: true`) is **refused in prod**: a `mode: new` import would create a live story with no draft and no change request. Preferred: before the first ship, a person creates an empty, disabled, change-controlled story with the export's exact name in the prod team [BY HAND] and commits its id as `prod: { story_id: <id> }` (removing `new: true`), so the first ship is a `versionReplace` into a draft + change request. Otherwise an explicit, logged `workflow_dispatch` (`slug`, `env: prod`, `new_in_prod_reason: "<one sentence>"`) imports with `mode: new`, and the job opens a follow-up PR that records the id and removes `new: true` (once an environment has an id, `new: true` is ignored). A merge that touches only `stories/_manifest.yaml` does not trigger a ship, so after merging that PR run `ship.yml` by `workflow_dispatch` (`slug`, `env: prod`); that ship opens the change request. Prod ships run from `main` only. **`ship.yml` never promotes.**

### 2.6 Approve — a person, in Tines

The named approver opens the change request, reads the live-vs-draft diff and the PR, and **approves and pushes**. That is the default. No key in CI can approve.

### 2.7 Optional `promote.yml`

`workflow_dispatch` with `slug`, `change_request_id`, `draft_id`; environment `production`:

```bash
./scripts/tines cr-view <slug> --env prod --draft <id>          # assert change_request.status == "APPROVED", else fail: "approve in Tines first"
./scripts/tines cr-promote <slug> --env prod --change-request-id <id> --draft <id> --delete-draft
#   POST /api/v1/stories/{id}/change_request/promote {change_request_id, delete_draft: true}   — bypass_approval is NEVER passed here
#   (--draft is required: the status is re-read from …/change_request/view?draft_id= before promoting)
./scripts/tines version-create <slug> --env prod --name "release <sha7>"
```

A PENDING request is never promoted by any pipeline. `cr-promote` is **denied** in the IDE.

### 2.8 After promotion

The team change-control webhook (approved / pushed) hits the router → the ops thread shows the deployment. `drift.yml` (03:00 nightly) exports prod, diffs it against `main`, and — if they differ — attributes the change through `GET /api/v1/audit_logs` (`user_email`, `operation_name`, `source`, `request_user_agent`; MCP activity rows flagged) and opens a PR labelled `drift`. The next sweep baselines the story.

### 2.9 The change-control path in one line, and what the tenant needs

**builder in editor → `/mcp` edits the DEV story (drafts? VERIFY, item 2 — policy on regardless) → export → branch → PR → `lint.yml` + `review.yml` → CODEOWNERS → human merge → `ship.yml`: `POST /versions` → `POST /stories/import` (`versionReplace`, `draft_name git-<sha>`) → recipients + `monitor_failures` on the draft → `POST /change_request` → approver reads `GET /change_request/view` (`live_story_export` vs `draft_export`) and the PR → approves in Tines → pushes (or `promote.yml` on APPROVED) → live → `drift.yml` proves it that night.**

Tenant settings this path assumes ([BY HAND], once):

- Tenant policies **Enable by default** and **Require approval for all changes** — admins and owners included; the emergency bypass is audited.
- Story requirements (name, description, owners, tags, event retention) set to required.
- Team change-control webhooks (created / cancelled / approved / rejected / pushed) pointed at the router so approvals appear in the ops thread.
- Draft naming: `git-<sha>` (ship) · `rollback-<target>` (rollback) · `monitor-<finding_id>` (the monitor's apply sub-story).
- Per `DESIGN.md` §3.9: drafts go inactive after 30 minutes and lock on review request; test-mode credentials apply in drafts. Confirm both on a scratch story before relying on them for a live demo (VERIFY, items 2 and 7).

---

## 3. Push skills (tenant-side Agent Skills as code)

**Files:** `tines-skills/<name>/SKILL.md` · `.claude/rules/tines-skills.md` (path-scoped) · `.claude/skills/tines-skills-push/` · `.github/workflows/skills.yml` · `stories/ops-story-health-monitor/story.meta.yaml` (`ai.agents[].skills`).

1. Edit or add `tines-skills/<name>/SKILL.md`. Frontmatter: `name` = directory, lowercase-hyphen, ≤ 64 chars, no "anthropic"/"claude"; `description` ≤ 1024 chars, third person, says what **and** when (agents see only name and description); `license`; `compatibility`; `metadata` as flat strings. Body under 500 lines / about 5,000 tokens.
2. Preview:
   ```
   /tines-skills-push <name>            # validate + dry run against $TINES_TEAM_ID (create vs update)
   /tines-skills-push <name> --dev      # real push to the dev team; then run the dev sweep on a deliberately failing scratch story
   ```
   which runs `./scripts/tines skills-push --validate-only --only <name>` and `./scripts/tines skills-push --team $TINES_TEAM_ID --dry-run --only <name>`. The Agent Skills validator `skills-ref` is not run until its package is confirmed and pinned (never `npx --yes`; VERIFY item 21).
3. Open a PR. `lint.yml` validates the frontmatter; `review.yml` checks the body against `AGENTS.md`; CODEOWNERS for `tines-skills/` includes the security-platform group because a skill changes agent behaviour in production. A human merges.
4. **`skills.yml`** (push to `main`, paths `tines-skills/**`, environment `production`) runs `./scripts/tines skills-push --team <prod team id>`; per skill:
   - `GET /api/v1/skills/<name>?team_id=` → **200** ⇒ `PUT /api/v1/skills/<name>` (`team_id`, `description`, `body`, `license`, `compatibility`, `metadata` incl. `git_sha`, `repo_path`)
   - **404** ⇒ `POST /api/v1/skills {team_id, name, description, body, license, compatibility, metadata}`
5. **Renames:** change the directory and the frontmatter in one PR; the API rewrites the name in every AI Agent action that references the skill.
6. **[BY HAND, once — no API found, VERIFY item 14]:** attach the skill to the sweep's `triage` agent and enable it on the Ops Workbench preset; record it in `stories/ops-story-health-monitor/story.meta.yaml: ai.agents[].skills`.
7. **Delete** only by `workflow_dispatch` with `confirm_delete=<name>` → `DELETE /api/v1/skills/<name>?team_id=`. Removing the folder alone does nothing in the tenant.

Skill limits, versioning and credit consumption are unpublished (VERIFY, item 14).

---

## 4. Monitor and alert — Mode 3 (the agent) and Mode 4 (the exposed tools)

**Files:** `stories/ops-error-router/` · `stories/ops-story-health-monitor/` (`DESIGN.md`, `agent/system-instructions.md`, `agent/output-schema.json`, `agent/tools.md`, `resources/*.example.json`, `records/record-types.md`) · `stories/ops-tools-server/` · `policies/cost-ceilings.yml` · `policies/never-touch.yml` · `.github/workflows/propose-fix.yml` · `.claude/skills/tines-propose-fix/`.
**Editor features in the loop:** none by design — the pipeline never holds `/mcp`. The Mode 4 server is what an editor connects to when a human wants to ask the same questions.

### 4.1 Coverage — every production story reports to the router

Set by `ship.yml` from the manifest: recipients = the router webhook (`OPS_ROUTER_URL`) + the email DL (`POST /api/v1/stories/{id}/recipients`); story-level `monitor_failures: true` (`PUT /api/v1/stories/{id}`); "notify if no events emitted" on scheduled and ingress actions at about 2× the interval (`PUT /api/v1/actions/{id} {monitor_no_events_emitted}` — on a change-controlled story this needs a draft and a change request, VERIFY item 7). Tenant AI credit usage alerts and event-limit alerts also target the router (defaults 80/100 VERIFY, item 10; set in Admin → AI [BY HAND] — no API).

### 4.2 The signals

| Signal | Source | Direct or derived | Owner action when it fires |
|---|---|---|---|
| Action failure | Monitoring notification → router Webhook (payload shape VERIFY, item 9) | Direct | Story owner; the router enriches with the last level-4 log (`GET /api/v1/actions/{id}/logs?level=4`) and a severity class: 401/403 → owner (credential or permission) · 429 → back off · persistent 5xx → escalate · no events → silent source |
| Silent source | `monitor_no_events_emitted` notification; or the sweep sees no events beyond 2× interval | Direct or derived | Story owner: check the feed and the key |
| Failing run | `GET /api/v1/stories/{id}/runs` has **no status field** — derived from `not_working_actions_count`, `pending_action_runs_count`, level-4 logs and event counts | Derived (VERIFY, item 16) | Story owner |
| Coverage drift | `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true`: `monitor_failures: false` or empty `recipients` | Direct | Dev: auto-fixed. Prod: a proposal a person approves |
| Credit burn | `GET /api/v1/ai_usage?relative_date=today&group_by=story` vs `ops_limits.credit_budget_daily` | Direct | 80 %: digest by team/story with the costliest agents · 95 %: proposal to pause or reroute the costliest agent · 100 %: the platform stops the story — so 80 % is the actionable alert |
| Overlap | Run duration ≥ `overlap_ratio` × schedule interval | Derived | Lock or schedule change proposal |
| Stale lock | `ops_lock` older than `stale_lock_minutes` | Derived | Treated as free; reported |
| Dead-letter depth | `ops_dead_letter` Records | Direct | Story owner |
| Mode 4 server health | No `initialize` events over a window; tools nearing the 30-second ceiling | Derived | Ops role |
| Change-control events | Team webhooks (created/cancelled/approved/rejected/pushed) → router | Direct | Appear in the ops thread; nothing to do |

### 4.3 Router — `[OPS] 01 · Route monitoring alerts` (LIVE, one flow)

Webhook (respond 200 fast) → `normalize` → Trigger `classify_source` (story monitoring | AI credit usage alert | event-limit alert | change-control webhook) → dedupe per story + action + 15-minute window (Deduplicate mode or an `ops_alerts` Records check) → enrich (story link, action name/type, last level-4 log with credential `tines_api_readonly`, severity class) → Slack thread per story per day (channel from `ops_routing`) → write `ops_alerts` → **Send to Story into the sweep** when severity ≥ medium or count ≥ 3. Runs LIVE because monitoring is unavailable in TEST mode. Its own recipients are the email DL only, so the monitor is monitored.

### 4.4 Sweep — `[OPS] 10 · Monitor story health and credits` (cron `*/15`, plus a daily 06:00 branch)

1. Trigger `kill_switch` on `ops_limits.enabled == true`.
2. Compare-and-swap lock: `POST /api/v1/global_resources/<ops_lock>/replace {key: "lock", value: "<<STORY_RUN_GUID()>>", if_value: "free"}`; a **422** means already running — excluded from `log_error_on_status` and branched on to exit quietly; a lock older than `stale_lock_minutes` is treated as free (CAS semantics VERIFY, item 19).
3. Reads with the **Viewer-role** key `tines_api_readonly` (read-only by role — VERIFY, item 18): `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true&per_page=100` → `GET /api/v1/ai_usage?relative_date=today&group_by=story` → `GET /api/v1/stories/{id}/runs?since=` for scheduled stories.
4. **Deterministic pre-filter** (an Event Transform, no AI): error count vs `error_threshold_per_window`; `not_working_actions_count > 0`; `pending_action_runs_count` > baseline × 3; coverage gap; credits today ≥ 80 % / 95 % of the daily budget; overlap; silence beyond 2× interval; stale lock; Mode 4 health. **Only anomalous stories reach the agent; a healthy sweep costs zero credits.**
5. Coverage gap: in **dev** auto-fix (`POST /recipients`, `PUT /stories/{id}`); in **prod** a proposal (step 7).
6. **`triage`** — one AI Agent action, Task mode, temperature 0.2, timeout raised above the 30-second default, retries low; skills `story-health-triage` + `credit-budget-analyst`; **five read-only Send to Story tools** (`ops_get_error_logs`, `ops_get_story_export`, `ops_get_live_activity`, `ops_get_recent_runs`, `ops_get_ai_usage`), each with a Timeout Duration, each returning 3–5 fields, each with a structured error on its failure branch; output schema enforced (`agent/output-schema.json`). Rejected proposals from `ops_alert_proposals` are injected into the prompt **by the story**, not as a sixth tool. **No write tool exists on this agent.** A tool-less **`critic`** (fast model) re-reads `evidence[]` for high/critical and may only confirm or downgrade; disagreement sets `needs_human`.
7. A Trigger on **explicit schema fields** (`severity`, `proposed_change.kind`, `needs_human` — never confidence or prose):
   - `none` → `ops_findings` Record (with `meta.credits_used`, tokens, model) + thread reply.
   - `alert_rule` → `ops_alert_proposals` (pending) + Slack Block Kit approval **verified against `ops_responders`** → the **apply sub-story** (the only place the Editor-role `tines_api_ops` credential lives): `recipient` → `POST /recipients`; `monitor_*` → `PUT /actions/{id}` or `PUT /stories/{id}` into a draft → `POST /change_request` titled `monitor-<finding_id>` for the same approver; `token_threshold` / `credit_budget` → no API → a Case task (if Cases is entitled) or a Record + thread [BY HAND].
   - `story_config` → a GitHub issue with the diagnosis, `evidence[]` and an exact `/tines-build-story` prompt; when the kind is on the auto-PR allow-list (add `retry_on_status`/`emit_failure_event`; change a schedule; adjust a `DEFAULT()`) also `repository_dispatch` `tines-fix-proposal` → **`propose-fix.yml`** → `/tines-propose-fix` (headless, no MCP, `Edit(stories/**)` only) → PR labelled `ops-proposal` → lint, review, human merge, `ship.yml`, human approval in Tines.
   - `disable_action` → Slack approval (**two approvers in prod**) → `POST /api/v1/stories/{id}/disable` on the named story only, never a never-touch entry.
   - `credit_action` → 80 % summary; 95 % proposal to pause the costliest agent or route it to a custom provider.
8. Release the lock (`if_value` = the run's GUID) on the last action and on every failure branch. The sweep's own watchdog (1,800 s) pages the DL if it goes silent.

### 4.5 Alert-setting behaviour (agentic, human-approved)

Thresholds come from data; the agent fills `alert_rule_proposal`, never sets a threshold itself: watchdog = `watchdog_multiplier` (2) × the p95 inter-event interval of the entry or scheduled action (from `GET /api/v1/events?story_id=` and the runs list, stored daily in `ops_baselines`) · per-story credit budget = p95 of the last 7 days' `credits_used` × 1.5 · error threshold = max(3, 3 × median level-4 logs per window) · a recipient proposal whenever a new published story appears without the router. Approved proposals are applied deterministically into a draft + change request and mirrored into `story.meta.yaml` by the next `drift.yml` PR so the repo stays the truth.

### 4.6 What stays by hand (no API on current evidence)

- AI Agent **token thresholds** on the Status tab (Notify at `daily_tokens_notify`, Disable action at `daily_tokens_disable`).
- **Per-team credit allocation** and **credit-usage alert thresholds** in Admin → AI.
- **Record types** (`records/record-types.md` lists the six).
- Attaching a **skill** to an agent or a preset (item 14).
- Enabling **Send to Story** access; raising **event retention**; turning **change control** on for a new story.

### 4.7 The weekly digest (Monday branch)

Coverage (stories with `monitor_failures: false`, empty recipients, `actions_with_monitoring: 0`) · credits per team and per story vs `policies/cost-ceilings.yml` (from `ops_credit_ledger`) · credits per completed finding · top failing actions · dead-letter depth and age · pending change requests (`GET …/change_request/view` per production story) · MCP activity count from `GET /api/v1/audit_logs` (operation name VERIFY, item 17) · drift PRs opened — to Slack and to Records for a Dashboard. Audit logs themselves reach the SIEM through the native S3 export every 15 minutes, not through a story.

### 4.8 Mode 4 — the same questions from outside (`[OPS] 20 · Ops tools (MCP server)`)

One MCP server action exposing the five read sub-stories (**Tool hints: Read only** on every lookup) and two request tools, `request_alert_rule` and `request_disable` (default Destructive hint, so Claude clients prompt on every call; descriptions state what they do **not** do: "Does not disable. Posts an approval and returns approval_id."). Access control **With a Tines API Key**, members of the ops team; `Include headers` on; the caller's `META.headers.email` is written to `ops_alert_proposals.requester`. The on-call person connects Claude Desktop, Claude Code or Cursor:

```json
{ "mcpServers": { "ops-tools": { "url": "https://<your-tenant>.tines.com/mcp/<mcp-path>", "headers": { "Authorization": "Bearer <api-key>" } } } }
```

and asks "why is `[SEC] 01` failing"; a request tool posts to the same approval channel the sweep uses. One flow; no AI credits; 30-second tool ceiling (the lookups return well under it; anything slower returns `{status: started, id}` and a status tool). Test with `npx @modelcontextprotocol/inspector` and API Token Authentication before a real client. The sweep's `triage` may attach this server as its **one** MCP connection instead of the five Send to Story tools once stable — never both. Whether the editor can add the MCP server action itself through `/mcp` is VERIFY (item 25); if not, drag it on by hand and let the editor wire the tools.

### 4.9 Runbook — when the monitor itself is silent

1. The sweep's watchdog (`monitor_no_events_emitted: 1800` on the schedule action) pages the email DL — the DL, not Slack, because Slack may be the thing that broke.
2. `./scripts/tines live-activity --env prod --slug ops-story-health-monitor` → `not_working_actions_count`, `pending_action_runs_count`.
3. `./scripts/tines action-logs <schedule action id> --level 4` and `./scripts/tines runs ops-story-health-monitor --env prod --since <1h ago>`.
4. If the lock is stuck: `./scripts/tines resource-cas <ops_lock id> --key lock --value free --if-value <stuck guid>` (or wait `stale_lock_minutes`).
5. If `ops_limits.enabled` is `false`, someone threw the kill switch — check `policies/break-glass-log.md` and the ops thread before turning it back on.
6. If the router is the silent one, production failure notifications are still going to the email DL (every production story has both recipients); read the DL until the router is back.
7. Everything else: `06-rollback-and-recovery.md` §7.

---

## 5. Roll back

Summary only — the full procedure, including emergency containment, change-request rejection and silencing the monitor, is `06-rollback-and-recovery.md`.

```
/tines-rollback <slug> <git-sha|previous>       # prepares the PR that keeps main equal to what will be live
```

then a human runs **`rollback.yml`** with `slug`, `target`, `reason` (and `emergency: true` only for the break-glass job, which needs two reviewers and appends `policies/break-glass-log.md` in the same run). Rollback goes through the **same** import → draft → change request → human approval path as a ship.

---

## Appendix A — `./scripts/tines` subcommands and the endpoints behind them

| Subcommand | Endpoint | IDE permission |
|---|---|---|
| `export <slug> [--env] [--draft <id>] [--out]` | `GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true[&draft_id=]` → `normalize.jq` | allow |
| `import-draft <slug> --env [--file] [--draft-name]` | `POST /api/v1/stories/import {data, team_id, folder_id, mode: "versionReplace", draft_name}` (or `mode: "new"` + `new_name`) | ask |
| `cr-open <slug> --env --draft <id> [--title] --pr-url <url> --diff <file> --rollback-ref <sha> [--reason]` | `POST /api/v1/stories/{id}/change_request` (description from a fixed template: story · environment · commit SHA · PR URL · semantic diff · rollback ref; there is no `--description` option) | ask |
| `cr-view <slug> --env --draft <id>` | `GET /api/v1/stories/{id}/change_request/view?draft_id=` → `status` + jq diff of `live_story_export` vs `draft_export` | allow |
| `cr-promote <slug> --env --change-request-id --draft <id> [--delete-draft] [--bypass-approval --reason]` | `POST /api/v1/stories/{id}/change_request/promote`; `--bypass-approval` accepted only with `BREAK_GLASS=1` and `--reason` | **deny** |
| `version-create <slug> --env --name` · `versions-list` | `POST` · `GET /api/v1/stories/{id}/versions` (metadata only; no export-of-a-version endpoint found — VERIFY, item 12) | ask · allow |
| `recipients-add` · `recipients-remove <slug> --env --address [--draft <id> [--via-draft]]` | `POST` · `DELETE /api/v1/stories/{id}/recipients {address, draft_id?}` | ask |
| `story-update <slug> --env --monitor-failures true\|false [--draft <id> [--via-draft]] [--locked] [--from-manifest]` | `PUT /api/v1/stories/{id}` (`--via-draft`: a never-touch id, only inside this ship's or rollback's own draft) | ask |
| `action-update <slug> --env --action-id <id> [--monitor-no-events <s>] [--action-monitor-failures true\|false] [--action-monitor-all-events true\|false] [--draft <id>]` | `PUT /api/v1/actions/{id}` (`--monitor-failures` would be the *story*-level flag) | ask |
| `story-disable <slug> --env` | `POST /api/v1/stories/{id}/disable` (toggles; bypasses change control; the kill switch) | ask |
| `live-activity [--env] [--slug]` | `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true&per_page=100` or `GET /api/v1/stories/{id}?include_live_activity=true` | allow |
| `action-logs <action_id> [--level 4]` | `GET /api/v1/actions/{id}/logs?level=4` | allow |
| `runs <slug> --env [--since] [--summary <guid>]` | `GET /api/v1/stories/{id}/runs?since=` (+ `/runs/{guid}/summary`) | allow |
| `ai-usage [--relative_date \| --start_date --end_date] [--group_by story\|team\|action\|day] [--story-id]` | `GET /api/v1/ai_usage` → `credits_used`, `billed_cost`, tokens | allow |
| `audit --after <ts> [--story-id] [--operation-name]` | `GET /api/v1/audit_logs?after=&per_page=&page=` (client-side `story_id` filter; MCP operation name VERIFY, item 17) | allow |
| `skills-push --team <id> [--dry-run] [--only] [--delete --confirm]` | `GET`/`PUT`/`POST`/`DELETE /api/v1/skills…` | ask |
| `resource-cas <resource_id> --key --value --if-value` | `POST /api/v1/global_resources/{id}/replace` (422 = mismatch, current value printed) | — |

The dispatcher: base `https://$TINES_TENANT.tines.com`; `Authorization: Bearer $TINES_API_KEY`; `--env` resolves ids from `stories/_manifest.yaml`; prod refused unless `TINES_ALLOW_PROD=1` (CI sets it); backoff on 429; never prints the key; a 404 on a write means an underprivileged key and says so.

## Appendix B — Who holds which identity at which step

| Step | Identity | Can | Cannot |
|---|---|---|---|
| Build (1) | The builder's own Tines user through OAuth-only `/mcp` | Whatever that user can do in the dev team | Anything the user cannot; production (the hook blocks it) |
| Review (2.1–2.3) | Nobody — no MCP, no tenant credentials | Read the repo | Touch the tenant |
| Ship (2.5) | **CI-prod** — team-scoped key, Editor role, prod team | Import, tag versions, set recipients and monitor flags, open change requests | Approve |
| Promote (2.7) | CI-prod | Promote an **APPROVED** request | Approve; bypass |
| Approve (2.6) | A person, in Tines | Approve and push | — (never a key) |
| Drift (2.8) | **CI-read** — Viewer-role team key | Export, read audit logs, read AI usage | Write (VERIFY, item 18) |
| Monitor reads (4.4) | `tines_api_readonly` — Viewer-role team key, `allowed_hosts` = the tenant host, Workbench access off | Read | Write |
| Monitor apply (4.4 step 7) | `tines_api_ops` — Editor-role team key, only inside the apply sub-story, behind a verified approval | Recipients, monitor flags into a draft, change requests | Approve |
| Break-glass (5) | CI-prod under GitHub environment `break-glass` (two reviewers) | `POST /disable`; `cr-promote --bypass-approval` with a reason and a log line | Anything unlogged |

## Verify in your tenant before presenting

Walk workflow 1 end to end on a scratch story in the dev team before any demo: it exercises items 1, 2, 3, 5, 8 and 26 of `07-verify-before-you-rely-on-it.md`. Walk `ship.yml` once against the dev team (`workflow_dispatch` with `env: dev`) to confirm items 6 and 7 before pointing it at prod.
