# Break-glass log

_Append-only. One line per `POST /api/v1/stories/{id}/disable` or `bypass_approval` used in anger. `rollback.yml`'s `break-glass` job appends its line in the same run and commits it; a human adds the follow-up PR and the audit-log ids afterwards. Never delete or edit a prior row — add a correction row instead._

Who may write here: the two reviewers of the GitHub `break-glass` environment (roles, not names, in the table — the audit logs hold the identities).

| Date (UTC) | Story (slug · env) | Who (role) | Action (`disable` \| `bypass_approval`) | Reason | `change_request_id` | Audit-log ids | Follow-up PR | Re-enabled at |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

## What counts as break-glass

- Disabling a production story outside a change request (`POST /disable` toggles and bypasses change control by design).
- Promoting a change request with `bypass_approval: true` (`bypass_approval_reason` mandatory).
- Nothing else. A normal rollback (draft → change request → approval) is not break-glass and is not logged here.

## After every row

1. Re-enable the story once the approver confirms (`POST /disable` toggles back) and fill **Re-enabled at**.
2. Open the follow-up PR that makes `main` equal to what is live (a rollback or a fix) and link it.
3. Add the incident to `stories/<slug>/README.md` (change log) and, if the monitor proposed it, mark the proposal `applied` in `ops_alert_proposals`.
4. Review at the next weekly digest: was the second reviewer independent, was the reason sufficient, could a change request have waited.
