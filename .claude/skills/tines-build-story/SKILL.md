---
name: tines-build-story
description: Builds or changes one Tines story through the Tines Stories MCP server using the explore-plan-implement-validate-export loop, then lints and commits the export. Use when the user wants to create, extend or fix a story, or says build, add an action, wire, validate or export.
argument-hint: <story-slug> "<what to build>"
allowed-tools: Bash(./scripts/tines export *), Bash(./scripts/tines runs *), Bash(./scripts/tines manifest-set-dev-id *), Bash(./scripts/lint-story.sh *), Bash(git checkout -b *), Bash(git add *), Bash(git commit *)
---

# /tines-build-story — one story, in the dev team, through `/mcp` (Mode 2)

**Inputs:** `$0` = the story slug (a folder under `stories/` and an entry in `stories/_manifest.yaml`) · `$1` = the ask, in quotes.
**Runs in:** the `tines-builder` subagent (`.claude/agents/tines-builder.md`) — the only context that holds the Tines Stories MCP server. From the main conversation, delegate to it; never attach the server to the main context.
**Read on demand:** `.claude/skills/tines-build-story/references/prompt-pack.md` (literal prompts, in build order) · `.claude/skills/tines-build-story/references/story-conventions.md` (naming, sub-story contract, HTTP hardening, monitoring, AI Agent design, tool design, limits).

## Preconditions — stop if any fails
1. `TINES_ENV` is `dev` (unset counts as dev). `guard-mcp.sh` refuses every `/mcp` call under `prod`.
2. `$0` is in `stories/_manifest.yaml` with a `dev.story_id`, or is added now with `new: true` and `dev: { story_id: 0 }` (a new story: its dev id is recorded in step 1 below; `new: true` concerns only the **prod** id, which the first prod ship or a by-hand prod shell story assigns). `stories/<slug>/` exists — copy `stories/_template/` if not — and `story.meta.yaml: slug` equals the folder name.
3. Every credential and Resource the story will reference **already exists in the dev team under the same name** (`story.meta.yaml: credentials[] / resources[]`). The server cannot create credential values. A missing one is a [BY HAND] line and a stop before the step that needs it.
4. The slug is not listed in `policies/never-touch.yml`, and is not an `ops-*` story unless the ask is from the ops team and says so (then the person sets `TINES_ALLOW_OPS_BUILD=1` in the dev shell — `guard-mcp.sh` otherwise blocks every `/mcp` call whose input matches the `^\[OPS\]` name pattern).

## The loop

1. **Explore.** Through the Tines Stories MCP server, read the story named in the manifest, or create it in the dev team inside the manifest's `folder_id`. **If you created it, record its id now, before any other call:** `./scripts/tines manifest-set-dev-id <slug> <id>` (an id is not a secret). It writes only `stories.<slug>.dev.story_id` in `stories/_manifest.yaml`, only while it is `0`, and refuses an id another story or the never-touch list holds; never `yq -i`, which could rewrite any file. Nothing else writes it — the story was created through `/mcp`, not by an import — `phase-gate.sh` allows no other `/mcp` call for the slug while it is `0`, and `/tines-export` (step 7) stops on a dev id of `0`. Report what is visible: actions, configurations, formulas, connections, recent execution logs, and the **names** of referenced credentials and Resources — never values, never other stories, never data in flight. Say what you saw before changing anything.
2. **Plan.** Anything bigger than one sentence becomes a numbered list of actions — type, name, field names, credential by name — plus the failure path and the Note. Wait for a yes. A one-sentence change skips the plan.
3. **Implement.** One prompt per action from the prompt pack, in build order: entry → `normalize` (`DEFAULT()` on every field) → a guard Trigger before any AI step → integrations by named credential → `verdict` → `result` → `error` → hardening → Note. Every prompt names the story, the action type, the action name and the fields, and ends with "then validate". Never name a `/mcp` tool — describe what you want done.
4. **Validate.** End with "Validate". Fix what it reports. **Two failed corrections on one issue → stop, report, and ask.** Never a third retry.
5. **Test.** Send `stories/<slug>/tests/sample-event.json` to the entry action: run it through the server where your permissions allow, or post it to the webhook URL (under change control a draft webhook accepts `?draft=<name>` — VERIFY `docs/VERIFY.md` #2). Read the run's events (`./scripts/tines runs <slug> --env dev --since <timestamp>`, or the server's recent execution logs) and assert `tests/expectations.yaml`: the entry action fired, `expected_actions_fired_min` reached, no error logs on the listed actions, every `result_fields` entry present.
6. **By hand.** The following cannot be done through `/mcp`. Print them as a checklist for the person; never claim they are done:
   - enable **Send to Story** access for the team if this is a sub-story (`(sub)`); set its **Timeout Duration** wherever it is used as a tool
   - raise **event retention** above 7 days (≥ 30 days for `tier: production`)
   - confirm **change control** is on for a new story (tenant policy "Enable by default" should do it — check)
   - create **Record types** the story writes to (whether `/mcp` can — VERIFY #26)
   - on every AI Agent action: the **token-usage alert on the Status tab** (Notify at `daily_tokens_notify`, Disable action at `daily_tokens_disable`, from `policies/cost-ceilings.yml`) and the `tines-skills/` skill attachment
   - re-create any **MCP connection** on an AI Agent action (imports drop them; never paste a token — reference a credential)
   - for a Mode 4 story, drag the **MCP server action** onto the canvas (whether `/mcp` can add it — VERIFY #25); the editor then wires the tools
7. **Export.** Run the scripts directly — `./scripts/tines export <slug>` (export → normalise → stamp `exported_from`), then `./scripts/lint-story.sh stories/<slug>/story.json` and `./scripts/diff-story.sh stories/<slug>/story.json --against HEAD` (semantic diff). These are the steps `/tines-export` runs; that skill sets `disable-model-invocation: true`, so the builder cannot invoke it — only a person can. Then complete `story.meta.yaml`: `credentials`, `resources`, `records`, `ai.agents[]` (each with `output_schema: true`, `token_alert`, `skills`, `budget_ref`), `monitoring`, `schedule_interval_seconds`. A new AI Agent action also needs a line under `policies/cost-ceilings.yml: agents` — `lint.yml` fails the PR without it.
8. **Commit.** Branch `story/<slug>/<short>`; message `story(<slug>): <what changed>`; stage only `stories/<slug>/**` (plus the budget line). Hand off with the sentence: **"Run `/tines-review` from a fresh session before opening the PR."**

## Never
- Hand-edit `stories/**/story.json` — links are index-based; the export is produced by the script.
- Paste a credential value, a Resource body, a token or a webhook URL anywhere — not in prompts, files, commit messages or MCP connections.
- Name `/mcp` tools; reference `tines:<tool>` only once `docs/VERIFY.md` records the tenant's tool list.
- Work while `TINES_ENV=prod`, touch a second story in the same branch, or claim a change reached production.
- Import Library stories through `/mcp` (it cannot) — say "[BY HAND] import into the 90 Seeds folder".
- Skip Validate, the test event, or the by-hand list.

## Done means
- [ ] Validate clean · test event matches `expectations.yaml` · by-hand list printed
- [ ] `story.json` exported, normalised and lint clean; `story.meta.yaml` complete; `exported_from` stamped after the last `/mcp` call (`stop-gate.sh` checks this)
- [ ] a budget line exists for every AI Agent action; every HTTP Request action is hardened; the Note carries the mode badge
- [ ] one story, one branch, one commit; the hand-off sentence said
