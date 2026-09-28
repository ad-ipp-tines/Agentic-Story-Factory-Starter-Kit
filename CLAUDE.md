# CLAUDE.md — Claude Code entry point

@AGENTS.md

The line above imports the shared conventions file: what this repo is, the four modes, the golden rules, naming, HTTP Request hardening, monitoring, AI Agent action rules, credits, ownership and never-touch, the skill map. There is one source of truth for conventions and it is `AGENTS.md`. What follows is Claude Code-specific.

## a. The Tines Stories MCP server is defined inline in `tines-builder`

- The `tines` server (`https://${TINES_TENANT}.tines.com/mcp`, HTTP) is defined **inline** in `.claude/agents/tines-builder.md` (`mcpServers`, REPO-DESIGN.md §3.3 row 19), so it connects only when that subagent starts and `mcp__tines__*` never loads into the main session. **Never register it at user scope** (`claude mcp add … --scope user`): a user-scope `tines` puts the authoring tools into every session, the orchestrator's included.
- Run `/tines-connect` once per machine: from a shell where `TINES_TENANT` is set, start a `claude --agent tines-builder` session, run `/mcp`, select `tines` and complete the OAuth consent screen titled **Tines Stories MCP server**. The inline form, `${TINES_TENANT}` expansion inside it and OAuth for an inline server are VERIFY (docs/VERIFY.md #3, #5); prefer the copy-ready snippet at `https://<your-tenant>.tines.com/mcp` if it differs.
- This repo commits **no `.mcp.json`** (`.mcp.json.example` is the shape, for reference). In `claude -p` and SDK sessions a repository `.mcp.json` connects its servers without a trust prompt and repository hooks run — so the entry is never a repository `.mcp.json`.
- The server name must be exactly `tines`: `.claude/settings.json` allows `mcp__tines__*` and the PreToolUse hooks match `mcp__tines__.*`. Any other name misses both.
- Authentication is OAuth only. An API key will not work. An "unauthorized" error or an empty tool list means the OAuth session lapsed: in a `claude --agent tines-builder` session, `/mcp` → `tines` → consent again.
- The server inherits your own Tines permissions and grants nothing more; every tool use is recorded in the tenant's audit logs as MCP activity.

## b. Builder and reviewer are different contexts

- Story edits are delegated to the **`tines-builder`** subagent (`.claude/agents/tines-builder.md`). It is the only context that holds the `/mcp` server, so its dozens of authoring tool descriptions never enter the main conversation. It works on one story in the dev team, plans before any change bigger than a sentence, ends with Validate and a test event, then runs `/tines-export`.
- Review is delegated to **`tines-reviewer`** (`.claude/agents/tines-reviewer.md`): a fresh context, no MCP, read-only tools, no tenant access. It judges only the diff, the export and the meta file and returns findings JSON. **The generator never reviews its own work** — `/tines-review` refuses if this session built the story, so run it from a fresh session before opening the PR.
- The review rule in one line: no story reaches a PR without a fresh-context review, and no PR reaches production without `lint.yml`, `review.yml`, a CODEOWNER, a human merge and a human change-request approval in Tines.

## c. Hooks enforce; this file advises

The five hooks in `.claude/hooks/` are wired in `.claude/settings.json` and run whether or not the model agrees:

| Hook | Event | Does |
|---|---|---|
| `guard-mcp.sh` | PreToolUse `mcp__tines__.*` | Mirrors every Tines MCP call to `.tines/mcp-activity.jsonl`; refuses any call while `TINES_ENV=prod`; blocks any call whose input references a production or never-touch story id (`policies/never-touch.yml`, `stories/_manifest.yaml`); blocks destructive-looking tool names (regex — VERIFY against the real tool list, then replace with an explicit deny list) |
| `phase-gate.sh` | PreToolUse `mcp__tines__.*` | Opens `/mcp` for one story only: the story in `.sdlc/active`, only while its row on `origin/main` is in build (G1 and G2 merged), only for the `tines-builder` caller (VERIFY K2 — until confirmed it denies every call), and only for that story's dev id. `SDLC_ENFORCE=0` is the logged scratch-story escape hatch |
| `block-secrets.sh` | PreToolUse `Write\|Edit\|MultiEdit\|NotebookEdit\|Bash` and `mcp__tines__.*` | Refuses any write, shell command or Tines MCP input whose content looks like a secret (`X-User-Token`, `Bearer …`, `xoxb-`, `AKIA…`, `sk-…`, `github_pat_…`, inline `api_key`) |
| `lint-on-write.sh` | PostToolUse `Write\|Edit` | Lints `stories/**/story.json` (blocking — the turn fails with the findings) and validates `tines-skills/**/SKILL.md` (advisory) |
| `stop-gate.sh` | Stop | Will not let a turn end with a failing lint or an export older than the last logged MCP call — it says exactly which `/tines-export <slug>` to run |

Exit 2 from a PreToolUse hook beats an allow rule, and the three `mcp__tines__.*` hooks run as `bash … || exit 2`, so a missing or crashing hook blocks the call instead of letting it through. Deny beats ask beats allow in `settings.json`; `cr-promote` and `terraform apply` are denied, and so are the model's own writes to `.claude/**`, `policies/**` and lifecycle state; deploy subcommands, exports, `git add`, `git commit` and `git push` ask; read-only subcommands are allowed.

## d. Headless runs

- The two headless workflows load this repository's settings with `--setting-sources project` and fence it instead. `propose-fix.yml` (default branch only — `repository_dispatch` / `workflow_dispatch`) adds `--strict-mcp-config` with an empty `--mcp-config`, explicit `--allowedTools` and `--disallowedTools`, `--max-turns`, a timeout and a checkout with no persisted git token. `review.yml` (same-repository PRs) adds a read-only `--allowedTools` list, `--max-turns` and a timeout, and configures no MCP server. Neither **ever expects `/mcp` to be available** — it is OAuth only and a headless session is assumed not to reuse an interactive consent (VERIFY, never relied on). A scripted batch of your own follows the same pattern.
- CI holds no MCP server and no tenant credentials for review; `ship.yml` and friends hold team-scoped keys that can import and open change requests but cannot approve.
- Fail a headless run on `mcp_server_errors` in the init event if a server was expected.

## Where things live (cold start)

- Conventions: `AGENTS.md` (imported above). Long form: `.claude/skills/tines-build-story/references/story-conventions.md`.
- Procedures: `.claude/skills/tines-*/SKILL.md`. The prompt pack: `.claude/skills/tines-build-story/references/prompt-pack.md`.
- The API: `./scripts/tines <subcommand>` — one audited code path; never compose raw `curl` against the key.
- Truth: `stories/<slug>/story.json` + `story.meta.yaml`; the environment map: `stories/_manifest.yaml`.
- The contract: `policies/POLICY.md`; budgets: `policies/cost-ceilings.yml`; write-protected ids: `policies/never-touch.yml`; lint rules: `policies/lint-rules.yml`.
- What is still assumed: `docs/VERIFY.md`. Update it when you confirm an item and say what changed in the repo.
- Never read `.env`, `.env.*`, `.mcp.json` or `.cursor/mcp.json` — they are denied in `settings.json`; the skills ask the person to `source .env` instead.
