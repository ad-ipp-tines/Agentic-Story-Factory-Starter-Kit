---
story_key: example-enrich-ip
reuse_decision:
  kind: import_seed
  target: "87626"
cited_library_ids: [87626, 1252750]
candidate_ids_unverified: []
---

# Discovery note — `example-enrich-ip`

> **Worked example — illustrative.** Placeholders only; see the note at the top of `intake.md`.

_Template: `storyline/templates/discovery-note.md` · Phase: 01 discover · Written by `story-scout` through `./scripts/storyline apply` on branch `design/example-enrich-ip` · Exit: the check `discovery_complete`._

## Where the scout looked

| Place | How | Result |
|---|---|---|
| The Story Library | `kit/catalog/library-seeds.yaml` only; the catalog ids' own Library pages confirmed with WebFetch (VERIFY K43) | 2 candidates |
| Stories in this repository | `stories/*/README.md`, `story.meta.yaml`, mode badges | 1 candidate |
| Published stories in the dev team | `./scripts/tines live-activity` (read-only) | none match |

## Candidates

| # | Source | Id | Name (as recorded) | Fit | Why | Entitlements needed | Verified by |
|---|---|---|---|---|---|---|---|
| 1 | library | 87626 | Analyze an IP in many services at once | high | Looks up one IP in several services and combines the answers — the core of this story; its vendor templates give the field names the verdict needs | none beyond the base plan | catalog |
| 2 | repo | `example-enrich-ip` | `[SEC] 01 · Enrich IP (sub)` | high | The scaffold already carries this slug's design (`stories/example-enrich-ip/README.md`: contract, action table, tests) and a SKELETON export. The design is reused; the SKELETON is never imported | Records (optional, for `ioc_cache`) | repo |
| 3 | library | 1252750 | Get IP address information | medium | A single-service IP lookup; the pattern for starter story #3 (`ip-info-tool`), which is a separate story — not a substitute for two services and a combined verdict | none beyond the base plan | catalog |

## Unverified ids (never cited)

None.

## Reuse decision

**`import_seed`** → **87626**. Import the seed into the dev team's Seeds folder to read its vendor templates and field names, and build `[SEC] 01 · Enrich IP (sub)` from the repository's existing design (candidate 2). The seed is a starting point to read, not a story to ship. The design must add what the seed does not have: the `never_block` guard before any lookup, the `ioc_cache` Record with a 24-hour TTL, the `result`/`refused`/`error` exits, and HTTP hardening on both lookups.

## Entitlement fit

Business tenant with Records (from `kit/tenant/config.yaml`): the `ioc_cache` Record type is available. No AI Agent action is needed. Send to Story is available on every plan.

## Constraints for design

- `virustotal_api` and `abuseipdb_api` must exist in the dev and prod teams under these names before build; the story references them by name only.
- The `never_block` Resource must exist in both teams and must **not** contain the documentation ranges, or the test event is refused.
- Free-tier vendor limits: sequential lookups, `retry_on_status` 429, a low retry count, and the cache.
- The Send to Story timeout stays at 25 s, under the 30-second tool ceiling of a Mode 4 MCP server action, so the same story is safe to expose as a tool later.

## [BY HAND]

- [ ] Import Library story 87626 into the Seeds folder of the dev team — the Tines Stories MCP server cannot import from the Library.
- [ ] Create the `ioc_cache` Record type in the dev and prod teams (whether `/mcp` can create Record types is scaffold VERIFY #26).
- [ ] Create `virustotal_api`, `abuseipdb_api` (with `allowed_hosts`, Workbench access off) and the `never_block` Resource in both teams.
- [ ] Enable Send to Story access for the team on the story once it exists.
