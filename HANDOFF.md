# HANDOFF — how this repository is enhanced from here

_For the AI contributors (Tines 3B, Cursor, Claude Code) that will extend this repository, and for the people who review their pull requests. Read this first, then [`AGENTS.md`](AGENTS.md)._

## 1. Where things stand

The repository is a complete first version: the stories-as-code layer at the root, the Storyline in [`storyline/`](storyline/README.md), and the starter kit in [`kit/`](kit/README.md) plus [`stories/kit-launch/`](stories/kit-launch/README.md). The spec for all of it is [`REPO-DESIGN.md`](REPO-DESIGN.md); the stories-as-code layer's own spec is [`DESIGN.md`](DESIGN.md).

**Checked before the first push**

| Check | Result |
|---|---|
| `./scripts/storyline check --all --strict` | 11 of 11 pass (phase names, tracker schema, field map, touch sets, 20 JSON schemas, bundle freshness, catalog ids, 496 relative links, env vars, agent frontmatter, template hygiene) |
| `python3 -m py_compile` on every script | 0 failures |
| `bash -n` on every hook and script | clean |
| Secret patterns, tenant hostnames, customer or personal names | none found |

**What is real and what is not yet**

| Item | State | What finishes it |
|---|---|---|
| Editor skills, hooks, agents, rules, CI workflows, policies, scripts, lifecycle, gates, templates, contracts, kit tracker, Records and Resource definitions, dashboard App source | real, reviewed | tenant confirmation of the VERIFY items they cite |
| `story.json` in `stories/example-enrich-ip`, `ops-error-router`, `ops-story-health-monitor`, `ops-tools-server`, `kit-launch` | **SKELETON** — each folder's README and action tables are the real design | build each through Mode 2 in a dev team, export, commit (see the maintainer release, `REPO-DESIGN.md` §15.6) |
| `kit/dashboard/dashboards/storyworks.dashboard.json` | **SKELETON** | build once by hand over the three Record types, export |
| `docs/VERIFY.md` | 80+ open items (behaviour not confirmed on a public page) | confirm in a tenant, record the result, change the repository if the answer differs |
| Study guides | 00 written; 01–06 specified | [`docs/study-guides/README.md`](docs/study-guides/README.md) |

**One decision to know about.** `./scripts/tines cr-promote` runs only inside GitHub Actions, only on a change request whose status is already APPROVED, and accepts a bypass only inside `rollback.yml`'s `break-glass-promote` job. The editor denies it outright.

## 2. Rules for AI contributors

These are the same rules every builder follows. `storyline.yml` and branch protection enforce most of them.

1. **Pull requests only.** Never push to `main`. One concern per pull request, small enough to review in ten minutes.
2. **Branch names say what the PR is.** `design/<slug>`, `story/<slug>`, `tracker/<name>`, `rollback/<slug>/<sha>` are lifecycle branches that `storyline.yml` checks against the touch sets. Everything else uses `enhance/<topic>`, `docs/<topic>` or `verify/<item>`.
3. **Fill the pull request template**, including the Lifecycle section when the PR moves a story.
4. **Never commit a secret, a tenant hostname, a customer name, a person's name or a model id.** Placeholders only: `<your-tenant>`, `<org>`. `block-secrets.sh` and gitleaks will stop you; do not work around them.
5. **Never state an unconfirmed behaviour as fact.** Cite its `docs/VERIFY.md` item, or add a new one.
6. **Never invent a Tines API endpoint or a Tines Stories MCP server tool name.** Use only what [`REPO-DESIGN.md`](REPO-DESIGN.md) and [`DESIGN.md`](DESIGN.md) name; propose anything new as a design change first.
7. **Do not weaken a control to make a check pass.** Hooks, permission rules, CODEOWNERS, touch sets, the human gates and the break-glass path are the product. A PR that loosens one needs a written reason in its description and a security-platform review.
8. **Leave `AGENTS.md` §4–§9 and its §12 shared block alone** unless the same change is made in `tines-skills/story-build-conventions/SKILL.md` in the same PR (`lint.yml` compares them byte for byte).
9. **Run the checks before opening the PR:** `./scripts/storyline check --all`, `python3 -m py_compile` on changed Python, `bash -n` on changed shell, and `./scripts/kit bundle --check` if you touched `tines-skills/`, `kit/` or `storyline/lifecycle/`.
10. **The four MCP surfaces are only ever called modes** (Mode 1–4, [`AGENTS.md`](AGENTS.md) §2).

## 3. The enhancement backlog

Work top to bottom. Each item is one or more pull requests.

**Before any agent starts: GitHub setup (a person, once)**

These are repository settings no pull request can make. Until they exist, several workflows fail closed.

1. **Branch protection on `main`:** require the `storyline.yml` check, require pull request reviews, turn on "Require review from Code Owners", and block force pushes.
2. **Environments, each created with its protection before any secret is added** (GitHub creates a missing environment unprotected): `production` (required reviewers = the G5a team in `storyline/gates/approvers.yaml`), `break-glass` (required reviewers, "Prevent self-reviews" on), `kit-sync` (required reviewers), `storyline-evals-ide` (required reviewers), `prod-read`, `tracker`, and `review` (no reviewers; deployment branches allow pull request branches).
3. **Secrets** go into those environments, never repository scope. Move `ANTHROPIC_API_KEY` for `propose-fix.yml` into an environment too.
4. **The `tracker-bot` GitHub App**, installed on the repository, for tracker and kit pull requests.
5. **The three labels** the workflows use: `ops-proposal`, `drift`, `budget`.

**Known gaps from the final review** (each a small PR)

- `git log --output=<file>` and `git show --output=<file>` can write files; narrow the `git log` and `git show` allow rules in `.claude/settings.json` and `review.yml`.
- "The platform stops the story at 100 %" is unconfirmed; find it in `policies/cost-ceilings.yml`, `scripts/ai_usage.py`, `drift.yml`, `stories/ops-error-router/` and `tines-skills/alert-policy/`, and either confirm it (VERIFY) or reword it.
- `drift.yml`, `rollback.yml` and `propose-fix.yml` still run `gh label create`; remove it now that the labels are a setup step.
- `REPO-DESIGN.md` §2, §3.2 and §3.3 still call some files unchanged that the review fixes edited; bring the tables up to date.
- Stale references: `kit/tracker/README.md` (the `--out` example), `docs/02-workflows.md` (which subcommands ask), `storyline/observability/README.md` and the example `events.jsonl` (who writes `merged` events), `storyline/crew/tines-builder.md` and `storyline/logbook.md` (the builder's `memory` setting), `kit/dashboard/README.md` (filterable fields), and the `kit-sync` descriptions in `kit/resources/README.md`.
- Decide the builder's memory: with `memory: local` and writes to `.claude/**` denied, it cannot save memory. Drop `memory` or allow its one folder.
- `phase-gate.sh` denies every Tines Stories MCP server call until `docs/VERIFY.md` #1 records the tool input shapes; until then create each dev story by hand and record its id with `./scripts/tines manifest-set-dev-id`.
- The kit's own build fails G1 as written (`./scripts/storyline ready kit-launch`); the maintainer release in P0 must start by writing its design artifacts under `storyline/work/kit-launch/`.
- Confirm on a live run that the job token can read environment approvals for G5a evidence, K45 (the change request status after a push), and the `tines-connect` fallback flag (VERIFY #5).

**P0 — make it real in a tenant**
1. Confirm the VERIFY items the day-one path depends on, in a maintainer tenant: the import behaviour and ids (K6, K8, K16, K17), Pages behaviour (K31, K32), credential naming (K9), the GitHub token permissions (K11, K12), and the scaffold's export key names. One `verify/<item>` PR per item: the result, the date, and the repository change if the answer differs.
2. Run the maintainer release ([`REPO-DESIGN.md`](REPO-DESIGN.md) §15.6): build `[KIT] 00` section by section with build prompts P-K1…P-K14, export with random URLs, build and export the dashboard, `./scripts/kit bundle`, pass `kit.yml`'s release job.
3. Replace the four remaining SKELETON exports by building each story through Mode 2 and exporting it.

**P1 — make it learnable**
4. Write study guides 01–06 to the spec in [`docs/study-guides/README.md`](docs/study-guides/README.md), one PR per guide, each with diagrams.
5. Consolidate `docs/`: the two numbering sets (the redirect stubs and the long pages) into one, fixing every link (`doc_links_resolve` must still pass).
6. Add a diagram to every phase file in `storyline/phases/` and every gate file in `storyline/gates/`.

**P2 — make it stronger**
7. Run the held-out eval cases in `storyline/evals/` against a dev tenant and record baselines; add regression cases from the first real failures.
8. Once Cursor can scope an MCP server to one chat (K4), extend Cursor support to the non-builder crew.
9. Replace `guard-mcp.sh`'s destructive-name regex with an explicit deny list once the Tines Stories MCP server's tool names are recorded in `docs/VERIFY.md`.
10. Add a second worked example beyond `example-enrich-ip`: an AI Agent story with one tool, an output schema and a token alert, taken through the whole lifecycle.

## 4. Starting prompts

**For Cursor or Claude Code, one item at a time**

```text
Read HANDOFF.md, AGENTS.md and REPO-DESIGN.md. Take backlog item <n> from HANDOFF.md §3.
Work on a new branch named as HANDOFF.md §2 rule 2 says. Follow every rule in HANDOFF.md §2.
Before opening the pull request, run the checks in rule 9 and paste their output into the PR
description, with the list of files changed and any VERIFY items you cited or added.
```

**For Tines 3B, repository review**

```text
Review this repository against HANDOFF.md, AGENTS.md and REPO-DESIGN.md. Do not change files.
Produce a list of proposed enhancements, each with: the problem, the files involved, the smallest
change that fixes it, the risk, and which HANDOFF.md §3 item it belongs to (or "new"). Flag any
control in HANDOFF.md §2 rule 7 that a proposal would weaken. Then open one pull request per
accepted proposal, following HANDOFF.md §2.
```

**For study guides**

```text
Write study guide <nn> to the spec in docs/study-guides/README.md. Reuse the diagrams in
docs/study-guides/00-visual-tour.md where they fit and never contradict them. Link every claim
to its source file. Run ./scripts/storyline check --all before opening the pull request.
```

## 5. How people review

- **Watch the pull requests and the required check.** `storyline.yml` is the one required check; it calls `lint.yml` and `review.yml` when their paths change.
- **CODEOWNERS decide who must approve.** `policies/`, `.claude/`, `.github/`, `storyline/gates/approvers.yaml`, `kit/` and `stories/ops-*` and `stories/kit-*` need a security-platform review.
- **Labels to watch:** `ops-proposal` (from the monitor), `drift` (production differs from `main`), `budget` (a ceiling reached 80 %).
- **Merge only what you would have written yourself.** An agent's pull request is a proposal; the merge is the decision.
- **When a PR loosens a control**, ask for the reason in writing before reviewing anything else in it.
