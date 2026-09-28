# `[OPS] 11 · Get error logs (sub)` — the `ops_get_error_logs` lookup, shared by the sweep and the Mode 4 server

**Slug:** `ops-get-error-logs` · **Mode badge:** `sub-story` · **Tier:** `ops` · **Owner:** ops (CODEOWNERS: security-platform) · **Descends from:** —

> **Not built yet.** This folder holds the contract, the meta file and the manifest entry so lint, review, ship and drift see this story before `[OPS] 10 · Monitor story health and credits` ships. Build it in the dev team with `/tines-build-story ops-get-error-logs "Build [OPS] 11 · Get error logs (sub) from stories/ops-get-error-logs/README.md"` (the owner sets `TINES_ALLOW_OPS_BUILD=1`), record its dev id in `../_manifest.yaml`, then `/tines-export ops-get-error-logs`. The contract, the verbatim tool description and the build order live in `../ops-story-health-monitor/agent/tools.md` — this README restates only what the folder needs.

## Purpose

One read-only lookup, `ops_get_error_logs`, used as a Send to Story tool by the sweep's `triage` agent (Mode 3) and exposed by `[OPS] 20 · Ops tools (MCP server)` (Mode 4). It wraps `GET /api/v1/actions/{id}/logs?level=4&per_page=<limit>` with the credential `tines_api_readonly` and returns 3–5 fields, never a body. Log messages are third-party free text and can echo tokens from a vendor's error body. Every sample message is passed through the secret-pattern scrub (the `scripts/tines_common.py` `SECRET_PATTERNS` mirror the monitor's `scrub` uses) and truncated **inside** this sub-story; with `include_messages: false` — which the Mode 4 `ops_get_error_logs` tool fixes — no message text is returned at all, only categories and log ids.

## Mode badge

`sub-story` — Send to Story enabled (team access, Timeout Duration 20 s wherever it is used as a tool); used from the Mode 3 `triage` agent in `ops-story-health-monitor` and the Mode 4 `ops-tools-server`.

## Entry and expected input

| Entry | Action name | Expected fields | Notes |
|---|---|---|---|
| Send to Story (a Webhook entry, team access) | named at build | `action_id` (integer, required) · `limit` (integer, default 20, max 100) · `include_messages` (boolean, default true — never model-supplied: the Mode 4 tool fixes it to `false`) | `normalize` wraps every field in `DEFAULT()`; `is_valid_input` / `is_invalid_input` Triggers before the API call |

## Output — the `result` shape

```json
{ "count": "integer — level-4 logs in the window", "last_at": "ISO 8601 — the newest one", "categories": "array — auth | rate_limit | upstream_5xx | timeout | validation | unknown", "log_ids": "array — ids of up to five of those logs", "sample_messages": "array — up to five messages, <= 200 characters, secret-looking spans redacted; ONLY when include_messages is true" }
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
- Fixed inputs on a Send to Story tool (`include_messages: false` on the Mode 4 copy) — **VERIFY E10**; the fallback is a Custom tool (`../ops-tools-server/README.md`).
- The log message format and the `categories` mapping — read one real level-4 log before trusting the classification.
- Every VERIFY item still open in `../../docs/VERIFY.md` is a sentence you cannot say as fact.
