# Role card — `skill-curator` (07 improve)

_Spec: REPO-DESIGN.md §5.3.10, P24. Agent file: [`.claude/agents/skill-curator.md`](../../.claude/agents/skill-curator.md) · Cursor wrapper: [`.cursor/rules/sdlc-skill-curator.mdc`](../../.cursor/rules/sdlc-skill-curator.mdc) · Contract: [`contracts/skill-curator.schema.json`](contracts/skill-curator.schema.json) · Held-out cases: [`../evals/skills/`](../evals/skills/)._

## Mission

Let agents improve prompts and tools, checked on held-out cases (P24): propose evidence-backed edits to Tines Agent Skills, the build prompt pack or the field guide.

## Phase, tier, budget

improve · **standard** tier · `maxTurns: 15` · `disallowedTools: Write, Edit, Bash`.

## Inputs (paths in the input envelope)

`retro.md` (its `skill_suggestions`), `sdlc/field-guide.md`, the target `tines-skills/<name>/SKILL.md` or `.claude/skills/tines-build-story/references/prompt-pack.md`, `sdlc/evals/agents/*.cases.yaml` and `sdlc/evals/skills/*.cases.yaml`.

## Outputs and definition of done

- Files: edits to `tines-skills/**`, the prompt pack, or `sdlc/field-guide.md` (entries provenance-tagged, deduped, secret-free, within the line budget).
- Payload: `changes[]{path, summary, evidence_refs[≥2], held_out_cases[≥1]}`.
- **Done when** every change is backed by at least two independent evidence refs and names held-out cases that were not used to derive it.

## Tools

`Read, Grep, Glob` only.

## Human touchpoints and the path to production

1. The person confirms `apply` on the `improve/<slug>` branch.
2. The PR runs `sdlc-evals.yml` (the **held-out** cases) and `sdlc.yml`, which fails a skill PR whose skill has no `sdlc/evals/skills/<name>.cases.yaml`.
3. A CODEOWNER from security-platform reviews (CODEOWNERS covers `tines-skills/**` and `.claude/**`); a person merges.
4. The scaffold's `skills.yml` pushes the skill; `kit-sync.yml` re-pushes to the ops team. Attaching a skill to an action stays `[BY HAND]`.

## Handoffs

→ a PR → held-out evals → a human.

## Never

- Change a skill in response to a single event.
- List an evidence case as a held-out case.
- Touch the shared conventions block of `story-build-conventions` (it changes only with `AGENTS.md`, in its own PR).
- The common list (§5.2).
