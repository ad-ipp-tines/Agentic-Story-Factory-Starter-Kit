---
name: tines-review
description: Reviews the changed story JSON exports and meta files against AGENTS.md conventions in a fresh context and returns findings as JSON. Use before opening a PR, in CI, or when asked to review a story change.
context: fork
agent: tines-reviewer
argument-hint: [pr-number | branch]
allowed-tools: Read, Grep, Glob, Bash(./scripts/lint-story.sh *), Bash(./scripts/diff-story.sh *)
---

# /tines-review — fresh-context review, machine-parseable findings

**Runs in:** a forked context on the `tines-reviewer` subagent — no MCP server, no API key, read-only tools. You judge the diff, the export, the meta file, the tests and the policies. Nothing else.
**Input:** `$0` = a PR number or a branch (optional; default is the current branch against `origin/main`).
**Output:** only the JSON defined in `.claude/skills/tines-review/references/findings-schema.json`. No prose before or after it. `review.yml` passes the schema to `--json-schema` (the `@file` form is VERIFY #21).

## Refuse to self-review
If the conversation this context was forked from built the story under review (a `/tines-build-story` run for the same slug in this session), output `{"verdict":"changes_requested","findings":[{"path":"<slug>","rule":"self-review","severity":"blocker","message":"The generator never reviews its own work; run /tines-review from a fresh session."}]}` and stop.

## Procedure
1. **Scope.** You have no `git diff` (`--output` writes files) and no `jq` (it can print the environment). In CI, `review.yml` lists the PR's changed paths under `stories`, `tines-skills`, `policies` and `.claude/skills` in `.review-scope/changed-paths.txt`, and the PR's own changes to `.claude/` and `scripts/` in `.review-scope/pr-config.diff` — read both. Elsewhere, the story is the one the handoff or `$0` names (`story/<slug>/<short>`). One story per PR is the rule: more than one changed `stories/<slug>/` directory is a `major` finding (`rule: one-story-per-pr`).
2. **Lint first.** `./scripts/lint-story.sh stories/<slug>/story.json --format json` — every `error` finding becomes a `blocker` with the lint rule id; every `warning` a `minor`. A rule whose export key is still `VERIFY` (#8) reports as `major` with the note "key name VERIFY", not as a blocker.
3. **Read** `story.json`, `story.meta.yaml`, `tests/expectations.yaml`, `README.md`, and `./scripts/diff-story.sh stories/<slug>/story.json --against origin/main`.
4. **Check the list below** (letters are the `rule` ids when no lint rule id applies). Conventions in full: `.claude/skills/tines-build-story/references/story-conventions.md`.
5. **Write findings.** `path` = `stories/<slug>/story.json#<action name>`, `stories/<slug>/story.meta.yaml`, or `tines-skills/<name>/SKILL.md`. `message` states the defect in one sentence. `suggested_fix` says what to change. `suggested_prompt` is a ready `/tines-build-story <slug> "<prompt>"` whenever the fix is a story change — fixes go through `/mcp`, never through editing the export. Credit observations go in `cost_notes`.
6. **Verdict.** `changes_requested` if any finding is `blocker` or `major`; otherwise `pass`.

## The checklist
| Rule | Check | Severity when it fails |
|---|---|---|
| **a** naming | `name` matches `^\[[A-Z]+\] [0-9]{2} · .+`; equals `meta.name`; sub-stories end in `(sub)`; actions snake_case, unique, described; a Note carries purpose and a mode badge | blocker |
| **b** contract | `(sub)` stories end on a message-only Event Transform named `result` emitting 3–5 fields; every failure branch ends on `error` with `{status, error_category, retryable, message}`; the story description states the `result` shape | blocker |
| **c** http | every HTTP Request action: retry on `[429, 500-599]`, retries ≤ 8, emit failure event **Always**, failure output linked, expected non-2xx excluded from error logging (key names VERIFY #8) | blocker (major while keys are VERIFY) |
| **d** agents | every AI Agent action (`Agents::LLMAgent` in exports — VERIFY #8): output schema present; a Trigger directly after it on `severity` / `proposed_change.kind` / `needs_human`, never confidence; ≤ 5 tools, ≤ 1 MCP connection, never both; `meta.ai.agents[]` entry with `output_schema: true`, `token_alert {notify, disable}`, `skills`, and a `budget_ref` that exists in `policies/cost-ceilings.yml: agents` | blocker |
| **e** secrets | no options value matches any `scripts/tines_common.py: SECRET_PATTERNS` entry — the one list, which `lint_story.py` applies (tokens, bearer values, Slack or AWS key shapes, inline `api_key`); no real email address (lint rule `email_in_export`); no webhook URL with a secret | blocker |
| **f** references | every credential and Resource referenced in options is listed in `meta.credentials[]` / `resources[]` (reference syntax VERIFY #8); every Record written is in `meta.records[]` | blocker |
| **g** monitoring | `meta.tier: production` ⇒ `monitoring.monitor_failures: true`, `recipients: manifest`, a `no_events_watchdog` on the entry or scheduled action at ≈ 2× its interval; `keep_events_for_days ≥ 30`; no literal recipient in the export | blocker |
| **h** diff sanity | agent count change and any removed link explained in the PR body; no agent reordered without a reason; no `guid` or `diagram_layout` edited by hand; `exported_from.at` newer than the last `/mcp` activity row for the story if `.tines/mcp-activity.jsonl` is present | major |
| **i** tenant skills | `tines-skills/*/SKILL.md`: `name` = folder, `^[a-z0-9]+(-[a-z0-9]+)*$`, ≤ 64 chars, no "anthropic"/"claude"; `description` ≤ 1024 chars, third person, says what **and when**; body < 500 lines; `metadata` flat strings without `git_sha` set by hand; `license`, `compatibility` present | major |
| **j** tools | tool names namespaced snake_case ≤ 64; any `block|delete|isolate|disable` tool starts with `request_`; Mode 4 lookups marked Read only (VERIFY where the export carries hints); each tool description 3–4 sentences with output fields and one example; long tools return `{status: started, id}` | major |
| **k** never-touch | no action writes (disable, recipients, update) to a story id, name pattern or team in `policies/never-touch.yml`; an `ops-*` slug changed by a non-ops PR | blocker |
| **l** tests | `tests/sample-event.json` uses documentation-range values only; `expectations.yaml` names the entry action and `result_fields` matching `result` | minor |
| **m** cost | new AI Agent action, tool count, schedule interval, provider — summarised in `cost_notes`; a schedule shorter than the sweep's overlap tolerance or a new smart-model agent without a budget line | major |

## Never approve a story that
references a credential or Resource not in meta · contains a string that looks like a token or an email address · has an AI Agent action without an output schema, a post-agent Trigger, a token alert or a budget line · has an unhardened HTTP Request action · has `tier: production` and no monitoring in meta · exposes a `block|delete|isolate|disable` tool not prefixed `request_` · removed links or reordered agents without the PR body explaining it.
