# Page `setup_report` (mid-story) — the day-1 result

_Spec: REPO-DESIGN.md §7.8 (`setup_report`), §7.2 A28–A32 (what feeds it) and the `[BY HAND]` list. Section A of `[KIT] 00 · Launch Storyworks`; built through Mode 2 with build prompt P-K11 (`../build-prompts.md`)._

**What it is.** The human-readable copy of `kit/tenant/setup-report.json`: overall status, links, one row per provisioning step, and the checklist of what no API can do. It is a **mid-story** Page, so each run has its own URL (`PAGE.setup_report`), which A32 emails to the submitter. It is a snapshot of that run; later progress on the `[BY HAND]` items is tracked in the day-1 milestone, not here.

## Settings

| Setting | Value | Notes |
|---|---|---|
| Page name (action name) | `setup_report` | |
| Kind | mid-story Page (per-run URL `PAGE.setup_report`) | the only way back to it is the emailed link or the run's events |
| Access | **Only team members** | §7.8 |
| Anonymise submissions | off | |
| Submission mode | **Redirect to URL** (the one Button) | below |

## Elements

| # | Element | Type | Content |
|---|---|---|---|
| 1 | "Storyworks — setup report" | Heading | — |
| 2 | Summary | Rich text | Overall status (`compose_report.report.status`: `ok`, `partial` or `failed`) in words; the repository link (`repo_url`); the App link `https://<<RESOURCE.kit_config.tenant_host>>/apps/<url-identifier>` if the App is published, otherwise "publish the App `[BY HAND]`" (or "Apps not entitled"); the Dashboard name ("Storyworks") or "build the Dashboard by hand (§9.4)" while the release ships a SKELETON; the provider verdict (`ok`, `tool_calls_unreliable`, `failed`, `not_entitled`) with the model and credits the probe reported |
| 3 | Steps | **Table** | `CSV_PARSE` of a `step,status,detail` CSV built by `compose_report` from `report.steps[]` — one row per `step_*` key (the formula that builds the CSV text is **K32**) |
| 4 | — | Divider | — |
| 5 | What you do by hand | Rich text | The `[BY HAND]` checklist, item by item, each marked `done`, `open` or `not_needed` — the seventeen items in [`../sections/A-kickoff-and-provisioning.md`](../sections/A-kickoff-and-provisioning.md) plus the conditional ones (skills that already existed, files over 1 MB, the Dashboard, a Slack credential named other than `slack_bot`). Order matters for three of them: **rotate the Webhook secrets before copying the tracker URLs**; **set the token alerts and attach the skills before enabling the runtime crew**; **run `kit.yml` and `tracker-pull.yml` last** |
| 6 | Where the report lives | Rich text | "This report is committed to `kit/tenant/setup-report.json`. Its push opens the setup-report PR, which records this story's id in `stories/_manifest.yaml` and `policies/never-touch.yml`. Merge that PR first." When `step_report` failed: "The commit failed — copy the table above into an issue, and re-run the kickoff after fixing the cause; the run resumes." |
| 7 | Open the tracker | Button | *Redirect to URL*: the App URL `https://<<RESOURCE.kit_config.tenant_host>>/apps/<url-identifier>` if it exists, otherwise the `tracker_home` root Page `https://<<RESOURCE.kit_config.tenant_host>>/pages/storyworks-tracker` |

**Never on this Page:** a token, a key, a webhook URL (the two tracker URLs are copied from the storyboard into the GitHub environment `tracker`, never shown here), or an approver's email. Step details are sentences, never raw response bodies.

## Verify in your tenant

| Item | What to check |
|---|---|
| K32 | The Table element fed from CSV text built by formula |
| K8 | The App and `tracker_home` identifiers after import |
