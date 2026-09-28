# `kit/records/` — the tracker's Record types

_Spec: REPO-DESIGN.md §8.1. Created by `[KIT] 00` A18 through `POST /api/v1/record_types`, with each file below as the request body and `team_id` set at run time (the files carry the `0` placeholder). The field ↔ YAML mapping is [`../tracker/field-map.yaml`](../tracker/field-map.yaml)._

Record types need **Records**, part of Advanced Workflows (Business and above). They are the **queryable projection** of the tracker in git and the **inbox** for decisions made in Tines (REPO-DESIGN.md §6.5); git stays the system of record.

| File | Record type | Holds | Retention |
|---|---|---|---|
| [`sdlc_backlog.record-type.json`](sdlc_backlog.record-type.json) | `sdlc_backlog` | one row per story — the tracker (32 custom fields) | none (kept for the licence's life); `max_records_limit: 1000`, `on_limit_reached: REJECT` |
| [`sdlc_events.record-type.json`](sdlc_events.record-type.json) | `sdlc_events` | the append-only transition and cost log | `ttl_days: 365`, `retention_column_name: CREATED_AT`, `on_limit_reached: EVICT_OLDEST`, `max_records_limit: 100000` |
| [`sdlc_milestones.record-type.json`](sdlc_milestones.record-type.json) | `sdlc_milestones` | the day-1, week-1 and week-4 milestones | none |

## Rules

- **Field types used:** `TEXT` (512 characters), `NUMBER`, `TIMESTAMP` (sent in UTC), `BOOLEAN`, `TEXT_ENUM` (at most 100 fixed values), `JSON` (not filterable) and `ARTIFACT` (large text; whether it holds 15,000 or 100k characters is **CONFLICT K29**, and D4's `render_brief` truncation depends on it — plan for the lower figure until it is resolved). At most 50 custom fields per type.
- **Enums are generated, not typed.** The `phase`, `status`, `open_gate`, `from_phase`, `to_phase` and `gate` fixed values are exactly the names in `sdlc/lifecycle/state-machine.yaml` (phases + `parked` + `rejected` + `retired`; the six statuses; `none` + the eleven gates; `none` + the phases for the event types). `./scripts/sdlc check` (`phase_enum_in_sync`) and `./scripts/kit tracker-json --check` fail when they drift. Changing the machine means changing these files in the same PR, then migrating the live types (`PUT /api/v1/record_types/{id}` adds fields; changing enum values needs care — REPO-DESIGN.md §14, con 11).
- **No secrets, no personal data in fields that reach git.** `actor` is always a role. `sdlc_events.actor_ref` holds the approver's email for in-tenant audit only; it is never sent to git (the outbox returns roles).
- **Only through the Records API.** Sections B–E read and write these types only through HTTP Request actions to the Records API, by the type and field ids A18 stored in `kit_state.rt_<type>` and `kit_state.fields_<type>` — never through Record actions — so nothing depends on how an import resolves record types (K6). Creation is not idempotent: upserts run under the `sdlc_sync_lock` compare-and-swap (B4–B7), and seeding under the `records_seeded` compare-and-swap (A20).
- **Test vs live.** Records written from a change-control draft are test records, and test and live records never mix. Submit the kickoff on the LIVE story (§7.1; K39).

## Licence tiers

Record types per licence: Starter 5, Essentials 50, Standard 100, Advanced 150, Enterprise L1 250. The kit adds 3 to the ops trio's 6 (nine in all). On **Starter**, A18 creates `sdlc_backlog` and `sdlc_milestones` only, keeps events in `events.jsonl` only, and says in the setup report that the ops trio's six types alone already exceed Starter's 5 (the bundle marks `sdlc_events` with `skip_on_records_tier: ["starter"]`). The Records API allows 400 requests a minute (Query 200) and a page size of 500.

## Verify in your tenant

| Item | What to check | What changes |
|---|---|---|
| **K16** | The exact key for a field's name in `fields[]` (the files use `name`, beside `result_type` and `fixed_values`, as on the Create API page), and whether the create response returns the field ids | These files' keys; A18's field-id maps in `kit_state` |
| **K29** | ARTIFACT capacity (15,000 vs 100k characters) | Brief and retro truncation |
| **K5 / K35** | The request bodies of `POST /api/v2/records/search` and `POST /api/v2/records/aggregate` | Server-side filtering in B5, C3, C5, D5, D6, E3; the per-agent daily count in D2 (else the documented v1 `GET /api/v1/records` and `POST /api/v1/records/query`) |
| **K39** | Records created through the API with `test_mode` off are live in a change-controlled story | The §7.1 note on submitting the kickoff on the live story |

The retention keys (`ttl_days`, `retention_column_name`, `on_limit_reached`, `max_records_limit`) are written as REPO-DESIGN.md §8.1 records them; confirm them with the same scratch type as K16.
