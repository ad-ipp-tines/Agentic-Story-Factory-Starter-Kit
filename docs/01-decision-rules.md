# 01 · Decision rules — the simplest-first ladder → full text in `01-thesis.md` §6

_This path is the name `DESIGN.md` §2.2 gives this document, and the one `AGENTS.md` §11 tells you to read before choosing an agent or MCP for anything. The ladder is stated here in brief so that read is short; the reasoning and the constraints per rung are in `01-thesis.md` §6._

## The ladder (climb only when the rung below cannot do the job)

1. **An HTTP Request action or a template** — known API, known sequence, no judgment. Deterministic, no AI credits, fastest, easiest to lint.
2. **A Send to Story sub-story with a Timeout Duration** — reuse inside the tenant; receives only the fields you pass, returns one `result` of 3–5 fields.
3. **An AI Agent action with Tines tools and no MCP** — judgment over Tines data, or chat. Output schema always; one tool first, at most five; a Trigger after the agent on an explicit schema field; a token alert on the Status tab; a budget line in `policies/cost-ceilings.yml`.
4. **Mode 3 — an AI Agent action with an MCP connection** — a vendor already hosts a server, or you built one in Tines. One tool first; enable tools individually; Streamable HTTP or Plain HTTP only; Bearer/header or OAuth 2.1; Business or Enterprise plan. Importing a story drops the connection — re-create it, never paste a token.
5. **Mode 4 — an MCP server action** — an AI client outside Tines must trigger a workflow or read data. Read tools plus **request** tools; **Tool hints: Read only** on every lookup; team-scoped access; 30-second tool ceiling, so long work returns `{status: started, id}` and a status tool.

Orthogonal to the ladder: **Mode 2 whenever the builder lives in an editor and wants diffs** — that is how this repository authors (`02-workflows.md` §1).

## Never

- Never MCP for **bulk data movement**, **sub-second latency**, or a **destructive action with no approval path**.
- Tool results are context, not a data plane — fan out inside a sub-story and return the summary.
- A typed, gate-able, auditable **request tool** beats a generic "run anything" tool (the `tools_are_requests` rule in `policies/lint-rules.yml` enforces the naming).

## Verify in your tenant before presenting

Rungs 4 and 5 quote plan-gated features (the AI Agent action on Business/Enterprise; Mode 4 on all plans). Confirm the tenant's plan mapping (item 13 in `07-verify-before-you-rely-on-it.md`) before stating either on a slide.
