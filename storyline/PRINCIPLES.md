# Principles of the Storyline

> **This lifecycle is derived from public practice.** It adapts the published agent development lifecycle and agent-engineering guidance listed at the end of this page to the life of one Tines story. It is **not** an official methodology of Tines or of any source named here. The sources are paraphrased, not quoted. The Salesforce page was read in a browser and not byte-checked.

_Spec: REPO-DESIGN.md §4.1. Each principle below says what it means, how this lifecycle applies it, where that lives in the repository, and which public sources it comes from._

---

### P1 · Decide whether to build at all, then build the simplest thing that works

Most wasted automation is automation that should not exist, or that climbed to an agent when a request and a transform would have done. So the first decision is whether to build, and the second is the lowest rung of capability that does the job. **Applied:** G0 intake triage decides build, reject or park before any design. The design must name the lowest rung of `docs/01-decision-rules.md` that works and say why each lower rung fails; the contract schema refuses a rung above 1 with no reason. Runtime crew start tool-less. **Where:** [`gates/G0-intake-triage.md`](gates/G0-intake-triage.md), [`phases/02-design.md`](phases/02-design.md), [`templates/story-contract.schema.json`](templates/story-contract.schema.json) (`mode.why_not_lower`). **Sources:** IBM Think, *What is the Agent Development Lifecycle*; Anthropic, *Building effective agents*; Microsoft Learn, *Agent development lifecycle*.

### P2 · Define quality before building (evals first)

If the test is written after the build, the build defines the test. Writing the cases from the acceptance criteria first makes "done" something a script can check, and it forces the design to be concrete enough to test. **Applied:** `eval-author` writes the cases during design; G1 fails without them. Cases cover both what should happen and what should not. Each is a case two experts would grade the same way, with a reference output where a model grades it. **Where:** [`evals/README.md`](evals/README.md), [`templates/eval-cases.yaml`](templates/eval-cases.yaml), [`gates/G1-readiness.md`](gates/G1-readiness.md). **Sources:** Anthropic, *Demystifying evals for AI agents*; Glean, *Agent development lifecycle*; Arthur, *The Agent Development Lifecycle*.

### P3 · Phases with entry and exit criteria, joined by gates

A lifecycle is useful only if everyone can tell which stage a piece of work is in and what it takes to leave. Explicit entry and exit criteria, with a gate between stages, turn that into something a machine and a person can both read. **Applied:** eight phases, each with entry criteria, exit criteria, artifacts and a gate; one state machine is the single source of names. **Where:** [`lifecycle/state-machine.yaml`](lifecycle/state-machine.yaml), [`phases/`](phases/00-intake.md), [`gates/`](gates/README.md). **Sources:** IBM; Salesforce Architects, *The Agent Development Lifecycle*; Microsoft Learn; LangChain, *The Agent Development Lifecycle*; Glean.

### P4 · Explore, plan, then implement against a self-contained spec, in a fresh context

Coding agents do better when they read before they write, agree a plan before they change anything, and work from a spec that says what to touch, what not to touch and how to check the result. A builder in a fresh context sees only that spec, so the spec has to be complete. **Applied:** discover → the design contract (files and interfaces, out of scope, the end-to-end check) → G3 plan approval → the builder implements in its own context. **Where:** [`phases/01-discover.md`](phases/01-discover.md), [`phases/02-design.md`](phases/02-design.md), [`gates/G3-plan-approval.md`](gates/G3-plan-approval.md). **Sources:** Claude Code docs, *Best practices*.

### P5 · Narrow crew, each with an objective, an output format, tool guidance and boundaries

A single agent asked to do everything does each part worse and is hard to evaluate. Crew with one job each can be given exactly the tools and context that job needs, and can be evaluated on it. The handoff to each one must state its objective, the format to return, which tools to use and where its job ends. **Applied:** the roster of crew, one job per agent; a handoff template per crew member. **Where:** `storyline/crew/README.md`, `.claude/skills/storyline/references/handoff-prompts.md`, [`lifecycle/dispatch-rules.yaml`](lifecycle/dispatch-rules.yaml). **Sources:** Claude Code docs, *Create custom subagents*; Anthropic, *How we built our multi-agent research system*.

### P6 · Hand off through persisted artifacts, not by relaying text

When one agent's output is pasted into another's prompt, information is lost, costs multiply and nothing is left to audit. Writing each output to a file and passing the path keeps the chain inspectable and resumable. **Applied:** every crew member output lands under `storyline/work/<slug>/` through `./scripts/storyline apply`; crew receive paths, not pasted content. **Where:** [`work/README.md`](work/README.md), [`lifecycle/dispatch-rules.yaml`](lifecycle/dispatch-rules.yaml) (`inputs`). **Sources:** Anthropic, *How we built our multi-agent research system*.

### P7 · Treat context as a finite budget and isolate it

Every token of tool description, history and pasted text competes for the model's attention. Keeping always-loaded instructions short, loading procedures on demand and giving each crew member its own context window keeps each job's context relevant. **Applied:** subagents return a summary of at most 1,500 characters plus files. In Claude Code only `tines-builder` loads the Tines Stories MCP server (an inline definition); in Cursor only the builder chat of a separate build-only worktree holds it. `AGENTS.md` stays short, and skills load on demand. **Where:** [`phases/03-build.md`](phases/03-build.md), [`lifecycle/state-machine.yaml`](lifecycle/state-machine.yaml) (`thresholds.summary_max_chars`). **Sources:** Anthropic, *Effective context engineering for AI agents*; Claude Agent SDK docs, *Subagents*; Claude Code docs, *Skills*.

### P8 · Structured, schema-validated outputs; branch on fields, never on prose

Prose is for people. When code has to act on what a model said, it should read a field validated against a schema, not interpret wording or a confidence phrase. **Applied:** every crew member returns a baton validated against `storyline/crew/contracts/*.schema.json` by `apply`; Tines-side agents have Output schemas, and the Triggers after them read explicit fields. **Where:** [`templates/`](templates/story-contract.schema.json), [`observability/event.schema.json`](observability/event.schema.json), `storyline/crew/contracts/`. **Sources:** OWASP, *AI Agent Security Cheat Sheet*; Anthropic, *How we built our multi-agent research system*.

### P9 · Least privilege and least agency

An agent should hold only the tools and permissions its job needs, and should be able to cause only the effects its job requires. Actions that change other systems should be requests a person approves, not direct calls. **Applied:** per-agent tool lists; runtime crew hold no tools and no credentials; tools that act on systems are `request_` tools; the provisioning token is short-lived. **Where:** `.claude/agents/*.md`, [`templates/story-contract.schema.json`](templates/story-contract.schema.json) (`tools_design`), [`lifecycle/touch-sets.yaml`](lifecycle/touch-sets.yaml). **Sources:** Claude Code docs, *Create custom subagents*; OWASP; IBM.

### P10 · Humans at gates for high-impact or irreversible steps, with a preview

Where a mistake is expensive or cannot be undone, a person decides, and decides after seeing what will change. **Applied:** G0, G2, G3, G4 (the merge), G5a (the first-ship reviewer) and G5b (the change request with the live-vs-draft diff), G6, G7 and GX are human. Agents never merge, promote or decide a gate. **Where:** [`gates/README.md`](gates/README.md). **Sources:** OWASP; LangChain; Anthropic, *Building effective agents*.

### P11 · The doer is never the grader

An agent reviewing its own work shares its own blind spots. Review belongs to a different context, and ideally a different process. **Applied:** the builder never reviews; `tines-reviewer`, `security-reviewer` and `story-qa` run in fresh contexts; `review.yml` is an independent instance; a person who is not the author merges. **Where:** [`phases/04-verify.md`](phases/04-verify.md). **Sources:** Claude Code docs, *Best practices*.

### P12 · Layered verification

No single check catches everything. Several cheap, different checks in sequence catch what each other miss. **Applied:** `lint.yml` → `storyline.yml` → the reviewers → the QA evals → a CODEOWNER → a human merge → the change request. **Where:** [`gates/G4-verify-and-merge.md`](gates/G4-verify-and-merge.md). **Sources:** Anthropic, *Demystifying evals for AI agents*.

### P13 · Enforce must-happen rules deterministically

A rule written in a prompt is a request; a rule enforced by a hook, a script or a Trigger is a rule. Anything that must always happen belongs in code. **Applied:** `phase-gate.sh`, the scaffold's four hooks, touch sets in `apply`, `storyline.yml`, Tines Triggers and Resources. **Where:** [`lifecycle/touch-sets.yaml`](lifecycle/touch-sets.yaml), [`phases/03-build.md`](phases/03-build.md). **Sources:** Claude Code docs, *Automate actions with hooks*.

### P14 · Observe decisions, tool calls, outcomes and cost

Agent systems fail in ways that are only visible in their traces: which decision was made, which tool was called, what it cost. Logging those as typed events makes failures diagnosable and cost attributable. **Applied:** `events.jsonl` and the `storyline_events` Record type; `.tines/mcp-activity.jsonl`; the AI Agent event metadata (tokens, credits, model) copied into `storyline_events`; `GET /api/v1/ai_usage`. **Where:** [`observability/README.md`](observability/README.md). **Sources:** Anthropic, *How we built our multi-agent research system*; OWASP; Arthur; LangChain.

### P15 · Production failures become eval cases

The most valuable test cases are the ones production already found. Turning each failure into a case means the same failure cannot ship twice unnoticed. **Applied:** the improve phase: `retro_writer` → the human → `eval-curator` → capability cases graduate to regression. **Where:** [`phases/07-improve.md`](phases/07-improve.md), [`evals/regression/README.md`](evals/regression/README.md). **Sources:** LangChain; Arthur; Anthropic, *Demystifying evals for AI agents*.

### P16 · External content is data, not instructions

Anything an agent reads that someone else wrote can contain text aimed at the agent. Treating all of it as data, and treating an embedded instruction as a finding, closes the most common injection path. **Applied:** Page inputs, use-case text, error logs, webhook payloads and fetched Library pages are untrusted; an embedded instruction is itself a finding (`sec.9`); `logbook.md` is read as data. **Where:** [`logbook.md`](logbook.md), [`templates/intake-brief.md`](templates/intake-brief.md). **Sources:** OWASP.

### P17 · Bound autonomy with stop conditions and budgets

Agents that loop without limits burn money and compound mistakes. Every autonomous step needs a turn limit, a retry limit and a budget, and a defined place to stop and ask. **Applied:** `maxTurns` per agent; a rework cap of 3; stop after two failed corrections; the GB budget gate; the `storyline_limits` caps and kill switch. **Where:** [`lifecycle/state-machine.yaml`](lifecycle/state-machine.yaml) (`caps`), [`gates/GB-budget.md`](gates/GB-budget.md), [`gates/GX-escalation.md`](gates/GX-escalation.md). **Sources:** Anthropic, *Building effective agents*; Claude Agent SDK docs, *Subagents*; OWASP.

### P18 · Scale the number of agents to the task

Multi-agent runs use many times the tokens of a single chat. They are worth it for broad, parallel work and wasteful for simple, sequential work. **Applied:** `dispatch-rules.yaml` skips the security reviewer when it has nothing to judge, and the cost checks are a script (`./scripts/storyline estimate --check`), not an agent. **Where:** [`lifecycle/dispatch-rules.yaml`](lifecycle/dispatch-rules.yaml) (`conditional`). **Sources:** Anthropic, *How we built our multi-agent research system*.

### P19 · Work incrementally and leave a clean, resumable state

Long-running agent work survives interruptions only if each step ends in a state the next session can pick up from without guessing. **Applied:** one story per branch and PR; WIP 1 per owner; `events.jsonl` plus the tracker let a fresh session resume; `storyline next` is resume-aware. **Where:** [`work/README.md`](work/README.md), [`lifecycle/state-machine.md`](lifecycle/state-machine.md). **Sources:** Anthropic, *Effective harnesses for long-running agents*.

### P20 · Progressive disclosure

Load the short, always-true rules every time; load procedures and details only when they are needed. **Applied:** short always-loaded rules, procedures in skills; Tines Agent Skills show only their name and description until matched. **Where:** `AGENTS.md`, `.claude/skills/`, `tines-skills/`. **Sources:** Claude Code docs, *Skills*; Tines Skills API docs.

### P21 · Side-effecting workflows are human-triggered

A workflow that changes something outside the conversation should start only when a person asks for it, never because a model decided to. **Applied:** `/storyline-gate` — like the scaffold's `/tines-ship`, `/tines-rollback` and `/tines-export` — carries `disable-model-invocation: true`, and `./scripts/storyline gate` asks for a confirmation on `/dev/tty`. **Where:** [`gates/README.md`](gates/README.md) rule 3. **Sources:** Claude Code docs, *Skills*.

### P22 · Safety by design: staged rollout and rollback from the start

Plan for the change to be wrong: release it in a mode where it cannot do harm, watch it, then widen it — and keep a way back. **Applied:** shadow mode and G6; change-control drafts; `rollback.yml`; the revert PR on a G5 rejection. **Where:** [`phases/06-operate.md`](phases/06-operate.md), [`phases/05-ship.md`](phases/05-ship.md). **Sources:** Glean; IBM; Salesforce Architects; Anthropic, *How we built our multi-agent research system* (gradual deployment).

### P23 · Experiment on real data

Synthetic inputs flatter a design. Cases built from real (sanitised) payloads, and experiments run where real conditions hold, show what production will do. **Applied:** eval cases are built from captured and sanitised dev payloads; spikes run in a scratch team. **Where:** [`evals/README.md`](evals/README.md) rule 5, [`templates/spike.md`](templates/spike.md). **Sources:** Microsoft Learn.

### P24 · Let agents improve prompts and tools, checked on held-out cases

Agents are good at proposing improvements to their own prompts and tools, and just as good at overfitting to the examples they learned from. Every proposed change is judged on cases that were not used to derive it. **Applied:** `skill-curator` proposes; the change must pass agent eval cases that were not used to derive it (`storyline-evals.yml`), and `storyline.yml` fails a skill PR without a held-out cases file. **Where:** [`phases/07-improve.md`](phases/07-improve.md), [`evals/README.md`](evals/README.md). **Sources:** Anthropic, *How we built our multi-agent research system*; Anthropic, *Writing effective tools for agents*.

### P25 · Govern: ownership, a catalog, retirement

Automations outlive their authors. Each needs an owner who answers for it, a catalog where it can be found, and a normal way to end. **Applied:** the tracker is the catalog; owners are roles; G7 runs quarterly; `retired` is a lifecycle state. **Where:** [`gates/G7-ownership-review.md`](gates/G7-ownership-review.md), `kit/tracker/backlog.yaml`. **Sources:** Glean; IBM; Arthur.

---

## Sources (all public)

- **Anthropic Engineering** — *Building effective agents* (anthropic.com/engineering/building-effective-agents) · *How we built our multi-agent research system* (anthropic.com/engineering/multi-agent-research-system) · *Demystifying evals for AI agents* (anthropic.com/engineering/demystifying-evals-for-ai-agents) · *Effective context engineering for AI agents* (anthropic.com/engineering/effective-context-engineering-for-ai-agents) · *Effective harnesses for long-running agents* (anthropic.com/engineering/effective-harnesses-for-long-running-agents) · *Writing effective tools for agents* (anthropic.com/engineering/writing-tools-for-agents)
- **Claude blog** — *Building agents with the Claude Agent SDK*
- **Claude Code docs** (code.claude.com/docs/en/) — *Create custom subagents* · *Best practices* · *Skills* · *Automate actions with hooks* · *Orchestrate subagents at scale with dynamic workflows*
- **Claude Agent SDK docs** — *Subagents in the SDK*
- **IBM Think** — *What is the Agent Development Lifecycle?*
- **Salesforce Architects** — *The Agent Development Lifecycle: From Conception to Production* (read in a browser; not byte-checked)
- **Microsoft Learn** — *Agent development lifecycle*
- **LangChain** — *The Agent Development Lifecycle*
- **Glean docs** — *Agent development lifecycle*
- **Arthur** — *The Agent Development Lifecycle*
- **OWASP Cheat Sheet Series** — *AI Agent Security Cheat Sheet*
- **Tines** — the Skills API documentation (P20)
