# AGENTS-3B.md — conventions for 3B workflows

Loaded on this pivot by Claude Code (`CLAUDE.md` imports this file) and by Cursor (`.cursor/rules/3b.mdc`). `AGENTS.md` still governs `stories/**`. Where the two disagree about a workflow directory, this file wins. Procedures are skills (task #7). Keep this file under 200 lines.

Facts below are the ones `3b/CURSOR-PROMPT.md` states. Anything else is **VERIFY**. The list lives in [`3b/PIVOT.md`](3b/PIVOT.md). The ledger update is task #19. Never state a VERIFY item as fact. Never invent an endpoint or a tool name.

## 1. What a workflow is

- A workflow is a folder: `workflow.toml` (preserve its `id`; never copy that id onto another workflow), a root `README.md`, and one directory per step.
- A step directory holds `config.toml`, a `Dockerfile` whose first line is `FROM 3b/base`, the code, and a `README.md`.
- Templates: shell, python, typescript (Bun), react (with Tailwind), agent. Default to TypeScript.
- Each step is an isolated process. Stdout becomes stdin for every step listed in `links`. Empty stdout stops downstream steps. A nonzero exit is the only failure signal.
- The layout in git is `workflows/<name>/`. Slug → workflow id per space is `workflows/_manifest.yaml`. No secrets in that file. Ids stay empty until a space assigns them.

## 2. Golden rules

1. **One concern per PR.** One workflow change, reviewed on its own.
2. **Agents propose, people approve.** The generator never approves its own work and never pushes live.
3. **No secrets** in code, chat, commits, or volumes. Credentials go through connectors only.
4. **No hard-coded hostnames.** Build the workflow's own URLs from `_3B_WORKFLOW_BASE_URL`.
5. **Routes default to space auth.** Wider exposure is a security-gated decision. `public` only when a person explicitly asks.
6. **Never invent an endpoint,** a CLI subcommand, or an MCP tool name. Describe the capability and mark the call VERIFY.
7. **A workflow id is not reusable.** Copying a folder without a new `id` is not a new workflow.
8. **READMEs are part of the workflow.** Every workflow and every step has one: purpose, inputs, outputs.

## 3. Routes and HTTP

| Trigger | Behaviour |
|---|---|
| `route` | The step receives the raw HTTP request |
| `cron` | Runs in Live only |
| `email_address` | Email trigger |

- A responding step sets `output = true` and prints a full HTTP response. The byte format of that response is **VERIFY**.
- `route_auth`: `space` (default), `tenant`, `sso`, `external_id` (webhooks), `connector`, `public`.
- A `route_type` requires a `title`. An API route ships `api.json` (OpenAPI 3.1 operations).
- `public`, `external_id`, and `sso` are flagged for approval. Do not add them in passing.
- A webpage sets a title and an SVG favicon. The keys that carry them are **VERIFY**.

## 4. Credentials, volumes, limits

- Connectors inject credentials. The builder, the model, and the repo never see the secret.
- Volumes mount at `/storage/<name>`. Draft branches get isolated volumes. Volumes are not a place for secrets.
- `timeout` is 1–300 seconds. A step has 1 vCPU and 2 GiB of memory.
- `retry_seconds` only when replaying the side effect is safe. A step that writes, notifies, or charges does not retry by default.

## 5. Draft, live, tests

- Work lands on a draft branch. **Push live** is a named person's action, not the model's.
- An earlier published version can be read and republished. That is rollback. The call that lists versions is **VERIFY**.
- A step test pins one step's input and output and replays with no network. Verify means those tests pass. Pinning is not optional once a step has behaviour worth keeping.
- `cron` does not run off Live.

## 6. Skills

A 3B skill is a `SKILL.md` with a frontmatter description. Skills are first-class in 3B. How a skill is distributed to a space is **VERIFY**. Do not paste a skill body into a workflow as a substitute for that distribution.

## 7. What this file does not do

- It does not rename the four Tines Stories MCP surfaces. Those stay modes 1–4 in `AGENTS.md`. The 3B connection is the 3B MCP server, the 3B CLI, or the in-product editor.
- It does not author Stories, change `story.json`, or open a change request.
- It does not confirm CLI flags, MCP tool names, `workflow.toml` keys beyond `id`, or which file holds `links`, `output`, `route_auth`, `route_type`, `title`, `timeout`, and `retry_seconds`. Those placements are **VERIFY** until a space clone is read.

## 8. Read next

- [`3b/PIVOT.md`](3b/PIVOT.md) — thesis, mapping, VERIFY boundary.
- [`3b/TASKS.md`](3b/TASKS.md) — issue per task, in phase order.
- [`storyline/README.md`](storyline/README.md) — the lifecycle. Gates are re-pointed in task #11, not here.
