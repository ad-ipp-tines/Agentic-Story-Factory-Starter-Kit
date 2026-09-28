#!/usr/bin/env python3
"""Append one row to policies/break-glass-log.md. No network. Used by rollback.yml's break-glass jobs.

The log is append-only (policies/break-glass-log.md): one row per
``POST /api/v1/stories/{id}/disable`` or ``bypass_approval`` used in anger, written
**in the same run** that used it (DESIGN.md §2.3 row 19, §3.2). This helper
inserts the row as the last line of the log table — never at the end of the
file, where it would fall outside the table — and never edits an earlier row.
A re-enable is logged as its own row (the file's rule: add a row, never edit one).

Columns, in the file's order:
``Date (UTC) | Story (slug · env) | Who (role) | Action | Reason | change_request_id |
Audit-log ids | Follow-up PR | Re-enabled at``

* **Who** is a role, never a name — the audit logs and the GitHub run hold the
  identities (the file says so). The workflow passes the role it actually
  verified (``--role``: the dispatcher plus the distinct environment approvers it
  counted in the run); the default says only where to look, never a fixed count.
* **Audit-log ids** starts as the GitHub run id; a person adds the Tines audit-log
  ids in a later row once read (``./scripts/tines audit --after <ts> --story-id <id>``).
* Cell text is one line, ``|`` escaped, and anything matching the repository's
  secret patterns is refused — a reason is prose, never a token.
* ``--phase intent`` writes the row BEFORE the privileged call (``Action`` reads
  "<action> — INTENT"), so a disable or bypass can never stand without a log
  line; ``--phase outcome`` (the default) writes the result row after it.
* ``--check`` validates the inputs (reason, role, PR URL) and writes nothing —
  ``rollback.yml``'s plan job runs it before any job acts.

The workflow commits the file on a ``break-glass/<slug>/<run id>`` branch and
opens (or updates) a PR labelled ``break-glass``; the row prints to stdout for
the job summary.

Examples
--------
    python3 scripts/break_glass_log.py --check --slug example-enrich-ip --env prod --action disable \\
        --reason "vendor quota burning"
    python3 scripts/break_glass_log.py --phase intent --slug example-enrich-ip --env prod --action disable \\
        --reason "vendor quota burning" --run-id "$GITHUB_RUN_ID" --role "dispatcher + 2 distinct approvers"
    python3 scripts/break_glass_log.py --slug example-enrich-ip --env prod --action bypass_approval \\
        --reason "…" --change-request-id 55 --run-id "$GITHUB_RUN_ID" --pr-url https://github.com/<org>/<repo>/pull/12
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import ScriptError, find_repo_root, looks_like_secret  # noqa: E402

HEADER_PREFIX = "| Date (UTC)"
ACTIONS = ("disable", "bypass_approval", "re-enable")
DEFAULT_ROLE = "break-glass job in rollback.yml (approvers: see the GitHub run)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="break_glass_log.py",
        description="Append one row to the break-glass log table (append-only; no network).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("--slug", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--action", required=True, choices=ACTIONS)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--outcome", choices=("ok", "failed"), default="ok", help="failed rows are still logged")
    parser.add_argument("--change-request-id", default="", help="the request promoted with bypass_approval, if any")
    parser.add_argument("--run-id", default="", help="GitHub run id (goes into the audit-log ids column)")
    parser.add_argument("--pr-url", default="", help="the follow-up / rollback PR, if known")
    parser.add_argument("--role", default=DEFAULT_ROLE, help="who, as a role (never a name) — the approvals actually verified")
    parser.add_argument("--phase", choices=("intent", "outcome"), default="outcome",
                        help="intent: the row written BEFORE the privileged call; outcome (default): the result row after it")
    parser.add_argument("--check", action="store_true", help="validate the inputs only; write nothing (rollback.yml plan job)")
    parser.add_argument("--log", type=Path, help="default: policies/break-glass-log.md")
    return parser


def cell(text: str, limit: int = 300) -> str:
    one = re.sub(r"\s+", " ", str(text or "")).strip()
    one = one.replace("|", "\\|")
    return one if len(one) <= limit else one[: limit - 1] + "…"


def insert_row(text: str, row: str) -> str:
    lines = text.splitlines()
    header = next((i for i, line in enumerate(lines) if line.startswith(HEADER_PREFIX)), None)
    if header is None:
        raise ScriptError("the break-glass log has no table header starting with '| Date (UTC)'; refusing to guess")
    last = header
    for i in range(header + 1, len(lines)):
        if lines[i].startswith("|"):
            last = i
        else:
            break
    lines.insert(last + 1, row)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for label, value in (("--reason", args.reason), ("--role", args.role), ("--pr-url", args.pr_url)):
        pattern = looks_like_secret(value or "")
        if pattern:
            raise ScriptError(f"{label} looks like it carries a secret ({pattern}); the log is committed — write prose")
    if len(args.reason.strip()) < 10:
        raise ScriptError("--reason must be at least a sentence")
    if re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", args.role):
        raise ScriptError("--role must be a role, not an address or a name")
    if args.check:
        print("break_glass_log: inputs valid (nothing written)")
        return 0

    now = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
    if args.phase == "intent":
        action = f"{args.action} — INTENT (logged before the call; the outcome row follows)"
    else:
        action = args.action if args.outcome == "ok" else f"{args.action} — FAILED, story unchanged"
    audit = f"GitHub run {args.run_id}; Tines ids: add in a later row" if args.run_id else "Tines ids: add in a later row"
    row = "| " + " | ".join([
        now,
        cell(f"{args.slug} · {args.env}"),
        cell(args.role),
        cell(action),
        cell(args.reason),
        cell(args.change_request_id) or "—",
        cell(audit),
        cell(args.pr_url) or "—",
        now if (args.action == "re-enable" and args.outcome == "ok" and args.phase == "outcome") else "",
    ]) + " |"

    path = args.log or (find_repo_root() / "policies" / "break-glass-log.md")
    if not path.exists():
        raise ScriptError(f"{path} not found")
    path.write_text(insert_row(path.read_text(encoding="utf-8"), row), encoding="utf-8")
    print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
