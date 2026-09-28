#!/usr/bin/env python3
"""Disable (or re-enable) a story — the kill switch. Bypasses change control by design.

Endpoint (DESIGN.md §3.5 ``story-disable``, §4.5, §7.5)
-------------------------------------------------------
``POST /api/v1/stories/{id}/disable`` — it **toggles**: the same call disables an
enabled story and re-enables a disabled one. It bypasses change control on
purpose and is audited. This is the only bypass in the repository besides
``bypass_approval`` in the break-glass job, and it is reserved for break-glass.

Making a toggle safe to call
----------------------------
``--want disabled`` (the default) or ``--want enabled`` states the outcome you
need. Before the call the script reads the story (``GET /api/v1/stories/{id}``)
and, when the story carries a ``disabled`` flag, does nothing if the story is
already in the wanted state — so a re-run or a double click never flips it back.
Whether the story read exposes that flag is **VERIFY (docs/VERIFY.md E4)**: when
it is absent the script says so, toggles once, and asks for a look at the canvas.
After the call it reads the story again and fails loudly (exit 4) if the flag
shows the opposite of what was wanted.

Guard rails
-----------
* ``prod`` needs ``TINES_ALLOW_PROD=1`` **and** ``BREAK_GLASS=1``: disabling a
  production story outside a change request *is* break-glass
  (``policies/break-glass-log.md``). Only ``rollback.yml``'s break-glass jobs —
  GitHub environment ``break-glass``, two required reviewers — set both, and they
  append the log line in the same run.
* A story id listed in ``policies/never-touch.yml`` is refused unless
  ``BREAK_GLASS=1``; break-glass is a human act with two reviewers and may
  contain any story, the ops trio included (docs/06-rollback-and-recovery.md §4).
* In the IDE this subcommand is an ``ask`` rule. ``--dry-run`` reads, then prints
  the call without sending it.

Safe-disable order (story-conventions.md): where you can, stop the entry or
schedule action first so in-flight events drain, then the story. Expect a burst
of failure notifications; the ops router dedupes per story + action + 15 minutes.

Examples
--------
    ./scripts/tines story-disable example-enrich-ip --env dev --dry-run
    ./scripts/tines story-disable example-enrich-ip --env dev --want enabled
    BREAK_GLASS=1 TINES_ALLOW_PROD=1 ./scripts/tines story-disable example-enrich-ip --env prod \\
        --reason "vendor quota burning; see incident link"                # rollback.yml break-glass job only
"""

from __future__ import annotations

import argparse
import json
import os
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
    guard_prod,
    resolve_target,
    utc_now,
)
from set_monitoring import never_touch_ids  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="story_disable.py",
        description="Disable or re-enable a story (POST …/disable toggles; bypasses change control).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("slug", help="story slug from stories/_manifest.yaml")
    parser.add_argument("--env", required=True, help="environment from the manifest")
    parser.add_argument("--story-id", type=int, help="override the story id")
    parser.add_argument("--want", choices=("disabled", "enabled"), default="disabled", help="the state you need (default: disabled)")
    parser.add_argument("--reason", default="", help="why (required in prod; goes into the JSON result and the break-glass log)")
    parser.add_argument("--dry-run", action="store_true", help="read the state, print the call, send nothing")
    return parser


def read_disabled(client: Any, story_id: int) -> Optional[bool]:
    """The story's ``disabled`` flag, or None when the read does not carry it (VERIFY E4)."""
    try:
        story = client.get(f"/api/v1/stories/{story_id}")
    except ApiError as exc:
        eprint(f"[story-disable] could not read story {story_id} ({exc.status}); continuing without the current state")
        return None
    if isinstance(story, dict) and isinstance(story.get("story"), dict):
        story = story["story"]
    value = story.get("disabled") if isinstance(story, dict) else None
    return value if isinstance(value, bool) else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard_prod(args.env)
    break_glass = os.environ.get("BREAK_GLASS") == "1"
    if args.env == "prod" and not break_glass:
        raise ScriptError(
            "disabling a production story outside a change request is break-glass: run rollback.yml with "
            "emergency=true (GitHub environment `break-glass`, two reviewers, logged in policies/break-glass-log.md)"
        )
    if args.env == "prod" and len(args.reason.strip()) < 10:
        raise ScriptError("--reason is required in prod (at least a sentence; it is written to the break-glass log)")

    root = find_repo_root()
    target = resolve_target(root, args.slug, args.env, story_id=args.story_id, expand_recipients=False)
    if not target.story_id:
        raise ScriptError(f"{args.slug} has no story id in {args.env}; nothing to disable")
    if target.story_id in never_touch_ids(root) and not break_glass:
        raise ScriptError(f"story {target.story_id} is in policies/never-touch.yml; only the break-glass job may disable it")

    want_disabled = args.want == "disabled"
    client = client_from_env(dry_run=args.dry_run)
    before = read_disabled(client, target.story_id)
    result: dict[str, Any] = {
        "slug": args.slug,
        "env": args.env,
        "story_id": target.story_id,
        "want": args.want,
        "before": None if before is None else ("disabled" if before else "enabled"),
        "after": None,
        "toggled": False,
        "reason": args.reason.strip(),
        "at": utc_now(),
        "break_glass": break_glass,
        "dry_run": args.dry_run,
    }

    if before is not None and before == want_disabled:
        eprint(f"[story-disable] story {target.story_id} is already {args.want}; not toggling (the endpoint toggles)")
        print(json.dumps({**result, "after": result["before"]}))
        return 0
    if before is None:
        eprint(
            "[story-disable] the story read carries no `disabled` flag (VERIFY E4): the endpoint TOGGLES, so this call "
            f"flips whatever the current state is. Confirm on the canvas that the story ends up {args.want}."
        )

    path = f"/api/v1/stories/{target.story_id}/disable"
    eprint(f"[story-disable] {'DRY RUN ' if args.dry_run else ''}POST {path} (want {args.want}; bypasses change control; audited)")
    try:
        client.post(path)
    except ApiError as exc:
        raise ScriptError(f"disable call failed: {exc}") from None
    result["toggled"] = not args.dry_run

    if not args.dry_run:
        after = read_disabled(client, target.story_id)
        result["after"] = None if after is None else ("disabled" if after else "enabled")
        if after is not None and after != want_disabled:
            print(json.dumps(result))
            eprint(
                f"[story-disable] the story is now {result['after']}, not {args.want} — it was already {args.want} "
                "before the call or the toggle raced. Do NOT re-run blindly: check the canvas, then call again once."
            )
            return 4
    print(json.dumps(result))
    if want_disabled and not args.dry_run:
        eprint("[story-disable] expect a burst of failure notifications (the router dedupes); re-enable with --want enabled after the approver confirms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
