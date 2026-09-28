#!/usr/bin/env python3
"""List a story's recent runs, or read one run's summary or events. Read-only.

Endpoints (DESIGN.md §3.5 ``runs``, §4.1 step 6, §5.3 "Story runs")
------------------------------------------------------------------
* ``GET /api/v1/stories/{id}/runs?since=<ts>``            — the list (default)
* ``GET /api/v1/stories/{id}/runs/{guid}/summary``         — ``--summary <guid>``
* ``GET /api/v1/stories/{id}/runs/{guid}``                 — ``--events <guid>``

Run fields named in the research: ``guid``, ``duration``, ``start_time``,
``end_time``, ``action_count``, ``event_count``. **There is no status field**, so
this command never says a run "failed": it prints the counts and the durations,
and failure is derived elsewhere from error logs and live activity (DESIGN.md
§5.3). The closing line mirrors the monitor's ``ops_get_recent_runs`` tool —
``{runs, median_duration_s, max_duration_s, last_start}`` — so a person and the
agent read the same numbers.

``--since`` takes an ISO time or a relative age (``15m``, ``1h``, ``2d``).

Known unknowns (VERIFY)
-----------------------
* #16 — whether ``end_time`` is null while a run is in flight, and the unit of
  ``duration`` (shown as returned; the stats assume seconds).
* The accepted format of ``since`` (an ISO-8601 UTC timestamp is sent).
* ``--events`` output: a run's events can carry payload data. Secret-looking
  strings are redacted; do not paste the output into tickets or PRs.

Examples
--------
    ./scripts/tines runs example-enrich-ip --env dev --since 1h
    ./scripts/tines runs ops-story-health-monitor --env prod --since 2026-09-25T02:00:00Z   # CI
    ./scripts/tines runs example-enrich-ip --env dev --summary <run-guid>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import ScriptError, client_from_env, eprint, find_repo_root, guard_prod, resolve_target  # noqa: E402
from tines_read import (  # noqa: E402
    api_or_exit,
    check_guid,
    extract_rows,
    fmt,
    markdown_table,
    median,
    num,
    parse_when,
    scrub_obj,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="story_runs.py",
        description="Recent runs of one story, or one run's summary or events (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("slug", help="story slug from stories/_manifest.yaml")
    parser.add_argument("--env", required=True, help="environment from the manifest")
    parser.add_argument("--story-id", type=int, help="override the story id")
    parser.add_argument("--since", help="only runs since this time (ISO 8601, or 15m / 1h / 2d)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--summary", metavar="GUID", help="print GET …/runs/{guid}/summary")
    mode.add_argument("--events", metavar="GUID", help="print GET …/runs/{guid} (events; secrets redacted)")
    parser.add_argument("--limit", type=int, default=50, help="rows to show, newest first (default 50)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    return parser


def run_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [num(r.get("duration")) for r in rows]
    durations = [d for d in durations if d is not None]
    starts = sorted(str(r.get("start_time")) for r in rows if r.get("start_time"))
    return {
        "runs": len(rows),
        "median_duration_s": median(durations),
        "max_duration_s": max(durations) if durations else None,
        "last_start": starts[-1] if starts else None,
        "in_flight": sum(1 for r in rows if r.get("start_time") and r.get("end_time") in (None, "")),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard_prod(args.env)
    target = resolve_target(find_repo_root(), args.slug, args.env, story_id=args.story_id, expand_recipients=False)
    if not target.story_id:
        raise ScriptError(f"{args.slug} has no story id in {args.env} yet (new: true)")
    client = client_from_env()
    base = f"/api/v1/stories/{target.story_id}/runs"

    if args.summary or args.events:
        guid = check_guid(args.summary or args.events)
        path = f"{base}/{guid}/summary" if args.summary else f"{base}/{guid}"
        eprint(f"[runs] GET {path}")
        response = api_or_exit(client.get, path)
        if args.events:
            eprint("[runs] events can carry payload data: secret-looking strings are redacted; do not paste this into tickets or PRs")
        print(json.dumps(scrub_obj(response), indent=2, sort_keys=True))
        return 0

    params: dict[str, Any] = {}
    if args.since:
        params["since"] = parse_when(args.since)
    eprint(f"[runs] GET {base}{'?since=' + params['since'] if params else ''}")
    response = api_or_exit(client.get, base, **params)
    rows = extract_rows(response, ("story_runs", "runs"))
    rows.sort(key=lambda r: str(r.get("start_time") or ""), reverse=True)
    stats = run_stats(rows)
    shown = rows[: max(args.limit, 0)]

    if args.json:
        keep = ("guid", "start_time", "end_time", "duration", "action_count", "event_count")
        print(json.dumps({"slug": args.slug, "env": args.env, "story_id": target.story_id, "since": params.get("since"),
                          **stats, "rows": [{k: r.get(k) for k in keep} for r in shown]}, indent=2))
        return 0

    print(f"### Runs of `{args.slug}` ({args.env}, story {target.story_id}){' since ' + params['since'] if params else ''}\n")
    columns = [("guid", "guid"), ("start_time", "start_time"), ("end_time", "end_time"), ("duration", "duration"),
               ("action_count", "actions"), ("event_count", "events")]
    print(markdown_table(shown, columns), end="")
    print(
        f"\nruns: {stats['runs']} · median_duration_s: {fmt(stats['median_duration_s'])} · "
        f"max_duration_s: {fmt(stats['max_duration_s'])} · last_start: {fmt(stats['last_start'])} · "
        f"in flight (no end_time): {stats['in_flight']}"
    )
    eprint("[runs] no status field exists on runs — failure is derived from error logs and live activity, never from this list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
