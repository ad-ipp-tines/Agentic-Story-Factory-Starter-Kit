#!/usr/bin/env python3
"""Create or list story versions (rollback points).

``create``  ``POST /api/v1/stories/{id}/versions {name}`` — tag the live story
            before an import (``pre-ship <sha>``), before a rollback
            (``pre-rollback <sha>``) or after a promotion (``release <sha>``).
``list``    ``GET /api/v1/stories/{id}/versions`` — metadata only. No
            export-of-a-version endpoint was found in the research (DESIGN.md
            §10 #12, VERIFY), so the **git ref is the source** for a rollback;
            versions are the in-tenant bookmark that pairs with it.

Examples
--------
    ./scripts/story_version.py create example-enrich-ip --env dev --name "pre-ship abc1234"
    ./scripts/story_version.py list example-enrich-ip --env dev
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    ApiError,
    ScriptError,
    client_from_env,
    eprint,
    find_repo_root,
    guard_prod,
    resolve_target,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="story_version.py",
        description="Create or list story versions (rollback points).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("slug", help="story slug")
    common.add_argument("--env", required=True, help="environment from the manifest")
    common.add_argument("--story-id", type=int, help="override the story id")
    common.add_argument("--dry-run", action="store_true", help="show the call without performing writes")
    p_create = sub.add_parser("create", parents=[common], help="tag a version of the live story")
    p_create.add_argument("--name", required=True, help="version name, e.g. 'pre-ship abc1234'")
    p_list = sub.add_parser("list", parents=[common], help="list versions (metadata only)")
    p_list.add_argument("--json", action="store_true", help="print the raw response")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard_prod(args.env)
    target = resolve_target(find_repo_root(), args.slug, args.env, story_id=args.story_id, expand_recipients=False)
    client = client_from_env(dry_run=args.dry_run)
    path = f"/api/v1/stories/{target.story_id}/versions"
    try:
        if args.command == "create":
            eprint(f"[version] POST {path} name={args.name!r}")
            response = client.post(path, {"name": args.name})
            print(json.dumps({"story_id": target.story_id, "name": args.name, "response": response}))
            return 0
        response = client.get(path)
        if args.json:
            print(json.dumps(response, indent=2, sort_keys=True))
            return 0
        versions = response.get("versions") if isinstance(response, dict) else response
        if not isinstance(versions, list):
            print(json.dumps(response, indent=2, sort_keys=True))
            return 0
        print(f"versions for {args.slug} ({args.env}, story {target.story_id}): {len(versions)}")
        for item in versions:
            if isinstance(item, dict):
                print(f"- {item.get('id')}\t{item.get('name')}\t{item.get('created_at', '')}")
        return 0
    except ApiError as exc:
        raise ScriptError(str(exc)) from None


if __name__ == "__main__":
    sys.exit(main())
