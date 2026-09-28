#!/usr/bin/env python3
"""Ship committed story exports into a target team — as change-control drafts.

This is the per-story chain the deploy workflow (``.github/workflows/ship.yml``)
runs, and what ``./scripts/tines ship`` calls locally to rehearse it against the
dev team. It orchestrates the single-purpose scripts in this directory in the
order DESIGN.md §4.2 step 4 prescribes and stops exactly where a person must
act. It **never promotes** and never sends ``bypass_approval``.

Per slug
--------
1. ``diff_story.py``     semantic diff of ``stories/<slug>/story.json`` against
                         ``--rollback-ref`` (default ``HEAD~1``) — embedded in the
                         change-request description so the approver sees it in Tines.
2. ``import_story.py``   ``POST /api/v1/stories/{id}/versions {name: "pre-ship <sha>"}``
                         (the rollback point) and then
                         ``POST /api/v1/stories/import {data, team_id, folder_id,
                         mode: "versionReplace", draft_name: "git-<sha>"}``.
                         Only when the environment's ``story_id`` is still ``0``
                         (``new: true``) is the story created with ``mode: "new"``
                         instead; its id is recorded in ``stories/_manifest.yaml``
                         and, for prod, ``new: true`` is removed in the same edit
                         (the workflow opens the PR). There is no draft and no
                         change request on that first ship; the next ship opens it.
                         **In prod, ``import_story.py`` refuses ``mode: "new"``**
                         unless ``--allow-new-in-prod "<reason>"`` is given here
                         (ship.yml passes it only from the ``new_in_prod_reason``
                         workflow_dispatch input; it is logged in the summary).
                         Preferred: a by-hand, disabled, change-controlled shell
                         story whose prod id is committed first, so the first
                         prod ship is already a draft + change request.
3. ``set_monitoring.py`` ``POST /api/v1/stories/{id}/recipients {address, draft_id}``
                         for every recipient of the story — ``story.meta.yaml:
                         monitoring.recipients`` when it is a list (the ops
                         trio), else the manifest's list for the environment —
                         and ``PUT /api/v1/stories/{id}
                         {monitor_failures: true[, locked: true], draft_id}``.
                         ``--via-draft`` lets these writes reach a story id in
                         ``policies/never-touch.yml``: they land in this ship's
                         own draft, never on the live story.
4. ``change_request.py`` ``POST /api/v1/stories/{id}/change_request {draft_id,
                         title, description}``, then ``GET …/change_request/view``
                         for the Markdown summary the workflow puts in front of
                         the approver.
5. A JSON notification to the ops router webhook (``OPS_ROUTER_URL``) so the
   change request shows up in the ops thread — skipped when the variable is
   unset or ``--no-notify`` is given.

Change control — the contract this script keeps
------------------------------------------------
Nothing becomes live here. An import with ``draft_name`` lands in a **named
draft**; the change request is opened for a **named person to approve in
Tines** (and push, or run ``promote.yml`` on an APPROVED request). The only
place ``bypass_approval`` exists in this repository is the break-glass job of
the rollback workflow (two reviewers, a reason, a log line). Production is
refused unless ``TINES_ALLOW_PROD=1`` — the workflow sets it inside the
``production`` GitHub environment; the editor never does.

Known unknowns (VERIFY, DESIGN.md §10)
---------------------------------------
* #6 — the import response field that carries the draft id; behaviour when the
  draft name already exists; what a ``mode: new`` import creates when the
  tenant policy "Enable by default" is on. A missing draft id fails the slug.
* #7 — whether ``POST /recipients`` with ``draft_id`` waits for promotion or
  applies to the live story at once.

Examples
--------
    ./scripts/ship_story.py example-enrich-ip --env dev --dry-run
    ./scripts/ship_story.py example-enrich-ip --env dev --source-url https://github.com/<org>/<repo>/pull/12
    TINES_ALLOW_PROD=1 ./scripts/ship_story.py example-enrich-ip ops-error-router --env prod \\
        --sha "$GITHUB_SHA" --summary-file "$GITHUB_STEP_SUMMARY" --results-file ship.jsonl    # CI only
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    ScriptError,
    eprint,
    find_repo_root,
    git_sha,
    guard_prod,
    load_manifest,
    resolve_target,
    story_dir,
)

try:  # only needed for the optional ops-router notification
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

HERE = Path(__file__).resolve().parent


class StepFailed(Exception):
    """A child script exited non-zero; ``stdout`` holds whatever it printed."""

    def __init__(self, script: str, code: int, stdout: str) -> None:
        self.script = script
        self.code = code
        self.stdout = stdout
        super().__init__(f"{script} exited {code}")


def run_script(script: str, args: list[str]) -> tuple[str, Optional[dict[str, Any]]]:
    """Run a sibling script; forward its stderr; return ``(stdout, last JSON line or None)``.

    Each child keeps its own guards (``guard_prod``, never-touch, name checks),
    so this orchestrator adds no privilege of its own.
    """
    cmd = [sys.executable, str(HERE / script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        sys.stderr.flush()
    if proc.returncode != 0:
        raise StepFailed(script, proc.returncode, proc.stdout)
    data: Optional[dict[str, Any]] = None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                data = parsed
                break
    return proc.stdout, data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ship_story.py",
        description="Version → import as draft → recipients/monitor flags → change request. Never promotes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("slugs", nargs="+", help="story slugs (folders under stories/)")
    parser.add_argument("--env", required=True, help="target environment from the manifest (dev | staging | prod)")
    parser.add_argument("--sha", help="commit being shipped (default: git HEAD)")
    parser.add_argument("--source-url", help="PR or commit URL cited in the change-request description")
    parser.add_argument("--rollback-ref", default="HEAD~1", help="git ref of the previous good export (default HEAD~1)")
    parser.add_argument("--draft-prefix", default="git", help="draft name prefix: <prefix>-<sha7> (default git)")
    parser.add_argument("--summary-file", type=Path, help="append a Markdown summary here (e.g. $GITHUB_STEP_SUMMARY)")
    parser.add_argument("--results-file", type=Path, help="append one JSON line per slug here")
    parser.add_argument("--no-notify", action="store_true", help="do not POST the result to OPS_ROUTER_URL")
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds to wait between stories (rate limits)")
    parser.add_argument("--continue-on-error", action="store_true", help="ship the remaining slugs after a failure")
    parser.add_argument(
        "--allow-new-in-prod",
        metavar="REASON",
        default="",
        help="EXPLICIT, LOGGED: passed to import_story.py so a new: true slug may be created in prod with mode=new "
        "(no change request). ship.yml sets it only from the new_in_prod_reason workflow_dispatch input",
    )
    parser.add_argument("--dry-run", action="store_true", help="print every call; perform no writes")
    return parser


def read_diff(root: Path, slug: str, against: str, dry_run: bool) -> str:
    export = story_dir(root, slug) / "story.json"
    try:
        stdout, _ = run_script("diff_story.py", [str(export), "--against", against])
        return stdout.strip() or "(no diff output)"
    except StepFailed as exc:
        eprint(f"[ship] diff unavailable for {slug}: exit {exc.code}")
        return "(semantic diff unavailable in this run)"


def notify(url: str, payload: dict[str, Any]) -> bool:
    """POST the ship result to the ops router webhook. The URL is never printed."""
    if requests is None:
        eprint("[ship] notification skipped: the 'requests' package is not installed")
        return False
    try:
        resp = requests.post(url, json=payload, timeout=15)
    except requests.RequestException as exc:  # type: ignore[attr-defined]
        eprint(f"[ship] notification failed: {exc.__class__.__name__}")
        return False
    if resp.status_code >= 300:
        eprint(f"[ship] notification returned HTTP {resp.status_code}")
        return False
    return True


def ship_one(root: Path, slug: str, args: argparse.Namespace, manifest: dict[str, Any], sha7: str) -> dict[str, Any]:
    target = resolve_target(root, slug, args.env, manifest=manifest, expand_recipients=False)
    env_cfg = (manifest.get("environments") or {}).get(args.env) or {}
    locked = slug in (env_cfg.get("locked_slugs") or [])
    # mode: new only while this environment has no story id; `new: true` is ignored once it has one.
    is_new = target.story_id == 0
    dry = ["--dry-run"] if args.dry_run else []
    result: dict[str, Any] = {
        "slug": slug,
        "env": args.env,
        "sha": sha7,
        "mode": "new" if is_new else "versionReplace",
        "story_id": target.story_id or None,
        "draft_id": None,
        "draft_name": None,
        "change_request_id": None,
        "change_request_status": None,
        "version": None,
        "recipients_added": 0,
        "locked": locked,
        "dry_run": args.dry_run,
        "next": None,
    }

    diff_text = read_diff(root, slug, args.rollback_ref, args.dry_run)
    diff_path = Path(os.environ.get("RUNNER_TEMP") or root / ".tines") / f"ship-{slug}.diff.md"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(diff_text + "\n", encoding="utf-8")

    if is_new:
        # First import of a new story: mode=new creates it; there is no draft to open a
        # change request on yet. The id is recorded in the manifest for the follow-up PR.
        new_args = [slug, "--env", args.env, "--record-id", *dry]
        if args.allow_new_in_prod:
            new_args += ["--allow-new-in-prod", args.allow_new_in_prod]
            result["new_in_prod_reason"] = " ".join(args.allow_new_in_prod.split())
        _, imported = run_script("import_story.py", new_args)
        story_id = (imported or {}).get("story_id") or target.story_id
        result["story_id"] = story_id or None
        result["next"] = (
            "first import created the story with no change request; merge the manifest PR the workflow opens "
            "(it records the id and, for prod, removes `new: true`), enable change control on it if the tenant "
            "policy 'Enable by default' is off [BY HAND] (VERIFY #6), then run ship.yml by workflow_dispatch for "
            "this slug to open a change request — a merge that touches only stories/_manifest.yaml does not ship"
        )
        if story_id and not args.dry_run:
            # Recipients and the failure flag on the new story itself (no draft exists yet; the id was
            # just created, so it cannot be in policies/never-touch.yml).
            mon_args = [slug, "--env", args.env, "--story-id", str(story_id), "--from-manifest", "--monitor-failures", "true"]
            try:
                _, mon = run_script("set_monitoring.py", mon_args)
                result["recipients_added"] = len((mon or {}).get("recipients_added") or [])
            except StepFailed as exc:
                eprint(f"[ship] monitoring on the new story failed (exit {exc.code}); set it by hand or re-run")
        return result

    version_name = f"pre-ship {sha7}"
    draft_name = f"{args.draft_prefix}-{sha7}"
    _, imported = run_script(
        "import_story.py",
        [slug, "--env", args.env, "--draft-name", draft_name, "--version-name", version_name, *dry],
    )
    result["version"] = version_name
    result["draft_name"] = draft_name
    draft_id = (imported or {}).get("draft_id")
    if args.dry_run and not draft_id:
        draft_id = "<draft-id>"
    if not draft_id:
        raise ScriptError(
            f"{slug}: the import response carried no draft id (field name VERIFY #6) — nothing else was changed; "
            "read the response keys printed above, fix import_story._find_draft_id, and re-run"
        )
    result["draft_id"] = draft_id

    # --via-draft: every production id is in policies/never-touch.yml after its first ship; these writes
    # land in the draft this ship just created, which is the one path the never-touch list allows.
    mon_args = [
        slug, "--env", args.env, "--draft", str(draft_id), "--via-draft",
        "--from-manifest", "--monitor-failures", "true", *dry,
    ]
    if locked:
        mon_args += ["--locked", "true"]
    _, mon = run_script("set_monitoring.py", mon_args)
    result["recipients_added"] = len((mon or {}).get("recipients_added") or [])

    cr_args = [
        "open", slug, "--env", args.env, "--draft", str(draft_id),
        "--title", f"{slug} {sha7}",
        "--diff", str(diff_path),
        "--rollback-ref", args.rollback_ref,
        *dry,
    ]
    if args.source_url:
        cr_args += ["--pr-url", args.source_url]
    _, cr = run_script("change_request.py", cr_args)
    result["change_request_id"] = (cr or {}).get("change_request_id")
    result["change_request_status"] = (cr or {}).get("status")

    if not args.dry_run:
        try:
            view_md, _ = run_script("change_request.py", ["view", slug, "--env", args.env, "--draft", str(draft_id)])
            result["view_markdown"] = view_md.strip()
        except StepFailed as exc:
            eprint(f"[ship] change_request view failed (exit {exc.code}); the request was still opened")
    result["next"] = (
        "a named approver opens the change request in Tines, reads the live-vs-draft diff and approves (and pushes), "
        "or promote.yml runs on the APPROVED request. This job stopped here."
    )
    return result


def summarise(result: dict[str, Any]) -> str:
    lines = [f"### `{result['slug']}` → **{result['env']}** ({'dry run' if result['dry_run'] else result['mode']})", ""]
    lines.append(
        f"- story id: `{result.get('story_id') or '—'}` · draft: `{result.get('draft_id') or '—'}` "
        f"(`{result.get('draft_name') or '—'}`) · change request: `{result.get('change_request_id') or '—'}`"
        f"{' · status: ' + str(result['change_request_status']) if result.get('change_request_status') else ''}"
    )
    if result.get("version"):
        lines.append(f"- rollback point: story version `{result['version']}`; git ref of the previous export in the description")
    lines.append(
        f"- recipients added: {result.get('recipients_added', 0)} · monitor_failures: true · locked: {str(result.get('locked')).lower()}"
    )
    if result.get("new_in_prod_reason"):
        lines.append(f"- **created in prod with mode=new (no change request), authorised by the dispatch input:** {result['new_in_prod_reason']}")
    if result.get("view_markdown"):
        lines.append("")
        lines.append(result["view_markdown"])
    if result.get("next"):
        lines.append("")
        lines.append(f"**Next:** {result['next']}")
    if result.get("error"):
        lines.append("")
        lines.append(f"**Failed:** {result['error']}")
    return "\n".join(lines) + "\n\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    guard_prod(args.env)
    root = find_repo_root()
    manifest = load_manifest(root)
    sha_full = args.sha or git_sha(short=False) or "local"
    sha7 = sha_full[:7]
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None
    router = None if args.no_notify else os.environ.get("OPS_ROUTER_URL")

    failures = 0
    for index, slug in enumerate(args.slugs):
        if index:
            time.sleep(args.sleep)
        eprint(f"[ship] ── {slug} → {args.env} ({sha7}) ──")
        try:
            result = ship_one(root, slug, args, manifest, sha7)
        except StepFailed as exc:
            failures += 1
            result = {"slug": slug, "env": args.env, "sha": sha7, "dry_run": args.dry_run, "error": f"{exc.script} exited {exc.code}"}
            eprint(f"[ship] {slug}: {exc.script} failed (exit {exc.code})")
        except ScriptError as exc:
            failures += 1
            result = {"slug": slug, "env": args.env, "sha": sha7, "dry_run": args.dry_run, "error": str(exc.code)}
        print(json.dumps({k: v for k, v in result.items() if k != "view_markdown"}))
        if args.results_file:
            with open(args.results_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({k: v for k, v in result.items() if k != "view_markdown"}) + "\n")
        if args.summary_file:
            with open(args.summary_file, "a", encoding="utf-8") as fh:
                fh.write(summarise(result))
        if router and not args.dry_run and not result.get("error"):
            payload = {
                "source": "ship_story.py",
                "event": "change_request_opened" if result.get("change_request_id") else "story_created",
                "env": args.env,
                "slug": slug,
                "story_id": result.get("story_id"),
                "draft_id": result.get("draft_id"),
                "change_request_id": result.get("change_request_id"),
                "sha": sha_full,
                "source_url": args.source_url,
                "run_url": run_url,
                "requires": "a named approver in Tines",
            }
            if notify(router, payload):
                eprint("[ship] ops router notified")
        if result.get("error") and not args.continue_on_error:
            eprint("[ship] stopping at the first failure (pass --continue-on-error to ship the rest)")
            break

    eprint(f"[ship] done: {len(args.slugs) - failures} shipped, {failures} failed. Nothing was promoted.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
