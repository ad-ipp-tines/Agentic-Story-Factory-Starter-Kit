---
# Machine-read keys: the check discovery_complete reads them (sdlc/lifecycle/state-machine.yaml).
story_key: <slug>
reuse_decision:
  kind: "[TBD]"                        # import_seed | reuse_story | build_new
  target: ""                           # a catalog Library id, a repo slug, or "" for build_new
cited_library_ids: []                  # every Library id this note cites; each MUST be in kit/catalog/library-seeds.yaml
candidate_ids_unverified: []           # ids seen but not in the catalog — never cited; a human adds them by CODEOWNER PR
---

# Discovery note — `<slug>`

_Template: `sdlc/templates/discovery-note.md` · Phase: `sdlc/phases/01-discover.md` · Written by `story-scout` through `./scripts/sdlc apply` · Exit: the check `discovery_complete` (no human gate — design has one)._

> The question this note answers: **does something already exist that does most of this?** Reuse before build (P1).

## Where the scout looked

| Place | How | Result |
|---|---|---|
| The Story Library | `kit/catalog/library-seeds.yaml` only; WebFetch only to confirm a catalog id's own `tines.com/library/stories/<id>/` page (VERIFY K43) | <n> candidates |
| Stories in this repository | `stories/*/README.md`, `story.meta.yaml`, mode badges | <n> candidates |
| Published stories in the dev team | `./scripts/tines live-activity` (read-only) | <n> candidates |

## Candidates (at most five)

| # | Source | Id | Name (as recorded) | Fit | Why | Entitlements needed | Verified by |
|---|---|---|---|---|---|---|---|
| 1 | library · repo · tenant | <id or slug> | <name> | high · medium · low | <one sentence> | <records, ai_agent_action, …> | catalog · repo |

## Unverified ids (never cited)

| Id | Where it was seen | Why it looked relevant |
|---|---|---|
| — | — | — |

## Reuse decision

**`import_seed` · `reuse_story` · `build_new`** → <target>. <Two or three sentences: why this, and what the design must add or remove.>

A seed is a starting point to read, not a story to ship. A reference-only seed is never recommended for shipping.

## Entitlement fit

<Against `kit/tenant/config.yaml`: which needs are met, which are not, and what the design must avoid because of it (for example: no Records → no cache Record; no AI Agent action → no Mode 3).>

## Constraints for design

- <credential or Resource that must pre-exist in both teams>
- <limit that shapes the design: the 30-second Mode 4 tool ceiling, a vendor's free-tier rate limit, a flow budget>

## [BY HAND]

- [ ] Import Library story <id> into the Seeds folder of the dev team — the Tines Stories MCP server cannot import from the Library.
- [ ] <anything else no API and no Mode 2 session can do>
