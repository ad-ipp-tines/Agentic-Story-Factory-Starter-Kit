#!/usr/bin/env python3
"""Semantic diff of a story export for PR bodies and change-request descriptions.

A raw ``git diff`` of ``story.json`` is noisy (``diagram_layout`` moves, sorted
keys). This script matches actions by ``guid`` and then by ``name`` and reports
what a reviewer and an approver need (DESIGN.md §3.5 ``diff-story.sh``):

* actions added, removed and renamed (same guid, new name)
* changed option keys per action — values shown, except anything that looks
  like a secret, which is shown as a length only
* links added and removed, as ``source → receiver`` names (``link_type`` kept)
* schedule, ``monitoring`` flags and ``disabled`` changes per action
* story-level changes: name, description, ``keep_events_for``,
  ``monitor_failures``, ``send_to_story_*``, Note count

Compare against a git ref (default ``HEAD``) or another file. Output is
Markdown (default) or JSON.

Examples
--------
    ./scripts/diff_story.py stories/example-enrich-ip/story.json
    ./scripts/diff_story.py stories/example-enrich-ip/story.json --against origin/main
    ./scripts/diff_story.py stories/x/story.json --against /tmp/live-export.json --format json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import ScriptError, eprint, find_repo_root, load_json_file, looks_like_secret, redact  # noqa: E402

TRACKED_STORY_KEYS = (
    "name",
    "description",
    "keep_events_for",
    "monitor_failures",
    "send_to_story_enabled",
    "send_to_story_timeout_enabled",
    "send_to_story_timeout_duration_seconds",
    "send_to_story_access",
)


def load_before(path: Path, against: str, root: Path) -> Optional[dict[str, Any]]:
    candidate = Path(against)
    if candidate.exists() and candidate.is_file():
        return load_json_file(candidate)
    rel = path.resolve().relative_to(root) if path.resolve().is_relative_to(root) else path
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"{against}:{rel.as_posix()}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def index_agents(export: Optional[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    agents = [a for a in ((export or {}).get("agents") or []) if isinstance(a, dict)]
    by_guid = {str(a["guid"]): i for i, a in enumerate(agents) if a.get("guid")}
    by_name = {str(a["name"]): i for i, a in enumerate(agents) if a.get("name")}
    return agents, by_guid, by_name


def shown(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    if looks_like_secret(text):
        return f"<redacted {redact(text)}>"
    return text if len(text) <= 160 else text[:157] + "..."


def link_labels(export: Optional[dict[str, Any]]) -> set[str]:
    agents = [a for a in ((export or {}).get("agents") or []) if isinstance(a, dict)]
    labels = set()
    for link in (export or {}).get("links") or []:
        if not isinstance(link, dict):
            continue
        s, r = link.get("source"), link.get("receiver")
        if isinstance(s, int) and isinstance(r, int) and 0 <= s < len(agents) and 0 <= r < len(agents):
            suffix = f" ({link['link_type']})" if link.get("link_type") else ""
            labels.add(f"{agents[s].get('name')} → {agents[r].get('name')}{suffix}")
    return labels


def compute(before: Optional[dict[str, Any]], after: dict[str, Any]) -> dict[str, Any]:
    b_agents, b_guid, b_name = index_agents(before)
    a_agents, a_guid, a_name = index_agents(after)

    pairs: list[tuple[int, int]] = []
    matched_b: set[int] = set()
    matched_a: set[int] = set()
    for guid, ai in a_guid.items():
        if guid in b_guid:
            pairs.append((b_guid[guid], ai))
            matched_b.add(b_guid[guid])
            matched_a.add(ai)
    for name, ai in a_name.items():
        if ai in matched_a:
            continue
        bi = b_name.get(name)
        if bi is not None and bi not in matched_b:
            pairs.append((bi, ai))
            matched_b.add(bi)
            matched_a.add(ai)

    added = [a_agents[i] for i in range(len(a_agents)) if i not in matched_a]
    removed = [b_agents[i] for i in range(len(b_agents)) if i not in matched_b]
    renamed, changed = [], []
    for bi, ai in sorted(pairs, key=lambda p: p[1]):
        b, a = b_agents[bi], a_agents[ai]
        if b.get("name") != a.get("name"):
            renamed.append({"from": b.get("name"), "to": a.get("name")})
        entry: dict[str, Any] = {"name": a.get("name"), "type": a.get("type"), "options": [], "flags": []}
        bo, ao = b.get("options") or {}, a.get("options") or {}
        for key in sorted(set(bo) | set(ao)):
            if bo.get(key) != ao.get(key):
                entry["options"].append({"key": key, "before": shown(bo.get(key)) if key in bo else None, "after": shown(ao.get(key)) if key in ao else None})
        for key in ("monitoring", "schedule", "disabled", "type", "description"):
            if b.get(key) != a.get(key):
                entry["flags"].append({"key": key, "before": shown(b.get(key)), "after": shown(a.get(key))})
        bt, at = b.get("tools") or [], a.get("tools") or []
        if bt != at:
            entry["flags"].append({"key": "tools", "before": f"{len(bt)} tool(s)", "after": f"{len(at)} tool(s)"})
        if entry["options"] or entry["flags"]:
            changed.append(entry)

    b_links, a_links = link_labels(before), link_labels(after)
    story_changes = []
    for key in TRACKED_STORY_KEYS:
        if (before or {}).get(key) != after.get(key):
            story_changes.append({"key": key, "before": shown((before or {}).get(key)), "after": shown(after.get(key))})
    notes_before = len((before or {}).get("diagram_notes") or [])
    notes_after = len(after.get("diagram_notes") or [])
    return {
        "new_file": before is None,
        "story": story_changes,
        "actions": {"before": len(b_agents), "after": len(a_agents)},
        "added": [{"name": a.get("name"), "type": a.get("type")} for a in added],
        "removed": [{"name": a.get("name"), "type": a.get("type")} for a in removed],
        "renamed": renamed,
        "changed": changed,
        "links_added": sorted(a_links - b_links),
        "links_removed": sorted(b_links - a_links),
        "notes": {"before": notes_before, "after": notes_after},
    }


def to_markdown(path: str, result: dict[str, Any]) -> str:
    lines = [f"### Semantic diff — `{path}`", ""]
    if result["new_file"]:
        lines.append("_New export (no previous version to compare against)._")
    lines.append(f"- actions: {result['actions']['before']} → {result['actions']['after']}; notes: {result['notes']['before']} → {result['notes']['after']}")
    for item in result["story"]:
        lines.append(f"- story.{item['key']}: `{item['before']}` → `{item['after']}`")
    for item in result["added"]:
        lines.append(f"- **added** `{item['name']}` ({item['type']})")
    for item in result["removed"]:
        lines.append(f"- **removed** `{item['name']}` ({item['type']})")
    for item in result["renamed"]:
        lines.append(f"- renamed `{item['from']}` → `{item['to']}`")
    for item in result["changed"]:
        keys = [o["key"] for o in item["options"]] + [f["key"] for f in item["flags"]]
        lines.append(f"- changed `{item['name']}`: {', '.join(keys)}")
        for opt in item["options"]:
            lines.append(f"    - options.{opt['key']}: `{opt['before']}` → `{opt['after']}`")
        for flag in item["flags"]:
            lines.append(f"    - {flag['key']}: `{flag['before']}` → `{flag['after']}`")
    for label in result["links_added"]:
        lines.append(f"- link added: {label}")
    for label in result["links_removed"]:
        lines.append(f"- link removed: {label}")
    if not any([result["story"], result["added"], result["removed"], result["renamed"], result["changed"], result["links_added"], result["links_removed"]]) and not result["new_file"]:
        lines.append("- no semantic changes (layout-only or identical)")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="diff_story.py", description="Semantic diff of a story export.", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="stories/<slug>/story.json")
    parser.add_argument("--against", default="HEAD", help="git ref (default HEAD) or a file to compare against")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.path.exists():
        raise ScriptError(f"not found: {args.path}")
    root = find_repo_root()
    after = load_json_file(args.path)
    before = load_before(args.path, args.against, root)
    if before is None:
        eprint(f"[diff] no previous version at {args.against}; treating as a new export")
    result = compute(before, after)
    rel = args.path.resolve().relative_to(root) if args.path.resolve().is_relative_to(root) else args.path
    if args.format == "json":
        print(json.dumps({"path": str(rel), "against": args.against, **result}, indent=2))
    else:
        sys.stdout.write(to_markdown(str(rel), result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
