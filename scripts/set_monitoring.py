#!/usr/bin/env python3
"""Add monitoring recipients and monitor flags to a story (or its draft).

The three monitoring writes DESIGN.md §4.4 step 1 requires on every production
story, each behind its own flag so a workflow can call exactly what it needs:

* ``--add-recipient ADDRESS`` / ``--from-manifest``
      ``POST /api/v1/stories/{id}/recipients {address, draft_id?}`` — an email
      address or a webhook URL. ``--from-manifest`` adds the story's recipients:
      ``story.meta.yaml: monitoring.recipients`` when it is a **list** (the ops
      trio: the email DL and a second channel, never the router), otherwise —
      when it is ``manifest`` or absent — the environment's ``recipients`` list
      from ``stories/_manifest.yaml``. ``${OPS_ROUTER_URL}`` / ``${OPS_EMAIL_DL}``
      and any other ``${VAR}`` are expanded from the environment (the router URL
      carries a secret and is never committed).
* ``--remove-recipient ADDRESS``
      ``DELETE /api/v1/stories/{id}/recipients {address, draft_id?}``.
* ``--monitor-failures true|false`` and ``--locked true|false``
      ``PUT /api/v1/stories/{id} {monitor_failures, locked, draft_id?}`` —
      story-level "Notify when any action fails"; ``locked`` for the ops
      stories listed under ``locked_slugs``.
* ``--action-id ID`` with ``--no-events-seconds N`` / ``--action-monitor-failures``
  / ``--action-monitor-all-events``
      ``PUT /api/v1/actions/{id} {monitor_no_events_emitted, monitor_failures,
      monitor_all_events, draft_id?}`` — the "notify if no events emitted"
      watchdog on the entry or scheduled action (≈ 2× its interval).
      Use ``--watchdog-from-meta`` to look the action up by the name in
      ``story.meta.yaml: monitoring.no_events_watchdog`` and the id from a live
      read (``GET /api/v1/stories/{id}?include_live_activity=true``).

Draft semantics (VERIFY, DESIGN.md §10 #7)
-----------------------------------------
On a change-controlled story, ``PUT /stories/{id}`` and ``PUT /actions/{id}``
with ``draft_id`` land in that draft and go live on promotion. Whether
``POST /recipients`` with ``draft_id`` behaves the same, or applies to the live
story immediately, is not documented — confirm on a scratch story, then remove
this note. ``--dry-run`` prints every call and performs none.

Guard rails
-----------
Production needs ``TINES_ALLOW_PROD=1``. Stories listed in
``policies/never-touch.yml`` (``story_ids``) are refused unless the write goes
into a change-control draft the caller created for this ship or rollback
(``--via-draft``, accepted only together with ``--draft``) — the one path the
never-touch list allows (``ship_story.py``, ``rollback.yml``).

Examples
--------
    ./scripts/set_monitoring.py example-enrich-ip --env dev --from-manifest --monitor-failures true --draft 1234
    ./scripts/set_monitoring.py example-enrich-ip --env dev --action-id 987 --no-events-seconds 7200 --dry-run
    ./scripts/set_monitoring.py ops-error-router --env prod --draft 1234 --via-draft --locked true  # CI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    POLICIES_DIR,
    ApiError,
    ScriptError,
    StoryTarget,
    client_from_env,
    eprint,
    expand_env_refs,
    find_repo_root,
    guard_prod,
    load_story_meta,
    load_yaml_file,
    resolve_target,
)


def _bool(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in ("true", "yes", "on", "1"):
        return True
    if lowered in ("false", "no", "off", "0"):
        return False
    raise argparse.ArgumentTypeError(f"expected true|false, got {text!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="set_monitoring.py",
        description="Add recipients and monitor flags to a story or its draft.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("slug", help="story slug")
    parser.add_argument("--env", required=True, help="environment from the manifest")
    parser.add_argument("--story-id", type=int, help="override the story id")
    parser.add_argument("--draft", metavar="DRAFT_ID", help="apply to this change-control draft (see draft semantics)")
    parser.add_argument(
        "--from-manifest",
        action="store_true",
        help="add the story's recipients: story.meta.yaml monitoring.recipients when it is a list, else the manifest's list for --env",
    )
    parser.add_argument("--add-recipient", action="append", default=[], metavar="ADDRESS", help="email or webhook URL")
    parser.add_argument("--remove-recipient", action="append", default=[], metavar="ADDRESS")
    parser.add_argument("--monitor-failures", type=_bool, metavar="true|false", help="story-level notify on any failure")
    parser.add_argument("--locked", type=_bool, metavar="true|false", help="lock the story (ops stories after ship)")
    parser.add_argument("--action-id", type=int, help="action to update with the --action-* / --no-events-seconds flags")
    parser.add_argument("--no-events-seconds", type=int, help="watchdog: notify if no events emitted for N seconds")
    parser.add_argument("--action-monitor-failures", type=_bool, metavar="true|false")
    parser.add_argument("--action-monitor-all-events", type=_bool, metavar="true|false")
    parser.add_argument(
        "--watchdog-from-meta",
        action="store_true",
        help="set the watchdog on the action named in story.meta.yaml monitoring.no_events_watchdog",
    )
    parser.add_argument(
        "--via-draft",
        action="store_true",
        help="allow a never-touch story id when the write lands in this ship's or rollback's own draft (requires --draft)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print every call; perform no writes")
    return parser


def never_touch_ids(root: Path) -> set[int]:
    path = root / POLICIES_DIR / "never-touch.yml"
    if not path.exists():
        return set()
    try:
        data = load_yaml_file(path)
    except SystemExit:
        eprint("[monitoring] policies/never-touch.yml not readable without PyYAML; never-touch check skipped")
        return set()
    ids = set()
    for value in (data or {}).get("story_ids") or []:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return ids


def story_recipients(root: Path, slug: str, target: StoryTarget) -> list[str]:
    """Recipients for ``--from-manifest``, with ``${VAR}`` references expanded.

    ``story.meta.yaml: monitoring.recipients`` wins when it is a list — the ops
    trio lists the email DL (and a second channel), because the router must never
    be its own recipient nor monitor what it routes. ``manifest`` (or no value)
    means the environment's ``recipients`` from ``stories/_manifest.yaml``.
    """
    listed: Any = None
    try:
        meta = load_story_meta(root, slug) or {}
        listed = (meta.get("monitoring") or {}).get("recipients")
    except SystemExit:
        eprint("[monitoring] story.meta.yaml not readable without PyYAML; using the manifest's recipients")
    if isinstance(listed, list):
        source, raw = "story.meta.yaml monitoring.recipients", [str(x) for x in listed if x not in (None, "")]
    elif listed in (None, "manifest"):
        source, raw = f"stories/_manifest.yaml environments.{target.env}.recipients", list(target.recipients)
    else:
        raise ScriptError(f"story.meta.yaml monitoring.recipients must be `manifest` or a list, got {listed!r}")
    eprint(f"[monitoring] recipients from {source} ({len(raw)})")
    return [expand_env_refs(address) for address in raw]


def find_action_id_by_name(client: Any, story_id: int, action_name: str) -> Optional[int]:
    """Look an action id up from a live read of the story (include_live_activity)."""
    story = client.get(f"/api/v1/stories/{story_id}", include_live_activity="true")
    if not isinstance(story, dict):
        return None
    for key in ("agents", "actions"):
        for item in story.get(key) or []:
            if isinstance(item, dict) and item.get("name") == action_name and isinstance(item.get("id"), int):
                return item["id"]
    return None  # VERIFY: whether the story read lists actions with ids


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard_prod(args.env)
    root = find_repo_root()
    if args.via_draft and not args.draft:
        raise ScriptError("--via-draft is accepted only together with --draft (the write must land in a draft)")
    # Recipients are expanded later, and only from the list actually used (meta or manifest).
    target = resolve_target(root, args.slug, args.env, story_id=args.story_id, expand_recipients=False)
    if target.story_id == 0:
        raise ScriptError(f"{args.slug} has no story id in {args.env}; import it first")

    if target.story_id in never_touch_ids(root) and not (args.via_draft and args.draft):
        raise ScriptError(
            f"story {target.story_id} is in policies/never-touch.yml — refusing to write; "
            "ship.yml and rollback.yml write to it only inside their own draft (--draft ID --via-draft)"
        )

    wants_write = any(
        [
            args.from_manifest,
            args.add_recipient,
            args.remove_recipient,
            args.monitor_failures is not None,
            args.locked is not None,
            args.action_id is not None,
            args.watchdog_from_meta,
        ]
    )
    if not wants_write:
        raise ScriptError("nothing to do: pass --from-manifest, --add-recipient, --monitor-failures, --locked or --action-id")

    client = client_from_env(dry_run=args.dry_run)
    draft: dict[str, Any] = {"draft_id": args.draft} if args.draft else {}
    results: dict[str, Any] = {"slug": args.slug, "env": args.env, "story_id": target.story_id, "draft_id": args.draft}

    # -- recipients ----------------------------------------------------------- #
    recipients = list(args.add_recipient)
    if args.from_manifest:
        recipients.extend(story_recipients(root, args.slug, target))
    seen: set[str] = set()
    added: list[str] = []
    for address in recipients:
        if address in seen:
            continue
        seen.add(address)
        shown = address if "@" in address and "://" not in address else "<webhook url>"
        eprint(f"[monitoring] POST /api/v1/stories/{target.story_id}/recipients address={shown} {draft or ''}")
        try:
            client.post(f"/api/v1/stories/{target.story_id}/recipients", {"address": address, **draft})
            added.append(shown)
        except ApiError as exc:
            if exc.status in (409, 422) and "already" in str(exc).lower():
                eprint(f"[monitoring] recipient already present: {shown}")
                continue
            raise ScriptError(f"could not add recipient {shown}: {exc}") from None
    results["recipients_added"] = added

    removed: list[str] = []
    for address in args.remove_recipient:
        shown = address if "@" in address and "://" not in address else "<webhook url>"
        eprint(f"[monitoring] DELETE /api/v1/stories/{target.story_id}/recipients address={shown} {draft or ''}")
        try:
            client.delete(f"/api/v1/stories/{target.story_id}/recipients", {"address": address, **draft})
            removed.append(shown)
        except ApiError as exc:
            raise ScriptError(f"could not remove recipient {shown}: {exc}") from None
    results["recipients_removed"] = removed

    # -- story-level flags ---------------------------------------------------- #
    story_body: dict[str, Any] = {}
    if args.monitor_failures is not None:
        story_body["monitor_failures"] = args.monitor_failures
    if args.locked is not None:
        story_body["locked"] = args.locked
    if story_body:
        story_body.update(draft)
        eprint(f"[monitoring] PUT /api/v1/stories/{target.story_id} {story_body}")
        try:
            client.put(f"/api/v1/stories/{target.story_id}", story_body)
        except ApiError as exc:
            raise ScriptError(f"could not update the story: {exc}") from None
        results["story_update"] = {k: v for k, v in story_body.items() if k != "draft_id"}

    # -- action-level watchdog ------------------------------------------------ #
    action_id = args.action_id
    no_events = args.no_events_seconds
    if args.watchdog_from_meta:
        meta = load_story_meta(root, args.slug) or {}
        watchdog = ((meta.get("monitoring") or {}).get("no_events_watchdog")) or {}
        action_name, seconds = watchdog.get("action"), watchdog.get("seconds")
        if not action_name or not seconds:
            raise ScriptError("story.meta.yaml has no monitoring.no_events_watchdog {action, seconds}")
        if action_id is None:
            action_id = find_action_id_by_name(client, target.story_id, str(action_name))
            if action_id is None:
                raise ScriptError(
                    f"could not find action {action_name!r} by name on story {target.story_id} "
                    "(pass --action-id; whether the story read lists action ids is VERIFY)"
                )
        no_events = no_events or int(seconds)

    if action_id is not None:
        action_body: dict[str, Any] = {}
        if no_events is not None:
            action_body["monitor_no_events_emitted"] = no_events
        if args.action_monitor_failures is not None:
            action_body["monitor_failures"] = args.action_monitor_failures
        if args.action_monitor_all_events is not None:
            action_body["monitor_all_events"] = args.action_monitor_all_events
        if not action_body:
            raise ScriptError("--action-id needs --no-events-seconds, --action-monitor-failures or --action-monitor-all-events")
        action_body.update(draft)
        eprint(f"[monitoring] PUT /api/v1/actions/{action_id} {action_body}")
        try:
            client.put(f"/api/v1/actions/{action_id}", action_body)
        except ApiError as exc:
            raise ScriptError(f"could not update action {action_id}: {exc}") from None
        results["action_update"] = {"action_id": action_id, **{k: v for k, v in action_body.items() if k != "draft_id"}}

    if args.draft:
        eprint("[monitoring] applied with draft_id — goes live with the change request (recipient draft semantics VERIFY)")
    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
