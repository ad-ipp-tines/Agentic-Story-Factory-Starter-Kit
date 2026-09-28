---
name: tines-export
description: Exports one Tines story's JSON from the dev team into stories/<slug>/story.json, normalises it, lints it and stamps story.meta.yaml. Use after every build and before every commit.
disable-model-invocation: true
argument-hint: <story-slug> [--draft <id>]
allowed-tools: Bash(./scripts/tines export *), Bash(./scripts/lint-story.sh *), Bash(./scripts/diff-story.sh *)
---

# /tines-export — pull one story into the repo, normalised and linted

**Inputs:** `$0` = slug · optional `--draft <id>` to export a change-control draft instead of the live story.
**Never** hand-edit the result. If lint fails, the fix goes back through `/tines-build-story` and a new export.

## What an export is
- `GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true` (`&draft_id=<id>` with `--draft`), piped through `scripts/normalize.jq`: `exported_at` dropped, keys sorted, **agent order preserved** (links reference agents by index), `guid` and `diagram_layout` kept.
- Exports contain configuration only: **no credential values, no Resource contents, no events**. Credentials and Resources appear by name. Recipients are cleared and set from `stories/_manifest.yaml` by `ship.yml`.
- Import matches the target story **by name** (`mode: versionReplace`), so the exported `name` must equal `story.meta.yaml: name` in every environment.

## Steps
1. **Export.** `./scripts/tines export <slug> [--draft <id>]` — resolves `dev.story_id` from the manifest (`--env dev` is the default; prod exports are for `drift.yml`, which runs with `--out` and `--no-stamp`). Writes `stories/<slug>/story.json`. A 404 on a story you can open in the browser means an underprivileged or wrong-team key — say so, do not retry.
2. **Lint.** `./scripts/lint-story.sh stories/<slug>/story.json` — the rules in `policies/lint-rules.yml`; rules whose export key is `VERIFY` (#8) report `major` with the key note, never a false blocker. The PostToolUse hook runs the same lint on every write.
3. **Stamp.** The dispatcher stamps `exported_from: { env, story_id, draft_id, at, sha }` into `stories/<slug>/story.meta.yaml`. If it was run with `--no-stamp`, or the stamp is missing, run step 1 again without `--no-stamp` so the dispatcher stamps it — never `yq -i`, which can rewrite any file. `stop-gate.sh` refuses to end the turn while `exported_from.at` is older than the last logged `/mcp` call for this story.
4. **Diff.** `./scripts/diff-story.sh stories/<slug>/story.json --against HEAD` — actions added / removed / renamed, changed option keys per action (values redacted to lengths when they match a secret pattern), links added / removed, schedule changes, `monitor_*` and `disabled` flag changes, in Markdown. Print it; it becomes the PR body and the change-request description.
5. **Check the meta file** against the export: every credential and Resource referenced by name is listed; every AI Agent action has an `ai.agents[]` entry with `output_schema: true`, `token_alert`, `skills` and a `budget_ref` that exists in `policies/cost-ceilings.yml`; `name` matches; `schedule_interval_seconds` matches the schedule.

## Checklist
- [ ] `story.json` written, normalised (no `exported_at`), valid JSON, lint clean
- [ ] `exported_from` stamped and newer than the last `/mcp` call
- [ ] semantic diff printed and sane — no links removed or agents reordered without a reason you can state
- [ ] no value in the file that looks like a token, a secret, a Resource body or an email address (an export never contains one — if it does, stop and report)
- [ ] `story.meta.yaml` complete and consistent with the export

## Troubleshooting
| Symptom | Cause | Do |
|---|---|---|
| 404 on export | Wrong id, wrong team, or a key without access | Check the manifest id; the dispatcher names an underprivileged key as such |
| Lint: `naming` | `story.json.name` ≠ `meta.name` or missing `(sub)` | Rename in the tenant through `/tines-build-story`; never in the file |
| Lint: a `key: VERIFY` rule | Export key not yet confirmed | Read this export, set the key in `policies/lint-rules.yml`, record #8 in `docs/VERIFY.md` |
| Diff shows agents reordered | A rebuild changed the order | Confirm links on the canvas before committing; reorders rewire index-based links |
| Draft export differs from live | You exported `--draft` | Expected under change control; say which one the file holds |
