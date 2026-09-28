# `[OPS] 14 · Get recent runs (sub)` — the `ops_get_recent_runs` lookup, shared by the sweep and the Mode 4 server

**Slug:** `ops-get-recent-runs` · **Mode badge:** `sub-story` · **Tier:** `ops` · **Owner:** ops (CODEOWNERS: security-platform) · **Descends from:** —

> **Not built yet.** This folder holds the contract, the meta file and the manifest entry so lint, review, ship and drift see this story before `[OPS] 10 · Monitor story health and credits` ships. Build it in the dev team with `/tines-build-story ops-get-recent-runs "Build [OPS] 14 · Get recent runs (sub) from stories/ops-get-recent-runs/README.md"` (the owner sets `TINES_ALLOW_OPS_BUILD=1`), record its dev id in `../_manifest.yaml`, then `/tines-export ops-get-recent-runs`. The contract, the verbatim tool description and the build order live in `../ops-story-health-monitor/agent/tools.md` — this README restates only what the folder needs.

## Purpose

One read-only lookup, `ops_get_recent_runs`, used as a Send to Story tool by the sweep's `triage` agent (Mode 3) and exposed by `[OPS] 20 · Ops tools (MCP server)` (Mode 4). It wraps `GET /api/v1/stories/{id}/runs?since=` + `GET /api/v1/stories/{id}/runs/{guid}/summary` with the credential `tines_api_readonly` and returns 3–5 fields, never a body. Story runs carry no status field; this returns nothing about events or payloads.

## Mode badge

`sub-story` — Send to Story enabled (team access, Timeout Duration 20 s wherever it is used as a tool); used from the Mode 3 `triage` agent in `ops-story-health-monitor` and the Mode 4 `ops-tools-server`.

## Entry and expected input

| Entry | Action name | Expected fields | Notes |
|---|---|---|---|
| Send to Story (a Webhook entry, team access) | named at build | `story_id` (integer, required) · `since` (ISO 8601, default 24 h ago) | `normalize` wraps every field in `DEFAULT()`; `is_valid_input` / `is_invalid_input` Triggers before the API call |

## Output — the `result` shape

```json
{ "runs": "integer", "median_duration_s": "number", "max_duration_s": "number", "last_start": "ISO 8601" }
```

## Failure shape

```json
{ "status": "error", "error_category": "auth | rate_limit | upstream_5xx | validation | permission | unknown", "retryable": true, "message": "human-readable, no secrets, no raw bodies" }
```

An empty lookup's 404 is excluded from `log_error_on_status` and branched on; it is not a failure.

## Credentials and Resources — by reference

| Kind | Name | Type | `allowed_hosts` | Workbench access | Must exist in |
|---|---|---|---|---|---|
| Credential | `tines_api_readonly` | Text — Viewer-role team API key (read-only by role — VERIFY #18) | the tenant host | off | dev team + prod team |

## Monitoring

- Story-level **Notify when any action fails**: on (`monitor_failures: true`), set by `ship.yml`; recipients from `../_manifest.yaml`.
- Event-driven (called, never scheduled): no own watchdog; the sweep's watchdog and its `mcp_health` signal cover silence.
- Event retention raised to 30 days [BY HAND]; `locked: true` in prod (`../_manifest.yaml` `locked_slugs`); never-touch by the `^\[OPS\]` name pattern.

## Verify in your tenant before presenting

- `tines_api_readonly` is read-only by role — **VERIFY #18** (attempt a write, expect a 404).
- Whether a Send to Story sub-story used as a tool counts as a flow — **VERIFY #13**.
- Whether `end_time` is set mid-run — **VERIFY #16**.
- Every VERIFY item still open in `../../docs/VERIFY.md` is a sentence you cannot say as fact.
