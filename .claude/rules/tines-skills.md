---
paths: ["tines-skills/**"]
---

# Tines Agent Skills (`tines-skills/<name>/SKILL.md`)

These files are pushed to the tenant by `skills.yml` through `POST` / `PUT /api/v1/skills` and attached to AI Agent actions and Workbench presets. An agent sees **only `name` and `description`** when deciding whether to load a skill, so those two fields carry the whole trigger.

- `name`: lowercase letters, digits and hyphens, ≤ 64 characters, **equal to the folder name**, unique per team; never contains "anthropic" or "claude".
- `description`: ≤ 1024 characters, third person, says what the skill does **and when** to use it.
- Body: under 500 lines and about 5,000 tokens; references one level deep; deterministic steps belong in the story or a script, not in prose.
- `metadata`: a flat map of strings only. CI stamps `git_sha` and `repo_path` — do not set them by hand.
- `license` and `compatibility` are free text; keep `compatibility` to the surfaces the skill is tested on (AI Agent action Task mode, Workbench presets).
- A rename is safe — the Skills API rewrites the name in every AI Agent action that references it — but it is still a PR: change the folder and the frontmatter together.
- Never paste a skill from an untrusted source. A skill changes agent behaviour in production, which is why CODEOWNERS for this tree includes the security-platform group.
- Preview before the PR with `/tines-skills-push <name>`; attaching a skill to a preset or an agent is [BY HAND] and is recorded in the story's `story.meta.yaml: ai.agents[].skills`.
- Size and count limits, versioning and credit consumption of skills are unpublished — VERIFY (docs/VERIFY.md #14).
