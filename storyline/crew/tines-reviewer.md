# Reuse card — `tines-reviewer` (04 verify)

_Spec: REPO-DESIGN.md §5.3.5. **The prompt lives in [`.claude/agents/tines-reviewer.md`](../../.claude/agents/tines-reviewer.md), unchanged, and is not copied here.** The procedure is the scaffold's [`/tines-review`](../../.claude/skills/tines-review/SKILL.md) (`context: fork`); the output is [`findings-schema.json`](../../.claude/skills/tines-review/references/findings-schema.json). Cursor wrapper: [`.cursor/rules/storyline-tines-reviewer.mdc`](../../.cursor/rules/storyline-tines-reviewer.mdc)._

## What is reused

The scaffold's fresh-context convention reviewer, its prompt byte for byte: read-only tools (narrowed to `Read, Grep, Glob`, `lint-story.sh` and `diff-story.sh` — no `jq`, which can print the environment, and no `git diff`, whose `--output` writes files), no MCP server, no tenant, findings JSON only, and its never-approve list (credentials not in meta, token-shaped strings, AI Agent actions without a schema, schema-field Trigger, budget line or token alert, HTTP Requests without hardening, production stories without monitoring, destructive tools without `request_`).

## How the lifecycle calls it

1. **Verify fan-out.** `./scripts/storyline next <slug>` returns `parallel: true` with `tines-reviewer` and, when its condition holds, `security-reviewer`. The showrunner spawns them in one turn; `./scripts/storyline estimate <slug> --check` runs beside them as a script.
2. **Handoff** (template `tines-reviewer`): run `/tines-review` for the story branch against `origin/main`. The session that built the story never runs it — the skill refuses a self-review.
3. **Apply.** The showrunner pipes the findings JSON into `./scripts/storyline apply <slug> tines-reviewer -` (ask). `apply` accepts the reused schema as-is (`--schema findings`) and saves it as `.storyline/out/<slug>/tines-reviewer-<attempt>.json`; `verify-merge` tags each finding with `source: tines-reviewer`.
4. **In CI.** `review.yml` runs the same reviewer headless on the PR (called by `storyline.yml` when its path filter matches), an independent instance with the base branch's configuration.

## Why it is not edited

The lifecycle wraps it with a handoff and an evidence check instead of editing its prompt (REPO-DESIGN.md §3.6). Its output shape is the finding shape every other reviewer reuses, so `verify-merge` treats all sources alike.

## Never (in lifecycle terms)

- Review a story the same session built.
- Hold tenant access or the Tines Stories MCP server.
- Decide G4 — its verdict feeds `verify-merge`; a person merges.
