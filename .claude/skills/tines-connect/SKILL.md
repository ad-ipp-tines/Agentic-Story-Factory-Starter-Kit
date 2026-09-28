---
name: tines-connect
description: Connects this editor to the Tines Stories MCP server — inline in the tines-builder subagent (Claude Code) or in a build-only worktree's project config (Cursor), never at user scope or in the global Cursor config — completes the OAuth consent and runs a smoke prompt. Use on first setup, after an 'unauthorized' or empty-tool-list error, or when switching tenants.
disable-model-invocation: true
allowed-tools: Bash(claude mcp list), Bash(claude mcp remove tines --scope user), Read
---

# /tines-connect — step 0: connect the editor to `/mcp` (Mode 2)

The Tines Stories MCP server is a first-party Model Context Protocol (MCP) endpoint built into every tenant at `https://<your-tenant>.tines.com/mcp`. **Authentication is OAuth only — an API key will not work.** The entry is never in a repository `.mcp.json` (`CLAUDE.md` §a: it would connect without a trust prompt in headless runs): in Claude Code it is defined **inline in the `tines-builder` subagent**, so only the builder loads it, and it is never registered with `claude mcp add`; in Cursor it lives only in the project `.cursor/mcp.json` of a **separate build-only worktree**, never the global `~/.cursor/mcp.json` (which would give it to every chat — per-chat scoping is VERIFY K4).

## Preconditions
- `TINES_TENANT` is set in the shell (`source .env`). This skill **never reads `.env`** — it is denied in `.claude/settings.json`. If the variable is unset, stop and ask the person to `source .env`.
- The person's Tines user is a member of the dev team named in `stories/_manifest.yaml`. The server inherits the prompting user's permissions and grants nothing more.

## Steps

1. **Read the tenant.** `echo "$TINES_TENANT"` must print a host prefix only — no `https://`, no `.tines.com`. Anything else: stop and say what is wrong.

2. **Add the server.**
   - **Claude Code:** do **not** run `claude mcp add` — the server is defined **inline** in `.claude/agents/tines-builder.md` (`mcpServers`), so it connects only for the builder and never loads `mcp__tines__*` into the main session (REPO-DESIGN.md §3.3 row 19, §6.2). If an earlier setup registered it at user scope, remove that entry first (`claude mcp list`; `claude mcp remove tines --scope user`) — a user-scope `tines` would put the tools back into every session. Then, from the same shell (so `TINES_TENANT` is set), start a dedicated builder session with `claude --agent tines-builder`; the inline server connects at startup. Run `/mcp` in that session, select `tines` and complete the consent screen titled **Tines Stories MCP server**, which lists the story authoring capabilities being granted. Tines publishes no Claude Code steps; the inline form, `${TINES_TENANT}` expansion inside it and OAuth for an inline server are **VERIFY** (`docs/VERIFY.md` #3, #5). If the inline form does not connect, builds run only in a dedicated `claude --agent tines-builder --mcp-config <a file outside the repository holding the `.mcp.json.example` entry>` session (REPO-DESIGN.md §6.2; VERIFY #5) — never `claude mcp add`, so no other session registers the server. If the copy-ready snippet at `https://<your-tenant>.tines.com/mcp` (login required) differs, the snippet wins.
   - **Cursor:** make a separate build-only worktree (`git worktree add ../<repo>-build`) and open it as its own Cursor workspace, used only for the `sdlc-tines-builder` chat. Paste the entry from `.cursor/mcp.json.example` into **that worktree's** project `.cursor/mcp.json` (gitignored) — never the global `~/.cursor/mcp.json`, which would give every chat the authoring server (per-chat scoping is VERIFY K4), and never the main workspace's project file. Saving triggers the OAuth flow. No `headers` key. Whether Cursor accepts or needs a `type` key is VERIFY (#4). Until K4 is confirmed, the other specialists run in Claude Code, not Cursor (`sdlc/agents/README.md`).
   - The server name must be exactly **`tines`**: `.claude/settings.json` allows `mcp__tines__*` and `guard-mcp.sh` matches `mcp__tines__.*`. Any other name misses both.

3. **Smoke prompt.** In the builder session (Claude Code) or the build worktree's chat (Cursor), ask: *"Using the Tines MCP server, list the teams I can see and the stories in each."*
   - An "unauthorized" error, or a server entry with no tools, means the OAuth session lapsed: consent again — `/mcp` → `tines` in a `claude --agent tines-builder` session (never `claude mcp add`), or re-save the build worktree's entry in Cursor.
   - A missing team means the Tines user is not a member of it. The server cannot grant it; a team admin must.
   - A healthy connection shows the server connected with a tool count in the dozens — an in-tenant observation, not a published number.

4. **Record the tool names** the client lists in `docs/VERIFY.md` under "Recorded `/mcp` tool names (item 1)": date, client, one name per line. Until that block is filled, no file in this repository may name a `/mcp` tool, and `guard-mcp.sh` guards destructive calls with a regex instead of an explicit deny list.

5. **Say three things** back to the person: an API key will not work here; production authoring is blocked by the hook (`TINES_ENV=prod` refuses every `/mcp` call); every tool use is recorded in the tenant's audit logs as MCP activity and mirrored locally to `.tines/mcp-activity.jsonl`.

## Checklist
- [ ] `TINES_TENANT` set; `.env` never read
- [ ] server named `tines`, inline in `tines-builder` (Claude Code) / the build-only worktree's `.cursor/mcp.json` (Cursor), HTTP transport, OAuth consent completed; no user-scope `tines` in Claude Code and none in the global `~/.cursor/mcp.json`
- [ ] smoke prompt lists the dev team and its stories
- [ ] tool names recorded in `docs/VERIFY.md`
- [ ] no `.mcp.json` created, and a `.cursor/mcp.json` only in the build-only worktree (both gitignored, both denied to Read)

## Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| `unauthorized` / empty tool list | OAuth session lapsed | Claude Code: `/mcp` → `tines` in a `claude --agent tines-builder` session and consent again (never `claude mcp add`; remove a stray user-scope entry with `claude mcp remove tines --scope user`). Cursor: re-save the build worktree's entry |
| A team is missing | Not a member | A team admin adds the user; the server cannot |
| A call is refused with `guard-mcp:` | `TINES_ENV=prod`, a protected story id, or a destructive-looking tool name | Build in dev; check `policies/never-touch.yml`; confirm with the story owner before `TINES_ALLOW_DESTRUCTIVE=1` |
| Headless run reports the server missing | `/mcp` is OAuth only; a headless session is assumed not to reuse the consent (VERIFY #20) | Authoring stays interactive; CI never holds `/mcp` |
| Tool call fails on a "credential not found" | Credential exists under another name or in another team | Create or rename it in the dev team [BY HAND]; never paste a value |
