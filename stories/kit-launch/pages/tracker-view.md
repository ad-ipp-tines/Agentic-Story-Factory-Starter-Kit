# Page `tracker_view` (mid-story) — the Page dashboard

_Spec: REPO-DESIGN.md §7.5 C3, §7.8 (`tracker_view`), §9.1 (Records, no Apps — and no Records), §9.3 (what a Page can render). Section C of `[KIT] 00 · Launch Storyworks`; built through Mode 2 with build prompt P-K13 (`../build-prompts.md`). Reached only from [`tracker_home`](tracker-home.md) (buttons `view` and `milestones`)._

**What it is.** The Page fallback dashboard for tenants with Records but without Apps, and the view of the `kit_tracker_view` mirror for tenants without Records. It is a snapshot: the view refreshes by clicking again from `tracker_home`, not live, and — as a mid-story Page — it has a per-run URL (`PAGE.tracker_view`) that is not bookmarkable. The App and the Tines Dashboard are the live views (`kit/dashboard/README.md`).

## Settings

| Setting | Value |
|---|---|
| Page name (action name) | `tracker_view` |
| Kind | mid-story Page (per-run URL `PAGE.tracker_view`) |
| Access | **Only team members** |
| Anonymise submissions | off |
| Submission mode (Back) | **Redirect to URL**: `https://<<RESOURCE.kit_config.tenant_host>>/pages/storyworks-tracker` — the `tracker_home` root Page (K8 for the identifier after import) |

## What feeds it (C3)

**Records entitled** — `list_rows` (HTTP Request, the Records API List of `storyline_backlog` and of `storyline_milestones`, page size 500, by the type and field ids in `RESOURCE.kit_state`, credential `tines_api_kit`, the scaffold's HTTP hardening) → `to_table` (Event Transform, message-only), which emits:

| Key | Content |
|---|---|
| `stories_csv` | a header row `key,title,phase,status,open_gate,owner,target_date,credit_estimate_monthly`, then one row per story, sorted by phase order then key; `target_date` as `YYYY-MM-DD`; values quoted |
| `milestones_csv` | a header row `id,title,status,due_date`, then the three milestones in the order day-1, week-1, week-4 |
| `counts_by_phase` | one number per phase, in the order of `RESOURCE.storyline_state_machine.all_phases` (zeros included) |
| `open_gates_md` | Markdown bullet lines: `<key> — <gate>: decided by <RESOURCE.storyline_state_machine.gate_decided_by[gate]>` |

The formula functions that build CSV text and the Table's parsing of it are **K32**; the Table element itself is built with `CSV_PARSE` from upstream data (§9.3).

**No Records** — no Records call: every element reads `RESOURCE.kit_tracker_view` instead (`stories_csv`, `milestones_csv`, `counts_by_phase`, `open_gates`), the mirror section B writes under the sync lock (B10). The two sources carry the same keys (`kit/resources/kit_tracker_view.example.json`), so each element's formula differs only in where it reads.

## Elements

Element types are the documented set only. Every element supports formulas and renders with the full upstream execution context.

| # | Element | Type | Content · condition |
|---|---|---|---|
| 1 | "Stories by phase" | Heading | — |
| 2 | Stories per phase | **Chart** (bar) | one bar per phase from `counts_by_phase`. Hidden when `tracker_home.body.button == "milestones"`. The Chart element's data formula shape is not in the kit's sources — VERIFY at build, alongside K32 |
| 3 | Backlog | **Table** | `CSV_PARSE(to_table.stories_csv)` — key · title · phase · status · open gate · owner · target date · monthly credit estimate. Hidden when `button == "milestones"`. No row selection |
| 4 | — | Divider | — |
| 5 | "Milestones" | Heading | — |
| 6 | Milestones | **Table** | `CSV_PARSE(to_table.milestones_csv)` — id · title · status · due |
| 7 | Open gates | Rich text | "**Open gates and who decides each**" + `open_gates_md`, then: "Decide G0, G6, G7, GX or an unpark from the tracker Page (**Decide a gate**). G2 and G4 are the merges of the design and build PRs; G5a is the GitHub production environment's reviewer; G5b is the change request in Tines." |
| 8 | Provisional note | Rich text | "Git is the system of record. A Tines-side decision is provisional until its tracker PR merges; a closed PR is reverted by the next nightly sync." |
| 9 | Back | Button | submission value `back` (Redirect to URL, above) |

Limits (§9.3): at most 100 looped elements (this Page has none); no drag-and-drop; no per-card detail page — the Table lists rows, and details come from the App or from git (`storyline/work/<slug>/`).

No element shows an email address: `owner` is a role, `actor_ref` is never listed, and approvers appear only as the role in `gate_decided_by`.

## Test

`tests/expectations.yaml` for `kit-launch` (section C): with the dev copy seeded from `tests/samples/tracker-sync.sample.json`, the `view` branch calls List twice, `to_table` emits the four keys with the header rows above, and the Page renders one Table row per story. On a tenant without Records the branch makes no Records API call and renders `kit_tracker_view`.

## Verify in your tenant

| Item | What to check |
|---|---|
| K32 | The formula functions that build CSV text for a Table |
| K31 | Element conditions reading `tracker_home.body.button` from an earlier Page |
| K8 | The `storyworks-tracker` identifier the Back button redirects to |
| K5 | Server-side filtering in `list_rows`; until confirmed it lists up to 500 rows and `to_table` sorts and filters |
