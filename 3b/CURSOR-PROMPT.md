# Cursor prompt: pivot the kit to the 3B Workflow Factory

## Role
You are the builder for the **3B Workflow Factory**, a pivot of this repository (the Tines Storyworks / Agentic Story Factory Starter Kit) to **3B**, the Tines workflow platform. Work on branch `pivot/3b-workflow-factory`. Read `3b/PIVOT.md` and `3b/TASKS.md` first. Each task is a GitHub issue labelled `3b-pivot` (#4–#19).

## Background
- The thesis stays the same: **the value is the system around the prompt**. That system is procedures (skills), shared conventions, deterministic lint, a reviewer that is not the author, hooks, human-held gates, an ops pair that proposes and never acts, and a VERIFY ledger.
- What changes:
  - **How agents connect:** from the Tines Stories MCP server ("Mode 2") to the 3B MCP server, the 3B CLI or the in-product editor.
  - **What gets built:** from `stories/**/story.json` to 3B workflow directories.
- 3B facts to rely on (anything else must be marked **VERIFY**):
  - A workflow is a folder: `workflow.toml` (preserve its `id`; never copy it to another workflow), a root `README.md`, and one directory per step containing `config.toml`, a `Dockerfile` that starts with `FROM 3b/base`, code and a `README.md`.
  - Step templates are shell, python, typescript (Bun), react (with Tailwind) and agent. Default to TypeScript.
  - Each step is an isolated process. Its stdout becomes stdin for every step listed in `links`. Empty stdout stops downstream steps. A nonzero exit is the only failure signal.
  - Triggers: `route` (the step receives the raw HTTP request), `cron` (runs in Live only), `email_address`. A responding step sets `output = true` and prints a full HTTP response.
  - `route_auth`: space (the default), tenant, sso, external_id (for webhooks), connector, public (only when explicitly requested). Any route with a `route_type` needs a `title`. API routes ship `api.json` (OpenAPI 3.1 operations).
  - Build the workflow's own URLs from `_3B_WORKFLOW_BASE_URL`. Never hard-code hostnames.
  - Credentials go through connectors only. Never put secrets in code, chat or volumes. Volumes are mounted at `/storage/<name>`, and draft branches get isolated volumes.
  - Limits: `timeout` 1–300 s; 1 vCPU, 2 GiB memory. Use `retry_seconds` only when replaying side effects is safe.
  - Draft branches are published with **Push live**. Earlier published versions can be read and republished (rollback). **Step tests** pin a step's input and output and replay with no network.
  - Skills (`SKILL.md` with a frontmatter description) are first-class in 3B.
- Keep these principles: agents propose and people approve; the generator never approves its own work; one concern per PR; never invent an endpoint; any wider route exposure is a security-gated decision.

## Tasks (in order; open one PR per task and reference its issue)
**Phase 0, Foundation**
1. **#4:** Finish `3b/PIVOT.md` and rewrite the README thesis for 3B.
2. **#5:** Add `workflows/` (3B space-clone layout), `workflows/_template/` (a single TypeScript step plus README) and `workflows/_manifest.yaml` (slug → workflow id per space, no secrets).
3. **#6:** Write `AGENTS-3B.md` (under 200 lines) covering the facts above. Import it from `CLAUDE.md` and `.cursor/rules/3b.mdc`.

**Phase 1, Skills**
4. **#7:** Port `.claude/skills/tines-*` to `3b-build-workflow`, `3b-review`, `3b-ship`, `3b-rollback` and `3b-connect`.
   - Build loop: brief → copy template → implement → run step → pin step tests → README → review → Push live by a named person.
5. **#8:** Turn `tines-skills/` into a 3B skills pack:
   - Skills: onboarding guide, workflow brief, build conventions, route-auth policy, connector setup, volume design, health triage, retrospective, cost analyst.
   - Add eval cases for each skill in `storyline/evals/skills/`.
6. **#9:** Rename the crew in `.claude/agents` and `.cursor/rules` for 3B:
   - Roles: workflow-scout, workflow-architect, 3b-builder (the only role that holds 3B access), 3b-reviewer, security-reviewer, workflow-qa, eval-author, eval-curator, skill-curator.

**Phase 2, Gates**
7. **#10:** Write `scripts/lint_workflow.py` and `policies/lint-rules-3b.yml`. Rules:
   - `FROM 3b/base` is the first line.
   - `color` is set.
   - `timeout` is within 1–300.
   - `route_type` implies `title`.
   - An api route has `api.json`.
   - public, external_id and sso routes are flagged for approval.
   - No hard-coded hosts and no credential patterns.
   - Every workflow and step has a README.
   - Webpages set a title and an SVG favicon.
8. **#11:** Re-point the Storyline gates:
   - verify = step tests pass
   - ship = Push live by an approver listed in `gates/approvers.yaml`
   - a new exposure gate for route_auth changes
   - update `lifecycle/touch-sets.yaml` to match
9. **#12:** Add CI under `.github/workflows` for lint, non-author review, step tests, ship, drift (Live vs repo) and rollback.

**Phase 3, Kit**
10. **#13:** Build `workflows/kit-3b-launchpad/`:
    - A React kickoff page with tenant auth that captures the plan, spaces, connectors and goals.
    - A setup step that creates the customer repo from this template, seeds the tracker, makes one test call through the model connector and writes a setup report to a volume.
11. **#14:** Build the onboarding tracker:
    - Source of truth: `kit/tracker/backlog.yaml`.
    - Mirror it into a SQLite volume behind an API route, with a dashboard route on top.
    - Optionally sync to Tines Cases/Records.
12. **#15:** Add a starter catalog of reference workflows, each with step tests and a README:
    - webhook → 202 → async worker
    - scheduled sync to a volume
    - React app with an API route
    - agent step with tools
    - MCP server behind space auth
    - Slack or Jira notifier
    - email triage

**Phase 4, Operate**
13. **#16:** Build the ops pair. A scheduled health monitor reads run failures, and an agent proposes fixes as PRs or draft branches. It never pushes live.
14. **#17:** Build the migration lane: convert `stories/*` (start with example-enrich-ip) into 3B workflows with parity notes.

**Phase 5, Adoption**
15. **#18:** Retarget the guide app (3B workflow `kzAk6fRAGldc`):
    - New `AREA_NOTES` (in `parse.ts`).
    - New `ROLES` (in `Overview.tsx`).
    - Diagrams generated from `config.toml` links.
16. **#19:** Add 3B entries to `docs/VERIFY.md`: CLI/MCP capabilities, space-clone push, skill distribution, limits and tunnels.

## Definition of done (every PR)
Lint passes, step tests pass, READMEs are updated, unconfirmed claims are marked VERIFY, there are no secrets and no invented endpoints, and `3b/TASKS.md` is updated with a status column.
