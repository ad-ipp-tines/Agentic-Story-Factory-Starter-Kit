# Study guide 00 · The visual tour

_Eleven diagrams, one idea each, in the order a new builder meets them. Every diagram links to the file that is the source of truth; where a diagram and its source disagree, the source wins and this page is the bug. The lifecycle's full state machine is [`storyline/lifecycle/state-machine.md`](../../storyline/lifecycle/state-machine.md)._

Time: 30 minutes. Audience: anyone new to the repository — builders, approvers, security reviewers, and the AI agents that will enhance it.

---

## 1. The repository in one picture

Three parts. The root is the stories-as-code layer. `storyline/` is the Storyline: how a story moves. `kit/` is what a new customer imports on day one.

```mermaid
flowchart TB
    subgraph ROOT["Repository root: stories and skills as code"]
        direction LR
        A1["AGENTS.md + CLAUDE.md<br/>conventions every session loads"]
        A2[".claude/ + .cursor/<br/>editor skills, agents, hooks, rules"]
        A3["stories/<br/>one folder per story: export + meta + tests"]
        A4["tines-skills/<br/>Agent Skills pushed to the tenant"]
        A5["policies/<br/>the contract: budgets, never-touch, lint rules"]
        A6["scripts/ + .github/workflows/<br/>one API dispatcher, CI gates, ship, drift, rollback"]
    end
    subgraph STORYLINE["storyline/: the Storyline (how a story moves)"]
        direction LR
        B1["lifecycle/<br/>state machine, dispatch rules, touch sets"]
        B2["phases/ + gates/<br/>entry and exit criteria, who decides"]
        B3["crew/<br/>the crew, contracts, runtime prompts"]
        B4["templates/ + evals/ + examples/"]
    end
    subgraph KIT["kit/: the starter kit"]
        direction LR
        C1["stories/kit-launch/<br/>[KIT] 00 · Launch Storyworks"]
        C2["tracker/<br/>backlog + milestones, the truth"]
        C3["records/ + resources/<br/>what the kit creates in Tines"]
        C4["dashboard/<br/>App or Page + Tines Dashboard"]
    end
    ROOT --- STORYLINE --- KIT
```

**Read next:** the root [`README.md`](../../README.md), [`storyline/README.md`](../../storyline/README.md), [`kit/README.md`](../../kit/README.md).

---

## 2. The four modes

Model Context Protocol (MCP) appears in Tines Stories in four places. This repository only ever calls them modes. It authors in Mode 2, runs its monitor in Mode 3, and exposes its ops lookups in Mode 4.

```mermaid
flowchart LR
    subgraph CLIENT["Tines is the MCP client"]
        M1["Mode 1<br/>Workbench + MCP tools<br/>a person chats in Tines"]
        M3["Mode 3<br/>AI Agent action + MCP tools<br/>a story runs"]
    end
    subgraph SERVER["Tines is the MCP server"]
        M2["Mode 2<br/>the Tines Stories MCP server /mcp<br/>your editor authors stories"]
        M4["Mode 4<br/>the MCP server action /mcp/path<br/>your stories become tools"]
    end
    ED["Cursor · Claude Code"] -->|"OAuth only"| M2
    EXT["Claude · Cursor · other clients"] -->|"team-scoped key"| M4
    M1 -->|"calls"| RS["remote MCP servers"]
    M3 -->|"calls"| RS
```

**In this repository:** Mode 2 is every build ([`AGENTS.md`](../../AGENTS.md) §2). Mode 3 is the ops monitor ([`stories/ops-story-health-monitor/`](../../stories/ops-story-health-monitor/README.md)). Mode 4 is the ops tools server ([`stories/ops-tools-server/`](../../stories/ops-tools-server/README.md)). Mode 1 is optional.

---

## 3. The build loop: one story, from an editor

A person asks; the builder subagent, the only context that holds the Tines Stories MCP server, plans, builds in the dev team, validates, tests and exports. Hooks run whether or not the model agrees.

```mermaid
sequenceDiagram
    autonumber
    actor P as Builder (a person)
    participant CC as Claude Code main session
    participant TB as tines-builder subagent
    participant H as Hooks
    participant T as Tines dev team via /mcp
    participant R as Repository
    P->>CC: /storyline slug run
    CC->>TB: handoff: build this one story
    TB->>P: numbered plan (action type, name, fields)
    P->>TB: approve plan (G3)
    TB->>H: every MCP call passes guard-mcp.sh and phase-gate.sh
    H-->>TB: allowed (dev team, not never-touch, phase is build)
    TB->>T: read, create, update, validate
    TB->>T: run the test event
    TB->>R: ./scripts/tines export, then lint-story.sh and diff-story.sh
    H-->>TB: stop-gate.sh refuses to end on a stale export or failing lint
    TB-->>CC: report + export
    CC->>R: branch story/slug, commit, open PR
```

**Read next:** [`.claude/skills/tines-build-story/SKILL.md`](../../.claude/skills/tines-build-story/SKILL.md), [`.claude/agents/tines-builder.md`](../../.claude/agents/tines-builder.md), [`CLAUDE.md`](../../CLAUDE.md) §c for the hooks.

---

## 4. The ship path: from pull request to production

Nothing reaches production except through a merged pull request, a draft, a change request and a named person approving in Tines. CI can open a change request; it cannot approve one.

```mermaid
flowchart LR
    PR["Pull request<br/>one story"] --> CHK["storyline.yml<br/>calls lint.yml + review.yml"]
    CHK --> QA["QA verification line<br/>+ CODEOWNER review"]
    QA -->|"G4: a person merges"| MAIN["main"]
    MAIN --> SHIP["ship.yml<br/>version → import as draft<br/>→ recipients + monitoring<br/>→ change request"]
    SHIP -->|"first ship only"| G5A["G5a<br/>production environment reviewer"]
    SHIP --> CR["Change request in Tines"]
    CR -->|"G5b: named approver"| LIVE["Live story"]
    CR -.->|"optional: promote.yml<br/>only if status is APPROVED"| LIVE
    LIVE --> DRIFT["drift.yml nightly<br/>export prod, diff vs main"]
    DRIFT -.->|"difference"| DPR["drift PR"]
```

**Read next:** [`docs/02-workflows.md`](../02-workflows.md) §2, [`policies/POLICY.md`](../../policies/POLICY.md), [`.github/workflows/ship.yml`](../../.github/workflows/ship.yml).

---

## 5. The lifecycle at a glance

Eight phases, eleven gates. Human gates are the ones that change what exists or what runs. The full state machine, with every transition, is [`storyline/lifecycle/state-machine.md`](../../storyline/lifecycle/state-machine.md).

```mermaid
flowchart LR
    I["intake"] -->|"G0 human"| D["discover"]
    D -->|"check"| DE["design"]
    DE -->|"G1 script<br/>G2 human merge"| B["build<br/>G3 plan, human"]
    B -->|"check"| V["verify"]
    V -->|"G4 checks + human merge"| S["ship"]
    V -.->|"changes requested<br/>attempt below 3"| B
    S -->|"G5a or G5b human"| O["operate<br/>G6 shadow to live"]
    O -->|"trigger"| IM["improve"]
    IM -->|"change needed"| DE
    O -->|"G7 human"| RT["retired"]
    I -->|"G0 reject"| RJ["rejected"]
    X["any phase"] -.->|"GB budget"| PK["parked"]
    X -.->|"GX escalation"| BL["blocked, owner decides"]
```

**Read next:** [`storyline/gates/README.md`](../../storyline/gates/README.md), then one phase file, for example [`storyline/phases/02-design.md`](../../storyline/phases/02-design.md).

---

## 6. The crew, and where each one runs

Narrow agents, one job each. Code decides who runs next, never a model. Only `tines-builder` holds the Tines Stories MCP server. The Tines-side agents hold no tools and no credentials.

```mermaid
flowchart TB
    ORC["showrunner<br/>main session · ./scripts/storyline next decides"]
    subgraph IDE["In the editor: Claude Code subagents"]
        SC["story-scout<br/>discover"]
        AR["story-architect<br/>design"]
        EA["eval-author<br/>design"]
        TB["tines-builder<br/>build · holds /mcp"]
        TR["tines-reviewer<br/>verify"]
        SR["security-reviewer<br/>verify"]
        QA["story-qa<br/>verify"]
        EC["eval-curator<br/>improve"]
        SK["skill-curator<br/>improve"]
    end
    subgraph TINES["In Tines: AI Agent actions, no tools"]
        PL["planner<br/>backlog"]
        BW["brief_writer<br/>intake"]
        RW["retro_writer<br/>improve"]
        OT["triage + critic<br/>operate, read-only tools"]
    end
    subgraph CODE["Scripts, not models"]
        CE["cost checks<br/>storyline estimate"]
        G1["readiness<br/>storyline ready"]
    end
    ORC --> SC --> AR --> EA
    EA --> TB --> TR & SR & QA
    ORC --> EC --> SK
    PL & BW & RW -.->|"proposals, a person accepts"| ORC
```

**Read next:** [`storyline/crew/README.md`](../../storyline/crew/README.md) (the roster and the spin-up matrix), one role card such as [`storyline/crew/story-architect.md`](../../storyline/crew/story-architect.md).

---

## 7. How a crew member hands off

Crew never write files directly. They return one JSON baton; `./scripts/storyline apply` validates it, checks the touch set, writes, appends an event and updates the tracker, and asks a person first.

```mermaid
sequenceDiagram
    autonumber
    participant ORC as showrunner
    participant S as ./scripts/storyline
    participant SP as crew member subagent
    participant FS as storyline/work/slug + tracker
    ORC->>S: next slug
    S-->>ORC: agent name + rendered handoff prompt
    ORC->>SP: spawn with the handoff (own context window)
    SP-->>ORC: output baton, one fenced JSON block
    ORC->>S: apply slug agent (asks a person)
    S->>S: validate baton + payload schema
    S->>S: check every path against the touch set
    S->>FS: write artifacts, append event, update tracker row
    Note over S,FS: invalid output is asked for once more,<br/>a second invalid one opens GX
```

**Read next:** [`storyline/crew/contracts/baton.schema.json`](../../storyline/crew/contracts/baton.schema.json), [`storyline/lifecycle/touch-sets.yaml`](../../storyline/lifecycle/touch-sets.yaml).

---

## 8. The monitoring loop: agentic, but a person decides

Every production story reports to the ops router. The health sweep's agent reads evidence through read-only tools and proposes; a critic checks it; a person approves; a fix arrives as a pull request.

```mermaid
flowchart LR
    PS["Production stories<br/>monitoring on"] -->|"failure or silence"| ER["[OPS] ops-error-router<br/>dedupe, route"]
    ER --> AL[("ops_alerts")]
    SW["[OPS] ops-story-health-monitor<br/>scheduled sweep"] --> TR["triage agent<br/>five read-only tools"]
    TR --> CR["critic agent<br/>no tools"]
    CR --> FD[("ops_findings<br/>ops_alert_proposals")]
    FD --> HU{"a person<br/>approves?"}
    HU -->|"alert change"| APPLY["applied by a person"]
    HU -->|"fix"| PF["propose-fix.yml<br/>headless, no MCP"]
    PF --> FPR["pull request<br/>label ops-proposal"]
    OTS["[OPS] ops-tools-server<br/>Mode 4"] -.->|"same lookups as tools"| ED["editors and Claude clients"]
```

**Read next:** [`stories/ops-story-health-monitor/README.md`](../../stories/ops-story-health-monitor/README.md), [`docs/03-monitoring-story.md`](../03-monitoring-story.md), [`.github/workflows/propose-fix.yml`](../../.github/workflows/propose-fix.yml).

---

## 9. Day one: what the starter kit does

Import one story, answer one Page. The story branches on what the tenant bought, provisions deterministically, checks the model provider, and writes a setup report. No kit AI Agent action runs until a person switches the guards on.

```mermaid
flowchart TB
    IMP["Import [KIT] 00 into the ops team<br/>(the maintainer release, never the SKELETON)"] --> PG["kickoff Page<br/>teams, entitlements, plan, model choice,<br/>GitHub org, use cases, chat surface"]
    PG --> RT{"entitlement router"}
    RT --> GH["GitHub: private repository from this template<br/>fallback: Contents API"]
    GH --> CFG["commit kit/tenant/config.yaml"]
    RT --> SKL["push seven Agent Skills"]
    RT -->|"Records entitled"| REC["create storyline_backlog, storyline_events,<br/>storyline_milestones Record types"]
    RT --> RES["create kit Resources<br/>storyline_limits starts disabled"]
    REC --> SEED["seed tracker + milestones"]
    RT -->|"Apps entitled"| APP["App: create + push files"]
    RT -->|"otherwise"| DSH["Page + Tines Dashboard"]
    RT -->|"AI Agent entitled"| PRB["provider probe<br/>one call, one tool call"]
    CFG & SKL & SEED & APP & DSH & PRB --> REP["setup report<br/>ok · partial · failed, with the BY HAND list"]
    REP --> KPR["kit.yml opens the setup-report PR"]
```

**Read next:** [`kit/README.md`](../../kit/README.md), [`kit/ONBOARDING.md`](../../kit/ONBOARDING.md), [`stories/kit-launch/README.md`](../../stories/kit-launch/README.md).

---

## 10. The tracker: git is the truth, Records is the view

Two flows, and they never write the same fields. Decisions made in Tines reach git only when a person merges.

```mermaid
flowchart LR
    subgraph GIT["Git: the system of record"]
        BY["kit/tracker/backlog.yaml<br/>milestones.yaml<br/>storyline/work/slug/events.jsonl"]
    end
    subgraph TN["Tines: the projection and the inbox"]
        RC[("storyline_backlog<br/>storyline_milestones<br/>storyline_events")]
        UI["Pages · App · runtime crew"]
        OB["tracker_outbox webhook"]
    end
    BY -->|"Flow 1: on merge<br/>tracker-sync.yml"| RC
    UI -->|"writes, marked pending_repo_sync"| RC
    RC --> OB
    OB -->|"Flow 2: every 30 min<br/>tracker-pull.yml"| TPR["tracker PR"]
    TPR -->|"a person merges"| BY
    RC --> DB["dashboard"]
```

**Read next:** [`kit/tracker/README.md`](../../kit/tracker/README.md), [`REPO-DESIGN.md`](../../REPO-DESIGN.md) §6.5.

---

## 11. Trust boundaries: who holds what

No secret lives in the repository, the prompt or the model's context. Each identity can do one job.

```mermaid
flowchart TB
    subgraph ED["Editor"]
        E1["Tines Stories MCP server<br/>OAuth, the person's own permissions<br/>dev team only, builder subagent only"]
    end
    subgraph CI["GitHub Actions"]
        C1["team-scoped Tines keys<br/>in GitHub environments"]
        C2["can import and open change requests<br/>cannot approve"]
        C3["break-glass: separate environment,<br/>a second reviewer, logged"]
    end
    subgraph TNS["Tines"]
        T1["credentials by name<br/>never exported, never sent to a client"]
        T2["runtime agents: no tools, no credentials"]
        T3["change control: a named approver"]
    end
    subgraph REPO["Repository"]
        R1[".env.example: names only<br/>block-secrets.sh + gitleaks"]
    end
    E1 -.->|"no production writes"| T3
    C2 -.->|"opens"| T3
```

**Read next:** [`docs/04-security-model.md`](../04-security-model.md), [`policies/POLICY.md`](../../policies/POLICY.md) §1.

---

## Check yourself

1. Which mode does a build use, and why does only one subagent hold it?
2. Name the three human gates between a design and a live story.
3. What stops CI from promoting a change request nobody approved?
4. Where is a story's phase stored, and which side wins when git and Records disagree?
5. What does the monitoring agent do when it finds a failing story, and what does it never do?
6. Which kit steps can no API perform, and where is that list?

Answers: [`AGENTS.md`](../../AGENTS.md) §2 and §3 · [`storyline/gates/README.md`](../../storyline/gates/README.md) · [`.github/workflows/promote.yml`](../../.github/workflows/promote.yml) · [`kit/tracker/README.md`](../../kit/tracker/README.md) · [`stories/ops-story-health-monitor/README.md`](../../stories/ops-story-health-monitor/README.md) · [`kit/README.md`](../../kit/README.md) "The [BY HAND] list".
