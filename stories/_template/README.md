# `[PREFIX] NN · Verb noun (sub)` — <one-line summary>

_Copy this folder to `stories/<slug>/`, replace every `<placeholder>`, delete this italic line. Sections are fixed (DESIGN.md §3.6); leave a section in with "n/a" rather than removing it, so reviewers can rely on the shape._

**Slug:** `<slug>` · **Mode badge:** `none | sub-story | mode-3-agent | mode-4-server` (which of the four MCP surfaces this story serves, or none) · **Tier:** `production | internal | ops | seed` · **Owner:** `<team role>` (a role, never a person) · **Descends from:** Library `<id>` (or "—")

## Purpose

One paragraph. This paragraph is copied onto the canvas as the Note (with the mode badge), so write it to be read there too: what comes in, what goes out, what it never does.

## Mode badge

- **none** — a plain story; no MCP surface.
- **sub-story** — Send to Story enabled; callable from other stories, attachable to a Mode 3 AI Agent action as a Send to Story tool (with a Timeout Duration), exposable through a Mode 4 MCP server action as one tool.
- **mode-3-agent** — the story contains an AI Agent action that calls tools (Tines tools, at most one MCP connection).
- **mode-4-server** — the story contains an MCP server action at `https://<your-tenant>.tines.com/mcp/<mcp-path>`.

State the badge and, for a sub-story, the three surfaces it may be used from.

## Entry and expected input

| Entry | Action name | Expected fields | Notes |
|---|---|---|---|
| Webhook / Send to Story / schedule | `<entry action>` | `field_a` (string, required) · `field_b` (string, optional, default `""`) | `normalize` wraps every field in `DEFAULT()` so a missing field never breaks a formula |

## Output — the `result` shape

Sub-stories finish on a message-only Event Transform named `result` emitting 3–5 fields. Document every field with its type; this text is the only "output schema" a tool built on this story will ever have.

```json
{ "verdict": "string — allowed values", "score": "integer 0–100", "sources": "array of strings", "summary": "string, one sentence" }
```

## Failure shape

Every failure branch ends on a message-only Event Transform named `error`:

```json
{ "status": "error", "error_category": "auth | rate_limit | upstream_5xx | validation | permission | unknown", "retryable": true, "message": "human-readable, no secrets, no raw bodies" }
```

Expected non-2xx responses (an empty lookup's 404, a lock's 422) are excluded from `log_error_on_status` and branched on with a Trigger; they are not failures.

## Credentials and Resources — by reference

| Kind | Name | Type | `allowed_hosts` | Workbench access | Must exist in |
|---|---|---|---|---|---|
| Credential | `<credential_name>` | Text / OAuth / … | `<vendor host>` | off for pipeline keys | dev team + prod team |
| Resource | `<resource_name>` | JSON | — | — | dev team + prod team |
| Record type | `<record_type>` | fields listed in `records/record-types.md` | — | — | created [BY HAND] |

Values never appear here, in `story.json`, in tests or in samples. `story.meta.yaml` lists the same names; the reviewer cross-checks.

## Monitoring

- Story-level **Notify when any action fails**: on (`monitor_failures: true`), set by `ship.yml`.
- Recipients: from `_manifest.yaml` (the ops router webhook + the email DL), applied on ship; cleared on export.
- No-events watchdog: `<entry or scheduled action>` at `<seconds>` (≈ 2× the expected interval).
- Event retention: `keep_events_for` ≥ 30 days for `tier: production` [BY HAND above 7 days].
- AI Agent actions: token alert on the Status tab — Notify at `<n>`, Disable action at `<m>` (`daily`), recorded in `story.meta.yaml: ai.agents[].token_alert`.

## HTTP hardening

Every HTTP Request action: `retry_on_status` `[429, 500-599]`; retries 5–8 (never the default 25 ≈ 3 h 20 min); `emit_failure_event` **Always**; `log_error_if` for 200-with-error bodies; failure path → `error` → the dead-letter Record; expected non-2xx excluded. Export key names for the retry count, `emit_failure_event` and `log_error_*` are VERIFY until read from a real export.

## Test event

`tests/sample-event.json` is posted to `<entry action>` (`?draft=<name>` when change control is on); `tests/expectations.yaml` is asserted against the run's events (`GET /api/v1/stories/{id}/runs` and `/runs/{guid}`). Documentation-range values only.

## Runbook — when the router pages for this story

| Signal (from `[OPS] 01`) | Likely cause | First check | Fix path |
|---|---|---|---|
| `<action>` failing with 401/403 | credential expired or wrong team | credential `expires_at`, `allowed_hosts` | owner rotates the credential [BY HAND]; no story change |
| `<action>` failing with 429 | vendor pacing | `GET /api/v1/actions/{id}/logs?level=4` | throttle or cache — `/tines-build-story` change through the normal PR path |
| no events on `<entry>` for 2× interval | upstream silent | the source system; the webhook URL in the source | fix upstream; if the story is at fault, PR |
| the story itself is wrong | shipped change | `git log --oneline -- stories/<slug>/story.json` | `/tines-rollback <slug> previous` |

## Verify in your tenant before presenting

- <the VERIFY items this story depends on, each also listed in `docs/VERIFY.md`>

## Change log

| Short sha | Date | What changed | Change request |
|---|---|---|---|
| `<sha>` | `<YYYY-MM-DD>` | initial build in the dev team | `<id>` |
