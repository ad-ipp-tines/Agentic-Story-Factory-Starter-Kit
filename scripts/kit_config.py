#!/usr/bin/env python3
"""Propagate the tenant config into the repository, and keep the generated Resources current in the tenant.

Spec: REPO-DESIGN.md §7.1 (the setup-report PR), §7.2 A16 (the config commit) and A28/A29 (the setup report),
§8.2 (``kit-sync.yml``), §3.3 rows 11–12 (never-touch and the manifest), §12 (budget lines), §15.4.

``./scripts/kit apply-config [--targets manifest,never-touch,ceilings,tracker] [--dry-run] [--check]``
    Reads ``kit/tenant/config.yaml`` (the day-1 config commit, JSON that YAML reads) and, when present,
    ``kit/tenant/setup-report.json``, and **fills placeholders only**:

    * ``stories/_manifest.yaml`` — ``environments.dev.team_id`` / ``environments.prod.team_id`` from the config's
      team ids; ``stories.kit-factory.prod.story_id`` from the report's ``kit_story_id`` (so ``ship.yml`` changes the
      imported copy through ``versionReplace`` instead of creating a second ``[KIT] 00``)
    * ``policies/never-touch.yml`` — the report's ``kit_story_id`` appended to ``story_ids``; the prod (ops) team
      id in ``teams`` in place of the ``0`` placeholder
    * ``policies/cost-ceilings.yml`` — ``teams.ops.team_id`` (the prod team is the ops team) and
      ``teams.dev.team_id``; the kit agents' ``provider`` (``tenant-default`` or ``custom:<provider name>``)
    * the tracker — an empty milestone ``due_date`` = ``provisioned_at`` + ``due_offset_days``; an empty
      ``target_date`` of a catalog story = ``provisioned_at`` + its ``target_offset_days``; the ``provider`` of rows
      whose story runs an AI Agent action. Each changed row's ``rev`` becomes main's rev + 1, with a ``sync`` event.
      On the Records path Flow 2 usually brings these first and nothing changes; on the Community path (no kit
      story) this is where they come from.

    A value that is already set and differs is a **conflict**: reported, never overwritten. The YAML policy files
    are edited line by line (comments kept) and each edit is verified by re-parsing; the tracker files are
    rewritten through ``kit_tracker``'s emitter. ``kit.yml`` opens two PRs with the ``tracker-bot`` token:
    ``kit/config-<run>`` (manifest, never-touch, ceilings) and ``tracker/config-<run>`` (the tracker, whose branch
    prefix the touch sets require).

``./scripts/kit sync-resources [--env prod] [--dry-run]``
    ``kit-sync.yml`` on every merge to ``main``, with the ops-team Editor key of the GitHub environment
    ``kit-sync``: under the ``sdlc_sync_lock`` compare-and-swap (``POST /api/v1/global_resources/{id}/replace``
    with ``if_value: free``), ``PUT /api/v1/global_resources/{id}`` the whole value of ``sdlc_state_machine``,
    ``kit_catalog`` and ``kit_config`` (with ``tenant_host`` = ``$TINES_TENANT.tines.com`` and ``environment:
    prod``); replace the ``sdlc_limits`` keys it owns (never ``enabled`` or ``guards_confirmed``); write each
    Resource's hash to ``kit_state.hash_<name>``; release the lock (also on failure). Resource ids come from the
    committed setup report (``created.resources[]``). Refused outside GitHub Actions on ``main`` unless
    ``--dry-run``. The whole-value PUT body is ``{"value": …}`` — VERIFY (the key name is not in the kit's
    sources; A19's create body uses ``value``). The skills push is ``./scripts/tines skills-push``, run by the
    workflow after this.

``./scripts/tines manifest-set-dev-id <slug> <id>`` (``kit_config.py set-dev-id``)
    Records the dev story id the builder created through ``/mcp`` — ``stories.<slug>.dev.story_id`` in
    ``stories/_manifest.yaml`` and nothing else (touch-sets patch ``manifest_dev_id``), with the same comment-keeping
    line edit, verified by re-parsing. It is the one manifest write ``/tines-build-story`` pre-approves, in place of
    ``yq -i`` (which can rewrite any file). Only while the recorded id is ``0``; it refuses an id that another manifest
    entry (dev or prod), this slug's prod entry, an environment's team or folder, or ``policies/never-touch.yml``
    already holds, so a build session cannot point its dev id at a protected story (``phase-gate.sh`` trusts it).
    No network.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import ApiError, ScriptError, client_from_env, eprint, find_repo_root, guard_prod, utc_now  # noqa: E402
from kit_tracker import (  # noqa: E402
    BACKLOG,
    BACKLOG_SCHEMA,
    CATALOG_STARTERS,
    MILESTONES,
    MILESTONES_SCHEMA,
    WORK_DIR,
    FieldMap,
    add_days_utc,
    append_events,
    assert_in_touch_set,
    canonical,
    dump_backlog,
    dump_milestones,
    header_comments,
    load_tracker,
    load_yaml_text,
    main_row_revs,
    make_event,
    read_json,
    read_yaml,
    require_ci_main,
    to_utc,
    untrusted_problems,
    validate,
    write_checked,
)
from kit_bundle import (  # noqa: E402
    LIMITS_HUMAN_KEYS,
    SYNCED_RESOURCES,
    TENANT_CONFIG,
    bundle_resource_values,
    generated_resource_values,
    load_config,
    resource_hash,
)

MANIFEST = Path("stories/_manifest.yaml")
NEVER_TOUCH = Path("policies/never-touch.yml")
CEILINGS = Path("policies/cost-ceilings.yml")
SETUP_REPORT = Path("kit/tenant/setup-report.json")
KIT_SLUG = "kit-factory"
KIT_AGENTS = ("planner", "brief_writer", "retro_writer", "llm_probe", "llm_tool_probe")
ALL_TARGETS = ("manifest", "never-touch", "ceilings", "tracker")
PROVIDER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")
LOCK_ATTEMPTS = 6
LOCK_WAIT_SECONDS = 20


# --------------------------------------------------------------------------- #
# Line-level YAML edits that keep comments, verified by re-parsing
# --------------------------------------------------------------------------- #

_KEY_LINE = re.compile(r"^(?P<indent>[ ]*)(?P<key>\"[^\"]*\"|'[^']*'|[^\s#:'\"-][^:#]*?)\s*:(?P<rest>(?:[ \t].*)?)$")
_REST = re.compile(r"^(?P<sp>[ \t]*)(?P<val>\"(?:[^\"\\]|\\.)*\"|'[^']*'|\[[^#]*\]|\{[^#]*\}|[^#]*?)(?P<gap>[ \t]*)(?P<comment>#.*)?$")


def _unquote(key: str) -> str:
    key = key.strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        return key[1:-1]
    return key


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _set_path(data: Any, path: list[str], value: Any) -> None:
    cur = data
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def _get_path(data: Any, path: list[str]) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


class YamlText:
    """Edit one scalar or one list in a YAML file without losing its comments or layout."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.data = load_yaml_text(self.text)

    def _locate(self, path: list[str]) -> tuple[int, int, re.Match[str]]:
        lines = self.text.splitlines()
        stack: list[tuple[int, str]] = []
        best: Optional[tuple[int, int, re.Match[str]]] = None
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if stripped.startswith("- ") or stripped == "-":
                continue
            match = _KEY_LINE.match(line)
            if not match:
                continue
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, _unquote(match.group("key"))))
            keys = [k for _, k in stack]
            if keys == path:
                return index, len(path), match
            rest = match.group("rest").strip()
            if len(keys) < len(path) and keys == path[:len(keys)] and rest.startswith("{"):
                best = (index, len(keys), match)
        if best is None:
            raise ScriptError(f"{self.path}: cannot find {'.'.join(path)} to edit; set it by hand")
        return best

    def _commit(self, new_text: str, path: list[str], value: Any, expected: Any) -> None:
        parsed = load_yaml_text(new_text)
        if canonical(parsed) != canonical(expected):
            raise ScriptError(f"{self.path}: editing {'.'.join(path)} would change more than that value; set it by hand")
        self.text = new_text
        self.data = parsed

    def set_scalar(self, path: list[str], value: Any) -> None:
        expected = copy.deepcopy(self.data)
        _set_path(expected, path, value)
        index, depth, match = self._locate(path)
        lines = self.text.splitlines(keepends=True)
        line = lines[index]
        newline = "\n" if line.endswith("\n") else ""
        body = line.rstrip("\n")
        head = body[: match.start("rest")]
        rest = match.group("rest")
        if depth == len(path):
            parts = _REST.match(rest)
            if not parts:
                raise ScriptError(f"{self.path}: cannot parse the value of {'.'.join(path)}; set it by hand")
            old_val = parts.group("val")
            new_val = _scalar(value)
            comment = parts.group("comment") or ""
            gap = parts.group("gap")
            if comment:
                width = len(old_val) + len(gap)
                gap = " " * max(1, width - len(new_val))
            new_rest = f"{parts.group('sp') or ' '}{new_val}{gap if comment else ''}{comment}"
            lines[index] = head + new_rest + newline
        else:
            remaining = path[depth:]
            key_re = lambda k: r"(?<![\w-])" + re.escape(k) + r"\s*:\s*"  # noqa: E731
            if len(remaining) == 1:
                pattern = r"(?P<pre>" + key_re(remaining[0]) + r")(?P<val>[^,}\s]+)"
            elif len(remaining) == 2:
                pattern = r"(?P<pre>" + key_re(remaining[0]) + r"\{[^{}]*?" + key_re(remaining[1]) + r")(?P<val>[^,}\s]+)"
            else:
                raise ScriptError(f"{self.path}: {'.'.join(path)} is nested too deeply in a flow map; set it by hand")
            new_rest, count = re.subn(pattern, lambda m: m.group("pre") + _scalar(value), rest, count=1)
            if count != 1:
                raise ScriptError(f"{self.path}: cannot find {'.'.join(remaining)} inside the flow map; set it by hand")
            lines[index] = head + new_rest + newline
        self._commit("".join(lines), path, value, expected)

    def set_list(self, path: list[str], values: list[Any]) -> None:
        expected = copy.deepcopy(self.data)
        _set_path(expected, path, list(values))
        index, depth, match = self._locate(path)
        if depth != len(path):
            raise ScriptError(f"{self.path}: {'.'.join(path)} is inside a flow map; set it by hand")
        lines = self.text.splitlines(keepends=True)
        line = lines[index].rstrip("\n")
        head = line[: match.start("rest")]
        rest = match.group("rest")
        key_indent = len(match.group("indent"))
        flow = "[" + ", ".join(_scalar(v) for v in values) + "]"
        parts = _REST.match(rest)
        if parts and parts.group("val").startswith("["):
            comment = parts.group("comment") or ""
            gap = parts.group("gap") if comment else ""
            if comment:
                gap = " " * max(1, len(parts.group("val")) + len(parts.group("gap")) - len(flow))
            lines[index] = f"{head} {flow}{gap}{comment}\n"
        elif rest.strip() == "" or rest.strip().startswith("#"):
            # a block list: replace the item lines that follow, keeping the first item's comment
            end = index + 1
            item_lines: list[int] = []
            while end < len(lines):
                stripped = lines[end].strip()
                indent = len(lines[end]) - len(lines[end].lstrip(" "))
                if stripped and not stripped.startswith("#") and indent <= key_indent and not stripped.startswith("- "):
                    break
                if stripped.startswith("- ") or stripped == "-":
                    if indent < key_indent:
                        break
                    item_lines.append(end)
                elif stripped and not stripped.startswith("#"):
                    break
                end += 1
            if not item_lines:
                lines[index] = f"{head} {flow}\n"
            else:
                first = lines[item_lines[0]]
                item_indent = " " * (len(first) - len(first.lstrip(" ")))
                first_parts = _REST.match(first.strip()[1:])
                comment = (first_parts.group("comment") if first_parts else None) or ""
                new_items = []
                for i, value in enumerate(values):
                    text = f"{item_indent}- {_scalar(value)}"
                    if i == 0 and comment:
                        text = text.ljust(len(first.rstrip("\n")) - len(comment)) + comment
                    new_items.append(text + "\n")
                if not values:
                    lines[index] = f"{head} []\n"
                start, stop = item_lines[0], item_lines[-1] + 1
                lines[start:stop] = new_items
        else:
            raise ScriptError(f"{self.path}: {'.'.join(path)} is not a list; set it by hand")
        self._commit("".join(lines), path, list(values), expected)

    def write(self) -> None:
        self.path.write_text(self.text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# apply-config
# --------------------------------------------------------------------------- #


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def provider_for(config: dict[str, Any]) -> tuple[str, str]:
    """(tracker provider, cost-ceilings provider) for the config's llm.choice."""
    llm = config.get("llm") or {}
    choice = str(llm.get("choice") or "tines_provided")
    name = str(llm.get("provider_name") or "").strip()
    label = f"custom:{name}" if PROVIDER_NAME_RE.match(name) else "custom:unnamed"
    if choice == "tines_provided":
        return "tines_provided", "tenant-default"
    if choice.startswith("local_"):
        return "local", label
    return "custom", label


class Planner:
    def __init__(self, root: Path, config: dict[str, Any], report: Optional[dict[str, Any]]) -> None:
        self.root = root
        self.config = config
        self.report = report or {}
        self.changes: list[dict[str, Any]] = []
        self.conflicts: list[dict[str, Any]] = []
        self.notes: list[str] = []
        self.files: list[str] = []

    def _fill(self, doc: YamlText, path: list[str], value: Any, placeholder: Any = 0) -> None:
        current = _get_path(doc.data, path)
        if current is None and _get_path(doc.data, path[:-1]) is None:
            self.notes.append(f"{doc.path.relative_to(self.root)}: {'.'.join(path[:-1])} does not exist; not set")
            return
        if canonical(current) == canonical(value):
            return
        if current not in (placeholder, None, ""):
            self.conflicts.append({"file": doc.path.relative_to(self.root).as_posix(), "path": ".".join(path),
                                   "current": current, "config": value})
            return
        doc.set_scalar(path, value)
        self.changes.append({"file": doc.path.relative_to(self.root).as_posix(), "path": ".".join(path),
                             "from": current, "to": value})

    def manifest(self, dry_run: bool) -> None:
        doc = YamlText(self.root / MANIFEST)
        teams = self.config.get("teams") or {}
        for env in ("dev", "prod"):
            team_id = _int((teams.get(env) or {}).get("id"))
            if team_id > 0:
                self._fill(doc, ["environments", env, "team_id"], team_id)
        kit_id = _int(self.report.get("kit_story_id"))
        if kit_id > 0:
            if _get_path(doc.data, ["stories", KIT_SLUG]) is None:
                self.notes.append(f"{MANIFEST}: no {KIT_SLUG} entry (REPO-DESIGN.md §3.3 row 12); kit_story_id not recorded")
            else:
                self._fill(doc, ["stories", KIT_SLUG, "prod", "story_id"], kit_id)
        self._write(doc, dry_run)

    def never_touch(self, dry_run: bool) -> None:
        doc = YamlText(self.root / NEVER_TOUCH)
        kit_id = _int(self.report.get("kit_story_id"))
        if kit_id > 0:
            ids = [int(i) for i in (doc.data.get("story_ids") or []) if str(i).lstrip("-").isdigit()]
            if kit_id not in ids:
                doc.set_list(["story_ids"], ids + [kit_id])
                self.changes.append({"file": NEVER_TOUCH.as_posix(), "path": "story_ids", "from": ids, "to": ids + [kit_id]})
        prod_id = _int(((self.config.get("teams") or {}).get("prod") or {}).get("id"))
        if prod_id > 0:
            teams = list(doc.data.get("teams") or [])
            if prod_id not in teams:
                new = [prod_id if t in (0, "0") else t for t in teams] if (0 in teams or "0" in teams) else teams + [prod_id]
                doc.set_list(["teams"], new)
                self.changes.append({"file": NEVER_TOUCH.as_posix(), "path": "teams", "from": teams, "to": new})
        self._write(doc, dry_run)

    def ceilings(self, dry_run: bool) -> None:
        doc = YamlText(self.root / CEILINGS)
        teams = self.config.get("teams") or {}
        prod_id = _int((teams.get("prod") or {}).get("id"))
        dev_id = _int((teams.get("dev") or {}).get("id"))
        if prod_id > 0:
            self._fill(doc, ["teams", "ops", "team_id"], prod_id)
        if dev_id > 0:
            self._fill(doc, ["teams", "dev", "team_id"], dev_id)
        _, ceiling_provider = provider_for(self.config)
        agents = doc.data.get("agents") or {}
        for agent in KIT_AGENTS:
            key = f"{KIT_SLUG}/{agent}"
            if key not in agents:
                continue
            self._fill(doc, ["agents", key, "provider"], ceiling_provider, placeholder="tenant-default")
        self._write(doc, dry_run)

    def tracker(self, dry_run: bool) -> None:
        provisioned = to_utc(self.config.get("provisioned_at"))
        fmap = FieldMap.load(self.root)
        backlog_text, backlog, ms_text, milestones = load_tracker(self.root)
        revs, mrevs, source = main_row_revs(self.root)
        starters = read_yaml(self.root / CATALOG_STARTERS)
        by_key = {s.get("key"): s for s in starters.get("stories") or [] if isinstance(s, dict)}
        ai_keys = {k for k, s in by_key.items() if "ai_agent_action" in (((s.get("needs") or {}).get("entitlements")) or [])}
        ai_keys.add(KIT_SLUG)
        row_provider, _ = provider_for(self.config)
        entitled_ai = bool(((self.config.get("entitlements") or {}).get("ai_agent_action")))
        events: dict[str, list[dict[str, Any]]] = {}
        if not provisioned:
            self.notes.append("kit/tenant/config.yaml provisioned_at is not a UTC timestamp; dates were not filled")
        for m in milestones.get("milestones") or []:
            if provisioned and not m.get("due_date") and isinstance(m.get("due_offset_days"), int):
                due = add_days_utc(provisioned, m["due_offset_days"])
                m["due_date"] = due
                m["rev"] = mrevs.get(str(m.get("id")), 0) + 1
                self.changes.append({"file": MILESTONES.as_posix(), "path": f"{m.get('id')}.due_date", "from": "", "to": due})
        for row in backlog.get("stories") or []:
            changed = []
            key = row.get("key")
            offset = (by_key.get(key) or {}).get("target_offset_days")
            if provisioned and not row.get("target_date") and isinstance(offset, int):
                row["target_date"] = add_days_utc(provisioned, offset)
                changed.append("target_date")
            if entitled_ai and key in ai_keys and row.get("provider") == "none" and row.get("phase") not in ("rejected", "retired"):
                row["provider"] = row_provider
                changed.append("provider")
            if changed:
                row["rev"] = revs.get(key, 0) + 1
                self.changes.append({"file": BACKLOG.as_posix(), "path": f"{key}: {', '.join(changed)}",
                                     "from": None, "to": f"rev {row['rev']}"})
                events.setdefault(key, []).append(make_event(
                    story_key=key, event_type="sync", decision="apply_config", actor="kit apply-config", actor_kind="ci",
                    summary=f"kit apply-config filled {', '.join(changed)} from kit/tenant/config.yaml",
                    refs=["kit/tenant/config.yaml"], tracker_rev=row["rev"]))
        for problem in validate(backlog, read_json(self.root / BACKLOG_SCHEMA)):
            raise ScriptError(f"refusing to write {BACKLOG}: {problem}")
        for problem in validate(milestones, read_json(self.root / MILESTONES_SCHEMA)):
            raise ScriptError(f"refusing to write {MILESTONES}: {problem}")
        if dry_run:
            return
        targets = [self.root / BACKLOG, self.root / MILESTONES] + [self.root / WORK_DIR / k / "events.jsonl" for k in events]
        assert_in_touch_set(self.root, targets)
        if canonical(load_yaml_text(backlog_text)) != canonical(backlog):
            write_checked(self.root / BACKLOG, dump_backlog(backlog, header_comments(backlog_text), fmap), backlog)
            self.files.append(BACKLOG.as_posix())
        if canonical(load_yaml_text(ms_text)) != canonical(milestones):
            write_checked(self.root / MILESTONES, dump_milestones(milestones, header_comments(ms_text), fmap), milestones)
            self.files.append(MILESTONES.as_posix())
        for key, evs in events.items():
            if append_events(self.root, key, evs, dry_run=False):
                self.files.append((WORK_DIR / key / "events.jsonl").as_posix())
        self.notes.append(f"tracker revs computed from {source} (main's rev + 1)")

    def _write(self, doc: YamlText, dry_run: bool) -> None:
        if dry_run:
            return
        if doc.text != doc.path.read_text(encoding="utf-8"):
            doc.write()
            self.files.append(doc.path.relative_to(self.root).as_posix())


def load_report(root: Path, path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    target = root / (path or SETUP_REPORT)
    if not target.exists():
        return None
    report = read_json(target)
    if not isinstance(report, dict):
        raise ScriptError(f"{target} must be a JSON object (the shape is in kit/tenant/README.md)")
    return report


def check_config(config: dict[str, Any]) -> list[str]:
    problems = untrusted_problems(config)
    if config.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    if "tenant_host" in config:
        problems.append("tenant_host must never be committed (it lives only in the kit_config Resource)")
    for env in ("dev", "prod"):
        team = ((config.get("teams") or {}).get(env)) or {}
        if not isinstance(team, dict) or "id" not in team:
            problems.append(f"teams.{env}.id is required (0 until known)")
    return problems


def pr_body(result: dict[str, Any], targets: list[str]) -> str:
    lines = ["## Apply the tenant config", "",
             "`./scripts/kit apply-config` propagated `kit/tenant/config.yaml`"
             + (" and `kit/tenant/setup-report.json`" if result.get("report") else "")
             + f" into: {', '.join(targets)}. It fills placeholders only (REPO-DESIGN.md §7.1, §8.2).", ""]
    if result["changes"]:
        lines += ["| File | Path | Now |", "|---|---|---|"]
        for c in result["changes"]:
            lines.append(f"| `{c['file']}` | `{c['path']}` | `{json.dumps(c['to'], ensure_ascii=False)}` |")
        lines.append("")
    if result["conflicts"]:
        lines += ["### Left as is (already set to a different value)", "",
                  "| File | Path | In the repo | In the config |", "|---|---|---|---|"]
        for c in result["conflicts"]:
            lines.append(f"| `{c['file']}` | `{c['path']}` | `{c['current']}` | `{c['config']}` |")
        lines.append("")
    if result["notes"]:
        lines += [f"- {n}" for n in result["notes"]]
        lines.append("")
    lines.append("A CODEOWNER reviews and a person merges; nothing here reaches the tenant until `kit-sync.yml` runs on the merge.")
    return "\n".join(lines) + "\n"


def cmd_apply(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="kit apply-config", description="Propagate kit/tenant/config.yaml into the repository.")
    parser.add_argument("--targets", default=",".join(ALL_TARGETS), help=f"comma-separated: {', '.join(ALL_TARGETS)}")
    parser.add_argument("--config", type=Path, help=f"default {TENANT_CONFIG}")
    parser.add_argument("--report", type=Path, help=f"default {SETUP_REPORT} (optional)")
    parser.add_argument("--dry-run", action="store_true", help="plan only; write nothing")
    parser.add_argument("--check", action="store_true", help="plan only; exit 1 when a change is pending")
    parser.add_argument("--summary", type=Path, help="write the JSON summary here (default: stdout)")
    parser.add_argument("--pr-body", type=Path, help="write a Markdown PR body here")
    args = parser.parse_args(argv)
    root = find_repo_root()
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    unknown = [t for t in targets if t not in ALL_TARGETS]
    if unknown:
        raise ScriptError(f"unknown target(s) {unknown}; choose from {', '.join(ALL_TARGETS)}")
    config_path = args.config or TENANT_CONFIG
    if not (root / config_path).exists():
        raise ScriptError(f"{config_path} does not exist yet — [KIT] 00 A16 commits it on day 1, or copy "
                          "kit/tenant/config.example.yaml by hand on the Community path")
    config = load_config(root, config_path)
    problems = check_config(config)
    if problems:
        raise ScriptError(f"{config_path} is not valid:\n  " + "\n  ".join(problems))
    report = load_report(root, args.report)
    planner = Planner(root, config, report)
    dry = args.dry_run or args.check
    for target in targets:
        {"manifest": planner.manifest, "never-touch": planner.never_touch, "ceilings": planner.ceilings,
         "tracker": planner.tracker}[target](dry)
    result = {"targets": targets, "report": report is not None, "changes": planner.changes,
              "conflicts": planner.conflicts, "notes": planner.notes, "files": planner.files, "dry_run": dry}
    text = json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n"
    if args.summary:
        args.summary.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.pr_body:
        args.pr_body.write_text(pr_body(result, targets), encoding="utf-8")
    eprint(f"[kit] apply-config: {len(planner.changes)} change(s), {len(planner.conflicts)} conflict(s)"
           f"{' (dry run)' if dry else ''}")
    return 1 if args.check and planner.changes else 0


# --------------------------------------------------------------------------- #
# sync-resources
# --------------------------------------------------------------------------- #


def resource_ids(report: dict[str, Any]) -> dict[str, int]:
    created = (report.get("created") or {}).get("resources") or []
    out = {}
    for item in created:
        if isinstance(item, dict) and item.get("name") and _int(item.get("id")) > 0:
            out[str(item["name"])] = _int(item["id"])
    return out


def cmd_sync(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="kit sync-resources", description="Keep the generated kit Resources current in the ops team.")
    parser.add_argument("--env", default="prod", help="the manifest environment of the ops team (it is the prod team)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan; call nothing")
    args = parser.parse_args(argv)
    root = find_repo_root()
    if not args.dry_run:
        require_ci_main("sync-resources")
        guard_prod(args.env)
    if not (root / TENANT_CONFIG).exists():
        raise ScriptError(f"{TENANT_CONFIG} does not exist: this is not a provisioned repository (nothing to sync)")
    report = load_report(root)
    if report is None:
        raise ScriptError(f"{SETUP_REPORT} does not exist: the Resource ids come from the setup report")
    ids = resource_ids(report)
    needed = ["sdlc_sync_lock", "kit_state", *SYNCED_RESOURCES]
    missing = [n for n in needed if n not in ids]
    if missing:
        raise ScriptError(f"the setup report lists no id for {missing} (created.resources[]); add them by PR")
    tenant = os.environ.get("TINES_TENANT", "")
    if not args.dry_run and not re.match(r"^[a-z0-9][a-z0-9-]{0,62}$", tenant):
        raise ScriptError("TINES_TENANT must be the host prefix (a secret of the kit-sync environment)")
    tenant_host = f"{tenant}.tines.com" if tenant else None
    config = load_config(root)
    values = generated_resource_values(root, config, tenant_host)          # what is written
    bundle_form = bundle_resource_values(root, config)                     # what is fingerprinted
    hashes = {name: resource_hash(bundle_form[name]) for name in SYNCED_RESOURCES}
    plan = {"resources": {name: {"id": ids[name], "hash": hashes[name]} for name in SYNCED_RESOURCES},
            "lock": ids["sdlc_sync_lock"], "kit_state": ids["kit_state"],
            "limits_keys": sorted(values["sdlc_limits"].keys()), "dry_run": args.dry_run}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        eprint("[kit] sync-resources: dry run — nothing was sent")
        return 0

    client = client_from_env()
    token = f"kit-sync-{os.environ.get('GITHUB_RUN_ID') or utc_now()}"
    lock_path = f"/api/v1/global_resources/{ids['sdlc_sync_lock']}/replace"
    acquired = False
    for attempt in range(1, LOCK_ATTEMPTS + 1):
        try:
            client.post(lock_path, {"key": "lock", "value": token, "if_value": "free"})
            acquired = True
            break
        except ApiError as exc:
            if exc.status != 422:
                raise ScriptError(f"acquiring sdlc_sync_lock failed: {exc}") from None
            eprint(f"[kit] sdlc_sync_lock is held (a tracker sync is running); retry {attempt}/{LOCK_ATTEMPTS} in {LOCK_WAIT_SECONDS}s")
            time.sleep(LOCK_WAIT_SECONDS)
    if not acquired:
        eprint("[kit] sdlc_sync_lock stayed held; nothing was written. The next merge or a dispatch re-runs kit-sync.yml.")
        return 3
    written: list[str] = []
    try:
        for name in ("sdlc_state_machine", "kit_catalog", "kit_config"):
            # VERIFY: the whole-value PUT body key (A19's create body uses `value`)
            client.put(f"/api/v1/global_resources/{ids[name]}", {"value": values[name]})
            written.append(name)
        limits_path = f"/api/v1/global_resources/{ids['sdlc_limits']}/replace"
        for key, value in sorted(values["sdlc_limits"].items()):
            if key in LIMITS_HUMAN_KEYS:
                continue
            client.post(limits_path, {"key": key, "value": value})
        written.append("sdlc_limits (owned keys)")
        state_path = f"/api/v1/global_resources/{ids['kit_state']}/replace"
        for name, digest in hashes.items():
            client.post(state_path, {"key": f"hash_{name}", "value": digest})
        written.append("kit_state.hash_*")
    except ApiError as exc:
        raise ScriptError(f"sync-resources stopped after {written or 'nothing'}: {exc}") from None
    finally:
        try:
            client.post(lock_path, {"key": "lock", "value": "free", "if_value": token})
        except ApiError as exc:
            eprint(f"[kit] warning: releasing sdlc_sync_lock failed ({exc}); free it with "
                   f"./scripts/tines resource-cas {ids['sdlc_sync_lock']} --key lock --value free --if-value {token}")
    print(json.dumps({"written": written, "hashes": hashes}, indent=2))
    eprint(f"[kit] sync-resources: wrote {', '.join(written)}")
    return 0


# --------------------------------------------------------------------------- #
# set-dev-id (./scripts/tines manifest-set-dev-id)
# --------------------------------------------------------------------------- #

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
STORY_ID_RE = re.compile(r"^[1-9][0-9]{0,17}$")


def cmd_set_dev_id(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="tines manifest-set-dev-id",
                                     description="Record the dev story id the builder created through /mcp "
                                                 "(writes only stories.<slug>.dev.story_id in stories/_manifest.yaml).")
    parser.add_argument("slug", help="the story key")
    parser.add_argument("story_id", help="the id the create call returned (a positive integer)")
    args = parser.parse_args(argv)
    if not SLUG_RE.match(args.slug):
        raise ScriptError(f"{args.slug!r} is not a story key", code=2)
    if not STORY_ID_RE.match(args.story_id):
        raise ScriptError(f"{args.story_id!r} is not a story id (a positive integer)", code=2)
    new_id = int(args.story_id)
    root = find_repo_root()
    doc = YamlText(root / MANIFEST)
    data = doc.data if isinstance(doc.data, dict) else {}
    stories = data.get("stories") if isinstance(data.get("stories"), dict) else {}
    entry = stories.get(args.slug)
    if not isinstance(entry, dict) or not isinstance(entry.get("dev"), dict):
        raise ScriptError(f"{MANIFEST}: no stories.{args.slug}.dev entry — add the slug first (dev: {{ story_id: 0 }})")
    current = _int(entry["dev"].get("story_id"))
    if current == new_id:
        print(f"{MANIFEST}: stories.{args.slug}.dev.story_id is already {new_id}; nothing written")
        return 0
    if current != 0:
        raise ScriptError(f"{MANIFEST}: stories.{args.slug}.dev.story_id is already {current}; changing a recorded id is a "
                          "reviewed manifest edit by a person, never this command")
    taken: dict[int, str] = {}
    for other, e in stories.items():
        for env in ("dev", "prod"):
            if not isinstance(e, dict) or (other == args.slug and env == "dev"):
                continue
            value = _int((e.get(env) or {}).get("story_id") if isinstance(e.get(env), dict) else 0)
            if value:
                taken.setdefault(value, f"stories.{other}.{env}.story_id")
    for env_name, env in (data.get("environments") or {}).items():
        for field in ("team_id", "folder_id"):
            value = _int(env.get(field)) if isinstance(env, dict) else 0
            if value:
                taken.setdefault(value, f"environments.{env_name}.{field}")
    never = read_yaml(root / NEVER_TOUCH) or {}   # fails closed when the never-touch list is missing
    for raw in list(never.get("story_ids") or []) + list(never.get("teams") or []):
        value = _int(raw)
        if value:
            taken.setdefault(value, f"{NEVER_TOUCH} (never-touch)")
    if new_id in taken:
        raise ScriptError(f"{new_id} is already {taken[new_id]}: a dev id is the story the builder just created in the dev team")
    doc.set_scalar(["stories", args.slug, "dev", "story_id"], new_id)
    doc.write()
    print(f"{MANIFEST}: stories.{args.slug}.dev.story_id = {new_id}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: kit_config.py apply-config [...] | sync-resources [...] | set-dev-id <slug> <id>"
              "   (normally ./scripts/kit apply-config | sync-resources, ./scripts/tines manifest-set-dev-id)")
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "apply-config":
        return cmd_apply(rest)
    if cmd == "sync-resources":
        return cmd_sync(rest)
    if cmd == "set-dev-id":
        return cmd_set_dev_id(rest)
    raise ScriptError(f"unknown subcommand {cmd!r}", code=2)


if __name__ == "__main__":
    sys.exit(main())
