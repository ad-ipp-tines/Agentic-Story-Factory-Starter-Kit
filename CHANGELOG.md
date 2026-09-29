# Changelog

## Tines Storyworks naming

Names only. No behaviour, logic, thresholds or gate semantics change.

| Old | New |
|---|---|
| Agentic Story Factory Starter Kit | Tines Storyworks Starter Kit |
| Agentic Story Factory | Tines Storyworks |
| story factory | Storyworks |
| Story Development Life Cycle | the Storyline |
| SDLC | Storyline |
| sdlc | storyline |
| folder `sdlc/` | `storyline/` |
| `sdlc/agents/` | `storyline/crew/` |
| orchestrator | showrunner |
| specialist / specialists / specialist agents | crew member / crew / crew members |
| the handoff envelope; `envelope.schema.json` | the baton; `baton.schema.json` |
| `sdlc/field-guide.md`; field guide | `storyline/logbook.md`; logbook |
| brain (and any brain-and-body metaphor) | the Storyline (how a story moves); the tenant (where stories run) |
| eval case field `case_id` | `eval_id` |
| `scripts/sdlc`; `scripts/sdlc_*.py` | `scripts/storyline`; `scripts/storyline_*.py` |
| `.claude/skills/sdlc/`; `.claude/skills/sdlc-gate/`; `/sdlc`; `/sdlc-gate` | `.claude/skills/storyline/`; `.claude/skills/storyline-gate/`; `/storyline`; `/storyline-gate` |
| `.cursor/rules/sdlc.mdc`; `sdlc-<agent>.mdc` | `.cursor/rules/storyline.mdc`; `storyline-<agent>.mdc` |
| `.github/workflows/sdlc.yml`; `sdlc-evals.yml` | `storyline.yml`; `storyline-evals.yml` |
| Records types `sdlc_backlog`, `sdlc_events`, `sdlc_milestones` | `storyline_backlog`, `storyline_events`, `storyline_milestones` |
| Resources `sdlc_state_machine`, `sdlc_limits`, `sdlc_approvers`, `sdlc_sync_lock` | `storyline_state_machine`, `storyline_limits`, `storyline_approvers`, `storyline_sync_lock` |
| env var `SDLC_ENFORCE`; local dir `.sdlc/` | `STORYLINE_ENFORCE`; `.storyline/` |
| story slug `kit-factory`; `[KIT] 00 · Run the story factory` | `kit-launch`; `[KIT] 00 · Launch Storyworks` |
| `docs/08-agentic-story-factory.md` | `docs/08-storyworks.md` |
| merger (the person who merges) | the person who merges; variable `merged_by` |
| lifecycle acronym in the Glean and Arthur source titles | the same titles in words, with no acronym |
