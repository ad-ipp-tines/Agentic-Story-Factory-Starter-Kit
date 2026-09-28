# The editor's model — Mode 2 and the IDE specialists

_Spec: REPO-DESIGN.md §10.4 (this page), §10.1 (the two "models"), §5.2 (model tiers), §12 rows 1, 12 and 13, §14. The Tines-side provider is a different choice: [`llm-provider-matrix.md`](llm-provider-matrix.md)._

## The editor's model is not the kickoff Page's `llm_choice`

| | **Editor-side model** (this page) | **Tines-side provider** |
|---|---|---|
| Runs | Every authoring session through **Mode 2**, the Tines Stories MCP server at `https://<your-tenant>.tines.com/mcp`; the orchestrator (`/sdlc`); every IDE specialist in `.claude/agents/`; `review.yml`'s headless reviewer | The AI Agent actions in your stories and in `[KIT] 00`, Workbench, Workbench for Storyboard |
| Chosen in | Cursor or Claude Code | Settings → AI settings, and per AI Agent action |
| Paid with | The editor plan | Tines AI credits, or your provider's bill |
| Governed by | **Your organisation's editor data policy** | Tines' AI settings and guarantees |

The kickoff Page never asks about the editor. Nothing in `kit/tenant/config.yaml` changes it.

## Three things to know

1. **The builder needs the strongest model the editor offers.** `tines-builder` drives the Tines Stories MCP server's dozens of authoring tools (the exact list is unpublished, VERIFY #1), which makes it the hardest tool-selection job in the kit: which tool, which arguments, in what order, and when to stop and Validate. Pointing an editor at a local or gateway model is an editor feature outside Tines' docs (VERIFY K42), and the worst fit for this role.
2. **Smaller models belong only on fast-tier specialists,** which hold no MCP server and do templated, bounded work.
3. **Data policy.** What the editor sends to its model provider — prompts, the story JSON it reads, tool results from `/mcp` — is governed by your organisation's editor data policy, not by Tines' AI guarantees. Story exports carry configuration only: no credential values, no Resource contents, no events.

## Model tiers, never model ids

Every IDE agent file sets `model: inherit`, with a comment naming its tier, so a subagent uses the model of the session that starts it. No file in this repository names a model id.

| Tier | For | Agents |
|---|---|---|
| **strong** | Planning, design, security judgement, driving `/mcp` | the orchestrator (the session itself), `story-architect`, `security-reviewer`, `tines-builder` |
| **standard** | Structured writing against a schema | `eval-author`, `story-qa`, `eval-curator`, `skill-curator` |
| **fast** | Search, arithmetic, templated output | `story-scout` |
| (the scaffold's own note) | Convention review | `tines-reviewer`: its file says a smaller model is acceptable for review, chosen per tenant |

REPO-DESIGN.md §5.2 lets a tenant that wants a smaller model for a fast-tier agent change that one agent's `model:` line. Today `./scripts/sdlc check` (`agents_frontmatter_valid`) requires `model: inherit` on every agent file, so such a change also needs that check relaxed for fast-tier agents, in the same PR, reviewed by security-platform. A reviewer from a different model family than the builder is an option, not a requirement.

## In Claude Code and in Cursor

| | Claude Code | Cursor |
|---|---|---|
| Who loads the Tines Stories MCP server | Only `tines-builder`: the server is defined inline in its `mcpServers`, so its tool descriptions never enter the main session or any other specialist's context (the inline form is VERIFY #5) | Only the builder chat: `/tines-connect` puts it in the project `.cursor/mcp.json` of a separate build-only worktree, never the global `~/.cursor/mcp.json` (per-chat scoping is VERIFY K4); until K4, the non-builder specialists run in Claude Code. The hard limit is still that builders hold no Editor or Admin role in the prod (ops) team |
| Where the model is chosen | The session's model; subagents inherit it | The chat's model |
| Enforcement | Hooks (`guard-mcp.sh`, `phase-gate.sh`, and the rest), permission rules, `./scripts/sdlc apply`, CI | No Claude Code hooks: `./scripts/sdlc apply`, `sdlc.yml` (which calls `lint.yml` and `review.yml`), CODEOWNERS, team roles |

## Cost

- **The build loop is off the Tines credit meter.** Mode 2 runs on the editor's plan; no Tines AI credits are listed for the Tines Stories MCP server (whether its research and listing helpers consume credits is VERIFY #11). Workbench for Storyboard, which spends credits, is a deliberate choice, never the default.
- **The one exception is verify.** `story-qa`'s model-graded eval trials (`./scripts/sdlc eval-run`) run the **dev** story's AI Agent actions, which spend dev-team Tines credits. `./scripts/sdlc estimate` counts them against the dev team's ceiling (`cost.9`).
- **Multi-agent runs cost many times a single chat.** The dispatch rules skip the security reviewer when it has nothing to judge, the cost checks are a script rather than an agent, every agent has a `maxTurns`, rework stops at three cycles, and summaries are capped at 1,500 characters.

## Verify in your tenant before relying on it

| Item | What is assumed |
|---|---|
| #1 | The Tines Stories MCP server's tool names and count |
| #5 | The inline `mcpServers` form for `tines-builder` |
| #11 | Whether `/mcp`'s research and listing helpers consume Tines credits |
| K4 | Cursor: per-chat MCP enablement; per-agent tool limits |
| K42 | Editor-side local or gateway models with `/mcp`'s many tools |
