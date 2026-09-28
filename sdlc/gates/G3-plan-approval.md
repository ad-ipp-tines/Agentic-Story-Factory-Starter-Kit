# G3 · Plan approval — the human says yes to the builder's numbered plan

| | |
|---|---|
| **Between** | inside build (no phase change) |
| **Type** | human |
| **Decided by** | the person driving the build session |
| **Evidence** | the builder's numbered plan: each action's type, name and field names, credentials by name, the failure path and the Note (step 2 of `/tines-build-story`) |
| **Instrument** | `/sdlc-gate <slug> G3 approve\|reject` — a human-only skill (`disable-model-invocation: true`) that runs `./scripts/sdlc gate` (ask) and asks for a confirmation on `/dev/tty` |
| **Recorded** | a `gate_decision` event with `gate: G3`, `actor_kind: human`, `actor` = the person's role, in `sdlc/work/<slug>/events.jsonl`. **Never** the builder's own report: `build-log.md` is never parsed |
| **Decisions** | `approve` · `reject` |

## Why it is a gate

The plan is the last point where a wrong design is cheap to fix: nothing has been built in the dev team yet. The scaffold's builder already stops and waits for a yes (AGENTS.md §3 rule 2); G3 turns that yes into evidence the lifecycle can check. The check `build_evidence` requires a G3 `gate_decision` event **after** the build start event, so a build cannot leave the phase without it.

## What the person checks

1. The plan implements the contract in `sdlc/work/<slug>/design.md` and nothing else (out of scope stays out).
2. Every action is named by the conventions (`normalize`, `is_<condition>`, `result`, `error`), and every HTTP Request action carries the hardening.
3. Credentials and Resources are referenced by name and exist in the dev team.
4. AI Agent actions have their output schema, the Trigger after them and the field it branches on.
5. On rework: the plan fixes only the findings in the rework package.

## Recording it

```
/sdlc-gate <slug> G3 approve
```

`reject` sends the builder back to re-plan in the same session (the story stays in build). The event reaches `main` inside the build PR, and `sdlc.yml` requires an approving review from the G3 team in [`approvers.yaml`](approvers.yaml). A "yes" typed into the chat is an instruction to the builder, not a record; without the event, `build_evidence` fails.
