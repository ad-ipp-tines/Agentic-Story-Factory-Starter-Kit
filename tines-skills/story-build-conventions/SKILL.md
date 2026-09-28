---
name: story-build-conventions
description: States this tenant's story conventions (naming, sub-story result contract, HTTP hardening, monitoring, AI Agent rules) so Workbench answers and agent-drafted configurations match the repository. Used whenever a story is being designed, reviewed or extended inside Tines.
license: Proprietary
compatibility: Tines AI Agent action (Task mode) and Workbench presets
metadata:
  owner: platform
  source: "AGENTS.md"
  version: "1"
---

# Story build conventions

These are the conventions of the repository that holds this tenant's stories as exported JSON. They exist so that a story drafted inside Tines — by Workbench for Storyboard, by an agent, or by a person asking Workbench — looks like a story built from the editor, passes the repository's lint and review, and exports without surprises. When you draft or assess a story configuration, apply every rule below and say which rule you applied.

The builder and the monitor share this one definition of "correct". A builder (the editor through the Tines Stories MCP server, or Workbench for Storyboard) drafts to these rules; the ops monitoring agent (the `story-health-triage` skill on `[OPS] 10`) measures an unhealthy story against the same rules, so every `story_config` proposal it makes — a missing `retry_on_status`, an agent without an output schema, a schedule inside a Group, an expected status logged as an error — is a convention stated here, never a preference of the moment. A rule that is not in this file is not something the monitor may propose, and not something a builder is held to.

The block between the two `shared-block` markers is the distillation of the corresponding sections of `AGENTS.md` in the repository (naming, HTTP hardening, monitoring, AI Agent actions, credits, ownership and never-touch). `AGENTS.md` carries the same block between the same markers, and the repository's `lint.yml` fails a pull request whose checksum of this block differs from that copy, so a convention changes in both files in one pull request.

<!-- shared-block: agents-md-conventions v1 begin -->

## Naming

- A story is named `[PREFIX] NN · Verb noun` — a bracketed team prefix, a two-digit number, a middle dot, an imperative phrase. Examples: `[SEC] 01 · Enrich IP (sub)`, `[OPS] 10 · Monitor story health and credits`.
- A sub-story (a story called through Send to Story) ends its name in `(sub)`.
- Story names are identical in every environment; the deployment pipeline matches stories by name.
- Action names are lowercase snake_case and say what the action does: `normalize`, `is_protected`, `lookup_reputation`, `verdict`, `result`, `error`. Triggers are named `is_<condition>` or `has_<thing>`.
- Every canvas carries one Note stating the story's purpose, its inputs, its outputs and its mode badge (Mode 1 Workbench calling MCP tools · Mode 2 the Tines Stories MCP server · Mode 3 the AI Agent action calling tools · Mode 4 the MCP server action · or "none").

## The sub-story contract

- A sub-story finishes on a **message-only Event Transform named `result`** that emits exactly 3–5 fields. The tool description documents those fields, because tool responses carry no output schema.
- Every failure branch ends on an Event Transform named `error` that emits `{status: "error", error_category, retryable, message}` — `error_category` one of `auth | rate_limit | upstream_5xx | validation | permission | unknown`, `retryable` a boolean, `message` a sentence a person can act on. Never an empty response for "auth failed".
- The entry action's expected fields are normalised first by an Event Transform named `normalize` using `DEFAULT()` fallbacks, so a missing field never breaks a formula downstream.
- A guard Trigger sits before any AI step and before any outbound action with side effects (for example `is_protected` checking a range against a Resource), and refuses with a structured `{status: "refused", reason}` before any lookup runs.

## HTTP Request hardening

| Setting | Value | Why |
|---|---|---|
| Retry on status | `[429, 500-599]` | transient upstream failures and rate limits |
| Retries | 5–8 (use 6) | the default of 25 spreads retries over roughly 3 h 20 min (duration VERIFY against a real export) and hides an outage |
| Emit failure event | **Always** | the default "Error response only" misses timeouts and DNS failures |
| Log error if | a formula for 200-with-error bodies | vendors that return `200 {"error": …}` |
| Log error on status | exclude expected non-2xx (a lock's `422`, an empty lookup's `404`) | expected outcomes are not errors |
| Failure path | connected to the `error` Event Transform and the dead-letter Record | nothing fails silently |

(Option names as shown in the action's settings; the key names in a story export are confirmed from a real export — VERIFY #8.)

## Monitoring

- Recipients are the ops router webhook and the ops email distribution list, both from the repository manifest — never a person's address, never a literal URL in a story.
- Story-level **Notify when any action fails** is on for every `production` story.
- **Notify if no events emitted** is on for every scheduled or ingress action, at about 2× its interval (the exact number is derived from baseline data by the ops sweep and proposed, not guessed).
- Monitoring only works on a story running LIVE.

## AI Agent actions

- An **output schema** on every AI Agent action, always. Make fields nullable when the source may lack them; include an `other` value with a detail field wherever a closed list is used.
- **One tool first, at most five.** Tools are added one at a time; a job that needs more is split across agents or moved into a Send to Story sub-story that returns one summary. Tools return 3–5 fields, never raw data; the loop lives in the story, not in the model.
- A **Trigger after the agent** branches on an explicit schema field (`severity`, `proposed_change.kind`, `needs_human`) — never on confidence, sentiment or prose.
- A **token-usage alert on the Status tab**: Notify at one threshold, Disable action at a higher one. Set by hand; recorded in the story's meta file.
- The relevant tenant skill attached (`story-health-triage`, `credit-budget-analyst`, `alert-policy`, or this one), and the attachment recorded in the story's meta file.
- **Agents reason, stories fetch.** Anything deterministic — a lookup, a fan-out, a filter — is an HTTP Request action, a Send to Story or an Event Transform before the agent, not a tool the agent has to decide to call.
- Every new AI Agent action needs a budget line in `policies/cost-ceilings.yml` before it ships.
- Task mode defaults are temperature 0.2, timeout 30 s, retries 25 — raise the timeout for a tool-using agent and lower the retries. A tool-less Task-mode agent runs on the fast model; adding a tool moves it to the smart model.

## Credits

- Know which provider each agent uses. A custom provider bypasses AI credits but still bills (`billed_cost`); the two are never summed.
- Each agent run's `meta.credits_used`, tokens and model are written to a Record so credits per completed task can be scored.

## Ownership and never-touch

- Each story prefix belongs to one team; the owner is a role, never a person.
- `policies/never-touch.yml` is the machine-read list of what no agent, skill, hook or pipeline writes to: production story ids, every `[OPS]` story (changed only through its own change request), the `90 Seeds` folder, and anything in another team. A story on that list may be *reported on*, never changed.
- Production is changed only through the repository: export → pull request → review → merge → import as a change-control draft → change request → a named approver. Never edit a live production story by hand or through Workbench; propose the change instead.

## Exports

- If the story will be exported to the repository — every `production`, `internal` and `ops` story is — reference credentials and resources **by name** only; the credential must exist under the same name in every team the story is deployed to. Exports contain no credential values, resource contents or events by design, and recipients are cleared on export and set from the manifest on deployment.
- Guards live in the story (Triggers, Resources, change control), not in prompt text.

<!-- shared-block: agents-md-conventions v1 end -->

## Story requirements and tags

The tenant's change-control policy sets the story requirements — name, description, owners, tags and event retention — to required, so a story missing any of them cannot open a change request. Fill them before proposing: the description restates the canvas Note's purpose line; owners are the owning team (a role, never a person); tags carry the team prefix in lowercase (`sec`, `ops`), the tier (`production`, `internal`, `ops`) and, for a sub-story, `sub` — the same words the repository's `story.meta.yaml` records, so a tag never says something the meta file does not. Event retention on a `production` story is at least 30 days.

## How to use this skill inside Tines

- **When asked to draft an action or a story** (Workbench for Storyboard build mode — whether preset skills load there is VERIFY #14): apply the rules above to the draft — name the story to the pattern, add `normalize`, the guard Trigger, `result` and `error`, harden every HTTP Request action, reference the credential by name rather than pasting anything — then list which rules you applied and which the person must finish by hand: monitoring recipients, the token alert, change control, event retention, Record types.
- **When asked to review a story**: walk the sections in order and report each rule as pass, fail or not applicable, with the action name. A story with an AI Agent action and no output schema, or an HTTP Request action on default retries, does not pass.
- **When asked to do something the conventions forbid** (edit a live production story, paste a token into an action, add a sixth tool, remove a failure path): say which rule forbids it and give the conforming alternative — a proposal, a named credential, a sub-story, an `error` branch.
- **When the person is a builder working from the editor**: remind them the story is exported afterwards, so links are index-based, agent order matters, and nothing typed into an option should be a value that must not land in a repository.

## Limits worth knowing before you design

Platform limits that shape a design (from the platform-limits sweep; re-check the numbers against the tenant's documentation — VERIFY): an event up to 100 MB; an HTTP Request response up to 30 MB; a Loop runs at most 5 minutes; 30,000 events per branch; queues drop above 20,000 pending; an AI Agent tool output truncates at 50,000 tokens unless disabled; an MCP server action tool must answer within 30 seconds. Design fan-out inside a Send to Story sub-story that returns one summary; design long work to return `{status: "started", id}` and expose a `status` tool.
