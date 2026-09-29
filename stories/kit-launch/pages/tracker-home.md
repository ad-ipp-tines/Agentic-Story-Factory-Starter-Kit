# Page `tracker_home` (root) — the tracker's entry page

_Spec: REPO-DESIGN.md §7.5 C1–C2, §7.8 (`tracker_home`), §9.1 (Records, no Apps; and no Records), §9.3 (what a Page can render). Section C of `[KIT] 00 · Launch Storyworks`; built through Mode 2 with build prompt P-K13 (`../build-prompts.md`). This file is the specification the builder follows and the reviewer checks the export against; it is never a substitute for the export._

**What it is.** The only bookmarkable entry to the tracker when the App is not available: mid-story Pages (`tracker_view`, `add_use_case`, `gate_decision`) have per-run URLs (`PAGE.<name>`), so every visit starts here. The App's "Decide" and "Add a use case" fallbacks link to this Page as well (`kit/dashboard/app/lib/tracker.ts`, `TRACKER_HOME_PAGE`).

## Settings

| Setting | Value | Notes |
|---|---|---|
| Page name (action name) | `tracker_home` | snake_case; answers arrive under `tracker_home.body.<field>` |
| Kind | root Page (an entry point of section C) | |
| URL identifier | `storyworks-tracker` | the root URL is `https://<your-tenant>.tines.com/pages/storyworks-tracker`. Whether the identifier survives story import is **K8**; if it does not, set it again after import and tell the App's users |
| Access | **Only team members** (the default; never "Anyone with the link") | REPO-DESIGN.md §7.8, §13 row 6 |
| Anonymise submissions | **off** | downstream actions read the submitter's email from the headers (`gate_decision`'s `is_approver`) |
| Submission mode | **Move to next page** | how this behaves with actions between Pages is **K31**; the chain below puts actions between this Page and the next one |

## Elements

Element types are the documented set only (Heading, Rich text, Divider, Button, and — elsewhere — Table and Chart). Whether an element can be marked required is K31; this Page has no inputs to require.

| # | Element | Type | Body key | Content · condition |
|---|---|---|---|---|
| 1 | "Storyworks tracker" | Heading | — | — |
| 2 | Intro | Rich text | — | "The tracker of every story this team plans to build. **Git is the system of record** (`kit/tracker/backlog.yaml`); this view is its Records projection, current as of the last tracker sync. A decision made here is **provisional until its tracker PR merges**." |
| 3 | Counts (no Records only) | Rich text | — | Shown only when `RESOURCE.kit_config.entitlements.records` is false: one line per phase from `RESOURCE.kit_tracker_view.counts_by_phase` and the number of `open_gates`. **Whether a root Page's formulas can read a Resource is K31**; if they cannot, drop this element — `tracker_view` still shows the counts after a click |
| 4 | — | Divider | — | — |
| 5 | View backlog | Button | `button` | submission value `view` |
| 6 | Add a use case | Button | `button` | submission value `add` |
| 7 | Decide a gate | Button | `button` | submission value `gate` |
| 8 | Milestones | Button | `button` | submission value `milestones` |
| 9 | Footer | Rich text | — | "Decisions are checked against the approvers list. G2, G4, G5a and G5b are not decided here: they are a merge, a GitHub environment review and a change request." |

No element carries a credential, a token, a webhook URL or an email address.

## What follows the Page (section C)

| Button value | Next | Then |
|---|---|---|
| `view` | C2 `route_button` (Trigger on `tracker_home.body.button == "view"`) | **Records entitled:** C3 `list_rows` (HTTP Request, Records API List of `storyline_backlog` and of `storyline_milestones`, by the type ids in `RESOURCE.kit_state`, with `tines_api_kit`) → `to_table` (Event Transform: CSV text and counts by phase; K32) → the [`tracker_view`](tracker-view.md) Page. **No Records:** straight to `tracker_view`, which renders `RESOURCE.kit_tracker_view` |
| `add` | C2 (`== "add"`) | the `add_use_case` Page (C4, `add-use-case.md`) |
| `gate` | C2 (`== "gate"`) | C5 `list_open_gates` (List: `open_gate` in G0, G6, G7, GX, or `phase` parked) → the `gate_decision` Page (`gate-decision.md`) |
| `milestones` | C2 (`== "milestones"`) | the same C3 chain → `tracker_view`, which shows the milestones Table first for this button (element conditions on `tracker_home.body.button`) |

A Trigger that matches none of the four values ends the run with no action (a Page submitted without a button value).

## Test

`tests/expectations.yaml` for `kit-launch` carries the section C expectations; for this Page: each of the four submission values reaches exactly one branch, and `view` without Records never calls the Records API.

## Verify in your tenant

| Item | What to check |
|---|---|
| K8 | The URL identifier `storyworks-tracker` after import |
| K31 | Root-page formulas reading a Resource (element 3); "Move to next page" with actions between Pages |
