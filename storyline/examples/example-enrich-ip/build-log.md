# Build log — `example-enrich-ip` · attempt 1

> **Worked example — illustrative.** Placeholders only; see the note at the top of `intake.md`. The story has not been built in a tenant; this shows the shape of a builder's report, not a real run.

_Template: `storyline/templates/build-log.md` · Phase: 03 build · Saved by `./scripts/storyline apply example-enrich-ip tines-builder -` from the builder's final report, **verbatim**. **Never parsed**: the phase exit is the check `build_evidence`, and G3 is the `gate_decision` event `/storyline-gate` recorded — not anything written here._

| | |
|---|---|
| Story | `example-enrich-ip` · `[SEC] 01 · Enrich IP (sub)` |
| Attempt | 1 (attempt 0 built the story; verify returned `changes_requested` with one major finding — see `events.jsonl`) |
| Branch | `story/example-enrich-ip/0000000` |
| Handoff | `/tines-build-story example-enrich-ip "Implement the contract in storyline/work/example-enrich-ip/design.md (contract v1). Acceptance = stories/example-enrich-ip/tests/expectations.yaml and the deterministic cases in storyline/work/example-enrich-ip/evals/cases.yaml. Out of scope: blocking or writing to any security tool; IPv6; raw vendor payloads; Mode 4 exposure. Credentials by name: virustotal_api, abuseipdb_api. First read .storyline/out/example-enrich-ip/rework-1.json; fix only the listed findings; each finding carries a suggested_prompt."` |
| Rework package | `.storyline/out/example-enrich-ip/rework-1.json` (local) — 1 finding: `http_retry_bounds` on `lookup_abuseipdb` |
| Build start event | 2026-10-05T13:00:00Z |

## The builder's report (verbatim, below this line)

**Story:** `[SEC] 01 · Enrich IP (sub)` in the dev team, dev id `0` (recorded in `stories/_manifest.yaml` during attempt 0).

**What I saw first.** 16 actions and the Note, as built in attempt 0. `lookup_abuseipdb` had retry on status `429, 500-599` and emit failure event Always, but its retries were still at the default. `lookup_virustotal` was already at 6. Credentials referenced by name: `virustotal_api`, `abuseipdb_api`; Resource: `never_block`; Record type: `ioc_cache`.

**Plan (approved; recorded as G3 with `/storyline-gate example-enrich-ip G3 approve`):**
1. In `[SEC] 01 · Enrich IP (sub)`, on the HTTP Request action `lookup_abuseipdb`, set retries to 6. Nothing else changes.

**Changed:** `lookup_abuseipdb` (HTTP Request) — retries 6.

**Validate:** no errors, no warnings.

**Test event:** `stories/example-enrich-ip/tests/sample-event.json` → `receive_ip`. 11 actions fired (minimum 10); no error logs on the listed actions; `result` carried exactly `verdict, score, sources, summary`; `error`, `refused` and `cache_hit` did not fire. Variants: `cached_second_run`, `refused_private_range` and `invalid_input` met their expectations.

**By hand (unchanged since attempt 0; none new):**
- [x] Send to Story access for the team; timeout 25 s at story level
- [x] `ioc_cache` Record type in the dev team
- [ ] `ioc_cache`, `virustotal_api`, `abuseipdb_api`, `never_block` in the **prod** team before the first ship
- [ ] Event retention 30 days in prod; change control on for the new prod story after the first ship

**Export:** `./scripts/tines export example-enrich-ip` → `stories/example-enrich-ip/story.json`; `./scripts/lint-story.sh` clean; `./scripts/diff-story.sh … --against HEAD`: one change, `lookup_abuseipdb` retries default → 6. `story.meta.yaml` `exported_from.at` = 2026-10-05T13:35:00Z.

**Commit:** `story(example-enrich-ip): bound lookup_abuseipdb retries at 6` on `story/example-enrich-ip/0000000`.

Run `/tines-review` from a fresh session before opening the PR.
