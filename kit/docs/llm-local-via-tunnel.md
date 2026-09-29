# A local model through a Tines Tunnel

_Spec: REPO-DESIGN.md §10.3 (this path), §10.2 (the matrix rows `local_*_via_tunnel`), §7.3 (the provider probe), §12 row 15. The whole matrix: [`llm-provider-matrix.md`](llm-provider-matrix.md). Everything marked VERIFY is in `docs/VERIFY.md`._

This page is for the kickoff Page's `llm_choice` values `local_ollama_via_tunnel`, `local_vllm_via_tunnel` and `local_other_openai_compatible_via_tunnel`: a model server inside your own network serves the Tines-side AI Agent actions, reached through a Tines Tunnel. It is about the **Tines-side** provider only; the editor's model is a separate choice ([`llm-editor-side.md`](llm-editor-side.md)).

## Can you use this path?

| Tenant | Local model inside your network |
|---|---|
| Business or Enterprise, **cloud**, with the **Tunnel add-on** enabled by Tines support | Yes — this page |
| Cloud without the Tunnel add-on | No. A custom provider must then be publicly reachable |
| **Self-hosted** | No Tunnel on self-hosted. The provider must be reachable from the self-hosted network directly, and a custom provider is required anyway |
| **Community Edition** | No Tunnel, so no private local path. A publicly reachable model endpoint is technically possible and **not recommended** |

Custom providers themselves are listed for all tenants in one Tines source and for Business and Enterprise only in another: CONFLICT, VERIFY K20. Whether the Tunnel is bought, enabled and accessible by all teams on your plan is VERIFY K36.

## What the model server must support

Tines' requirement is an **OpenAI-API-compatible endpoint that supports streaming and tool use**. In practice:

- `POST …/v1/chat/completions` accepting `messages`, `tools[]` and `stream: true`;
- streamed chunks whose `delta.tool_calls` (index, id, function name, partial arguments) are accumulated by index and end with `finish_reason: "tool_calls"`;
- follow-up messages with `role: "tool"` and the `tool_call_id`;
- ideally a models list, so Tines can discover the models automatically.

Do **not** rely on `tool_choice` or `strict`: they are not portable, and Ollama lacks `tool_choice`.

| Server | Notes |
|---|---|
| **Ollama** | On Tines' list of compatible providers. It serves an OpenAI-compatible API under `…/v1/`; clients must send an API key, which Ollama ignores; it has streamed tool calls since 2025-05-28. Choose a model from Ollama's list of tool-capable models |
| **vLLM** | **Not named anywhere in Tines' docs (VERIFY K22).** Its tool-calling server flags sit outside Tines' docs. Treat it as "other OpenAI-compatible" until the kit's tool probe passes against it |
| Any other OpenAI-compatible server | Must stream and support tool use. Pick the API type under Extra options |

## Set it up

1. **Buy the Tunnel add-on and ask Tines support to enable it.**
2. **Run the Tunnel container** (`oci.tines.com/tines-tunnel`) on a host that can reach the model server, with the tunnel secret Tines gives you — the secret stays on that host, never in this repository or a prompt. The container needs **outbound TCP 7844 only** and no inbound rules. It uses the host's DNS: test name resolution with `nslookup` inside the container. NTLM proxies are not supported. For high availability, run a second container with the same secret.
3. **Make the tunnel accessible by all teams** at `/admin/tunnel`. Only such tunnels can carry AI-provider traffic.
4. **Add the custom provider** in Settings → AI settings → custom provider:
   - Extra options → **Use tunnel**, and the base URL of the internal host.
   - By default Tines appends `/v1` and the endpoint path to the base URL. To send the exact URL instead, turn on **"Use full API endpoint URL"** — and then add the model ids by hand, because discovery no longer runs.
   - The API key goes in a **credential**, never pasted. For Ollama any placeholder value works; whether a blank key, or a plain `http://` base URL, is accepted is VERIFY K23.
   - Select a custom CA if the server uses private TLS.
   - Give the provider the name you will type on the kickoff Page (`provider_name`).
5. **Run the kit's probe.** On day 1, submit the kickoff Page with the matching `local_*` choice; section F runs a tool-less call and a one-tool call and reports a verdict. After a later fix, re-run section F as `stories/kit-launch/sections/F-llm-probe.md` describes, and read `kit_state.step_probe`.
6. **Keep a foundation provider active beside it** (below), and pin every tool-using AI Agent action to it.

## Read the verdict

| Verdict | Means | Do |
|---|---|---|
| `ok` and `credits_used == 0` | The local model answers and handles a streamed tool call | Proceed. The local model may serve the tool-less agents now; tool-using agents move only after their own eval set passes on it |
| `tool_calls_unreliable` | The tool-less call passed; the tool call failed | Expected on small models. Keep tool-using agents on the foundation provider; the three runtime crew are tool-less and may stay local. Acknowledge it in the day-1 milestone |
| `failed` | The tool-less call failed | Check, in order: the Tunnel is up and accessible by all teams (K36); the base URL and "Use full API endpoint URL"; the key credential (K23); streaming support; the provider's name matches the Page |
| `ok` but `credits_used > 0` | The action ran on a Tines-provided model | The local provider is not the default for the ops team: check the provider's team scoping and the tenant defaults |

The probe checks the tenant's **defaults** (fast for the tool-less call, smart for the tool call), because a per-action model cannot be chosen per run (VERIFY K26). A model pinned on an action later is exercised by that story's own eval cases, run with `./scripts/storyline eval-run` against the dev copy.

## Cost

- **Zero Tines AI credits.** Custom models use no run-time credits.
- **Not covered by Tines' credit alerts.** The kit's own bounds still apply: the `storyline_limits` daily caps and kill switch, a token alert per AI Agent action (whether those act on custom providers is VERIFY K25), and a budget line per action in `policies/cost-ceilings.yml`.
- **The real cost is the host**: the GPU or CPU, the power, and the operations.
- `GET /api/v1/ai_usage` still reports tokens; what `billed_cost` shows for a local provider is VERIFY K25.

## The expected weakness, stated plainly

Small local models are markedly weaker than foundation models:

- at **choosing and calling tools** — which tool, which arguments, when to stop;
- at following an output schema;
- at following long instructions.

Tines' own guidance for Workbench for Storyboard on self-hosted tenants strongly recommends the latest Anthropic or OpenAI foundation models. Read that as a warning for any tool-using agent. The kit's tool probe catches gross tool-call failure; each story's eval set, run with pass^k, measures the rest.

## Where a local model fits by design

- **First candidates:** the kit's runtime crew (`planner`, `brief_writer`, `retro_writer`) and the ops sweep's `critic`. All four are **tool-less**. The three kit agents carry a skill, which counts as an agentic capability, so their model is pinned on the action whichever provider serves it.
- **Only after their own eval set passes on the local model:** tool-using agents — the ops `triage`, any Mode 3 story.
- **Never by default:** Workbench for Storyboard, which is a smart-model, tool-heavy job.

## Fallback

1. **Keep one foundation provider active** beside the local one, and pin tool-using actions to it with per-action model selection.
2. **A twin for each local-model action.** When a local-model action fails its schema Trigger or times out, route the event to a twin AI Agent action pinned to the fallback model, with the same instructions and output schema. If the twin fails too, the event goes to a person (`needs_human`).
3. **If the Tunnel is down,** the action errors and the scaffold's router pages ops; set `storyline_limits.enabled` to false to stop the runtime crew until it is back.
4. **Community Edition** has no Tunnel, so there is no private local path at all.

## Verify in your tenant before relying on it

| Item | What is assumed |
|---|---|
| K20 | Custom providers by plan (CONFLICT) |
| K22 | vLLM behind Tines: streamed tool-call deltas; the server flags |
| K23 | A plain `http://` base URL and a blank API key are accepted; the `provider_type` a local provider reports |
| K25 | `billed_cost` for a local provider; whether token alerts act on custom providers |
| K26 | Whether the model field accepts a formula |
| K36 | The Tunnel on your plan: bought, enabled by support, accessible by all teams |
