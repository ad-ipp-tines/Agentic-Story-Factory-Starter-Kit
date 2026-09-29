---
story_key: example-enrich-ip
title: "[SEC] 01 · Enrich IP (sub)"
owner: security-automation
source: kickoff_page
drafted_by: brief_writer
data_sensitivity: internal
simplest_rung: 2
candidate_seed_ids: [87626]
---

# Intake brief — `example-enrich-ip` · [SEC] 01 · Enrich IP (sub)

> **Worked example — illustrative.** This folder walks the scaffold's example story, `stories/example-enrich-ip/`, through every phase of the lifecycle. The story has not been built in a tenant: every id is `0`, every commit is `0000000`, every time, count and credit figure is a placeholder, and nothing here claims how Tines behaved. It lives in `storyline/examples/`, outside `apply`'s root and every touch set, so a real story #1 starts from clean templates. Read the files in this order: `intake.md` → `discovery.md` → `design.md` → `evals/cases.yaml` → `build-log.md` → `verify-report.json` → `ship.md` → `retro.md`, with `events.jsonl` beside them.

_Template: `storyline/templates/intake-brief.md` · Phase: 00 intake · Drafted by the Tines-side `brief_writer` from the kickoff Page's first use-case slot (starter story #1), brought into git by the first tracker PR, then decided at G0 on the `gate_decision` Page._

## Use case (as submitted)

> Starter story #1 from the kickoff Page: "Enrich an IP from several reputation services and return one verdict."

## Problem

Analysts and other stories check the same suspicious IPv4 addresses in two reputation services by hand, or each automation re-implements the lookups with its own credentials, pacing and error handling. Answers differ between callers, free-tier quotas run out on repeated lookups of the same address, and nothing refuses internal ranges before a lookup leaves the tenant.

## Trigger or entry

Other stories (Send to Story), an AI Agent action using it as a tool (Mode 3), and later an AI client through the ops tools server (Mode 4). The story does not start on its own.

## Systems touched

| System | Read or write | Credential (name only) | Notes |
|---|---|---|---|
| VirusTotal (IP report) | read | `virustotal_api` | must exist in the dev and prod teams under this name; free tier is rate-limited |
| AbuseIPDB (IP check) | read | `abuseipdb_api` | as above |
| `ioc_cache` Record type | read, write | — | a 24-hour cache; its own Records, no external write |
| `never_block` Resource | read | — | the protected ranges the guard refuses |

## Success metric

One consistent verdict per address for every caller, with a repeated lookup of the same address inside 24 hours answered from the cache — zero vendor calls for a cache hit.

## Volume estimate

About 50 calls a day across callers at first (placeholder; the owner confirms after week 1). Peaks follow alert bursts.

## Human touchpoints

None in the flow: the story only reads and returns a verdict. Callers decide what to do with it; any block or isolate action belongs to the caller, behind its own approval path.

## Data sensitivity

`internal` — IP addresses of suspected activity and the requester's email for the audit Record. The requester is never echoed in the result, and no personal data goes into URLs or logs.

## Simplest-first hypothesis

Rung 2 of `docs/01-decision-rules.md`: a Send to Story sub-story with a timeout. Rung 1 (an HTTP Request action in each caller) would repeat the guard, both lookups, the pacing and the cache in every caller, and the copies would drift. No judgement is needed, so no AI Agent action.

## Candidate seeds

- **87626** — Analyze an IP in many services at once (from `kit/catalog/library-seeds.yaml`).

## Open questions

1. Which free-tier limits apply to the two credentials in this tenant? — the owner, before build.
2. Should IPv6 be in scope? — the owner at G0. (Answer at G0: no, out of scope for iteration 1.)

## G0 decision

_Recorded as a `gate_decision` event (never edited here): `build`, by security-automation (the story owner) on the `gate_decision` Page — see `events.jsonl`._
