# Pivot: Tines Storyworks → the 3B Workflow Factory

_Branch `pivot/3b-workflow-factory`. Status: foundation in review (issue #4). A behaviour is a fact here only when `3b/CURSOR-PROMPT.md` states it. Anything else is **VERIFY** until a 3B space confirms it and task #19 records that in `docs/VERIFY.md`. Nothing marked VERIFY is a headline claim._

## Thesis

The value is the system around the prompt. That sentence does not belong to one product.

Anyone can ask a model to build a workflow. The prompt is the cheapest part. What makes the result fast, controlled and safe is the system the prompt sits inside: a procedure the model follows every time, one conventions file, an artifact that diffs in git, deterministic lint, a reviewer that is not the author, hooks, a human gate on what goes live, an ops pair that proposes and never acts, and a VERIFY ledger.

On Tines Stories that system is this repository: `stories/**/story.json`, the Tines Stories MCP server (Mode 2), change control, and `AGENTS.md`. On 3B the same system stands, and two things change:

- **The wire.** Agents connect through the 3B MCP server, the 3B CLI, or the in-product editor. This repository does not call that connection a mode. "Mode" stays the word for the four Tines Stories MCP surfaces only.
- **The artifact.** A workflow is a directory of files. There is no export and no normalise step. The directory is already the thing git reviews.

Roughly the lifecycle, the gates, the crew shape, the policies, the evals, the tracker and the VERIFY discipline carry over. The Stories tree stays in this repository until a later task replaces it. This document is the map. It does not perform the replacement.

## What a 3B workflow is

These are the facts the rest of the pivot is allowed to rely on.

- A workflow is a folder: `workflow.toml` (it has an `id`; preserve that id; never copy it onto another workflow), a root `README.md`, and one directory per step.
- A step directory holds `config.toml`, a `Dockerfile` whose first line is `FROM 3b/base`, the step's code, and a `README.md`.
- Step templates are shell, python, typescript (Bun), react (with Tailwind), and agent. The default is TypeScript.
- Each step is an isolated process. Its stdout becomes stdin for every step listed in `links`. Empty stdout stops downstream steps. A nonzero exit is the only failure signal.
- Triggers are `route` (the step receives the raw HTTP request), `cron` (runs in Live only), and `email_address`. A responding step sets `output = true` and prints a full HTTP response.
- `route_auth` is one of: space (the default), tenant, sso, external_id (for webhooks), connector, public. Public is used only when a person explicitly asks for it. Any route with a `route_type` needs a `title`. An API route ships `api.json` (OpenAPI 3.1 operations).
- The workflow builds its own URLs from `_3B_WORKFLOW_BASE_URL`. Hostnames are never hard-coded.
- Credentials go through connectors only. Secrets never go in code, chat, or volumes. Volumes are mounted at `/storage/<name>`. Draft branches get isolated volumes.
- `timeout` is 1–300 seconds. A step has 1 vCPU and 2 GiB of memory. `retry_seconds` is used only when replaying the side effect is safe.
- Draft branches are published with **Push live**. An earlier published version can be read and republished (rollback). A **step test** pins a step's input and output and replays with no network.
- A skill is a `SKILL.md` with a frontmatter description. Skills are first-class in 3B.

## Mapping

| Storyworks today | 3B equivalent | What this pivot does |
|---|---|---|
| `stories/**/story.json` plus normalise | `workflows/<name>/` space clone | Replace the artifact (layout is task #5; a round-trip through a space is VERIFY) |
| Mode 2, the Tines Stories MCP server | 3B MCP server, 3B CLI, or the in-product editor | Replace the wire. Tool names and CLI subcommands are VERIFY. Do not invent them |
| `.claude/skills/tines-*` | `3b-build-workflow`, `3b-review`, `3b-ship`, `3b-rollback`, `3b-connect` | Port (task #7) |
| `tines-skills/` via the Skills API | 3B space skills (`SKILL.md`) plus evals | Port (task #8). How a skill is distributed to a space is VERIFY |
| Crew (`.claude/agents`, `.cursor/rules`) | The same shape of roles, in 3B words | Port (task #9) |
| `lint-story` and `policies/lint-rules.yml` | Workflow lint on `config.toml`, `route_auth`, and secrets | Rewrite (task #10) |
| Change-request approval | Draft branch, then step tests, then a reviewer, then Push live by a named person | Simplify (tasks #11 and #12). The exact Push live control is VERIFY |
| Rollback by re-import | Republish an earlier published version | Simplify. The version-list call is VERIFY |
| Ops error router and health monitor | A scheduled workflow and an agent step that proposes fixes and never pushes live | Port (task #16) |
| `[KIT] 00 · Launch Storyworks` | A 3B Launchpad workflow | Rebuild (task #13). No endpoint is invented ahead of that task |
| Records tracker and dashboard | A volume (SQLite) plus a dashboard route, with an optional Cases or Records sync | Rebuild (task #14) |
| Storyline, gates, principles, VERIFY | The same lifecycle, gates re-pointed | Keep, then re-point (task #11) |
| Guide app | The same app, with new area notes, roles, and diagrams | Keep and retarget (task #18) |

## Target architecture

1. **Editor.** Claude Code or Cursor, with `AGENTS-3B.md` (task #6), skills, and crew. Only the builder holds 3B access. How that access is granted (OAuth, CLI login, or something else) is VERIFY.
2. **Repository.** Workflows, skills, policies, evals, and the tracker. A pull request is the unit of change. One concern per PR.
3. **Gates.** Deterministic lint, a review by someone who did not author the change, step tests, a security gate when route exposure widens, and a named person on Push live. The generator never approves its own work.
4. **Platform.** Launchpad, the tracker and dashboard, a starter catalog, and an ops pair. Skills are distributed to spaces. The distribution mechanism is VERIFY.
5. **Adoption.** The guide app, a study path per role, and a migration lane from Tines stories (task #17).

## VERIFY (not confirmed in a tenant)

Task #19 is the ledger entry. Until that task, this list is the boundary. Do not state any of these as fact, and do not invent a stand-in:

- CLI subcommands, MCP tool names, and the in-product editor's file schema.
- The key names inside `workflow.toml` and `config.toml`, other than the names in [What a 3B workflow is](#what-a-3b-workflow-is) (`id`, `links`, `output`, `route_auth`, `route_type`, `title`, `timeout`, `retry_seconds`). Which file each of those keys lives in is itself VERIFY.
- The byte format of "a full HTTP response".
- The allowed values of `color`, and how a webpage sets its title and SVG favicon.
- Space-clone push, draft-branch publish, and republish-previous-version.
- Skill distribution, spend metering, tunnels, and the connector-setup flow.
- Whether `cron` "Live" is a space, a flag, or a publish state.
- Any URL path, route template, or API operation that a later task has not designed and a person has not accepted.

## Principles kept

Agents propose. People approve. The generator never approves its own work. Secrets stay out of chat, code, and volumes — connectors only. A route defaults to space auth. Widening that exposure is a gated decision. Never invent an endpoint.

## Delivery

Foundation, then skills, then gates, then the kit, then operate, then adoption. The task list is [`TASKS.md`](TASKS.md), mirrored as GitHub issues labelled `3b-pivot` (#4–#19). Finish a phase's gate before the next phase's build work. The guide-app retarget (task #18) may start in parallel.
