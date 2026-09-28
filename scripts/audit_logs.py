#!/usr/bin/env python3
"""Read the tenant's audit logs after a point in time — attribution for drift, digests and incidents. Read-only.

Endpoint (DESIGN.md §3.5 ``audit``, §3.4 ``drift.yml``, §5.3 "Audit")
--------------------------------------------------------------------
``GET /api/v1/audit_logs?after=<ts>&per_page=<n>&page=<n>``, paged under the
audit-log rate limit (1,000 requests/minute; this script pauses between pages).

Columns named in the research: ``user_email``, ``operation_name``, ``source``,
``request_user_agent``. ``created_at`` and ``id`` are shown when a row has them.

Filters
-------
* ``--story-id`` (repeatable) is applied **client-side**: a row is kept when any
  key named ``story_id`` anywhere inside it equals one of the ids. Whether the
  endpoint filters by story server-side, and where a row carries the story id,
  are VERIFY (#17, E6) — rows that never mention a story id cannot be attributed
  this way, and the output says how many rows were read in total.
* ``--operation-name`` (repeatable) is sent server-side as ``operation_name[]``
  (DESIGN.md §3.5; VERIFY #17). Use it once the MCP-activity operation name has
  been read from a real audit log and recorded in docs/VERIFY.md.
* ``--mcp-only`` keeps rows flagged as MCP activity. Until the operation name is
  known (#17) the flag is a **heuristic**: ``mcp`` appears in
  ``operation_name``, ``source`` or ``request_user_agent``. Every output marks it so.

These rows name people (``user_email``). They are printed because attribution is
the point (DESIGN.md §3.4 ``drift.yml``); do not copy them anywhere a story
export, a skill or a committed file would carry them.

Examples
--------
    ./scripts/tines audit --after 24h
    ./scripts/tines audit --after 2026-09-24T00:00:00Z --story-id 1234 --format markdown
    ./scripts/tines audit --after 7d --mcp-only --json
    ./scripts/tines audit --env prod --after 2026-09-01 --story-id 1234 --format markdown   # drift.yml, CI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import client_from_env, eprint, guard_prod  # noqa: E402
from tines_read import api_or_exit, default_env, fetch_pages, markdown_table, one_line, parse_when  # noqa: E402

PATH = "/api/v1/audit_logs"
MCP_FIELDS = ("operation_name", "source", "request_user_agent")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_logs.py",
        description="Read audit logs after a time; filter by story (client-side) or operation (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("--after", required=True, help="ISO 8601 time, or a relative age (1h, 24h, 7d)")
    parser.add_argument("--story-id", type=int, action="append", default=[], help="keep rows mentioning this story id (repeatable; client-side)")
    parser.add_argument("--operation-name", action="append", default=[], help="server-side operation_name[] filter (repeatable; VERIFY #17)")
    parser.add_argument("--mcp-only", action="store_true", help="keep rows flagged as MCP activity (heuristic until #17 is confirmed)")
    parser.add_argument("--env", default=None, help="manifest environment, for the prod guard (default: $TINES_ENV or dev)")
    parser.add_argument("--per-page", type=int, default=100, help="page size (default 100)")
    parser.add_argument("--max-pages", type=int, default=20, help="stop after this many pages (default 20)")
    parser.add_argument("--limit", type=int, default=100, help="rows to show in table/markdown output (default 100)")
    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument("--json", action="store_true", help="print one JSON object")
    fmt_group.add_argument("--format", choices=("table", "markdown", "json"), default="table", help="output format (markdown = a PR-ready section)")
    return parser


def _story_ids_in(obj: Any) -> set[int]:
    """Every integer value found under a key named ``story_id`` anywhere in ``obj``."""
    found: set[int] = set()
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for key, value in cur.items():
                if key == "story_id":
                    try:
                        found.add(int(value))
                    except (TypeError, ValueError):
                        pass
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(cur, list):
            stack.extend(cur)
    return found


def is_mcp(row: dict[str, Any]) -> bool:
    """Heuristic MCP-activity flag until the operation name is known (VERIFY #17)."""
    return any("mcp" in str(row.get(k) or "").lower() for k in MCP_FIELDS)


def shape(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "created_at": row.get("created_at"),
        "user_email": row.get("user_email"),
        "operation_name": row.get("operation_name"),
        "source": row.get("source"),
        "request_user_agent": one_line(row.get("request_user_agent"), 80) if row.get("request_user_agent") else None,
        "mcp": is_mcp(row),
        "story_ids": sorted(_story_ids_in(row)),
    }


def filter_rows(rows: Iterable[dict[str, Any]], story_ids: list[int], mcp_only: bool) -> list[dict[str, Any]]:
    wanted = set(story_ids)
    out = []
    for row in rows:
        if wanted and not (_story_ids_in(row) & wanted):
            continue
        if mcp_only and not is_mcp(row):
            continue
        out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_name = args.env or default_env()
    guard_prod(env_name)
    after = parse_when(args.after)
    client = client_from_env()

    params: dict[str, Any] = {"after": after}
    if args.operation_name:
        params["operation_name[]"] = list(args.operation_name)
    eprint(f"[audit] GET {PATH}?after={after}{' + operation_name[]' if args.operation_name else ''} (paged, ≤ {args.max_pages} pages)")
    raw, truncated = api_or_exit(
        fetch_pages, client, PATH, params, preferred_keys=("audit_logs", "logs"),
        per_page=args.per_page, max_pages=args.max_pages, pause_seconds=0.1,
    )
    kept = [shape(r) for r in filter_rows(raw, args.story_id, args.mcp_only)]
    kept.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    result = {
        "after": after,
        "story_ids": args.story_id,
        "operation_names": args.operation_name,
        "rows_read": len(raw),
        "rows_matched": len(kept),
        "truncated": truncated,
        "mcp_rows": sum(1 for r in kept if r["mcp"]),
        "mcp_flag": "heuristic (VERIFY #17)",
        "rows": kept,
    }

    output = "json" if args.json else args.format
    if output == "json":
        print(json.dumps(result, indent=2))
        return 0

    columns = [("created_at", "when"), ("user_email", "user_email"), ("operation_name", "operation_name"),
               ("source", "source"), ("request_user_agent", "request_user_agent"), ("mcp", "MCP?")]
    scope = f" for story {', '.join(str(s) for s in args.story_id)}" if args.story_id else ""
    if output == "markdown":
        print(f"#### Attribution — audit logs{scope} since {after}\n")
    else:
        print(f"### Audit logs{scope} since {after}\n")
    if kept:
        print(markdown_table(kept, columns, limit=args.limit), end="")
    else:
        print("_No audit row after this time mentions the story id. The change may predate the window, the rows may not "
              "carry `story_id` (VERIFY #17 / E6), or the key may not be allowed to read audit logs._")
    print(
        f"\nrows read: {len(raw)}{' (truncated — raise --max-pages)' if truncated else ''} · matched: {len(kept)} · "
        f"flagged MCP activity: {result['mcp_rows']} (heuristic until the operation name is confirmed, VERIFY #17)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
