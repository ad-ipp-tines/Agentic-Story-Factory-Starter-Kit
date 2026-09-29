# Study guides

_The learning path for the Tines Storyworks. Guide 00 is written. Guides 01–06 are specified below so an AI contributor can write them as pull requests against the same rules as everything else in this repository (see [`HANDOFF.md`](../../HANDOFF.md))._

## The path

| # | Guide | For | Time | Status |
|---|---|---|---|---|
| 00 | [The visual tour](00-visual-tour.md) — eleven diagrams, one idea each | everyone | 30 min | written |
| 01 | Your first story, end to end | builders | 90 min, hands on | to write |
| 02 | Approving gates | approvers, CODEOWNERS | 30 min | to write |
| 03 | The crew and how they hand off | builders, platform owners | 45 min | to write |
| 04 | Day one with the starter kit | onboarding engineers, tenant owners | 60 min, hands on | to write |
| 05 | Running it: monitoring, drift, rollback, break-glass | ops, security | 45 min | to write |
| 06 | Cost and security for decision makers | managers, security reviewers | 20 min | to write |

Until 01–06 exist, these existing pages carry the same material in reference form:

| Guide | Read today |
|---|---|
| 01 | [`docs/09-lifecycle-walkthrough.md`](../09-lifecycle-walkthrough.md), [`storyline/examples/example-enrich-ip/`](../../storyline/examples/example-enrich-ip/), [`.claude/skills/tines-build-story/SKILL.md`](../../.claude/skills/tines-build-story/SKILL.md) |
| 02 | [`storyline/gates/README.md`](../../storyline/gates/README.md) and one file per gate |
| 03 | [`storyline/crew/README.md`](../../storyline/crew/README.md), [`storyline/crew/contracts/`](../../storyline/crew/contracts/) |
| 04 | [`kit/README.md`](../../kit/README.md), [`kit/ONBOARDING.md`](../../kit/ONBOARDING.md), [`kit/docs/`](../../kit/docs/) |
| 05 | [`docs/02-workflows.md`](../02-workflows.md) §4, [`docs/06-rollback-and-recovery.md`](../06-rollback-and-recovery.md) |
| 06 | [`docs/03-cost-controls.md`](../03-cost-controls.md), [`docs/04-security-model.md`](../04-security-model.md), [`docs/05-pros-and-cons.md`](../05-pros-and-cons.md) |

## What every guide must have

A guide is accepted when it:

1. **Teaches one job.** The title says who it is for and what they can do after reading it.
2. **Opens with a diagram** (Mermaid, rendered by GitHub) and adds one per major step. Reuse the diagrams in 00 where they fit; never contradict them.
3. **Walks one concrete example** — `example-enrich-ip` for builders, the kit's kickoff for onboarding, the ops trio for operators — with the exact commands, files and gates, in order.
4. **Links every claim to its source file** in this repository. A guide explains; the linked file is the truth. Where they disagree, the file wins.
5. **Marks anything unconfirmed** with its `docs/VERIFY.md` item number instead of stating it as fact.
6. **Ends with a "Check yourself" block** of five or six questions, answered by links.
7. **Uses only placeholders** (`<your-tenant>`, `<org>`). No customer names, hostnames, credentials or model ids. The four MCP surfaces are only ever called modes.
8. **Passes `./scripts/storyline check --all`** (the `doc_links_resolve` check covers every relative link).

## Spec per guide

**01 · Your first story, end to end.** Follow `example-enrich-ip` from intake to live: `/storyline` intake, the scout's discovery note, the architect's design and contract, the eval cases, G1 and G2, the build loop with the G3 plan, export and lint, the verify reviewers and G4, `ship.yml` and the change request, G5, shadow and G6. One diagram per phase, one command block per step, and what the builder sees at each gate.

**02 · Approving gates.** For each human gate (G0, G2, G3, G4, G5a, G5b, G6, G7, GX, and releasing GB): what arrives, what evidence to open, what to check, how to record the decision, and what happens next. A decision tree diagram per gate family. What an approver must never delegate to an agent.

**03 · The crew and how they hand off.** The roster by phase, the baton and payload contracts, the touch sets, `apply`, the rework cap, what `next` decides and why no model decides it, running the same flow in Claude Code and in Cursor (and what Cursor cannot yet scope, VERIFY K4), and the Tines-side runtime agents.

**04 · Day one with the starter kit.** The plan check, the credentials by name, the import, the kickoff Page field by field, reading the setup report, merging the setup-report PR, the `[BY HAND]` list, turning the runtime crew on, and choosing a model provider including a local model behind the tunnel.

**05 · Running it.** The monitoring signals, the router, the sweep and its proposals, approving an alert change, the propose-fix PR, drift PRs, rollback, and the break-glass jobs — each with a diagram and a runbook table.

**06 · Cost and security for decision makers.** What spends Tines AI credits and what does not, the ceilings and alerts, a worked month, the identities and what each can do, the four proofs a security reviewer can check, and the honest pros and cons.
