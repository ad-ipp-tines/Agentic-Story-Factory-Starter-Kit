# Page `gate_decision` (mid-story) — decide a Tines-side gate

_Spec: REPO-DESIGN.md §7.8 (`gate_decision`), §7.5 C5, §4.5 (gates, instruments, rule 2 on authority), §6.5 (field ownership, provisional state), §13 row 6. Section C of `[KIT] 00 · Launch Storyworks`; built through Mode 2 with build prompt P-K13 (`../build-prompts.md`). Reached from [`tracker_home`](tracker-home.md) (button `gate`), and from the App's "Decide" deep link until K18 is confirmed._

**What it is.** **The one instrument** for the gates decided in Tines when Records are entitled: **G0** intake triage, **G6** go-live, **G7** ownership review, **GX** escalation, and the **unpark** that releases a GB park. Each decision is checked against the approvers in the `storyline_approvers` Resource, applied as a **provisional** change on the row, logged with the approver's **role** (the email stays in the tenant), and reaches git through the next tracker PR a person merges. On the Community path these gates are decided with `/storyline-gate` instead, and `./scripts/storyline gate` refuses them whenever Records are entitled — the two sides never decide the same gate.

**Not here:** G1 (a script), G2 and G4 (merges), G3 (`/storyline-gate` in the build session), G5a (the GitHub `production` environment's reviewer) and G5b (a change request in Tines).

## Settings

| Setting | Value | Notes |
|---|---|---|
| Page name (action name) | `gate_decision` | answers under `gate_decision.body.<field>` |
| Kind | mid-story Page (per-run URL `PAGE.gate_decision`) | reached after `list_open_gates` |
| Access | **Via SSO**, restricted to the **approvers SSO group**, where the tenant has SSO group-based page access (an admin turns it on in the Authentication settings `[BY HAND]`); otherwise **Only team members**, and `storyline_approvers` is locked once K40 is resolved | §4.5 rule 2: the kickoff submitter fills `storyline_approvers` and any ops-team Editor can edit it, so the Page itself is narrowed too |
| Anonymise submissions | **off** — `is_approver` compares the submitter's email from the Page headers with `RESOURCE.storyline_approvers[<gate>]` | the email is kept only in `storyline_events.actor_ref` (in-tenant audit) |
| Submission mode | **Show success message**, naming the resulting phase: "Recorded: `<story_key>` moves to `<phase>` (`<status>`). This is provisional until the next tracker PR merges into git." The phase is looked up from `RESOURCE.storyline_state_machine.page_decision_table` with the Page's own answers (whether a success message can use formulas over Resources is K31; if not, the message says "the resulting phase is shown in the tracker and in the confirmation email") | |

## Elements

| # | Element | Type | Body key | Content · options |
|---|---|---|---|---|
| 1 | "Decide a gate" | Heading | — | — |
| 2 | Open gates | Rich text | — | One line per row from `open_gate_options.rows`: `<story_key> — <title> — <open_gate or parked> (<phase>/<status>)` |
| 3 | Story | Option | `story_key` | from the upstream List: `open_gate_options.keys` |
| 4 | Gate | Option | `gate` | `G0 \| G6 \| G7 \| GX \| unpark` |
| 5 | Decision | Option | `decision` | filtered by gate — **G0** `build \| reject \| park` · **G6** `go_live \| stay_shadow` · **G7** `keep \| rescope \| retire` · **GX** `resume \| park \| reject` · **unpark** `unpark`. The lists are `RESOURCE.storyline_state_machine.page_options`; if an Option cannot be filtered by another element (K31), all decisions are listed and `apply_decision` refuses a pair the table does not hold |
| 6 | Note | Long text | `note` | Why — evidence for git and the audit trail. Untrusted text; trimmed to 512 characters in the event |
| 7 | Decide | Button | `button` | submission value `decide` |

## What follows the Page (C5)

`gate_decision` → `gate_identity` (the submitter's email from the headers) → `is_approver` (**the email is in `storyline_approvers[<gate>]`**) → `is_gate_open` (the row's `open_gate` equals the gate; for unpark, the row is `parked`) → `apply_decision` (the next phase and status from `page_decision_table`) → `has_valid_transition` → `gate_update_row` (`phase`, `status`, `open_gate`; **`pending_repo_sync: true`**, **`pending_base_rev` = the row's `rev`**, **`outbox_seq` + 1**; never `rev`) → `gate_log_event` (`gate_decision`, `actor` = `<gate>-approver`, `actor_ref` = the email, `actor_kind: human`) → section D (for example G0 `build` puts the row in discover; a transition is also a backlog change for the planner). Any refusal — not an approver, gate not open, no valid transition, a failed write — ends on `gate_refused`, emailed to the submitter with the reason.

## Rules the Page does not relax

- **Authority comes from the Resource**, never from chat, a note or a request body. A person not listed for the gate is refused even if the Page let them in.
- **One open gate per story.** The Page lists only rows whose gate is open.
- **The decision is provisional** until its tracker PR merges; a closed PR is reset by the nightly snapshot after `pending_reset_hours` and git's values return (§6.5).
- **Destructive or production-changing decisions stay human-only** (§4.5 rule 4): G6 and G7 are decided here by a person; the retire itself — disabling the story — is `[BY HAND]` in Tines after the decision, and a PR marks the row `retired`.

## Verify in your tenant

| Item | What to check |
|---|---|
| K31 | An Option filtered by another element; a success message with formulas; the submitter header key |
| K40 | What "unlocking through the API is permanent" means, before locking `storyline_approvers` |
| K8 | Nothing to rotate on this Page (it is mid-story), but the `tracker_home` identifier that leads here |
