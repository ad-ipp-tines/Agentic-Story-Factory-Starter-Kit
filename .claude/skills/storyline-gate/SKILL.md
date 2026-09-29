---
name: storyline-gate
description: Records a repo-side human gate decision for one story — G3 plan approval always; G0, G6, G7, GB unpark and GX only on the Community path (no Records). Runs ./scripts/storyline gate, which asks the person to confirm on their own terminal. Use only when a person types /storyline-gate; never on the model's initiative.
disable-model-invocation: true
argument-hint: <slug> <gate> <decision>
allowed-tools: Bash(./scripts/storyline status *), Bash(./scripts/storyline next *), Read
---

# /storyline-gate — a person records a gate decision

**Inputs:** `$0` = story key · `$1` = gate · `$2` = decision. Spec: REPO-DESIGN.md §4.5 (gate rules 2–4), §6.1 (`gate`), `storyline/gates/README.md` and the gate's own file.

This skill is human-only (`disable-model-invocation: true`, P21). A decision typed into the chat is an instruction to you, **not a record**; the record is the `gate_decision` event this command writes, with the decider's **role**. You never decide, suggest or pre-fill a decision, and you never run the command for a gate or decision the person did not type.

## Which gates this records

| Gate | Decisions | When `./scripts/storyline gate` accepts it |
|---|---|---|
| **G3** plan approval | `approve` · `reject` | always — the story is in build and the build start event exists (`./scripts/storyline start <slug>`) |
| **G0** intake triage | `build` · `reject` · `park` | **Community path only** — with Records entitled, the `gate_decision` Page is G0's one instrument |
| **G6** go-live | `go_live` · `stay_shadow` | Community path only; `storyline/work/<slug>/go-live-review.md` must exist first |
| **G7** ownership review | `keep` · `rescope` · `retire` | Community path only |
| **GB** budget | `unpark` | Community path only; the story is parked |
| **GX** escalation | `resume` · `park` · `reject` | Community path only |

G1 is a script (`./scripts/storyline ready`); G2 and G4 are merges; G5a is the GitHub `production` environment's reviewer; G5b is the change request in Tines. The command refuses all of them. Decision words come only from `gate_info.<gate>.decisions` in `storyline/lifecycle/state-machine.yaml`.

## Steps

1. **Check the arguments.** Exactly three. If any is missing, ask the person for it; do not guess.
2. **Show the evidence.** Run `./scripts/storyline status $0` and `./scripts/storyline next $0`. Tell the person, in two or three lines: the story's phase, status and open gate; who decides this gate and with what evidence (the `gate` block of `next`, and the gate's file under `storyline/gates/`). If `$1` is not the open gate (G3 excepted), say so and stop.
3. **Ask for the role.** The decider's **role** (for example `security-automation`), never a name or an email. It goes into `--by`.
4. **Run the command** (it asks for permission):

   ```
   ./scripts/storyline gate $0 $1 $2 --by <role> --note "<one sentence from the person, optional>"
   ```

   It asks the person to type the story key on **/dev/tty**. Your Bash tool has no terminal to answer from, so when the command reports that no terminal is available, give the person the exact command above to run **in their own terminal**, and stop. Never try to supply the confirmation yourself (no pipes, no `script`, no `expect`, no `yes`).
5. **Report** what was recorded: the gate, the decision, the role, and the new phase / status / open gate from the command's output. For a Community-path gate, the command switched to the branch `tracker/<slug>-<gate>`: remind the person to commit the tracker row and `events.jsonl` there and open a PR — it needs an approving review from the gate's team in `storyline/gates/approvers.yaml`. G3's event travels in the build PR.
6. **Say what follows**, from the gate's file: after G3 `approve` the builder implements the plan; after G6 `go_live` the Resource `<slug>_rollout` is flipped `[BY HAND]`; after G7 `retire` the owner disables the story in Tines `[BY HAND]` and a PR removes it from `stories/_manifest.yaml`.

## Never

- Record a decision the person did not type, or change its words.
- Answer the /dev/tty confirmation, or edit `storyline/work/**`, `kit/tracker/**` or `.storyline/**` by any other route.
- Record G0, G6, G7, GB or GX when Records are entitled (the Page is the one instrument), or G1, G2, G4, G5a, G5b at all.
- Put a person's name or email anywhere; the record carries a role.
