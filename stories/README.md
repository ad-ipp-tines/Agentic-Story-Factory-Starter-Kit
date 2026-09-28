# `stories/` — Tines Stories as code

_Scaffold `tines-stories-as-code` · builder `stories` · spec `../DESIGN.md` §3.6 · created 2026-09-24 · platform **Tines Stories** (Tines Classic)._

**This folder is the truth.** A story exists in this repository as a normalised JSON export plus the facts the export does not carry. The tenant is a deployment target; the file in this folder is what gets diffed, reviewed, shipped, rolled back and drift-checked every night. Nothing here is edited by hand and nothing here holds a secret.

## Layout — one folder per story

```
stories/
├── README.md                    ← this file: the folder shape and the lifecycle of story.json
├── _manifest.yaml               ← environments + slug → story_id map (no secrets, no hostnames)
├── _template/                   ← copy this for every new story
├── example-enrich-ip/           ← [SEC] 01 · Enrich IP (sub) — the worked example every builder copies
├── ops-error-router/            ← [OPS] 01 · Route monitoring alerts — the single monitoring recipient (DESIGN.md §3.6)
├── ops-story-health-monitor/    ← [OPS] 10 · Monitor story health and credits — the agentic sweep (Mode 3)
└── ops-tools-server/            ← [OPS] 20 · Ops tools (MCP server) — the same lookups exposed to editors (Mode 4; DESIGN.md §3.6)
```

Every story folder holds the same core set. Optional sub-folders exist only where the story needs them (the ops stories do).

| File | What it is | Who writes it |
|---|---|---|
| `story.json` | The **normalised export** of the story: `GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true` piped through `scripts/normalize.jq`. Credentials, Resource contents and events are excluded by Tines; recipients are cleared on export and re-applied from the manifest on ship. | `/tines-export` only. Never a person, never a model editing JSON. |
| `story.meta.yaml` | The environment-independent facts the export does not carry: mode badge, tier, owner, credentials and Resources **by name**, Record types, AI Agent actions with their token alerts and budget refs, monitoring intent, the schedule interval, and where the export came from. Lint, ship, the reviewer and the ops sweep all read it. | The builder, at export time (`/tines-export` stamps `exported_from`). |
| `README.md` | Purpose (matches the on-canvas Note) · **mode badge** · entry and expected input fields · output (the `result` shape) · failure shape · credentials and Resources by name · monitoring · test event · runbook · **change log** (`sha → what`). | The builder. |
| `tests/sample-event.json` | One sample event for the entry action. Documentation-range values only (`203.0.113.0/24`, `*.example.invalid`). | The builder. |
| `tests/expectations.yaml` | What a run on the sample must produce: entry action, minimum actions fired, actions that must log no errors, the `result` fields. The build skill asserts these against the run's events. | The builder. |
| `agent/` (optional) | For a story with an AI Agent action: `system-instructions.md`, `output-schema.json`, `tools.md`. The canvas holds copies; these files are the reviewed source. | The builder. |
| `resources/` (optional) | `*.example.json` shapes for the Resources the story reads. Real values are set in the tenant and never committed. | The builder. |
| `records/` (optional) | `record-types.md` — the Record types the story needs, field by field. Record-type creation is [BY HAND]. | The builder. |
| `samples/` (optional) | Payloads captured once from the tenant (a monitoring notification, a webhook body) that a `normalize` action is written against. | The builder, once, from a deliberate LIVE test. |
| `DESIGN.md` (optional) | An in-repo design for a story complex enough to need one (the ops sweep carries `../DESIGN.md` §5). | The builder. |

**Change log convention:** the last section of each story's `README.md` is `## Change log`, one line per shipped change: `<short sha> · <date> · <what changed> · <change_request_id>`. There is no separate changelog file (DESIGN.md §3.6); the git history of `story.json` is the authoritative record and the README line is the human index into it.

## What `story.json` contains — and does not

Sample-first facts, read from real exports (`schema_version` 28–30) rather than assumed:

- **Top-level keys** include `name`, `description`, `guid`, `slug`, `schema_version`, `agents[]`, `links[]`, `diagram_notes[]`, `sections[]`, `send_to_stories[]`, `keep_events_for` (seconds: `604800` = 7 days), `monitor_failures`, `recipients[]`, `send_to_story_enabled`, `send_to_story_access`, `send_to_story_timeout_enabled`, `send_to_story_timeout_duration_seconds`, `entry_agent_guid`, `exit_agent_guids[]`, `diagram_layout` (a JSON *string*), `exported_at` (removed by `normalize.jq`).
- **Links reference agents by index** — `{"source": 0, "receiver": 6}`. This is why `normalize.jq` preserves agent order, why a removed or reordered action silently rewires the story, and why `story.json` is never hand-edited.
- **Every action** carries `type`, `name`, `description`, `guid`, `disabled`, `options`, `monitoring: {monitor_all_events, monitor_failures, monitor_no_events_emitted}`, `schedule`, `reporting`, `template`, `width`.
- **The AI Agent action** exports as `Agents::LLMAgent` with `options.mode: "task"`, `options.instructions`, `options.prompt`, `options.output_structure` (the output schema — a JSON Schema object), optional `options.reasoning_effort`, `options.code_analyst_enabled`, `options.web_search_enabled`; attached tools sit in a top-level `tools[]` array of action-shaped objects; the Status-tab token alerts export as `monitoring.ai_monitoring_thresholds[]` with `threshold_type: notify | disable_action`, `enabled`, `threshold`, `period: daily | weekly | monthly`, `metric: token`.
- **HTTP Request actions** export `options.url`, `method`, `content_type`, `payload`, `headers`, `retry_on_status` (an array of strings, e.g. `["429"]`), optional `timeout` and `local`. The keys for the retry count, `emit_failure_event` and `log_error_on_status` / `log_error_if` were **not observed** in the samples — **VERIFY** against your first real export, then set them in `scripts/lint_story.py` (the key names are hard-coded there; `lint-story.sh` is a shim over it) and change the rule's `key:` in `policies/lint-rules.yml`, which documents keys but does not supply them.
- **Event Transform** `options.mode` values observed: `message_only`, `automatic`, `delay`; **Trigger** `options.rules[]` with `type` values observed: `field==value`, `field>value`, `in`, `regex`; **Send to Story** action `options.story: "<< STORY.<slug> >>"` plus `payload`; a **Webhook** action's `options.path`, `secret`, `verbs`; a **Note** is `diagram_notes[] {content, position, guid, width}`.
- **References use the `<<CREDENTIAL.name>>` / `<<RESOURCE.name>>` form** in observed exports; the `{{ .CREDENTIAL.x }}` form named in DESIGN.md §3.5 is **VERIFY** — treat both as reference patterns in `lint-story.sh` until one is confirmed.
- **Excluded by design:** credential values, Resource contents, events, MCP connections (re-created after import), recipients (cleared by `clear_recipients=true`).
- ⚠ **In the raw export, and never committed:** a Webhook action's `path` and `secret` *are* in the export (observed), and so is an MCP server action's `path`. `scripts/normalize.jq` (and its Python mirror) replaces `options.path` and `options.secret` on **every** action that carries them — by key name, never by action type — with `<assigned-on-import>` before anything is written, so the router URL, the approval callback and the Mode 4 path never reach git. `lint_story.py` reports any real value that survives as `webhook_secret_in_export` (severity **error**), `lint.yml` adds a matching gitleaks rule, and `drift.yml` strips the same keys before a drift PR. Whether an import into an existing story keeps that story's own path and secret is VERIFY #6; if stable production URLs are needed, keep them in GitHub environment secrets and re-apply them at ship time — never in the export.

## The lifecycle of `story.json`

```
 build in the DEV team through the Tines Stories MCP server  (Mode 2, /tines-build-story)
      │  Validate + test event; by-hand steps the skill names
      ▼
 /tines-export <slug>   →   GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true
      │                      | scripts/normalize.jq  →  stories/<slug>/story.json
      │                      ./scripts/lint-story.sh   (the PostToolUse hook runs it again on every write)
      │                      story.meta.yaml: exported_from = {env, story_id, draft_id, at, sha}
      ▼
 branch story/<slug>/<short> → commit → /tines-review (fresh context) → PR
      │  lint.yml (no model) · review.yml (independent instance, no tenant) · CODEOWNERS · human merge
      ▼
 ship.yml (GitHub environment `production`)
      │  POST /api/v1/stories/{id}/versions                       ← rollback point
      │  POST /api/v1/stories/import {mode: versionReplace, draft_name: git-<sha>}
      │  POST /api/v1/stories/{id}/recipients {address, draft_id}  ← from the manifest
      │  PUT  /api/v1/stories/{id} {monitor_failures: true, draft_id}
      │  POST /api/v1/stories/{id}/change_request {draft_id, title, description}
      ▼
 a named approver reads GET …/change_request/view?draft_id= in Tines and approves — and pushes,
 or a human runs promote.yml, which promotes ONLY a request whose status is APPROVED (never bypass)
      ▼
 live   →   drift.yml exports prod nightly, diffs it against main, attributes any change via the audit logs
            and opens a drift PR; the ops sweep baselines the story on its next runs
```

Rollback is the same path in reverse (`/tines-rollback`, `rollback.yml`): a git ref → import as a draft named `rollback-<target>` → change request → human approval. Emergency containment is `POST /api/v1/stories/{id}/disable`, only from `rollback.yml`'s `break-glass` job, always logged in `policies/break-glass-log.md`.

## Rules that apply to every folder here

1. **Never hand-edit `story.json`.** Change the story through the Tines Stories MCP server with `/tines-build-story`, then `/tines-export`. Links are index-based; `guid`, `links`, `diagram_layout` and agent order are never touched by a person or a model.
2. **Names are identical in every environment.** `POST /api/v1/stories/import` with `mode: versionReplace` matches the existing story **by name**; `story.json.name` must equal `story.meta.yaml.name`, and `lint.yml` checks it.
3. **Credentials and Resources by name only.** They must pre-exist in every target team under the same names (created [BY HAND] with `allowed_hosts`); `story.meta.yaml` lists them; the reviewer refuses a story that references one it does not list; a value anywhere in this folder is a stop-and-report.
4. **One story per branch and per PR.** Embedded sub-stories are not imported; each sub-story is its own folder, its own slug and its own PR.
5. **Sub-stories end in `(sub)`** and finish on a message-only Event Transform named `result` emitting 3–5 fields; the failure path returns `{status, error_category, retryable, message}`; the description of any tool built on the sub-story documents the output shape, because tool responses carry no output schema.
6. **A Note on every canvas** states purpose and mode badge; the README's Purpose paragraph matches it.
7. **Monitoring is configuration, not hope.** `tier: production` ⇒ `monitor_failures: true`, recipients from the manifest, a no-events watchdog on the entry or scheduled action at ≈ 2× its interval, `keep_events_for` ≥ 30 days.
8. **Every AI Agent action** has an output schema, a Trigger after it on an explicit schema field, a token alert on the Status tab (recorded in meta), a `tines-skills/` attachment noted, and a line in `policies/cost-ceilings.yml`.
9. **Test data is fictional.** `203.0.113.0/24`, `198.51.100.0/24`, `*.example.invalid`, ids `0` until first ship.
10. **The ops stories are never-touch.** `ops-*` slugs are `locked: true` in prod, listed in `policies/never-touch.yml`, and changed only through their own change requests.

## Stories in this tree

| Slug | Name | Mode badge | Tier | Descends from | Status in this scaffold |
|---|---|---|---|---|---|
| `example-enrich-ip` | `[SEC] 01 · Enrich IP (sub)` | sub-story (also a Mode 3 tool and a Mode 4 tool) | production | Library 87626 | Design + skeleton written; `story.json` is a labelled SKELETON until the first `/tines-export` |
| `ops-error-router` | `[OPS] 01 · Route monitoring alerts` | none (LIVE intake) | ops | Library 1231438 | Design + skeleton written; `story.json` is a labelled SKELETON until the first `/tines-export`; `samples/monitoring-payload.sample.json` is a placeholder until captured by a deliberate LIVE failure (VERIFY #9) |
| `ops-story-health-monitor` | `[OPS] 10 · Monitor story health and credits` | **Mode 3** (AI Agent action, Task mode, Tines tools) | ops | — (built from `DESIGN.md`) | Design + skeleton written; `story.json` is a labelled SKELETON until the first `/tines-export` |
| `ops-tools-server` | `[OPS] 20 · Ops tools (MCP server)` | **Mode 4** (MCP server action) | ops | Library 1324549 for reference only (Seeds folder) | Design + skeleton written; `story.json` is a labelled SKELETON until the first `/tines-export`; no `tests/` by design — tested with the MCP Inspector session in its README |

A slug in `_manifest.yaml` with `story_id: 0` has not been shipped. A new story's **dev** id is recorded by hand right after the builder creates it through `/mcp` (nothing else writes it; `/tines-export` stops on `0`). Its **prod** id: preferably a person creates an empty, disabled, change-controlled shell story in the prod team [BY HAND] and commits its id (removing `new: true`), so the first ship is a draft + change request; a `mode: new` import into prod is refused unless `ship.yml` is dispatched with an explicit, logged `new_in_prod_reason`, and then the returned id is committed by the follow-up PR the job opens.

## Verify in your tenant before presenting

Nothing below is a headline claim; each item is tracked in `../docs/VERIFY.md`.

- The export key names for the HTTP retry count, `emit_failure_event`, `log_error_on_status` / `log_error_if`, the schedule shape on a scheduled action, the Records action type, how a failure-path link is represented, and how a Send to Story tool declares its parameters — read one real export first.
- Whether `/mcp` edits on a change-controlled dev story land as drafts (and whether `?draft=<name>` is needed to post the test event).
- The `POST /api/v1/stories/import` response field that carries the draft id.
- Whether Send to Story sub-stories used as tools count as flows (account team).
- Whether the Tines Stories MCP server can create Record types (assumed not — [BY HAND]).
- The credential and Resource reference syntax in your tenant's exports (`<< >>` observed; `{{ }}` named in DESIGN.md).
