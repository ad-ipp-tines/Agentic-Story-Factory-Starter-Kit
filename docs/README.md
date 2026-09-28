# docs/ — why this repository is shaped the way it is

_Tines Stories as Code · Platform: **Tines Stories** · docs v1 (2026-09-24) · Builder: `docs` · Source of truth for the design: `../DESIGN.md`._

`docs/` is the **"why" layer** of the repository. The other layers are: `AGENTS.md` (rules), `.claude/skills/` (procedures), `scripts/tines` (the API), `stories/` (truth), `tines-skills/` (tenant-side skills), `policies/` (the contract) and `.github/workflows/` (gates). Nothing in `docs/` is executed by anything; everything in `docs/` explains something that is.

## Reading order

| Read this | When | Time |
|---|---|---|
| `01-thesis.md` | You are deciding whether to adopt this way of building, or need to explain it | 15 min |
| `02-workflows.md` | You are about to build, ship, push a skill, read the monitor, or roll back | 20 min |
| `03-cost-controls.md` | Someone asks "what will this cost" or a budget alert fired | 15 min |
| `04-security-model.md` | A security reviewer is signing off, or you are answering a threat question | 20 min |
| `05-pros-and-cons.md` | You are deciding **not** to do this for a story, a team or a tenant | 10 min |
| `06-rollback-and-recovery.md` | Production is misbehaving, an approver rejected a change, or the monitor must be silenced | 10 min — read it **before** you need it |
| `07-verify-before-you-rely-on-it.md` | Before any demo, slide, or written claim — the consolidated VERIFY list with in-tenant checks | 10 min |
| `08-agentic-story-factory.md` | You are deciding whether to adopt the story factory: how this scaffold, the lifecycle (`sdlc/`) and the starter kit (`kit/`) fit together, what it costs and what stays by hand | 15 min |
| `09-lifecycle-walkthrough.md` | You are about to take a story through the lifecycle: one story from intake to improve, with every command, gate and file, following `sdlc/examples/example-enrich-ip/` | 25 min |
| `study-guides/` | You are new, or teaching someone who is: [the visual tour](study-guides/00-visual-tour.md) (eleven diagrams) and the specs for guides 01–06 | 30 min |
| `VERIFY.md` | The **ledger**: which VERIFY items your tenant has confirmed, when, and what changed in the repo | living |

## The four modes, one line each

Model Context Protocol (MCP) appears in Tines in four places. This repository uses the word **mode** for them and nothing else.

| Mode | Surface | This repository uses it for |
|---|---|---|
| Mode 1 | Workbench calling MCP tools (Workbench → MCP tab → New MCP connection) | Not required; the tenant-side skills in `tines-skills/` are also usable on Workbench presets |
| **Mode 2** | The **Tines Stories MCP server** at `https://<your-tenant>.tines.com/mcp` (OAuth only) | **Authoring from the editor** — every build (`02-workflows.md` §1) |
| **Mode 3** | The **AI Agent action** calling tools | **The monitoring agent** in `stories/ops-story-health-monitor/` (`02-workflows.md` §4) |
| **Mode 4** | The **MCP server action** at `https://<your-tenant>.tines.com/mcp/<mcp-path>` | **Exposing the ops lookups and request tools** in `stories/ops-tools-server/` (`02-workflows.md` §4.8) |

## How the docs map to `DESIGN.md`

`DESIGN.md` §2.2 lists the docs under slightly different names. Both sets describe the same content; this table says where each DESIGN.md name lives so that cross-references from `AGENTS.md`, `README.md`, the skills and the hooks resolve.

| `DESIGN.md` name | Lives here | Notes |
|---|---|---|
| `docs/00-why-stories-as-code.md` | `01-thesis.md` §1–§5 | The three ways to build are compared in §5 |
| `docs/01-decision-rules.md` | `01-thesis.md` §6 "The simplest-first ladder" | Referenced by `AGENTS.md` "Read next" |
| `docs/02-change-control-path.md` | `02-workflows.md` §2 (steps) and §2.9 (the path in one line, tenant policies, draft naming) | |
| `docs/03-monitoring-story.md` | `02-workflows.md` §4 (signals table, approval flow, by-hand list, silent-monitor runbook) | The design itself is `stories/ops-story-health-monitor/DESIGN.md` |
| `docs/04-cost-controls.md` | `03-cost-controls.md` | Adds a worked month |
| `docs/05-security-controls.md` | `04-security-model.md` | Adds the threat → control mapping |
| `docs/06-pros-and-cons.md` | `05-pros-and-cons.md` | Adds "when not to do this" |
| `docs/VERIFY.md` | `VERIFY.md` (the ledger) + `07-verify-before-you-rely-on-it.md` (the method) | Every builder appends to `VERIFY.md` when an item is confirmed (DESIGN.md §9 rule 15) |

Every `DESIGN.md` name in the table exists as a short redirect file at that path (`00-why-stories-as-code.md`, `01-decision-rules.md`, `02-change-control-path.md`, `03-monitoring-story.md`, `04-cost-controls.md`, `05-security-controls.md`, `06-pros-and-cons.md`), so links from `AGENTS.md`, the root `README.md`, `policies/POLICY.md` and the story READMEs resolve; each redirect names the exact section where the content lives. The reading order above is the set of full documents.

## Conventions these docs follow (DESIGN.md §9)

- **Placeholders, never real values:** `<your-tenant>`, `<org>`, ids `0`, `*.example.invalid`, `203.0.113.0/24`.
- **VERIFY** marks any claim not confirmed on a public Tines page or in the research; **[BY HAND]** marks a step the editor cannot do through `/mcp`. Nothing marked VERIFY is a headline claim.
- **No customer names, people, codenames or tenant hostnames.** Owner lines carry a role.
- **Product names as Tines writes them:** Tines Stories, the Tines Stories MCP server, MCP server action, AI Agent action, Task mode, Chat mode, Workbench, Workbench for Storyboard, Send to Story, Custom tools, Tool hints, Summary tab, Status tab, AI credits, flow, Community Edition, Tines tunnel, Streamable HTTP.
- **No invented `/mcp` tool names or API endpoints.** The Tines Stories MCP server is described by its documented capabilities; the only endpoints named are those in `DESIGN.md` §3.5, §4 and §5.
- **No secrets, ever.** These docs contain no credential values, and nothing in them tells you to paste one anywhere.

## Verify in your tenant before presenting

The docs are written against public Tines documentation and Anthropic's published guidance, current to 2026-09-17, and the platform sweep of 2026-09-24. Before any of this is shown to a customer or an internal audience:

1. Complete `/tines-connect` and record the `/mcp` tool names your client lists in `VERIFY.md` (item 1). Until then, the hook guard is a regex and the skills describe the server by capability only.
2. Edit a scratch story in the dev team through the editor and confirm whether the edits land as change-control drafts (item 2). The policy is enabled regardless.
3. Read one real export before quoting any lint rule (item 8) — the option key names for retry, monitor and output-schema settings are set from a real export, not from memory.
4. Fail one action in a LIVE scratch story with a test recipient to capture the monitoring payload (item 9). The router's `normalize` is tuned to that sample.
5. Confirm plan entitlements (item 13): the AI Agent action is Business/Enterprise only and unavailable in personal teams; Community tenants cannot run the monitoring agent.

The full list, with how to check each item, is `07-verify-before-you-rely-on-it.md`.
