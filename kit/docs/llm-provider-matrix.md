# The model-provider matrix — which model runs your Tines-side AI

_Spec: REPO-DESIGN.md §10.1–§10.2, §7.2 A8–A9, §7.3 (section F), §12 rows 2, 10 and 15. Companion guides: [`llm-local-via-tunnel.md`](llm-local-via-tunnel.md) (a local model) and [`llm-editor-side.md`](llm-editor-side.md) (the editor's model). Everything marked VERIFY is in `docs/VERIFY.md`._

## Two different "models", kept apart

This repository has two model choices, and they never mix. This page is about the first.

| | **Tines-side provider** (this page) | **Editor-side model** ([`llm-editor-side.md`](llm-editor-side.md)) |
|---|---|---|
| Powers | AI Agent actions — the kit's `planner`, `brief_writer`, `retro_writer` and the two probes; the ops sweep's `triage` and `critic`; any Mode 3 story — plus Workbench and Workbench for Storyboard | Authoring through Mode 2, and every IDE specialist in `.claude/agents/` |
| Configured | Settings → AI settings, by a tenant owner, **in the UI only**: the API only lists providers | In the editor (Cursor, Claude Code) |
| Paid with | Tines AI credits, or your own provider's bill | The editor plan. No Tines credits are listed for the Tines Stories MCP server; whether its research and listing helpers use credits is VERIFY #11 |
| The kickoff Page's `llm_choice` means | **this column** | not this |

## The matrix

`llm_choice` is the kickoff Page's answer (`kit/tenant/config.yaml` → `llm.choice`).

| `llm_choice` | Configure | Tines credits | Credit alerts | Plan | Network path | Models | What the kit's probe expects | Notes |
|---|---|---|---|---|---|---|---|---|
| `tines_provided` | Nothing: the default is Anthropic Claude on AWS Bedrock; Tines also manages an OpenAI provider | **Consumed.** 1 credit = $0.01; allowances reset on the 1st; top-ups roll over; Community gets 50 a month | Yes — tenant, unallocated, per team, and per-team Workbench for Storyboard; defaults of 80 % and 100 % by email; custom alerts by email, in-app or webhook | all | Tines-managed | The smart and fast defaults | `provisioning_type: tines_provisioned`; `credits_used > 0` | AI Agent limits: 40 (eu-west-1) or 100 runs a minute per tenant |
| `byo_anthropic` · `byo_openai` · `byo_bedrock` | "Use custom provider" → provider → base URL, API key (a credential or a formula, never pasted), custom models, custom headers; optional team scoping (Access) | **None** — custom models consume no run-time credits | **Not covered** | CONFLICT K20: all tenants vs Business and Enterprise only | Public endpoint; optionally a Tunnel (Anthropic and Bedrock tunnel support since 2026-06-15) | Discovered automatically if the provider serves a models list, otherwise added by hand | `customer_provisioned` with `provider_type` `ANTHROPIC`, `OPEN_AI` or `AWS_BEDROCK`; `credits_used == 0` | External providers: 500 runs a minute per tenant (CONFLICT K21: "no limit"). The bill shows as `billed_cost` in AI usage (K25). Bedrock Mantle uses the API type "OpenAI Responses" |
| `byo_azure_openai` | As above, with **API type = Azure** under Extra options | None | Not covered | K20 | Public | Usually added by hand | `customer_provisioned`; the `provider_type` Azure reports is K24 | — |
| (a proxy or observability gateway) | OpenAI or Anthropic behind a proxy, Helicone, OpenRouter, xAI: schema-compatible providers configured the same way. Choose `byo_openai` or `byo_anthropic` on the Page and give the provider's name | None | Not covered | K20 | Public | As above | As above | Useful as one gateway in front of every model |
| `local_ollama_via_tunnel` | Custom provider (OpenAI-compatible; **Ollama is on Tines' compatible list**) + Extra options → **Use tunnel** | **None** | **Not covered** | K20 + the **Tunnel add-on** (Business or Enterprise, cloud only, enabled by Tines support) | A Tines Tunnel container inside your network → the Ollama server | Discovered automatically (Ollama serves the models list) | `customer_provisioned`; `credits_used == 0`; the tool probe may fail on small models | [`llm-local-via-tunnel.md`](llm-local-via-tunnel.md) |
| `local_vllm_via_tunnel` | As above | None | Not covered | As above | As above | As above | As above | **vLLM is not named anywhere in Tines' docs (K22).** Treat it as "other OpenAI-compatible" until the tool probe passes |
| `local_other_openai_compatible_via_tunnel` | Custom provider: OpenAI-API-schema compatible, the API type set under Extra options, **streaming and tool use required** | None | Not covered | As above | As above | Discovered or added by hand; with **"Use full API endpoint URL"** on, model ids must be added by hand | As above | A custom CA is supported for private TLS |
| (a self-hosted tenant) | A custom provider is **required** | None | Credit limits do not apply to self-hosted | self-hosted | The provider must be reachable from the self-hosted network; **no Tunnel on self-hosted** | — | As above | Tines strongly recommends the latest Anthropic or OpenAI foundation models for Workbench for Storyboard on self-hosted |

## What holds for every choice

- Several providers can be active at once, and at least one must stay active.
- A model chosen on an AI Agent action (or in Workbench) **overrides** the tenant's smart and fast defaults.
- "Additional request parameters" (key/value pairs merged into the request) exist for **custom providers only**.
- Providers can be scoped to teams. AI Agent access follows the action's team; Workbench access follows the user.

## Smart and fast, and why the kit pins a model

A Task-mode AI Agent action with **no agentic capability** runs on the tenant's **fast** default. Tools, code analysis, web search **or an attached skill** switch the default to the **smart** model. The kit's three runtime specialists are tool-less but each carries a skill, so the fast model is **pinned on each action** `[BY HAND]` and recorded in `stories/kit-factory/story.meta.yaml`; without the pin they would run on the smart model. The cost check `cost.4` (`./scripts/sdlc estimate --check`) estimates any agentic action at the smart model unless a model is pinned, and fails a fast-tier agent that carries a skill without one.

## How the kit checks your choice on day 1

1. **A8–A9** read `GET /api/v1/ai_providers` and match your `llm_choice`:

   | `llm_choice` | Matches a provider with | `provider_type` |
   |---|---|---|
   | `tines_provided` | `provisioning_type: tines_provisioned` | — |
   | `byo_anthropic` · `byo_openai` · `byo_bedrock` | `customer_provisioned` and the name you gave | `ANTHROPIC` · `OPEN_AI` · `AWS_BEDROCK` |
   | `byo_azure_openai` | `customer_provisioned` and the name you gave | presumed `OPEN_AI` (K24) |
   | `local_*` | `customer_provisioned` and the name you gave | presumed `OPEN_AI` (K23) |

   The result is `ok`, `not_found`, `disabled`, `mismatch` (a provider of that name with another type) or `unknown` (the call failed). Anything but `ok` adds "configure or confirm the provider in Settings → AI settings" to the `[BY HAND]` list.
2. **Section F** runs two AI Agent actions: `llm_probe` (no tools, so the tenant's fast default) must return the run's nonce through its output schema, and `llm_tool_probe` (one Custom tool, so the smart default) must call the tool and report its value. A per-action model cannot be chosen per run (K26), so the probe checks the tenant's **defaults**, not a model pinned later.

   | Verdict | Means | Do |
   |---|---|---|
   | `ok` | The provider answers and handles a streamed tool call | Nothing. For `tines_provided` expect `credits_used > 0`; for every custom or local provider expect `credits_used == 0` |
   | `tool_calls_unreliable` | The tool-less call passed and the tool call failed | Run only **tool-less** agents on this model (the kit's three runtime specialists are); keep tool-using agents, such as the ops `triage`, on a foundation provider pinned per action. Acknowledge it in the day-1 milestone |
   | `failed` | The tool-less call failed | Check the provider's base URL, key credential and team scoping; for a local model, the Tunnel ([`troubleshooting.md`](troubleshooting.md), `step_probe`) |
   | `not_entitled` | The AI Agent action is not entitled | The runtime specialists stay off; intake briefs are written from the template |

   `credits_used > 0` on a custom provider means the action ran on a Tines-provided model: the custom provider is not the default for the ops team.

## Choosing

- **Start with `tines_provided`** unless policy says otherwise: no configuration, credit alerts work, and the probe's expectations are the simplest.
- **Bring your own provider** when a contract, a data-handling rule or one bill for every model requires it. Custom providers consume no Tines credits but are **not covered by Tines' credit alerts**, so the kit's own bounds carry the weight: the `sdlc_limits` caps and kill switch, a token alert per AI Agent action (whether those act on custom providers is K25) and a budget line per action.
- **A local model** fits the tool-less agents first — the three runtime specialists and the ops `critic` — and tool-using agents only after their own eval set passes on it ([`llm-local-via-tunnel.md`](llm-local-via-tunnel.md)).
- **Changing later** is a Settings change plus a PR to `kit/tenant/config.yaml` (`llm.choice`, `llm.provider_name`), so `kit_config` and the cost checks follow. Re-run the probe after a provider change or after pinning a model (`stories/kit-factory/sections/F-llm-probe.md`).

## Verify in your tenant before relying on it

| Item | What is assumed |
|---|---|
| K20 · K21 | Custom providers by plan; the external-provider rate limit |
| K22 · K23 · K24 | vLLM behind Tines; plain `http://` and blank keys for local providers and the `provider_type` they report; Azure's `provider_type` |
| K25 | `billed_cost` for custom and local providers; whether Status-tab token alerts act on custom providers |
| K26 | Whether the AI Agent action's model field accepts a formula (a per-run model) |
| #11 | Whether the Tines Stories MCP server's research and listing helpers consume credits |
