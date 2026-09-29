# Role card — `security-reviewer` (04 verify, conditional)

_Spec: REPO-DESIGN.md §5.3.6. Agent file: [`.claude/agents/security-reviewer.md`](../../.claude/agents/security-reviewer.md) · Cursor wrapper: [`.cursor/rules/storyline-security-reviewer.mdc`](../../.cursor/rules/storyline-security-reviewer.mdc) · Contract: [`contracts/security-reviewer.schema.json`](contracts/security-reviewer.schema.json) · Evals of this agent: [`../evals/agents/security-reviewer.cases.yaml`](../evals/agents/security-reviewer.cases.yaml)._

## Mission

Threat-model one built story from the repository alone, in a fresh context, with OWASP-derived checks that the scaffold does not already gate (P9, P11, P16).

## When it runs

Only when `storyline/lifecycle/dispatch-rules.yaml` → `conditional.security-reviewer?` holds: the contract names egress hosts, credentials or AI agents, is a Mode 4 server, or opens any access wider than the team. Otherwise `verify-merge` records it as `skipped` (P18).

## Phase, tier, budget

verify · **strong** tier · `maxTurns: 15` · `disallowedTools: Write, Edit`. Spawned beside `tines-reviewer` in one turn (`parallel: true`).

## Inputs (paths in the input baton)

The diff range, `stories/<slug>/story.json`, `story.meta.yaml`, the contract (`egress_hosts`, `credentials`, `access`, `risk`), `policies/POLICY.md`, `policies/never-touch.yml`.

## The checks

| Id | Finds |
|---|---|
| sec.1 | untrusted input reaching an AI Agent action whose output drives an action without a schema-field Trigger |
| sec.2 | a side effect without an approval path or shadow mode |
| sec.3 | an egress host not in the contract |
| sec.4 | a credential used outside its declared hosts |
| sec.5 | Page, Webhook or MCP server access wider than the contract without a reason |
| sec.7 | personal data in URLs, Record TEXT fields or logs |
| sec.9 | prompt text that carries instructions sourced from inputs |
| sec.10 | Records or Resources holding secrets |

Cited, not re-checked: `tools_are_requests`, `mode4_read_only_hints`, `never_touch_targets`.

## Outputs and definition of done

- Findings in the baton (reused findings shape, rule ids `sec.N`), blocker first.
- Payload: `verdict` · `checks[8]` · `threat_model{entry_points[], untrusted_inputs_to_ai[], egress_hosts[], side_effects[], data_classes[]}`.
- **Done when** every check has a line and every `fail` has a finding with a `suggested_prompt` where the fix is a story change.

## Tools

`Read, Grep, Glob, Bash(./scripts/lint-story.sh *), Bash(./scripts/diff-story.sh *)`. No tenant access. No `Bash(git diff *)`: `git diff --output=<file>` writes files and would get around `disallowedTools`; `diff-story.sh` gives the diff. No `Bash(jq *)`: `jq -n env` would print the process environment (a tenant key) into findings that `apply` commits; the export is read with Read.

## Human touchpoints

The person confirms `apply`; the findings reach the PR through `verify-report.json`; a CODEOWNER and the person who merges read them (G4).

## Handoffs

→ `verify-merge` (deterministic) → rework or the build PR.

## Never

- Approve its own suggestions.
- Request tenant access.
- The common list (§5.2).
