# 03 · The monitoring story, for operators → read `02-workflows.md` §4

_This path is the name `DESIGN.md` §2.2 gives this document. The operator-facing prose lives in `02-workflows.md` §4; the design itself is `stories/ops-story-health-monitor/DESIGN.md` (a copy of `DESIGN.md` §5). This file exists so the link resolves and says where each piece is._

| `DESIGN.md` §3.9 asks for | Where it lives |
|---|---|
| The signals table (source → direct or derived → owner action) | `02-workflows.md` §4.2 |
| The router (`[OPS] 01 · Route monitoring alerts`) | `02-workflows.md` §4.3; `stories/ops-error-router/README.md` |
| The sweep (`[OPS] 10 · Monitor story health and credits`) and the agent's role — read-only, propose only | `02-workflows.md` §4.4; `stories/ops-story-health-monitor/README.md` |
| The approval flow and the alert-setting behaviour (thresholds from baseline data, a human applies) | `02-workflows.md` §4.5 |
| The "what stays by hand" list — AI Agent token thresholds on the Status tab; per-team credit allocation in Admin → AI; credit-usage alert thresholds; Record types | `02-workflows.md` §4.6 |
| The weekly digest | `02-workflows.md` §4.7 |
| The Mode 4 face (`[OPS] 20 · Ops tools (MCP server)`) | `02-workflows.md` §4.8; `stories/ops-tools-server/README.md` |
| The runbook for when the monitor itself is silent (its own watchdog pages the DL) | `02-workflows.md` §4.9; `06-rollback-and-recovery.md` §7 for silencing or disabling it |
| Cost of the ops pair | `03-cost-controls.md` §9 (the worked month) |

## Verify in your tenant before presenting

The monitoring payload shape (item 9), the derived-failure signal (item 16), the double-signal question (item 24) and the flow count (item 13) are open until your tenant confirms them — see `07-verify-before-you-rely-on-it.md` §D and §E.
