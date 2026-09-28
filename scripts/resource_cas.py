#!/usr/bin/env python3
"""Compare-and-swap one key of a Resource — the ops lock, the kill switch. Writes to the tenant.

Endpoint (DESIGN.md §3.5 ``resource-cas``, §5.2, story-conventions.md "overlap guard")
-------------------------------------------------------------------------------------
``POST /api/v1/global_resources/{id}/replace {key, value, if_value}``

The replace happens only when the key's current value equals ``if_value``. A
**422** means it did not (another run holds the lock, or the value moved): the
script exits **3** and prints what the API said, which the research expects to
include the current value (VERIFY #19). Nothing else is retried: a mismatch is
an answer, not an error.

Uses (docs/06-rollback-and-recovery.md §7, docs/02-workflows.md §4.9)
--------------------------------------------------------------------
* free a stuck lock:   ``resource-cas <ops_lock id> --key lock --value free --if-value <stuck guid>``
* throw the kill switch: ``resource-cas <ops_limits id> --key enabled --value false --if-value true --typed``
* test the lock semantics on a scratch Resource before relying on them (VERIFY #19)

Values are strings unless ``--typed`` is given, which sends ``--value`` and
``--if-value`` as JSON literals (``false``, ``3``, ``"free"``) — whether the
endpoint compares typed JSON or strings is part of VERIFY #19. A value that
looks like a secret is refused: Resources referenced by this repository hold
flags, limits and lock tokens, never credentials, and a command line is not a
place for a secret.

Guard rails: production needs ``TINES_ALLOW_PROD=1``; in the IDE this
subcommand is an ``ask`` rule; ``--dry-run`` prints the call and sends nothing.

Examples
--------
    ./scripts/tines resource-cas 4321 --key lock --value free --if-value 3f2a…-guid
    ./scripts/tines resource-cas 4321 --key lock --value test-run --if-value free --dry-run
    ./scripts/tines resource-cas 5678 --key enabled --value false --if-value true --typed --env prod    # CI, TINES_ALLOW_PROD=1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import ApiError, ScriptError, client_from_env, eprint, guard_prod, looks_like_secret  # noqa: E402
from tines_read import default_env, one_line  # noqa: E402

KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resource_cas.py",
        description="Compare-and-swap one key of a Resource (POST …/global_resources/{id}/replace).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("resource_id", type=int, help="the Resource id (Resources page in Tines)")
    parser.add_argument("--key", required=True, help="the key inside the Resource, e.g. lock or enabled")
    parser.add_argument("--value", required=True, help="the new value")
    parser.add_argument("--if-value", required=True, dest="if_value", help="replace only when the current value equals this")
    parser.add_argument("--typed", action="store_true", help="send --value and --if-value as JSON literals (VERIFY #19)")
    parser.add_argument("--env", default=None, help="manifest environment, for the prod guard (default: $TINES_ENV or dev)")
    parser.add_argument("--dry-run", action="store_true", help="print the call; send nothing")
    return parser


def _coerce(text: str, typed: bool, what: str) -> Any:
    if not typed:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ScriptError(f"--typed: {what} {text!r} is not a JSON literal (quote strings: '\"free\"')") from None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_name = args.env or default_env()
    guard_prod(env_name)
    if not KEY_RE.match(args.key):
        raise ScriptError(f"--key {args.key!r} must be letters, digits, '_', '.', '-' (≤ 128)")
    for label, text in (("--value", args.value), ("--if-value", args.if_value)):
        pattern = looks_like_secret(text)
        if pattern:
            raise ScriptError(f"{label} looks like a secret ({pattern}); Resources used here hold flags, limits and lock tokens only")

    body = {"key": args.key, "value": _coerce(args.value, args.typed, "--value"), "if_value": _coerce(args.if_value, args.typed, "--if-value")}
    path = f"/api/v1/global_resources/{args.resource_id}/replace"
    client = client_from_env(dry_run=args.dry_run)
    eprint(f"[resource-cas] POST {path} key={args.key!r} value={body['value']!r} if_value={body['if_value']!r}")
    try:
        client.post(path, body)
    except ApiError as exc:
        if exc.status == 422:
            print(json.dumps({"resource_id": args.resource_id, "key": args.key, "swapped": False, "status": 422,
                              "detail": one_line(str(exc), 400)}))
            eprint("[resource-cas] not swapped: the current value is not --if-value (lock held, or the value moved). "
                   "Read the detail above; it should carry the current value (VERIFY #19).")
            return 3
        raise ScriptError(str(exc)) from None

    print(json.dumps({"resource_id": args.resource_id, "key": args.key, "swapped": not args.dry_run,
                      "value": body["value"], "dry_run": args.dry_run}))
    if not args.dry_run:
        eprint("[resource-cas] swapped. If this freed a lock or flipped the kill switch, say so in the ops thread.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
