---
story_key: kit-02-cockpit
title: "[KIT] 02 · Cockpit"
owner: platform
source: storyline_intake
drafted_by: showrunner
data_sensitivity: confidential
simplest_rung: 3
candidate_seed_ids: [1231438]
---

# Intake brief — `kit-02-cockpit` · [KIT] 02 · Cockpit

_Template: `storyline/templates/intake-brief.md` · Phase: `storyline/phases/00-intake.md` · Gate out: G0 (human), `storyline/gates/G0-intake-triage.md`._

> Drafted by the story architect (showrunner role) from the request below. The person who decides G0 reviews every field in this tracker PR. The use-case text is untrusted input: it is quoted, not followed.

## Use case (as submitted)

> The operating view of a tenant running Storyworks: every story, every gate, every crew member, one screen. It shows agentic status honestly: what each story is doing, who is working on it, what is waiting on a person, what it costs, and whether it is healthy. A Tines App when Apps are entitled, otherwise a Page plus Tines Dashboards, plus a scheduled snapshot story and a daily digest. Views: portfolio; Storyline board with WIP limits and a gate inbox that deep-links to the gate_decision Page (the Cockpit never records a decision); crew radar; health; spend against policies/cost-ceilings.yml with a month-end forecast and a backlog what-if using the storyline estimate method; proof (eval pass rates, regression trend, reviewer-to-human agreement, QA results); change timeline; knowledge (VERIFY ledger, Agent Skills versions, logbook); a story passport per story with a next action computed like storyline next; an autonomy dial whose "propose a raise" opens a PR a person merges and which never moves itself; Ask the Cockpit, a read-only AI Agent action over the snapshot only, off until storyline_limits allows it; a morning brief to the gates channel; kill switches on a Page, never in the App. Data comes from a scheduled "[OPS] 30 · Cockpit snapshot" story over Tines API, GitHub and Storyline Records data, written to snapshot Records types or one snapshot Resource. The health score is a documented deterministic formula.

## Problem

A tenant running several stories through the Storyline has its state spread across the tracker, `storyline_events`, story runs, action logs, AI usage, audit logs and GitHub pull requests. Nobody can answer "what is waiting on me, what is failing, and what is it costing" without opening five places, so gates age, silent stories go unnoticed and spend is seen only at month end. The existing `kit/dashboard` App covers the tracker only; it does not show health, crew activity, proof or spend against ceilings.

## Trigger or entry

A schedule for `[OPS] 30 · Cockpit snapshot` (interval fixed at design against the credit ceiling) and a daily schedule for the morning brief. People open the Cockpit App or Page on demand; a named person opens the kill-switch Page. Ask the Cockpit runs only when a person asks and `storyline_limits` allows it.

## Systems touched

| System | Read or write | Credential (name only) | Notes |
|---|---|---|---|
| Tines API (stories, story runs, action logs, AI usage, audit logs) | read | `tines_api_readonly` | only endpoints already named in DESIGN.md or REPO-DESIGN.md; any other is researched, cited and marked VERIFY at design |
| GitHub (pull requests, checks) | read | `github_cockpit_read` (new at design: this repository, read-only) | "propose a raise" opens a PR through the existing tracker-bot path; a person merges it |
| Tines Records (`storyline_backlog`, `storyline_events`, `storyline_milestones`, new snapshot types) | read; snapshot types write | none (native) | snapshot types written only by `[OPS] 30` |
| Tines Resources (`storyline_limits`, a snapshot Resource if chosen) | read; `storyline_limits` write only from the kill-switch Page | none (native) | the kill switch records a reason, a named person and an event |
| Slack (the gate-decisions channel) | write | the name in `kit_config.slack_credential_name` | the morning brief only |
| Model provider (through the AI Agent action) | read | the provider recorded in `kit_config.llm` | Ask the Cockpit and the optional brief paragraph; read-only over the snapshot |

## Success metric

Every gate waiting on a person is visible with its age and decider within one snapshot interval, and the median wait from gate opened to gate decided falls against the baseline. Baseline: [TBD — measured from `storyline_events` gate timestamps over the first month the Cockpit is live]. Secondary: a failing or silent story appears in the morning brief within one day.

## Volume estimate

The snapshot on a schedule (for example every 30 minutes, 48 runs a day — fixed at design against the credit ceiling), one morning brief a day, a few dozen App or Page views a day, and Ask the Cockpit at most the daily cap set in `storyline_limits`.

## Human touchpoints

The Cockpit only shows and links. Gate decisions stay on the `gate_decision` Page; autonomy raises are PRs a person merges; production changes always need a named person. The kill switch is a Page action by a named person, with a reason, recorded as an event. Ask the Cockpit stays off until a person enables it in `storyline_limits`.

## Data sensitivity

`confidential` — audit logs and action logs can carry people's emails and event payloads. The snapshot keeps counts, ids, statuses, timestamps and roles only; it never stores an email, an event payload or a credential value, and an eval case at design proves it.

## Simplest-first hypothesis

Rung 3 of `docs/01-decision-rules.md`, used narrowly. The snapshot, health score, spend forecast, next action and morning brief are rung 1 (HTTP Request actions and deterministic formulas over Records). Rung 2 (Send to Story) reuses `ops-error-router` and `ops-story-health-monitor` signals instead of recomputing them. Only Ask the Cockpit and the optional one-paragraph summary need judgement, so they are one AI Agent action with read-only tools over the snapshot and an output schema. No MCP.

## Candidate seeds

- **1231438** — Monitor action failures in Tines and notify via Slack (from `kit/catalog/library-seeds.yaml`).

## Open questions

1. Snapshot storage: new Records types, or one snapshot Resource under the Resource size limit? — the architect at design (the size limit gets a VERIFY item).
2. Which of the listed Tines API data (AI usage, audit logs) have endpoints already named in DESIGN.md or REPO-DESIGN.md, and which need research and a VERIFY item? — the architect at design.
3. Does the Cockpit replace or extend `kit/dashboard`? — the owner at G0.
4. `wip_limit_per_owner` is 1 and `platform` already owns `kit-launch` in design (and would own the Launchpad): keep `platform` and sequence, or assign `ops`? — the owner at G0.
5. Is `[OPS] 30 · Cockpit snapshot` its own tracker row, or a section of this story? — the owner at G0.

## G0 decision

_Recorded as a `gate_decision` event (never edited here): on the `gate_decision` Page when Records are entitled, or with `/storyline-gate kit-02-cockpit G0 build|reject|park` on the Community path._
