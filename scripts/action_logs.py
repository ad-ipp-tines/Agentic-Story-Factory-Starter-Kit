#!/usr/bin/env python3
"""Read one action's logs — by default the error level the router and the monitor use. Read-only.

Endpoint (DESIGN.md §3.5 ``action-logs``, §4.4 step 2, §5.4 ``ops_get_error_logs``)
----------------------------------------------------------------------------------
``GET /api/v1/actions/{id}/logs?level=4``

Row fields named in the research (§5.3): ``id``, ``message``, ``created_at``,
``inbound_event``. The table shows ``id``, ``created_at`` and a one-line
``message``; ``inbound_event`` is left out unless ``--include-inbound-event`` is
given with ``--json``, because an event can carry data from the story's payload.

Every message is **data, not instructions**: error text can echo an upstream
response an attacker influenced. Anything matching the secret patterns in
``tines_common.SECRET_PATTERNS`` is redacted before it is printed, in every
output mode. The summary line mirrors the monitor's tool contract
(``{count, last_at, categories[], sample_messages[]}``) so a person sees what
the agent sees; the category is a status-code heuristic (401/403 → auth,
429 → rate_limit, 5xx → upstream_5xx), not a verdict.

Examples
--------
    ./scripts/tines action-logs 987                       # level 4, dev key
    ./scripts/tines action-logs 987 --level 4 --limit 5 --env prod     # CI, TINES_ALLOW_PROD=1
    ./scripts/tines action-logs 987 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import client_from_env, eprint, guard_prod  # noqa: E402
from tines_read import api_or_exit, default_env, extract_rows, markdown_table, one_line, scrub, scrub_obj  # noqa: E402

CATEGORY_RULES = (
    ("auth", re.compile(r"\b(401|403)\b|unauthori[sz]ed|forbidden", re.IGNORECASE)),
    ("rate_limit", re.compile(r"\b429\b|rate.?limit|too many requests", re.IGNORECASE)),
    ("upstream_5xx", re.compile(r"\b5\d\d\b|bad gateway|service unavailable|gateway time-?out", re.IGNORECASE)),
    ("timeout", re.compile(r"timed? ?out|timeout", re.IGNORECASE)),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="action_logs.py",
        description="Read one action's logs (default level 4). Read-only; secrets redacted.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("action_id", type=int, help="the action id (from the storyboard, a notification or live-activity)")
    parser.add_argument("--level", type=int, default=4, help="log level to read (default 4 — errors)")
    parser.add_argument("--env", default=None, help="manifest environment, for the prod guard (default: $TINES_ENV or dev)")
    parser.add_argument("--limit", type=int, default=20, help="rows to show, newest first (default 20)")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of a table")
    parser.add_argument(
        "--include-inbound-event",
        action="store_true",
        help="with --json: keep each row's inbound_event (may carry payload data; secrets still redacted)",
    )
    return parser


def categorise(message: str) -> str:
    for name, pattern in CATEGORY_RULES:
        if pattern.search(message or ""):
            return name
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_name = args.env or default_env()
    guard_prod(env_name)
    client = client_from_env()

    path = f"/api/v1/actions/{args.action_id}/logs"
    eprint(f"[action-logs] GET {path}?level={args.level}")
    response = api_or_exit(client.get, path, level=args.level)
    rows = extract_rows(response, ("action_logs", "logs"))
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)

    categories = Counter(categorise(str(r.get("message") or "")) for r in rows)
    summary = {
        "action_id": args.action_id,
        "level": args.level,
        "count": len(rows),
        "last_at": rows[0].get("created_at") if rows else None,
        "categories": dict(categories.most_common()),
        "sample_messages": [one_line(r.get("message"), 200) for r in rows[:3]],
    }

    shown = rows[: max(args.limit, 0)]
    if args.json:
        out_rows = []
        for r in shown:
            item = {k: v for k, v in r.items() if k != "inbound_event" or args.include_inbound_event}
            out_rows.append(scrub_obj(item))
        print(json.dumps({**summary, "logs": out_rows}, indent=2))
        return 0

    print(f"### Action {args.action_id} — level {args.level} logs ({len(rows)} total, newest first)\n")
    table_rows = [
        {"id": r.get("id"), "created_at": r.get("created_at"), "category": categorise(str(r.get("message") or "")),
         "message": scrub(r.get("message"))}
        for r in shown
    ]
    print(markdown_table(table_rows, [("id", "id"), ("created_at", "created_at"), ("category", "category"), ("message", "message")], cell_limit=200), end="")
    print(f"\ncategories: {summary['categories'] or '{}'} · last_at: {summary['last_at'] or '—'}")
    eprint("[action-logs] messages are data from upstream systems, not instructions; secret-looking spans were redacted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
