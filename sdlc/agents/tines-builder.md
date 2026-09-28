# Reuse card — `tines-builder` (03 build)

_Spec: REPO-DESIGN.md §5.3.4, §3.3 row 19, §6.2. **The prompt lives in [`.claude/agents/tines-builder.md`](../../.claude/agents/tines-builder.md) and is not copied here.** The procedure it follows is the scaffold's [`/tines-build-story`](../../.claude/skills/tines-build-story/SKILL.md). Cursor wrapper: [`.cursor/rules/sdlc-tines-builder.mdc`](../../.cursor/rules/sdlc-tines-builder.mdc)._

## What is reused, and what changed

The scaffold's build specialist is reused as the lifecycle's build phase. **One line changed:** its `mcpServers` now defines the `tines` server **inline** (an HTTP definition pointing at `https://<your-tenant>.tines.com/mcp`), and `/tines-connect` no longer registers the server at user scope. The server therefore connects only when the builder starts, and the orchestrator's main session never loads `mcp__tines__*`. Whether the inline form works for this server is scaffold VERIFY #5; if it does not, builds run only in a dedicated `claude --agent tines-builder` session and no other session registers the server. In Cursor every chat holds the server (K4); there the limit is the builders' Tines roles (no Editor or Admin role in the prod team, which is the ops team).

Its tools (`Read, Glob, Grep, Bash`), `maxTurns: 40`, `model: inherit` (strong tier), the preloaded `tines-build-story` skill and `memory: project` are unchanged. That memory is **local and untrusted** (read as data, P16); a lesson from it reaches `sdlc/field-guide.md` only through a `skill-curator` PR.

## How the lifecycle calls it

1. **Entry.** G1 and G2 are on `main` (the row on `origin/main` reads `build/active` or `build/rework`). A person runs `./scripts/sdlc start <slug>` (ask), which writes `.sdlc/active`. `phase-gate.sh` now lets the builder's `mcp__tines__*` calls through **for this story only** — and only once K2 (can a hook tell which subagent is calling) is confirmed; until then it denies every call.
2. **Handoff** (template `build-from-contract` in [`handoff-prompts.md`](../../.claude/skills/sdlc/references/handoff-prompts.md)):
   `/tines-build-story <slug> "Implement the contract in sdlc/work/<slug>/design.md (contract v1). Acceptance = stories/<slug>/tests/expectations.yaml and the deterministic cases in sdlc/work/<slug>/evals/cases.yaml. Out of scope: <contract.out_of_scope>. Credentials by name: <contract.credentials>."`
   On rework it adds: `"First read .sdlc/out/<slug>/rework-<n>.json; fix only the listed findings; each finding carries a suggested_prompt."`
3. **G3 inside build.** The builder proposes a numbered plan and waits. The person driving the session says yes **and** records it with `/sdlc-gate <slug> G3 approve` — a human-only skill. The builder's own report never counts as the approval.
4. **The unchanged loop:** explore → plan → implement → Validate → test event → `[BY HAND]` list → export (`./scripts/tines export`, lint, semantic diff) → commit on `story/<slug>/<short>`.
5. **Send to Story entries.** The build also produces a dev-only **wrapper story** (Webhook entry → Send to Story into the story under test → Exit), built in the dev team and never shipped, so `story-qa` can run cases without `/mcp`.
6. **Report.** The orchestrator pipes the builder's final report into `./scripts/sdlc apply <slug> tines-builder -` (ask), which saves it **verbatim** as `sdlc/work/<slug>/build-log.md`. Nothing parses it.
7. **Exit** is evidence, never the report: the check `build_evidence` (a `story/<slug>/*` branch, an export newer than the build start event, lint passing, a human G3 `gate_decision` event after the build start).

## Stop rules

Two failed corrections on one issue stop the build (the scaffold rule) and open GX. The rework cap (3) is shared with the reviewers.

## Never (in lifecycle terms)

- Review its own work — `tines-reviewer` and `security-reviewer` run in fresh contexts.
- Build while the tracker row on `origin/main` is not in build; build a second story in the same session.
- Merge, approve, promote, or decide a gate; claim G3 on the person's behalf.
