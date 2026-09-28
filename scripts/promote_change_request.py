#!/usr/bin/env python3
"""Promote a change request that a person has already APPROVED in Tines. CI only. Never approves.

Endpoint (DESIGN.md §3.5 ``cr-promote``, §2.3 rows 2 and 19, §4.2 step 5, §4.5 step 4)
--------------------------------------------------------------------------------------
``POST /api/v1/stories/{id}/change_request/promote {change_request_id, delete_draft}``

and, only in the break-glass job, ``{…, bypass_approval: true, bypass_approval_reason}``
(the key then needs STORY_MANAGE).

The default is still a person: the approver approves **and pushes** in Tines.
This script exists for ``promote.yml`` (a human dispatches it after approving)
and for ``rollback.yml``'s break-glass promotion. It is the dispatcher's
``cr-promote`` subcommand, and every guard below runs before any call:

1. **CI only, on every path.** Refused unless ``GITHUB_ACTIONS=true`` AND the
   run carries the evidence GitHub Actions sets for a workflow run of THIS
   repository: ``GITHUB_WORKFLOW_REF`` names ``<GITHUB_REPOSITORY>/.github/workflows/
   promote.yml@…`` or ``…/rollback.yml@…`` (the only two callers), and
   ``GITHUB_RUN_ID`` / ``GITHUB_JOB`` are set. A caller can set environment
   variables too, so this is defence in depth, not the control: the IDE denies
   ``cr-promote`` and direct calls of this file in ``.claude/settings.json``, and
   the prod key lives only in environment-gated jobs. (Neither job requests
   ``id-token: write``, so ``ACTIONS_ID_TOKEN_REQUEST_URL`` is not available as
   evidence.) A person in a terminal approves and pushes in Tines.
2. **Production** needs ``TINES_ALLOW_PROD=1`` (set only inside environment-gated jobs).
3. **APPROVED or nothing.** Without ``--bypass-approval`` it re-reads
   ``GET /api/v1/stories/{id}/change_request/view?draft_id=<draft>`` and promotes
   only when the status is ``APPROVED`` (exit 3 otherwise — "approve in Tines
   first"). The view MUST name a change-request id and it must equal
   ``--change-request-id``; a view that names none is refused, so an APPROVED
   draft can never vouch for a different request (where the id sits in the
   response is VERIFY E7 — until it is confirmed, a refusal here means "read the
   view keys", never "skip the check"). A PENDING, REJECTED or CANCELLED request
   is never promoted by any pipeline.
4. **Bypass only in the break-glass job.** ``--bypass-approval`` is accepted
   only when ``BREAK_GLASS=1``, ``--reason`` carries at least a sentence, the job
   is ``break-glass-promote`` and the workflow is ``rollback.yml``
   (``GITHUB_JOB`` / ``GITHUB_WORKFLOW_REF``). Those variables are defence in
   depth — the real control is that the key with STORY_MANAGE lives only in the
   ``break-glass`` GitHub environment, behind two required reviewers — and the
   job appends ``policies/break-glass-log.md`` in the same run.

It never sends ``bypass_approval: false`` either: the key is simply absent
unless the break-glass path is taken.

Known unknowns (VERIFY, docs/VERIFY.md E7)
------------------------------------------
Where ``status`` and the request id sit in the view response (``change_request``
object or top level — both are read, as ``change_request.py`` does), and the
promote response body (printed as returned).

Examples
--------
    # promote.yml (GitHub environment `production`, after the approver approved in Tines)
    ./scripts/tines cr-promote example-enrich-ip --env prod --change-request-id 55 --draft 1234 --delete-draft

    # rollback.yml job `break-glass-promote` only (environment `break-glass`, two reviewers)
    BREAK_GLASS=1 ./scripts/tines cr-promote example-enrich-ip --env prod --change-request-id 55 \\
        --draft 1234 --delete-draft --bypass-approval --reason "harm is ongoing; approver unreachable; incident link"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import ApiError, ScriptError, client_from_env, eprint, find_repo_root, guard_prod, resolve_target  # noqa: E402
from change_request import _extract_status  # noqa: E402

BREAK_GLASS_JOB = "break-glass-promote"
BREAK_GLASS_WORKFLOW = "/.github/workflows/rollback.yml@"
CALLER_WORKFLOWS = ("/.github/workflows/promote.yml@", BREAK_GLASS_WORKFLOW)


def check_ci_evidence() -> None:
    """Refuse unless this looks like a GitHub Actions run of promote.yml or rollback.yml in this repository."""
    problems = []
    if os.environ.get("GITHUB_ACTIONS") != "true":
        problems.append("GITHUB_ACTIONS is not 'true'")
    repo = os.environ.get("GITHUB_REPOSITORY") or ""
    ref = os.environ.get("GITHUB_WORKFLOW_REF") or ""
    if not repo or not any(ref.startswith(repo + wf) for wf in CALLER_WORKFLOWS):
        problems.append("GITHUB_WORKFLOW_REF does not name promote.yml or rollback.yml in GITHUB_REPOSITORY")
    for name in ("GITHUB_RUN_ID", "GITHUB_JOB"):
        if not os.environ.get(name):
            problems.append(f"{name} is not set")
    if problems:
        raise ScriptError(
            "cr-promote runs only in CI (promote.yml, or rollback.yml's break-glass job): " + "; ".join(problems)
            + ". Approve and push in Tines instead; the IDE denies this subcommand."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promote_change_request.py",
        description="Promote an APPROVED change request (CI only; bypass only in rollback.yml's break-glass job).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("slug", help="story slug")
    parser.add_argument("--env", required=True, help="environment from the manifest")
    parser.add_argument("--story-id", type=int, help="override the story id")
    parser.add_argument("--change-request-id", required=True, help="the change request to promote")
    parser.add_argument("--draft", metavar="DRAFT_ID", help="the request's draft (required to re-read the status)")
    parser.add_argument("--delete-draft", action="store_true", help="send delete_draft: true (the pipelines always do)")
    parser.add_argument("--bypass-approval", action="store_true", help="BREAK-GLASS ONLY: promote without an approval")
    parser.add_argument("--reason", default="", help="mandatory with --bypass-approval; sent as bypass_approval_reason")
    parser.add_argument("--dry-run", action="store_true", help="run every check and read; print the promote call; send nothing")
    return parser


def _cr_id_in(response: Any) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    cr = response.get("change_request")
    if isinstance(cr, dict) and cr.get("id") not in (None, ""):
        return str(cr["id"])
    return None


def _id_value(text: str) -> Any:
    return int(text) if text.isdigit() else text


def check_bypass_allowed(args: argparse.Namespace) -> None:
    problems = []
    if os.environ.get("BREAK_GLASS") != "1":
        problems.append("BREAK_GLASS=1 is not set")
    if len(args.reason.strip()) < 10:
        problems.append("--reason is missing or shorter than a sentence")
    if os.environ.get("GITHUB_JOB") != BREAK_GLASS_JOB:
        problems.append(f"the job is not `{BREAK_GLASS_JOB}`")
    if BREAK_GLASS_WORKFLOW not in (os.environ.get("GITHUB_WORKFLOW_REF") or ""):
        problems.append("the workflow is not rollback.yml")
    if problems:
        raise ScriptError(
            "--bypass-approval refused: " + "; ".join(problems) + ". bypass_approval exists only in rollback.yml's "
            "break-glass job (GitHub environment `break-glass`, two reviewers, a line in policies/break-glass-log.md)"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    check_ci_evidence()
    guard_prod(args.env)
    if args.bypass_approval:
        check_bypass_allowed(args)
    elif not args.draft:
        raise ScriptError("--draft is required: the status is re-read from …/change_request/view?draft_id= before promoting")

    target = resolve_target(find_repo_root(), args.slug, args.env, story_id=args.story_id, expand_recipients=False)
    if not target.story_id:
        raise ScriptError(f"{args.slug} has no story id in {args.env}")
    client = client_from_env(dry_run=args.dry_run)

    status: Optional[str] = None
    if args.draft:
        view_path = f"/api/v1/stories/{target.story_id}/change_request/view"
        eprint(f"[cr-promote] GET {view_path}?draft_id={args.draft}")
        try:
            view = client.get(view_path, draft_id=args.draft)
        except ApiError as exc:
            raise ScriptError(f"could not read the change request: {exc}") from None
        status = _extract_status(view)
        named = _cr_id_in(view)
        if named is None:
            raise ScriptError(
                "the change-request view names no change-request id, so it cannot vouch for "
                f"--change-request-id {args.change_request_id} — refusing to promote (fail closed). Where the id sits in "
                "the view response is VERIFY E7: read the response keys and fix _cr_id_in(), never skip this check"
            )
        if named != str(args.change_request_id):
            raise ScriptError(
                f"the draft's change request is {named}, not {args.change_request_id} — refusing to promote a request "
                "other than the one named"
            )
        eprint(f"[cr-promote] status: {status!r}")
    if not args.bypass_approval and (status or "").upper() != "APPROVED":
        eprint(f"[cr-promote] status is {status!r}, not APPROVED — a named approver must approve it in Tines first. Nothing was promoted.")
        return 3

    body: dict[str, Any] = {"change_request_id": _id_value(str(args.change_request_id)), "delete_draft": bool(args.delete_draft)}
    if args.bypass_approval:
        body["bypass_approval"] = True
        body["bypass_approval_reason"] = args.reason.strip()
        eprint(f"[cr-promote] BREAK-GLASS: promoting WITHOUT approval (status {status!r}); reason recorded; log line required in this run")
    path = f"/api/v1/stories/{target.story_id}/change_request/promote"
    eprint(f"[cr-promote] {'DRY RUN ' if args.dry_run else ''}POST {path} change_request_id={args.change_request_id} delete_draft={body['delete_draft']}")
    try:
        response = client.post(path, body)
    except ApiError as exc:
        hint = " (bypass_approval needs STORY_MANAGE on the key)" if args.bypass_approval and exc.status in (401, 403, 404) else ""
        raise ScriptError(f"promote failed: {exc}{hint}") from None

    print(json.dumps({
        "slug": args.slug,
        "env": args.env,
        "story_id": target.story_id,
        "change_request_id": args.change_request_id,
        "draft_id": args.draft,
        "status_before": status,
        "bypass_approval": bool(args.bypass_approval),
        "delete_draft": bool(args.delete_draft),
        "promoted": not args.dry_run,
        "response": response if isinstance(response, (dict, list)) else None,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
