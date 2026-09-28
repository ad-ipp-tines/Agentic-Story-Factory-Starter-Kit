# The App's three endpoints

_Spec: REPO-DESIGN.md §7.5 C6 and §9.2. Documentation only: this file is **left out of the bundle**, because Apps accept only tsx, ts, jsx, js and json files. The endpoints themselves are actions in `[KIT] 00` section C, built through Mode 2 with build prompt P-K13 (`stories/kit-factory/build-prompts.md`)._

An App cannot write a Record, call the network, or run on a schedule. Every write and every external call goes through an **app endpoint**: a Webhook entry in `[KIT] 00` section C, a chain of actions, and a **message-only Event Transform** as the exit, whose output is the App's answer. The timeout is 30 s; under 1 s is recommended. Each endpoint is wired to the App **[BY HAND]** in the story's Interfaces → App endpoints after the App is published (the `[BY HAND]` list in the setup report). Rotate each endpoint Webhook's secret after import, before use (§7.2, K8).

| Endpoint | Chain (section C) | Used by | Status in v1 |
|---|---|---|---|
| `app_add_use_case` | the C4 chain: `normalize_use_case` → guard → `create_row` → `log_event` → section D | `routes/Backlog.tsx`, "Add a use case" | Built in the story. The App's call primitive is **VERIFY K18**, so until it is wired in `lib/tracker.ts` (`callAppEndpoint`) the form says so and links to the tracker Page |
| `app_gate_decision` | the C5 chain: `is_approver` → `is_gate_open` → `apply_decision` → `update_row` → `log_event` → section D | nobody yet | Built in the story, **not called by the App**: whether an app endpoint receives the viewer's identity is **K18**, and `is_approver` needs it. Until K18 is confirmed, the App deep-links to the `gate_decision` Page, which reads the submitter's email from the Page headers |
| `app_costs` | `GET /api/v1/ai_usage` (month to date: `start_date` = the 1st, `end_date` = today, `group_by=story`) with `tines_api_readonly` → shape | `routes/Costs.tsx` | Built in the story; the call primitive is K18. `tines_api_readonly` sees only what that key may see (**K38**) |

Every exit follows the scaffold's result conventions (`AGENTS.md` §4): a success carries 3–5 fields; a failure ends on an Event Transform named `error` that returns `{status: "error", error_category, retryable, message}` with `error_category` one of `auth | rate_limit | upstream_5xx | validation | permission | unknown`; a guard refuses with `{status: "refused", reason}` before any write.

## `app_add_use_case`

**Request** (the App's form, `routes/Backlog.tsx`):

```json
{
  "title": "Triage suspicious login alerts",
  "use_case": "Untrusted free text: what happens today and what should happen.",
  "owner_role": "security-automation",
  "target_date": "2026-11-02T00:00:00Z",
  "library_seed_id": null,
  "mode_hint": "unknown"
}
```

- `target_date` is empty or UTC with `Z` (Records drop offsets). `library_seed_id` is `null` or an id in the `kit_catalog` Resource's `seed_ids` (never free text). `mode_hint` is one of `none | sub-story | mode-1-preset | mode-3-agent | mode-4-server | unknown`.
- **Guard (a Trigger before any write):** required fields present; `owner_role` contains no `@`; no field matches a token pattern (`ghp_`, `github_pat_`, `gho_`, `ghs_`, `xox[bp]-`, `sk-`, `AKIA`, `Bearer `), the same list as A3; `library_seed_id` is in `kit_catalog.seed_ids`. A failure returns `{status: "refused", reason}`.
- **Key:** the title lowercased and hyphenated, at most 48 characters, `-2`, `-3`… on collision — the rule A2 uses for custom rows.
- **Create** (`POST /api/v1/records` by type and field id from `kit_state`): `phase: intake`, `status: active`, `open_gate: none`, `specialist_due: brief-writer` (when the AI Agent action is entitled), `specialist_status: pending`, `pending_repo_sync: true`, `pending_base_rev: 0`, `rev: 0`, timestamps in UTC. `mode_hint: unknown` is stored as `mode: none` (the tracker has no `unknown` mode; design sets the real one).
- **Event:** an `sdlc_events` row `event_type: transition`, `from_phase: none`, `to_phase: intake`, `actor` = the owner role, `actor_kind: human`. Then section D (the brief writer).

**Response:**

```json
{ "status": "ok", "story_key": "triage-suspicious-login-alerts", "phase": "intake", "provisional": true }
```

`provisional: true` because the row reaches git only when a person merges the next tracker PR (Flow 2, REPO-DESIGN.md §6.5).

## `app_gate_decision`

**Request:** `{ "story_key": "<slug>", "gate": "G0 | G6 | G7 | GX | unpark", "decision": "<one of sdlc_state_machine.page_options[gate]>", "note": "free text" }`

- **Identity (K18).** `is_approver` compares the caller's email with `RESOURCE.sdlc_approvers[<gate>]`. If the endpoint does not receive the viewer's identity, it **refuses every call** (`{status: "refused", reason: "caller identity unavailable"}`) — it never falls back to trusting a field in the request body. This is why the App does not call it in v1.
- `is_gate_open`: the row's `open_gate` equals the gate chosen (for `unpark`, the row is `parked`).
- `apply_decision`: the next phase and status from `RESOURCE.sdlc_state_machine.page_decision_table["<gate>:<decision>"]` (or `["unpark"]`), matched on the row's current phase — the same table the `gate_decision` Page uses, generated from `sdlc/lifecycle/state-machine.yaml` by `./scripts/kit bundle`.
- `update_row`: `pending_repo_sync: true`, `pending_base_rev` = the row's `rev`, `outbox_seq + 1`. `log_event`: `event_type: gate_decision`, `actor` = the approver's **role**, `actor_ref` = the email (in-tenant only; never sent to git).

**Response:** `{ "status": "ok", "story_key": "<slug>", "from_phase": "intake", "to_phase": "discover", "provisional": true }`

G1, G2, G3, G4, G5a and G5b are **never** decidable here: they are a script, merges, a build-session command, a GitHub environment review and a change request (REPO-DESIGN.md §4.5).

## `app_costs`

**Request:** `{ "period": "month_to_date", "group_by": "story" }` — the only period in v1.

**Chain:** compute `start_date` (the 1st of this month, tenant time) and `end_date` (today) → `GET /api/v1/ai_usage?start_date=…&end_date=…&group_by=story` with the credential `tines_api_readonly` (the scaffold's Viewer key; `allowed_hosts` = the tenant host) → shape.

**Response:**

```json
{
  "status": "ok",
  "from": "2026-11-01", "to": "2026-11-14",
  "rows": [ { "story_id": 0, "story_key": "", "credits_used": 0, "billed_cost": null } ]
}
```

- `story_key` is optional: the endpoint may fill it by matching `story_id` with `sdlc_backlog.prod_story_id`; the App matches on either.
- `credits_used` and `billed_cost` are **never summed**. A custom or local provider spends no Tines credits and bills outside Tines; `billed_cost` for those providers is **K25**. The App shows such stories as "not metered in credits".
- Which rows a team-scoped, non-admin Viewer key sees is **K38**; the App says "n/a" rather than zero when a story has no row.

## Verify in your tenant before relying on these

| Item | What to check | Until then |
|---|---|---|
| K18 | How an App calls an app endpoint; whether the endpoint receives the viewer's identity; nested file paths in `PUT …/files`; which packages Apps may import; whether API file pushes spend credits | `callAppEndpoint` returns "not wired" and every caller falls back to the tracker Page |
| K38 | Which `ai_usage` rows `tines_api_readonly` sees | Costs shows "n/a" for missing stories; the Tines Dashboard and `drift.yml`'s budget job report actuals |
| K25 | `billed_cost` for custom and local providers | Those stories show "not metered in credits" |
| K8 | Whether import keeps each Webhook's path and secret | Rotate every endpoint Webhook's secret after import |
