#!/usr/bin/env python3
"""The tracker's two directions: YAML → JSON for Flow 1, and the Tines outbox → YAML for Flow 2.

Spec: REPO-DESIGN.md §6.5 (state, field ownership, Flow 1, Flow 2, conflicts, events), §7.4 (section B),
§7.7 (section E), §8.1 (Record types), §8.3 (the repo-side tracker files). Called through ``./scripts/kit``:

``./scripts/kit tracker-json [--full] [--out FILE] [--push]``
    (``--out`` only under ``.sdlc/``, or ``$RUNNER_TEMP`` in GitHub Actions — never over repository configuration)
    Flow 1. Reads ``kit/tracker/backlog.yaml`` and ``milestones.yaml``, validates them, and converts them through
    ``kit/tracker/field-map.yaml`` into ``{schema_version, source_sha, full, entries[], milestones[], view}`` —
    Record-field names, UTC timestamps, empty values as null. ``view`` is the ``kit_tracker_view`` value that
    section B writes (B10) only when Records are not entitled. ``--push`` POSTs it to ``$TRACKER_SYNC_URL`` (the
    ``tracker_sync_in`` Webhook) and **refuses unless GITHUB_ACTIONS=true and GITHUB_REF=refs/heads/main**: the
    URL carries a secret and lives only in the GitHub environment ``tracker``, and no working-tree tracker is ever
    pushed past the human merge (REPO-DESIGN.md §3.3 row 5).

``./scripts/kit tracker-fold (--input FILE|- | --pull) [--summary FILE] [--pr-body FILE] [--dry-run]``
    Flow 2. Folds a section E ``pull`` response ``{items[{key, base_rev, outbox_seq, changes{}, brief_md?,
    retro_md?}], milestones[], events[]}`` into ``backlog.yaml`` / ``milestones.yaml``, writes ``intake.md`` or
    ``retro.md`` under ``sdlc/work/<slug>/`` and appends the events Tines logged to ``events.jsonl``. Only fields
    whose owner side is ``tines`` are taken from Tines; phase/status/open_gate only through a Tines-side gate
    decision (G0, G6, G7, GB release, GX) or the D9 improve trigger, and only when state-machine.yaml allows the
    move. Every changed row's ``rev`` becomes main's rev + 1. A field that also changed in git since the item's
    ``base_rev`` is a **conflict**: git's value is kept and the PR body says so. ``--pull`` POSTs ``{op: "pull"}``
    to ``$TRACKER_OUTBOX_URL`` first (CI on main only).

``./scripts/kit tracker-fold --ack SUMMARY``
    POSTs ``{op: "ack", items[{key, outbox_seq}]}`` for the items a PR now carries (E4). CI on main only.

``./scripts/kit tracker-fold --snapshot [--open-pr-keys K,K] [--report FILE] [--fold-divergent] [--dry-run]``
    The nightly comparison: POSTs ``{op: "snapshot", open_pr_keys[]}`` (E5 clears abandoned pending rows and
    returns every row and the ``kit_state.hash_<name>`` values), compares every row with git and every hash with
    the Resource generated from ``main`` (``resources_in_sync``). ``--fold-divergent`` applies the Tines values of
    divergent rows (a ``tracker-drift`` PR: merge it to accept the tenant's state, close it and git wins at the
    next full sync). ``--snapshot-input FILE`` reads a saved response instead (offline). Exit 4 on divergence.

Importable helpers (used by kit_bundle.py, kit_config.py and ``./scripts/sdlc check``):
``validate(instance, schema)``, ``tracker_problems(root)``, ``field_map_problems(root)``, ``load_tracker(root)``,
``dump_backlog`` / ``dump_milestones``, ``main_row_revs(root)``, ``make_event(...)``, ``append_events(...)``.

Writes are refused outside the tracker touch set (``sdlc/lifecycle/touch-sets.yaml`` ``sets.tracker``). Nothing
here ever prints a webhook URL. Dependencies: the standard library and PyYAML (``scripts/requirements.txt``).
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime as _dt
import io
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    EMAIL_RE,
    ScriptError,
    eprint,
    find_repo_root,
    is_placeholder_email,
    looks_like_secret,
    utc_now,
    walk_strings,
)

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

# --------------------------------------------------------------------------- #
# Paths and constants
# --------------------------------------------------------------------------- #

BACKLOG = Path("kit/tracker/backlog.yaml")
MILESTONES = Path("kit/tracker/milestones.yaml")
FIELD_MAP = Path("kit/tracker/field-map.yaml")
BACKLOG_SCHEMA = Path("kit/tracker/backlog.schema.json")
MILESTONES_SCHEMA = Path("kit/tracker/milestones.schema.json")
RECORDS_DIR = Path("kit/records")
CATALOG_SEEDS = Path("kit/catalog/library-seeds.yaml")
CATALOG_STARTERS = Path("kit/catalog/starter-stories.yaml")
STATE_MACHINE = Path("sdlc/lifecycle/state-machine.yaml")
TOUCH_SETS = Path("sdlc/lifecycle/touch-sets.yaml")
EVENT_SCHEMA = Path("sdlc/observability/event.schema.json")
WORK_DIR = Path("sdlc/work")

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
MAX_ENTRIES = 500                                   # B3 refuses more
TINES_SIDE_GATES = ("G0", "G6", "G7", "GB", "GX")   # §6.5: decided in Tines when Records are entitled
NEW_ROW_FIXED = ("phase", "status", "open_gate", "attempt")   # a row created by a fold starts intake/active/none/0
RUNTIME_AGENTS = ("planner", "brief_writer", "retro_writer", "brief-writer", "retro-writer")
EVENT_KEY_ORDER = ["ts", "story_key", "event_type", "from_phase", "to_phase", "gate", "decision", "actor",
                   "actor_kind", "agent", "model_tier", "model_reported", "turns", "credits_used", "summary",
                   "refs", "tracker_rev", "sha"]
# The tracker touch set (sdlc/lifecycle/touch-sets.yaml sets.tracker) — the fallback when that file is absent.
TRACKER_SET_FALLBACK = ["kit/tracker/backlog.yaml", "kit/tracker/milestones.yaml", "sdlc/work/*/intake.md",
                        "sdlc/work/*/retro.md", "sdlc/work/*/go-live-review.md", "sdlc/work/*/ship.md",
                        "sdlc/work/*/events.jsonl"]
EXIT_DIVERGED = 4


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #


def need_yaml() -> None:
    if yaml is None:
        raise ScriptError("PyYAML is required (pip install -r scripts/requirements.txt)")


def _normalise_loaded(value: Any) -> Any:
    """PyYAML turns unquoted timestamps into datetime objects; the tracker keeps them as UTC strings with Z."""
    if isinstance(value, _dt.datetime):
        if value.tzinfo is not None:
            value = value.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, _dt.date):
        return value.strftime("%Y-%m-%dT00:00:00Z")
    if isinstance(value, dict):
        return {str(k): _normalise_loaded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise_loaded(v) for v in value]
    return value


def load_yaml_text(text: str) -> Any:
    need_yaml()
    return _normalise_loaded(yaml.safe_load(text))


def read_yaml(path: Path) -> Any:
    if not path.exists():
        raise ScriptError(f"{path} not found")
    return load_yaml_text(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    if not path.exists():
        raise ScriptError(f"{path} not found")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def get_dotted(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def has_dotted(data: dict[str, Any], dotted: str) -> bool:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def set_dotted(data: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur = data
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def to_utc(text: Any) -> Optional[str]:
    """Normalise a timestamp to ``YYYY-MM-DDTHH:MM:SSZ``; None when empty or unreadable."""
    if text in (None, ""):
        return None
    if isinstance(text, (int, float)):
        return None
    s = str(text).strip()
    if UTC_RE.match(s):
        return s.split(".")[0] + "Z" if "." in s else s
    try:
        parsed = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def add_days_utc(start: str, days: int) -> Optional[str]:
    base = to_utc(start)
    if not base:
        return None
    parsed = _dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%SZ")
    return (parsed + _dt.timedelta(days=int(days))).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def untrusted_problems(obj: Any) -> list[str]:
    """Secret-looking strings and real email addresses never reach git (REPO-DESIGN.md §13 rows 1, 12)."""
    problems: list[str] = []
    for path, text in walk_strings(obj):
        name = looks_like_secret(text)
        if name:
            problems.append(f"{path}: looks like a secret ({name})")
        for match in EMAIL_RE.findall(text):
            if not is_placeholder_email(match):
                problems.append(f"{path}: carries an email address (roles only reach git)")
                break
    return problems


# --------------------------------------------------------------------------- #
# A minimal JSON Schema validator (the subset the kit's schemas use)
# --------------------------------------------------------------------------- #


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and not (
            isinstance(value, float) and (math.isnan(value) or math.isinf(value)))
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ScriptError(f"schema $ref {ref!r} is not a local reference; the kit's validator supports '#/...' only")
    node: Any = root_schema
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance: Any, schema: dict[str, Any], root_schema: Optional[dict[str, Any]] = None,
             path: str = "$") -> list[str]:
    """Validate ``instance`` against a draft 2020-12 schema; returns human-readable problems (empty = valid).

    Supports: $ref (local), type, enum, const, pattern, minLength, maxLength, minimum, maximum, required,
    properties, additionalProperties, items, minItems, maxItems, uniqueItems, allOf, anyOf, oneOf, if/then/else.
    ``format`` is annotation only. Uses ``jsonschema`` when it is installed, for full coverage.
    """
    root_schema = root_schema if root_schema is not None else schema
    if path == "$":
        try:  # full validator when available; the kit does not require it
            import jsonschema  # type: ignore

            target = schema if schema is root_schema else {"$defs": root_schema.get("$defs", {}), **schema}
            validator_cls = jsonschema.validators.validator_for(root_schema)
            validator = validator_cls(target)
            return [f"{'$' + ''.join(f'[{p!r}]' if isinstance(p, int) else f'.{p}' for p in err.absolute_path)}: "
                    f"{err.message}" for err in validator.iter_errors(instance)]
        except ImportError:
            pass
    problems: list[str] = []
    if "$ref" in schema:
        problems += validate(instance, _resolve_ref(schema["$ref"], root_schema), root_schema, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(instance, t) for t in types):
            return problems + [f"{path}: expected type {' or '.join(types)}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        problems.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if "const" in schema and instance != schema["const"]:
        problems.append(f"{path}: must equal {schema['const']!r}")
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            problems.append(f"{path}: {instance[:60]!r} does not match {schema['pattern']}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            problems.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            problems.append(f"{path}: longer than {schema['maxLength']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            problems.append(f"{path}: below {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            problems.append(f"{path}: above {schema['maximum']}")
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                problems.append(f"{path}: missing required key {req!r}")
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                problems += validate(value, props[key], root_schema, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                problems.append(f"{path}: unexpected key {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                problems += validate(value, schema["additionalProperties"], root_schema, f"{path}.{key}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            problems.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            problems.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = [canonical(v) for v in instance]
            if len(seen) != len(set(seen)):
                problems.append(f"{path}: items are not unique")
        if isinstance(schema.get("items"), dict):
            for index, value in enumerate(instance):
                problems += validate(value, schema["items"], root_schema, f"{path}[{index}]")
    for sub in schema.get("allOf", []):
        problems += validate(instance, sub, root_schema, path)
    if "anyOf" in schema and all(validate(instance, sub, root_schema, path) for sub in schema["anyOf"]):
        problems.append(f"{path}: matches none of anyOf")
    if "oneOf" in schema:
        matches = sum(1 for sub in schema["oneOf"] if not validate(instance, sub, root_schema, path))
        if matches != 1:
            problems.append(f"{path}: matches {matches} of oneOf (exactly one required)")
    if "if" in schema:
        if not validate(instance, schema["if"], root_schema, path):
            if "then" in schema:
                problems += validate(instance, schema["then"], root_schema, path)
        elif "else" in schema:
            problems += validate(instance, schema["else"], root_schema, path)
    return problems


# --------------------------------------------------------------------------- #
# YAML emitter — a fixed, readable format that round-trips exactly
# --------------------------------------------------------------------------- #

_PLAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_NUMERIC_RE = re.compile(r"^[-+]?(\.[0-9]+|[0-9][0-9_]*(\.[0-9_]*)?)([eE][-+]?[0-9]+)?$")
_YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "null", "y", "n", "~", "nan", "inf"}


def emit_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ScriptError("non-finite numbers are not allowed in the tracker")
        return repr(value)
    text = str(value)
    if _PLAIN_RE.match(text) and text.lower() not in _YAML_WORDS and not _NUMERIC_RE.match(text):
        return text
    return json.dumps(text, ensure_ascii=False)


def emit_flow_map(data: dict[str, Any], order: list[str]) -> str:
    keys = [k for k in order if k in data] + [k for k in data if k not in order]
    return "{ " + ", ".join(f"{k}: {emit_scalar(data[k])}" for k in keys) + " }"


def header_comments(text: str) -> str:
    """The leading comment block (and the blank lines inside it) of a YAML file."""
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("#") or not line.strip():
            out.append(line)
            continue
        break
    header = "".join(out).rstrip("\n")
    return header + "\n\n" if header else ""


def _row_order(fmap: "FieldMap", type_name: str) -> tuple[list[str], dict[str, list[str]]]:
    top: list[str] = []
    nested: dict[str, list[str]] = {}
    for f in fmap.fields(type_name):
        if not f.get("yaml"):
            continue
        parts = f["yaml"].split(".")
        if parts[0] not in top:
            top.append(parts[0])
        if len(parts) == 2:
            nested.setdefault(parts[0], []).append(parts[1])
    return top, nested


def dump_backlog(data: dict[str, Any], header: str, fmap: "FieldMap") -> str:
    top, nested = _row_order(fmap, "sdlc_backlog")
    lines = [f"version: {emit_scalar(data.get('version', 1))}",
             f"wip_limit_per_owner: {emit_scalar(data.get('wip_limit_per_owner', 1))}",
             "stories:"]
    for row in data.get("stories") or []:
        keys = [k for k in top if k in row] + [k for k in row if k not in top]
        for index, key in enumerate(keys):
            value = row[key]
            prefix = "  - " if index == 0 else "    "
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}: {emit_flow_map(value, nested.get(key, []))}")
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}: [{', '.join(emit_scalar(v) for v in value)}]")
            else:
                lines.append(f"{prefix}{key}: {emit_scalar(value)}")
    if not data.get("stories"):
        lines[-1] = "stories: []"
    return header + "\n".join(lines) + "\n"


def dump_milestones(data: dict[str, Any], header: str, fmap: "FieldMap") -> str:
    top, _ = _row_order(fmap, "sdlc_milestones")
    order = [k for k in top if k != "due_offset_days"]
    order.insert(order.index("due_date") if "due_date" in order else len(order), "due_offset_days")
    lines = [f"version: {emit_scalar(data.get('version', 1))}", "milestones:"]
    for item in data.get("milestones") or []:
        keys = [k for k in order if k in item] + [k for k in item if k not in order]
        for index, key in enumerate(keys):
            value = item[key]
            prefix = "  - " if index == 0 else "    "
            if isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                lines.extend(f"      - {emit_scalar(v)}" for v in value)
            else:
                lines.append(f"{prefix}{key}: {emit_scalar(value)}")
    return header + "\n".join(lines) + "\n"


def write_checked(path: Path, text: str, expected: Any) -> None:
    """Write YAML only if it parses back to exactly ``expected`` (no silent reformatting of data)."""
    parsed = load_yaml_text(text)
    if canonical(parsed) != canonical(expected):
        raise ScriptError(f"refusing to write {path}: the emitted YAML does not round-trip (report this as a bug)")
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# The field map
# --------------------------------------------------------------------------- #


class FieldMap:
    """kit/tracker/field-map.yaml — YAML key ↔ Record field ↔ result_type ↔ owner side."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.types: dict[str, dict[str, Any]] = data.get("record_types") or {}

    @classmethod
    def load(cls, root: Path) -> "FieldMap":
        return cls(read_yaml(root / FIELD_MAP))

    def fields(self, type_name: str) -> list[dict[str, Any]]:
        return list((self.types.get(type_name) or {}).get("fields") or [])

    def by_record(self, type_name: str, record_field: str) -> Optional[dict[str, Any]]:
        for f in self.fields(type_name):
            if f.get("record") == record_field:
                return f
        return None

    def by_yaml(self, type_name: str, yaml_key: str) -> Optional[dict[str, Any]]:
        for f in self.fields(type_name):
            if f.get("yaml") == yaml_key:
                return f
        return None

    def mirrored(self, type_name: str) -> list[dict[str, Any]]:
        """Fields present on both sides (a YAML key and a Record field)."""
        return [f for f in self.fields(type_name) if f.get("yaml") and f.get("record")]


def to_record_value(value: Any, f: dict[str, Any]) -> Any:
    """A repo value → the value section B writes to the Record field."""
    rtype = f.get("result_type")
    transform = f.get("transform")
    if transform == "list_to_markdown":
        return "\n".join(f"- {item}" for item in (value or []))
    if transform == "refs_to_ref":
        return "; ".join(value or []) or None
    if transform == "none_as_null":
        return "none" if value in (None, "") else value
    if rtype == "TIMESTAMP":
        return to_utc(value)
    if value == "" and f.get("empty", "keep") is None:
        return None
    return value


def from_record_value(value: Any, f: dict[str, Any]) -> Any:
    """A Record value (as the outbox returns it) → the repo value."""
    rtype = f.get("result_type")
    transform = f.get("transform")
    if transform == "list_to_markdown":
        if isinstance(value, list):
            return [str(v) for v in value]
        return [line[2:].strip() if line.startswith("- ") else line.strip()
                for line in str(value or "").splitlines() if line.strip()]
    if transform == "refs_to_ref":
        if isinstance(value, list):
            return [str(v) for v in value]
        return [part.strip() for part in str(value or "").split(";") if part.strip()]
    if transform == "none_as_null":
        return None if value in (None, "", "none") else value
    if rtype == "TIMESTAMP":
        return to_utc(value) or ""
    if rtype == "NUMBER":
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return int(value)
        try:
            number = float(value) if isinstance(value, (int, float)) else float(str(value))
        except ValueError:
            return None
        if isinstance(value, int):
            return value
        return int(number) if number.is_integer() else number
    if rtype == "BOOLEAN":
        return bool(value) if not isinstance(value, str) else value.lower() == "true"
    if rtype in ("TEXT", "ARTIFACT", "TEXT_ENUM"):
        return "" if value is None else str(value)
    return value


# --------------------------------------------------------------------------- #
# Loading the tracker, the state machine, the catalog
# --------------------------------------------------------------------------- #


def load_tracker(root: Path) -> tuple[str, dict[str, Any], str, dict[str, Any]]:
    backlog_text = (root / BACKLOG).read_text(encoding="utf-8")
    milestones_text = (root / MILESTONES).read_text(encoding="utf-8")
    return backlog_text, load_yaml_text(backlog_text) or {}, milestones_text, load_yaml_text(milestones_text) or {}


def load_state_machine(root: Path) -> dict[str, Any]:
    return read_yaml(root / STATE_MACHINE)


def all_phases(sm: dict[str, Any]) -> list[str]:
    return list(sm.get("phases") or []) + list(sm.get("holding") or []) + list(sm.get("terminal") or [])


def catalog_seed_ids(root: Path) -> set[int]:
    data = read_yaml(root / CATALOG_SEEDS)
    return {int(s["id"]) for s in (data.get("seeds") or []) if isinstance(s, dict) and "id" in s}


def record_type(root: Path, name: str) -> dict[str, Any]:
    return read_json(root / RECORDS_DIR / f"{name}.record-type.json")


def record_enum(root: Path, type_name: str, field: str) -> Optional[list[str]]:
    for f in record_type(root, type_name).get("fields") or []:
        if f.get("name") == field:
            return list(f.get("fixed_values") or [])
    return None


# --------------------------------------------------------------------------- #
# git helpers (git wins; revs are computed from main)
# --------------------------------------------------------------------------- #


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout


def is_own_git_repo(root: Path) -> bool:
    top = _git(root, "rev-parse", "--show-toplevel")
    return bool(top) and Path(top.strip()).resolve() == root.resolve()


def main_ref(root: Path) -> Optional[str]:
    """The ref whose tracker is `main`: origin/main, else main, else None (no history: the working tree is used)."""
    if not is_own_git_repo(root):
        return None
    for ref in ("origin/main", "main"):
        if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"):
            return ref
    return None


def git_show(root: Path, ref: str, rel: Path) -> Optional[str]:
    return _git(root, "show", f"{ref}:{rel.as_posix()}")


def main_row_revs(root: Path) -> tuple[dict[str, int], dict[str, int], str]:
    """(backlog revs by key, milestone revs by id, where they came from) as they stand on main.

    Falls back to the working tree (with a warning) when there is no git history, so a local dry run works.
    """
    ref = main_ref(root)
    source = ref or "working tree"
    backlog_text = git_show(root, ref, BACKLOG) if ref else None
    milestones_text = git_show(root, ref, MILESTONES) if ref else None
    if backlog_text is None:
        backlog_text = (root / BACKLOG).read_text(encoding="utf-8")
        if ref:
            source = f"{ref} (no tracker there yet; working tree used)"
    if milestones_text is None:
        milestones_text = (root / MILESTONES).read_text(encoding="utf-8")
    backlog = load_yaml_text(backlog_text) or {}
    milestones = load_yaml_text(milestones_text) or {}
    revs = {str(r.get("key")): int(r.get("rev") or 0) for r in backlog.get("stories") or [] if isinstance(r, dict)}
    mrevs = {str(m.get("id")): int(m.get("rev") or 0) for m in milestones.get("milestones") or []
             if isinstance(m, dict)}
    if not ref:
        eprint("[kit] no git history (or not this repository's own git): revs are computed from the working tree")
    return revs, mrevs, source


class History:
    """A row's value as it stood at a given rev, read from main's git history of one tracker file."""

    def __init__(self, root: Path, rel: Path, list_key: str, key_field: str, max_commits: int = 200) -> None:
        self.versions: list[dict[str, dict[str, Any]]] = []
        ref = main_ref(root)
        if not ref:
            return
        log = _git(root, "log", f"-n{max_commits}", "--format=%H", ref, "--", rel.as_posix()) or ""
        for sha in log.split():
            text = git_show(root, sha, rel)
            if text is None:
                continue
            try:
                data = load_yaml_text(text) or {}
            except Exception:  # an unparseable historic version is skipped, never fatal
                continue
            rows = {str(r.get(key_field)): r for r in data.get(list_key) or [] if isinstance(r, dict)}
            self.versions.append(rows)

    def value_at(self, key: str, rev: int, dotted: str) -> tuple[bool, Any]:
        """(found, value) of ``dotted`` in the newest version whose row ``key`` has ``rev`` ≤ the given rev."""
        for rows in self.versions:  # newest first
            row = rows.get(key)
            if row is not None and int(row.get("rev") or 0) <= rev:
                return True, get_dotted(row, dotted)
        return False, None


# --------------------------------------------------------------------------- #
# Checks (also used by ./scripts/sdlc check)
# --------------------------------------------------------------------------- #


def field_map_problems(root: Path) -> list[str]:
    """Every schema property, Record field and event key appears in field-map.yaml exactly once, and vice versa."""
    problems: list[str] = []
    fmap = FieldMap.load(root)
    for type_name, spec in fmap.types.items():
        fields = fmap.fields(type_name)
        yaml_keys = [f["yaml"] for f in fields if f.get("yaml")]
        record_keys = [f["record"] for f in fields if f.get("record")]
        for label, keys in (("yaml", yaml_keys), ("record", record_keys)):
            dupes = sorted({k for k in keys if keys.count(k) > 1})
            if dupes:
                problems.append(f"field-map {type_name}: duplicate {label} keys {dupes}")
        for f in fields:
            if f.get("owner") not in ("git", "tines", "tines-only"):
                problems.append(f"field-map {type_name}.{f.get('yaml') or f.get('record')}: owner must be git | tines | tines-only")
            if f.get("owner") == "tines-only" and f.get("yaml"):
                problems.append(f"field-map {type_name}.{f['yaml']}: a tines-only field has no YAML key")
        rt_file = spec.get("record_type_file")
        if rt_file and (root / rt_file).exists():
            rt = read_json(root / rt_file)
            rt_fields = {f["name"]: f for f in rt.get("fields") or []}
            for name in rt_fields:
                if name not in record_keys:
                    problems.append(f"{rt_file}: field {name!r} is missing from field-map.yaml ({type_name})")
            for f in fields:
                if f.get("record") and f["record"] not in rt_fields:
                    problems.append(f"field-map {type_name}: record field {f['record']!r} is not in {rt_file}")
                elif f.get("record") and rt_fields[f["record"]].get("result_type") != f.get("result_type"):
                    problems.append(f"field-map {type_name}.{f['record']}: result_type {f.get('result_type')} "
                                    f"≠ {rt_fields[f['record']].get('result_type')} in {rt_file}")
        schema_file = spec.get("schema_file")
        if schema_file and (root / schema_file).exists():
            schema = read_json(root / schema_file)
            if type_name == "sdlc_events":
                props = set((schema.get("properties") or {}).keys())
            else:
                list_key = spec.get("list_key")
                item_schema = (schema.get("properties") or {}).get(list_key, {}).get("items", {})
                if "$ref" in item_schema:
                    item_schema = _resolve_ref(item_schema["$ref"], schema)
                props = set()
                for key, sub in (item_schema.get("properties") or {}).items():
                    if sub.get("type") == "object" and sub.get("properties"):
                        props |= {f"{key}.{child}" for child in sub["properties"]}
                    else:
                        props.add(key)
                file_keys = set(spec.get("file_keys") or [])
                top_props = set((schema.get("properties") or {}).keys())
                if file_keys != top_props:
                    problems.append(f"field-map {type_name}: file_keys {sorted(file_keys)} ≠ {schema_file} top-level keys {sorted(top_props)}")
            for key in sorted(props - set(yaml_keys)):
                problems.append(f"{schema_file}: key {key!r} is missing from field-map.yaml ({type_name})")
            for key in sorted(set(yaml_keys) - props):
                problems.append(f"field-map {type_name}: yaml key {key!r} is not in {schema_file}")
    return problems


def enum_problems(root: Path) -> list[str]:
    """The Record TEXT_ENUMs and the tracker schema carry exactly the state machine's names."""
    problems: list[str] = []
    sm = load_state_machine(root)
    phases = all_phases(sm)
    gates = [sm.get("open_gate_none", "none")] + list(sm.get("gates") or [])
    expected = {
        ("sdlc_backlog", "phase"): phases,
        ("sdlc_backlog", "status"): list(sm.get("statuses") or []),
        ("sdlc_backlog", "open_gate"): gates,
        ("sdlc_events", "from_phase"): ["none"] + phases,
        ("sdlc_events", "to_phase"): ["none"] + phases,
        ("sdlc_events", "gate"): gates,
    }
    for (type_name, field), values in expected.items():
        actual = record_enum(root, type_name, field)
        if actual != values:
            problems.append(f"kit/records/{type_name}.record-type.json {field}: {actual} ≠ state-machine.yaml {values}")
    schema = read_json(root / BACKLOG_SCHEMA)
    row = schema["$defs"]["row"]["properties"]
    for field, values in (("phase", phases), ("status", list(sm.get("statuses") or [])), ("open_gate", gates)):
        if row[field].get("enum") != values:
            problems.append(f"{BACKLOG_SCHEMA} {field}: {row[field].get('enum')} ≠ state-machine.yaml {values}")
    for field in ("mode", "tier", "provider"):
        if row[field].get("enum") != record_enum(root, "sdlc_backlog", field):
            problems.append(f"{BACKLOG_SCHEMA} {field} enum ≠ kit/records/sdlc_backlog.record-type.json")
    per_phase = {}
    for clause in schema["$defs"]["row"].get("allOf") or []:
        phase = (((clause.get("if") or {}).get("properties") or {}).get("phase") or {}).get("const")
        if phase:
            per_phase[phase] = (((clause.get("then") or {}).get("properties") or {}).get("status") or {}).get("enum")
    for phase, info in (sm.get("phase_info") or {}).items():
        if per_phase.get(phase) != list((info or {}).get("statuses") or []):
            problems.append(f"{BACKLOG_SCHEMA}: statuses for {phase} {per_phase.get(phase)} ≠ state-machine.yaml phase_info")
    return problems


def tracker_problems(root: Path) -> list[str]:
    """Schema validity of backlog.yaml and milestones.yaml, unique keys, catalog-only seed ids."""
    problems: list[str] = []
    _, backlog, _, milestones = load_tracker(root)
    problems += [f"{BACKLOG}: {p}" for p in validate(backlog, read_json(root / BACKLOG_SCHEMA))]
    problems += [f"{MILESTONES}: {p}" for p in validate(milestones, read_json(root / MILESTONES_SCHEMA))]
    keys = [r.get("key") for r in backlog.get("stories") or [] if isinstance(r, dict)]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        problems.append(f"{BACKLOG}: duplicate keys {dupes}")
    ids = [m.get("id") for m in milestones.get("milestones") or [] if isinstance(m, dict)]
    if sorted(ids) != sorted(set(ids)):
        problems.append(f"{MILESTONES}: duplicate milestone ids")
    seeds = catalog_seed_ids(root)
    for row in backlog.get("stories") or []:
        seed = row.get("library_seed_id") if isinstance(row, dict) else None
        if seed is not None and seed not in seeds:
            problems.append(f"{BACKLOG}: {row.get('key')}: library_seed_id {seed} is not in {CATALOG_SEEDS}")
    return problems


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #


def make_event(**fields: Any) -> dict[str, Any]:
    event = {key: fields.get(key) for key in EVENT_KEY_ORDER}
    event["ts"] = fields.get("ts") or utc_now()
    event["refs"] = list(fields.get("refs") or [])
    return event


SCRIPT_ACTORS = ("tracker-pull", "kit apply-config")   # their events repeat only when the same input is folded again


def event_signature(event: dict[str, Any]) -> str:
    """Dedupe key. A script's own sync/conflict event is the same event whenever its summary is (no timestamp)."""
    ts = None if event.get("actor") in SCRIPT_ACTORS else event.get("ts")
    return canonical([ts, event.get("story_key"), event.get("event_type"), event.get("gate"), event.get("decision"),
                      event.get("agent"), (event.get("summary") or "")[:200]])


def read_events(root: Path, key: str) -> list[dict[str, Any]]:
    path = root / WORK_DIR / key / "events.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def append_events(root: Path, key: str, events: list[dict[str, Any]], dry_run: bool) -> int:
    """Append-only: existing lines are never rewritten; duplicates (same signature) are skipped."""
    if not events:
        return 0
    existing = {event_signature(e) for e in read_events(root, key)}
    fresh = [e for e in events if event_signature(e) not in existing]
    if not fresh or dry_run:
        return len(fresh)
    path = root / WORK_DIR / key / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current and not current.endswith("\n"):
            prefix = "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(prefix + "".join(json.dumps({k: e.get(k) for k in EVENT_KEY_ORDER}, ensure_ascii=False) + "\n"
                                  for e in fresh))
    return len(fresh)


TENANT_ONLY_EVENT_KEYS = ("actor_ref",)   # the approver's email: in-tenant audit only (§8.1, §13 row 12)


def strip_tenant_only(events: list[dict[str, Any]], notes: list[str], key: str) -> list[dict[str, Any]]:
    """Drop keys that must never reach git before anything else reads the events (the outbox should not send them)."""
    out = []
    dropped = False
    for e in events:
        if not isinstance(e, dict):
            continue
        if any(k in e for k in TENANT_ONLY_EVENT_KEYS):
            dropped = True
        out.append({k: v for k, v in e.items() if k not in TENANT_ONLY_EVENT_KEYS})
    if dropped:
        notes.append(f"{key}: the outbox sent actor_ref (in-tenant only); it was dropped and never written")
    return out


def event_from_record(raw: dict[str, Any], fmap: FieldMap, tracker_rev: int) -> tuple[Optional[dict[str, Any]], list[str]]:
    """An sdlc_events Record (as the outbox returns it) → one events.jsonl line; (event, problems)."""
    notes: list[str] = []
    out: dict[str, Any] = {}
    for f in fmap.fields("sdlc_events"):
        ykey, rkey = f.get("yaml"), f.get("record")
        if not ykey:
            continue  # actor_ref, input_tokens, output_tokens stay in the tenant
        if rkey and (rkey in raw or ykey in raw):
            value = raw.get(rkey, raw.get(ykey))
            out[ykey] = from_record_value(value, f) if f.get("transform") else value
    out["ts"] = to_utc(raw.get("ts") or raw.get("created_at") or raw.get("CREATED_AT")) or utc_now()
    agent = out.get("agent") or None
    out["agent"] = agent
    out["model_tier"] = "fast" if agent in RUNTIME_AGENTS else None
    out["turns"] = None
    for key in ("decision", "model_reported", "summary"):
        if out.get(key) in ("",):
            out[key] = None
    out["summary"] = (out.get("summary") or f"{out.get('event_type', 'event')} recorded in Tines")[:1500]
    actor = str(out.get("actor") or "")
    if "@" in actor or not actor:
        notes.append("an event actor was not a role; recorded as `approver` (the email stays in the tenant)")
        out["actor"] = "approver"
    sha = out.get("sha")
    out["sha"] = sha if isinstance(sha, str) and SHA_RE.match(sha) else None
    credits = out.get("credits_used")
    out["credits_used"] = credits if isinstance(credits, (int, float)) and not isinstance(credits, bool) else None
    out["tracker_rev"] = tracker_rev
    event = make_event(**out)
    return event, notes


# --------------------------------------------------------------------------- #
# Touch set
# --------------------------------------------------------------------------- #


def tracker_touch_set(root: Path) -> list[str]:
    path = root / TOUCH_SETS
    if path.exists():
        try:
            data = read_yaml(path)
            files = (((data.get("sets") or {}).get("tracker") or {}).get("files")) or []
            if files:
                return [str(f) for f in files]
        except ScriptError:
            pass
    return TRACKER_SET_FALLBACK


def _glob_match(pattern: str, rel: str) -> bool:
    regex = "^" + re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
    return re.match(regex, rel) is not None


def assert_in_touch_set(root: Path, paths: Iterable[Path]) -> None:
    allowed = tracker_touch_set(root)
    for path in paths:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        if not any(_glob_match(p, rel) for p in allowed):
            raise ScriptError(f"refusing to write {rel}: outside the tracker touch set ({TOUCH_SETS} sets.tracker)")


# --------------------------------------------------------------------------- #
# Flow 1 — tracker-json
# --------------------------------------------------------------------------- #


def row_to_entry(row: dict[str, Any], fmap: FieldMap, type_name: str) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    for f in fmap.mirrored(type_name):
        entry[f["record"]] = to_record_value(get_dotted(row, f["yaml"]), f)
    return entry


def _csv(rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return buf.getvalue()


def build_view(backlog: dict[str, Any], milestones: dict[str, Any], sm: dict[str, Any]) -> dict[str, Any]:
    """The kit_tracker_view value (used by B10 only when Records are not entitled; kit/resources/README.md)."""
    phases = all_phases(sm)
    stories = [r for r in backlog.get("stories") or [] if isinstance(r, dict)]
    counts = {p: 0 for p in phases}
    for row in stories:
        counts[row.get("phase")] = counts.get(row.get("phase"), 0) + 1
    gate_info = sm.get("gate_info") or {}
    open_gates = [{"key": r["key"], "title": r.get("title", ""), "gate": r.get("open_gate"),
                   "decided_by": (gate_info.get(r.get("open_gate")) or {}).get("decided_by", "")}
                  for r in stories if r.get("open_gate") not in (None, "none")]
    story_rows = [{"key": r["key"], "title": r.get("title", ""), "phase": r.get("phase"), "status": r.get("status"),
                   "open_gate": r.get("open_gate"), "owner": r.get("owner"), "target_date": r.get("target_date", ""),
                   "credit_estimate_monthly": (r.get("credit_estimate") or {}).get("monthly")} for r in stories]
    ms_rows = [{"id": m.get("id"), "title": m.get("title", ""), "status": m.get("status"),
                "due_date": m.get("due_date", "")} for m in milestones.get("milestones") or [] if isinstance(m, dict)]
    return {
        "schema_version": 1,
        "counts_by_phase": counts,
        "open_gates": open_gates,
        "stories": story_rows,
        "stories_csv": _csv([["key", "title", "phase", "status", "open_gate", "owner", "target_date",
                              "credit_estimate_monthly"]] + [[r[k] for k in ("key", "title", "phase", "status",
                                                                             "open_gate", "owner", "target_date",
                                                                             "credit_estimate_monthly")]
                                                             for r in story_rows]),
        "milestones": ms_rows,
        "milestones_csv": _csv([["id", "title", "status", "due_date"]] +
                               [[m["id"], m["title"], m["status"], m["due_date"]] for m in ms_rows]),
    }


def source_sha(root: Path) -> str:
    env_sha = os.environ.get("GITHUB_SHA", "")
    if SHA_RE.match(env_sha):
        return env_sha
    if is_own_git_repo(root):
        out = _git(root, "rev-parse", "HEAD")
        if out and SHA_RE.match(out.strip()):
            return out.strip()
    return ""


def build_sync_payload(root: Path, full: bool) -> dict[str, Any]:
    problems = tracker_problems(root) + field_map_problems(root)
    if problems:
        raise ScriptError("the tracker is not valid; nothing is sent:\n  " + "\n  ".join(problems))
    fmap = FieldMap.load(root)
    sm = load_state_machine(root)
    _, backlog, _, milestones = load_tracker(root)
    stories = backlog.get("stories") or []
    if len(stories) > MAX_ENTRIES:
        raise ScriptError(f"{len(stories)} rows; section B accepts at most {MAX_ENTRIES} per payload (B3)")
    sha = source_sha(root)
    view = build_view(backlog, milestones, sm)
    view["source_sha"] = sha
    return {
        "schema_version": 1,
        "source_sha": sha,
        "full": bool(full),
        "entries": [row_to_entry(r, fmap, "sdlc_backlog") for r in stories],
        "milestones": [row_to_entry(m, fmap, "sdlc_milestones") for m in milestones.get("milestones") or []],
        "view": view,
    }


# --------------------------------------------------------------------------- #
# The webhook calls (CI on main only; URLs are never printed)
# --------------------------------------------------------------------------- #


def require_ci_main(what: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ScriptError(
            f"{what} runs only in GitHub Actions on refs/heads/main (GITHUB_ACTIONS=true, GITHUB_REF=refs/heads/main). "
            "The tracker webhook URLs carry secrets and live only in the GitHub environment `tracker`; a laptop never "
            "holds them, and no working-tree tracker is pushed past the human merge.", code=2)


def _webhook_url(var: str) -> str:
    url = os.environ.get(var, "")
    if not url:
        raise ScriptError(f"{var} is not set (a secret of the GitHub environment `tracker`)")
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not re.match(r"^[a-z0-9-]+\.tines\.com$", host):
        raise ScriptError(f"{var} must be an https URL on a <tenant>.tines.com host (the value is not printed)")
    return url


def post_webhook(var: str, body: dict[str, Any], timeout: int = 60) -> tuple[int, Any]:
    """POST JSON to the Webhook named by env var ``var``; returns (status, parsed body). Never prints the URL."""
    url = _webhook_url(var)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json",
                                              "User-Agent": "agentic-story-factory-kit/1.0"})
    last_error = ""
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - host validated above
                raw = resp.read().decode("utf-8", errors="replace")
                status = resp.status
            try:
                return status, json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                return status, raw
        except urllib.error.HTTPError as exc:
            if exc.code in (429,) or 500 <= exc.code <= 599:
                last_error = f"HTTP {exc.code}"
                time.sleep(5 * attempt)
                continue
            raise ScriptError(f"POST to ${var} failed: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc.__class__.__name__
            time.sleep(5 * attempt)
    raise ScriptError(f"POST to ${var} failed after retries ({last_error})")


def unwrap_response(body: Any) -> dict[str, Any]:
    """The response-enabled Webhook returns the first Exit action's output; accept it bare or under body/result."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            raise ScriptError("the outbox response is not JSON") from None
    if isinstance(body, dict):
        for key in ("body", "result", "data"):
            inner = body.get(key)
            if isinstance(inner, dict) and ({"items", "rows", "entries", "milestones", "events"} & set(inner)):
                return inner
        return body
    raise ScriptError("the outbox response is not a JSON object")


# --------------------------------------------------------------------------- #
# Flow 2 — tracker-fold
# --------------------------------------------------------------------------- #


def _when_holds(when: Optional[str], attempt: Optional[int], sm: dict[str, Any]) -> bool:
    """The two `when` guards a Tines-side gate can meet; any other guard is not a Tines-side concern (True)."""
    if not when:
        return True
    cap = int(((sm.get("caps") or {}).get("rework_cap")) or 3)
    text = when.replace(" ", "")
    if attempt is None:
        return True
    if text == "attempt<rework_cap":
        return attempt < cap
    if text == "attempt>=rework_cap":
        return attempt >= cap
    return True


def resolve_transition(sm: dict[str, Any], from_phase: str, gate: str, decision: Optional[str],
                       attempt: Optional[int] = None) -> Optional[tuple[str, Optional[str]]]:
    """(to_phase, status) for a gate decision from ``from_phase``, per state-machine.yaml; None when not allowed.

    Rows are read in file order and the first match wins (state-machine.yaml, "How ./scripts/sdlc reads
    transitions"): a row with a `decision` matches only that decision; a row without one is the catch-all for its
    gate. "$same" resolves to from_phase; "$previous" and quoted expressions come back as the token itself (the
    Tines-side value is then accepted when it is a valid phase/status); a missing status is the target phase's
    first status.
    """
    terminal = set(sm.get("terminal") or [])
    info = sm.get("phase_info") or {}
    for row in sm.get("transitions") or []:
        if row.get("gate") != gate:
            continue
        src = row.get("from")
        if src != from_phase and not (src == "*" and from_phase not in terminal):
            continue
        if row.get("decision") and row.get("decision") != decision:
            continue
        if not _when_holds(row.get("when"), attempt, sm):
            continue
        to = row.get("to")
        to = from_phase if to == "$same" else to
        status = row.get("status")
        if status is None and to in info:
            status = ((info.get(to) or {}).get("statuses") or [None])[0]
        return to, status
    return None


def _explained_state_change(sm: dict[str, Any], row: dict[str, Any], new_state: dict[str, Any],
                            events: list[dict[str, Any]], brief_md: bool) -> tuple[bool, str]:
    old_phase = row.get("phase")
    new_phase = new_state.get("phase", old_phase)
    phases = all_phases(sm)
    if new_phase not in phases:
        return False, f"phase {new_phase!r} is not a phase of state-machine.yaml"
    # brief_writer opening G0 inside intake (D4 save_brief): no phase change
    if old_phase == new_phase == "intake" and new_state.get("open_gate") in ("G0", row.get("open_gate")):
        if brief_md or any(e.get("event_type") == "specialist_run" and e.get("agent") in ("brief_writer", "brief-writer")
                           for e in events):
            return True, "brief_writer opened G0"
    for e in events:
        gate, decision = e.get("gate"), e.get("decision")
        if e.get("event_type") in ("gate_decision", "budget", "escalation") and gate in TINES_SIDE_GATES:
            if e.get("event_type") == "gate_decision" and e.get("actor_kind") != "human":
                continue
            resolved = resolve_transition(sm, old_phase, gate, decision if e.get("event_type") != "escalation" else None,
                                          attempt=int(row.get("attempt") or 0))
            if not resolved:
                continue
            to_phase, _status = resolved
            if to_phase == "$previous" or to_phase == new_phase:
                return True, f"{gate} {decision or 'opened'}"
        if (e.get("event_type") == "transition" and e.get("decision") == "improve_trigger"
                and old_phase == "operate" and new_phase == "improve"):
            return True, "D9 improve_trigger"
    if new_phase == old_phase and new_state.get("status") == row.get("status") and \
            new_state.get("open_gate") == row.get("open_gate"):
        return True, "no change"
    return False, (f"{old_phase}/{row.get('status')} → {new_phase}/{new_state.get('status')} has no matching "
                   f"Tines-side gate decision (G0, G6, G7, GB, GX) or D9 event in this pull")


def _front_matter(md: str) -> dict[str, Any]:
    if not md.startswith("---"):
        return {}
    parts = md.split("\n---", 1)
    if len(parts) != 2:
        return {}
    try:
        data = load_yaml_text(parts[0][3:])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _with_front_matter(md: str, keys: dict[str, Any]) -> str:
    if md.lstrip().startswith("---"):
        return md if md.endswith("\n") else md + "\n"
    lines = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False) if not isinstance(v, (int, bool)) else emit_scalar(v)}"
                       for k, v in keys.items()] + ["---", ""]
    return "\n".join(lines) + md.lstrip("\n") + ("" if md.endswith("\n") else "\n")


class Folder:
    """One tracker-fold run over the working tree."""

    def __init__(self, root: Path, run_ref: str, dry_run: bool) -> None:
        self.root = root
        self.run_ref = run_ref
        self.dry_run = dry_run
        self.fmap = FieldMap.load(root)
        self.sm = load_state_machine(root)
        self.backlog_text, self.backlog, self.ms_text, self.milestones = load_tracker(root)
        self.backlog_schema = read_json(root / BACKLOG_SCHEMA)
        self.ms_schema = read_json(root / MILESTONES_SCHEMA)
        self.event_schema = read_json(root / EVENT_SCHEMA) if (root / EVENT_SCHEMA).exists() else None
        self.seed_ids = catalog_seed_ids(root)
        self.revs, self.mrevs, self.rev_source = main_row_revs(root)
        self._history: Optional[History] = None
        self._ms_history: Optional[History] = None
        self.summary: dict[str, Any] = {
            "run": run_ref, "rev_source": self.rev_source, "changed": [], "created": [], "conflicts": [],
            "ignored": [], "refused": [], "acks": [], "milestones_changed": [], "events_appended": 0,
            "files": [], "notes": [],
        }
        self.pending_events: dict[str, list[dict[str, Any]]] = {}
        self.pending_files: dict[Path, str] = {}

    # -- history (lazy: only when a conflict needs it) ------------------------ #

    def history(self) -> History:
        if self._history is None:
            self._history = History(self.root, BACKLOG, "stories", "key")
        return self._history

    def ms_history(self) -> History:
        if self._ms_history is None:
            self._ms_history = History(self.root, MILESTONES, "milestones", "id")
        return self._ms_history

    def changed_in_git_since(self, history: History, key: str, base_rev: int, current_rev: int, dotted: str,
                             current: Any) -> bool:
        if base_rev >= current_rev:
            return False
        found, base_value = history.value_at(key, base_rev, dotted)
        if not found:
            return current not in (None, "", [], 0)
        return canonical(base_value) != canonical(current)

    # -- rows ----------------------------------------------------------------- #

    def row(self, key: str) -> Optional[dict[str, Any]]:
        for r in self.backlog.get("stories") or []:
            if isinstance(r, dict) and r.get("key") == key:
                return r
        return None

    def new_row(self, key: str, changes: dict[str, Any]) -> dict[str, Any]:
        row: dict[str, Any] = {
            "key": key, "title": "", "use_case": "", "library_seed_id": None, "mode": "none", "owner": "",
            "tier": "production", "phase": "intake", "status": "active", "open_gate": "none", "attempt": 0,
            "target_date": "", "credit_estimate": {"monthly": None, "basis": "set at design"}, "provider": "none",
            "links": {"design_pr": "", "build_pr": "", "change_request_id": ""}, "prod_story_id": 0,
            "live_since": "", "rev": 0,
        }
        for rec_field, value in changes.items():
            f = self.fmap.by_record("sdlc_backlog", rec_field)
            if not f or not f.get("yaml") or f.get("owner") == "tines-only":
                continue
            if f["yaml"] in NEW_ROW_FIXED:
                # a new row always starts intake / active / no gate / attempt 0: a Tines-supplied state would let a
                # merge skip G0, G1 and G2 (sdlc.yml's pr_tracker_transitions refuses it too)
                if canonical(from_record_value(value, f)) != canonical(row[f["yaml"]]):
                    self.summary["notes"].append(f"{key}: a new row starts intake/active; the Tines-side {f['yaml']} "
                                                 f"{value!r} was not folded")
                continue
            new = from_record_value(value, f)
            if f["yaml"] == "mode" and new not in (record_enum(self.root, "sdlc_backlog", "mode") or []):
                self.summary["notes"].append(f"{key}: mode {value!r} is not a tracker mode; folded as none (design sets it)")
                new = "none"
            set_dotted(row, f["yaml"], new)
        if row["library_seed_id"] is not None and row["library_seed_id"] not in self.seed_ids:
            self.summary["notes"].append(f"{key}: library_seed_id {row['library_seed_id']} is not in the catalog; dropped")
            row["library_seed_id"] = None
        if not row.get("owner") or "@" in str(row.get("owner")):
            self.summary["notes"].append(f"{key}: no owner role arrived from Tines; recorded as `unassigned`")
            row["owner"] = "unassigned"
        if not row.get("title"):
            row["title"] = key
        row["key"] = key
        return row

    def fold_item(self, item: dict[str, Any], events_raw: list[dict[str, Any]]) -> None:
        key = str(item.get("key") or item.get("story_key") or "")
        outbox_seq = item.get("outbox_seq")
        if not KEY_RE.match(key):
            self.summary["refused"].append({"key": key, "outbox_seq": outbox_seq, "reasons": ["key is not a slug"]})
            return
        events_raw = strip_tenant_only(events_raw, self.summary["notes"], key)
        bad = untrusted_problems({"item": item, "events": events_raw})
        if bad:
            self.summary["refused"].append({"key": key, "outbox_seq": outbox_seq, "reasons": bad})
            return
        try:
            base_rev = int(item.get("base_rev") or 0)
        except (TypeError, ValueError):
            base_rev = 0
        changes = item.get("changes") or {}
        if not isinstance(changes, dict):
            self.summary["refused"].append({"key": key, "outbox_seq": outbox_seq, "reasons": ["changes is not an object"]})
            return
        row = self.row(key)
        new_rev = self.revs.get(key, 0) + 1
        changed_fields: list[str] = []
        conflicts: list[dict[str, Any]] = []
        ignored: list[str] = []
        created = False

        if row is None:
            row = self.new_row(key, changes)
            row["rev"] = new_rev
            problems = validate(row, self.backlog_schema["$defs"]["row"], self.backlog_schema)
            if problems:
                self.summary["refused"].append({"key": key, "outbox_seq": outbox_seq,
                                                "reasons": [f"new row is not valid: {p}" for p in problems]})
                return
            self.backlog.setdefault("stories", []).append(row)
            created = True
            changed_fields = sorted(f["yaml"] for f in self.fmap.mirrored("sdlc_backlog")
                                    if f["record"] in changes and f["yaml"] not in ("key", "rev", *NEW_ROW_FIXED))
        else:
            state_changes: dict[str, Any] = {}
            for rec_field, value in sorted(changes.items()):
                f = self.fmap.by_record("sdlc_backlog", rec_field)
                if f is None:
                    ignored.append(f"{rec_field} (not a sdlc_backlog field)")
                    continue
                if f.get("owner") == "tines-only" or not f.get("yaml"):
                    continue
                new = from_record_value(value, f)
                current = get_dotted(row, f["yaml"])
                if canonical(new) == canonical(current):
                    continue
                if f.get("tines_via"):
                    state_changes[f["yaml"]] = new
                    continue
                if f.get("owner") != "tines":
                    ignored.append(f"{f['yaml']} (git-owned; changed only by ./scripts/sdlc and PR merges)")
                    continue
                if self.changed_in_git_since(self.history(), key, base_rev, int(row.get("rev") or 0), f["yaml"], current):
                    conflicts.append({"field": f["yaml"], "git": current, "tines": new, "base_rev": base_rev})
                    continue
                set_dotted(row, f["yaml"], new)
                changed_fields.append(f["yaml"])
            if state_changes:
                new_state = {k: state_changes.get(k, row.get(k)) for k in ("phase", "status", "open_gate")}
                ok, why = _explained_state_change(self.sm, row, new_state, events_raw, bool(item.get("brief_md")))
                moved_in_git = any(self.changed_in_git_since(self.history(), key, base_rev, int(row.get("rev") or 0),
                                                             k, row.get(k)) for k in ("phase", "status", "open_gate"))
                if not ok or moved_in_git:
                    conflicts.append({"field": "phase/status/open_gate",
                                      "git": {k: row.get(k) for k in ("phase", "status", "open_gate")},
                                      "tines": new_state, "base_rev": base_rev,
                                      "why": why if not ok else "the row moved in git since the Tines-side decision"})
                else:
                    trial = copy.deepcopy(row)
                    trial.update(new_state)
                    problems = validate(trial, self.backlog_schema["$defs"]["row"], self.backlog_schema)
                    if problems:
                        conflicts.append({"field": "phase/status/open_gate", "git": {k: row.get(k) for k in new_state},
                                          "tines": new_state, "base_rev": base_rev, "why": "; ".join(problems)})
                    else:
                        for k, v in new_state.items():
                            if row.get(k) != v:
                                row[k] = v
                                changed_fields.append(k)
            if changed_fields:
                row["rev"] = new_rev

        # drafts from the runtime specialists → files (never over a human's work)
        file_changes = self.fold_drafts(key, row, item)
        changed_any = bool(changed_fields) or created or bool(file_changes)
        if file_changes and not changed_fields and not created:
            row["rev"] = new_rev
        tracker_rev = int(row.get("rev") or 0)

        events: list[dict[str, Any]] = []
        for raw in events_raw:
            event, notes = event_from_record(raw, self.fmap, tracker_rev)
            self.summary["notes"].extend(f"{key}: {n}" for n in notes)
            if event is None:
                continue
            if event.get("story_key") != key:
                event["story_key"] = key
            if self.event_schema is not None:
                problems = validate(event, self.event_schema)
                if problems:
                    self.summary["notes"].append(f"{key}: an event from Tines was not valid and was skipped: {problems[0]}")
                    continue
            events.append(event)
        if changed_any or conflicts:
            summary_text = []
            if created:
                summary_text.append("new row from Tines")
            if changed_fields:
                summary_text.append("fields " + ", ".join(sorted(set(changed_fields))))
            if file_changes:
                summary_text.append("drafts " + ", ".join(file_changes))
            if changed_any:
                events.append(make_event(story_key=key, event_type="sync", decision="folded", actor="tracker-pull",
                                         actor_kind="ci", summary=("tracker-fold: " + "; ".join(summary_text) +
                                                                   f" (outbox_seq {outbox_seq})")[:1500],
                                         refs=[self.run_ref], tracker_rev=tracker_rev))
            if conflicts:
                reasons = "; ".join(f"{c['field']}: {c.get('why') or f'changed in git since base_rev {base_rev}'}"
                                    for c in conflicts)
                events.append(make_event(story_key=key, event_type="conflict", decision="kept_git", actor="tracker-pull",
                                         actor_kind="ci",
                                         summary=f"tracker-fold kept git's value (outbox_seq {outbox_seq}) — {reasons}"[:1500],
                                         refs=[self.run_ref], tracker_rev=tracker_rev))
        if events:
            self.pending_events.setdefault(key, []).extend(events)
        if created:
            self.summary["created"].append(key)
        if changed_any:
            self.summary["changed"].append({"key": key, "fields": sorted(set(changed_fields)), "files": file_changes,
                                            "rev": tracker_rev})
        for c in conflicts:
            self.summary["conflicts"].append({"key": key, **c})
        for i in ignored:
            self.summary["ignored"].append({"key": key, "field": i})
        if outbox_seq is not None:
            self.summary["acks"].append({"key": key, "outbox_seq": outbox_seq})

    def fold_drafts(self, key: str, row: dict[str, Any], item: dict[str, Any]) -> list[str]:
        written: list[str] = []
        brief = item.get("brief_md")
        if isinstance(brief, str) and brief.strip():
            path = self.root / WORK_DIR / key / "intake.md"
            existing_fm = _front_matter(path.read_text(encoding="utf-8")) if path.exists() else {}
            if not path.exists() or (existing_fm.get("drafted_by") == "brief_writer" and row.get("phase") == "intake"):
                text = _with_front_matter(brief, {
                    "story_key": key, "title": row.get("title", ""), "owner": row.get("owner", ""),
                    "source": item.get("source") if item.get("source") in ("kickoff_page", "add_use_case_page", "app")
                    else "kickoff_page",
                    "drafted_by": "brief_writer", "data_sensitivity": "[TBD]", "simplest_rung": 0,
                    "candidate_seed_ids": [],
                })
                fm = _front_matter(text)
                if fm.get("story_key") not in (None, key):
                    self.summary["notes"].append(f"{key}: the brief's story_key {fm.get('story_key')!r} does not match; not written")
                else:
                    ids = [i for i in (fm.get("candidate_seed_ids") or []) if isinstance(i, int)]
                    stray = [i for i in ids if i not in self.seed_ids]
                    if stray:
                        self.summary["notes"].append(f"{key}: the brief cites ids outside the catalog {stray}; not written")
                    elif not path.exists() or path.read_text(encoding="utf-8") != text:
                        self.pending_files[path] = text
                        written.append("intake.md")
            else:
                self.summary["notes"].append(f"{key}: a new brief draft arrived but intake.md was kept (edited or past intake)")
        retro = item.get("retro_md")
        if isinstance(retro, str) and retro.strip():
            path = self.root / WORK_DIR / key / "retro.md"
            if not path.exists():
                text = _with_front_matter(retro, {
                    "story_key": key, "window": {"from": "", "to": ""}, "trigger": "retro_due",
                    "keep_or_change": "[TBD]", "eval_cases_requested": [], "skill_suggestions": [],
                    "cost_variance": {"estimate": 0, "actual": 0, "ratio": 0}, "curated": False, "closed": False,
                })
                self.pending_files[path] = text
                written.append("retro.md")
            else:
                self.summary["notes"].append(f"{key}: a new retro draft arrived but retro.md already exists and was kept")
        return written

    # -- milestones ----------------------------------------------------------- #

    def fold_milestone(self, raw: dict[str, Any]) -> None:
        mid = str(raw.get("milestone_id") or raw.get("id") or "")
        items = {m.get("id"): m for m in self.milestones.get("milestones") or [] if isinstance(m, dict)}
        if mid not in items:
            self.summary["notes"].append(f"milestone {mid!r} is not in {MILESTONES}; ignored")
            return
        bad = untrusted_problems(raw)
        if bad:
            self.summary["refused"].append({"milestone": mid, "reasons": bad})
            return
        current = items[mid]
        changes = raw.get("changes") if isinstance(raw.get("changes"), dict) else {
            k: v for k, v in raw.items() if k not in ("milestone_id", "id", "rev", "base_rev", "pending_repo_sync")}
        try:
            base_rev = int(raw.get("base_rev", raw.get("rev", 0)) or 0)
        except (TypeError, ValueError):
            base_rev = 0
        changed: list[str] = []
        for rec_field, value in sorted(changes.items()):
            f = self.fmap.by_record("sdlc_milestones", rec_field)
            if f is None or not f.get("yaml") or f.get("owner") == "tines-only":
                continue
            new = from_record_value(value, f)
            old = current.get(f["yaml"])
            if canonical(new) == canonical(old):
                continue
            if f.get("owner") != "tines":
                self.summary["ignored"].append({"milestone": mid, "field": f"{f['yaml']} (git-owned)"})
                continue
            if self.changed_in_git_since(self.ms_history(), mid, base_rev, int(current.get("rev") or 0), f["yaml"], old):
                self.summary["conflicts"].append({"milestone": mid, "field": f["yaml"], "git": old, "tines": new,
                                                  "base_rev": base_rev})
                continue
            trial = copy.deepcopy(current)
            trial[f["yaml"]] = new
            if validate(trial, self.ms_schema["$defs"]["milestone"], self.ms_schema):
                self.summary["notes"].append(f"milestone {mid}: {f['yaml']} {new!r} is not valid; ignored")
                continue
            current[f["yaml"]] = new
            changed.append(f["yaml"])
        if changed:
            current["rev"] = self.mrevs.get(mid, 0) + 1
            self.summary["milestones_changed"].append({"id": mid, "fields": changed, "rev": current["rev"]})

    # -- write ---------------------------------------------------------------- #

    def write(self) -> None:
        targets: list[Path] = [self.root / BACKLOG, self.root / MILESTONES, *self.pending_files.keys(),
                               *[self.root / WORK_DIR / k / "events.jsonl" for k in self.pending_events]]
        assert_in_touch_set(self.root, targets)
        if self.event_schema is not None:
            for key, events in self.pending_events.items():
                for event in events:
                    problems = validate(event, self.event_schema)
                    if problems:
                        raise ScriptError(f"refusing to append an invalid event for {key}: {problems[0]}")
        for problem in validate(self.backlog, self.backlog_schema):
            raise ScriptError(f"refusing to write {BACKLOG}: {problem}")
        for problem in validate(self.milestones, self.ms_schema):
            raise ScriptError(f"refusing to write {MILESTONES}: {problem}")
        new_backlog = dump_backlog(self.backlog, header_comments(self.backlog_text), self.fmap)
        new_ms = dump_milestones(self.milestones, header_comments(self.ms_text), self.fmap)
        if self.dry_run:
            self.summary["events_appended"] = sum(
                append_events(self.root, k, v, dry_run=True) for k, v in self.pending_events.items())
            return
        if canonical(load_yaml_text(self.backlog_text)) != canonical(self.backlog):
            write_checked(self.root / BACKLOG, new_backlog, self.backlog)
            self.summary["files"].append(BACKLOG.as_posix())
        if canonical(load_yaml_text(self.ms_text)) != canonical(self.milestones):
            write_checked(self.root / MILESTONES, new_ms, self.milestones)
            self.summary["files"].append(MILESTONES.as_posix())
        for path, text in self.pending_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.summary["files"].append(path.relative_to(self.root).as_posix())
        for key, events in self.pending_events.items():
            added = append_events(self.root, key, events, dry_run=False)
            self.summary["events_appended"] += added
            if added:
                self.summary["files"].append((WORK_DIR / key / "events.jsonl").as_posix())


def fold_outbox(root: Path, outbox: dict[str, Any], run_ref: str, dry_run: bool) -> dict[str, Any]:
    folder = Folder(root, run_ref, dry_run)
    items = outbox.get("items") or []
    events = outbox.get("events") or []
    if not isinstance(items, list) or not isinstance(events, list):
        raise ScriptError("the outbox response must carry items[] and events[] arrays")
    by_key: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        if isinstance(e, dict):
            by_key.setdefault(str(e.get("story_key") or ""), []).append(e)
    seen: set[str] = set()
    for item in sorted((i for i in items if isinstance(i, dict)), key=lambda i: str(i.get("key") or "")):
        key = str(item.get("key") or item.get("story_key") or "")
        seen.add(key)
        folder.fold_item(item, by_key.get(key, []))
    for key, evs in sorted(by_key.items()):
        if key in seen or not KEY_RE.match(key):
            continue
        row = folder.row(key)
        if row is None:
            folder.summary["notes"].append(f"{len(evs)} event(s) for unknown story {key!r} skipped")
            continue
        evs = strip_tenant_only(evs, folder.summary["notes"], key)
        bad = untrusted_problems(evs)
        if bad:
            folder.summary["refused"].append({"key": key, "events": len(evs), "reasons": bad})
            continue
        converted = []
        for raw in evs:
            event, notes = event_from_record(raw, folder.fmap, int(row.get("rev") or 0))
            folder.summary["notes"].extend(f"{key}: {n}" for n in notes)
            if event is not None and (folder.event_schema is None or not validate(event, folder.event_schema)):
                converted.append(event)
        if converted:
            folder.pending_events.setdefault(key, []).extend(converted)
    for m in outbox.get("milestones") or []:
        if isinstance(m, dict):
            folder.fold_milestone(m)
    folder.write()
    folder.summary["changed_keys"] = sorted({c["key"] for c in folder.summary["changed"]} |
                                            {c["key"] for c in folder.summary["conflicts"] if "key" in c})
    return folder.summary


def pr_body(summary: dict[str, Any], title: str) -> str:
    keys = summary.get("changed_keys") or []
    lines = [f"<!-- tracker-keys: {','.join(keys)} -->", f"## {title}", ""]
    lines.append("Tines-side changes folded into the tracker by `./scripts/kit tracker-fold` (REPO-DESIGN.md §6.5, "
                 "Flow 2). **They are provisional until a human merges this PR**; Flow 1 then brings the merged state "
                 "back into Records. Closing the PR discards them: the nightly snapshot clears the pending rows after "
                 "`sdlc_limits.pending_reset_hours`, and the nightly full sync restores git's values.")
    lines.append("")
    if summary.get("changed"):
        lines += ["| Story | Fields | Drafts | rev |", "|---|---|---|---|"]
        for c in summary["changed"]:
            lines.append(f"| `{c['key']}` | {', '.join(c['fields']) or '—'} | {', '.join(c['files']) or '—'} | {c['rev']} |")
        lines.append("")
    if summary.get("milestones_changed"):
        lines.append("**Milestones:** " + "; ".join(f"`{m['id']}` {', '.join(m['fields'])} (rev {m['rev']})"
                                                    for m in summary["milestones_changed"]))
        lines.append("")
    if summary.get("conflicts"):
        lines += ["### ⚠ Conflicts — git's value was kept", "",
                  "Each field below changed in git after the Tines-side write it came from (the item's `base_rev` is "
                  "below the row's rev), or the move is not one `sdlc/lifecycle/state-machine.yaml` allows. Git wins. "
                  "To take the Tines value instead, change it here before merging.", "",
                  "| Row | Field | git | Tines | Why |", "|---|---|---|---|---|"]
        for c in summary["conflicts"]:
            row = c.get("key") or c.get("milestone")
            lines.append(f"| `{row}` | {c['field']} | `{canonical(c.get('git'))}` | `{canonical(c.get('tines'))}` | "
                         f"{c.get('why', 'changed in git since base_rev ' + str(c.get('base_rev')))} |")
        lines.append("")
    if summary.get("ignored"):
        lines.append("**Ignored (git-owned fields change only through ./scripts/sdlc and PR merges):** " +
                     "; ".join(f"`{i.get('key') or i.get('milestone')}` {i['field']}" for i in summary["ignored"]))
        lines.append("")
    if summary.get("refused"):
        lines.append("**Refused and not acknowledged** (they stay in the outbox until fixed in Tines): " +
                     "; ".join(f"`{r.get('key') or r.get('milestone')}`: {r['reasons'][0]}" for r in summary["refused"]))
        lines.append("")
    if summary.get("notes"):
        lines.append("<details><summary>Notes</summary>\n")
        lines += [f"- {n}" for n in summary["notes"]]
        lines.append("\n</details>\n")
    lines.append(f"_Revs computed from `{summary.get('rev_source')}` (main's rev + 1). Run: {summary.get('run')}._")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Snapshot — the nightly comparison (divergence + resources_in_sync)
# --------------------------------------------------------------------------- #


def compare_snapshot(root: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    fmap = FieldMap.load(root)
    _, backlog, _, _ = load_tracker(root)
    rows = snapshot.get("rows") or snapshot.get("entries") or snapshot.get("items") or []
    tines_rows = {str(r.get("story_key") or r.get("key")): r for r in rows if isinstance(r, dict)}
    git_rows = {r["key"]: r for r in backlog.get("stories") or [] if isinstance(r, dict)}
    divergent: list[dict[str, Any]] = []
    for key, row in sorted(git_rows.items()):
        rec = tines_rows.get(key)
        if rec is None:
            divergent.append({"key": key, "kind": "missing_in_records", "fields": []})
            continue
        if str(rec.get("pending_repo_sync")).lower() == "true":
            continue  # a pending Tines-side change is an expected difference
        diffs = []
        for f in fmap.mirrored("sdlc_backlog"):
            if f["record"] not in rec:
                continue
            git_value = to_record_value(get_dotted(row, f["yaml"]), f)
            tines_value = to_record_value(from_record_value(rec[f["record"]], f), f)
            if canonical(git_value) != canonical(tines_value):
                diffs.append({"field": f["yaml"], "git": git_value, "tines": rec[f["record"]]})
        if diffs:
            divergent.append({"key": key, "kind": "differs", "fields": diffs})
    for key, rec in sorted(tines_rows.items()):
        if key not in git_rows and str(rec.get("pending_repo_sync")).lower() != "true":
            divergent.append({"key": key, "kind": "only_in_records", "fields": []})
    try:
        from kit_bundle import resources_in_sync_problems  # local import: kit_bundle imports this module
        resource_problems = resources_in_sync_problems(root, snapshot)
    except ScriptError as exc:
        resource_problems = [f"resources_in_sync could not run: {exc}"]
    return {"divergent_rows": divergent, "resource_problems": resource_problems,
            "in_sync": not divergent and not resource_problems}


def fold_divergent(root: Path, snapshot: dict[str, Any], report: dict[str, Any], run_ref: str,
                   dry_run: bool) -> dict[str, Any]:
    """Apply the Tines values of divergent rows (the tracker-drift PR). Merging accepts them; closing lets git win."""
    folder = Folder(root, run_ref, dry_run)
    rows = snapshot.get("rows") or snapshot.get("entries") or snapshot.get("items") or []
    tines_rows = {str(r.get("story_key") or r.get("key")): r for r in rows if isinstance(r, dict)}
    for d in report["divergent_rows"]:
        if d["kind"] != "differs":
            continue
        key = d["key"]
        row = folder.row(key)
        rec = tines_rows.get(key) or {}
        if row is None or untrusted_problems(rec):
            continue
        trial = copy.deepcopy(row)
        for diff in d["fields"]:
            f = folder.fmap.by_yaml("sdlc_backlog", diff["field"])
            if f:
                set_dotted(trial, f["yaml"], from_record_value(rec.get(f["record"]), f))
        trial["rev"] = folder.revs.get(key, 0) + 1
        if validate(trial, folder.backlog_schema["$defs"]["row"], folder.backlog_schema):
            folder.summary["notes"].append(f"{key}: the Records row is not a valid tracker row; left for the full sync")
            continue
        row.clear()
        row.update(trial)
        fields = [diff["field"] for diff in d["fields"]]
        folder.summary["changed"].append({"key": key, "fields": fields, "files": [], "rev": trial["rev"]})
        folder.pending_events.setdefault(key, []).append(make_event(
            story_key=key, event_type="conflict", decision="tracker_drift", actor="tracker-pull", actor_kind="ci",
            summary=f"tracker drift: Records differed from git in {', '.join(fields)}; this PR proposes the Records values",
            refs=[run_ref], tracker_rev=trial["rev"]))
    folder.write()
    folder.summary["changed_keys"] = sorted(c["key"] for c in folder.summary["changed"])
    return folder.summary


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _run_ref() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return f"tracker-pull run {run_id}" if run_id.isdigit() else f"tracker-fold {utc_now()}"


def check_json_out(root: Path, out: Path) -> Path:
    """``tracker-json --out`` writes only under ``.sdlc/`` (local, gitignored) or ``$RUNNER_TEMP`` (GitHub Actions).

    Anywhere else would be an arbitrary file write past the editor's Write/Edit deny rules — for example JSON over
    ``policies/never-touch.yml`` (which then parses with no story_ids or name_patterns) or ``.claude/settings.json``.
    The target is resolved first, so a symlink or a ``..`` cannot lead out of an allowed folder.
    """
    target = (out if out.is_absolute() else Path.cwd() / out).resolve()
    allowed = [(root / ".sdlc").resolve()]
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_TEMP"):
        allowed.append(Path(os.environ["RUNNER_TEMP"]).resolve())
    for base in allowed:
        try:
            target.relative_to(base)
            return target
        except ValueError:
            continue
    raise ScriptError(f"--out {out}: tracker-json writes only under .sdlc/ (or $RUNNER_TEMP in GitHub Actions); "
                      "the default is stdout")


def cmd_json(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="kit tracker-json", description="Flow 1: the tracker as Record-field JSON.")
    parser.add_argument("--full", action="store_true", help="mark the payload as a nightly full sync (B6 overwrites every non-pending row)")
    parser.add_argument("--out", type=Path, help="write the payload here — only under .sdlc/, or $RUNNER_TEMP in CI (default: stdout, unless --push)")
    parser.add_argument("--push", action="store_true", help="POST to $TRACKER_SYNC_URL — CI on main only")
    parser.add_argument("--check", action="store_true", help="validate the tracker and the field map; print nothing else")
    args = parser.parse_args(argv)
    root = find_repo_root()
    if args.out is not None:
        check_json_out(root, args.out)
    if args.push:
        require_ci_main("tracker-json --push")
    if args.check:
        problems = tracker_problems(root) + field_map_problems(root) + enum_problems(root)
        for p in problems:
            print(f"FAIL {p}")
        if not problems:
            print("PASS tracker valid (backlog.yaml, milestones.yaml, field-map.yaml, enums)")
        return 1 if problems else 0
    payload = build_sync_payload(root, args.full)
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        eprint(f"[kit] wrote {args.out} ({len(payload['entries'])} entries, {len(payload['milestones'])} milestones)")
    elif not args.push:
        sys.stdout.write(text)
    if args.push:
        status, body = post_webhook("TRACKER_SYNC_URL", payload)
        eprint(f"[kit] tracker_sync_in answered HTTP {status} ({len(payload['entries'])} entries, full={payload['full']})")
        summary = body if isinstance(body, (dict, list)) else str(body)[:300]
        print(json.dumps({"status": status, "entries": len(payload["entries"]), "full": payload["full"],
                          "response": summary}, ensure_ascii=False))
    return 0


def cmd_fold(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="kit tracker-fold", description="Flow 2: fold the Tines outbox into the tracker.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", help="a saved section E pull response (JSON file, or - for stdin)")
    mode.add_argument("--pull", action="store_true", help="POST {op: pull} to $TRACKER_OUTBOX_URL, then fold — CI on main only")
    mode.add_argument("--ack", type=Path, metavar="SUMMARY", help="POST {op: ack, items} for a fold summary — CI on main only")
    mode.add_argument("--snapshot", action="store_true", help="POST {op: snapshot} and compare — CI on main only")
    mode.add_argument("--snapshot-input", type=Path, help="compare a saved snapshot response (offline)")
    parser.add_argument("--open-pr-keys", default="", help="comma-separated story keys with an open tracker PR (snapshot)")
    parser.add_argument("--fold-divergent", action="store_true", help="snapshot: apply the Records values of divergent rows")
    parser.add_argument("--summary", type=Path, help="write the fold summary JSON here (default: stdout)")
    parser.add_argument("--pr-body", type=Path, help="write a Markdown PR body here")
    parser.add_argument("--report", type=Path, help="snapshot: write the comparison report JSON here")
    parser.add_argument("--save-response", type=Path, help="save the raw outbox response here (CI artifact; no secrets)")
    parser.add_argument("--dry-run", action="store_true", help="compute everything, write nothing")
    args = parser.parse_args(argv)
    root = find_repo_root()
    run_ref = _run_ref()

    if args.ack:
        require_ci_main("tracker-fold --ack")
        summary = read_json(args.ack)
        items = [{"key": a["key"], "outbox_seq": a["outbox_seq"]} for a in summary.get("acks") or []
                 if KEY_RE.match(str(a.get("key") or "")) and a.get("outbox_seq") is not None]
        if not items:
            eprint("[kit] nothing to acknowledge")
            return 0
        status, _ = post_webhook("TRACKER_OUTBOX_URL", {"op": "ack", "items": items})
        eprint(f"[kit] tracker_outbox ack answered HTTP {status} ({len(items)} item(s))")
        return 0

    if args.snapshot or args.snapshot_input:
        if args.snapshot:
            require_ci_main("tracker-fold --snapshot")
            keys = [k.strip() for k in args.open_pr_keys.split(",") if KEY_RE.match(k.strip())]
            _, body = post_webhook("TRACKER_OUTBOX_URL", {"op": "snapshot", "open_pr_keys": keys})
            snapshot = unwrap_response(body)
            if args.save_response:
                args.save_response.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            snapshot = unwrap_response(read_json(args.snapshot_input))
        report = compare_snapshot(root, snapshot)
        if args.fold_divergent and any(d["kind"] == "differs" for d in report["divergent_rows"]):
            report["fold"] = fold_divergent(root, snapshot, report, run_ref, args.dry_run)
            if args.pr_body:
                args.pr_body.write_text(pr_body(report["fold"], "Tracker drift — Records differ from git"),
                                        encoding="utf-8")
        text = json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n"
        if args.report:
            args.report.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        for d in report["divergent_rows"]:
            eprint(f"[kit] drift: {d['key']} {d['kind']} {', '.join(x['field'] for x in d['fields'])}")
        for p in report["resource_problems"]:
            eprint(f"[kit] resources_in_sync: {p}")
        return 0 if report["in_sync"] else EXIT_DIVERGED

    if args.pull:
        require_ci_main("tracker-fold --pull")
        _, body = post_webhook("TRACKER_OUTBOX_URL", {"op": "pull"})
        outbox = unwrap_response(body)
    elif args.input == "-":
        outbox = unwrap_response(json.load(sys.stdin))
    else:
        outbox = unwrap_response(read_json(Path(args.input)))
    if args.save_response:
        args.save_response.write_text(json.dumps(outbox, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = fold_outbox(root, outbox, run_ref, args.dry_run)
    text = json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n"
    if args.summary:
        args.summary.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.pr_body:
        args.pr_body.write_text(pr_body(summary, "Tracker pull — Tines-side changes"), encoding="utf-8")
    eprint(f"[kit] folded: {len(summary['changed'])} row(s) changed, {len(summary['created'])} new, "
           f"{len(summary['conflicts'])} conflict(s), {len(summary['refused'])} refused, "
           f"{summary['events_appended']} event(s){' (dry run)' if args.dry_run else ''}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: kit_tracker.py json [...] | fold [...]   (normally called as ./scripts/kit tracker-json | tracker-fold)")
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd in ("json", "tracker-json"):
        return cmd_json(rest)
    if cmd in ("fold", "tracker-fold"):
        return cmd_fold(rest)
    raise ScriptError(f"unknown subcommand {cmd!r}", code=2)


if __name__ == "__main__":
    sys.exit(main())
