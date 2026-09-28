# G1 · Readiness — is the design ready to build?

| | |
|---|---|
| **Between** | design → build (first of two; G2 follows) |
| **Type** | deterministic |
| **Decided by** | `./scripts/sdlc ready <slug>` (allow), and `sdlc.yml` again on the design PR |
| **Evidence** | the design contract, the eval cases, the story folder, the manifest, the budget ceilings, the tenant config |
| **Instrument** | the script: exit 0 or 1, with a JSON result listing each check and its reason |
| **Recorded** | the JSON result attached to the design PR, and the `sdlc.yml` check. Never a `gate_decision` event (`approvers.yaml` sets `event_allowed: false`) |
| **Decisions** | `pass` · `fail` |

## The checks (every one must pass)

| # | Check | Reads |
|---|---|---|
| 1 | The contract block validates | the one ```` ```json story-contract ```` block in `sdlc/work/<slug>/design.md` against [`story-contract.schema.json`](../templates/story-contract.schema.json) |
| 2 | There is at least one testable acceptance criterion | `contract.acceptance_criteria` |
| 3 | Every criterion maps to at least one case, and there is at least one should-not case | `sdlc/work/<slug>/evals/cases.yaml` (`covers`, `should_trigger: false`) |
| 4 | Credentials and Resources are named in meta | `stories/<slug>/story.meta.yaml` vs `contract.credentials`, `contract.resources` |
| 5 | Every AI Agent action has a `budget_ref`, and the line exists in `policies/cost-ceilings.yml` | `contract.ai_agents[].budget_ref`, `.agents."<slug>/*"` |
| 6 | The manifest has an entry (`new: true`) | `stories/_manifest.yaml` `.stories.<slug>` |
| 7 | The contract's needs fit the tenant's entitlements | `kit/tenant/config.yaml` vs `contract.records`, `ai_agents`, `mode`, `access` |
| 8 | The touch set is respected | the branch diff vs [`touch-sets.yaml`](../lifecycle/touch-sets.yaml) (`design`) |
| 9 | `./scripts/sdlc estimate --check` passes | the cost checks `cost.4`–`cost.9` (REPO-DESIGN.md §5.3.7); they run again at G4 |
| 10 | The GB check passes, counting the verify-phase eval-run cost (cases × k × credits per run) against the dev team's ceiling | `policies/cost-ceilings.yml`, committed estimates in `kit/tracker/backlog.yaml` |
| 11 | Every spike's decision is recorded (`go` or `no_go`) | `sdlc/work/<slug>/spikes/*.md` front matter |
| 12 | The owner's WIP allows it: fewer than `wip_limit_per_owner` stories of this owner in build or verify on `main` | `kit/tracker/backlog.yaml` on `main` |

Checks 11 and 12 follow from REPO-DESIGN.md §4.4 (a design is not final until its spikes are decided) and §4.2 (the WIP invariant). A failing check 10 or 12 opens [GB](GB-budget.md) rather than just failing.

## After the result

- **Pass** → `./scripts/sdlc advance <slug>` (ask) writes `phase: build, status: active` on `design/<slug>`, and the design PR opens for [G2](G2-design-approval.md).
- **Fail** → the JSON names each failing check. `./scripts/sdlc next` dispatches the specialist that owns the gap (the architect for the contract, the eval author for coverage) or names the human fix. Nothing moves.
