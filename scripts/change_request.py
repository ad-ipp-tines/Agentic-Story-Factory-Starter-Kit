#!/usr/bin/env python3
"""Open or view a change request on a story draft. Never promotes.

Subcommands
-----------
``open``   ``POST /api/v1/stories/{id}/change_request {draft_id, title, description}``
           The description is built from a fixed template (DESIGN.md §2.3 #12,
           §3.5 ``cr-open``): story · environment · commit SHA · PR or commit
           URL · semantic diff · rollback ref · "requires a named approver".
           Prints ``{"story_id", "draft_id", "change_request_id", "status"}``.

``view``   ``GET /api/v1/stories/{id}/change_request/view?draft_id=<id>``
           Prints the request's ``status`` and a compact live-vs-draft diff
           (actions added / removed / changed) computed from
           ``live_story_export`` and ``draft_export`` in the response, in
           Markdown for a job summary or a PR comment. ``--json`` prints the raw
           response instead.

What this script will not do
----------------------------
It has no ``promote`` subcommand. Promotion is a person approving in Tines (and
pushing), or the optional ``promote.yml`` workflow on a request whose status is
already ``APPROVED``. ``bypass_approval`` is never sent from this repository
except by the break-glass job of the rollback workflow (DESIGN.md §4.5).

Examples
--------
    ./scripts/change_request.py open example-enrich-ip --env dev --draft 1234 \\
        --title "example-enrich-ip abc1234" --pr-url https://github.com/<org>/<repo>/pull/12
    ./scripts/change_request.py view example-enrich-ip --env dev --draft 1234
    ./scripts/change_request.py view example-enrich-ip --env prod --draft 1234 --json   # CI, TINES_ALLOW_PROD=1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    ApiError,
    ScriptError,
    client_from_env,
    eprint,
    find_repo_root,
    git_sha,
    guard_prod,
    resolve_target,
)


DESCRIPTION_TEMPLATE = """Story: {name} ({slug})
Environment: {env}
Commit: {sha}
Source: {source_url}
Draft: {draft_id}
Rollback ref: {rollback_ref}

Semantic diff:
{diff}

Approval: this change request requires a named approver in Tines. The pipeline
opened it and stopped; it does not promote and never bypasses approval.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="change_request.py",
        description="Open or view a change request on a story draft (never promotes).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("slug", help="story slug")
    common.add_argument("--env", required=True, help="environment from the manifest")
    common.add_argument("--story-id", type=int, help="override the story id")
    common.add_argument("--draft", required=True, metavar="DRAFT_ID", help="the draft the request is about")
    common.add_argument("--dry-run", action="store_true", help="show the call without performing writes")

    p_open = sub.add_parser("open", parents=[common], help="open a change request for a draft")
    p_open.add_argument("--title", help="request title (default: '<slug> <sha>')")
    p_open.add_argument("--pr-url", help="PR or commit URL to cite in the description")
    p_open.add_argument("--diff", type=Path, help="file with the semantic diff (from diff_story.py) to embed")
    p_open.add_argument("--rollback-ref", help="git ref of the previous good export (default: HEAD~1)")
    p_open.add_argument("--reason", help="free-text reason (rollbacks, incident links)")

    p_view = sub.add_parser("view", parents=[common], help="print status and live-vs-draft diff")
    p_view.add_argument("--json", action="store_true", help="print the raw response")
    p_view.add_argument("--require-status", help="exit 3 unless the request status equals this (e.g. APPROVED)")
    return parser


def _agents_by_name(export: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(export, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for agent in export.get("agents") or []:
        if isinstance(agent, dict) and agent.get("name"):
            out[str(agent["name"])] = agent
    return out


def summarise_diff(live: Any, draft: Any) -> str:
    """Markdown summary of actions added, removed and changed between two exports."""
    before, after = _agents_by_name(live), _agents_by_name(draft)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = []
    for name in sorted(set(before) & set(after)):
        a, b = before[name], after[name]
        keys = []
        for key in ("type", "options", "monitoring", "schedule", "disabled", "description"):
            if a.get(key) != b.get(key):
                keys.append(key)
        if keys:
            changed.append((name, keys))
    lines = []
    lines.append(f"- actions: {len(before)} live → {len(after)} draft")
    lines.append(f"- links: {len((live or {}).get('links') or [])} → {len((draft or {}).get('links') or [])}")
    for key in ("monitor_failures", "keep_events_for", "send_to_story_enabled"):
        if (live or {}).get(key) != (draft or {}).get(key):
            lines.append(f"- story.{key}: {(live or {}).get(key)!r} → {(draft or {}).get(key)!r}")
    for name in added:
        lines.append(f"- added: `{name}` ({after[name].get('type')})")
    for name in removed:
        lines.append(f"- removed: `{name}` ({before[name].get('type')})")
    for name, keys in changed:
        lines.append(f"- changed: `{name}` ({', '.join(keys)})")
    if not (added or removed or changed):
        lines.append("- no action-level differences between live and draft")
    return "\n".join(lines)


def _extract_status(response: Any) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    cr = response.get("change_request")
    if isinstance(cr, dict) and cr.get("status"):
        return str(cr["status"])
    if response.get("status"):
        return str(response["status"])
    return None


def cmd_open(args: argparse.Namespace) -> int:
    guard_prod(args.env)
    root = find_repo_root()
    target = resolve_target(root, args.slug, args.env, story_id=args.story_id, expand_recipients=False)
    sha = git_sha() or "unknown"
    title = args.title or f"{args.slug} {sha}"
    diff_text = args.diff.read_text(encoding="utf-8").strip() if args.diff and args.diff.exists() else "(not supplied)"
    if args.reason:
        diff_text = f"Reason: {args.reason}\n\n{diff_text}"
    description = DESCRIPTION_TEMPLATE.format(
        name=(target.name or args.slug),
        slug=args.slug,
        env=args.env,
        sha=sha,
        source_url=args.pr_url or "(none)",
        draft_id=args.draft,
        rollback_ref=args.rollback_ref or "HEAD~1",
        diff=diff_text,
    )
    client = client_from_env(dry_run=args.dry_run)
    body = {"draft_id": args.draft, "title": title, "description": description}
    eprint(f"[cr] POST /api/v1/stories/{target.story_id}/change_request title={title!r} draft_id={args.draft}")
    try:
        response = client.post(f"/api/v1/stories/{target.story_id}/change_request", body)
    except ApiError as exc:
        raise ScriptError(f"could not open the change request: {exc}") from None
    cr_id = None
    if isinstance(response, dict):
        cr_id = response.get("id") or response.get("change_request_id")
        cr = response.get("change_request")
        if cr_id is None and isinstance(cr, dict):
            cr_id = cr.get("id")
    print(
        json.dumps(
            {
                "story_id": target.story_id,
                "draft_id": args.draft,
                "change_request_id": cr_id,
                "status": _extract_status(response) or ("dry_run" if args.dry_run else None),
                "title": title,
            }
        )
    )
    eprint("[cr] opened; a named approver reads the live-vs-draft diff in Tines and approves. Stop here.")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    guard_prod(args.env)
    root = find_repo_root()
    target = resolve_target(root, args.slug, args.env, story_id=args.story_id, expand_recipients=False)
    client = client_from_env(dry_run=args.dry_run)
    eprint(f"[cr] GET /api/v1/stories/{target.story_id}/change_request/view?draft_id={args.draft}")
    try:
        response = client.get(f"/api/v1/stories/{target.story_id}/change_request/view", draft_id=args.draft)
    except ApiError as exc:
        raise ScriptError(f"could not view the change request: {exc}") from None
    status = _extract_status(response)
    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        live = response.get("live_story_export") if isinstance(response, dict) else None
        draft = response.get("draft_export") if isinstance(response, dict) else None
        print(f"### Change request for `{args.slug}` ({args.env}) — draft {args.draft}\n")
        print(f"- status: **{status or 'unknown'}**")
        print(summarise_diff(live, draft))
    if args.require_status and (status or "").upper() != args.require_status.upper():
        eprint(f"[cr] status is {status!r}, required {args.require_status!r} — approve in Tines first")
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "open":
        return cmd_open(args)
    if args.command == "view":
        return cmd_view(args)
    raise ScriptError(f"unknown command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
