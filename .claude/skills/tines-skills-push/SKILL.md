---
name: tines-skills-push
description: Validates tines-skills/<name>/SKILL.md and dry-runs the Skills API upsert against a team, showing create vs update. Use before opening a PR that adds or changes a tenant-side skill, or to push to the dev team for testing.
disable-model-invocation: true
argument-hint: <skill-name> [--dev]
allowed-tools: Bash(./scripts/tines skills-push *), Read, Grep
---

# /tines-skills-push — preview what `skills.yml` will do; push to dev for a live test

Tines Agent Skills (`tines-skills/<name>/SKILL.md`) are pushed to the tenant by `.github/workflows/skills.yml` after merge through `POST` / `PUT /api/v1/skills` and attached to AI Agent actions and Workbench presets. They change agent behaviour in production, so they are reviewed like code and CODEOWNERS for `tines-skills/` includes the security-platform group.

**Inputs:** `$0` = the skill name (equals the folder) · `--dev` = also push to the dev team (`TINES_TEAM_ID`) for a live test.
**Environment:** `TINES_TENANT`, a team-scoped `TINES_API_KEY`, `TINES_TEAM_ID` (dev). Never reads `.env`. Production pushes happen only in `skills.yml`.

## Steps
1. **Frontmatter check** (`.claude/rules/tines-skills.md`): `name` = folder, lowercase letters / digits / hyphens, ≤ 64 chars, unique per team, no "anthropic" or "claude"; `description` ≤ 1024 chars, third person, says what **and when** (an agent sees only these two fields when deciding to load it); body under 500 lines and about 5,000 tokens; `metadata` a flat string map **without** `git_sha` or `repo_path` (CI stamps them); `license` and `compatibility` present.
2. **Validate.** `./scripts/tines skills-push --validate-only --only <name>` — the same frontmatter and body checks `lint.yml` runs. The Agent Skills reference validator (`skills-ref`) is **not** run until its package and publisher are confirmed (VERIFY #21): never `npx --yes` a package by name. Once confirmed and pinned (a lockfile plus `npm ci`, or vendored), it runs as `npx --no skills-ref validate tines-skills/<name>`; until then say the validator was skipped.
3. **Dry run.** `./scripts/tines skills-push --team $TINES_TEAM_ID --dry-run --only <name>` — for the skill: `GET /api/v1/skills/<name>?team_id=` → 200 means `PUT /api/v1/skills/<name>` (update), 404 means `POST /api/v1/skills` (create), with `team_id`, `name`, `description`, `body`, `license`, `compatibility`, `metadata`. Print create-versus-update and the field diff. Nothing is sent.
4. **With `--dev`:** `./scripts/tines skills-push --team $TINES_TEAM_ID --only <name>` — the real upsert into the **dev** team. Then test it live: attach it [BY HAND] to a scratch AI Agent action or a Workbench preset in dev, run the dev sweep on a deliberately failing scratch story, and read the agent's event `steps` to see the skill load.
5. **Say what happens next:** open the PR (`lint.yml` validates the frontmatter, `review.yml` checks the body against `AGENTS.md`, a human merges); `skills.yml` pushes to the prod team; **attaching** a skill to a preset or an agent has no API found (VERIFY #14) and is [BY HAND], recorded in the story's `story.meta.yaml: ai.agents[].skills`.

## Renames and deletes
- **Rename:** change the folder and the frontmatter `name` in one PR. The API rewrites the name in every AI Agent action that references it — still a PR, still a review.
- **Delete:** only `skills.yml` via `workflow_dispatch` with `confirm_delete=<name>` → `DELETE /api/v1/skills/<name>?team_id=`. Removing the folder alone leaves the skill live in the tenant. This skill never deletes.

## Never
- Push to the prod team from the IDE (`--team` must be the dev team id; the prod id is in `policies/never-touch.yml: teams`).
- Paste a skill from an untrusted source, or a skill body that names a customer, a person, a credential value or an unverified product claim.
- Set `metadata.git_sha` by hand.

## Checklist
- [ ] frontmatter valid; name = folder; description says what and when
- [ ] validator run (or its absence stated)
- [ ] dry run printed: create or update, field diff
- [ ] with `--dev`: pushed to dev, attached by hand, load observed in an agent's `steps`
- [ ] attach step and prod push stated as `skills.yml` + [BY HAND]

Size and count limits, versioning and credit consumption of skills are unpublished — VERIFY #14.
