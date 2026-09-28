# 07 · improve — failures become evals; evals and lessons become skills

_Phase `improve` in [`state-machine.yaml`](../lifecycle/state-machine.yaml) · Exit: the checks `retro_closed`, `change_needed` or `retire_candidate` · Spec: REPO-DESIGN.md §4.4 (07 improve)._

## Purpose

Close the flywheel (P15, P24): what went wrong in production becomes an eval case, stable cases become the regression suite, and repeated lessons become changes to the Tines Agent Skills, the prompt pack or the field guide — each checked on cases that were not used to derive it.

## Entry criteria

`improve_trigger` fired (see [06 operate](06-operate.md), "Leaving operate"). The row is `phase: improve, status: active`. Repo-side work happens on the branch `improve/<slug>`.

## Work

1. **The retro draft.** On a Records tenant with the AI Agent action, the Tines-side `retro_writer` ([`runtime-retro-writer.md`](../agents/runtime-retro-writer.md); tool-less, fast model pinned, skill `story-retrospective`) drafts it from the story's `ops_findings` and `ops_alerts` rows for the window, the `sdlc_events` gate history and credit rows, and the design estimate. The draft reaches git as `sdlc/work/<slug>/retro.md` through the tracker PR. Otherwise the orchestrator fills [`retro.md`](../templates/retro.md) with the human.
2. **The human completes `retro.md`**: confirms or overrides `keep_or_change` (the draft is a proposal), checks the evidence refs, and sets `closed: true`.
3. **`eval-curator`** ([role card](../agents/eval-curator.md)) turns each failure mode into eval cases (`suite: capability`) in `sdlc/work/<slug>/evals/cases.yaml` and `stories/<slug>/tests/cases/`, and graduates stable capability cases into the regression suite ([`sdlc/evals/regression/README.md`](../evals/regression/README.md)). It never deletes a regression case without a reason recorded in the retro. After it is applied, `retro.md` gets `curated: true`.
4. **`skill-curator`** ([role card](../agents/skill-curator.md)) runs only when the retro lists skill suggestions. It proposes edits to `tines-skills/**`, the prompt pack or [`sdlc/field-guide.md`](../field-guide.md), each validated on **held-out** agent evals (not the ones used to derive it); `sdlc.yml` fails a skill PR whose skill has no held-out cases file in `sdlc/evals/skills/`. Those PRs follow the scaffold's `skills.yml` path, with a security-platform CODEOWNER review. It never changes a skill in response to a single event.

## Exit criteria

`./scripts/sdlc advance <slug>` (ask) applies the first check that passes:

| Check | Evidence | Next |
|---|---|---|
| `change_needed` | `retro.md` `keep_or_change == change` | → **design**, a new iteration (attempt resets to 0) with the retro as input |
| `retire_candidate` | `keep_or_change == retire_candidate` | → **operate** with G7 open; G7 decides |
| `retro_closed` | `retro.md` marked closed, and the eval cases it asked for are merged and passing | → **operate** (the status it had before) |

## Artifacts

| Artifact | Path | Written by |
|---|---|---|
| Retro | `sdlc/work/<slug>/retro.md` | `retro_writer` via the tracker PR, then the human |
| New cases | `sdlc/work/<slug>/evals/cases.yaml`, `stories/<slug>/tests/cases/*.json` | `apply` ← `eval-curator` |
| Skill, prompt-pack and field-guide edits | `tines-skills/**`, `.claude/skills/tines-build-story/references/prompt-pack.md`, `sdlc/field-guide.md` | `apply` ← `skill-curator`, merged by PR |

## Templates

[`retro.md`](../templates/retro.md) · [`eval-cases.yaml`](../templates/eval-cases.yaml)

## Specialists

| Specialist | Where | Tier | Tools |
|---|---|---|---|
| `retro_writer` | Tines, `[KIT] 00` section D | fast, pinned | none |
| `eval-curator` | IDE | standard, `maxTurns` 15 | `Read, Grep, Glob` |
| `skill-curator` | IDE | standard, `maxTurns` 15 | `Read, Grep, Glob` |

## Gate

None of its own. It hands off to G7 when the retro proposes retirement, and to design (G1, G2 again) when it asks for a change.

## Failure modes

| Symptom | Cause | What happens |
|---|---|---|
| `retro_closed` never passes | a requested case fails on the live design | that is a `change`, not a `keep`: set `keep_or_change: change` and start a new iteration |
| The retro draft cites instructions found in logs | untrusted content in the evidence | the human ignores them; an embedded instruction is itself a finding (P16) |
| A skill change passes only the cases it was derived from | overfitting | the held-out cases in `sdlc/evals/skills/` fail it in `sdlc-evals.yml`; the PR does not merge |
| The field guide grows past its budget | lessons are not being deduped | `skill-curator` merges or drops entries; the budget is in [`field-guide.md`](../field-guide.md) |
