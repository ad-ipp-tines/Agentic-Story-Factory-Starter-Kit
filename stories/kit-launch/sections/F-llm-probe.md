# Section F — the provider probe (one test call, plus a tool check)

_Spec: REPO-DESIGN.md §7.3 (this section), §10 (the provider matrix, the local path), §12 rows 15 and 18. Part of `[KIT] 00 · Launch Storyworks`; on the canvas it sits between A24 and A28 (A25–A27). Built through Mode 2 by build prompt **P-K10** (`../build-prompts.md`). Its two AI Agent actions are the story's only ones outside section D, and both are checks, not runtime tool paths — the story's mode badge stays **none**._

**What it does.** It proves, on day 1, that the model provider the customer chose actually answers the kit's AI Agent actions: one tool-less call (does the provider answer and follow an output schema?) and one call with one tool (does it support streamed tool use, which a custom provider must?). It records the model the tenant reported, the tokens and the credits, and hands a verdict to the setup report. It runs once per provisioning run — twice the calls, never a loop.

**What it cannot check.** A per-action model cannot be chosen per run (whether the model field accepts a formula is **K26**), so the probe checks the tenant's **defaults**: the fast default for the tool-less call and the smart default for the tool call. The three runtime crew in section D have the fast model **pinned** on their actions (`[BY HAND]` at build); if the pinned model is a different one from the fast default, re-run the probe after pinning (below) — or trust the first eval run in the dev copy (`storyline/evals/agents/runtime-*.cases.yaml`), which exercises the pinned actions themselves.

## Gate

| # | Action | Type | Does | Next |
|---|---|---|---|---|
| F0 | `ent_ai_agent_action` | Trigger | `normalize.entitlements.ai_agent_action` is true. AI Agent availability on Community is a **CONFLICT (K7)**; the kit's Community path does not import this story at all | → F1 |
| F0a | `has_no_ai_agent_action` | Trigger | the complement | → F0b |
| F0b | `probe_not_entitled` | Event Transform | `{verdict: "not_entitled", detail: "the AI Agent action is not entitled; the runtime crew stay off and intake briefs are written with the template (storyline/templates/intake-brief.md)"}` | → `record_probe` → A28 |

## The actions

| # | Action | Type | Configuration | Checks · next |
|---|---|---|---|---|
| F1 | `llm_probe` | **AI Agent action, Task mode** | **No tools**, so it runs on the tenant's **fast** default. Model: not set on the action (the tenant default is what is being checked). Temperature **0** · timeout **60 s** · retries **1**. No skill (the probes stay skill-less). **Instructions:** "You are a connectivity check. Reply with only the JSON object the output schema describes. Set ok to true and copy the nonce from the prompt exactly." **Prompt:** `Return {"ok": true, "nonce": "<<normalize.run_guid>>"}.` **Output schema:** `{"type": "object", "additionalProperties": false, "required": ["ok", "nonce"], "properties": {"ok": {"type": "boolean"}, "nonce": {"type": "string", "maxLength": 64}}}`. Token alert (Notify 5,000 / Disable 10,000 daily) `[BY HAND]`; budget line `kit-launch/llm_probe` | → F1a / F1b |
| F1a | `llm_probe_ok` | Trigger (**directly after the agent**) | `llm_probe.output.ok` is true **and** `llm_probe.output.nonce` equals `normalize.run_guid` — schema fields only, never prose or confidence | → F2 |
| F1b | `llm_probe_failed` | Trigger | the complement, including an action error (emit failure event) or an output-schema failure | → F3 |
| F2 | `llm_tool_probe` | **AI Agent action, Task mode, one tool** | Tool = a **Custom tool**: the action Group **`probe_constant`** inside this story, whose one action is **`probe_constant_value`** (Event Transform, message-only) returning `{"value": 42}`. The tool's description (three sentences, as the scaffold's tool rules ask): "Returns the constant used to check tool calling. Call it once, with no arguments, whenever you are asked for the probe value. It returns an object whose value field is the number to report." Adding a tool moves the action to the tenant's **smart** default. Temperature **0** · timeout **60 s** · retries **1**. **Instructions:** "You are a tool-calling check. Call the probe_constant tool exactly once, then reply with only the JSON object the output schema describes." **Prompt:** `Call probe_constant and report its value.` **Output schema:** `{"type": "object", "additionalProperties": false, "required": ["value", "tool_called"], "properties": {"value": {"type": "number"}, "tool_called": {"type": "boolean"}}}`. Token alert (Notify 10,000 / Disable 20,000 daily) `[BY HAND]`; budget line `kit-launch/llm_tool_probe` | → F2a / F2b |
| F2a | `tool_probe_ok` | Trigger (directly after the agent) | `llm_tool_probe.output.value == 42` **and** `llm_tool_probe.output.tool_called` is true | → F3 |
| F2b | `tool_probe_failed` | Trigger | the complement, including an action error or a timeout | → F3 |
| F3 | `probe_verdict` | Event Transform | `verdict`: **`ok`** (F1 and F2 pass) · **`tool_calls_unreliable`** (F1 passes, F2 fails: the report recommends running only **tool-less** agents on this model, §10.2) · **`failed`** (F1 fails; F2 is not run). Emits `{verdict, model, input_tokens, output_tokens, credits_used, tool_calls, duration_ms, detail}` from `llm_probe.meta` and `llm_tool_probe.meta` (the model and `credits_used` keys are the ones the scaffold's `[OPS] 10` already reads; the token and duration keys are read from the first dev run, scaffold VERIFY #8) | → `record_probe` (`step_probe`) → A28 |

`probe_constant` is a Group, and a Group is never scheduled (lint `schedule_sanity`). The Group is used only as F2's tool; nothing else links into it.

## What the verdict means, by provider

| `llm_choice` (§10.2) | Expect | If not |
|---|---|---|
| `tines_provided` | `ok`; `credits_used > 0` on both calls | `failed`: check the tenant's AI settings and the ops team's credit allocation |
| `byo_anthropic` · `byo_openai` · `byo_bedrock` · `byo_azure_openai` | `ok`; `credits_used == 0` (custom models consume no run-time credits; the bill is `billed_cost`, **K25**) | `failed`: the provider's base URL, key credential or team scoping. `credits_used > 0`: the action ran on a Tines-provided model — the custom provider is not the default for this team |
| `local_*_via_tunnel` | `ok`, or `tool_calls_unreliable` on small models; `credits_used == 0` | `tool_calls_unreliable`: keep tool-using agents on a foundation provider (§10.3 "Fallback"); the three runtime crew are tool-less and may stay local. `failed`: the Tunnel (**K36**), the base URL, a plain `http://` URL or blank key (**K23**), streaming support. vLLM is not named in Tines' docs (**K22**) |
| self-hosted tenant | as the custom row; a custom provider is **required** | — |

The verdict is advisory. It gates nothing by itself: the runtime crew stay off until a person sets `storyline_limits.enabled` and `guards_confirmed`, and a person reads the verdict before doing so (day-1 milestone: "the provider probe is ok, or tool_calls_unreliable is acknowledged").

## Cost

Two calls per provisioning run. Both actions have budget lines (`runs_per_day_max: 5`) and token alerts. A4 stops a completed run, so the probe does not repeat unless someone re-runs it on purpose.

**Re-running the probe** (after a provider change, a Tunnel fix, or pinning a model): re-emit the last event of `ent_ai_agent_action` from the storyboard `[BY HAND]` (the storyboard's re-emit control is confirmed at build — VERIFY; if it is missing, the probe is re-checked through the dev copy's runtime eval run instead), which runs F1–F3 and `record_probe` again with the recorded answers; then read `kit_state.step_probe`. The report in git is not rewritten by a re-run of F alone.

## Test

`../tests/expectations.yaml`: the happy path must fire `ent_ai_agent_action`, `llm_probe`, `llm_probe_ok`, `llm_tool_probe`, `tool_probe_ok`, `probe_verdict` with `verdict: ok` on a Tines-provided dev tenant; the variant `ai_not_entitled` must fire `has_no_ai_agent_action` and `probe_not_entitled` and neither agent. Model calls in dev spend dev-team credits (a few hundredths of a credit per run).

## Verify in your tenant

| Item | What to check |
|---|---|
| K7 | AI Agent availability on Community (the kit's Community path does not import this story) |
| K22 · K23 · K36 | vLLM behind Tines; plain `http://` and blank keys for local providers; the Tunnel on the plan |
| K25 | `billed_cost` for custom and local providers; whether token alerts act on custom providers |
| K26 | Whether the AI Agent action's model field accepts a formula — if it does, F1/F2 can probe the exact chosen model |
| scaffold #8 | The event `meta` keys for tokens and duration |
