---
story_key: example-enrich-ip
window: { from: "2026-10-06T11:00:00Z", to: "2026-10-13T11:00:00Z" }
trigger: retro_due
keep_or_change: change
eval_cases_requested: [out-of-range-octet-is-validation-error]
skill_suggestions: []
cost_variance: { estimate: 0, actual: 0, ratio: 0 }
curated: true
closed: true
---

# Retro — `example-enrich-ip` · 2026-10-06 → 2026-10-13

> **Worked example — illustrative.** Placeholders only; see the note at the top of `intake.md`. Record ids are `0`; counts are made up to show the shape.

_Template: `sdlc/templates/retro.md` · Phase: 07 improve · Trigger: retro due, 7 days after live, detected by `[KIT] 00` section D (D9) · Drafted by `retro_writer` (Tines-side, tool-less) from `ops_findings`, `ops_alerts`, `sdlc_events` and the credit ledger; brought into git by the tracker PR; completed by the owner (security-automation) on `improve/example-enrich-ip`._

## What happened

- The story ran on every call from its first callers; no high or critical finding in the window. — `ops_findings` (none of severity high or critical)
- A handful of runs ended in `error` with `error_category: unknown` after a vendor rejected the address. Each input was an address with an octet above 255, which the pattern check in `is_valid_input` accepts. — `ops_findings:0`
- Two short bursts of 429 responses from the free tier on `lookup_abuseipdb` were absorbed by the retries and the cache; no run failed because of them. — `ops_findings:0`, `ops_alerts:0`
- No change request, rollback or break-glass in the window. — `sdlc_events`

## Failure modes

| Category | Count | Evidence |
|---|---|---|
| validation (a design gap: the pattern accepts octets above 255, so the error is reported as `unknown`, not `validation`) | 4 | `ops_findings:0` |
| rate_limit (absorbed; no failed run) | 2 | `ops_findings:0`, `ops_alerts:0` |

## Eval cases this retro asks for

| Proposed case id | Input (sanitised; ref) | Expected | From evidence |
|---|---|---|---|
| `out-of-range-octet-is-validation-error` | `{"ip": "999.0.0.1", "requester": "builder@example.invalid", "source": "test"}` | `is_invalid_input` and `error` fire with `error_category: validation`, `retryable: false`; no lookup fires | `ops_findings:0` |

_eval-curator added it as a `capability` case (it fails on the live design) and graduated `happy-path`, `refused-private-range` and `invalid-input` to `regression` — see `evals/cases.yaml`._

## Skill and prompt suggestions

None. The lesson — a pattern check does not validate IPv4 octet ranges — comes from one retro, and `skill-curator` never changes a skill in response to a single event. It is recorded here; if a second story shows it, it becomes a field-guide entry or a prompt-pack line.

## Cost

Estimate 0 credits, actual 0 (ratio 0): no AI Agent action. The free-tier quota, not credits, is this story's budget; the cache kept repeated lookups off it.

## Keep, change or retire

**`change`** — the guard must reject an out-of-range octet before any lookup leaves the tenant, and report it as `validation`. The next design iteration replaces the pattern in `is_valid_input` with a range check and keeps everything else. The rate-limit bursts need no change now; they are a note for the next G7.

The live story keeps running and monitored in production while iteration 2 is designed and built.

## Human completion

- [x] Every section above is complete and the evidence refs resolve.
- [x] `keep_or_change` confirmed: `change` (the draft proposed `change`).
- [x] `closed: true` set in the front matter.
