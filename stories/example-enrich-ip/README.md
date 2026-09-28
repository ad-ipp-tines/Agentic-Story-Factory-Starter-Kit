# `[SEC] 01 · Enrich IP (sub)` — the worked example every builder copies

**Slug:** `example-enrich-ip` · **Mode badge:** **sub-story** — callable from any story via Send to Story, attachable to a Mode 3 AI Agent action as a Send to Story tool (with a Timeout Duration), and exposed through the Mode 4 `ops-tools-server` as one tool · **Tier:** production · **Owner:** security-automation (a role) · **Descends from:** Library **87626** (Analyze an IP in many services at once) · **Spec:** `../../DESIGN.md` §3.6

> `story.json` in this folder is a **labelled SKELETON**: the actions, names, types and links the build produces, with placeholder GUIDs. The first `/tines-export example-enrich-ip` replaces it with the real export. Never edit it by hand; change the story through the Tines Stories MCP server and export again.

## Purpose

Take one IP address, refuse it if it sits in a protected range, answer from the cache if the verdict is fresh, otherwise look it up in two reputation services, and return **one verdict with a score, the sources consulted and a one-sentence summary**. It never blocks, never writes to any security tool, and never returns raw vendor payloads: the caller — a story, an AI Agent action or an MCP client — gets 3–5 fields and nothing else. (This paragraph is the on-canvas Note, with the mode badge.)

Why this is the worked example: it shows the whole sub-story contract in one small canvas — a guarded entry, `DEFAULT()` fallbacks, named credentials, paced free-tier lookups, a cache Record with a TTL, the `result` shape, the `error` shape, and HTTP hardening on every request — and it is the shape both the monitoring agent's tools (§5.4 of the root design) and the Mode 4 server's tools reuse.

## Contract

| | |
|---|---|
| **Entry** | Send to Story (the story's entry action is a Webhook named `receive_ip`; Send to Story is enabled at story level with team access) |
| **Input** | `{ "ip": "203.0.113.10", "requester": "builder@example.invalid", "source": "test" }` — `ip` required; `requester` and `source` optional (default `"unknown"`) |
| **Output** (`result`) | `{ "verdict": "clean \| suspicious \| malicious", "score": 0–100, "sources": ["virustotal", "abuseipdb", "cache"], "summary": "one sentence" }` |
| **Refused** (`refused`) | `{ "status": "refused", "reason": "protected range", "ip": "…" }` — returned **before any lookup** for anything in the `never_block` Resource |
| **Failure** (`error`) | `{ "status": "error", "error_category": "auth \| rate_limit \| upstream_5xx \| validation \| unknown", "retryable": true\|false, "message": "…" }` |
| **Timeout** | Story-level Send to Story timeout enabled at **25 s** — under the 30-second tool-response ceiling of a Mode 4 MCP server action, so the same story is safe to expose as a tool |
| **Tool description** (when attached as a tool) | "Looks up one IPv4 address in VirusTotal and AbuseIPDB and returns a single verdict. Refuses private and protected ranges without calling any service. Returns `{verdict, score, sources, summary}`; on failure `{status: error, error_category, retryable, message}`. Does not block, isolate or write anywhere. Example: `{\"ip\": \"203.0.113.10\"}`." |

The description is the API: tool responses carry no output schema, so the output shape lives in the description text.

## Storyboard walk-through — action by action

Indices are the `agents[]` order in `story.json`; links reference them by index, which is why the order is fixed.

| # | Action | Type (export) | What it does | Fields / formulas (sketch) | On failure |
|---|---|---|---|---|---|
| 0 | `receive_ip` | `Agents::WebhookAgent` | The Send to Story entry. Accepts the payload; no-events watchdog at 7,200 s. | `verbs: post`; `path` and `secret` are set by Tines on import | — |
| 1 | `normalize` | `Agents::EventTransformationAgent` (message-only) | Wraps every input in `DEFAULT()` so a missing field never breaks a formula downstream. | `ip: =DEFAULT(receive_ip.body.ip, "")` · `requester: =DEFAULT(receive_ip.body.requester, "unknown")` · `source: =DEFAULT(receive_ip.body.source, "unknown")` | — |
| 2 | `is_valid_input` | `Agents::TriggerAgent` | Passes only a well-formed IPv4 address. | rule `regex` on `normalize.ip`, pattern `^(\d{1,3}\.){3}\d{1,3}$` | — |
| 3 | `is_invalid_input` | `Agents::TriggerAgent` | The complement of #2 → `error` with `error_category: validation`, `retryable: false`. | rule type for "does not match regex" — **VERIFY** the export value | → 15 |
| 4 | `is_protected` | `Agents::TriggerAgent` | The guard **before any lookup**: the IP is inside a CIDR listed in the `never_block` Resource. | `=IN_CIDR(normalize.ip, RESOURCE.never_block)` is `true` (argument shape of `IN_CIDR` against an array — **VERIFY**; loop with `MAP` if it takes one CIDR) | → 14 |
| 5 | `is_not_protected` | `Agents::TriggerAgent` | The complement of #4. | same expression is `false` | — |
| 6 | `check_cache` | Records action — export type **VERIFY** | Looks for an `ioc_cache` record for this IP whose `expires_at` is in the future. | filter `ip == normalize.ip` and `expires_at > now` | → 15 |
| 7 | `cache_hit` | `Agents::TriggerAgent` | A fresh record exists → straight to `result` (sources = `["cache"]`). | records count `> 0` (Records action output path **VERIFY**) | — |
| 8 | `cache_miss` | `Agents::TriggerAgent` | No fresh record → lookups. | records count `== 0` | — |
| 9 | `lookup_virustotal` | `Agents::HTTPRequestAgent` | The VirusTotal template from the Templates panel, credential `virustotal_api`. Paced to the free tier; hardened (below). | response field of interest: the malicious count in the last-analysis stats — confirm the template's field names from its output | → 15 |
| 10 | `lookup_abuseipdb` | `Agents::HTTPRequestAgent` | The AbuseIPDB template, credential `abuseipdb_api`. Sequential after #9 so one branch carries both results (no fan-in needed). | response field of interest: the abuse confidence score — confirm from the template's output | → 15 |
| 11 | `verdict` | `Agents::EventTransformationAgent` (message-only) | Combines the two lookups into a score and a verdict with `DEFAULT()` on every vendor field. | `score: =MAX(DEFAULT(<abuse confidence>, 0), DEFAULT(<vt malicious>, 0) * 10)` · `verdict: =IF(score >= 70, "malicious", IF(score >= 30, "suspicious", "clean"))` · `sources: ["virustotal", "abuseipdb"]` · `summary` | — |
| 12 | `write_cache` | Records action — export type **VERIFY** | Writes `{ip, verdict, score, sources, summary, expires_at}` to `ioc_cache` with a 24-hour TTL. | `expires_at = now + 86400 s` | → 15 |
| 13 | `result` | `Agents::EventTransformationAgent` (message-only) | **The exit.** Exactly four fields; from the cache path or the lookup path (`DEFAULT()` picks whichever exists). | `verdict`, `score`, `sources`, `summary` | — |
| 14 | `refused` | `Agents::EventTransformationAgent` (message-only) | Exit for protected ranges. | `{status: "refused", reason: "protected range", ip}` | — |
| 15 | `error` | `Agents::EventTransformationAgent` (message-only) | Exit for every failure branch; the structured shape callers and agents can act on. Also writes the dead-letter reference in production (`ops_dead_letter`, never the body). | `{status: "error", error_category, retryable, message}` | — |
| — | Note | `diagram_notes[]` | The Purpose paragraph and the mode badge, on the canvas. | — | — |

Exit actions (`exit_agent_guids`): `result`, `refused`, `error`. Entry action (`entry_agent_guid`): `receive_ip`.

## The result transform

`result` is a message-only Event Transform. Its payload is the entire tool response, so it is deliberately small and stable:

```
verdict:  =DEFAULT(verdict.verdict, <cached record>.verdict)
score:    =DEFAULT(verdict.score,   <cached record>.score)
sources:  =DEFAULT(verdict.sources, ["cache"])
summary:  =DEFAULT(verdict.summary, <cached record>.summary)
```

Rules the reviewer enforces on it: named exactly `result`; message-only mode; 3–5 fields; no raw vendor body, no credential reference, no requester email echoed back (the requester is for the audit Record, not the response).

## Credentials and Resources — by reference

| Kind | Name | Type | `allowed_hosts` | Workbench access | Exists in |
|---|---|---|---|---|---|
| Credential | `virustotal_api` | Text | the VirusTotal API host | off | dev team + prod team (test-mode value in dev) |
| Credential | `abuseipdb_api` | Text | the AbuseIPDB API host | off | dev team + prod team |
| Resource | `never_block` | JSON array of CIDRs | — | — | dev team + prod team — e.g. `["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16"]`. Keep the documentation ranges (`203.0.113.0/24`, `198.51.100.0/24`) **out** of it so the test event is not refused. |
| Record type | `ioc_cache` | fields: `ip` (text), `verdict` (text), `score` (number), `sources` (json), `summary` (text), `expires_at` (datetime), `requester` (text) | — | — | created [BY HAND] in each team |

No value appears in this folder. The export references them as `<<CREDENTIAL.virustotal_api>>`, `<<CREDENTIAL.abuseipdb_api>>`, `<<RESOURCE.never_block>>` (the `<< >>` form is what observed exports use).

## HTTP hardening (actions 9 and 10)

| Setting | Value | Why | Export key |
|---|---|---|---|
| Retry on status | `[429, 500-599]` | vendor pacing and transient upstream errors | `retry_on_status` (observed as an array of strings, e.g. `["429"]`; how a range is expressed — **VERIFY**) |
| Retries | 6 | the default of 25 ≈ 3 h 20 min of silent retrying | **VERIFY** |
| Emit failure event | **Always** | the default "Error response only" misses timeouts and DNS failures | **VERIFY** |
| Log error if | the vendor's 200-with-error body shape | a 200 with `"error"` in the body is still a failure | **VERIFY** |
| Failure path | → `error` | the caller always gets a structured answer | link representation **VERIFY** |
| Excluded from error logs | an empty lookup's 404 (if the vendor returns one) | not a failure; branched on in `verdict` | **VERIFY** |

Until the first real export is read, `scripts/lint_story.py` (behind the `lint-story.sh` shim) tags these keys VERIFY and reports them as warnings or info, never errors. When an export confirms one, set it in `lint_story.py` — the key names are hard-coded there — and change the rule's `key:` in `policies/lint-rules.yml`.

## Monitoring

- Story-level "Notify when any action fails": on (set on the ship draft by `ship.yml`); recipients = the ops router webhook + the email DL, from `_manifest.yaml`.
- No-events watchdog on `receive_ip` at **7,200 s** (this story is called on demand, so the watchdog is a coarse "nobody has called us for two hours" signal; tune per caller).
- `keep_events_for` = 30 days (`2592000` s) in prod [BY HAND above 7 days].
- What the router will page for and what to do: see the runbook.

## Cost and pacing

- No AI Agent action, no AI credits, no model in the loop — this is the "simplest first" rung of the decision ladder (`docs/01-decision-rules.md`).
- Free-tier vendor limits are respected twice: sequential lookups with `retry_on_status` 429 and a low retry count, and the `ioc_cache` Record (24 h TTL) so a rehearsal or a chatty agent never burns a quota on the same IP twice.
- Counts as **one flow**. When attached as a Send to Story tool to an agent or a Mode 4 server it is the same flow — whether sub-stories used as tools count separately is **VERIFY** with the account team.

## Tests

- `tests/sample-event.json` → `receive_ip` (`?draft=<name>` when change control is on). Expected: `normalize`, `is_valid_input`, `is_not_protected`, `check_cache`, `cache_miss`, both lookups, `verdict`, `write_cache`, `result` fire; `error` and `refused` do not; `result` carries exactly `verdict, score, sources, summary`.
- Second run of the same sample within 24 h: `cache_hit` → `result` with `sources: ["cache"]` and no lookup events (the pacing proof).
- Refused variant (in `tests/expectations.yaml`): `{"ip": "10.0.0.5"}` → `refused` fires, no lookup fires.
- Invalid variant: `{"ip": "not-an-ip"}` → `error` with `error_category: validation`.

## Build prompts — Mode 2, through the Tines Stories MCP server

Run `/tines-build-story example-enrich-ip "Enrich one IP and return a verdict"` from the dev team with `TINES_ENV=dev`. The skill delegates to the `tines-builder` subagent, which works one story at a time and ends every step with **Validate**. The prompts below are the pack it uses (`.claude/skills/tines-build-story/references/prompt-pack.md`), instantiated for this story. Each prompt names the story, the action type, the action name and the field names.

1. **Create.** "In the Tines team `<dev team>`, folder `<manifest folder>`, create a new story named `[SEC] 01 · Enrich IP (sub)`. Add a Webhook action named `receive_ip` as the entry that expects a JSON body with the fields `ip`, `requester`, `source`. Then add an Event Transform in message-only mode named `normalize` that outputs `{ip: DEFAULT(receive_ip.body.ip, ""), requester: DEFAULT(receive_ip.body.requester, "unknown"), source: DEFAULT(receive_ip.body.source, "unknown")}`. Then validate."
2. **Guard.** "In `[SEC] 01 · Enrich IP (sub)`, after `normalize` add two Trigger actions: `is_valid_input` passing when `normalize.ip` matches the regex `^(\d{1,3}\.){3}\d{1,3}$`, and `is_invalid_input` passing when it does not. After `is_valid_input` add two more Triggers: `is_protected` passing when `IN_CIDR(normalize.ip, RESOURCE.never_block)` is true, and `is_not_protected` passing when it is false. Then validate."
3. **Cache.** "In `[SEC] 01 · Enrich IP (sub)`, after `is_not_protected` add a Records action named `check_cache` that searches the `ioc_cache` record type for `ip` equal to `normalize.ip` and `expires_at` later than now. Add a Trigger `cache_hit` when at least one record is returned and a Trigger `cache_miss` when none is. Then validate."
4. **Integrate.** "In `[SEC] 01 · Enrich IP (sub)`, after `cache_miss` add the VirusTotal IP report template as an HTTP Request action named `lookup_virustotal` using the credential named `virustotal_api` from this team, for the IP `normalize.ip`. After it add the AbuseIPDB check template as an HTTP Request action named `lookup_abuseipdb` using the credential named `abuseipdb_api`, for the same IP. Then validate."
5. **Verdict.** "In `[SEC] 01 · Enrich IP (sub)`, after `lookup_abuseipdb` add a message-only Event Transform named `verdict` that outputs `score` as the maximum of the AbuseIPDB confidence score (default 0) and ten times the VirusTotal malicious count (default 0), `verdict` as `malicious` at 70 or above, `suspicious` at 30 or above, otherwise `clean`, `sources` as `["virustotal", "abuseipdb"]`, and `summary` as one sentence naming the IP, the verdict and the score. Use `DEFAULT()` on every vendor field. Then add a Records action `write_cache` that creates an `ioc_cache` record with `ip, verdict, score, sources, summary, requester` and `expires_at` 24 hours from now. Then validate."
6. **Finish.** "In `[SEC] 01 · Enrich IP (sub)`, add a final message-only Event Transform named `result` emitting exactly `{verdict, score, sources, summary}`, reached from both `write_cache` and `cache_hit` (from the cache path take the fields from the cached record and set `sources` to `["cache"]`). Add a message-only Event Transform named `refused` after `is_protected` emitting `{status: "refused", reason: "protected range", ip: normalize.ip}`. Add a message-only Event Transform named `error` emitting `{status: "error", error_category, retryable, message}` and connect `is_invalid_input` to it with `error_category: "validation"` and `retryable: false`. Set `result`, `refused` and `error` as the story's exit actions. Then validate."
7. **Harden.** "In `[SEC] 01 · Enrich IP (sub)`, on `lookup_virustotal` and `lookup_abuseipdb` set retry on status to `429` and `500-599`, retries to 6, emit failure event to Always, and connect each action's failure path to `error` with `error_category` derived from the status (`401`/`403` → `auth`, `429` → `rate_limit`, `5xx` → `upstream_5xx`, otherwise `unknown`) and `retryable` true only for `rate_limit` and `upstream_5xx`. Then validate."
8. **Note.** "In `[SEC] 01 · Enrich IP (sub)`, add a Note to the canvas with the Purpose paragraph from this README and the line `Mode badge: sub-story`. Then validate."
9. **Test.** The skill posts `tests/sample-event.json` to `receive_ip` and compares the run with `tests/expectations.yaml`.
10. **Export** is the script, not the editor: `/tines-export example-enrich-ip`.

Correction habits (from the prompt pack): a wrong reference → "the payload arrives at `receive_ip`'s body; fix the reference"; "credential not found" → wrong team or a different name, fix by hand once; two failures on one issue → clear and restart with a better prompt.

## By hand — what the Tines Stories MCP server cannot do

- Enable **Send to Story** access for the team on this story (story settings) and confirm `receive_ip` is the entry and `result`/`refused`/`error` the exits.
- Create the `ioc_cache` Record type (whether `/mcp` can create Record types is **VERIFY**).
- Create `virustotal_api` and `abuseipdb_api` (Text credentials with `allowed_hosts`, Workbench access off) and the `never_block` Resource in **both** teams under these exact names.
- Raise event retention to 30 days; turn change control on if the story is new.
- Set the Send to Story timeout (25 s) at story level.

## Runbook — when `[OPS] 01` pages for this story

| Signal | Likely cause | First check | Fix path |
|---|---|---|---|
| `lookup_virustotal` / `lookup_abuseipdb` 401/403 | credential expired or missing in this team | `expires_at`, `allowed_hosts`, team | owner rotates [BY HAND]; no story change |
| 429 persisting past retries | free-tier quota | `GET /api/v1/actions/{id}/logs?level=4`; cache hit ratio in `ioc_cache` | raise the cache TTL or pace callers — PR through the normal path |
| `check_cache` / `write_cache` failing | Record type missing or renamed in this team | the Record type in the team | create/rename [BY HAND]; then re-run |
| no events on `receive_ip` for 2 h | no caller, or a caller's story is down | the calling stories' live activity | usually nothing; tune the watchdog per caller |
| verdicts look wrong after a ship | shipped change | `git log --oneline -- stories/example-enrich-ip/story.json` | `/tines-rollback example-enrich-ip previous` |

## Verify in your tenant before presenting

- The export key names for the retry count, `emit_failure_event`, `log_error_if`, the failure-path link, the Records action type and its output path, and the "does not match regex" Trigger rule type.
- `IN_CIDR` argument shape against an array Resource.
- Library 87626 as the seed: import it into the Seeds folder and confirm its vendor set and template field names before building.
- Whether a Send to Story sub-story used as a tool counts as an additional flow.
- Whether `/mcp` edits in the dev team land as change-control drafts (and whether the test event needs `?draft=<name>`).

## Change log

| Short sha | Date | What changed | Change request |
|---|---|---|---|
| — | 2026-09-24 | design + skeleton written; not yet built in a tenant | — |
