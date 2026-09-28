# Gates — who decides what, with which evidence, recorded where

_Spec: REPO-DESIGN.md §4.5. Gate names come from [`sdlc/lifecycle/state-machine.yaml`](../lifecycle/state-machine.yaml) (`gates`, `gate_info`, `instruments`); nothing here renames them. If you approve gates, this is the page to read first (REPO-DESIGN.md §1.2)._

A gate is the point where a story may not move until a decision is recorded. Some gates are code, some are people, and one is layered. **Agents never decide a gate**, never merge and never promote (REPO-DESIGN.md §5.2, the common never-list).

## The eleven gates

| Gate | Between | Type | Decided by | Evidence the decider sees | Recorded by |
|---|---|---|---|---|---|
| [**G0** Intake triage](G0-intake-triage.md) | intake → discover / rejected / parked | **human** | The story owner or an approver listed for G0 | `intake.md` (the draft brief) | the `gate_decision` Page (or the App's deep link to it) when Records are entitled; `/sdlc-gate` only on the Community path |
| [**G1** Readiness](G1-readiness.md) | design → build | **deterministic** | `./scripts/sdlc ready` (also `sdlc.yml` on the design PR) | the checks in G1-readiness.md | the script's JSON result, attached to the PR |
| [**G2** Design approval](G2-design-approval.md) | design → build | **human** | A CODEOWNER of the story's prefix, not the author | The design PR: contract, evals, meta, budget line | the merge (the tracker change rides in the PR) |
| [**G3** Plan approval](G3-plan-approval.md) | inside build | **human** | The person driving the build session | The builder's numbered plan (action type, name, fields) | `/sdlc-gate <slug> G3 approve` → a `gate_decision` event with `actor_kind: human` in `events.jsonl` (never the builder's own report) |
| [**G4** Verify and merge](G4-verify-and-merge.md) | verify → ship | **deterministic + model + human** | `sdlc.yml` (which calls `lint.yml` and `review.yml`), `verify-report.json`, the human QA verification line, a CODEOWNER, and a human merge (never the author) | PR checks, findings, QA results, cost projection | the merge |
| [**G5a** First ship](G5-change-request-approval.md) | ship → operate, when the manifest says `new: true` | **human, in GitHub** | A required reviewer of the GitHub `production` environment, before `ship.yml`'s `mode: new` import; then change control on the new story `[BY HAND]` | The PR and the story's export | `ship.md`, written by CI through a PR |
| [**G5b** Change request](G5-change-request-approval.md) | ship → operate | **human, in Tines** | The named approver (no approver key in CI) | The live-vs-draft diff (`cr-view`) and the PR | `ship.md`, written by CI through a PR; `sdlc advance` reads it |
| [**G6** Go-live](G6-go-live.md) | operate shadow → live | **human** | Owner + an approver listed for G6 | `go-live-review.md` | the `gate_decision` Page when Records are entitled; `/sdlc-gate` only on the Community path |
| [**G7** Ownership review](G7-ownership-review.md) | operate → retired or re-scope | **human** | Owner + platform | Usage, findings, cost vs estimate | the `gate_decision` Page when Records are entitled; `/sdlc-gate` only on the Community path |
| [**GB** Budget](GB-budget.md) | at any dispatch boundary | **deterministic** to open, **human** to release | `sdlc ready` (design), `sdlc_limits` (Tines), the ops sweep (operate) | Ceilings in `policies/cost-ceilings.yml` and `sdlc_limits` | tracker `parked` + event |
| [**GX** Escalation](GX-escalation.md) | rework cap reached · two failed corrections · `needs_human` · critic disagreement · schema failure, in any phase | **human** | Owner | The rework history, findings, transcripts | the `gate_decision` Page when Records are entitled; `/sdlc-gate` only on the Community path |

## The strip

```
intake ─G0─▶ discover ─check─▶ design ─G1─G2─▶ build (G3 inside) ─check─▶ verify ─G4─▶ ship ─G5a│G5b─▶ operate ─trigger─▶ improve
                                                                                                      │ G6: shadow ▶ live      │
                                                                                                      │ G7: keep·rescope·retire└─▶ operate │ design
any phase: GX ▶ blocked (owner decides)        GB ▶ parked (a human unparks)
```

## Human gates vs deterministic gates

- **Deterministic gates are scripts and CI.** G1 is `./scripts/sdlc ready`; GB opens from a script or a Tines Trigger; the deterministic half of G4 is `sdlc.yml`, `lint.yml` and `verify-merge`. They run the same way every time and print one PASS/FAIL line per check.
- **Model checks are never gates on their own.** `tines-reviewer`, `security-reviewer` and `story-qa` produce findings. Their findings feed G4's deterministic merge rule; a person still merges.
- **Human gates are merges, change-request approvals, Page submissions or `/sdlc-gate` runs**, and every human decision records the decider's **role** — never a name, never an email in git.

## The rules

1. **One open gate per story.** Gates never expire, but the dispatch sweep (`[KIT] 00` D7) re-nudges after `gate_nudge_days` (default 3).
2. **Authority comes from versioned files, never from chat replies.**
   - In git: CODEOWNERS, branch protection and [`approvers.yaml`](approvers.yaml) (gate → GitHub team, owned by security-platform). `sdlc.yml` rejects a PR that adds a `gate_decision` event unless that gate's team has approved the PR.
   - In Tines: the `sdlc_approvers` Resource, checked against the submitter's email in the Page headers on every decision. Because the kickoff submitter fills that Resource and any ops-team Editor can edit it, the `gate_decision` Page's access is set to **Via SSO**, restricted to an approvers SSO group, where the tenant has SSO group-based page access (an admin turns it on in the Authentication settings, `[BY HAND]`); otherwise `sdlc_approvers` is locked once VERIFY K40 is resolved.
3. **Each gate type has its own instrument, and each Tines-side gate has exactly one.** The Page when Records are entitled; `/sdlc-gate` only on the Community path. `./scripts/sdlc gate` refuses the other case, and it asks for an interactive confirmation on `/dev/tty`, which a model's Bash call cannot supply. `/sdlc-gate` carries `disable-model-invocation: true` (P21).
4. **Destructive or production-changing gates are human-only:** G2, G4, G5a, G5b, G6, G7, and every disable.
5. **GB fires only at dispatch boundaries,** never in the middle of a phase. It warns at 80 % of a ceiling and parks at 100 %. Tines alerts at 80 % and 100 % by default; the stops are the per-action Disable-action token alert and the kit's `sdlc_limits` caps and kill switch.

## Where a decision is recorded

| Gate | Git | Tines |
|---|---|---|
| G0, G6, G7, GX, GB release | a `gate_decision` event, arriving through the tracker PR (Records) or a `tracker/<slug>-<gate>` PR from `/sdlc-gate` (Community) | the `sdlc_backlog` row (`pending_repo_sync: true`) and an `sdlc_events` row with `actor_ref` = the approver's email (never sent to git) |
| G1 | the `sdlc.yml` check and the JSON attached to the design PR | — |
| G2, G4 | the merge; the tracker change and a `transition` event ride in the PR | through Flow 1 after the merge |
| G3 | a `gate_decision` event in the build PR | through Flow 1 after the merge |
| G5a, G5b | `ship.md` + a `gate_decision` event, through CI's evidence PR | the change request itself (G5b) |

The decision words each gate may record are `gate_info.<gate>.decisions` in the state machine; `./scripts/sdlc gate` and the Page refuse any other word.
