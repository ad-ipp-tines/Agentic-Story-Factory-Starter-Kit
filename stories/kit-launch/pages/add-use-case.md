# Page `add_use_case` (mid-story) — intake from Tines

_Spec: REPO-DESIGN.md §7.8 (`add_use_case`), §7.5 C4, §4.4 (00 intake). Section C of `[KIT] 00 · Launch Storyworks`; built through Mode 2 with build prompt P-K13 (`../build-prompts.md`). Reached from [`tracker_home`](tracker-home.md) (button `add`)._

**What it is.** A person adds a story to the backlog without leaving Tines. The submission becomes an `storyline_backlog` row in `intake` (provisional: `pending_repo_sync: true`), the `brief_writer` drafts its intake brief when the AI Agent action is entitled, and the row reaches `kit/tracker/backlog.yaml` through the next tracker PR a person merges. The App's intake form (`app_add_use_case`) runs the same chain.

## Settings

| Setting | Value |
|---|---|
| Page name (action name) | `add_use_case` |
| Kind | mid-story Page (per-run URL `PAGE.add_use_case`) |
| Access | **Only team members** |
| Anonymise submissions | **off** — `normalize_use_case` reads the submitter's email from the headers (in-tenant audit and refusal notices only; never committed) |
| Submission mode | **Show success message**: "Added. The story is in intake and reaches git with the next tracker PR. When the AI Agent action is enabled, an intake brief is drafted for the G0 decision." |

## Elements

| # | Element | Type | Body key | Content · condition |
|---|---|---|---|---|
| 1 | "Add a use case" | Heading | — | — |
| 2 | Intro | Rich text | — | "Describe the problem, not a solution. Do not paste tokens, keys, passwords, customer data or email addresses: the text is stored in the tracker and reaches git." |
| 3 | Title | Short text | `title` | A short imperative phrase. The G0 decider gives it its `[PREFIX] NN` |
| 4 | Use case | Long text | `use_case` | What happens today, what should happen, how often. **Untrusted text**: stored, never interpreted (§13 row 13) |
| 5 | Owner role | Short text | `owner_role` | A team role (for example `security-automation`, `ops`, `platform`), **never a person** — an `@` is refused |
| 6 | Target date | Date or time | `target_date` | Optional; stored in UTC |
| 7 | Library seed | Option | `library_seed_id` | The catalog's ids with their names (`RESOURCE.kit_catalog.library_seeds`) + `none`. Whether an Option list can come from a Resource is **K31**; if not, the list is typed from `kit/catalog/library-seeds.yaml` at build and kept equal by the reviewer. **No free text**: only verified ids can be cited |
| 8 | Mode hint | Option | `mode_hint` | `none \| sub-story \| mode-1-preset \| mode-3-agent \| mode-4-server \| unknown` — a hint for the designer, never a decision; `unknown` is stored as `none` |
| 9 | Add | Button | `button` | submission value `add` |

## What follows the Page (C4)

`add_use_case` → `normalize_use_case` → `is_valid_use_case` (required fields; no `@` in the owner; no token pattern — the A3 list; the seed in the catalog) → `list_keys_for_use_case` → `assign_use_case_key` (the title lowercased and hyphenated, ≤ 48 characters, `-2`… on a collision) → `use_case_create_row` (`phase: intake`, `specialist_due: brief-writer` when entitled, `pending_repo_sync: true`, `pending_base_rev: 0`, `rev: 0`, `outbox_seq: 1`) → `use_case_log_event` → section D (`brief_writer`). A refusal (`use_case_refused`) is emailed to the submitter with the rule that failed, never the offending value.

## Test

In the dev copy: submitting a valid use case creates exactly one row in `intake` with `pending_repo_sync: true`; a use case containing a token-shaped string creates nothing; the next `tracker-pull.yml` pull returns the row with every mirrored field in `changes{}` (`../sections/E-tracker-outbox.md`). The App path is `../tests/expectations.yaml` → `app_add_use_case_*`.

## Verify in your tenant

| Item | What to check |
|---|---|
| K31 | Option lists from a Resource; required fields; the submitter header key |
| K29 | ARTIFACT capacity for long use-case text |
