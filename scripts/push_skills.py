#!/usr/bin/env python3
"""Create or update Tines Agent Skills from ``tines-skills/<name>/SKILL.md``.

Tines Agent Skills (the same ``SKILL.md`` files Workbench presets and AI Agent
actions use — facts: skills on agents since 2026-08-11, CRUD API since
2026-09-01) live in this repository so "how our agents behave" is reviewed in
the same PR as "how we build". This script is the only path that pushes them
(DESIGN.md §4.3, §3.4 ``skills.yml``).

Per skill directory it:

1. Parses the frontmatter and validates it against the Agent Skills rules in
   DESIGN.md §3.3 / §9.13: ``name`` equals the directory, lowercase-hyphen,
   ≤ 64 chars, no "anthropic" / "claude"; ``description`` ≤ 1024 chars, present;
   ``metadata`` a flat string map; body under 500 lines.
2. ``GET /api/v1/skills/<name>?team_id=<id>`` — 200 ⇒ update with
   ``PUT /api/v1/skills/<name>``; 404 ⇒ create with ``POST /api/v1/skills``
   ``{team_id, name, description, body, license, compatibility, metadata}``.
3. Stamps ``metadata.git_sha`` and ``metadata.repo_path`` (whether ``metadata``
   accepts arbitrary keys is VERIFY — DESIGN.md §10 #14).

``--dry-run`` performs the GET and prints create-vs-update per skill without
writing. ``--validate-only`` needs no tenant at all (used by ``lint.yml``).
Deletion is deliberate: ``--delete <name> --confirm <name>`` calls
``DELETE /api/v1/skills/<name>?team_id=``; removing the folder alone does
nothing in the tenant.

Renames: change the directory and the frontmatter ``name`` in one PR; the API
rewrites the name in every AI Agent action that references the skill
(DESIGN.md §4.3 step 5). Attaching a skill to a preset or an agent is a
by-hand step in Tines — no API was found (VERIFY).

Examples
--------
    ./scripts/push_skills.py --validate-only
    ./scripts/push_skills.py --team "$TINES_TEAM_ID" --dry-run --only story-health-triage
    ./scripts/push_skills.py --team "$TINES_TEAM_ID"                       # dev push
    TINES_ALLOW_PROD=1 ./scripts/push_skills.py --team "$TINES_TEAM_ID_PROD" --env prod   # CI only
    ./scripts/push_skills.py --team "$TINES_TEAM_ID" --delete old-skill --confirm old-skill
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    SKILLS_DIR,
    ApiError,
    ScriptError,
    client_from_env,
    eprint,
    find_repo_root,
    git_sha,
    guard_prod,
    parse_frontmatter,
    split_frontmatter,
)

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_BODY_LINES = 500
FORBIDDEN_NAME_WORDS = ("anthropic", "claude")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="push_skills.py",
        description="Create/update Tines Agent Skills from tines-skills/**/SKILL.md via the Skills API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("--team", type=int, help="target team id (required unless --validate-only)")
    parser.add_argument("--env", default="dev", help="label for the prod guard (prod needs TINES_ALLOW_PROD=1)")
    parser.add_argument("--only", action="append", default=[], metavar="NAME", help="limit to these skill names")
    parser.add_argument("--skills-dir", type=Path, help="override the tines-skills/ directory")
    parser.add_argument("--validate-only", action="store_true", help="validate frontmatter and bodies; no tenant")
    parser.add_argument("--dry-run", action="store_true", help="GET each skill and print create/update; no writes")
    parser.add_argument("--delete", metavar="NAME", help="delete this skill from the team (needs --confirm NAME)")
    parser.add_argument("--confirm", metavar="NAME", help="repeat the name to confirm deletion")
    parser.add_argument("--json", action="store_true", help="print a JSON summary on stdout")
    return parser


def load_skill(skill_dir: Path) -> dict[str, Any]:
    """Read and validate one skill folder; returns the API payload plus findings."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise ScriptError(f"{skill_dir} has no SKILL.md")
    text = skill_md.read_text(encoding="utf-8")
    front_text, body = split_frontmatter(text)
    if not front_text:
        raise ScriptError(f"{skill_md}: missing YAML frontmatter")
    front = parse_frontmatter(front_text)

    problems: list[str] = []
    name = str(front.get("name", "")).strip()
    description = str(front.get("description", "")).strip()
    if not name:
        problems.append("frontmatter 'name' is required")
    elif name != skill_dir.name:
        problems.append(f"name {name!r} must equal the directory name {skill_dir.name!r}")
    if name and not NAME_RE.match(name):
        problems.append("name must be lowercase letters/digits separated by single hyphens")
    if len(name) > MAX_NAME:
        problems.append(f"name longer than {MAX_NAME} characters")
    if any(word in name.lower() for word in FORBIDDEN_NAME_WORDS):
        problems.append("name must not contain 'anthropic' or 'claude'")
    if not description:
        problems.append("frontmatter 'description' is required (agents choose skills by name and description)")
    if len(description) > MAX_DESCRIPTION:
        problems.append(f"description longer than {MAX_DESCRIPTION} characters")
    if description and re.match(r"^(I|We|You)\b", description):
        problems.append("description should be written in the third person (what it does and when)")
    metadata = front.get("metadata") or {}
    if metadata and not isinstance(metadata, dict):
        problems.append("metadata must be a flat map of strings")
    elif isinstance(metadata, dict):
        for key, value in metadata.items():
            if isinstance(value, (dict, list)):
                problems.append(f"metadata.{key} must be a flat string, not a nested structure")
    body_lines = body.count("\n") + (1 if body and not body.endswith("\n") else 0)
    if body_lines > MAX_BODY_LINES:
        problems.append(f"body has {body_lines} lines; keep it under {MAX_BODY_LINES}")
    if not body.strip():
        problems.append("body is empty")
    for pattern_name, needle in (("token-like", "xoxb-"), ("aws key", "AKIA")):
        if needle in body:
            problems.append(f"body contains a {pattern_name} string ({needle})")

    payload = {
        "name": name,
        "description": description,
        "body": body,
        "license": str(front.get("license", "")) or None,
        "compatibility": str(front.get("compatibility", "")) or None,
        "metadata": {str(k): str(v) for k, v in (metadata or {}).items()},
    }
    return {"dir": skill_dir, "payload": payload, "problems": problems}


def discover_skills(skills_dir: Path, only: list[str]) -> list[Path]:
    if not skills_dir.exists():
        raise ScriptError(f"{skills_dir} does not exist")
    dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
    if only:
        wanted = set(only)
        dirs = [p for p in dirs if p.name in wanted]
        missing = wanted - {p.name for p in dirs}
        if missing:
            raise ScriptError(f"skills not found: {', '.join(sorted(missing))}")
    return dirs


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = find_repo_root()
    skills_dir = args.skills_dir or (root / SKILLS_DIR)
    summary: dict[str, Any] = {"validated": [], "created": [], "updated": [], "deleted": [], "problems": {}}

    # -- deletion is its own path ---------------------------------------------- #
    if args.delete:
        guard_prod(args.env)
        if args.confirm != args.delete:
            raise ScriptError("deletion needs --confirm <name> equal to --delete <name>")
        if args.team is None:
            raise ScriptError("--team is required")
        client = client_from_env(dry_run=args.dry_run)
        eprint(f"[skills] DELETE /api/v1/skills/{args.delete}?team_id={args.team}")
        try:
            client.delete(f"/api/v1/skills/{args.delete}", team_id=args.team)
        except ApiError as exc:
            raise ScriptError(f"delete failed: {exc}") from None
        summary["deleted"].append(args.delete)
        if args.json:
            print(json.dumps(summary))
        return 0

    # -- validate ---------------------------------------------------------------- #
    loaded = []
    failed = False
    for skill_dir in discover_skills(skills_dir, args.only):
        item = load_skill(skill_dir)
        loaded.append(item)
        rel = skill_dir.relative_to(root) if skill_dir.is_relative_to(root) else skill_dir
        if item["problems"]:
            failed = True
            summary["problems"][skill_dir.name] = item["problems"]
            for problem in item["problems"]:
                print(f"{rel}/SKILL.md: error: {problem}")
        else:
            summary["validated"].append(skill_dir.name)
            eprint(f"[skills] ok  {rel} ({len(item['payload']['body'])} chars)")
    if failed:
        if args.json:
            print(json.dumps(summary))
        return 1
    if args.validate_only:
        eprint(f"[skills] validated {len(loaded)} skill(s)")
        if args.json:
            print(json.dumps(summary))
        return 0

    # -- push ---------------------------------------------------------------------- #
    guard_prod(args.env)
    if args.team is None:
        raise ScriptError("--team is required to push (or use --validate-only)")
    client = client_from_env(dry_run=args.dry_run)
    sha = git_sha() or "unknown"
    for item in loaded:
        payload = dict(item["payload"])
        name = payload["name"]
        payload["metadata"] = {
            **payload["metadata"],
            "git_sha": sha,  # VERIFY: metadata accepts arbitrary flat string keys
            "repo_path": str(item["dir"].relative_to(root)) if item["dir"].is_relative_to(root) else str(item["dir"]),
        }
        exists = False
        try:
            client.get(f"/api/v1/skills/{name}", team_id=args.team)
            exists = True
        except ApiError as exc:
            if exc.status != 404:
                raise ScriptError(f"GET /api/v1/skills/{name} failed: {exc}") from None
        try:
            if exists:
                eprint(f"[skills] {'would update' if args.dry_run else 'update'} PUT /api/v1/skills/{name} (team {args.team})")
                client.put(f"/api/v1/skills/{name}", {"team_id": args.team, **{k: v for k, v in payload.items() if k != 'name'}})
                summary["updated"].append(name)
            else:
                eprint(f"[skills] {'would create' if args.dry_run else 'create'} POST /api/v1/skills {name} (team {args.team})")
                client.post("/api/v1/skills", {"team_id": args.team, **payload})
                summary["created"].append(name)
        except ApiError as exc:
            raise ScriptError(f"push of {name} failed: {exc}") from None

    eprint(
        f"[skills] done: created={len(summary['created'])} updated={len(summary['updated'])}"
        f"{' (dry run)' if args.dry_run else ''}. Attaching a skill to a preset or an AI Agent action is by hand."
    )
    if args.json:
        print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
