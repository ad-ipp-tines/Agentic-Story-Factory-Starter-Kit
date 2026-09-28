#!/usr/bin/env python3
"""Shared helpers for ``./scripts/sdlc`` — the only writer of lifecycle state.

Spec: REPO-DESIGN.md §4.2 (the state machine), §4.6 (touch sets), §6.1 (the subcommands), §6.5 (the tracker and the
event log). Every name this module uses — phases, statuses, gates, checks, touch sets, patches — is read from
``sdlc/lifecycle/*.yaml``; nothing here defines a phase or a gate.

What lives here
---------------
1. **Paths and loading** — the repository root, the lifecycle files (``state-machine.yaml``, ``dispatch-rules.yaml``,
   ``touch-sets.yaml``), ``sdlc/gates/approvers.yaml``, the manifest, the budgets, the tenant config, the catalog.
   ``--config-root`` (CI only) lets ``sdlc.yml`` read the *rules* from the base branch while the *data* comes from the
   pull request, so a PR cannot widen its own touch set.
2. **The machine** (``Machine``) — transitions matched in file order, guards (``when``), ``$same`` / ``$previous``,
   status expressions, the gate a transition leaves open.
3. **Touch sets** — the glob grammar of ``touch-sets.yaml`` (``*`` one segment, ``**`` any depth, ``<slug>``), and
   the allow-listed patches (``.stories.<slug>``, ``.stories.<slug>.dev.story_id``, ``.agents."<slug>/*"``, the story's
   own tracker row), including a comment-preserving writer for the manifest and the budget file.
4. **JSON Schema** — a small, deterministic validator for the draft 2020-12 subset the repository's schemas use
   (``type``, ``enum``, ``const``, ``required``, ``properties``, ``additionalProperties``, ``patternProperties``,
   ``propertyNames``, ``items``, ``min/maxItems``, ``uniqueItems``, ``min/maxLength``, ``pattern``, ``minimum``,
   ``maximum``, ``exclusiveMinimum/Maximum``, ``$ref`` to ``#/…``, ``allOf``, ``anyOf``, ``oneOf``, ``not``,
   ``if/then/else``). It needs no third-party package (``scripts/requirements.txt`` stays ``requests`` + ``pyyaml``), so
   the editor and CI validate the same way.
5. **Artifacts** — YAML front matter of ``sdlc/work/<slug>/*.md`` (read, and a key-level writer that keeps the prose),
   and the one fenced ``json story-contract`` block of ``design.md``.
6. **The tracker** (``kit/tracker/backlog.yaml``) — rows read from the working tree and from ``origin/main``; one row
   rewritten in place (every other line of the file, comments included, is kept byte for byte); ``rev`` computed as
   ``main``'s rev + 1 so several writes on one branch land as one bump.
7. **The event log** (``sdlc/work/<slug>/events.jsonl``) — one typed line per write, validated against
   ``sdlc/observability/event.schema.json`` before it is appended; never rewritten.
8. **Git** — read-only helpers (``git show``, branches, diffs). Nothing here pushes.

Environment read here: none beyond what ``tines_common`` reads. ``GITHUB_ACTIONS`` / ``GITHUB_REF`` are read by the
CI-only entry points in ``sdlc_state.py``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    EMAIL_RE,
    ScriptError as _BaseScriptError,
    eprint,
    is_placeholder_email,
    looks_like_secret,
    utc_now,
    yaml,
)

# --------------------------------------------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------------------------------------------- #

STATE_MACHINE = "sdlc/lifecycle/state-machine.yaml"
DISPATCH_RULES = "sdlc/lifecycle/dispatch-rules.yaml"
TOUCH_SETS = "sdlc/lifecycle/touch-sets.yaml"
APPROVERS = "sdlc/gates/approvers.yaml"
EVENT_SCHEMA = "sdlc/observability/event.schema.json"
CONTRACT_SCHEMA = "sdlc/templates/story-contract.schema.json"
VERIFY_REPORT_SCHEMA = "sdlc/templates/verify-report.schema.json"
REWORK_SCHEMA = "sdlc/templates/rework-package.schema.json"
TEMPLATES_DIR = "sdlc/templates"
WORK_DIR = "sdlc/work"
EXAMPLES_DIR = "sdlc/examples"
AGENT_CONTRACTS_DIR = "sdlc/agents/contracts"
ENVELOPE_SCHEMA = "sdlc/agents/contracts/envelope.schema.json"
FINDINGS_SCHEMA = ".claude/skills/tines-review/references/findings-schema.json"
HANDOFF_PROMPTS = ".claude/skills/sdlc/references/handoff-prompts.md"

TRACKER = "kit/tracker/backlog.yaml"
MILESTONES = "kit/tracker/milestones.yaml"
BACKLOG_SCHEMA = "kit/tracker/backlog.schema.json"
MILESTONES_SCHEMA = "kit/tracker/milestones.schema.json"
FIELD_MAP = "kit/tracker/field-map.yaml"
TENANT_CONFIG = "kit/tenant/config.yaml"
TENANT_CONFIG_EXAMPLE = "kit/tenant/config.example.yaml"
CATALOG_SEEDS = "kit/catalog/library-seeds.yaml"
STARTER_STORIES = "kit/catalog/starter-stories.yaml"

MANIFEST = "stories/_manifest.yaml"
COST_CEILINGS = "policies/cost-ceilings.yml"
REPO_DESIGN = "REPO-DESIGN.md"

LOCAL_DIR = ".sdlc"
ACTIVE_FILE = ".sdlc/active"
OUT_DIR = ".sdlc/out"

MAIN_BRANCH = "main"

# The story key. The event schema allows ^[a-z0-9-]{1,64}$; a key never starts with a hyphen.
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# A role, never a person and never an email (event.schema.json `actor`).
ROLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()/:+-]{0,127}$")

class ScriptError(_BaseScriptError):
    """tines_common.ScriptError (prints ``error: <message>`` and exits non-zero) that also keeps its message."""

    def __init__(self, message: str, code: int = 1) -> None:
        self.message = message
        super().__init__(message, code)


_ROOT_OVERRIDE: Optional[Path] = None
_CONFIG_ROOT_OVERRIDE: Optional[Path] = None


def set_roots(root: Optional[str] = None, config_root: Optional[str] = None) -> None:
    """``--root`` / ``--config-root`` (CI): data from one tree, lifecycle rules from another."""
    global _ROOT_OVERRIDE, _CONFIG_ROOT_OVERRIDE
    if root:
        _ROOT_OVERRIDE = Path(root).resolve()
    if config_root:
        _CONFIG_ROOT_OVERRIDE = Path(config_root).resolve()


def repo_root() -> Path:
    """The directory holding ``sdlc/lifecycle/state-machine.yaml`` (cwd upwards first, then this script's repo)."""
    if _ROOT_OVERRIDE is not None:
        return _ROOT_OVERRIDE
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / STATE_MACHINE).exists():
            return candidate
    return Path(__file__).resolve().parent.parent


def config_root() -> Path:
    """Where the lifecycle RULES are read from (default: the repository root)."""
    return _CONFIG_ROOT_OVERRIDE or repo_root()


def rpath(rel: str) -> Path:
    return repo_root() / rel


def cpath(rel: str) -> Path:
    return config_root() / rel


def add_root_args(parser: Any) -> None:
    """The two CI-only options every module accepts (hidden from the usual help text)."""
    import argparse

    parser.add_argument("--root", help=argparse.SUPPRESS)
    parser.add_argument("--config-root", help=argparse.SUPPRESS)


def apply_root_args(args: Any) -> None:
    set_roots(getattr(args, "root", None), getattr(args, "config_root", None))


# --------------------------------------------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------------------------------------------- #


def check_slug(slug: str) -> str:
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise ScriptError(f"story key {slug!r} must be kebab-case: lowercase letters, digits and hyphens, ≤ 64 characters")
    return slug


def check_role(role: str, what: str = "--by") -> str:
    role = (role or "").strip()
    if not role or "@" in role or not ROLE_RE.match(role):
        raise ScriptError(f"{what} must be a role (for example security-automation), never a person or an email; got {role!r}")
    return role


def need_yaml(path: Any = "a YAML file") -> None:
    if yaml is None:
        raise ScriptError(f"reading {path} needs PyYAML (python3 -m pip install -r scripts/requirements.txt)")


def read_yaml(path: Path, *, required: bool = True) -> Any:
    if not path.exists():
        if required:
            raise ScriptError(f"{rel(path)} not found")
        return None
    need_yaml(path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # type: ignore[union-attr]
        raise ScriptError(f"{rel(path)} is not valid YAML: {str(exc).splitlines()[0]}") from None


def read_json(path: Path, *, required: bool = True) -> Any:
    if not path.exists():
        if required:
            raise ScriptError(f"{rel(path)} not found")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScriptError(f"{rel(path)} is not valid JSON: {exc}") from None


def rel(path: Path | str) -> str:
    p = Path(path)
    for base in (repo_root(), config_root()):
        try:
            return str(p.resolve().relative_to(base))
        except ValueError:
            continue
    return str(p)


def print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False))


def sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> str:
    """Canonical JSON text: sorted keys, no whitespace, UTF-8 kept."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def resource_hash(value: Any) -> str:
    """The hash recorded as ``kit_state.hash_<name>`` for a generated Resource (REPO-DESIGN.md §8.2).

    sha256 hex of the canonical JSON (sorted keys, no whitespace) of the value ``./scripts/kit`` generates from ``main``.
    ``kit-sync.yml`` must write exactly this; ``sdlc check resources_in_sync`` recomputes it.
    """
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: Any) -> Optional[dt.datetime]:
    """Parse an ISO-8601 timestamp (``Z`` or an offset); None for empty or unparsable values."""
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def truncate(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: max(limit - 1, 0)] + "…"


# --------------------------------------------------------------------------------------------------------------- #
# Globs (touch-sets.yaml grammar) and allow-listed patches
# --------------------------------------------------------------------------------------------------------------- #

_GLOB_CACHE: dict[str, re.Pattern[str]] = {}


def glob_problems(glob: str) -> list[str]:
    """Why a touch-set glob is malformed (empty list when it is well formed)."""
    problems = []
    if not isinstance(glob, str) or not glob:
        return ["empty or not a string"]
    if glob.startswith("/") or glob.startswith("./"):
        problems.append("must be repo-relative (no leading / or ./)")
    if "\\" in glob:
        problems.append("backslash")
    if "{" in glob or "}" in glob:
        problems.append("brace expansion is not part of the grammar (list each alternative)")
    if "//" in glob:
        problems.append("empty path segment")
    for seg in glob.rstrip("/").split("/"):
        if seg == "..":
            problems.append("'..' segment")
        if "**" in seg and seg != "**":
            problems.append(f"'**' must be a whole segment ({seg!r})")
    rest = re.sub(r"<[a-z_]+>", "", glob)
    if "<" in rest or ">" in rest:
        problems.append("unknown <placeholder> (only <slug> and <attempt>)")
    for ph in re.findall(r"<([a-z_]+)>", glob):
        if ph not in ("slug", "attempt"):
            problems.append(f"unknown placeholder <{ph}>")
    return problems


def glob_regex(glob: str) -> re.Pattern[str]:
    """``*`` = one path segment (no ``/``), ``**`` = any depth (zero or more segments), a trailing ``/`` = the folder."""
    cached = _GLOB_CACHE.get(glob)
    if cached is not None:
        return cached
    g = glob[:-1] + "/**" if glob.endswith("/") else glob
    out = []
    parts = g.split("/")
    for i, seg in enumerate(parts):
        last = i == len(parts) - 1
        if seg == "**":
            out.append(".*" if last else "(?:[^/]+/)*")
            continue
        piece = ""
        for ch in seg:
            piece += "[^/]*" if ch == "*" else ("[^/]" if ch == "?" else re.escape(ch))
        out.append(piece + ("" if last else "/"))
    pattern = re.compile("^" + "".join(out) + "$")
    _GLOB_CACHE[glob] = pattern
    return pattern


def expand_glob(glob: str, slug: Optional[str] = None, attempt: Optional[int] = None) -> str:
    if slug is not None:
        glob = glob.replace("<slug>", slug)
    if attempt is not None:
        glob = glob.replace("<attempt>", str(attempt))
    return glob


def path_allowed(path: str, globs: Iterable[str], slug: Optional[str] = None, attempt: Optional[int] = None) -> bool:
    path = path.lstrip("./") if path.startswith("./") else path
    for glob in globs:
        if glob_regex(expand_glob(glob, slug, attempt)).match(path):
            return True
    return False


def safe_relpath(path: str) -> str:
    """Refuse absolute paths, ``..`` and backslashes in a path a specialist asks to write."""
    if not isinstance(path, str) or not path.strip():
        raise ScriptError("a file path in the envelope is empty")
    p = path.strip()
    if p.startswith("/") or p.startswith("~") or "\\" in p or re.match(r"^[A-Za-z]:", p):
        raise ScriptError(f"{p!r}: only repository-relative paths may be written")
    parts = [s for s in p.split("/") if s not in ("", ".")]
    if any(s == ".." for s in parts):
        raise ScriptError(f"{p!r}: '..' is not allowed")
    return "/".join(parts)


# --------------------------------------------------------------------------------------------------------------- #
# JSON Schema (the draft 2020-12 subset the repository's schemas use)
# --------------------------------------------------------------------------------------------------------------- #


def _type_ok(value: Any, typ: str) -> bool:
    if typ == "null":
        return value is None
    if typ == "boolean":
        return isinstance(value, bool)
    if typ == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())
    if typ == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if typ == "string":
        return isinstance(value, str)
    if typ == "array":
        return isinstance(value, list)
    if typ == "object":
        return isinstance(value, dict)
    return False


def _resolve_ref(ref: str, root: dict[str, Any]) -> Any:
    if not ref.startswith("#"):
        raise ScriptError(f"only local $ref values are supported, got {ref!r}")
    node: Any = root
    for raw in ref[1:].lstrip("/").split("/"):
        if raw == "":
            continue
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            raise ScriptError(f"$ref {ref!r} does not resolve")
    return node


def _json_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def _closest(branch_errors: list[list[str]], path: str) -> list[str]:
    """The branch that got furthest: fewest errors at the instance's own level, then fewest errors."""
    return min(branch_errors, key=lambda errs: (sum(1 for e in errs if e.startswith(f"{path}:")), len(errs)))


def validate(instance: Any, schema: Any, root: Optional[dict[str, Any]] = None, path: str = "$") -> list[str]:
    """Return a list of error strings (empty = valid)."""
    if root is None:
        root = schema if isinstance(schema, dict) else {}
    if schema is True or schema is None:
        return []
    if schema is False:
        return [f"{path}: no value is allowed here"]
    if not isinstance(schema, dict):
        return []
    errors: list[str] = []

    if "$ref" in schema:
        errors += validate(instance, _resolve_ref(schema["$ref"], root), root, path)

    typ = schema.get("type")
    if typ is not None:
        types = typ if isinstance(typ, list) else [typ]
        if not any(_type_ok(instance, t) for t in types):
            return errors + [f"{path}: expected {'/'.join(types)}, got {type(instance).__name__}"]

    if "enum" in schema and not any(_json_equal(instance, e) for e in schema["enum"]):
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if "const" in schema and not _json_equal(instance, schema["const"]):
        errors.append(f"{path}: must be {schema['const']!r}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {truncate(instance, 60)!r} does not match {schema['pattern']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below the minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: above the maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: must be above {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: must be below {schema['exclusiveMaximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = []
            for item in instance:
                key = canonical_json(item)
                if key in seen:
                    errors.append(f"{path}: items are not unique")
                    break
                seen.append(key)
        items = schema.get("items")
        if isinstance(items, (dict, bool)):
            for i, item in enumerate(instance):
                errors += validate(item, items, root, f"{path}[{i}]")

    if isinstance(instance, dict):
        props = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        pattern_props = schema.get("patternProperties") or {}
        for key, value in instance.items():
            matched = False
            if key in props:
                matched = True
                errors += validate(value, props[key], root, f"{path}.{key}")
            for pat, sub in pattern_props.items():
                if re.search(pat, key):
                    matched = True
                    errors += validate(value, sub, root, f"{path}.{key}")
            if not matched and "additionalProperties" in schema:
                ap = schema["additionalProperties"]
                if ap is False:
                    errors.append(f"{path}: unexpected key {key!r}")
                elif isinstance(ap, dict):
                    errors += validate(value, ap, root, f"{path}.{key}")
        if "propertyNames" in schema:
            for key in instance:
                errors += validate(key, schema["propertyNames"], root, f"{path}.<key {key!r}>")
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errors.append(f"{path}: fewer than {schema['minProperties']} keys")
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errors.append(f"{path}: more than {schema['maxProperties']} keys")

    for sub in schema.get("allOf") or []:
        errors += validate(instance, sub, root, path)
    if "anyOf" in schema:
        branch_errors = [validate(instance, sub, root, path) for sub in schema["anyOf"]]
        if all(branch_errors):
            closest = _closest(branch_errors, path)
            errors.append(f"{path}: matches none of anyOf (closest branch: {'; '.join(closest[:3])})")
    if "oneOf" in schema:
        branch_errors = [validate(instance, sub, root, path) for sub in schema["oneOf"]]
        hits = sum(1 for e in branch_errors if not e)
        if hits != 1:
            closest = _closest(branch_errors, path) if hits == 0 else []
            errors.append(f"{path}: matches {hits} of oneOf (exactly 1 required)" + (f" (closest branch: {'; '.join(closest[:3])})" if closest else ""))
    if "not" in schema and not validate(instance, schema["not"], root, path):
        errors.append(f"{path}: matches a 'not' schema")
    if "if" in schema:
        if not validate(instance, schema["if"], root, path):
            if "then" in schema:
                errors += validate(instance, schema["then"], root, path)
        elif "else" in schema:
            errors += validate(instance, schema["else"], root, path)
    return errors


def schema_problems(schema: Any) -> list[str]:
    """Structural problems in a schema file: not an object, unresolvable $ref, unknown type names, bad patterns."""
    problems: list[str] = []
    if not isinstance(schema, dict):
        return ["the schema is not a JSON object"]
    known_types = {"null", "boolean", "integer", "number", "string", "array", "object"}

    map_keywords = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
    one_keywords = ("items", "additionalProperties", "not", "if", "then", "else", "propertyNames", "contains", "unevaluatedProperties")
    list_keywords = ("allOf", "anyOf", "oneOf", "prefixItems")

    def walk(node: Any, where: str) -> None:
        """Walk SCHEMA positions only (a property named `type` is a name, not the keyword)."""
        if isinstance(node, bool):
            return
        if not isinstance(node, dict):
            problems.append(f"{where}: a schema must be an object or a boolean")
            return
        if "$ref" in node:
            try:
                _resolve_ref(str(node["$ref"]), schema)
            except ScriptError as exc:
                problems.append(f"{where}: {getattr(exc, 'message', exc)}")
        typ = node.get("type")
        if typ is not None:
            for t in typ if isinstance(typ, list) else [typ]:
                if not isinstance(t, str) or t not in known_types:
                    problems.append(f"{where}: unknown type {t!r}")
        if "pattern" in node:
            try:
                re.compile(str(node["pattern"]))
            except re.error as exc:
                problems.append(f"{where}: pattern does not compile ({exc})")
        if "required" in node and not isinstance(node["required"], list):
            problems.append(f"{where}: 'required' must be a list")
        if "enum" in node and not isinstance(node["enum"], list):
            problems.append(f"{where}: 'enum' must be a list")
        for key in map_keywords:
            sub = node.get(key)
            if isinstance(sub, dict):
                for name, value in sub.items():
                    walk(value, f"{where}.{key}.{name}")
                    if key == "patternProperties":
                        try:
                            re.compile(name)
                        except re.error as exc:
                            problems.append(f"{where}.{key}: {name!r} does not compile ({exc})")
            elif sub is not None:
                problems.append(f"{where}.{key} must be an object")
        for key in one_keywords:
            if key in node:
                walk(node[key], f"{where}.{key}")
        for key in list_keywords:
            if key in node:
                if not isinstance(node[key], list):
                    problems.append(f"{where}.{key} must be a list")
                    continue
                for i, item in enumerate(node[key]):
                    walk(item, f"{where}.{key}[{i}]")

    walk(schema, "$")
    return problems


def load_schema(relpath: str, *, from_config: bool = False, required: bool = False) -> Optional[dict[str, Any]]:
    path = (cpath if from_config else rpath)(relpath)
    data = read_json(path, required=required)
    return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------------------------------------------- #
# Front matter and the design contract
# --------------------------------------------------------------------------------------------------------------- #

_FM_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)


def split_front_matter(text: str) -> tuple[Optional[dict[str, Any]], str, str]:
    """Return ``(front_matter_or_None, front_matter_text, body)``."""
    m = _FM_RE.match(text)
    if not m:
        return None, "", text
    need_yaml("front matter")
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:  # type: ignore[union-attr]
        raise ScriptError(f"front matter is not valid YAML: {str(exc).splitlines()[0]}") from None
    if not isinstance(data, dict):
        raise ScriptError("front matter must be a YAML mapping")
    return data, m.group(1), text[m.end():]


def read_front_matter(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    fm, _, _ = split_front_matter(path.read_text(encoding="utf-8"))
    return fm


def set_front_matter_key(path: Path, key: str, value: Any) -> None:
    """Set one top-level scalar key in a file's front matter, keeping every other line (and the prose) as it is."""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ScriptError(f"{rel(path)} has no front matter")
    fm_text = m.group(1)
    rendered = yaml.safe_dump({key: value}, default_flow_style=True, width=10000).strip()  # type: ignore[union-attr]
    rendered = rendered[1:-1].strip() if rendered.startswith("{") else rendered
    line_re = re.compile(rf"^{re.escape(key)}:[^\n]*$", re.M)
    if line_re.search(fm_text):
        def _keep_comment(match: re.Match[str]) -> str:
            old = match.group(0)
            comment = ""
            cm = re.search(r"\s+#.*$", old)
            if cm and not re.search(r"['\"]", old[cm.start():]):
                comment = cm.group(0)
            return rendered + comment

        new_fm = line_re.sub(_keep_comment, fm_text, count=1)
    else:
        new_fm = fm_text.rstrip("\n") + "\n" + rendered
    new_text = text[: m.start(1)] + new_fm + text[m.end(1):]
    check, _, _ = split_front_matter(new_text)
    if check is None or check.get(key) != value:
        raise ScriptError(f"could not set {key} in {rel(path)} safely")
    path.write_text(new_text, encoding="utf-8")


_CONTRACT_FENCE_RE = re.compile(r"^```json[ \t]+story-contract[ \t]*\n(.*?)\n```[ \t]*$", re.S | re.M)


def extract_contract(text: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """The ONE fenced ``json story-contract`` block of a design.md: ``(contract, error)``."""
    blocks = _CONTRACT_FENCE_RE.findall(text)
    if not blocks:
        return None, "design.md holds no fenced block with the info string `json story-contract`"
    if len(blocks) > 1:
        return None, f"design.md holds {len(blocks)} `json story-contract` blocks; exactly one is allowed"
    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        return None, f"the contract block is not valid JSON: {exc}"
    if not isinstance(data, dict):
        return None, "the contract block is not a JSON object"
    return data, None


def work_dir(slug: str) -> Path:
    return rpath(f"{WORK_DIR}/{slug}")


def load_contract(slug: str) -> tuple[Optional[dict[str, Any]], list[str]]:
    """The story's contract and its validation errors against story-contract.schema.json."""
    design = work_dir(slug) / "design.md"
    if not design.is_file():
        return None, [f"{rel(design)} does not exist"]
    contract, err = extract_contract(design.read_text(encoding="utf-8"))
    if err:
        return None, [err]
    schema = load_schema(CONTRACT_SCHEMA, from_config=True)
    errors = validate(contract, schema) if schema else [f"{CONTRACT_SCHEMA} not found"]
    if contract and contract.get("story_key") not in (None, slug):
        errors.append(f"contract story_key is {contract.get('story_key')!r}, not {slug!r}")
    return contract, errors


# --------------------------------------------------------------------------------------------------------------- #
# Git (read-only helpers)
# --------------------------------------------------------------------------------------------------------------- #


def git(*args: str, check: bool = False, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=str(cwd or repo_root()), capture_output=True, text=True, check=check)
    except FileNotFoundError:
        raise ScriptError("git is not installed") from None
    except subprocess.CalledProcessError as exc:
        raise ScriptError(f"git {' '.join(args)} failed: {(exc.stderr or '').strip()[:300]}") from None


def in_git() -> bool:
    try:
        return git("rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except ScriptError:
        return False


def main_ref() -> Optional[str]:
    """``origin/main`` when the remote-tracking ref exists, else the local ``main`` branch, else None."""
    if not in_git():
        return None
    for ref in (f"origin/{MAIN_BRANCH}", MAIN_BRANCH):
        if git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0:
            return ref
    return None


def git_show(ref: str, relpath: str) -> Optional[str]:
    if not in_git():
        return None
    p = git("show", f"{ref}:{relpath}")
    return p.stdout if p.returncode == 0 else None


def current_branch() -> Optional[str]:
    if not in_git():
        return None
    name = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    return None if name in ("", "HEAD") else name


def head_sha(short: bool = True) -> Optional[str]:
    if not in_git():
        return None
    p = git("rev-parse", "--short=7", "HEAD") if short else git("rev-parse", "HEAD")
    if p.returncode != 0:
        return None
    return p.stdout.strip() or None


def branches_matching(prefix: str) -> list[str]:
    """Local and remote-tracking branch names (without ``origin/``) starting with ``prefix``."""
    if not in_git():
        return []
    p = git("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    names = set()
    for ref in p.stdout.split():
        if ref.startswith("refs/heads/"):
            name = ref[len("refs/heads/"):]
        elif ref.startswith("refs/remotes/"):
            name = ref[len("refs/remotes/"):].split("/", 1)[-1]
        else:
            continue
        if name.startswith(prefix):
            names.add(name)
    return sorted(names)


def commit_time(ref: str) -> Optional[dt.datetime]:
    if not in_git():
        return None
    p = git("log", "-1", "--format=%cI", ref)
    return parse_ts(p.stdout.strip()) if p.returncode == 0 else None


def is_ancestor(sha: str, ref: str) -> Optional[bool]:
    if not in_git():
        return None
    p = git("merge-base", "--is-ancestor", sha, ref)
    if p.returncode in (0, 1):
        return p.returncode == 0
    return None


def changed_paths(base: str, head: str = "HEAD") -> list[str]:
    p = git("diff", "--name-only", "--no-renames", f"{base}...{head}")
    if p.returncode != 0:
        p = git("diff", "--name-only", "--no-renames", base, head)
        if p.returncode != 0:
            raise ScriptError(f"cannot diff {base}..{head}: {p.stderr.strip()[:200]}")
    return [line for line in p.stdout.splitlines() if line.strip()]


def gh_json(*args: str) -> Optional[Any]:
    """Run ``gh`` (read-only calls only: ``pr list`` / ``pr view``); None when gh is missing or fails."""
    try:
        p = subprocess.run(["gh", *args], cwd=str(repo_root()), capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout or "null")
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------------------------------------------- #
# Lifecycle files
# --------------------------------------------------------------------------------------------------------------- #


class Machine:
    """``sdlc/lifecycle/state-machine.yaml`` — the single source of phase, status and gate names."""

    def __init__(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ScriptError(f"{STATE_MACHINE} must be a mapping")
        self.data = data
        self.phases: list[str] = list(data.get("phases") or [])
        self.holding: list[str] = list(data.get("holding") or [])
        self.terminal: list[str] = list(data.get("terminal") or [])
        self.statuses: list[str] = list(data.get("statuses") or [])
        self.gates: list[str] = list(data.get("gates") or [])
        self.caps: dict[str, Any] = dict(data.get("caps") or {})
        self.timers: dict[str, Any] = dict(data.get("timers") or {})
        self.thresholds: dict[str, Any] = dict(data.get("thresholds") or {})
        self.open_gate_none: str = str(data.get("open_gate_none") or "none")
        self.phase_info: dict[str, Any] = dict(data.get("phase_info") or {})
        self.gate_info: dict[str, Any] = dict(data.get("gate_info") or {})
        self.instruments: dict[str, list[str]] = {k: list(v or []) for k, v in (data.get("instruments") or {}).items()}
        self.transitions: list[dict[str, Any]] = [t for t in (data.get("transitions") or []) if isinstance(t, dict)]
        self.checks: dict[str, Any] = dict(data.get("checks") or {})
        self.runtime_dispatch: dict[str, Any] = dict(data.get("runtime_dispatch") or {})

    # names
    @property
    def all_phases(self) -> list[str]:
        return self.phases + self.holding + self.terminal

    @property
    def gate_values(self) -> list[str]:
        return [self.open_gate_none, *self.gates]

    def cap(self, name: str, default: int) -> int:
        try:
            return int(self.caps.get(name, default))
        except (TypeError, ValueError):
            return default

    def statuses_for(self, phase: str) -> list[str]:
        info = self.phase_info.get(phase) or {}
        return list(info.get("statuses") or self.statuses)

    def decisions_for(self, gate: str) -> list[str]:
        return list((self.gate_info.get(gate) or {}).get("decisions") or [])

    def is_terminal(self, phase: str) -> bool:
        return phase in self.terminal

    # transitions
    def matches(
        self,
        t: dict[str, Any],
        phase: str,
        *,
        gate: Optional[str] = None,
        check: Optional[str] = None,
        decision: Optional[str] = None,
        guard: Optional[Any] = None,
    ) -> bool:
        """File-order matching (state-machine.yaml header): from, gate or check, decision, when."""
        frm = t.get("from")
        if frm == "*":
            if self.is_terminal(phase):
                return False
        elif frm != phase:
            return False
        if gate is None and check is None:
            return False
        if gate is not None and not (t.get("gate") == gate or gate in (t.get("gates") or [])):
            return False
        if check is not None and t.get("check") != check:
            return False
        if "decision" in t and t.get("decision") != decision:
            return False  # a row with a decision matches only that decision; without one it is the gate's catch-all
        when = t.get("when")
        if when:
            if guard is None or not guard(str(when)):
                return False
        return True

    def find(self, phase: str, **kw: Any) -> Optional[dict[str, Any]]:
        for t in self.transitions:
            if self.matches(t, phase, **kw):
                return t
        return None


@dataclass
class Lifecycle:
    machine: Machine
    rules: dict[str, Any]
    touch: dict[str, Any]


def load_machine() -> Machine:
    return Machine(read_yaml(cpath(STATE_MACHINE)) or {})


def load_rules() -> dict[str, Any]:
    return read_yaml(cpath(DISPATCH_RULES)) or {}


def load_touch_sets() -> dict[str, Any]:
    return read_yaml(cpath(TOUCH_SETS)) or {}


def load_approvers() -> dict[str, Any]:
    return read_yaml(cpath(APPROVERS), required=False) or {}


def load_lifecycle() -> Lifecycle:
    return Lifecycle(load_machine(), load_rules(), load_touch_sets())


def load_manifest() -> dict[str, Any]:
    return read_yaml(rpath(MANIFEST)) or {}


def load_ceilings() -> dict[str, Any]:
    return read_yaml(rpath(COST_CEILINGS), required=False) or {}


def manifest_entry(slug: str, manifest: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    manifest = manifest if manifest is not None else load_manifest()
    entry = (manifest.get("stories") or {}).get(slug)
    return entry if isinstance(entry, dict) else None


def manifest_new(slug: str, manifest: Optional[dict[str, Any]] = None) -> bool:
    entry = manifest_entry(slug, manifest) or {}
    return bool(entry.get("new", False))


def load_story_meta(slug: str) -> Optional[dict[str, Any]]:
    path = rpath(f"stories/{slug}/story.meta.yaml")
    data = read_yaml(path, required=False)
    return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------------------------------------------- #
# Touch sets
# --------------------------------------------------------------------------------------------------------------- #


def phase_touch(touch: dict[str, Any], phase: str) -> dict[str, Any]:
    return dict((touch.get("phases") or {}).get(phase) or {})


def agent_touch(touch: dict[str, Any], agent: str) -> Optional[dict[str, Any]]:
    entry = (touch.get("agents") or {}).get(agent)
    return dict(entry) if isinstance(entry, dict) else None


def set_touch(touch: dict[str, Any], name: str) -> dict[str, Any]:
    return dict((touch.get("sets") or {}).get(name) or {})


def script_touch(touch: dict[str, Any], script: str, *, phase: Optional[str] = None, agent: Optional[str] = None) -> tuple[list[str], list[str]]:
    """``(file globs, patch names)`` a lifecycle script may write, intersected with its phase's entry where it has one."""
    entry = dict((touch.get("scripts") or {}).get(script) or {})
    if not entry:
        raise ScriptError(f"{TOUCH_SETS} has no scripts.{script} entry")
    files = list(entry.get("files") or [])
    patches = list(entry.get("patches") or [])
    src = entry.get("files_from")
    if src == "agent":
        a = agent_touch(touch, agent or "") or {}
        files = list(a.get("files") or []) + list(entry.get("extra_files") or [])
    elif src == "phase":
        files = list(phase_touch(touch, phase or "").get("files") or [])
    elif isinstance(src, str) and src.startswith("set:"):
        files = list(set_touch(touch, src[4:]).get("files") or [])
    return files, patches


def patch_spec(touch: dict[str, Any], name: str) -> dict[str, Any]:
    spec = (touch.get("patches") or {}).get(name)
    if not isinstance(spec, dict):
        raise ScriptError(f"{TOUCH_SETS} has no patches.{name}")
    return dict(spec)


# The four yq paths touch-sets.yaml allow-lists, recognised by shape. Anything else is refused.
PATCH_SHAPES = {
    ".stories.<slug>": "manifest_entry",
    ".stories.<slug>.dev.story_id": "manifest_dev_id",
    '.agents."<slug>/*"': "budget_lines",
    '.stories[] | select(.key == "<slug>")': "tracker_row",
}


def patch_shape(path_expr: str) -> str:
    shape = PATCH_SHAPES.get(str(path_expr).strip())
    if shape is None:
        raise ScriptError(f"patch path {path_expr!r} is not one of the allow-listed shapes {list(PATCH_SHAPES)}")
    return shape


def strip_patch(data: Any, shape: str, slug: str) -> Any:
    """``data`` with the part a patch may change removed (for 'nothing else changed' comparisons)."""
    data = json.loads(json.dumps(data if data is not None else {}, default=str))
    if not isinstance(data, dict):
        return data
    if shape == "manifest_entry":
        (data.get("stories") or {}).pop(slug, None) if isinstance(data.get("stories"), dict) else None
    elif shape == "manifest_dev_id":
        entry = (data.get("stories") or {}).get(slug) if isinstance(data.get("stories"), dict) else None
        if isinstance(entry, dict) and isinstance(entry.get("dev"), dict):
            entry["dev"].pop("story_id", None)
    elif shape == "budget_lines":
        if isinstance(data.get("agents"), dict):
            data["agents"] = {k: v for k, v in data["agents"].items() if not str(k).startswith(f"{slug}/")}
    elif shape == "tracker_row":
        if isinstance(data.get("stories"), list):
            data["stories"] = [r for r in data["stories"] if not (isinstance(r, dict) and r.get("key") == slug)]
    return data


def patch_only_violation(file: str, base_text: Optional[str], head_text: Optional[str], shapes: list[str], slug: str) -> Optional[str]:
    """None when ``file`` changed only inside the allow-listed patch shapes for ``slug``."""
    need_yaml(file)
    try:
        base = yaml.safe_load(base_text or "") or {}  # type: ignore[union-attr]
        head = yaml.safe_load(head_text or "") or {}  # type: ignore[union-attr]
    except yaml.YAMLError:  # type: ignore[union-attr]
        return f"{file}: not valid YAML on one side"
    if head_text is None:
        return f"{file}: deleted — a lifecycle PR may only patch it"
    for shape in shapes:
        base, head = strip_patch(base, shape, slug), strip_patch(head, shape, slug)
    if canonical_json(json.loads(json.dumps(base, default=str))) != canonical_json(json.loads(json.dumps(head, default=str))):
        return f"{file}: changes outside the allow-listed patch ({', '.join(shapes)} for {slug})"
    return None


def branch_rule(touch: dict[str, Any], branch: str) -> Optional[dict[str, Any]]:
    """The first ``branches:`` entry whose prefix and pattern match, with the slug it names (if any)."""
    for b in touch.get("branches") or []:
        if not isinstance(b, dict) or not branch.startswith(str(b.get("prefix") or "\0")):
            continue
        pattern = str(b.get("pattern") or "")
        rx = "^" + re.escape(pattern).replace(re.escape("<slug>"), "(?P<slug>[a-z0-9][a-z0-9-]{0,63})").replace(r"\*", "[^/]+") + "$"
        m = re.match(rx, branch)
        if not m:
            return {**b, "slug": None, "malformed": True}
        return {**b, "slug": m.groupdict().get("slug")}
    return None


def allowed_for(touch: dict[str, Any], *, phases: Optional[list[str]] = None, set_name: Optional[str] = None) -> tuple[list[str], list[str]]:
    """(file globs, patch names) for a union of phases, or for a named set."""
    files: list[str] = []
    patches: list[str] = []
    if set_name:
        s = set_touch(touch, set_name)
        files += list(s.get("files") or [])
        patches += list(s.get("patches") or [])
    for ph in phases or []:
        e = phase_touch(touch, ph)
        files += list(e.get("files") or [])
        patches += list(e.get("patches") or [])
    return files, sorted(set(patches))


def touch_violations(changed: list[str], *, slug: Optional[str], files: list[str], patches: list[str], touch: dict[str, Any],
                     base_ref: str, head_reader: Any) -> list[str]:
    """Every changed path outside ``files``, or a patch file changed outside its allow-listed shape."""
    by_file: dict[str, list[str]] = {}
    for name in patches:
        spec = patch_spec(touch, name)
        by_file.setdefault(str(spec.get("file")), []).append(patch_shape(str(spec.get("path"))))
    out = []
    for path in changed:
        if slug is not None and path_allowed(path, files, slug):
            continue
        if slug is None and path_allowed(path, [f for f in files if "<slug>" not in f]):
            continue
        if path in by_file and slug is not None:
            v = patch_only_violation(path, git_show(base_ref, path), head_reader(path), by_file[path], slug)
            if v:
                out.append(v)
            continue
        out.append(f"{path}: outside the touch set")
    return out


def working_changes(base_ref: str) -> list[str]:
    """Paths changed on this branch relative to its merge-base with ``base_ref`` — committed, staged, unstaged and
    untracked (so ``sdlc ready`` sees what the PR will carry before it is committed)."""
    mb = git("merge-base", base_ref, "HEAD")
    base = mb.stdout.strip() if mb.returncode == 0 and mb.stdout.strip() else base_ref
    p = git("diff", "--name-only", "--no-renames", base)
    paths = set(p.stdout.splitlines()) if p.returncode == 0 else set()
    u = git("ls-files", "--others", "--exclude-standard")
    paths |= set(u.stdout.splitlines()) if u.returncode == 0 else set()
    return sorted(x for x in paths if x and not is_local_path(x))


def is_local_path(path: str) -> bool:
    """Local by design and never committed (.sdlc/, .tines/, Python bytecode) — gitignored by §3.3 row 4."""
    parts = path.split("/")
    return parts[0] in (".sdlc", ".tines") or "__pycache__" in parts or path.endswith(".pyc")


def read_head_file(path: str) -> Optional[str]:
    full = repo_root() / path
    return full.read_text(encoding="utf-8") if full.is_file() else None


# --------------------------------------------------------------------------------------------------------------- #
# Comment-preserving YAML edits (the allow-listed patches)
# --------------------------------------------------------------------------------------------------------------- #


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _flow(value: Any) -> str:
    text = yaml.safe_dump(value, default_flow_style=True, sort_keys=False, width=10000, allow_unicode=True).strip()  # type: ignore[union-attr]
    if text.endswith("\n..."):
        text = text[: -len("\n...")]
    if text.endswith("..."):
        text = text[:-3].strip()
    return text


def yaml_key_text(key: str) -> str:
    return key if re.match(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$", key) else json.dumps(key)


def set_mapping_child(path: Path, parent: str, key: str, value: Any) -> None:
    """Set ``<parent>.<key> = value`` in a top-level mapping of a YAML file, as one flow-style line.

    Only the child's own lines are replaced (or one line appended at the end of the parent's block); every other line,
    comments included, stays byte for byte. The result is re-parsed and compared before it is written.
    """
    need_yaml(path)
    text = path.read_text(encoding="utf-8")
    before = yaml.safe_load(text) or {}  # type: ignore[union-attr]
    lines = text.splitlines(keepends=True)
    p_idx = next((i for i, ln in enumerate(lines) if re.match(rf"^{re.escape(parent)}:\s*(#.*)?$", ln.rstrip("\n"))), None)
    if p_idx is None:
        raise ScriptError(f"{rel(path)} has no top-level block `{parent}:` to patch")
    end = len(lines)
    for j in range(p_idx + 1, len(lines)):
        s = lines[j]
        if s.strip() and not s.lstrip().startswith("#") and _indent(s) == 0:
            end = j
            break
    child_indent = None
    for j in range(p_idx + 1, end):
        s = lines[j]
        if s.strip() and not s.lstrip().startswith("#"):
            child_indent = _indent(s)
            break
    child_indent = child_indent or 2
    key_re = re.compile(rf"^ {{{child_indent}}}(?:{re.escape(key)}|{re.escape(json.dumps(key))}|'{re.escape(key)}'):(\s|$)")
    k_idx = next((j for j in range(p_idx + 1, end) if key_re.match(lines[j])), None)
    new_line = " " * child_indent + f"{yaml_key_text(key)}: {_flow(value)}\n"
    if k_idx is None:
        insert_at = end
        while insert_at > p_idx + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines.insert(insert_at, new_line)
    else:
        k_end = end
        for j in range(k_idx + 1, end):
            s = lines[j]
            if s.strip() and not s.lstrip().startswith("#") and _indent(s) <= child_indent:
                k_end = j
                break
        while k_end > k_idx + 1 and (not lines[k_end - 1].strip() or (lines[k_end - 1].lstrip().startswith("#") and _indent(lines[k_end - 1]) <= child_indent)):
            k_end -= 1
        comment = ""
        m = re.search(r"\s+#[^'\"]*$", lines[k_idx].rstrip("\n"))
        if m and k_end == k_idx + 1:
            comment = m.group(0)
        lines[k_idx:k_end] = [new_line.rstrip("\n") + comment + "\n"]
    new_text = "".join(lines)
    after = yaml.safe_load(new_text) or {}  # type: ignore[union-attr]
    expected = json.loads(json.dumps(before, default=str))
    expected.setdefault(parent, {})
    if expected[parent] is None:
        expected[parent] = {}
    expected[parent][key] = json.loads(json.dumps(value, default=str))
    if canonical_json(json.loads(json.dumps(after, default=str))) != canonical_json(expected):
        raise ScriptError(f"refusing to write {rel(path)}: the patch would change more than {parent}.{key}")
    path.write_text(new_text, encoding="utf-8")


def deep_merge(base: Any, update: Any) -> Any:
    if isinstance(base, dict) and isinstance(update, dict):
        out = dict(base)
        for k, v in update.items():
            out[k] = deep_merge(base.get(k), v) if k in base else v
        return out
    return update


# --------------------------------------------------------------------------------------------------------------- #
# The tracker (kit/tracker/backlog.yaml)
# --------------------------------------------------------------------------------------------------------------- #

# The row shape ./scripts/sdlc writes (REPO-DESIGN.md §6.5). kit/tracker/backlog.schema.json is the authority; when it
# exists every row is validated against it before the file is written.
ROW_KEYS = [
    "key", "title", "use_case", "library_seed_id", "mode", "owner", "tier", "phase", "status", "open_gate",
    "attempt", "target_date", "credit_estimate", "provider", "links", "prod_story_id", "live_since", "rev",
]
# Fields a specialist's tracker_row patch may set (git-owned, and not the lifecycle state itself).
ROW_PATCHABLE = {"title", "mode", "tier", "library_seed_id", "credit_estimate", "provider", "links", "target_date", "owner"}
# Fields only the lifecycle scripts change.
ROW_STATE = {"key", "phase", "status", "open_gate", "attempt", "rev", "prod_story_id", "live_since"}


class Tracker:
    def __init__(self, path: Path, text: str) -> None:
        need_yaml(path)
        self.path = path
        self.text = text
        try:
            self.data = yaml.safe_load(text) or {}  # type: ignore[union-attr]
        except yaml.YAMLError as exc:  # type: ignore[union-attr]
            raise ScriptError(f"{rel(path)} is not valid YAML: {str(exc).splitlines()[0]}") from None
        if not isinstance(self.data, dict):
            raise ScriptError(f"{rel(path)} must be a mapping with a `stories:` list")

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [r for r in (self.data.get("stories") or []) if isinstance(r, dict)]

    def row(self, slug: str) -> Optional[dict[str, Any]]:
        return next((r for r in self.rows if r.get("key") == slug), None)

    @property
    def wip_limit(self) -> Optional[int]:
        value = self.data.get("wip_limit_per_owner")
        return int(value) if isinstance(value, int) else None


def load_tracker(required: bool = True) -> Optional[Tracker]:
    path = rpath(TRACKER)
    if not path.exists():
        if required:
            raise ScriptError(
                f"{TRACKER} not found — the repo tracker (REPO-DESIGN.md §6.5, built by kit-data-and-dashboard, §15.4). "
                "In a customer repository it comes with the template."
            )
        return None
    return Tracker(path, path.read_text(encoding="utf-8"))


def tracker_at(ref: str) -> Optional[Tracker]:
    text = git_show(ref, TRACKER)
    if text is None:
        return None
    try:
        return Tracker(rpath(TRACKER), text)
    except ScriptError:
        return None


def require_row(tracker: Tracker, slug: str) -> dict[str, Any]:
    row = tracker.row(slug)
    if row is None:
        raise ScriptError(f"{slug!r} has no row in {TRACKER} (start one with ./scripts/sdlc intake, or the kickoff / add_use_case Page)")
    return row


def main_row(slug: str) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    ref = main_ref()
    if ref is None:
        return None, None
    t = tracker_at(ref)
    return ref, (t.row(slug) if t else None)


def next_rev(slug: str, working_row: Optional[dict[str, Any]]) -> int:
    """``main``'s rev + 1 for this row (1 for a row main does not have). Idempotent across writes on one branch."""
    ref, mrow = main_row(slug)
    if ref is not None:
        base = int((mrow or {}).get("rev") or 0) if mrow else 0
        return base + 1
    eprint(f"sdlc: no {MAIN_BRANCH} ref to compute rev from (not a git checkout, or {MAIN_BRANCH} unknown) — bumping the working-tree rev")
    return int((working_row or {}).get("rev") or 0) + 1


def validate_row(row: dict[str, Any]) -> list[str]:
    """Validate one row against the row schema in backlog.schema.json (items of `stories`), when it exists."""
    schema = load_schema(BACKLOG_SCHEMA)
    if not schema:
        return []
    row_schema = _find_row_schema(schema)
    if row_schema is None:
        return []
    return validate(row, row_schema, schema)


def _find_row_schema(schema: dict[str, Any]) -> Optional[Any]:
    stories = ((schema.get("properties") or {}).get("stories") or {})
    if isinstance(stories, dict):
        if "$ref" in stories:
            try:
                stories = _resolve_ref(stories["$ref"], schema)
            except ScriptError:
                return None
        items = stories.get("items") if isinstance(stories, dict) else None
        if items is not None:
            return items
    return None


def _row_block(lines: list[str], slug: str) -> Optional[tuple[int, int, int]]:
    """``(start, end, dash_indent)`` of a row's lines in the tracker text, or None."""
    key_re = re.compile(rf"^(\s*)-\s+key:\s*[\"']?{re.escape(slug)}[\"']?\s*(#.*)?$")
    for i, line in enumerate(lines):
        m = key_re.match(line.rstrip("\n"))
        if not m:
            continue
        dash = len(m.group(1))
        end = len(lines)
        for j in range(i + 1, len(lines)):
            s = lines[j]
            if not s.strip():
                continue
            if _indent(s) <= dash:
                end = j
                break
        while end > i + 1 and not lines[end - 1].strip():
            end -= 1
        return i, end, dash
    return None


def render_row(row: dict[str, Any], dash: int) -> list[str]:
    ordered = {k: row[k] for k in ROW_KEYS if k in row}
    for k, v in row.items():
        if k not in ordered:
            ordered[k] = v
    text = yaml.safe_dump(ordered, default_flow_style=None, sort_keys=False, width=10000, allow_unicode=True)  # type: ignore[union-attr]
    out = []
    for n, line in enumerate(text.splitlines()):
        prefix = " " * dash + ("- " if n == 0 else "  ")
        out.append(prefix + line + "\n")
    return out


def write_row(slug: str, row: dict[str, Any], *, tracker: Optional[Tracker] = None) -> None:
    """Rewrite one row (or append it) in kit/tracker/backlog.yaml; every other line stays byte for byte."""
    tracker = tracker or load_tracker()
    assert tracker is not None
    if row.get("key") != slug:
        raise ScriptError("internal: row key does not match the slug")
    problems = validate_row(row)
    if problems:
        raise ScriptError(f"the new row for {slug!r} does not validate against {BACKLOG_SCHEMA}: " + "; ".join(problems[:5]))
    lines = tracker.text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    block = _row_block(lines, slug)
    if block is not None:
        start, end, dash = block
        lines[start:end] = render_row(row, dash)
    else:
        s_idx = next((i for i, ln in enumerate(lines) if re.match(r"^stories:\s*(\[\s*\])?\s*(#.*)?$", ln.rstrip("\n"))), None)
        if s_idx is None:
            lines += ["stories:\n"] + render_row(row, 2)
        else:
            if "[" in lines[s_idx]:
                lines[s_idx] = "stories:\n"
            end = len(lines)
            for j in range(s_idx + 1, len(lines)):
                s = lines[j]
                if s.strip() and not s.lstrip().startswith("#") and _indent(s) == 0:
                    end = j
                    break
            while end > s_idx + 1 and not lines[end - 1].strip():
                end -= 1
            dash = 2
            for j in range(s_idx + 1, end):
                m = re.match(r"^(\s*)-\s", lines[j])
                if m:
                    dash = len(m.group(1))
                    break
            lines[end:end] = render_row(row, dash)
    new_text = "".join(lines)
    new = Tracker(tracker.path, new_text)
    others_before = [r for r in tracker.rows if r.get("key") != slug]
    others_after = [r for r in new.rows if r.get("key") != slug]
    if canonical_json(json.loads(json.dumps(others_before, default=str))) != canonical_json(json.loads(json.dumps(others_after, default=str))):
        raise ScriptError(f"refusing to write {TRACKER}: the edit would change another story's row")
    if {k: v for k, v in new.data.items() if k != "stories"} != {k: v for k, v in tracker.data.items() if k != "stories"}:
        raise ScriptError(f"refusing to write {TRACKER}: the edit would change a top-level key")
    written = new.row(slug)
    if canonical_json(json.loads(json.dumps(written, default=str))) != canonical_json(json.loads(json.dumps(row, default=str))):
        raise ScriptError(f"refusing to write {TRACKER}: the row did not round-trip")
    tracker.path.write_text(new_text, encoding="utf-8")
    tracker.text = new_text
    tracker.data = new.data


# --------------------------------------------------------------------------------------------------------------- #
# Events (sdlc/work/<slug>/events.jsonl) — append-only
# --------------------------------------------------------------------------------------------------------------- #

EVENT_KEYS = [
    "ts", "story_key", "event_type", "from_phase", "to_phase", "gate", "decision", "actor", "actor_kind", "agent",
    "model_tier", "model_reported", "turns", "credits_used", "summary", "refs", "tracker_rev", "sha",
]


def events_path(slug: str) -> Path:
    return work_dir(slug) / "events.jsonl"


def read_events(slug: str, path: Optional[Path] = None) -> list[dict[str, Any]]:
    path = path or events_path(slug)
    if not path.is_file():
        return []
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            raise ScriptError(f"{rel(path)}:{n} is not valid JSON (events are append-only; correct with a new event, never by editing)") from None
        if isinstance(obj, dict):
            out.append(obj)
    return out


def make_event(slug: str, event_type: str, *, actor: str, actor_kind: str, summary: str, tracker_rev: int, **fields: Any) -> dict[str, Any]:
    event: dict[str, Any] = {k: None for k in EVENT_KEYS}
    event.update(
        ts=fields.pop("ts", None) or utc_now(),
        story_key=slug,
        event_type=event_type,
        actor=actor,
        actor_kind=actor_kind,
        summary=truncate(summary, 1500),
        refs=list(fields.pop("refs", None) or []),
        tracker_rev=int(tracker_rev),
    )
    for k, v in fields.items():
        if k not in event:
            raise ScriptError(f"internal: unknown event key {k!r}")
        event[k] = v
    if event.get("sha") in ("", None):
        event["sha"] = None
    return event


def validate_event(event: dict[str, Any]) -> list[str]:
    schema = load_schema(EVENT_SCHEMA, from_config=True)
    if not schema:
        return [f"{EVENT_SCHEMA} not found"]
    errors = validate(event, schema)
    for key in ("summary", "actor"):
        value = str(event.get(key) or "")
        if looks_like_secret(value):
            errors.append(f"{key}: looks like it carries a secret")
        for m in EMAIL_RE.finditer(value):
            if not is_placeholder_email(m.group(0)):
                errors.append(f"{key}: carries an email address (roles only)")
    return errors


def append_event(slug: str, event: dict[str, Any]) -> dict[str, Any]:
    errors = validate_event(event)
    if errors:
        raise ScriptError("the event does not validate against the event schema: " + "; ".join(errors[:5]))
    path = events_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    prefix = "" if (not existing or existing.endswith("\n")) else "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(prefix + json.dumps(event, ensure_ascii=False) + "\n")
    return event


# --------------------------------------------------------------------------------------------------------------- #
# Tenant config, catalog
# --------------------------------------------------------------------------------------------------------------- #

ENTITLEMENT_NAMES = ["pages", "apps", "cases", "records", "ai_agent_action", "change_control", "tunnel"]


def load_tenant_config() -> Optional[dict[str, Any]]:
    data = read_yaml(rpath(TENANT_CONFIG), required=False)
    return data if isinstance(data, dict) else None


def _lookup(config: dict[str, Any], *names: str) -> Any:
    for name in names:
        node: Any = config
        ok = True
        for part in name.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                ok = False
                break
        if ok:
            return node
    return None


def entitlements(config: Optional[dict[str, Any]]) -> dict[str, Optional[bool]]:
    """Entitlements from kit/tenant/config.yaml: ``entitlements.<name>`` or the Page's ``ent_<name>`` keys."""
    out: dict[str, Optional[bool]] = {}
    for name in ENTITLEMENT_NAMES:
        if not config:
            out[name] = None
            continue
        value = _lookup(config, f"entitlements.{name}", f"entitlements.ent_{name}", f"ent_{name}", name)
        out[name] = bool(value) if isinstance(value, bool) else None
    return out


def plan_tier(config: Optional[dict[str, Any]]) -> Optional[str]:
    if not config:
        return None
    value = _lookup(config, "plan_tier", "plan.tier", "plan")
    return str(value) if isinstance(value, str) else None


def llm_choice(config: Optional[dict[str, Any]]) -> Optional[str]:
    if not config:
        return None
    value = _lookup(config, "llm_choice", "llm.choice", "ai.llm_choice")
    return str(value) if isinstance(value, str) else None


def community_path(config: Optional[dict[str, Any]]) -> bool:
    """True on the Community path: Community Edition, or no Records entitlement (the manual path, §1.4)."""
    ent = entitlements(config)
    return plan_tier(config) == "community_edition" or ent.get("records") is False


def records_entitled(config: Optional[dict[str, Any]]) -> Optional[bool]:
    if not config:
        return None
    if plan_tier(config) == "community_edition":
        return False
    return entitlements(config).get("records")


def runtime_specialists_enabled(config: Optional[dict[str, Any]]) -> bool:
    ent = entitlements(config)
    return bool(ent.get("records")) and bool(ent.get("ai_agent_action")) and plan_tier(config) != "community_edition"


def catalog_ids() -> Optional[set[int]]:
    """Library ids from kit/catalog/library-seeds.yaml (None when the file does not exist yet)."""
    data = read_yaml(rpath(CATALOG_SEEDS), required=False)
    if data is None:
        return None
    ids: set[int] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("id", "library_id", "seed_id") and isinstance(v, (int, str)) and str(v).isdigit():
                    ids.add(int(v))
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return ids


# --------------------------------------------------------------------------------------------------------------- #
# Local state (.sdlc/)
# --------------------------------------------------------------------------------------------------------------- #


def out_dir(slug: str) -> Path:
    return rpath(f"{OUT_DIR}/{slug}")


def read_active() -> Optional[str]:
    path = rpath(ACTIVE_FILE)
    if not path.is_file():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value if SLUG_RE.match(value) else None


def write_active(slug: str) -> None:
    path = rpath(ACTIVE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(slug + "\n", encoding="utf-8")


def latest_qa_result(slug: str) -> Optional[dict[str, Any]]:
    """The newest ``.sdlc/out/<slug>/qa-*.json`` written by eval-run."""
    d = out_dir(slug)
    files = sorted(d.glob("qa-*.json")) if d.is_dir() else []
    for f in reversed(files):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            data["_file"] = rel(f)
            return data
    return None


# --------------------------------------------------------------------------------------------------------------- #
# Derived state
# --------------------------------------------------------------------------------------------------------------- #


def operate_status(slug: str, contract: Optional[dict[str, Any]], events: list[dict[str, Any]]) -> str:
    """The operate status a story holds: live after a G6 go_live (or with no side effects), else shadow."""
    last_entry = None
    for i, e in enumerate(events):
        if e.get("to_phase") == "operate" and e.get("from_phase") == "ship":
            last_entry = i
    g6 = [
        e for e in events[(last_entry or 0):]
        if e.get("event_type") == "gate_decision" and e.get("gate") == "G6"
    ]
    if g6:
        return "live" if g6[-1].get("decision") == "go_live" else "shadow"
    side_effects = bool(((contract or {}).get("risk") or {}).get("side_effects"))
    return "shadow" if side_effects else "live"


def previous_phase_before_parked(events: list[dict[str, Any]], default: str = "intake") -> str:
    for e in reversed(events):
        if e.get("to_phase") == "parked" and e.get("from_phase"):
            return str(e["from_phase"])
    return default


__all__ = [name for name in dir() if not name.startswith("_") or name in ("_resolve_ref",)]
