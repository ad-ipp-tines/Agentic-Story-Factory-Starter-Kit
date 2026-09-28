#!/usr/bin/env python3
"""Import a committed story export into a target team — as a change-control draft.

What it does
------------
1. Resolves ``<slug>`` in ``--env`` (``dev`` | ``staging`` | ``prod``) from
   ``stories/_manifest.yaml``: team id, folder id, story id, ``new`` flag.
2. Reads ``stories/<slug>/story.json`` (or ``--file``) and pre-flights it: it
   must be normalised (no ``exported_at``), its ``name`` must equal
   ``story.meta.yaml: name`` when a meta file exists, and — for an existing
   story — the live story's name must match, because ``versionReplace``
   matches the target **by name** (DESIGN.md §3.6).
3. Optionally tags a rollback point first: ``POST /api/v1/stories/{id}/versions``
   with ``--version-name`` (DESIGN.md §4.2 step 4).
4. Calls ``POST /api/v1/stories/import`` with
   ``{data, team_id, folder_id, mode: "versionReplace", draft_name}`` for an
   existing story, or ``{data, team_id, folder_id, mode: "new", new_name}`` only
   when the target environment's ``story_id`` is still ``0`` (the slug is marked
   ``new: true``). Once ``<env>.story_id`` is non-zero, ``new: true`` is ignored.
   With ``--record-id`` a ``mode: new`` import writes the returned id into the
   manifest and, for ``prod``, removes ``new: true`` from the slug in the same
   edit (the follow-up PR carries both).

   **Production refuses ``mode: new``** — it would create a LIVE story in the
   prod team with no draft and no change request. The preferred path: a person
   creates an empty, disabled, change-controlled shell story with the export's
   exact name in the prod team [BY HAND], commits its id as
   ``stories.<slug>.prod.story_id`` (removing ``new: true``), and the next ship is a ``versionReplace``
   into a draft + change request. Only an explicit, logged
   ``--allow-new-in-prod "<reason>"`` (ship.yml passes it from the
   ``new_in_prod_reason`` workflow_dispatch input, never on a push) lets a
   ``mode: new`` import reach prod.
5. Prints a JSON line on stdout — ``{"slug", "env", "story_id", "draft_id",
   "mode", "draft_name"}`` — for the next step (``set_monitoring.py`` then
   ``change_request.py open``).

Change control — read this before running it against production
----------------------------------------------------------------
On a story with change control enabled, an import in ``versionReplace`` mode
with a ``draft_name`` lands in a **named draft**. Nothing is live until a
change request is opened (``change_request.py open``) and a **named person
approves it in Tines**. This script never calls promote and never sets
``bypass_approval`` — the only place that exists is the break-glass job of the
rollback workflow, with two reviewers and a log line (DESIGN.md §2.3 #19).
Production is refused unless ``TINES_ALLOW_PROD=1`` (the deploy workflow sets
it; the editor never does). Draft naming convention: ``git-<sha>`` for ships,
``rollback-<target>`` for rollbacks, ``monitor-<finding_id>`` for the ops pair.

Known unknowns (VERIFY in your tenant, then update DESIGN.md §10 #6)
--------------------------------------------------------------------
* Which response field carries the draft id. The script looks for
  ``draft_id``, ``draft.id`` and ``id`` and prints whatever it finds.
* Behaviour when the draft name already exists, and when a referenced
  credential or resource is missing in the target team (names must pre-exist).
* Whether ``data`` is accepted as the export object (sent by default) or must
  be a JSON string (``--data-as-string``).

Examples
--------
    ./scripts/import_story.py example-enrich-ip --env dev --dry-run
    ./scripts/import_story.py example-enrich-ip --env dev --draft-name git-abc1234 \\
        --version-name "pre-ship abc1234"
    TINES_ALLOW_PROD=1 ./scripts/import_story.py example-enrich-ip --env prod \\
        --draft-name git-$GITHUB_SHA --record-id          # CI only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    MANIFEST_RELATIVE,
    ApiError,
    ScriptError,
    client_from_env,
    eprint,
    find_repo_root,
    git_sha,
    guard_prod,
    load_json_file,
    load_story_meta,
    resolve_target,
    story_dir,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_story.py",
        description="Import stories/<slug>/story.json into a target team as a change-control draft.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("slug", help="story slug (folder name under stories/)")
    parser.add_argument("--env", required=True, help="target environment from the manifest (dev | staging | prod)")
    parser.add_argument("--file", type=Path, help="export to import (default: stories/<slug>/story.json)")
    parser.add_argument("--story-id", type=int, help="override the target story id")
    parser.add_argument("--team-id", type=int, help="override the target team id")
    parser.add_argument("--folder-id", type=int, help="override the target folder id")
    parser.add_argument("--draft-name", help="change-control draft name (default: git-<short sha>)")
    parser.add_argument("--new-name", help="story name when creating with mode=new (default: the export's name)")
    parser.add_argument("--version-name", help="tag a story version before importing (rollback point)")
    parser.add_argument("--record-id", action="store_true", help="after a mode=new import, write the returned id into the manifest")
    parser.add_argument(
        "--allow-new-in-prod",
        metavar="REASON",
        default="",
        help="EXPLICIT, LOGGED: allow a mode=new import into prod (creates a live story with no change request); "
        "a sentence of reason is required. Prefer a by-hand shell story whose id is committed first",
    )
    parser.add_argument("--data-as-string", action="store_true", help="send 'data' as a JSON string instead of an object (VERIFY)")
    parser.add_argument("--skip-name-check", action="store_true", help="do not compare the live story name with the export name")
    parser.add_argument("--dry-run", action="store_true", help="show what would be sent; perform reads only")
    return parser


def _find_draft_id(response: Any) -> Optional[str]:
    """Pull a draft id out of the import response (field name VERIFY)."""
    if not isinstance(response, dict):
        return None
    for key in ("draft_id", "story_draft_id"):
        if response.get(key) not in (None, ""):
            return str(response[key])
    draft = response.get("draft")
    if isinstance(draft, dict) and draft.get("id") not in (None, ""):
        return str(draft["id"])
    return None


def _find_story_id(response: Any, fallback: int) -> int:
    if isinstance(response, dict):
        for key in ("story_id", "id"):
            value = response.get(key)
            if isinstance(value, int) and value > 0:
                return value
        story = response.get("story")
        if isinstance(story, dict) and isinstance(story.get("id"), int):
            return story["id"]
    return fallback


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_content(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def record_story_id(root: Path, slug: str, env_name: str, story_id: int) -> bool:
    """Replace the ``story_id: 0`` placeholder for ``<slug>.<env>`` with the real id.

    Text-level on purpose (comments and ordering survive; no YAML writer). It
    handles the three shapes the manifest is written in:

    * flow on the slug line   ``slug: { dev: { story_id: 0 }, prod: { story_id: 0 } }``
    * flow on the env line    ``dev:  { story_id: 0 }``  (the committed shape)
    * block                   ``dev:`` newline ``story_id: 0``

    Only a ``0`` placeholder is ever replaced; an existing id is never
    overwritten. Returns True when a replacement happened.
    """
    path = root / MANIFEST_RELATIVE
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    slug_re = re.compile(rf"^(\s*){re.escape(slug)}\s*:(.*)$")
    flow_env_re = re.compile(rf"({re.escape(env_name)}\s*:\s*\{{\s*story_id\s*:\s*)0(\s*[,}}])")
    flow_id_re = re.compile(r"(\{\s*story_id\s*:\s*)0(\s*[,}])")
    block_id_re = re.compile(r"^(\s*story_id\s*:\s*)0(\s*(?:#.*)?)$")

    def write() -> bool:
        path.write_text("".join(lines), encoding="utf-8")
        return True

    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        m = slug_re.match(line)
        if not m:
            continue
        slug_indent = len(m.group(1))
        # shape 1: everything on the slug line
        new_rest, n = flow_env_re.subn(rf"\g<1>{story_id}\g<2>", m.group(2), count=1)
        if n:
            lines[i] = f"{m.group(1)}{slug}:{new_rest}\n"
            return write()
        # shapes 2 and 3: the env key on a deeper-indented line below the slug
        env_re = re.compile(rf"^(\s*{re.escape(env_name)}\s*:)(.*)$")
        j = i + 1
        while j < len(lines):
            cur = lines[j].rstrip("\n")
            if _is_content(cur):
                if _indent(cur) <= slug_indent:
                    return False  # left the slug's block without finding the env
                em = env_re.match(cur)
                if em:
                    new_body, n = flow_id_re.subn(rf"\g<1>{story_id}\g<2>", em.group(2), count=1)
                    if n:
                        lines[j] = f"{em.group(1)}{new_body}\n"
                        return write()
                    env_indent = _indent(cur)
                    k = j + 1
                    while k < len(lines):
                        cur2 = lines[k].rstrip("\n")
                        if _is_content(cur2):
                            if _indent(cur2) <= env_indent:
                                return False
                            sm = block_id_re.match(cur2)
                            if sm:
                                lines[k] = f"{sm.group(1)}{story_id}{sm.group(2)}\n"
                                return write()
                        k += 1
                    return False
            j += 1
        return False
    return False


def clear_new_flag(root: Path, slug: str) -> bool:
    """Remove ``new: true`` from ``<slug>`` in the manifest (text-level, like ``record_story_id``).

    Called after a ``mode: new`` import has recorded the **prod** id, so the
    follow-up PR that commits the id also drops the flag and the next ship is a
    ``versionReplace`` into a draft. Handles ``new: true`` on its own line inside
    the slug's block and inside a flow map on the slug line. Returns True when a
    change was made.
    """
    path = root / MANIFEST_RELATIVE
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    slug_re = re.compile(rf"^(\s*){re.escape(slug)}\s*:(.*)$")
    flow_new_re = re.compile(r"\s*,\s*new\s*:\s*true\b|\bnew\s*:\s*true\s*,\s*")
    block_new_re = re.compile(r"^\s*new\s*:\s*true\s*(?:#.*)?$")

    for i, raw in enumerate(lines):
        m = slug_re.match(raw.rstrip("\n"))
        if not m:
            continue
        slug_indent = len(m.group(1))
        new_rest, n = flow_new_re.subn("", m.group(2), count=1)
        if n:
            lines[i] = f"{m.group(1)}{slug}:{new_rest}\n"
            path.write_text("".join(lines), encoding="utf-8")
            return True
        for j in range(i + 1, len(lines)):
            cur = lines[j].rstrip("\n")
            if not _is_content(cur):
                continue
            if _indent(cur) <= slug_indent:
                return False  # left the slug's block without finding the flag
            if block_new_re.match(cur):
                del lines[j]
                path.write_text("".join(lines), encoding="utf-8")
                return True
        return False
    return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard_prod(args.env)
    root = find_repo_root()

    target = resolve_target(
        root, args.slug, args.env, story_id=args.story_id, team_id=args.team_id, folder_id=args.folder_id
    )
    export_path = args.file or (story_dir(root, args.slug) / "story.json")
    if not export_path.exists():
        raise ScriptError(f"export not found: {export_path} (run export_story.py first)")
    export = load_json_file(export_path)

    # -- pre-flight on the committed export ---------------------------------- #
    if "exported_at" in export:
        raise ScriptError(f"{export_path} is not normalised (contains exported_at); re-run export_story.py")
    export_name = export.get("name")
    if not export_name:
        raise ScriptError(f"{export_path} has no 'name'")
    meta = None
    try:
        meta = load_story_meta(root, args.slug)
    except SystemExit:
        eprint("[import] story.meta.yaml not readable without PyYAML; skipping the meta name check")
    if meta and meta.get("name") and meta["name"] != export_name:
        raise ScriptError(f"story.meta.yaml name {meta['name']!r} != export name {export_name!r}")
    if target.tier == "production" and meta and meta.get("change_control") not in (None, "required"):
        eprint("[import] warning: meta.change_control is not 'required' for a production-tier story")

    # mode: new only while this environment has no story id; `new: true` is ignored once
    # <env>.story_id is non-zero, so a recorded id can never create a duplicate story.
    mode = "new" if target.story_id == 0 else "versionReplace"
    if mode == "new" and args.env == "prod":
        reason = " ".join((args.allow_new_in_prod or "").split())
        if len(reason) < 10:
            raise ScriptError(
                f"{args.slug} has no prod story id, and a mode=new import would create a LIVE story in the prod team "
                "with no draft and no change request — refused. Preferred: create an empty, disabled, change-controlled "
                f"story named {export_name!r} in the prod team [BY HAND], commit its id as "
                f"stories.{args.slug}.prod.story_id in {MANIFEST_RELATIVE} (removing `new: true`), and ship again (versionReplace into a draft + "
                "change request). Otherwise pass --allow-new-in-prod \"<reason>\" (ship.yml: the new_in_prod_reason "
                "workflow_dispatch input), which is logged"
            )
        eprint(f"[import] NEW STORY IN PROD authorised explicitly (--allow-new-in-prod): {reason!r} — logged; no change request exists for this import")
    draft_name = args.draft_name or f"git-{git_sha() or 'local'}"
    client = client_from_env(dry_run=args.dry_run)

    # -- read-only checks against the tenant --------------------------------- #
    if mode == "versionReplace" and not args.skip_name_check:
        try:
            live = client.get(f"/api/v1/stories/{target.story_id}")
        except ApiError as exc:
            raise ScriptError(f"cannot read target story {target.story_id} in {args.env}: {exc}") from None
        live_name = live.get("name") if isinstance(live, dict) else None
        if live_name and live_name != export_name:
            raise ScriptError(
                f"live story {target.story_id} is named {live_name!r} but the export is {export_name!r}; "
                "versionReplace matches by name, so names must be identical in every environment"
            )
        if isinstance(live, dict) and live.get("team_id") not in (None, target.team_id):
            raise ScriptError(
                f"live story {target.story_id} belongs to team {live.get('team_id')}, not the {args.env} team "
                f"{target.team_id} — refusing to import across teams"
            )

    # -- rollback point ------------------------------------------------------ #
    if args.version_name and mode == "versionReplace":
        eprint(f"[import] POST /api/v1/stories/{target.story_id}/versions name={args.version_name!r}")
        try:
            client.post(f"/api/v1/stories/{target.story_id}/versions", {"name": args.version_name})
        except ApiError as exc:
            raise ScriptError(f"could not create the pre-import version: {exc}") from None

    # -- the import ---------------------------------------------------------- #
    payload: dict[str, Any] = {
        "data": json.dumps(export) if args.data_as_string else export,
        "team_id": target.team_id,
        "mode": mode,
    }
    if target.folder_id:
        payload["folder_id"] = target.folder_id
    if mode == "versionReplace":
        payload["draft_name"] = draft_name
    else:
        payload["new_name"] = args.new_name or export_name

    eprint(
        f"[import] {'DRY RUN ' if args.dry_run else ''}POST /api/v1/stories/import "
        f"slug={args.slug} env={args.env} mode={mode} team_id={target.team_id} "
        f"folder_id={target.folder_id} story_id={target.story_id or 'new'} "
        f"{'draft_name=' + draft_name if mode == 'versionReplace' else 'new_name=' + payload['new_name']!r}"
    )
    eprint(
        "[import] change control: this creates a DRAFT (or a new story); nothing is live until a change "
        "request is approved by a person in Tines. This script never promotes."
    )
    try:
        response = client.post("/api/v1/stories/import", payload)
    except ApiError as exc:
        hint = ""
        if exc.status in (400, 422):
            hint = " — if the message names a credential or resource, create it by the same name in the target team first"
        raise ScriptError(f"import failed: {exc}{hint}") from None

    if args.dry_run:
        result = {
            "slug": args.slug,
            "env": args.env,
            "story_id": target.story_id,
            "draft_id": None,
            "mode": mode,
            "draft_name": draft_name if mode == "versionReplace" else None,
            "dry_run": True,
        }
        print(json.dumps(result))
        return 0

    story_id = _find_story_id(response, target.story_id)
    draft_id = _find_draft_id(response)
    if mode == "versionReplace" and draft_id is None:
        eprint(
            "[import] warning: no draft id found in the response (field name VERIFY); "
            f"response keys: {sorted(response.keys()) if isinstance(response, dict) else type(response).__name__}"
        )
    if mode == "new" and args.record_id and story_id:
        if record_story_id(root, args.slug, args.env, story_id):
            eprint(f"[import] recorded story_id {story_id} for {args.slug}.{args.env} in {MANIFEST_RELATIVE}")
            if args.env == "prod":
                if clear_new_flag(root, args.slug):
                    eprint(f"[import] removed `new: true` from {args.slug} in {MANIFEST_RELATIVE} (the prod id is recorded)")
                else:
                    eprint(f"[import] could not remove `new: true` from {args.slug}; remove it by hand in the same PR")
        else:
            eprint(
                f"[import] could not patch the manifest for {args.slug}.{args.env}; "
                f"commit story_id: {story_id} by hand"
                f"{' and remove `new: true` from the slug' if args.env == 'prod' else ''}"
            )

    result = {
        "slug": args.slug,
        "env": args.env,
        "story_id": story_id,
        "draft_id": draft_id,
        "mode": mode,
        "draft_name": draft_name if mode == "versionReplace" else None,
    }
    print(json.dumps(result))
    eprint("[import] next: set_monitoring.py --from-manifest --draft <id>, then change_request.py open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
