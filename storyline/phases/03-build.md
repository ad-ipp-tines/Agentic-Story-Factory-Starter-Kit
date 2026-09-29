# 03 · build — implement the contract in the dev team through Mode 2

_Phase `build` in [`state-machine.yaml`](../lifecycle/state-machine.yaml) · Gate inside: [G3](../gates/G3-plan-approval.md) (human) · Exit: the check `build_evidence` · Spec: REPO-DESIGN.md §4.4 (03 build), §6.1–§6.3._

## Purpose

Build exactly what the contract says, in the dev team, through the Tines Stories MCP server (Mode 2), using the scaffold's own build loop unchanged. The lifecycle wraps the builder with a handoff and an evidence check; it does not edit the builder's prompt (REPO-DESIGN.md §3.6).

## Entry criteria

G1 and G2 are on `main`: the design PR has merged and the row on `origin/main` reads `phase: build`.

`./scripts/storyline start <slug>` (ask) writes `.storyline/active` (local, gitignored) and appends the build start event. From then on `phase-gate.sh` lets `tines-builder`'s `mcp__tines__*` calls through **for this story only**, because:

- the row on `origin/main` (read with `git show origin/main:kit/tracker/backlog.yaml`, never the working tree) is `build/active` or `build/rework`;
- the caller is identified as `tines-builder` — whether a hook can tell which subagent is calling is **VERIFY K2**, and until K2 is confirmed the hook denies every `mcp__tines__*` call;
- the tool input names no story id other than this slug's `dev.story_id` in `stories/_manifest.yaml`.

The editor's Write and Edit tools are denied on `.storyline/**`, `kit/tracker/**` and `storyline/work/**`, so no file edit can open `/mcp` without G1 and G2. `STORYLINE_ENFORCE=0` is the scratch-story escape hatch; `guard-mcp.sh` still mirrors every call.

## Work

The showrunner hands `tines-builder` the scaffold's skill, rendered from the contract (handoff template `build-from-contract`):

```
/tines-build-story <slug> "Implement the contract in storyline/work/<slug>/design.md (contract v1). Acceptance =
stories/<slug>/tests/expectations.yaml and the deterministic cases in storyline/work/<slug>/evals/cases.yaml.
Out of scope: <contract.out_of_scope>. Credentials by name: <contract.credentials>."
```

On rework it adds: *"First read `.storyline/out/<slug>/rework-<n>.json`; fix only the listed findings; each finding carries a `suggested_prompt`."*

The builder runs its unchanged loop, on branch `story/<slug>/<short>`:

1. **Explore** — read the story in the dev team (or create it and record its dev id in the manifest).
2. **Plan** — a numbered list of actions with type, name and field names. **G3:** the person driving the session says yes, and records it with `/storyline-gate <slug> G3 approve` (a human-only skill). The builder's own report never counts as the approval.
3. **Implement** — one prompt per action from the prompt pack, each naming the story, the action type, the action name and the fields.
4. **Validate**, then the **test event** against `tests/expectations.yaml`.
5. The **`[BY HAND]`** list.
6. **Export** — `./scripts/tines export <slug>`, `./scripts/lint-story.sh`, `./scripts/diff-story.sh` (the steps `/tines-export` runs).
7. **Commit** on `story/<slug>/<short>`.

**Stories with a Send to Story entry** also get a dev-only **wrapper story** (a Webhook entry → Send to Story into the story under test → Exit), built in the dev team and never shipped, so that verify can run cases without `/mcp` (REPO-DESIGN.md §5.3.8; its URL form is VERIFY K37).

When the builder returns, the showrunner pipes its report into `./scripts/storyline apply <slug> tines-builder -` (ask), which saves it **verbatim** as `build-log.md` and appends the build end event. Nothing parses it.

## Exit criteria

The check `build_evidence` passes — all four:

- a `story/<slug>/*` branch exists
- `story.meta.yaml` `exported_from.at` is later than the build start event
- `./scripts/lint-story.sh` passes
- `events.jsonl` holds a `gate_decision` event for G3 with `actor_kind: human`, after the build start event

Then `./scripts/storyline advance <slug>` (ask) writes `build → verify` on the same branch.

## Artifacts

| Artifact | Path | Written by |
|---|---|---|
| Export | `stories/<slug>/story.json` (never hand-edited) | `./scripts/tines export` inside `/tines-build-story` |
| Meta | `stories/<slug>/story.meta.yaml` (`exported_from`, `ai.agents[]`, credentials by name) | the builder's skill |
| Build log | `storyline/work/<slug>/build-log.md` | `apply` ← the builder's report, verbatim |
| Events | `storyline/work/<slug>/events.jsonl` | `start`, `/storyline-gate` (G3), `apply`, `advance` |

## Templates

[`build-log.md`](../templates/build-log.md)

## Crew

`tines-builder` **(reused)** — `.claude/agents/tines-builder.md`; its only change is the inline `mcpServers` definition (REPO-DESIGN.md §3.3 row 19), which makes it **the only Claude Code context that loads the Tines Stories MCP server**. Reuse card: [`storyline/crew/tines-builder.md`](../crew/tines-builder.md). In Cursor only the builder chat of a separate build-only worktree holds the server — never the global `~/.cursor/mcp.json` (per-chat scoping is VERIFY K4); the hard limit there is that builders' Tines accounts hold no Editor or Admin role in the prod team, which is the ops team.

## Gate

**[G3 — plan approval](../gates/G3-plan-approval.md)**, human, inside build. There is no gate out: the exit is evidence, checked by a script.

## Failure modes

| Symptom | Cause | What happens |
|---|---|---|
| `phase-gate.sh` denies `/mcp` | the design PR has not merged, `.storyline/active` names another slug, or K2 is unconfirmed | the hook says which: run `/storyline <slug>`; never edit the tracker to open it (the tools are denied, and `main` is what counts) |
| Two failed corrections on one issue | the prompt or the contract is wrong | the builder stops (scaffold rule) and the story opens GX; a human re-prompts or sends it back to design |
| `build_evidence` fails on the export time | the builder changed the story after exporting | `stop-gate.sh` already refuses a turn with a stale export; run the export again |
| `build_evidence` fails on G3 | the plan was approved in chat, not recorded | the human runs `/storyline-gate <slug> G3 approve`; a chat "yes" is not an instrument |
| A credential is missing in the dev team | it was never created there | `[BY HAND]`, then continue; the export never carries a value |
