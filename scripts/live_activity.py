#!/usr/bin/env python3
"""Show live activity and monitoring coverage for published stories. Read-only.

Endpoints (DESIGN.md §3.5 ``live-activity``, §5.3 "Live activity")
------------------------------------------------------------------
* every published story the key can see:
  ``GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true&per_page=100``
* one story (``--slug`` with ``--env``, or ``--story-id``):
  ``GET /api/v1/stories/{id}?include_live_activity=true``

Columns: ``not_working_actions_count``, ``pending_action_runs_count``,
``monitor_failures``, ``actions_with_monitoring``, the **number** of
``recipients``, ``change_control_enabled``, ``locked``, ``mode``. Recipient
addresses are never printed: the ops router's webhook URL carries a secret.

``--attention`` keeps only stories that need a look: an action not working,
story-level failure notifications off, or no recipients (the coverage gaps the
sweep proposes to fix). There is **no run-status field** anywhere in the API, so
"not working" here is the platform's own counter, not a verdict (VERIFY #16:
the exact semantics of ``not_working_actions_count``).

Known unknowns (VERIFY)
-----------------------
* #16 — whether the live-activity fields sit at the top level of each story or
  inside a nested object; both are read.
* #27 — list pagination: ``meta.next_page`` is followed when present, otherwise
  the walk stops at the first page shorter than ``per_page``.

Examples
--------
    ./scripts/tines live-activity                                   # dev team, every published story
    ./scripts/tines live-activity --env prod --slug ops-story-health-monitor
    ./scripts/tines live-activity --env prod --attention --json     # CI, TINES_ALLOW_PROD=1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    client_from_env,
    eprint,
    find_repo_root,
    guard_prod,
    load_manifest,
    resolve_target,
)
from tines_read import api_or_exit, default_env, fetch_pages, markdown_table  # noqa: E402

FIELDS = (
    "not_working_actions_count",
    "pending_action_runs_count",
    "monitor_failures",
    "actions_with_monitoring",
    "change_control_enabled",
    "locked",
    "mode",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="live_activity.py",
        description="Live activity and monitoring coverage for published stories (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("--env", default=None, help="manifest environment (default: $TINES_ENV or dev)")
    parser.add_argument("--slug", help="one story, resolved from stories/_manifest.yaml")
    parser.add_argument("--story-id", type=int, help="one story by id")
    parser.add_argument("--attention", action="store_true", help="only stories with a not-working action or a coverage gap")
    parser.add_argument("--per-page", type=int, default=100, help="page size for the list call (default 100)")
    parser.add_argument("--max-pages", type=int, default=20, help="stop after this many pages (default 20)")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of a table")
    return parser


def _pick(story: dict[str, Any], key: str) -> Any:
    """A live-activity field from the top level or a nested object (placement VERIFY #16)."""
    if key in story:
        return story[key]
    for nested in ("live_activity", "liveActivity"):
        inner = story.get(nested)
        if isinstance(inner, dict) and key in inner:
            return inner[key]
    return None


def _count(value: Any) -> Optional[int]:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def summarise(story: dict[str, Any], slugs_by_id: dict[int, str]) -> dict[str, Any]:
    """One row per story. Recipients become a count; addresses are never kept."""
    story_id = story.get("id")
    row: dict[str, Any] = {
        "story_id": story_id,
        "slug": slugs_by_id.get(story_id) if isinstance(story_id, int) else None,
        "name": story.get("name"),
    }
    for key in FIELDS:
        value = _pick(story, key)
        row[key] = _count(value) if key == "actions_with_monitoring" and isinstance(value, list) else value
    row["recipients_count"] = _count(_pick(story, "recipients"))
    reasons = []
    if (row.get("not_working_actions_count") or 0) > 0:
        reasons.append("not_working_actions")
    if row.get("monitor_failures") is False:
        reasons.append("monitor_failures_off")
    if row.get("recipients_count") == 0:
        reasons.append("no_recipients")
    row["attention"] = reasons
    return row


def slug_index(root: Path, env_name: str) -> dict[int, str]:
    """story id → slug for the environment, when the manifest is readable."""
    try:
        manifest = load_manifest(root)
    except SystemExit:
        return {}
    out: dict[int, str] = {}
    for slug, entry in (manifest.get("stories") or {}).items():
        value = ((entry or {}).get(env_name) or {}).get("story_id")
        try:
            sid = int(value)
        except (TypeError, ValueError):
            continue
        if sid > 0:
            out[sid] = slug
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_name = args.env or default_env()
    guard_prod(env_name)
    root = find_repo_root()
    client = client_from_env()
    slugs_by_id = slug_index(root, env_name)

    single_id: Optional[int] = args.story_id
    if args.slug and single_id is None:
        target = resolve_target(root, args.slug, env_name, expand_recipients=False)
        if not target.story_id:
            eprint(f"[live-activity] {args.slug} has no story id in {env_name} yet (new: true)")
            return 1
        single_id = target.story_id

    truncated = False
    if single_id is not None:
        eprint(f"[live-activity] GET /api/v1/stories/{single_id}?include_live_activity=true")
        story = api_or_exit(client.get, f"/api/v1/stories/{single_id}", include_live_activity="true")
        if isinstance(story, dict) and isinstance(story.get("story"), dict):
            story = story["story"]
        stories = [story] if isinstance(story, dict) else []
    else:
        eprint("[live-activity] GET /api/v1/stories?filter=PUBLISHED&include_live_activity=true (paged)")
        stories, truncated = api_or_exit(
            fetch_pages,
            client,
            "/api/v1/stories",
            {"filter": "PUBLISHED", "include_live_activity": "true"},
            preferred_keys=("stories",),
            per_page=args.per_page,
            max_pages=args.max_pages,
        )

    rows = [summarise(s, slugs_by_id) for s in stories]
    if args.attention:
        rows = [r for r in rows if r["attention"]]
    rows.sort(key=lambda r: (-(r.get("not_working_actions_count") or 0), str(r.get("name") or "")))

    if args.json:
        print(json.dumps({"env": env_name, "count": len(rows), "truncated": truncated, "stories": rows}, indent=2))
        return 0

    columns = [
        ("story_id", "id"),
        ("slug", "slug"),
        ("name", "name"),
        ("not_working_actions_count", "not working"),
        ("pending_action_runs_count", "pending runs"),
        ("monitor_failures", "monitor_failures"),
        ("actions_with_monitoring", "actions monitored"),
        ("recipients_count", "recipients"),
        ("change_control_enabled", "change control"),
        ("locked", "locked"),
        ("mode", "mode"),
    ]
    printable = [{**r, "slug": r.get("slug") or "—", "attention": ", ".join(r["attention"])} for r in rows]
    print(f"### Live activity — {env_name} ({len(rows)} stor{'y' if len(rows) == 1 else 'ies'}{', attention only' if args.attention else ''})\n")
    print(markdown_table(printable, columns + [("attention", "attention")]), end="")
    if truncated:
        print(f"\n_Stopped after {args.max_pages} page(s); more stories exist — raise --max-pages._")
    needing = sum(1 for r in rows if r["attention"])
    eprint(f"[live-activity] {len(rows)} row(s); {needing} need attention; recipients are shown as counts only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
