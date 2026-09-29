---
story_key: example-enrich-ip
iteration: 1
---

# Design brief — `example-enrich-ip` · [SEC] 01 · Enrich IP (sub)

> **Worked example — illustrative.** Placeholders only; see the note at the top of `intake.md`. The design follows the scaffold's own `stories/example-enrich-ip/README.md`, which is the long-form description of this story.

_Template: `storyline/templates/design-brief.md` · Phase: 02 design · Written by `story-architect` through `./scripts/storyline apply` on branch `design/example-enrich-ip` · Gates out: G1 (`./scripts/storyline ready`: pass), then G2 (the design PR merged by a tines-builders CODEOWNER who was not its author)._

## 1. What we are building and why

One sub-story every caller shares: it takes one IPv4 address, refuses it if it sits in a protected range, answers from a 24-hour cache when it can, otherwise looks it up in VirusTotal and AbuseIPDB, and returns **one verdict with a score, the sources and a one-sentence summary**. Discovery chose to read Library seed 87626 for its vendor templates and to build from the repository's existing design.

## 2. The rung, and why not lower

Rung **2** of `docs/01-decision-rules.md` — a Send to Story sub-story with a timeout.

- Rung 1 (an HTTP Request action or template in each caller) would repeat the guard, both lookups, the pacing and the cache in every story, agent and Mode 4 server that needs a verdict, and the copies would drift.

No higher rung is needed: combining two scores into a verdict is a formula, not a judgement, so there is no AI Agent action and no model in the loop.

## 3. Shape

`receive_ip` (Webhook, the Send to Story entry) → `normalize` (`DEFAULT()` on `ip`, `requester`, `source`) → `is_valid_input` / `is_invalid_input` → `is_protected` / `is_not_protected` (the guard **before any lookup**, against `never_block`) → `check_cache` → `cache_hit` / `cache_miss` → `lookup_virustotal` → `lookup_abuseipdb` (sequential, hardened) → `verdict` → `write_cache` (24-hour TTL) → `result` (exactly four fields). Exits: `result`, `refused`, `error`. A Note on the canvas carries the purpose and the mode badge **sub-story**.

## 4. Risks, shadow mode, data

- **Side effects:** none outside its own `ioc_cache` Records. It never blocks, never writes to a security tool, never returns raw vendor payloads. So it does **not** start in shadow, and G6 does not apply.
- **Data:** `internal`. The requester's email is for the audit Record only; it is never echoed in `result`.
- **Untrusted input:** `ip` is validated by pattern before any use; nothing in the payload reaches a prompt (there is none).

## 5. Cost

`./scripts/storyline estimate example-enrich-ip`: **0 credits** — no AI Agent action. Vendor free-tier quotas are the real limit; the cache and sequential lookups with `retry_on_status` 429 protect them.

## 6. Spikes

None. Two VERIFY items touch this design but do not block it: the argument shape of `IN_CIDR` against an array Resource, and the export key names of the HTTP hardening (scaffold VERIFY #8). The builder confirms both from the first real export; the story's README lists them under "Verify in your tenant before presenting".

## 7. Definition of Ready

- [x] The contract block below validates.
- [x] At least one acceptance criterion is testable from a run's events, logs or result (all five are).
- [x] Every criterion maps to at least one case in `evals/cases.yaml`, and there are two should-not cases.
- [x] `virustotal_api`, `abuseipdb_api` and `never_block` are named in `stories/example-enrich-ip/story.meta.yaml`.
- [x] No AI Agent action, so no `budget_ref` is needed.
- [x] `stories/_manifest.yaml` has `example-enrich-ip` with `new: true`.
- [x] The needs fit the tenant: Records for `ioc_cache`; Send to Story on every plan.
- [x] Every changed path is inside the design touch set.
- [x] `./scripts/storyline estimate example-enrich-ip --check` passes.
- [x] The GB check passes (0 credits; the verify-phase eval-run cost is 0 — no model-graded case).
- [x] (G2) Rung 2 is the lowest that works; out of scope is explicit; no production write.

## 8. Contract

```json story-contract
{
  "contract_version": 1,
  "story_key": "example-enrich-ip",
  "title": "[SEC] 01 · Enrich IP (sub)",
  "summary": "Takes one IPv4 address, refuses protected ranges before any lookup, answers from a 24-hour cache when it can, otherwise asks two reputation services, and returns one verdict with a score, the sources consulted and a one-sentence summary.",
  "tier": "production",
  "mode": {
    "rung": 2,
    "value": "sub-story",
    "why_not_lower": [
      "Rung 1 (an HTTP Request in each caller) would repeat the guard, both lookups, the pacing and the cache in every caller, and the copies would drift."
    ]
  },
  "acceptance_criteria": [
    { "id": "AC-1", "given": "an IPv4 address outside every never_block range and not in the cache", "when": "it arrives at receive_ip", "then": "both lookups run once, write_cache runs, and result emits verdict, score, sources and summary" },
    { "id": "AC-2", "given": "the same address was looked up less than 24 hours ago", "when": "it arrives again", "then": "result answers from ioc_cache with sources [\"cache\"], and neither lookup nor write_cache runs" },
    { "id": "AC-3", "given": "an address inside a never_block range", "when": "it arrives", "then": "refused emits status refused with reason protected range, and no cache read or lookup runs" },
    { "id": "AC-4", "given": "a value that is not an IPv4 address", "when": "it arrives", "then": "error emits error_category validation with retryable false, and no lookup runs" },
    { "id": "AC-5", "given": "any successful run", "when": "result emits", "then": "it carries exactly verdict, score, sources and summary: no vendor payload and no requester email" }
  ],
  "entry": {
    "type": "send_to_story",
    "action": "receive_ip",
    "fields": [
      { "name": "ip", "required": true, "description": "one IPv4 address" },
      { "name": "requester", "required": false, "default": "unknown", "description": "for the audit Record only" },
      { "name": "source", "required": false, "default": "unknown" }
    ]
  },
  "actions_outline": [
    { "name": "receive_ip", "type": "Webhook", "does": "the Send to Story entry; no-events watchdog at 7,200 s" },
    { "name": "normalize", "type": "Event Transform", "does": "message-only; DEFAULT() on ip, requester and source" },
    { "name": "is_valid_input", "type": "Trigger", "does": "passes a well-formed IPv4 address" },
    { "name": "is_invalid_input", "type": "Trigger", "does": "the complement; to error with validation", "on_failure": "error" },
    { "name": "is_protected", "type": "Trigger", "does": "the address is inside a never_block range; to refused" },
    { "name": "is_not_protected", "type": "Trigger", "does": "the complement; continues to the cache" },
    { "name": "check_cache", "type": "Records", "does": "an ioc_cache record for this ip whose expires_at is in the future", "on_failure": "error" },
    { "name": "cache_hit", "type": "Trigger", "does": "a fresh record exists; to result with sources cache" },
    { "name": "cache_miss", "type": "Trigger", "does": "no fresh record; to the lookups" },
    { "name": "lookup_virustotal", "type": "HTTP Request", "does": "the VirusTotal IP report template, credential virustotal_api, hardened", "on_failure": "error" },
    { "name": "lookup_abuseipdb", "type": "HTTP Request", "does": "the AbuseIPDB check template, credential abuseipdb_api, hardened, after lookup_virustotal", "on_failure": "error" },
    { "name": "verdict", "type": "Event Transform", "does": "message-only; score and verdict from both lookups with DEFAULT() on every vendor field" },
    { "name": "write_cache", "type": "Records", "does": "writes the verdict to ioc_cache with a 24-hour expires_at", "on_failure": "error" },
    { "name": "result", "type": "Event Transform", "does": "message-only exit: exactly verdict, score, sources, summary" },
    { "name": "refused", "type": "Event Transform", "does": "message-only exit: status refused, reason protected range, ip" },
    { "name": "error", "type": "Event Transform", "does": "message-only exit: status error, error_category, retryable, message" }
  ],
  "credentials": ["virustotal_api", "abuseipdb_api"],
  "resources": ["never_block"],
  "records": ["ioc_cache"],
  "egress_hosts": ["<virustotal-api-host>", "<abuseipdb-api-host>"],
  "ai_agents": [],
  "tools_design": [],
  "access": {
    "page": { "level": "none" },
    "webhook": { "level": "secret", "reason": "The entry Webhook keeps its secret; callers reach it through Send to Story with team access. How the Webhook access level interacts with Send to Story is to be confirmed from the first export (VERIFY)." },
    "mcp_server": { "level": "none" }
  },
  "risk": { "side_effects": false, "shadow_mode": false, "data_sensitivity": "internal" },
  "out_of_scope": [
    "Blocking, isolating or writing to any security tool; callers decide what to do with the verdict",
    "IPv6 addresses",
    "Returning raw vendor payloads",
    "Exposing the story as a Mode 4 tool; ops-tools-server does that in its own story"
  ],
  "touch_set": ["storyline/work/example-enrich-ip/**", "stories/example-enrich-ip/**"],
  "cost_estimate": { "runs_per_day": 50, "credits_per_run_est": 0, "monthly_credits_est": 0, "provider": "none", "basis": "no AI Agent action" },
  "qa_guidance": "After eval-run, open the story's recent runs in the dev team. On the happy path, confirm lookup_virustotal and lookup_abuseipdb each fired once and in that order, that write_cache wrote one ioc_cache record expiring 24 hours later, and that result carries exactly four fields with no requester email. On the refused case, confirm no Records or HTTP Request action fired at all."
}
```
