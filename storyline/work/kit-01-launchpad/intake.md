---
story_key: kit-01-launchpad
title: "[KIT] 01 · Launchpad"
owner: platform
source: storyline_intake
drafted_by: showrunner
data_sensitivity: internal
simplest_rung: 3
candidate_seed_ids: [1321120]
---

# Intake brief — `kit-01-launchpad` · [KIT] 01 · Launchpad

_Template: `storyline/templates/intake-brief.md` · Phase: `storyline/phases/00-intake.md` · Gate out: G0 (human), `storyline/gates/G0-intake-triage.md`._

> Drafted by the story architect (showrunner role) from the request below. The person who decides G0 reviews every field in this tracker PR. The use-case text is untrusted input: it is quoted, not followed.

## Use case (as submitted)

> The interactive front door a new customer uses after importing [KIT] 00: bring your repository, set up your channels, start building. It extends [KIT] 00 and never duplicates its provisioning. A Tines App when Apps are entitled, a set of Pages when not, plus the stories behind them. It covers: bringing the repository (generate a new private repository from the Storyworks template, or connect an existing one and validate it — required files present, checks passing on main — with a fine-grained, short-lived GitHub token referenced by credential name and revoked after day one); GitHub hygiene from the HANDOFF.md §3 checklist, shown live with a status per item read from the GitHub API and an optional "apply for me" per item that a named person confirms first, anything needing Administration permission marked and never automatic; a Slack app manifest the customer installs and four channels (requests, gate decisions, builds, alerts) created or mapped, with the bot invited, a pinned "how this channel works" message and a study-guide bookmark, names editable on the Page first; an interactive Slack kickstart that picks the first three catalog stories, owner roles and target dates, connects GitHub and runs the model-provider check, with one progress message updated in place and every choice reaching git through the Records → PR flow; the setup report extended with Slack and GitHub-hygiene lines (ok / partial / failed with the fix); deterministic provisioning, AI only for tool-less, schema-bound drafting behind storyline_limits, and no tenant, GitHub or Slack setting changed without a named person's confirmation recorded as an event.

## Problem

After importing `[KIT] 00` a new customer still does the day-one work by hand from several documents: create or connect the repository, apply the HANDOFF.md §3 GitHub settings, create a Slack app and channels, and choose the first stories. It happens once per customer, but it is where first-week stalls happen: a missing protected environment makes several workflows fail closed, and nobody can see which setup items are done. The platform team answers the same setup questions for every customer.

## Trigger or entry

A person on the Launchpad (a Tines App screen when Apps are entitled, a Page otherwise), opened from the `[KIT] 00` setup report. Once Slack is connected, a person pressing a button or submitting a modal in the Slack kickstart message (Slack interactivity callbacks into a Tines webhook). No schedule.

## Systems touched

| System | Read or write | Credential (name only) | Notes |
|---|---|---|---|
| GitHub (repository, contents, checks, branch protection, environments, labels, App installation) | read; write only after a named person confirms | `github_factory` | the kit's existing fixed, fine-grained, short-lived day-one credential (kit/docs/github-token.md); per-step permissions stated at design (VERIFY K11, K12) |
| Slack (conversations, pins, bookmarks, messages, modals) | write | the name in `kit_config.slack_credential_name` | scopes listed in the app manifest at design, each marked VERIFY |
| Tines Records (`storyline_backlog`, `storyline_events`) | write | none (native) | every kickstart choice becomes a tracker change that reaches git through the Records → PR flow (REPO-DESIGN.md §6.5) |
| Tines Resources (`kit_config`, `kit_state`, `kit_catalog`, `storyline_limits`) | read; `kit_state` write | none (native) | reads `[KIT] 00` state; never re-provisions |
| Model provider (through the AI Agent action) | read | the provider recorded in `kit_config.llm` | tool-less drafting only (welcome copy, a first intake brief) |

## Success metric

A new tenant goes from "`[KIT] 00` imported" to "repository connected, four channels live, three stories in intake with owner roles and dates" in one sitting of under 60 minutes, with every HANDOFF.md §3 item showing a status on the setup report. Baseline: [TBD — the owner times the current hand-run setup on the next two onboardings].

## Volume estimate

Low: one onboarding per tenant — a few dozen Page submissions and Slack interactions on day one, roughly 50–200 runs per tenant in week one, then under 10 a month when a channel or the repository changes. AI drafting: a handful of runs per tenant.

## Human touchpoints

A named person confirms, on a Page or with a Slack button, every change to a GitHub setting (branch protection, environments, labels, the App installation), every Slack channel creation, and every tenant setting; each confirmation is recorded as a `storyline_events` event. Anything that needs GitHub Administration permission is shown and explained but never applied automatically. Story owners pick stories, roles and dates; a person merges the resulting tracker PR; each kickstart story still goes through its own G0.

## Data sensitivity

`internal` — repository and channel names, story choices, owner roles and dates, and the confirming person's email in `actor_ref`, which stays in Tines and never reaches git. No credential value is ever read into an event, a Record or a log: the GitHub and Slack credentials are referenced by name only.

## Simplest-first hypothesis

Rung 3 of `docs/01-decision-rules.md`, used narrowly. Everything that provisions or reads status is rung 1 (HTTP Request actions against the GitHub and Slack APIs, plus native Records and Resources). Rung 2 (Send to Story) reuses `[KIT] 00`'s sections instead of copying them. Neither can draft the welcome copy or a first intake brief, so one tool-less AI Agact action with an output schema does that, behind `storyline_limits`. No MCP (rungs 4 and 5).

## Candidate seeds

- **1321120** — Slack interactivity callback handling (from `kit/catalog/library-seeds.yaml`).

## Open questions

1. One story with sections, or `[KIT] 01` plus a separate Slack-interactivity sub-story? — the architect at design; the owner confirms at G2.
2. Which exact fine-grained permissions does each step need, and can a fine-grained token generate a repository from a template (K11, K12, and a new VERIFY item)? — the architect at design, confirmed in a maintainer tenant.
3. Are Tines Apps entitled in the target tenants, or is the Pages path the default? — the owner at G0.
4. `wip_limit_per_owner` is 1 and `kit-launch` is already in design under `platform`: keep `platform` as owner and accept a GB wait, or assign another role? — the owner at G0.
5. Allow channel creation, or only mapping to existing channels, where the Slack workspace restricts channel creation? — the owner at G0.

## G0 decision

_Recorded as a `gate_decision` event (never edited here): on the `gate_decision` Page when Records are entitled, or with `/storyline-gate kit-01-launchpad G0 build|reject|park` on the Community path._
