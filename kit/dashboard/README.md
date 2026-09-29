# `kit/dashboard/` — the dashboard, by entitlement

_Spec: REPO-DESIGN.md §9 (all of it), §7.2 A23–A24, §7.5 (section C), §7.8 (the Page specs)._

Every dashboard here reads the **Records projection** of the tracker (`storyline_backlog`, `storyline_events`, `storyline_milestones`) or, without Records, its Resource mirror. Git stays the system of record (`kit/tracker/backlog.yaml`), and what any dashboard shows is current as of the last tracker sync. **No dashboard changes the lifecycle on its own:** a phase moves only through a gate — a Page decision, a merge, a change request — and reaches git by pull request.

## Which dashboard you get

The kit reads the tenant's own answers on the kickoff Page (`ent_records`, `ent_apps`) and never assumes a plan.

| Tenant has | Dashboard | Created by |
|---|---|---|
| **Records + Apps** (Business or Enterprise with the Apps add-on) | **The App "Storyworks"** ([`app/`](app/App.tsx)) as the working surface, **plus** a Tines Dashboard for scheduled email snapshots | A24 (create + push files; publishing and endpoint wiring are `[BY HAND]`); A23 |
| **Records, no Apps** | **Pages** — `tracker_home` → `tracker_view`, `add_use_case`, `gate_decision` — **plus** a Tines Dashboard | the kit story itself (section C); A23 |
| **No Records** (the manual Community path) | A `tracker_home` Page rendering the `kit_tracker_view` Resource mirror (K31), and the YAML in GitHub | section B writes the mirror |

Apps limits are a **CONFLICT (K19)**: one source gives 3 on Business, 5 on Enterprise and none on Community; another gives 3 on Community, 5 on Business and "contact" on Enterprise.

## The App (`app/`)

React 19 + Tailwind in a sandboxed iframe; `App.tsx` is the entry (its name cannot change) and routes go through TinesRouter.

- **Reads** Records and Resources **directly** through the read-only `@tines/apps` hooks — `useRecords` (20 per page by default, 500 max), `useRecordsQuery` (up to 1,000 rows per query), `useResource` — which run **as the viewer**, with the viewer's own permissions.
- **Writes and external calls** go only through the three **app endpoints** in section C, each a Webhook entry plus a message-only Event Transform exit, 30 s timeout (under 1 s recommended): [`app/endpoints.md`](app/endpoints.md).
- **Sandbox:** no network calls from app code, no `localStorage` or cookies, no `crypto.randomUUID`, no embedding outside Tines, no anonymous access. **Access:** anyone on the team (the default), anyone in the tenant, specific people, or SSO. **Files:** tsx, ts, jsx, js and json only; 128 KB per file; 5 MB per build.

| Route | File | Renders | Data |
|---|---|---|---|
| Backlog | [`routes/Backlog.tsx`](app/routes/Backlog.tsx) + [`components/PhaseBoard.tsx`](app/components/PhaseBoard.tsx) | One column per phase; each card shows key · title · mode badge · owner · target date · open gate; filters by owner, tier and mode; an "Add a use case" form | `useRecords(storyline_backlog)`; phase names from `useResource(storyline_state_machine)`; seed ids from `kit_catalog`; the form → `app_add_use_case` |
| Story detail | [`routes/StoryDetail.tsx`](app/routes/StoryDetail.tsx) + [`components/Timeline.tsx`](app/components/Timeline.tsx) | The transition timeline, gate decisions, the brief and retro drafts, planner proposals, links to the PRs and the change request | `useRecordsQuery(storyline_events, story_key)`; the row's ARTIFACT and JSON fields |
| Gates | [`routes/Gates.tsx`](app/routes/Gates.tsx) | Every open gate with who decides it and its one instrument. For G0, G6, G7, GX and the GB release it offers **"Decide"**, a deep link to the tracker Page (until K18 confirms that an app endpoint receives the viewer's identity); for G2 and G4 it links to the PR; for G5b it shows the change request | `useRecords(storyline_backlog)`, `open_gate ≠ none` |
| Milestones | [`routes/Milestones.tsx`](app/routes/Milestones.tsx) | The day-1 / week-1 / week-4 checklist with status, due date and evidence | `useRecords(storyline_milestones)` |
| Costs | [`routes/Costs.tsx`](app/routes/Costs.tsx) + [`components/BarChart.tsx`](app/components/BarChart.tsx) | Monthly credit estimate vs credits used per story, as a hand-written SVG bar chart (no chart dependency assumed); custom- or local-provider stories show "not metered in credits" (`billed_cost`, K25) | estimates from Records; actuals from `app_costs` → `GET /api/v1/ai_usage` (scope K38) |

**It cannot** write Records directly, run on a schedule, show data the viewer may not read, work outside Tines, or notify anyone. Notifications come from the kit story.

**One file touches the platform.** [`app/lib/tracker.ts`](app/lib/tracker.ts) is the only file that imports `@tines/apps`. The design's sources name the hooks and TinesRouter but not their argument or result shapes, how an App calls an app endpoint, or whether nested file paths are accepted; every such line is marked **VERIFY K18** there. The routes and components receive plain typed rows, so resolving K18 changes that one file. Until the endpoint call is wired, the App reads everything and falls back to the tracker Page for every write.

**Publishing (`[BY HAND]`).** A24 creates the App and pushes its draft files (`POST /api/v1/apps`, then `PUT /api/v1/apps/{id}/files` with the bundle's `app_files`). Enable Apps for the ops team at `/settings/apps` (if entitled), publish the App in the UI — or through Mode 2, whose App tools the MCP docs page does not list yet (K18) — and wire the three endpoints (Interfaces → App endpoints). Pushing files through the API avoids App-builder chats, which spend Workbench (smart-model) credits; whether API pushes cost anything is K18.

## The Page fallback (section C)

`stories/kit-launch/pages/tracker-home.md` and `tracker-view.md` specify it; `add_use_case` and `gate_decision` are in the same folder.

- **Elements:** Heading, Rich text (CommonMark), Divider, **Table** (built with `CSV_PARSE` from upstream data; optional row selection), **Chart** (line, bar, pie), Image, File and Buttons. Every element supports formulas, and a Page renders with the full upstream execution context.
- **URLs:** mid-story Pages (`tracker_view`, `add_use_case`, `gate_decision`) have per-run URLs (`PAGE.<name>`), so the only bookmarkable entry is the root `tracker_home`. The view refreshes by clicking again, not live.
- **Limits:** at most 100 looped elements; no drag-and-drop; no per-card detail page.

## The Tines Dashboard ([`dashboards/storyworks.dashboard.json`](dashboards/storyworks.dashboard.json))

**A SKELETON until the §15.6 maintainer release** builds the dashboard once by hand over the three Record types in a maintainer dev team, exports it, and saves the export in its place. The skeleton lists the intended charts without guessing the export's keys; the release check fails while its label remains. A23 imports it with `POST /api/v1/dashboards/import` `{team_id, data, mode: "new", new_name: "Storyworks"}`; record charts refer to types by `record_type_name`, and whether the import resolves them against types that already exist in the team is **K17** (else build it by hand).

| Chart | Type | Record type · fields |
|---|---|---|
| Stories by phase | bar | `storyline_backlog` · count by `phase` |
| Phase by owner | stacked | `storyline_backlog` · `owner` × `phase` |
| Open gates | bar | `storyline_backlog` · count by `open_gate` (excluding `none`) |
| Milestones | pie | `storyline_milestones` · count by `status` |
| Credit estimate by story | bar | `storyline_backlog` · `credit_estimate_monthly` by `story_key` |
| Crew member runs and credits over time | bar | `storyline_events` · `specialist_run`, sum of `credits_used` by creation period (week if the chart can group by time, else day; the export decides) |
| Notes | Note | Gate rules and who decides; the rules live in `storyline/gates/README.md` |

Dashboards chart **Records and Cases only** (Charts over records, Case views — unused here — and Markdown Notes). Record charts live only on **team** dashboards, so this one sits in the ops team. Limits: 20 dashboards per team, 30 charts per dashboard; series caps bar 100, pie 50, stacked 25. Snapshots: email on a schedule, 10 per dashboard, 50 recipients each. `JSON` fields are not filterable, so every chart uses `TEXT_ENUM`, `NUMBER` or `TIMESTAMP` fields.

## Side by side

| Capability | App | Page | Dashboards |
|---|---|---|---|
| Live view without a click | ✓ | root page only | ✓ |
| Board, per-story detail, timeline | ✓ | — (Table only) | — |
| Charts | hand-drawn SVG | line, bar, pie | bar, pie, stacked |
| Decide a gate | via the Page (until K18) | ✓ | — |
| Add a use case | ✓ (endpoint) | ✓ | — |
| Scheduled email snapshot | — | — | ✓ |
| Needs | the Apps add-on + Records | Records (or the Resource mirror) | Records (Advanced Workflows) |

## Verify in your tenant

| Item | Check | Until then |
|---|---|---|
| K18 | Hook and TinesRouter shapes; the App's endpoint-call primitive; viewer identity at an endpoint; nested paths in `PUT …/files`; packages; credits for API pushes | `lib/tracker.ts` falls back to the Page for writes; flip `ROUTER_MODE` to `"hash"` if TinesRouter's props differ |
| K17 | Dashboard import resolves `record_type_name` against existing types | Build the dashboard by hand |
| K19 | Apps limits on your plan | Read `/settings/apps` |
| K31, K32 | Page formula behaviour; a Table from CSV text built by formula | The Page fallback's Tables and root-page counts |
| K38 | `ai_usage` rows a team-scoped Viewer key sees | Costs shows "n/a" |
