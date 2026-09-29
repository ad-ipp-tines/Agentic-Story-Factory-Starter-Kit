# scripts/ — the one audited code path to the Tines API

_Tines Stories as Code · Builder: `ci` · Spec: `../DESIGN.md` §3.5 (scripts) and §3.4 (workflows) · Platform: **Tines Stories**._

Every call this repository makes against a Tines tenant goes through the scripts in this folder. Skills, hooks, the `/tines-*` procedures and the GitHub workflows all call the same code, so a security reviewer reads one place, permission rules in `.claude/settings.json` are per dispatcher subcommand, and the model never composes raw `curl` against a key.

**Python behind a bash dispatcher, with `normalize.jq` as the one normalisation rule.** `DESIGN.md` §3.5 specifies one bash+jq dispatcher plus `normalize.jq`. This build implements the subcommands in Python 3 (standard library plus `requests`; `PyYAML` for the manifest, meta and policy files). The DESIGN paths are kept as entry points so nothing else in the repository changes: `scripts/tines` dispatches to the Python scripts, and `scripts/lint-story.sh` and `scripts/diff-story.sh` are shims over `lint_story.py` and `diff_story.py`. **`scripts/normalize.jq` is the single definition of what normalisation removes** (`exported_at` today; keys sorted; every array — above all `agents[]`, which `links` reference by index — left in order). `export_story.py` pipes each export through it when `jq` is on PATH (`--normalizer auto`, the default) and writes the result with `dump_json` (sorted keys, two-space indent), so the committed bytes are identical whether jq or the Python fallback (`tines_common.normalize_export`, `exported_at` only) ran; it also refuses to write if the agent order changed. `lint-story.sh` re-applies `normalize.jq` to every export it lints and reports `not_normalised` for anything beyond `exported_at`, and `drift.yml` compares production with `main` only after both went through it. Add a volatile key to `normalize.jq` (after reading a real export — `docs/VERIFY.md` #8) and all three follow without a Python change.

## Requirements and environment

```
python3 -m pip install -r scripts/requirements.txt      # requests, pyyaml
cp .env.example .env && $EDITOR .env && source .env      # the scripts never read .env themselves
```

| Variable | Meaning | Where it lives |
|---|---|---|
| `TINES_TENANT` | Host prefix only (`<your-tenant>` in `https://<your-tenant>.tines.com`) | `.env` locally; a GitHub secret in CI |
| `TINES_API_KEY` | A **team-scoped** API key (Editor role) for the team you are talking to. Never a personal key. | `.env` (dev team); in CI the workflow reads the secret **named in the manifest** (`environments.<env>.api_key_secret`, e.g. `TINES_API_KEY_PROD`) and exports it as `TINES_API_KEY` |
| `TINES_ENV` | `dev` \| `staging` \| `prod` — the manifest environment | `.env`; the workflow sets it per job |
| `TINES_ALLOW_PROD` | `1` lets a script touch `prod`. Only environment-gated jobs set it: `ship.yml`, `skills.yml`, `promote.yml` and `rollback.yml` (environments `production` / `break-glass`) and `drift.yml` (environment `prod-read`, a Viewer-role key that only reads). The editor never does. | CI only |
| `BREAK_GLASS` | `1` lets `story-disable` touch a prod story and `cr-promote` accept `--bypass-approval`. Set only by `rollback.yml`'s break-glass jobs (environment `break-glass`); `promote.yml` and the `rollback` job force it empty; the IDE denies `Bash(BREAK_GLASS=1 *)`. | CI only |
| `TINES_TEAM_ID` / `TINES_FOLDER_ID` / `TINES_STORY_ID` | Optional overrides of the manifest ids | rarely; explicit CLI flags beat them |
| `OPS_ROUTER_URL` | The `ops-error-router` webhook URL — it carries a secret, so the manifest holds `${OPS_ROUTER_URL}` and this variable resolves it | `.env`; a GitHub environment secret |
| `OPS_EMAIL_DL` | The ops distribution list the manifest references as `${OPS_EMAIL_DL}` | `.env`; a GitHub environment secret |

Precedence for ids: explicit flag → environment variable → `stories/_manifest.yaml`. A manifest `0` is the committed placeholder and counts as unset.

No script prints a key. Progress goes to **stderr**; **stdout** is data (one JSON line per result), so the workflows and the `/tines-*` skills can chain them.

## The scripts

| Script | Purpose | Tines API calls (only those in `DESIGN.md`) | Dispatcher subcommand |
|---|---|---|---|
| `tines_common.py` | Shared client (`TinesClient`: Bearer auth, 429/5xx backoff, never prints the key, names a 404-on-write as an underprivileged key), manifest resolution, export normalisation, the secret-pattern list, SKILL.md frontmatter parsing | — | — |
| `export_story.py` | Export one story to `stories/<slug>/story.json`, normalise, stamp `exported_from` in `story.meta.yaml` | `GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true[&draft_id=]` | `export` |
| `import_story.py` | Import a committed export into a target team **as a change-control draft**; `--dry-run`; `--version-name` tags the rollback point first; a slug marked `new: true` is created with `mode: new` and `--record-id` writes the returned id into the manifest | `POST /api/v1/stories/{id}/versions` · `POST /api/v1/stories/import {data, team_id, folder_id, mode: versionReplace, draft_name}` (or `mode: new, new_name`) · `GET /api/v1/stories/{id}` (name check) | `import-draft` |
| `set_monitoring.py` | Recipients and monitor flags on a story or its draft: `--from-manifest`, `--add-recipient`, `--remove-recipient`, `--monitor-failures`, `--locked`, `--action-id --no-events-seconds` (the watchdog), `--watchdog-from-meta` | `POST` / `DELETE /api/v1/stories/{id}/recipients {address, draft_id?}` · `PUT /api/v1/stories/{id} {monitor_failures, locked, draft_id?}` · `PUT /api/v1/actions/{id} {monitor_no_events_emitted, monitor_failures, monitor_all_events, draft_id?}` | `recipients-add` · `recipients-remove` · `story-update` · `action-update` |
| `change_request.py` | `open` a change request on a draft (fixed description template: story · environment · commit · source URL · semantic diff · rollback ref); `view` prints the status and the live-vs-draft summary; `--require-status APPROVED` for `promote.yml`. **No promote subcommand exists.** | `POST /api/v1/stories/{id}/change_request {draft_id, title, description}` · `GET /api/v1/stories/{id}/change_request/view?draft_id=` | `cr-open` · `cr-view` |
| `story_version.py` | `create` a story version (rollback bookmark); `list` versions (metadata only — no export-of-a-version endpoint was found, VERIFY #12, so the git ref is the rollback source) | `POST` / `GET /api/v1/stories/{id}/versions` | `version-create` · `versions-list` |
| `ship_story.py` | The per-story chain `ship.yml` runs: semantic diff → version → import as draft → recipients + `monitor_failures` (+ `locked` for `locked_slugs`) on the draft → change request → view; JSON line per slug, Markdown summary, optional ops-router notification. **Never promotes.** | the calls above, through the scripts above | `ship` |
| `push_skills.py` | Tines Agent Skills as code: validate `tines-skills/<name>/SKILL.md` frontmatter and body, then upsert; `--validate-only` needs no tenant; `--dry-run` shows create vs update; `--delete NAME --confirm NAME` | `GET /api/v1/skills/{name}?team_id=` · `PUT /api/v1/skills/{name}` · `POST /api/v1/skills` · `DELETE /api/v1/skills/{name}?team_id=` | `skills-push` |
| `lint_story.py` | Deterministic convention checks over exports (+ meta), driven by `policies/lint-rules.yml`; `--format text|json|github`; `--strict` | none (no network) | `lint` (also `./scripts/lint-story.sh`, which adds the `normalize.jq` check) |
| `diff_story.py` | Semantic diff of an export against a git ref or a file: actions added / removed / renamed, changed option keys (secret-looking values redacted to a length), links, schedules, monitor flags, `disabled`; Markdown or JSON | none | `diff` (also `./scripts/diff-story.sh`) |
| `normalize.jq` | The one definition of normalisation: drop `volatile_top_level_keys` (`exported_at`), replace every action's ingress `options.path` / `options.secret` with `<assigned-on-import>` (by key name, never by action type; formulas and placeholders kept), sort keys, never reorder an array; refuses anything without `agents[]` | none | used by `export`, `lint-story.sh`, `drift.yml` |
| `tines_read.py` | Read-side helpers for the subcommands below: ISO or relative times (`15m`, `1h`, `2d`), baton-tolerant row extraction (VERIFY), `page`/`per_page` paging with a cap and a pause, secret scrubbing before anything is printed, bounded Markdown tables | — | — |
| `live_activity.py` | Coverage and live counters per published story; `--attention` = a not-working action, `monitor_failures` off, or no recipients. Recipients are shown as a **count** — the router URL carries a secret | `GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true&per_page=100` (paged) · `GET /api/v1/stories/{id}?include_live_activity=true` | `live-activity` |
| `action_logs.py` | One action's logs (default level 4), newest first, secret-looking spans redacted, a status-code category per row and the `{count, last_at, categories, sample_messages}` line the monitor's tool returns; `inbound_event` only with `--json --include-inbound-event` | `GET /api/v1/actions/{id}/logs?level=4` | `action-logs` |
| `story_runs.py` | A story's recent runs with `median_duration_s`, `max_duration_s`, `last_start`, in-flight count; `--summary <guid>`, `--events <guid>` (scrubbed). Never says "failed" — runs have no status field | `GET /api/v1/stories/{id}/runs?since=` · `…/runs/{guid}/summary` · `…/runs/{guid}` | `runs` |
| `ai_usage.py` | AI usage by story / team / action / day / feature, credits **and** `billed_cost`; `--check-ceilings` compares stories today, teams and tenant month to date, and agents' tokens today with `policies/cost-ceilings.yml` and writes a Markdown report (`drift.yml`'s budget job) | `GET /api/v1/ai_usage` (`relative_date` or `start_date`+`end_date`, `group_by`, `story_id`) | `ai-usage` |
| `audit_logs.py` | Audit rows after a time; `--story-id` filtered client-side (any `story_id` key in the row), `--operation-name` sent as `operation_name[]`, `--mcp-only` by heuristic until the operation name is known; `--format markdown` is the drift PR's attribution table | `GET /api/v1/audit_logs?after=&per_page=&page=` (≤ 1,000 req/min — paced) | `audit` |
| `story_disable.py` | The kill switch, made safe to call: reads the story's `disabled` flag and does nothing when it already matches `--want disabled|enabled` (the endpoint toggles); re-reads after the call; prod needs `BREAK_GLASS=1` and a reason; never-touch ids only under break-glass | `GET /api/v1/stories/{id}` · `POST /api/v1/stories/{id}/disable` | `story-disable` |
| `resource_cas.py` | Compare-and-swap one Resource key (the `ops_lock`, the `ops_limits.enabled` kill switch); a 422 is an answer (exit 3, detail printed), not an error; `--typed` sends JSON literals; refuses secret-looking values | `POST /api/v1/global_resources/{id}/replace {key, value, if_value}` | `resource-cas` |
| `promote_change_request.py` | Promote a change request **only when its status is APPROVED** (re-read from the view; the request id must match); **CI only**; `--bypass-approval` only with `BREAK_GLASS=1`, a reason, in `rollback.yml`'s `break-glass-promote` job | `GET …/change_request/view?draft_id=` · `POST /api/v1/stories/{id}/change_request/promote {change_request_id, delete_draft[, bypass_approval, bypass_approval_reason]}` | `cr-promote` |
| `break_glass_log.py` | Append one row to the table in `policies/break-glass-log.md` (append-only; role, never a name; refuses secret-looking text). Used by `rollback.yml`'s break-glass jobs in the same run | none (no network) | — (CI helper) |

### Read-side, kill-switch and promote subcommands — and their guards

| Subcommand | IDE rule (`.claude/settings.json`) | Guards in the script | Used by |
|---|---|---|---|
| `live-activity`, `action-logs`, `runs`, `ai-usage`, `audit` | **allow** | read-only; prod needs `TINES_ALLOW_PROD=1`; secrets scrubbed; recipients counted, never printed | `drift.yml` (audit, ai-usage), `/tines-rollback` and docs/06 (live-activity, runs), the runbook in docs/02 §4.9 |
| `story-disable` | **ask** | toggle made idempotent with `--want`; prod needs `BREAK_GLASS=1` + a reason; never-touch only under break-glass | `rollback.yml` jobs `break-glass` and `break-glass-re-enable` |
| `resource-cas` | **ask** | 422 → exit 3; no secret-looking values; prod guard | stale-lock and kill-switch runbooks; VERIFY #19 tests |
| `cr-promote` | **deny** (also direct calls of `promote_change_request.py` and any `BREAK_GLASS=1 …` command) | CI only (`GITHUB_ACTIONS=true`, checked in the dispatcher and the script); APPROVED only; bypass only in `rollback.yml`'s `break-glass-promote` job with `BREAK_GLASS=1` and a reason | `promote.yml`; `rollback.yml` job `break-glass-promote` |

The `GITHUB_JOB` / `GITHUB_WORKFLOW_REF` check on a bypass is defence in depth, not the control: the key that can bypass lives only in the GitHub environment `break-glass`, behind a second person.

## The ship path and change control

```
main merge ──▶ ship.yml ──▶ [staging team, if the manifest defines `staging`] ──▶ GitHub environment `production`
                                                                                   (required reviewers = manual approval)
                            per story:  version "pre-ship <sha>"
                                     →  POST /stories/import  {mode: versionReplace, draft_name: git-<sha>}
                                     →  POST /recipients + PUT /stories/{id} {monitor_failures: true}  (on the DRAFT)
                                     →  POST /change_request  {draft_id, title, description}
                                     →  GET  /change_request/view  → job summary, commit comment, ops router
                            STOP.  A named person approves in Tines (and pushes), or promote.yml on APPROVED.
```

- Nothing on the ship path promotes or sets `bypass_approval`. The only promoter is `promote_change_request.py` (`cr-promote`): CI only, an APPROVED request only, and `bypass_approval` only inside `rollback.yml`'s `break-glass-promote` job. `guard_prod` refuses `prod` without `TINES_ALLOW_PROD=1`; `set_monitoring.py` refuses story ids in `policies/never-touch.yml` unless the write lands in the caller's own draft (`--draft <id> --via-draft`, which `ship_story.py` and `rollback.yml` pass; `--via-draft` is refused without `--draft`); `import_story.py` refuses an export whose name differs from the live story (import matches **by name**) or that belongs to another team.
- Draft names: `git-<sha7>` for ships, `rollback-<target>` for rollbacks, `monitor-<finding_id>` for the ops pair.
- A story's first ship (`new: true` in the manifest) is a `mode: new` import; there is no draft to open a change request on. The workflow opens a follow-up PR that commits the returned id; the next ship opens the change request. Append the production ids to `policies/never-touch.yml` in that PR.
- Rehearse locally against the dev team: `./scripts/tines ship <slug> --env dev --dry-run`, then without `--dry-run`.

## Lint: what is enforced, and what is honest about the export shape

`lint_story.py` implements the rules `policies/lint-rules.yml` names. Every rule is tagged **confirmed** (its key was read on real exports: `agents[].type`, `options`, `monitoring.{monitor_all_events, monitor_failures, monitor_no_events_emitted, ai_monitoring_thresholds[]}`, `tools[]`, `options.output_structure`, `options.retry_on_status`, `links[] = {source, receiver}`, `diagram_notes[]`, `keep_events_for`, `recipients[]`, `send_to_story_*`, `CREDENTIAL.<name>` / `RESOURCE.<name>`) or **VERIFY** (the key was not observed: HTTP `retries`, `emit_failure_event`, `log_error_on_status`, the schedule shape, the MCP server action's type string and Tool-hint keys, a per-tool Timeout Duration). A VERIFY rule reports an informational or warning finding and is **capped at `warning` even when the policy file says `error`**, so nothing unconfirmed blocks a PR or a hook; `lint_story.py` prints which rules were capped. When one real export confirms a key, set it in the script, remove the `key: VERIFY` in the policy, and note it in `docs/VERIFY.md` #8.

Policy ids implemented under another name: `unique_action_names → unique_agent_names`, `agent_tool_cap → agent_tool_count`, `mode4_read_only_hints → mcp_server_tool_hints`. Policy ids with no implementation in the script: `http_failure_path_connected` (how failure links appear in `links[]` is VERIFY), `never_touch_targets` (enforced at write time by `set_monitoring.py` and `.claude/hooks/guard-mcp.sh`), `manifest_consistency` (checked by `lint.yml` directly).

What the lint does check that the brief asked for: the `[PREFIX] NN · Verb noun` naming and the `(sub)` contract (a message-only `result` Event Transform, an `error` shape); every AI Agent action has an output schema (`options.output_structure`), an enabled token-usage alert with Notify and Disable thresholds (`monitoring.ai_monitoring_thresholds[]`), a Trigger after it, at most five tools, a `story.meta.yaml` entry and a budget line in `policies/cost-ceilings.yml`; tool descriptions of at least three sentences and snake_case names; `block|delete|isolate|disable`-style tools must be `request_*`; MCP server action lookups marked Read only (VERIFY keys); no secret-looking strings and no real email addresses anywhere in the export; every `CREDENTIAL.` / `RESOURCE.` reference declared by name in meta; `tier: production` ⇒ `monitor_failures`, recipients, a watchdog, `keep_events_for` ≥ 30 days.

## The secret-pattern list

`tines_common.SECRET_PATTERNS` is the one list: `X-User-Token`, a literal Bearer/Basic token, `xox[abps]-`, `xapp-`, `AKIA…`, `sk-…`, `gh[pousr]_…`, a private-key block, an inline `api_key = "…"`. Placeholders (`Bearer <api-key>`, `<<CREDENTIAL.x>>`, `${VAR}`) pass. `lint_story.py` applies it to exports, `lint.yml` to every committed file under `stories/`, `tines-skills/` and `policies/` (plus gitleaks over the whole tree), and `.claude/hooks/block-secrets.sh` mirrors it in the editor. Change it in one place and the others by the same PR.

## The workflows (`.github/workflows/`)

The build brief names two of these "deploy" and "push-skills"; the files carry the `DESIGN.md` §2.2 names because every cross-reference in `README.md`, `AGENTS.md`, `docs/`, `stories/` and `tines-skills/` uses them.

| File (brief name) | Trigger | Identity / secrets | Does | Never does |
|---|---|---|---|---|
| `lint.yml` | every PR touching `stories/**`, `tines-skills/**`, `policies/**`, `.claude/skills/**`, `scripts/**`, `AGENTS.md` | none (read-only token; PyPI and the gitleaks image are the only network) | refuses committed `.env`/`.mcp.json`-class files · `jq empty` + no `exported_at` on every export · `lint-story.sh` on the exports the PR changes, with GitHub annotations (labelled `SKELETON` placeholders skipped) · manifest consistency · `skills-push --validate-only` · the shared conventions block vs `AGENTS.md` (skipped with a notice until `AGENTS.md` carries the markers) · the secret-pattern scan · gitleaks (the image pinned by digest in `GITLEAKS_IMAGE`; a custom rule for a Tines ingress `path`/`secret` in an export) · the semantic diff as a PR comment | call the tenant; run a model; `npx --yes` an unpinned package (the `skills-ref` validator waits for VERIFY #21 and a pinned version) |
| `review.yml` | same PRs, non-draft, same-repository only | `ANTHROPIC_API_KEY` **secret of the environment `review` — optional**, never a repository secret; with it absent the `gate` job reports skipped | one independent Claude Code instance runs `/tines-review <pr>` with `--allowedTools` read-only, `--max-turns` from `policies/cost-ceilings.yml`, `--setting-sources project` over the **base branch's** `.claude/` and `scripts/` (the PR checkout is data only), a 15-minute timeout, the findings schema inlined when present; posts one findings comment; passes only on `verdict: pass` from a run that succeeded (fails closed on an errored, timed-out or unparsed run) | hold an MCP server or a Tines credential; review a fork PR; load the PR's own reviewer, hooks or scripts |
| `ship.yml` (**deploy**) | push to `main` touching `stories/**`; `workflow_dispatch` (`slug`, `env`) | `TINES_TENANT`, the key **named in the manifest** for each environment (`secrets[<name>]`), `OPS_ROUTER_URL`, `OPS_EMAIL_DL` — GitHub environment secrets on `staging` / `production` | `plan` (changed slugs, secret names) → `staging` (only if the manifest defines it) → `production` (GitHub environment `production`: **required reviewers = the manual approval**) → `scripts/ship_story.py` per story → summary, commit comment, ops-router notification → follow-up PR for ids from a first import | promote; send `bypass_approval`; touch prod outside the `production` environment or from a ref other than `main`; create a `new: true` story in prod without the logged `new_in_prod_reason` dispatch input; put a hostname in a comment |
| `skills.yml` (**push-skills**) | push to `main` touching `tines-skills/**`; `workflow_dispatch` (`only`, `dry_run`, `confirm_delete`) — `main` only; every name validated against `^[a-z0-9]+(-[a-z0-9]+)*$` and passed through an env var, never interpolated into shell | the prod team's key named by `environments.prod.api_key_secret`; team id from the manifest or the variable `TINES_TEAM_ID_PROD` | validate → dry run (create vs update) → `PUT`/`POST /api/v1/skills` with `metadata.git_sha` → summary; deletion only with `confirm_delete=<name>` after the folder is gone from `main` | attach a skill to a preset or an agent (by hand, VERIFY #14) |
| `promote.yml` | `workflow_dispatch` (`slug`, `change_request_id`, `draft_id`, `env`, `release_sha`) — optional; the default is the approver pushing in Tines | CI-prod key named in the manifest, environment `production`; `BREAK_GLASS` forced empty | validate inputs (prod from `main` only) → `cr-view --require-status APPROVED` (fail: "approve in Tines first") → `cr-promote --delete-draft` (re-checks APPROVED itself) → `version-create "release <sha7>"` → summary + router | promote a PENDING / REJECTED / CANCELLED request; send `bypass_approval`; approve |
| `drift.yml` | nightly `0 3 * * *`; `workflow_dispatch` (`slug`, `after`, `skip_budget`) | CI-read: the Viewer-role key named by `environments.prod.read_key_secret` (`TINES_API_KEY_PROD_READ`), environment **`prod-read`** (no reviewers — it only reads; deployment branch `main`) | **drift:** `export --env prod --story-id --no-stamp` per slug with a prod id → both sides through `normalize.jq`, ship's `monitor_failures: true` (and `locked` for locked slugs) applied to main's side, every action's ingress `path`/`secret` excluded on both sides (by key name, any action type) → on a difference: `audit --after <main's last change, ≤ 30 days> --story-id` → the PR files scanned (secret patterns, ingress placeholders, gitleaks pinned by digest) before any push → one PR per story on `drift/<slug>` (label `drift`; re-runs update it; a branch carrying a person's commits is never overwritten) → router summary; fails the run if a prod export could not be read. **budget:** `ai-usage --check-ceilings` → one open issue labelled `budget` created or updated at ≥ 80 % | change the tenant; copy a production ingress path or secret (Webhook, MCP server action or any other) into git |
| `rollback.yml` | `workflow_dispatch` (`slug`, `target`, `reason`, `emergency`, `bypass_approval`, `re_enable`, `env`, `pr_url`) | `production`: CI-prod key; **`break-glass`**: its own secret of the same name (a key that can disable and, for bypass, holds STORY_MANAGE) — required reviewers + **Prevent self-reviews** | `plan` (target resolves and holds the story; `new: true` refused; prod from `main` only) → [`break-glass`: two-person check → `story-disable --want disabled` → router → a row in `policies/break-glass-log.md` committed on `break-glass/<slug>/<run>` + PR, same run] → `rollback`: `version-create "pre-rollback"` → `import-draft --file <target's story.json> --draft-name rollback-<target7>` → `story-update --from-manifest --monitor-failures true` on the draft → `cr-open "ROLLBACK <slug> to <target7>"` → `cr-view` → router → [`break-glass-promote` (only with `bypass_approval`): APPROVED → normal promote; otherwise `cr-promote --bypass-approval --reason` → a log row] · `re_enable: true` runs only `break-glass-re-enable` (`story-disable --want enabled` → a log row) | bypass anything outside the break-glass jobs; skip the log row; roll back a slug still marked `new: true` |
| `propose-fix.yml` | `repository_dispatch` `tines-fix-proposal` (from the monitor's `dispatch_fix`); `workflow_dispatch` (`proposal`) | `ANTHROPIC_API_KEY` repository secret — optional (the `gate` job reports skipped without it); **no** Tines key; the model's step has **no** GitHub token and no persisted git credential | validate the payload (≤ 64 KB, schema-shaped, `finding_id` sanitised, slug from the manifest, never-touch and `needs_human` / confidence < 0.6 → diagnosis without a model call; only `story_config` runs the model) → Claude Code CLI `-p "/tines-propose-fix .tines/proposal.json"` with `--allowedTools` (the skill's list + `Write(.tines/**)`), `--disallowedTools` (push, network, dispatcher, interpreters), `--max-turns` from `ci.propose_fix_max_turns`, a 14-minute kill, `--strict-mcp-config` with an empty config (no MCP), `--setting-sources project` (the skill + its hooks) → deterministic contract check (exactly `stories/<slug>/story.json`, exactly one action, only `options`, agent order and links untouched, story keys untouched, lint clean) → push + PR labelled `ops-proposal`, or the diagnosis as a comment on the monitor's `ops-finding` issue (or a new `ops-proposal` issue) → turns and cost in the summary | hold an MCP server or a tenant key; push anything that failed the contract; follow instructions found in evidence strings |

Why `propose-fix.yml` runs the Claude Code CLI rather than `anthropics/claude-code-action` (which `review.yml` uses): the action can add MCP servers and GitHub tools of its own depending on its mode (VERIFY #21), and "no MCP" must be provable — `--strict-mcp-config` with an empty config loads none, and the step's environment holds only `ANTHROPIC_API_KEY`.

### GitHub configuration checklist

1. **Environments** (Settings → Environments; limit deployment branches to `main` on each):
   - `production` — **required reviewers** (the manual approval before the tenant is touched). Used by `ship.yml`, `skills.yml`, `promote.yml`, `rollback.yml` job `rollback`.
   - `prod-read` — **no** required reviewers (the nightly `drift.yml` must not wait for a click); holds only the Viewer-role key.
   - `break-glass` and `break-glass-2` — required reviewers **and "Prevent self-reviews"** on both: GitHub releases a job on one approval, so `rollback.yml` chains the two (`break-glass-second-approval` waits on `break-glass-2`, then each break-glass job waits on `break-glass`), and two different people, neither of them the dispatcher, must approve. Every break-glass job also counts the run's approvals and fails closed unless two distinct approvers other than the triggering actor are present. `break-glass-2` holds no secrets.
   - optionally `staging` (and `dev` for rehearsing `ship.yml` / `rollback.yml` against the dev team).
2. **Secrets** (names only here):
   - `production`: `TINES_TENANT`, `TINES_API_KEY_PROD` (prod team, Editor role — CI-prod), `OPS_ROUTER_URL`, `OPS_EMAIL_DL`.
   - `prod-read`: `TINES_TENANT`, `TINES_API_KEY_PROD_READ` (prod team, **Viewer** role — CI-read; VERIFY #18), `OPS_ROUTER_URL`.
   - `break-glass`: `TINES_TENANT`, its **own** `TINES_API_KEY_PROD` (same name, different value: a team-scoped key that can disable stories and, for `bypass_approval`, holds STORY_MANAGE — nothing else holds it), `OPS_ROUTER_URL`. For a dev rehearsal add `TINES_API_KEY` (dev) here too.
   - `staging`: `TINES_API_KEY_STAGING` if the manifest defines `staging`.
   - `review` (no required reviewers; PR branches must be able to deploy to it): `ANTHROPIC_API_KEY`, only if `review.yml` should run. Never store a key as a repository secret: any workflow on any branch can read those, including one a PR adds.
   - Repository: `ANTHROPIC_API_KEY` only if `propose-fix.yml` should run (it reads the repository scope; it runs on the default branch only).
   Keys are created by `API_KEY_CREATE` holders, team-scoped, rotated quarterly, never personal. No approver key exists in CI — approval happens in Tines, by a person.
3. **Variables:** `TINES_TEAM_ID_PROD` if the manifest still carries `team_id: 0`.
4. **Labels** (the workflows create them if missing): `drift`, `budget`, `break-glass`, `ops-proposal`; the monitor's own issues use `ops-finding`.
5. **Branch protection on `main`:** require `lint` (and `review` when enabled), require a CODEOWNERS review (`.github/CODEOWNERS`), forbid self-merge. PRs opened by a workflow with `GITHUB_TOKEN` (drift, break-glass log, ops-proposal, manifest follow-ups) do not trigger `lint.yml` / `review.yml` by themselves: push an empty commit from a person or use a GitHub App token.
6. **Tenant side, once:** change-control policies **Enable by default** and **Require approval for all changes** on; credentials and resources created by the same names in every team; `OPS_ROUTER_URL` pointing at the LIVE `ops-error-router` story; the monitor's `github_dispatch` credential allowed to call `repository_dispatch` on this repository.

## VERIFY items these scripts depend on (`docs/VERIFY.md`)

| # | Assumed here | Confirm | Then change |
|---|---|---|---|
| 6 | `POST /api/v1/stories/import` returns the draft id as `draft_id`, `story_draft_id` or `draft.id`; `data` is accepted as an object; a missing credential fails with a message naming it | Import a scratch export into a change-controlled dev story with `--draft-name`; read the response | `import_story._find_draft_id`, `--data-as-string` default, `ship_story.py` failure text |
| 7 | `POST /recipients` and `PUT /stories/{id}` with `draft_id` land in the draft and go live on promotion | Apply both on a scratch story with change control on | `set_monitoring.py` docstring; the ship order |
| 8 | Export key names for HTTP retries / `emit_failure_event` / `log_error_on_status`, the schedule shape, the MCP server action type and Tool-hint keys | Read one real export of each action type | `lint_story.py` VERIFY rules, `policies/lint-rules.yml` `key:` markers |
| 12 | No export-of-a-version endpoint | Versions API on a scratch story | `story_version.py`; `rollback.yml` target options |
| 14 | `metadata` on `POST`/`PUT /api/v1/skills` accepts `git_sha` and `repo_path`; no attach API | Push one skill to a scratch team | `push_skills.py` metadata stamp; `skills.yml` summary text |
| 21 | `anthropics/claude-code-action@v1` inputs (`anthropic_api_key`, `prompt`, `claude_args`, `allowed_bots`) and output (`execution_file`); the inline `--json-schema` form; `npx skills-ref validate` availability | One PR with `ANTHROPIC_API_KEY` set | `review.yml` parsing step; `lint.yml` skills-ref step |
| 16 | `end_time` is null while a run is in flight; `duration` is in seconds; the live-activity fields sit on each story (or in a nested object — both are read) | `./scripts/tines runs <slug> --env dev --since 15m` during a run; `live-activity --json` | `story_runs.run_stats`; `live_activity._pick` |
| 17 | The MCP-activity `operation_name`; where a story id appears in an audit row (any `story_id` key is matched); `operation_name[]` accepted server-side | `./scripts/tines audit --after <session start> --json` after a `/tines-build-story` session | `audit_logs.is_mcp` (replace the heuristic), `--operation-name` in `drift.yml`, docs/VERIFY.md E6 |
| 18 | A Viewer-role team key reads exports, audit logs and AI usage, and cannot write | Run `drift.yml` by hand; attempt `story-update` with the Viewer key (expect 404) | `prod-read` secrets; `drift.yml` fallbacks |
| 19 | `/replace` compares `if_value` and returns 422 with the current value; typed vs string comparison | `./scripts/tines resource-cas <scratch id> --key lock --value a --if-value free` twice | `resource_cas.py` `--typed` default; the lock sub-story |
| 27 | List pagination: `meta.next_page` (followed when present), else a short page ends the walk | `live-activity --json` on a tenant with > 100 published stories | `tines_read.fetch_pages` |
| E4 | `GET /api/v1/stories/{id}` exposes `disabled`, so the toggle can be made idempotent; `POST …/disable` takes no body | `./scripts/tines story-disable <scratch> --env dev` twice, then `--want enabled` | `story_disable.read_disabled`; drop the "state unknown" branch |
| E5 | `ai_usage` baton and row keys (`story_id`/`story_name`, `team_id`/`team_name`, `action_name`, `input_tokens`/`output_tokens`), `YYYY-MM-DD` dates, the time zone of `today` | `./scripts/tines ai-usage --relative_date today --group_by team --json` | `ai_usage.py` row keys and team matching; add `team_id:` to `policies/cost-ceilings.yml` teams if names do not match |
| E6 | `audit_logs` baton; `created_at` on rows | as #17 | `audit_logs.shape` |
| E7 | Where the view response carries `status` and the request id; the promote response body; `bypass_approval` needs STORY_MANAGE | `promote.yml` against a scratch story in `dev` after approving in Tines | `promote_change_request._cr_id_in`; the `break-glass` key's role |
| E8 | Claude Code CLI flags used headless: `--strict-mcp-config` with an inline empty `--mcp-config`, `--setting-sources project`, path-scoped `Edit(stories/**)` / `Write(.tines/**)` in `--allowedTools`, the `--output-format json` result fields | `workflow_dispatch` of `propose-fix.yml` with a sample proposal on a scratch story | `propose-fix.yml` flags and the cost summary |

## Local runs

Read-only (allowed in the IDE):

```
export TINES_TENANT=<your-tenant> TINES_API_KEY=<team-scoped-dev-key> OPS_ROUTER_URL=<router-url>
./scripts/tines live-activity --attention                        # coverage gaps and not-working actions, dev team
./scripts/tines action-logs <action_id> --limit 5                # level-4 errors, secrets redacted
./scripts/tines runs <slug> --env dev --since 1h                 # durations and counts (no status field exists)
./scripts/tines ai-usage --relative_date today --group_by story  # credits and billed_cost
./scripts/tines ai-usage --check-ceilings --report-file .tines/budget.md    # what drift.yml's budget job does
./scripts/tines audit --after 24h --story-id <id> --format markdown         # what drift.yml's attribution does
./scripts/tines lint stories/                                    # every export, policy-driven
./scripts/tines diff stories/<slug>/story.json --against HEAD~1  # what changed, semantically
```

Dry runs of writes (ask in the IDE; nothing sent):

```
./scripts/tines import-draft <slug> --env dev --dry-run          # the import call, printed, not sent
./scripts/tines ship <slug> --env dev --dry-run                  # the whole chain, printed, not sent
./scripts/tines story-disable <slug> --env dev --dry-run         # reads the state, prints the toggle
./scripts/tines resource-cas <id> --key lock --value free --if-value <guid> --dry-run
./scripts/tines skills-push --validate-only                      # frontmatter and bodies only
./scripts/tines skills-push --team "$TINES_TEAM_ID" --dry-run    # GET only; create vs update per skill
```

Reads still go out in a dry run (the live-story name check, the skills `GET`, the disable state); writes are printed and skipped. `cr-promote` has no local form: it refuses outside GitHub Actions.
