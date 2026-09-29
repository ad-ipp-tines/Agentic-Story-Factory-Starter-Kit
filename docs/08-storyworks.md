# 08 · Tines Storyworks — how the scaffold, the lifecycle and the starter kit fit

_Tines Storyworks Starter Kit · docs v1 (2026-09-27) · Matches `REPO-DESIGN.md` §1, §4–§14 · For decision makers: the people who approve adopting this, fund it, or sign off on its security. Facts come from the Tines platform sweep of 2026-09-25, public MCP research current to 2026-09-17 and `DESIGN.md`; anything else is marked VERIFY and listed in [`VERIFY.md`](VERIFY.md)._

## 1. In one paragraph

The stories-as-code scaffold in this repository already lets a team build Tines Stories from an editor, review them like code and ship them only through Tines change control ([`01-thesis.md`](01-thesis.md)). The **Tines Storyworks** takes that one level up. Every story the team plans becomes a unit of work that moves through one **lifecycle** — intake, discover, design, build, verify, ship, operate, improve — with evidence and a gate at each step. **Narrow crew members** do the work of each phase, **code** decides which one runs next, and **people** hold every gate that changes what exists or what runs. A **starter kit** gets a new tenant there on day 1 from one import and one Page, and a **tracker** keeps the plan visible in git and in Tines. The thesis is the scaffold's own: the value is the system around the prompt. Storyworks makes that system a lifecycle with contracts.

## 2. Three parts, one repository

| Part | Where | What it is | Read |
|---|---|---|---|
| **A. The root** | `/` | The stories-as-code scaffold: conventions, hooks, the build and review skills, export and lint, `ship.yml` into change control, the ops trio that monitors production, rollback | [`../README.md`](../README.md) |
| **B. The Storyline** | `storyline/` | the **Storyline**: a state machine, eight phases with entry and exit criteria, eleven gates, templates, a contract for every design, and the crew members it spins up | [`../storyline/README.md`](../storyline/README.md) |
| **C. The starter kit** | `kit/` + `stories/kit-launch/` | One importable Tines story, `[KIT] 00 · Launch Storyworks`, whose kickoff Page provisions the customer's repository and tenant; the tracker, the dashboard, the model-provider guides and ten starter stories | [`../kit/README.md`](../kit/README.md) |

Storyworks **reuses** the scaffold rather than forking it. The scaffold's builder and reviewer agents are the build and review crew; its workflows are the verify, ship, operate and roll-back machinery; its ops trio is the operate phase's runtime. The lifecycle adds only what was missing: intake, discovery, the design contract, evals written before the build, QA, security and cost review, and a loop that turns production failures into new tests.

## 3. What happens to one idea

```
 an idea ─▶ intake ─G0─▶ discover ─▶ design ─G1 G2─▶ build (G3) ─▶ verify ─G4─▶ ship ─G5─▶ operate ─▶ improve
            brief        reuse         contract +      Mode 2,        independent   change    monitored   retro, new
            drafted      before        evals written   dev team       reviewers,    control   by the      eval cases,
                         building      first                          QA, cost                ops trio    skill changes
```

1. Someone adds a use case — on the kickoff Page, on a Page in Tines, in the App, or with one command. A tool-less agent in Tines drafts an **intake brief**, and the owner decides at **G0** whether it deserves a story at all.
2. A scout checks whether something **already exists** — a verified Story Library seed, a story in the repository, a published story in the dev team — before anything is built.
3. An architect writes a **contract**: the simplest adequate design, and why each simpler one fails; acceptance criteria; credentials and Resources by name; a cost estimate. An eval author turns every criterion into a **test case before the build**. Code checks readiness (**G1**) and a reviewer approves the design by merging it (**G2**).
4. The scaffold's builder builds it in the **dev team** through the Tines Stories MCP server (Mode 2), after a person approves its plan (**G3**).
5. Independent reviewers, a security reviewer, QA against the eval cases and a cost script verify it; a person merges (**G4**).
6. Production is reached only through **change control**: a named person approves in Tines (**G5**).
7. The ops trio watches it; findings trigger a **retro**, which becomes new eval cases and, when a lesson repeats, a change to the skills.

[`09-lifecycle-walkthrough.md`](09-lifecycle-walkthrough.md) follows one story through every step, with the exact commands.

## 4. Who decides what

| Kind | Examples | Why it is safe |
|---|---|---|
| **People** | G0 (build this?), G2 (design approved — a merge), G3 (the build plan), G4 (verified — a merge), G5a (a first ship, a GitHub environment reviewer), G5b (a change request, approved in Tines), G6 (shadow to live), G7 (keep, re-scope or retire), releasing a budget park, every escalation | Every gate that changes what exists or what runs is human. A decision records the decider's **role**, never a name |
| **Code** | Which crew member runs next; G1 readiness; the budget gate; the verify merge rule (any blocker or major finding means rework); the one required CI check | The same answer every time, one PASS/FAIL line per check |
| **Agents** | Drafting briefs, retros and plans; discovery; the design contract; eval cases; the build itself; reviews; QA grading | Their outputs are **proposals** — branches, pull requests, Records rows. Agents never merge, approve a gate or promote |

Authority comes from **versioned files**, never from a chat reply: CODEOWNERS and branch protection in GitHub, `storyline/gates/approvers.yaml` for who may approve each gate's evidence, and the `storyline_approvers` Resource in Tines.

## 5. The agents, and what they may not do

- **In the editor** (Claude Code or Cursor): seven new crew — scout, architect, eval author, security reviewer, QA, eval curator, skill curator — plus the scaffold's reused builder and reviewer, and a showrunner that runs in the main session. Each has one job, an explicit tool list, a turn limit and a closing "never" list. In Claude Code only the builder loads the Tines Stories MCP server; in Cursor only the builder chat of a separate build-only worktree holds it, the other crew run in Claude Code until per-chat scoping is verified (K4), and the hard limit is that builders hold no write role in production.
- **In Tines**: three **tool-less** runtime crew in the kit story (`brief_writer`, `planner`, `retro_writer`) with no credentials, an output schema, a daily cap and a kill switch, plus the scaffold's reused monitoring agents.
- **Everywhere**: crew write nothing directly. Their output is a schema-checked baton that one script (`./scripts/storyline apply`) validates, confines to the paths that phase may touch, writes, and logs.

The lifecycle is **derived from public practice**: published agent-development-lifecycle and agent-engineering guidance from Anthropic, the Claude Code and Claude Agent SDK documentation, IBM, Salesforce Architects, Microsoft Learn, LangChain, Glean, Arthur and OWASP, adapted to the life of one Tines story. It is not an official methodology of Tines or of any of those sources. The principles and their sources are in [`../storyline/PRINCIPLES.md`](../storyline/PRINCIPLES.md).

## 6. What it costs

| Cost | How it is bounded |
|---|---|
| **Building** | Mode 2 runs on the editor's plan; no Tines AI credits are listed for the Tines Stories MCP server (whether its research and listing helpers use credits is VERIFY #11). The exception is verify: QA's model-graded trials run the dev story's AI Agent actions and spend dev-team credits, which the cost estimate counts |
| **Runtime crew** | Tool-less, on the tenant's fast model (pinned on each action), dispatched deterministically on state changes only, under daily run caps, token alerts, budget lines and a kill switch |
| **Your stories' AI** | Every AI Agent action needs a budget line before it ships; estimates come from credits observed in dev; the budget gate warns at 80 % and parks work at 100 % of a ceiling |
| **Model choice** | Tines-provided (credits), your own provider (no Tines credits, your bill; not covered by Tines' credit alerts, so the kit's caps carry the weight), or a local model through a Tunnel (no credits; the cost is the host). [`../kit/docs/llm-provider-matrix.md`](../kit/docs/llm-provider-matrix.md) |
| **Multi-agent** | A full verify fan-out is several fresh contexts per story. The dispatch rules skip reviewers with nothing to judge, and the cost checks are a script, not an agent |
| **Licences** | Business or Enterprise with **two licensed teams** (dev and prod) and Records (Advanced Workflows). Apps (for the App dashboard) and the Tunnel (for a local model) are add-ons. The kit story is one story of roughly 5–8 flows (VERIFY K30) |

## 7. What a security reviewer signs off

The reviewer reads [`../policies/POLICY.md`](../policies/POLICY.md) (the identities table and its rules), then `REPO-DESIGN.md` §13, then [`../storyline/gates/README.md`](../storyline/gates/README.md). The headline controls:

- **No token ever on a Page.** The kickoff Page asks for credential names and rejects token-shaped answers.
- **A short-lived provisioning token.** One fine-grained GitHub token, used on day 1 only, expiring within 7 days and revoked. After day 1 the kit story never writes to GitHub; the repository *pulls* changes from Tines and opens pull requests a person merges.
- **Builders cannot write to production from the editor.** The Tines Stories MCP server acts with the user's own permissions, and builders hold no Editor or Admin role in the prod team. In Claude Code, a hook also refuses every MCP call unless the story is in build on `main` and the caller is the builder (VERIFY K2; until confirmed, it refuses every call).
- **Tool-less runtime agents** with no credentials; their outputs are proposals.
- **One required check** on every pull request, enforcing which paths each phase may change, append-only event logs, and an approving review from the right team for every gate decision.
- **No secrets or personal data in git.** The config commit leaves out the tenant host and every email; approver emails live only in a Tines Resource.
- **Production only through change control**, and a story's first ship only through a GitHub `production` environment reviewer.

## 8. What stays by hand

Some steps have no API and no Mode 2 equivalent, and the kit lists them rather than pretending: configuring the AI provider, token alerts on each AI Agent action, attaching skills, per-team credit allocation, publishing the App and wiring its endpoints, GitHub secrets and branch protection, the Tunnel, rotating Webhook secrets after import, importing Story Library seeds, and switching change control on for a newly shipped story. The setup report carries the list, item by item ([`../kit/ONBOARDING.md`](../kit/ONBOARDING.md)).

## 9. Pros and cons

| Pros | Cons |
|---|---|
| **Storyworks on day 1**: one import and one Page produce a repository, a config, skills, a tracker, Resources, a provider check and a report | **Ceremony**: each story takes a design PR, a build PR and a change request. Lighter tiers soften it; the gates stay |
| **A lifecycle, not only a pipeline**: every story has phases, evidence and gates | **Many VERIFY items at the edges** (Records API request bodies, flow counting, Page behaviour, token scopes): run the first provisioning in a scratch tenant, as a spike |
| **Reuse over duplication**: the scaffold's builder, reviewer, workflows and ops trio do the heavy lifting | **Steps stay by hand** (section 8) |
| **Contracts at every handoff**: schema-checked envelopes and per-phase write limits keep failures local | **Two-way sync is eventually consistent**: a decision made in Tines is provisional until its tracker PR merges |
| **Evals first**, and production failures become new tests | **Cursor enforces later**: it runs no hooks, so enforcement is in the scripts and CI |
| **Cost is designed in**: an off-meter build loop, tool-less runtime agents, estimates from observed credits | **Multi-agent runs cost tokens**, and small local models are weak at tool use |
| **Least privilege end to end**, and **both editors work** | **Plan limits**: Community Edition and one-team tenants get a manual path; self-hosted gets no Tunnel |
| **Resumable**: git is the truth, so a fresh session rebuilds state from the tracker and the event log | **The lifecycle needs maintenance**, and the kit story is itself large and can fail (the ops trio monitors it) |

The full lists are `REPO-DESIGN.md` §14.

## 10. What this does not claim

- It is not product documentation; Tines' own documentation is the source for product behaviour.
- It does not claim that anything marked VERIFY works. Storyworks' own items are K1–K45 in [`VERIFY.md`](VERIFY.md).
- It does not replace Tines change control.
- It never auto-applies what an agent proposes.

## 11. Adopting it

| When | Milestone | Done when (in short) |
|---|---|---|
| Day 1 | Storyworks is provisioned and safe to build in | The setup report is ok or explained; access, branch protection and environments are set; the provisioning token is revoked; story #1 has passed G0 and discovery |
| Week 1 | The first stories are live and the tracker round trip works | Story #1, the ops router and the ops sweep are live; a decision made in Tines reached git by a merged PR |
| Week 4 | The lifecycle runs end to end, including improve | Three stories live, including one AI agent story with every guard; the first retro closed and an eval case graduated; one skill change shipped; credits reviewed |

The runbook is [`../kit/ONBOARDING.md`](../kit/ONBOARDING.md); the plans the kit supports are in [`../kit/README.md`](../kit/README.md).

## Verify in your tenant before presenting

Nothing marked VERIFY is a headline claim. Before this page is shown to anyone, confirm at least: **K2** (a hook can tell which subagent is calling — until then no build can start), **K8** (import keeps Page identifiers and Webhook secrets — the template is not published until it does), **K30** (how the kit story's flows are counted), the plan conflicts **K7**, **K19**, **K20** and **K28**, and scaffold items **#1**, **#2** and **#11**. The ledger is [`VERIFY.md`](VERIFY.md).
