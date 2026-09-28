<!-- One story per PR. This body doubles as the change-request description the approver reads in Tines. -->

## Story and environment

- Slug: `<slug>` · Name: `[PREFIX] NN · Verb noun`
- Target: `prod` (via `ship.yml` on merge) · Tier: `production | internal | ops`
- Mode badge: `none | sub-story | mode-3-agent | mode-4-server`

## Lifecycle

<!-- sdlc/README.md. A design PR (branch design/<slug>) asks for G2: its merge is the design approval. A build PR
     (branch story/<slug>/<short>) asks for G4: its merge is the verify-and-merge gate, and sdlc.yml refuses it
     until the QA line below says pass and names a role (never a person or an email). The QA line is the human's
     verdict on the human_verification_prompt story-qa wrote; after editing it, re-run the failed sdlc job.
     Tracker, kit and rollback PRs: write n/a on each line. -->

- Story key: `<slug>` · tracker row `rev` in this PR: `<main's rev + 1>`
- Phase this PR completes: `design | build and verify | improve | n/a`
- Gate it asks for: `G2 design approval | G4 verify and merge | n/a`
- Rework attempt: `<n>/3`
- QA verification: pass/fail · by <role>
- Lifecycle artifacts: `sdlc/work/<slug>/`

## What changed

<!-- Paste the output of: ./scripts/diff-story.sh stories/<slug>/story.json --against origin/main -->

```
```

## Why

<!-- The problem, the ask, or the incident. Link the issue. -->

## Test event and observed events

- Sample: `stories/<slug>/tests/sample-event.json` → entry action `<name>` (`?draft=<name>` under change control)
- Run guid: `<guid>` · `action_count`: `<n>` · `event_count`: `<n>` (from `GET /api/v1/stories/{id}/runs`)
- Expectations in `tests/expectations.yaml` met: yes / no (say which failed)

## Cost impact

- New AI Agent action? yes / no · tools on it: `<n>` (max five) · budget line added to `policies/cost-ceilings.yml`: yes / n/a
- Schedule interval changed? `<before> → <after>` · Token alert set on the Status tab and recorded in `story.meta.yaml`: yes / n/a

## Monitoring

- Recipients: `manifest` (router webhook + email DL, set by `ship.yml`) · `monitor_failures: true`
- Watchdog (`notify if no events emitted`) on `<entry or scheduled action>`: `<seconds>` s (≈ 2× interval)

## Risk and blast radius

<!-- Which downstream stories call this one; which vendors; what happens if it is wrong for an hour. -->

## Rollback ref

- Previous good export: commit `<sha>` (`git log --oneline -- stories/<slug>/story.json`)

## Approver in Tines

- Role: `<security-platform | ops | security-automation>` — a role, never a person

## Checklist

- [ ] Built in the **dev team** with `/tines-build-story` — one story in this PR
- [ ] Validated in the editor and the test event passed
- [ ] Exported with `/tines-export` (`clear_recipients=true`, normalised — no `exported_at`)
- [ ] Lint passes locally (`./scripts/lint-story.sh stories/<slug>/story.json`)
- [ ] `story.meta.yaml` updated (credentials, resources, agents, monitoring, budget ref, `exported_from`)
- [ ] Credentials and resources exist in the **prod team** under the same names
- [ ] `/tines-review` run from a **fresh** session; findings addressed
- [ ] No credential values, resource contents, tokens, hostnames, customer names or people anywhere in the diff
- [ ] Ran `./scripts/kit bundle` and committed `kit/bundle/` and `kit/resources/*.example.json` if this PR changes a bundle source (`kit/bundle/README.md`) — or, in the template repository, **adds or removes any file** (the bundle's file manifest changes; `sdlc.yml`'s `bundle_fresh` fails otherwise)
