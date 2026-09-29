---
# Machine-read keys. One file per spike: storyline/work/<slug>/spikes/<spike_id>.md, proposed by story-architect.
story_key: <slug>
spike_id: <kebab-case-id>
verify_ids: []                         # the VERIFY items that block the design (K1–K45 or scaffold #n), from docs/VERIFY.md
scratch_team: <scratch team role>      # never the dev team's real stories and never the prod team
timebox_days: 2
decision: pending                      # pending | go | no_go
decided_by: <role>
---

# Spike — `<spike_id>` for `<slug>`

_Template: `storyline/templates/spike.md` · Used in `storyline/phases/02-design.md` when a VERIFY item blocks a design decision. The design is not final, and G1 does not pass, until every spike's decision is `go` or `no_go`._

> A spike answers a question the documentation does not. It runs in a **scratch team**, with placeholder data, inside its timebox. It never changes a real story, and what it builds is thrown away.

## Questions

1. <the exact question, and the VERIFY id it resolves>

## Hypothesis to falsify

<One sentence that a single observation could prove wrong: "A formula reading a Resource that does not exist yields null, not an error (K10).">

## How it will be tested

<Steps in the scratch team: what to build, what to send, what to read. Placeholders only.>

## Non-goals

- <what this spike will not try to answer or build>

## Result

<What was observed, with the date and the role that ran it. Record the outcome in `docs/VERIFY.md` as that file's own rules require (append-only, a role never a name).>

## Go / no-go

**`go`** — the design may rely on the confirmed behaviour · **`no_go`** — the design takes the fallback named in the VERIFY table. <Which, and what changes in `design.md`.>
