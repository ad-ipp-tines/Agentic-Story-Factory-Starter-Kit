# tines-skills/ — Tines Agent Skills as code

_tines-stories-as-code · builder `agent-skills` · spec `../DESIGN.md` §3.7, §4.3, §2.3 #12–#14 · written 2026-09-24_

**Mode badge: none.** Skills are not one of the four MCP surfaces. They are `SKILL.md` files the tenant loads into a **Mode 3** AI Agent action (the sweep's `triage` agent) and into **Mode 1** Workbench presets. Nothing in this folder is reachable through `/mcp`, and nothing in it runs on its own.

## 1. Two skill families, one standard, one PR

| | IDE skills | Tines Agent Skills (this folder) |
|---|---|---|
| Path | `.claude/skills/<name>/SKILL.md` | `tines-skills/<name>/SKILL.md` |
| Teaches | the editor: connect, build, export, review, ship, roll back | the tenant's agents and presets: triage, budgets, alert policy, build conventions |
| Loaded by | Claude Code; Cursor (reads the tree as a legacy path) | the AI Agent action it is attached to; the Workbench preset it is enabled on |
| Runs on | the editor's model plan | the tenant's AI provider (AI credits, or a custom provider) |
| Pushed by | nothing — the editor reads the repository | `.github/workflows/skills.yml` on merge to `main`, through the Skills API |
| Reviewed by | `lint.yml` + `review.yml` + CODEOWNERS | the same PR and the same gates, plus the security-platform CODEOWNERS group (a skill changes agent behaviour in production) |

Both families follow the **Agent Skills standard**: a folder named after the skill containing `SKILL.md` with YAML frontmatter and a Markdown body. Agents see only `name` and `description` until the skill is triggered (about 100 tokens resident per skill); the body loads on use and must stay under 5,000 tokens / 500 lines. Tines attaches these same files to AI Agent actions (since 2026-08-11) and to Workbench presets, and exposes CRUD API endpoints for them (since 2026-09-01).

## 2. The skills

| Skill | Attached to [BY HAND] | Owner (a role) | What it does |
|---|---|---|---|
| `story-health-triage` | `[OPS] 10 · Monitor story health and credits` → `triage`; the Ops Workbench preset | ops | Reads the evidence for one unhealthy story, classifies the failure (transient / configuration / credential / external / silent), decides escalate vs propose, returns the output schema |
| `credit-budget-analyst` | the same `triage` agent; the Ops Workbench preset | ops | Reads AI-usage rows against the budgets in the prompt, names the costliest story or action with the row that proves it, proposes one `credit_action` |
| `alert-policy` | the Ops Workbench preset; optionally `triage` (see §7) | ops | States which monitoring options, recipients and thresholds each story tier carries, and how each number is derived from baseline data |
| `story-build-conventions` | the builders' Workbench for Storyboard preset (whether that surface honours preset skills is VERIFY #14) | platform | The repository's story conventions, so answers given inside Tines match `AGENTS.md` |

`_manifest.yaml` in this folder records each skill's team scope and attachment targets. `stories/ops-story-health-monitor/story.meta.yaml: ai.agents[].skills` records what is actually attached to each agent; the reviewer refuses an agent whose meta lists a skill this folder does not contain. The `critic` agent carries no skills on purpose.

## 3. Frontmatter contract (enforced by `lint.yml`; advisory in `lint-on-write.sh`)

```yaml
---
name: story-health-triage          # == directory name; ^[a-z0-9]+(-[a-z0-9]+)*$; <= 64 chars; unique per team; never contains "anthropic" or "claude"
description: >-                    # <= 1024 chars, third person, says WHAT it does and WHEN to use it — agents choose on this line alone
  Triages a failing or silent Tines story … Used when …
license: Proprietary
compatibility: Tines AI Agent action (Task mode) and Workbench presets
metadata:                          # flat string map only; CI adds git_sha and repo_path at push time — never write them here
  owner: ops
  version: "1"
---
```

Body rules: Markdown; under 500 lines and about 5,000 tokens; references one level deep (a `references/` file next to `SKILL.md` is allowed — nothing here needs one yet); no secrets, no tenant hostnames, no customer or personal names, no `/mcp` tool names (unpublished), no Tines API endpoint that `../DESIGN.md` does not list; VERIFY in place on any behaviour the research did not confirm, so the agent knows the boundary too.

## 4. How they are versioned here

- **Git is the version store.** The tenant holds one copy of each skill per team; history lives in `git log -- tines-skills/<name>/SKILL.md`. No server-side versioning of skills is documented (VERIFY #14), so never rely on the tenant to remember a previous body.
- **`metadata.version`** is bumped by hand when the skill's *behaviour* changes (a new rule, a changed threshold source), not for a typo. It is a string.
- **`metadata.git_sha` and `metadata.repo_path`** are stamped by `scripts/tines skills-push` at push time so the tenant copy says which commit it came from. Whether `metadata` accepts these keys is VERIFY #14; if the API rejects them the push fails with the API's error — remove the two keys from `scripts/push_skills.py`, record the finding in `../docs/VERIFY.md` #14, and fall back to `metadata.version` alone.
- **Renames** are one PR that changes the directory name and `name:` together. The API rewrites the name in every AI Agent action that references the skill, so the attachment survives — the PR still needs the security-platform review.
- **Deletion** never happens by removing the folder. Only `skills.yml` run by `workflow_dispatch` with `confirm_delete: <name>` calls `DELETE /api/v1/skills/<name>?team_id=`; the folder is removed in the same PR that records why.
- **One shared block.** `story-build-conventions/SKILL.md` carries the conventions between `<!-- shared-block: agents-md-conventions v1 begin -->` and `<!-- shared-block: agents-md-conventions v1 end -->`. It is a distillation of `AGENTS.md` §4–§9, not a copy: the skill is read by a model inside Tines, `AGENTS.md` by an editor. `../DESIGN.md` §3.7 has `lint.yml` compare a checksum of this block with `AGENTS.md`; `AGENTS.md` §12 carries the identical block between the same markers, so the comparison runs on every PR and fails when the two copies differ. The rule: a change to a convention is one PR that touches both files, and the `v1` in the marker is bumped with `metadata.version`.

## 5. How they are pushed

**Endpoints (as recorded in `../DESIGN.md` §3.4 and §4.3 — the only Skills API calls this repo makes; request and response field names VERIFY against the tenant's API reference before the first push):**

| Step | Call | Notes |
|---|---|---|
| exists? | `GET /api/v1/skills/<name>?team_id=<team>` | 200 → update; 404 → create (a 404 on a *write* means an under-privileged key — the dispatcher says so) |
| update | `PUT /api/v1/skills/<name>` with `team_id`, `description`, `body`, `license`, `compatibility`, `metadata` | body = the Markdown below the frontmatter |
| create | `POST /api/v1/skills` with `team_id`, `name`, `description`, `body`, `license`, `compatibility`, `metadata` | |
| delete | `DELETE /api/v1/skills/<name>?team_id=` | `workflow_dispatch` + `confirm_delete` only |

**The path a change takes:**

1. Edit or add `tines-skills/<name>/SKILL.md`. The path-scoped rule `.claude/rules/tines-skills.md` loads in the editor; `lint-on-write.sh` runs `npx skills-ref validate` (package availability VERIFY #21) as advisory feedback in the same turn.
2. **`/tines-skills-push <name>`** — validates, then `./scripts/tines skills-push --team $TINES_TEAM_ID --dry-run --only <name>` prints *create* or *update* and the payload. With `--dev` it pushes to the **dev team** so you can run the dev sweep on a deliberately failing scratch story and read what the agent returned (§6). Without a tenant at all, `./scripts/tines skills-push --validate-only` runs the same frontmatter and body checks the validator applies (name = directory, the name regex and length, description present and ≤ 1024, flat `metadata`, body under 500 lines, no token-like strings) — this is the call `lint.yml` makes.
3. Open a PR. `lint.yml` validates the frontmatter and the shared-block checksum; `review.yml` checks the body against `AGENTS.md`; CODEOWNERS for `tines-skills/` includes the security-platform group; a human merges.
4. **`skills.yml`** (GitHub environment `production`) runs `./scripts/tines skills-push --team $TINES_TEAM_ID_PROD` for every skill in this folder: the upsert in the table above, `metadata.git_sha` and `metadata.repo_path` stamped. The team id is the same one `stories/_manifest.yaml: environments.prod.team_id` records; it is never written in this folder.
5. **[BY HAND, once per attachment — no attach API found, VERIFY #14]:** open the AI Agent action (or the Workbench preset), add the skill, and record it in `stories/<slug>/story.meta.yaml: ai.agents[].skills` (agents) or `_manifest.yaml: skills.<name>.attach` (presets) in a follow-up PR so the repo stays the truth.

The push identity is the prod **team-scoped** key (`policies/POLICY.md` → CI-prod). Skills are not stories: they are not under change control, and a pushed skill takes effect on the next agent run. That is exactly why the PR review is the only gate — treat a skill change with the seriousness of a production story change.

## 6. Testing a skill before it reaches production

Skills have no test runner. The repo's substitute, per `../DESIGN.md` §4.3 step 2:

1. `/tines-skills-push <name> --dev` → the skill lands in the dev team.
2. In the dev team, break a scratch story on purpose (an HTTP Request action that references a credential name that does not exist; a scheduled action with its source turned off) and trigger the dev copy of `[OPS] 10` by hand.
3. Read the `triage` agent's event: the output-schema fields, `meta.credits_used`, tokens and model, and the tool `steps`. Score four things: did it pick the right tool, did it finish, did it ask for an approval a person would reject, what did it cost per completed finding.
4. Fix the *description* or the *body* before you add a tool. Repeat until the finding matches the scratch story's `tests/expectations.yaml`.
5. Only then open the PR.

## 7. Design note — what this folder contains versus `../DESIGN.md` §2.2

`../DESIGN.md` §2.2 first listed three skills here (`story-health-triage`, `credit-budget-analyst`, `story-build-conventions`) and no manifest. Both additions below are kept, and `../DESIGN.md` §2.2, §2.3 #12 and the root `README.md` tree now list them:

- **`alert-policy/SKILL.md`** — the monitoring policy (which stories get which options and recipients, and how a threshold is derived) as a skill, so the Ops Workbench preset answers policy questions the way the repo does and the `triage` agent's `alert_rule_proposal` follows a stated rule. §5.4 of the design attaches **two** skills to `triage`; attaching `alert-policy` as a third is optional and, if done, is recorded in `story.meta.yaml`.
- **`_manifest.yaml`** — per-skill team scope and attachment targets, in the shape of `stories/_manifest.yaml`.

Nothing else here departs from the spec.

## 8. What a skill must never contain

- A credential value, a webhook URL that carries a secret, a tenant hostname, a person's name or address, a customer name — `block-secrets.sh` and `lint.yml` are the backstop, not the rule.
- An instruction that tells the agent to *do* something to production. Skills here teach reading, classifying and proposing; the story's Triggers, Resources and a human approval decide.
- A `/mcp` tool name (unpublished), or a Tines API endpoint `../DESIGN.md` does not list.
- Text copied from a customer engagement or an observed call.
- A claim that a feature exists when the research says VERIFY — write the marker into the skill body.

## 9. Verify in your tenant before presenting

| Item | How | Then |
|---|---|---|
| Skill size and count limits per team, and whether the tenant versions skills | The Skills page; push a 500-line body to a scratch team | Tighten the body rule in §3 |
| Whether skills consume AI credits beyond the tokens they add to the prompt | `GET /api/v1/ai_usage?group_by=action` before and after attaching one | `credit-budget-analyst` §1 last bullet |
| Whether Workbench for Storyboard honours skills enabled on a preset | Enable `story-build-conventions` on a preset; ask Workbench for Storyboard to draft an action; compare with the conventions | Where `story-build-conventions` is attached; `_manifest.yaml` |
| Whether attaching a skill to an agent or preset has an API | The API reference; the AI Agent action's properties panel | `skills.yml` step 5 stops being [BY HAND] |
| Whether `metadata` accepts `git_sha` and `repo_path` | Push one skill to the dev team without `--dry-run`; read it back with `GET` | `scripts/tines skills-push` metadata handling |
| `npx skills-ref validate` availability in CI | A dry run | `lint.yml`, `lint-on-write.sh` |
| The exact request and response fields of `POST` / `PUT /api/v1/skills` | One create and one update against a scratch team | The endpoint table in §5 |

Nothing in this table is a headline claim. See `../docs/VERIFY.md` #14 and #21.
