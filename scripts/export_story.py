#!/usr/bin/env python3
"""Export one Tines story into ``stories/<slug>/story.json``.

What it does
------------
1. Resolves the story id for ``<slug>`` in ``--env`` (default ``dev``) from
   ``stories/_manifest.yaml`` — or takes ``--story-id`` directly.
2. Calls ``GET /api/v1/stories/{id}/export`` with
   ``randomize_urls=false&clear_recipients=true`` (DESIGN.md §3.5); adds
   ``draft_id=<id>`` when ``--draft`` is given so a change-control draft can be
   exported before it is promoted.
3. Normalises the export through ``scripts/normalize.jq`` — the one definition
   of what normalisation removes or replaces (``exported_at``; every action's
   ingress identifiers ``options.path`` / ``options.secret`` become
   ``<assigned-on-import>``; agent order preserved because ``links`` are
   index-based) — and writes it with sorted keys. With ``--normalizer auto``
   (the default) jq is used when it is on PATH; without it the Python mirror
   ``tines_common.normalize_export`` applies the same two steps. Python always
   writes the file, so the formatting is identical either way, and the agent
   order is checked unchanged after jq.
4. Stamps ``exported_from: { env, story_id, draft_id, at, sha }`` into
   ``stories/<slug>/story.meta.yaml`` unless ``--no-stamp`` is given, so the
   Stop hook can tell a stale export from a fresh one.

Webhook paths and secrets never reach git
-----------------------------------------
The request still asks for ``randomize_urls=false`` (DESIGN.md §3.5), so the
raw export carries each Webhook action's ``path`` and ``secret`` (observed on
real exports) and an MCP server action's ``path``. Normalisation replaces them
BY KEY NAME on every action with ``<assigned-on-import>`` before anything is
written, so the router URL, the approval callback and the Mode 4 path are never
committed. ``lint_story.py`` reports any real value that survives as
``webhook_secret_in_export`` (severity **error**) and lint.yml adds a matching
gitleaks rule. Whether an import into an existing story keeps that story's own
path and secret is VERIFY #6; if stable production URLs are needed, keep them in
GitHub environment secrets and re-apply them at ship time — never in the export.
``--raw`` skips normalisation and is for debugging only (with ``--out`` or
``--stdout``); a raw export committed to ``stories/`` fails lint. ``--raw`` is
**refused unless GITHUB_ACTIONS=true**: in an editor it would put every live
Webhook path and secret into the model's context or onto disk.

Where ``--out`` may write
-------------------------
Only under ``.sdlc/`` (local, gitignored), ``$RUNNER_TEMP`` (CI), or the story's
own ``stories/<slug>/`` folder — and, in GitHub Actions only, ``.tines/drift/``
(drift.yml's working folder). Anything else is refused, so an export can never
overwrite ``.claude/``, ``policies/`` or another story (a symlink is resolved
first).

``webhook-url`` — one entry Webhook, in memory
----------------------------------------------
``./scripts/tines webhook-url <slug> [--env dev] [--story-id ID] [--action NAME]``
reads the story's export in memory and returns ONLY the named Webhook action's
``path`` and ``secret`` — never a file, never the rest of the raw export.
``sdlc_eval.py`` imports ``entry_webhook()`` for the same thing and keeps the
values in memory; the command-line form prints them only when
GITHUB_ACTIONS=true, after ``::add-mask::`` lines for both.

The export never contains credential values, resource contents or events —
Tines omits them by design. Recipients are cleared on export and set again from
the manifest by ``set_monitoring.py`` on ship.

Examples
--------
    ./scripts/export_story.py example-enrich-ip
    ./scripts/export_story.py example-enrich-ip --env dev --draft 1234
    ./scripts/export_story.py ops-error-router --story-id 42 --out .sdlc/x.json --no-stamp
    TINES_ENV=prod TINES_ALLOW_PROD=1 ./scripts/export_story.py example-enrich-ip --env prod \\
        --out .tines/drift/example-enrich-ip.json --no-stamp      # the nightly drift check

Environment: ``TINES_TENANT``, ``TINES_API_KEY`` (team-scoped), optional
``TINES_TEAM_ID`` / ``TINES_STORY_ID`` overrides, ``TINES_ALLOW_PROD=1`` for prod.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

NORMALIZE_JQ = Path(__file__).resolve().parent / "normalize.jq"
WEBHOOK_TYPE = "Agents::WebhookAgent"   # scripts/lint_story.py WEBHOOK_TYPE

from tines_common import (  # noqa: E402
    ApiError,
    ScriptError,
    client_from_env,
    dump_json,
    eprint,
    find_repo_root,
    git_sha,
    guard_prod,
    normalize_export,
    resolve_target,
    stamp_exported_from,
    story_dir,
    utc_now,
)


def in_ci() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def _within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def check_out_path(root: Path, slug: str, out: Path) -> Path:
    """Refuse an ``--out`` outside ``.sdlc/``, ``$RUNNER_TEMP`` (CI) or ``stories/<slug>/`` (and ``.tines/drift/``, CI only).

    Without this, ``--out`` is an arbitrary file write that sidesteps the editor's Write/Edit deny rules (for example
    over ``.claude/settings.json`` or ``policies/never-touch.yml``). The target is resolved first, so a symlink or a
    ``..`` cannot lead out of an allowed folder.
    """
    target = (out if out.is_absolute() else Path.cwd() / out).resolve()
    allowed = [(root / ".sdlc").resolve(), story_dir(root, slug).resolve()]
    if in_ci():
        if os.environ.get("RUNNER_TEMP"):
            allowed.append(Path(os.environ["RUNNER_TEMP"]).resolve())
        allowed.append((root / ".tines" / "drift").resolve())   # drift.yml's working folder
    if not any(_within(target, base) for base in allowed):
        raise ScriptError(
            f"--out {out}: an export is written only under .sdlc/, stories/{slug}/ or (in GitHub Actions) $RUNNER_TEMP "
            "or .tines/drift/ — never over repository configuration"
        )
    return target


def entry_webhook(slug: str, env: str, story_id: int, *, name: Optional[str] = None, prefer: Optional[str] = None) -> dict[str, Any]:
    """The one entry Webhook's ``path`` and ``secret``, read from the story's export IN MEMORY.

    Nothing is written and nothing is printed: the caller holds the two values only as long as it needs them. ``prefer``
    narrows to the Webhooks of that name when any exist; ``name`` requires it; exactly one Webhook must remain. Also
    returns ``action_names`` — ``{id: name}`` for every action (ids and names are not secrets), which ``eval-run`` uses to
    name the actions in a run's events. Same endpoint as ``export``: ``GET /api/v1/stories/{id}/export``.
    """
    guard_prod(env)
    client = client_from_env()
    try:
        data = client.get(f"/api/v1/stories/{int(story_id)}/export", randomize_urls="false", clear_recipients="true")
    except ApiError as exc:
        raise ScriptError(str(exc)) from None
    if not isinstance(data, dict) or "agents" not in data:
        raise ScriptError(f"the export of {slug} (story {story_id}) did not return a story object with 'agents' — check the story id and the key's team")
    agents = [a for a in (data.get("agents") or []) if isinstance(a, dict)]
    hooks = [a for a in agents if a.get("type") == WEBHOOK_TYPE]
    if prefer:
        hooks = [a for a in hooks if a.get("name") == prefer] or hooks
    if name:
        hooks = [a for a in hooks if a.get("name") == name]
    if len(hooks) != 1:
        raise ScriptError(f"expected exactly one entry Webhook in {slug} (story {story_id}), found {len(hooks)} — name it (--action)")
    opts = hooks[0].get("options") or {}
    return {
        "name": hooks[0].get("name"),
        "path": str(opts.get("path") or ""),
        "secret": str(opts.get("secret") or ""),
        "action_names": {a.get("id"): a.get("name") for a in agents if a.get("id") is not None},
    }


def main_webhook_url(argv: list[str]) -> int:
    """``./scripts/tines webhook-url``: the named Webhook's path and secret, printed only in GitHub Actions (masked)."""
    parser = argparse.ArgumentParser(
        prog="tines webhook-url",
        description="Print ONE entry Webhook's path and secret from the story's export (GitHub Actions only, masked first).",
    )
    parser.add_argument("slug", help="story slug (folder name under stories/)")
    parser.add_argument("--env", default="dev", help="environment in the manifest (default: dev)")
    parser.add_argument("--story-id", type=int, help="override the story id from the manifest")
    parser.add_argument("--action", help="the Webhook action's name (required when the story has more than one Webhook)")
    args = parser.parse_args(argv)
    if not in_ci():
        raise ScriptError(
            "webhook-url prints a live Webhook path and secret, so it runs only in GitHub Actions (GITHUB_ACTIONS=true); "
            "locally, ./scripts/sdlc eval-run reads them in memory"
        )
    story_id = args.story_id
    if story_id is None:
        story_id = resolve_target(find_repo_root(), args.slug, args.env).story_id
        if not story_id:
            raise ScriptError(f"{args.slug} has no story id in {args.env} in stories/_manifest.yaml")
    hook = entry_webhook(args.slug, args.env, story_id, name=args.action)
    for value in (hook["path"], hook["secret"]):
        if value:
            print(f"::add-mask::{value}")
    print(json.dumps({"action": hook["name"], "path": hook["path"], "secret": hook["secret"]}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_story.py",
        description="Export one Tines story to stories/<slug>/story.json (normalised).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("slug", help="story slug (folder name under stories/)")
    parser.add_argument("--env", default="dev", help="environment in the manifest (default: dev)")
    parser.add_argument("--story-id", type=int, help="override the story id from the manifest")
    parser.add_argument("--team-id", type=int, help="override the team id (only used for the manifest check)")
    parser.add_argument("--draft", metavar="DRAFT_ID", help="export a change-control draft instead of the live story")
    parser.add_argument("--out", type=Path, help="write here instead of stories/<slug>/story.json")
    parser.add_argument(
        "--randomize-urls",
        action="store_true",
        help="ask Tines to randomise webhook paths/secrets in the export (default: keep them; normalisation replaces "
        "every path/secret with <assigned-on-import> either way, so none reaches git)",
    )
    parser.add_argument(
        "--keep-recipients",
        action="store_true",
        help="do not clear recipients in the export (default: clear; ship sets them from the manifest)",
    )
    parser.add_argument("--no-stamp", action="store_true", help="do not update exported_from in story.meta.yaml")
    parser.add_argument("--raw", action="store_true", help="write the export without normalisation (debugging only)")
    parser.add_argument("--stdout", action="store_true", help="print the normalised JSON to stdout instead of a file")
    parser.add_argument(
        "--normalizer",
        choices=("auto", "jq", "python"),
        default="auto",
        help="auto (default): scripts/normalize.jq when jq is on PATH, else the Python mirror; jq: require it",
    )
    return parser


def _agent_order(export: Any) -> list[Any]:
    agents = export.get("agents") if isinstance(export, dict) else None
    return [a.get("guid", a.get("name")) if isinstance(a, dict) else a for a in (agents or [])]


def normalise(data: dict[str, Any], how: str) -> tuple[dict[str, Any], str]:
    """Apply scripts/normalize.jq (or its Python mirror); return ``(export, which)``.

    jq only computes the result (compact output); ``dump_json`` writes the file,
    so formatting never depends on the normaliser. ``links[]`` reference agents
    by index, so the agent order is compared before and after and a change is fatal.
    """
    jq = shutil.which("jq") if how in ("auto", "jq") else None
    if jq and NORMALIZE_JQ.exists():
        proc = subprocess.run(
            [jq, "-c", "-f", str(NORMALIZE_JQ)],
            input=json.dumps(data, ensure_ascii=False),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise ScriptError(f"normalize.jq failed: {proc.stderr.strip()[:300]}")
        out = json.loads(proc.stdout)
        if _agent_order(out) != _agent_order(data):
            raise ScriptError("normalize.jq changed the agent order — links are index-based; refusing to write the export")
        return out, "normalize.jq"
    if how == "jq":
        raise ScriptError("--normalizer jq: jq is not on PATH or scripts/normalize.jq is missing")
    return normalize_export(data), "python mirror (exported_at and every action's ingress path/secret; install jq to apply scripts/normalize.jq itself)"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["webhook-url"]:
        return main_webhook_url(argv[1:])
    args = build_parser().parse_args(argv)
    guard_prod(args.env)
    if args.raw and not in_ci():
        raise ScriptError("--raw is refused outside GitHub Actions (GITHUB_ACTIONS=true): a raw export carries every live "
                          "Webhook path and secret; use ./scripts/tines webhook-url (CI) or eval-run, which read one in memory")
    root = find_repo_root()
    if args.out is not None:
        check_out_path(root, args.slug, args.out)

    if args.story_id is not None and (args.out or args.stdout):
        # Fully explicit: no manifest needed.
        story_id = args.story_id
        target_slug = args.slug
    else:
        target = resolve_target(root, args.slug, args.env, story_id=args.story_id, team_id=args.team_id)
        if target.story_id == 0:
            if args.env == "dev":
                raise ScriptError(
                    f"{args.slug} has no dev story id in stories/_manifest.yaml. A new story is created in the dev team "
                    "through /mcp, not by an import, so nothing records its id for you: after the builder creates it, "
                    f"set `dev: {{ story_id: <id> }}` under stories.{args.slug} (an id is not a secret), then export again"
                )
            raise ScriptError(f"{args.slug} has no story id in {args.env} yet (new: true) — nothing to export there")
        story_id = target.story_id
        target_slug = target.slug

    client = client_from_env()
    params = {
        "randomize_urls": "true" if args.randomize_urls else "false",
        "clear_recipients": "false" if args.keep_recipients else "true",
    }
    if args.draft:
        params["draft_id"] = args.draft

    eprint(f"[export] GET /api/v1/stories/{story_id}/export {params}")
    try:
        data = client.get(f"/api/v1/stories/{story_id}/export", **params)
    except ApiError as exc:
        raise ScriptError(str(exc)) from None
    if not isinstance(data, dict) or "agents" not in data:
        raise ScriptError("export did not return a story object with 'agents' — check the story id and the key's team")

    if args.raw:
        export, which = data, "none (--raw)"
    else:
        export, which = normalise(data, args.normalizer)
    eprint(f"[export] normalised with {which}")
    text = dump_json(export)

    if args.stdout:
        sys.stdout.write(text)
        return 0

    out_path = args.out or (story_dir(root, target_slug) / "story.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    eprint(f"[export] wrote {out_path} ({len(export.get('agents', []))} actions, name={export.get('name')!r})")

    if not args.no_stamp and args.out is None:
        meta_path = story_dir(root, target_slug) / "story.meta.yaml"
        stamp_exported_from(
            meta_path,
            env_name=args.env,
            story_id=story_id,
            draft_id=str(args.draft or ""),
            at=utc_now(),
            sha=git_sha() or "",
        )
        eprint(f"[export] stamped exported_from in {meta_path}")

    eprint("[export] next: ./scripts/lint_story.py " + str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
