# Glossary — the words the lifecycle uses, and only those meanings

_Phase, status and gate names are defined once, in [`lifecycle/state-machine.yaml`](lifecycle/state-machine.yaml); this page explains them. Spec: REPO-DESIGN.md §4–§6._

## The state of a story

**Story key (slug).** The kebab-case name of a story: its folder under `stories/` and `storyline/work/`, its row key in `kit/tracker/backlog.yaml`, its entry in `stories/_manifest.yaml`. Generated once, never changed.

**Phase.** Where the lifecycle work on a story is: `intake · discover · design · build · verify · ship · operate · improve`, in that order. Phase is not the same as "running": a live story whose next iteration is in `design` is still running in production and still monitored.

**Holding state.** `parked` — the story waits (budget, WIP, or a human decision) and returns to the phase it left when a human unparks it.

**Terminal state.** `rejected` or `retired`. Nothing runs; the folder stays as the record of why.

**Status.** The condition within a phase: `active` (work can proceed) · `awaiting_gate` (a gate is open) · `rework` (back in build after a rejection) · `blocked` (GX is open). In operate only: `shadow` · `live`. Which phase may hold which status is `phase_info` in the state machine.

**Open gate.** The one gate currently waiting for a decision, or `none`. At most one per story.

**Attempt.** The rework counter within one design iteration: 0 for the first build, then 1, 2, 3. At `rework_cap` (3) the story escalates (GX). It resets to 0 for a new iteration and when a person resumes a story from GX at the cap.

**Iteration.** One pass from design to operate. `improve` → `design` (`change_needed`) or a G7 `rescope` starts a new one; `design.md` records its number.

**WIP limit.** At most `wip_limit_per_owner` (1) stories per owner in build or verify. A breach at the design → build boundary parks the story through GB.

## Moving between states

**Transition.** A move from one phase (and status) to another. Every allowed transition is a row in the state machine; nothing else can move a story.

**Gate.** A point where a story may not move until a decision is recorded. Eleven gates: G0, G1, G2, G3, G4, G5a, G5b, G6, G7, GB, GX ([`gates/README.md`](gates/README.md)). A gate is **human**, **deterministic**, **layered** (G4: deterministic + model + human) or **budget** (GB: deterministic to open, human to release).

**Check.** A named, deterministic test over evidence that moves a story without a person: `discovery_complete`, `build_evidence`, `improve_trigger`, `change_needed`, `retire_candidate`, `retro_closed`. Implemented in `scripts/storyline_state.py`; applied by `./scripts/storyline advance`.

**Decision.** The word a gate records (`build`, `merged`, `approved_and_pushed`, `go_live`, …). Each gate's allowed words are `gate_info.<gate>.decisions`.

**Instrument.** The one way a gate's decision is made and recorded: a merge, a GitHub environment review, a change request in Tines, the `gate_decision` Page, or `/storyline-gate`. Each Tines-side gate has exactly one: the Page when Records are entitled, `/storyline-gate` only on the Community path.

**Evidence.** What a check or a decider reads: files on disk and on `main`, branches, PR state, `story.meta.yaml`'s `exported_from`, `events.jsonl`. **Git wins** over the tracker: when they disagree, `storyline next` prints `drift` and proposes a correction.

**Dispatch boundary.** The moment between two units of work where `storyline next` (or section D in Tines) decides what runs next. GB fires only here, never in the middle of a phase.

**Provisional.** A Tines-side change (a Page decision, a runtime crew member's draft) that has not yet reached `main`. It becomes true only when a human merges the tracker PR that carries it; a closed PR reverts it on the next full sync.

**Shadow.** The operate status of a story whose contract says `risk.side_effects: true`: its side-effecting actions sit behind a Trigger on the Resource `<slug>_rollout`, so it computes and records but does not act. **Live** is the status after G6 (`go_live`), or straight after ship for a story with no side effects.

## Who does the work

**Crew member.** A narrow agent with one job, an objective, an output format, tool guidance and boundaries (P5). **IDE crew** run in the editor as Claude Code subagents or Cursor chats (`story-scout`, `story-architect`, `eval-author`, `security-reviewer`, `story-qa`, `eval-curator`, `skill-curator`). **Tines-side (runtime) crew** are tool-less AI Agent actions in `[KIT] 00` section D (`planner`, `brief_writer`, `retro_writer`). **Reused** crew are the scaffold's `tines-builder`, `tines-reviewer`, and the ops sweep's `triage` and `critic`, unchanged.

**Showrunner.** The lead: the `/storyline` skill in the Claude Code main session, `storyline.mdc` in a Cursor main chat, and section D's deterministic dispatch in Tines. It runs `./scripts/storyline next`, spawns what the script names, pipes the outputs into `apply`, and stops at every gate. It writes no file itself and decides no gate.

**Handoff.** The prompt the showrunner renders for a crew member from `.claude/skills/storyline/references/handoff-prompts.md`: objective, the input baton with paths, the output format, tool guidance, boundaries and `max_turns`. The subagent receives only this string, so everything it needs is in it.

**Baton.** The fixed JSON wrapper of every handoff (`storyline/crew/contracts/baton.schema.json`). The **input baton** carries the story key, phase, attempt, tracker rev, objective, input paths with their hashes, constraints (touch set, entitlements, plan tier, LLM choice), budget and the rework package. The **output baton** is the crew member's final message, exactly: verdict, a summary of at most 1,500 characters, files, patches, findings, an agent-specific payload, `needs_human`, the suggested next phase and telemetry. The showrunner never extracts JSON from prose.

**Touch set.** The only paths a phase, a crew member or a script may write ([`lifecycle/touch-sets.yaml`](lifecycle/touch-sets.yaml)). `./scripts/storyline apply` refuses anything outside it; `storyline.yml` repeats the check on the PR diff by branch prefix, because Cursor runs no hooks.

**Patch.** An allow-listed structured edit (a yq path) outside a touch set's file list: the story's manifest entry, its budget lines, its own tracker row. Nothing else in those files may change.

**Model tier.** Never a model id. IDE crew: **strong** (planning, design, security judgement), **standard** (structured writing), **fast** (search, arithmetic, templated output); every agent file says `model: inherit` with its tier in a comment. Tines-side: the tenant's **fast** and **smart** defaults, or a model pinned on the action.

## Design and verification

**Contract.** The one fenced JSON block with the info string `json story-contract` in `design.md`, valid against `templates/story-contract.schema.json`. It is what the builder implements and what G1 checks. Versioned by `contract_version`.

**Definition of Ready.** The prose half of `design.md`: the checklist a person reads at G2, mirroring what G1 checks by script.

**Spike.** A timeboxed experiment in a scratch team that answers a question a VERIFY item leaves open, before the design is final (`templates/spike.md`: questions, a hypothesis to falsify, non-goals, go/no-go).

**Eval case.** An input plus a check on what the story or agent did with it ([`evals/README.md`](evals/README.md)). **Deterministic** cases are graded by code; **model-graded** cases by a rubric with a reference output. A **should-not case** (`should_trigger: false`) checks that the guard holds and nothing acts.

**Capability / regression.** The two suites. Capability: what it should be able to do (new cases start here). Regression: what it must keep doing, at a nearly-100 % bar ([`evals/regression/README.md`](evals/regression/README.md)).

**pass^k.** A model-graded case passes pass^k only when all k trials pass. Required to be 1 where consistency matters. (pass@k, at least one of k, is never a gate.)

**Held-out case.** A case not used to derive a change, used to validate it (P24).

**Rework package.** What the builder receives when verify or a release bounces the story back: the failing gate, the attempt, every finding with its path, rule, severity and `suggested_prompt`, the failing cases and the prior attempts (`templates/rework-package.schema.json`; local, `.storyline/out/<slug>/rework-<n>.json`).

**Verify report.** `verify-report.json`: the deterministic merge of every verify verdict. Any `blocker` or `major` → `changes_requested`.

## State and sync

**Tracker.** `kit/tracker/backlog.yaml` (one row per story) and `milestones.yaml` in git — the system of record — mirrored into the `storyline_backlog` and `storyline_milestones` Record types in Tines, the queryable projection and the inbox for Tines-side decisions.

**rev.** A row's revision number. Only `./scripts/storyline` and `./scripts/kit tracker-fold` change it. **A PR that changes a row sets its `rev` to `main`'s rev + 1** — the scripts compute it from `origin/main`, so several writes on one branch still land as one bump — and `storyline.yml` rejects any other value, so two concurrent branches cannot both land the same bump (the second rebases). A Tines-side write never bumps `rev`.

**`pending_repo_sync`.** A Record flag meaning "a Tines-side change is waiting to reach git". It clears only when git's `rev` rises above the row's `pending_base_rev`, i.e. after a merge that followed the Tines-side write.

**Flow 1 / Flow 2.** Flow 1: repo → Records on every merge to `main` (`tracker-sync.yml` → section B). Flow 2: Records → repo as a PR, never a direct push (`tracker-pull.yml` pulls section E's outbox → `./scripts/kit tracker-fold` → a PR a human merges).

**Outbox.** Section E of `[KIT] 00`: a response-enabled Webhook the repository pulls from, returning the rows with `pending_repo_sync: true`.

**Drift.** A disagreement between the tracker, the evidence and the tenant. `storyline next` reports lifecycle drift; `drift.yml` reports story drift (production vs `main`); the nightly snapshot reports Record and Resource drift. None is fixed silently.

**Events.** `storyline/work/<slug>/events.jsonl`: the typed, append-only log every lifecycle write adds one line to ([`observability/README.md`](observability/README.md)).

**Logbook.** [`logbook.md`](logbook.md): cross-run lessons, provenance-tagged, deduped, within a line budget, and read as untrusted data.

## Words from the scaffold

**Mode 1–4.** The only words for the four MCP surfaces. Mode 1 = Workbench calling MCP tools. Mode 2 = the Tines Stories MCP server at `https://<your-tenant>.tines.com/mcp` (OAuth only) — how every story is built. Mode 3 = the AI Agent action calling tools. Mode 4 = the MCP server action at `https://<your-tenant>.tines.com/mcp/<mcp-path>`.

**Dev team / prod team / ops team.** Builds happen in the dev team. Production is the prod team, which **is** the ops team: the kit story, the ops trio and their Records and Resources live there. Builders hold no Editor or Admin role in it.

**Seed / catalog / reference-only.** A seed is a Library story used as a starting point to read, never shipped as-is; importing it into the Seeds folder is `[BY HAND]`. The catalog (`kit/catalog/library-seeds.yaml`) is the only list of Library ids any agent or Page may cite. A reference-only seed (1324549) is never recommended for shipping.

**`[BY HAND]`.** A step no API and no Mode 2 session can do; a person does it, and the lifecycle lists it rather than pretending.

**VERIFY.** Behaviour the kit assumes but has not confirmed (REPO-DESIGN.md §16, K1–K45; `docs/VERIFY.md`). Never stated as fact.

**SKELETON.** A file that shows the shape of a real export (a `story.json`, a dashboard) before the real one exists. The release check fails while the label remains.

**Community path.** The manual path for Community Edition or a single licensed team (`kit/docs/community-path.md`): no Records, so the tracker lives in git only and every Tines-side gate is recorded with `/storyline-gate`.
