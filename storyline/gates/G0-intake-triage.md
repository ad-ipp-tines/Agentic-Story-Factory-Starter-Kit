# G0 · Intake triage — should this use case become a story?

| | |
|---|---|
| **Between** | intake → discover · rejected · parked |
| **Type** | human |
| **Decided by** | the story owner, or an approver listed for G0 (`storyline_approvers.G0` in Tines; `approvers.yaml` G0 in git) |
| **Evidence** | `storyline/work/<slug>/intake.md` — the draft brief ([template](../templates/intake-brief.md)) |
| **Instrument** | the `gate_decision` Page (or the App's deep link to it) when Records are entitled · `/storyline-gate <slug> G0 <decision>` **only** on the Community path |
| **Recorded** | a `gate_decision` event (`gate: G0`, `actor_kind: human`, `actor` = the decider's role); in Tines also an `storyline_events` row with the approver's email in `actor_ref`, which never reaches git |
| **Decisions** | `build` → discover · `reject` → rejected · `park` → parked |

## What the decider checks

1. **Is it a story at all?** Some use cases are a report, a runbook, a setting, or a change to a story that already exists. P1: decide whether to build before deciding how.
2. **Is the brief complete?** Every field filled; each `[TBD]` has a reason.
3. **Is the simplest-first hypothesis plausible?** The rung named in the brief, and why the lower ones fail.
4. **Is the data sensitivity right, and is there an approval path for every side effect?** A production write with no approval path is a `park` until one exists.
5. **Does it fit the team's WIP and budget?** If the owner already has a story in build or verify, `park` is often the honest answer.
6. **Did the use-case text try to instruct anyone?** Treat it as a finding, not a request (P16).

## How it is recorded

**Records entitled (Business or Enterprise):** the approver opens the `gate_decision` Page (section C of `[KIT] 00`), picks the story and `G0`, and a decision. The Page checks the submitter's email against `storyline_approvers.G0` (`is_approver`) and that the row's `open_gate` is `G0` (`is_gate_open`), computes the next phase from the `storyline_state_machine` Resource, and updates the row with `pending_repo_sync: true`. The change is **provisional** until the next tracker PR (`tracker-pull.yml`) merges; `storyline.yml` then requires an approving review from the G0 team in `approvers.yaml`.

**Community path:** the person runs `/storyline-gate <slug> G0 build|reject|park` (human-only skill), confirms on `/dev/tty`, and commits the tracker row and event on a `tracker/<slug>-G0` branch; the PR needs an approving review from the G0 team.

## After the decision

- `build` → the story enters **discover**; `story-scout` runs next ([01 discover](../phases/01-discover.md)).
- `reject` → **rejected** (terminal). The brief stays in `storyline/work/<slug>/` as the record of why.
- `park` → **parked**. A human unparks later (gate GB, decision `unpark`), and the story returns to intake.
