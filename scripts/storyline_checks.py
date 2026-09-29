#!/usr/bin/env python3
"""``./scripts/storyline check [--all]`` — the contract-checker registry: named invariants, one PASS/FAIL line each.

Spec: REPO-DESIGN.md §6.1 (the registry), §13 row 17 (template_hygiene), §15.6 (release_not_skeleton), §8.2
(resources_in_sync), §15.1 (what storyline.yml enforces on a PR). ``storyline/examples/`` is excluded from the tracker invariants.

Usage
-----
  ./scripts/storyline check [--all] [--strict] [NAME ...]         the registry (default: every check below except the two
                                                               mode-bound ones)
  ./scripts/storyline check --release                              + release_not_skeleton; every SKIP becomes a FAIL (§15.6)
  ./scripts/storyline check resources_in_sync --snapshot FILE      on the nightly snapshot (tracker-pull.yml)
  ./scripts/storyline check --pr --base SHA --branch NAME [--pr-json FILE]
                                                              the pull-request checks storyline.yml runs (below)

A check reports ``SKIP`` when an input it needs does not exist yet. When that input is a path the REPO-DESIGN.md §2 tree
plans (another builder's file, §15), the SKIP says ``planned``; ``--strict`` (storyline.yml) and ``--release`` turn every such
SKIP into a FAIL. A SKIP that is merely not applicable (``resources_in_sync`` without a snapshot) never fails.

The registry
------------
phase_enum_in_sync          state-machine.yaml is the single source of phase, status and gate names. Checked against:
                            its own gate_info / phase_info / instruments / transitions / checks; dispatch-rules.yaml;
                            storyline/observability/event.schema.json; every enum in storyline/templates/*.schema.json that names
                            phases, statuses or gates; kit/tracker/backlog.schema.json (phase, status, open_gate);
                            the TEXT_ENUM values of kit/records/storyline_backlog|storyline_events.record-type.json; and the
                            storyline_state_machine Resource (kit/resources/storyline_state_machine.example.json)
tracker_schema_valid        kit/tracker/backlog.yaml and milestones.yaml against their schemas, plus the invariants:
                            unique kebab-case keys, phase/status pairs allowed by phase_info, open_gate a gate or none,
                            awaiting_gate ⇒ a gate open, blocked ⇒ GX, parked ⇒ GB, attempt 0..rework_cap, rev ≥ 0,
                            WIP ≤ wip_limit_per_owner, and every storyline/work/<slug>/ has a row
field_map_complete          kit/tracker/field-map.yaml maps every field of the three Record types (REPO-DESIGN.md §8.1,
                            with its result_type) and every key of a backlog row; owner ∈ git | tines | tines-only; the
                            kit/records/*.record-type.json bodies carry the same fields and types
touch_sets_resolve          every glob in touch-sets.yaml is well formed; every phase, agent, patch, set and script it
                            names exists; each agent's globs sit inside its phase's; branch patterns parse
contracts_valid_json_schema every *.schema.json the lifecycle uses is a well-formed schema (local $refs resolve; with the
                            jsonschema package installed, also the 2020-12 meta-schema); the per-agent contracts carry
                            $defs.input and $defs.output; and the artifacts validate against them: every events.jsonl
                            line, every verify-report.json, every design.md contract block (storyline/work/ and storyline/examples/)
bundle_fresh                kit/bundle/kit-bundle.json (and the generated kit/resources/*.example.json) equal what
                            ``./scripts/kit bundle`` generates now: ``kit_bundle.py --check`` (0 fresh, 1 stale), or — for
                            a generator without --check — the generator run in a scratch copy of the tree. The generator
                            is the one beside this file (the BASE branch's in storyline.yml), never the PR's own
catalog_ids_verified        every Library id cited — starter stories, tracker rows, discovery and intake front matter,
                            ``tines.com/library/stories/<id>`` links — is in kit/catalog/library-seeds.yaml
doc_links_resolve           relative Markdown links in the lifecycle and kit documentation resolve (a missing target the
                            §2 tree plans is a SKIP, not a FAIL)
env_example_matches_reads   every environment variable the lifecycle and kit scripts and phase-gate.sh read is named in
                            .env.example — except the platform's own and the CI-only tracker URLs (§3.3 row 5)
agents_frontmatter_valid    .claude/agents/*.md (the §5.1/§5.3 tools, disallowedTools, maxTurns; model: inherit; no
                            mcpServers or memory on a new crew member), .claude/skills/*/SKILL.md (name = folder; the
                            side-effecting skills set disable-model-invocation), .cursor/rules/storyline*.mdc (description,
                            alwaysApply: false, no globs), tines-skills/*/SKILL.md (name = folder, description ≤ 1,024)
template_hygiene            §13 row 17: no *.tines.com host other than <your-tenant> (and the public www / oci hosts), no
                            email outside *.example.invalid, every id 0 in the template's placeholder files, and no Webhook
                            path or secret in stories/kit-launch/story.json that is not empty or a placeholder. In a
                            provisioned repository (kit/tenant/config.yaml exists) the id rule does not apply
release_not_skeleton        (--release only) stories/kit-launch/story.json and the dashboard export carry no SKELETON
resources_in_sync           (--snapshot only) kit_state.hash_<name> from the nightly snapshot equals the hash of each
                            Resource generated from main (storyline_common.resource_hash over kit/bundle/kit-bundle.json)

The pull-request checks (``--pr``; rules read from ``--config-root``, the BASE branch in storyline.yml)
  pr_touch_set          the diff sits inside the touch set of its branch prefix (touch-sets.yaml ``branches``); a branch
                        that matches no prefix may not touch ``protected`` paths; patch files change only in their
                        allow-listed paths
  pr_tracker_rev        every tracker row the PR changes has rev = main's rev + 1 (1 for a new row)
  pr_events_append_only every events.jsonl only gains lines, and each new line validates against the event schema
  pr_tracker_transitions every new tracker row is intake/active/none with attempt 0; every changed row's (phase, status,
                        open_gate) is a legal state reached by a transition of state-machine.yaml, recorded by a
                        transition, gate_decision (human), budget or escalation event added in the same PR
  pr_build_on_main      a story/<slug>/* PR needs the row on main in build
  pr_design_ready       a design/<slug> PR passes ./scripts/storyline ready (G1, GB)
  pr_cost_checks        a G4 PR (story/<slug>/* whose row goes to ship) passes ./scripts/storyline estimate --check
  pr_qa_line            a G4 PR body carries "QA verification: pass · by <role>"
  pr_gate_approvers     every gate_decision event the PR adds has an approving review, on the head commit, from someone
                        who is not the PR author — one per team listed in storyline/gates/approvers.yaml (require: all), at
                        least one (require: any); a gate with event_allowed: false fails. A review that names no commit
                        oid is not counted. Team membership itself is not read (no team-membership endpoint is named in
                        REPO-DESIGN.md): CODEOWNERS gives storyline/work/*/events.jsonl and storyline/work/*/ship.md to
                        security-platform, so branch protection's code-owner review holds the team for every added
                        event — VERIFY that "Require review from Code Owners" is on
  pr_skill_held_out     a PR that changes tines-skills/<name>/ needs storyline/evals/skills/<name>.cases.yaml

The field-map shape this check reads (kit/tracker/field-map.yaml, written by kit-data-and-dashboard): a mapping whose
keys include the Record type names ``storyline_backlog``, ``storyline_events``, ``storyline_milestones`` (at the top level or under one
wrapper key); under each, either a list of entries or a mapping ``<yaml key>: {entry}``. An entry names the YAML key
(``yaml`` | ``yaml_key`` | ``key``), the Record field (``record`` | ``record_field`` | ``field``; null when the key is not
mirrored), the ``result_type`` and the ``owner`` (``git`` | ``tines`` | ``tines-only``).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import storyline_common as C  # noqa: E402
from storyline_common import ScriptError  # noqa: E402
from tines_common import EMAIL_RE  # noqa: E402
from tines_common import ScriptError as BaseScriptError  # noqa: E402

PLANNED_ENV = {"STORYLINE_ENFORCE": "REPO-DESIGN.md §3.3 row 5 (.env.example)"}
CI_ONLY_ENV = {"TRACKER_SYNC_URL", "TRACKER_OUTBOX_URL"}  # §3.3 row 5: they never reach a laptop, so never .env.example
PLATFORM_ENV_RE = re.compile(r"^(GITHUB_|RUNNER_|ACTIONS_|BASH_|CLAUDE_)|^(CI|HOME|PATH|PWD|OLDPWD|TMPDIR|IFS|PYTHON|SHELL|USER|LANG|TERM|RANDOM|LINENO|OSTYPE|SECONDS|EPOCHSECONDS)$")
PUBLIC_TINES_HOSTS = {"www", "oci"}
SKIP_DIRS = {".git", ".storyline", ".tines", "__pycache__", "node_modules", ".terraform", ".venv", "venv"}
TEXT_SUFFIXES = {".md", ".mdc", ".yml", ".yaml", ".json", ".jsonl", ".py", ".sh", ".tf", ".jq", ".txt", ".ts", ".tsx", ".js", ".jsx", ".toml", ".example", ""}

# REPO-DESIGN.md §8.1 — the Record fields and their result_types.
RECORD_FIELDS: dict[str, dict[str, str]] = {
    "storyline_backlog": {
        "story_key": "TEXT", "title": "TEXT", "use_case": "ARTIFACT", "library_seed_id": "NUMBER", "mode": "TEXT_ENUM", "owner": "TEXT",
        "tier": "TEXT_ENUM", "phase": "TEXT_ENUM", "status": "TEXT_ENUM", "open_gate": "TEXT_ENUM", "attempt": "NUMBER",
        "target_date": "TIMESTAMP", "credit_estimate_monthly": "NUMBER", "credit_estimate_basis": "TEXT", "provider": "TEXT_ENUM",
        "prod_story_id": "NUMBER", "live_since": "TIMESTAMP", "design_pr": "TEXT", "build_pr": "TEXT", "change_request_id": "TEXT",
        "rev": "NUMBER", "pending_repo_sync": "BOOLEAN", "pending_base_rev": "NUMBER", "outbox_seq": "NUMBER", "acked_seq": "NUMBER",
        "specialist_due": "TEXT_ENUM", "specialist_status": "TEXT_ENUM", "proposal": "JSON", "brief": "ARTIFACT", "retro": "ARTIFACT",
        "last_actor": "TEXT", "last_transition_at": "TIMESTAMP",
    },
    "storyline_events": {
        "story_key": "TEXT", "event_type": "TEXT_ENUM", "from_phase": "TEXT_ENUM", "to_phase": "TEXT_ENUM", "gate": "TEXT_ENUM",
        "decision": "TEXT", "actor": "TEXT", "actor_ref": "TEXT", "actor_kind": "TEXT_ENUM", "agent": "TEXT", "model": "TEXT",
        "credits_used": "NUMBER", "input_tokens": "NUMBER", "output_tokens": "NUMBER", "summary": "TEXT", "ref": "TEXT",
        "tracker_rev": "NUMBER", "source_sha": "TEXT",
    },
    "storyline_milestones": {
        "milestone_id": "TEXT_ENUM", "title": "TEXT", "criteria": "ARTIFACT", "status": "TEXT_ENUM", "due_date": "TIMESTAMP",
        "evidence_ref": "TEXT", "owner": "TEXT", "rev": "NUMBER", "pending_repo_sync": "BOOLEAN",
    },
}
RESULT_TYPES = {"TEXT", "NUMBER", "TIMESTAMP", "BOOLEAN", "TEXT_ENUM", "JSON", "ARTIFACT"}

# REPO-DESIGN.md §5.1 / §5.3 — the new IDE crew's frontmatter.
EXPECTED_AGENTS: dict[str, dict[str, Any]] = {
    "story-scout": {"tools": ["Read", "Grep", "Glob", "WebFetch", "Bash(./scripts/tines live-activity *)"], "disallowed": ["Write", "Edit"], "maxTurns": 20},
    "story-architect": {"tools": ["Read", "Grep", "Glob", "Bash(./scripts/storyline estimate *)"], "disallowed": ["Write", "Edit"], "maxTurns": 25},
    "eval-author": {"tools": ["Read", "Grep", "Glob"], "disallowed": ["Write", "Edit", "Bash"], "maxTurns": 15},
    "security-reviewer": {"tools": ["Read", "Grep", "Glob", "Bash(./scripts/lint-story.sh *)", "Bash(./scripts/diff-story.sh *)"], "disallowed": ["Write", "Edit"], "maxTurns": 15},
    "story-qa": {"tools": ["Read", "Grep", "Glob", "Bash(./scripts/storyline eval-run *)", "Bash(./scripts/tines runs *)", "Bash(./scripts/tines action-logs *)"], "disallowed": ["Write", "Edit"], "maxTurns": 20},
    "eval-curator": {"tools": ["Read", "Grep", "Glob"], "disallowed": ["Write", "Edit", "Bash"], "maxTurns": 15},
    "skill-curator": {"tools": ["Read", "Grep", "Glob"], "disallowed": ["Write", "Edit", "Bash"], "maxTurns": 15},
}
FORBIDDEN_TOOL_RE = re.compile(r"^Bash\((yq|jq|git diff|\./scripts/tines ai-usage)\b")   # write files, print the environment, or bypass storyline estimate
HUMAN_ONLY_SKILLS = ("storyline-gate", "tines-ship", "tines-rollback", "tines-export")
CURSOR_RULES = ["storyline", "storyline-story-scout", "storyline-story-architect", "storyline-eval-author", "storyline-tines-builder", "storyline-tines-reviewer",
                "storyline-security-reviewer", "storyline-story-qa", "storyline-eval-curator", "storyline-skill-curator"]


class Result:
    def __init__(self, name: str) -> None:
        self.name = name
        self.fails: list[str] = []
        self.planned: list[str] = []
        self.notes: list[str] = []
        self.na: Optional[str] = None
        self.summary = ""

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def plan(self, path: str, why: str = "") -> None:
        self.planned.append(f"{path}{' — ' + why if why else ''}")

    @property
    def status(self) -> str:
        if self.fails:
            return "FAIL"
        if self.na or self.planned:
            return "SKIP"
        return "PASS"


# --------------------------------------------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------------------------------------------- #

_PLANNED: Optional[set[str]] = None


def planned_paths() -> set[str]:
    """Every path the REPO-DESIGN.md §2 tree names (files and folders)."""
    global _PLANNED
    if _PLANNED is not None:
        return _PLANNED
    out: set[str] = set()
    path = C.rpath(C.REPO_DESIGN)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        m = re.search(r"## 2\. The final repository tree.*?```\n(.*?)\n```", text, re.S)
        if m:
            stack: list[str] = []
            for line in m.group(1).splitlines():
                idx = max(line.find("├── "), line.find("└── "))
                if idx < 0:
                    continue
                depth = idx // 4
                name = line[idx + 4:].split("  #")[0].split(" #")[0].strip()
                if not name or any(ch in name for ch in ",{}*…") or " " in name.strip("/"):
                    continue
                is_dir = name.endswith("/")
                name = name.rstrip("/")
                stack = stack[:depth]
                full = "/".join(stack + [name])
                out.add(full)
                if "/" in name:
                    parts = full.split("/")
                    for i in range(1, len(parts)):
                        out.add("/".join(parts[:i]))
                if is_dir:
                    stack.append(name)
                else:
                    stack.append(name)
    _PLANNED = out
    return out


def is_planned(relpath: str) -> bool:
    return relpath.rstrip("/") in planned_paths()


def need(res: Result, relpath: str) -> Optional[Path]:
    """The path if it exists; otherwise record a planned SKIP (or a FAIL when the §2 tree does not plan it)."""
    p = C.rpath(relpath)
    if p.exists():
        return p
    if is_planned(relpath):
        res.plan(relpath, "planned in REPO-DESIGN.md §2, not present yet")
    else:
        res.fail(f"{relpath} does not exist")
    return None


def repo_files() -> list[str]:
    root = C.repo_root()
    if C.in_git():
        p = C.git("ls-files", "--cached", "--others", "--exclude-standard")
        if p.returncode == 0:
            return sorted(f for f in p.stdout.splitlines() if f and not any(part in SKIP_DIRS for part in f.split("/")) and (root / f).is_file())
    out = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        out.append(str(rel))
    return sorted(out)


def text_of(relpath: str) -> Optional[str]:
    p = C.rpath(relpath)
    if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in (".gitignore", "CODEOWNERS", "tines", "storyline", "kit"):
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def enum_values(values: Any) -> list[Any]:
    out = []
    for v in values or []:
        if isinstance(v, dict):
            v = v.get("value", v.get("name"))
        out.append(v)
    return out


def find_record_field(doc: Any, field: str) -> Optional[dict[str, Any]]:
    """A field object named ``field`` in a record-type body (the exact key for the field name is VERIFY K16)."""
    found = None

    def walk(node: Any) -> None:
        nonlocal found
        if found is not None:
            return
        if isinstance(node, dict):
            if any(node.get(k) == field for k in ("name", "field_name", "key", "title")) and any(k in node for k in ("result_type", "type", "fixed_values")):
                found = node
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return found


def record_fields(doc: Any) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            name = next((node.get(k) for k in ("name", "field_name", "key") if isinstance(node.get(k), str)), None)
            rtype = node.get("result_type") or node.get("type")
            if name and isinstance(rtype, str) and rtype.upper() in RESULT_TYPES:
                out[name] = rtype.upper()
                return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return out


def fixed_values(field: dict[str, Any]) -> Optional[list[Any]]:
    for key in ("fixed_values", "values", "enum", "options"):
        if isinstance(field.get(key), list):
            return enum_values(field[key])
    return None


def schema_enum(schema: Any, prop: str) -> Optional[list[Any]]:
    """The enum of the first property named ``prop`` found anywhere in a schema (following local $refs)."""
    found: list[Any] = []

    def walk(node: Any, depth: int = 0) -> None:
        if found or depth > 40:
            return
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict) and isinstance(props.get(prop), dict):
                target = props[prop]
                if "$ref" in target:
                    try:
                        target = C._resolve_ref(target["$ref"], schema)
                    except ScriptError:
                        target = {}
                if isinstance(target, dict) and isinstance(target.get("enum"), list):
                    found.append(target["enum"])
                    return
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node:
                walk(v, depth + 1)

    walk(schema)
    return found[0] if found else None


def same_set(a: list[Any], b: list[Any]) -> bool:
    return set(x for x in a if x is not None) == set(x for x in b if x is not None)


def load_json_or_fail(res: Result, relpath: str) -> Optional[Any]:
    p = need(res, relpath)
    if p is None:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        res.fail(f"{relpath}: not valid JSON ({exc})")
        return None


def load_yaml_or_fail(res: Result, relpath: str) -> Optional[Any]:
    p = need(res, relpath)
    if p is None:
        return None
    try:
        return C.yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — any YAML error is the finding
        res.fail(f"{relpath}: not valid YAML ({str(exc).splitlines()[0]})")
        return None


def kit_helper(module: str, name: str) -> Optional[Callable[..., Any]]:
    """A check the kit's own scripts export for `storyline check` (scripts/kit_tracker.py, kit_bundle.py), so the two
    definitions never drift apart. None when the kit scripts are not in this checkout."""
    try:
        mod = __import__(module)
    except Exception:  # noqa: BLE001 — planned file, or a checkout without the kit
        return None
    fn = getattr(mod, name, None)
    return fn if callable(fn) else None


def add_kit_problems(res: Result, module: str, name: str, *args: Any) -> None:
    fn = kit_helper(module, name)
    if fn is None:
        return
    try:
        problems = fn(*args)
    except BaseScriptError as exc:
        problems = [f"{module}.{name}: {getattr(exc, 'message', None) or 'stopped'}"]
    except Exception as exc:  # noqa: BLE001 — report, do not crash the registry
        problems = [f"{module}.{name} raised {exc.__class__.__name__}: {exc}"]
    seen = set(res.fails)
    for p in problems or []:
        if p not in seen:
            res.fail(f"{p} ({module}.{name})")
            seen.add(p)


# --------------------------------------------------------------------------------------------------------------- #
# The registry
# --------------------------------------------------------------------------------------------------------------- #


def check_phase_enum_in_sync(res: Result) -> None:
    m = C.load_machine()
    P, S, G = m.all_phases, m.statuses, m.gates
    G_none = [m.open_gate_none, *G]
    if len(set(P)) != len(P) or not P:
        res.fail("phases/holding/terminal are empty or repeat a name")
    if set(m.gate_info) != set(G):
        res.fail(f"gate_info keys {sorted(m.gate_info)} ≠ gates {G}")
    if set(m.phase_info) != set(P):
        res.fail(f"phase_info keys {sorted(m.phase_info)} ≠ phases+holding+terminal {P}")
    for ph, info in m.phase_info.items():
        bad = [s for s in (info or {}).get("statuses") or [] if s not in S]
        if bad:
            res.fail(f"phase_info.{ph}.statuses has unknown statuses {bad}")
    for name, gates in m.instruments.items():
        bad = [g for g in gates if g not in G]
        if bad:
            res.fail(f"instruments.{name} names unknown gates {bad}")
    for i, t in enumerate(m.transitions):
        for end in ("from", "to"):
            v = t.get(end)
            if v not in P and v not in ("*", "$same", "$previous"):
                res.fail(f"transitions[{i}].{end} = {v!r} is not a phase")
        for g in ([t["gate"]] if t.get("gate") else []) + list(t.get("gates") or []):
            if g not in G:
                res.fail(f"transitions[{i}] names unknown gate {g!r}")
        if t.get("check") and t["check"] not in m.checks:
            res.fail(f"transitions[{i}].check {t['check']!r} is not under checks:")
        if t.get("decision") and t.get("gate") and t["decision"] not in m.decisions_for(t["gate"]):
            res.fail(f"transitions[{i}] decision {t['decision']!r} is not one of gate_info.{t['gate']}.decisions")
        st = t.get("status")
        if isinstance(st, str) and re.fullmatch(r"[a-z_]+", st) and st not in S:
            res.fail(f"transitions[{i}].status {st!r} is not a status")
    rules = C.load_rules()
    for i, r in enumerate(rules.get("rules") or []):
        for key, allowed in (("phase", P), ("status", S)):
            vals = r.get(key)
            for v in (vals if isinstance(vals, list) else [vals]):
                if v not in allowed and v != "*":
                    res.fail(f"dispatch-rules.yaml rules[{i}].{key} {v!r} is unknown")
        if r.get("gate") and r["gate"] not in G:
            res.fail(f"dispatch-rules.yaml rules[{i}].gate {r['gate']!r} is unknown")
    ev = C.load_schema(C.EVENT_SCHEMA, from_config=True)
    if ev is None:
        res.fail(f"{C.EVENT_SCHEMA} is missing")
    else:
        phases = ((ev.get("$defs") or {}).get("phase_or_null") or {}).get("enum") or []
        if not same_set(phases, P):
            res.fail(f"event.schema.json phase enum {sorted(x for x in phases if x)} ≠ {sorted(P)}")
        gates = ((ev.get("properties") or {}).get("gate") or {}).get("enum") or []
        if not same_set(gates, G):
            res.fail(f"event.schema.json gate enum ≠ gates {G}")
    for f in sorted(C.cpath(C.TEMPLATES_DIR).glob("*.schema.json")):
        schema = json.loads(f.read_text(encoding="utf-8"))

        def walk(node: Any, where: str) -> None:
            if isinstance(node, dict):
                enum = node.get("enum")
                if isinstance(enum, list):
                    vals = [v for v in enum if isinstance(v, str)]
                    if vals and all(re.fullmatch(r"G[0-9A-Z][a-z]?", v) for v in vals) and not set(vals) <= set(G):
                        res.fail(f"{f.name} {where}: gate enum {vals} has names outside the machine")
                for k, v in node.items():
                    if k in ("phase", "from_phase", "to_phase") and isinstance(v, dict) and isinstance(v.get("enum"), list):
                        if not set(x for x in v["enum"] if x is not None) <= set(P) | {m.open_gate_none}:
                            res.fail(f"{f.name} {where}.{k}: phase enum outside the machine")
                    if k == "status" and isinstance(v, dict) and isinstance(v.get("enum"), list) and set(v["enum"]) & set(S):
                        extra = set(v["enum"]) - set(S)
                        if extra and not set(v["enum"]) & {"pass", "PASS"}:
                            res.fail(f"{f.name} {where}.status: statuses outside the machine {sorted(extra)}")
                    walk(v, f"{where}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{where}[{i}]")

        walk(schema, "$")
    backlog_schema = load_json_or_fail(res, C.BACKLOG_SCHEMA)
    if backlog_schema is not None:
        for prop, want in (("phase", P), ("status", S), ("open_gate", G_none)):
            got = schema_enum(backlog_schema, prop)
            if got is None:
                res.fail(f"{C.BACKLOG_SCHEMA}: no enum for {prop}")
            elif not same_set(got, want):
                res.fail(f"{C.BACKLOG_SCHEMA}: {prop} enum {sorted(map(str, got))} ≠ {sorted(want)}")
    for rt, fields in (("storyline_backlog", (("phase", P), ("status", S), ("open_gate", G_none))),
                       ("storyline_events", (("from_phase", P + ["none"]), ("to_phase", P + ["none"]), ("gate", G_none)))):
        doc = load_json_or_fail(res, f"kit/records/{rt}.record-type.json")
        if doc is None:
            continue
        for fname, want in fields:
            f = find_record_field(doc, fname)
            vals = fixed_values(f) if f else None
            if vals is None:
                res.fail(f"kit/records/{rt}.record-type.json: no fixed values for {fname}")
            elif not same_set(vals, want):
                res.fail(f"kit/records/{rt}.record-type.json: {fname} values {sorted(map(str, vals))} ≠ {sorted(want)}")
    resource = load_json_or_fail(res, "kit/resources/storyline_state_machine.example.json")
    if resource is not None:
        node = resource.get("value", resource) if isinstance(resource, dict) else {}
        phases = list(node.get("phases") or []) + list(node.get("holding") or []) + list(node.get("terminal") or [])
        if not same_set(phases, P):
            res.fail("kit/resources/storyline_state_machine.example.json: phases ≠ state-machine.yaml (run ./scripts/kit bundle)")
        if not same_set(node.get("statuses") or [], S) or not same_set(node.get("gates") or [], G):
            res.fail("kit/resources/storyline_state_machine.example.json: statuses or gates ≠ state-machine.yaml (run ./scripts/kit bundle)")
    res.summary = f"{len(P)} phases, {len(S)} statuses, {len(G)} gates"


def check_tracker_schema_valid(res: Result) -> None:
    m = C.load_machine()
    work = C.rpath(C.WORK_DIR)
    folders = sorted(p.name for p in work.iterdir() if p.is_dir()) if work.is_dir() else []
    tracker_path = C.rpath(C.TRACKER)
    if not tracker_path.exists():
        if folders:
            res.fail(f"{C.TRACKER} is missing but storyline/work/ holds {folders}")
        else:
            need(res, C.TRACKER)
        return
    data = load_yaml_or_fail(res, C.TRACKER)
    if data is None:
        return
    schema = load_json_or_fail(res, C.BACKLOG_SCHEMA)
    if schema is not None:
        for e in C.validate(data, schema)[:10]:
            res.fail(f"{C.TRACKER}: {e}")
    rows = [r for r in (data.get("stories") or []) if isinstance(r, dict)] if isinstance(data, dict) else []
    keys = [str(r.get("key")) for r in rows]
    for k in {k for k in keys if keys.count(k) > 1}:
        res.fail(f"duplicate key {k!r}")
    cap = m.cap("rework_cap", 3)
    for r in rows:
        k = str(r.get("key"))
        if not C.SLUG_RE.match(k):
            res.fail(f"{k!r}: not a kebab-case key")
        ph, st, gate = str(r.get("phase")), str(r.get("status")), str(r.get("open_gate") or m.open_gate_none)
        if ph not in m.all_phases:
            res.fail(f"{k}: phase {ph!r} is not in the machine")
            continue
        if st not in m.statuses_for(ph):
            res.fail(f"{k}: status {st!r} is not allowed in {ph}")
        if gate not in [m.open_gate_none, *m.gates]:
            res.fail(f"{k}: open_gate {gate!r} is not a gate")
        if st == "awaiting_gate" and gate == m.open_gate_none:
            res.fail(f"{k}: awaiting_gate with no open gate")
        if st == "blocked" and gate != "GX":
            res.fail(f"{k}: blocked without GX open")
        if ph == "parked" and gate != "GB":
            res.fail(f"{k}: parked without GB open")
        att = r.get("attempt")
        if not isinstance(att, int) or not 0 <= att <= cap:
            res.fail(f"{k}: attempt {att!r} outside 0..{cap}")
        if not isinstance(r.get("rev"), int) or r["rev"] < 0:
            res.fail(f"{k}: rev must be a non-negative integer")
    limit = data.get("wip_limit_per_owner") if isinstance(data.get("wip_limit_per_owner"), int) else m.cap("wip_limit_per_owner", 1)
    owners: dict[str, list[str]] = {}
    for r in rows:
        if r.get("phase") in ("build", "verify"):
            owners.setdefault(str(r.get("owner")), []).append(str(r.get("key")))
    for owner, ks in owners.items():
        if len(ks) > limit:
            res.fail(f"WIP: owner {owner} has {len(ks)} stories in build or verify {ks} (limit {limit})")
    for f in folders:
        if f not in keys:
            res.fail(f"storyline/work/{f}/ has no tracker row")
    add_kit_problems(res, "kit_tracker", "tracker_problems", C.repo_root())
    if C.rpath(C.MILESTONES).exists() or is_planned(C.MILESTONES):
        mdata = load_yaml_or_fail(res, C.MILESTONES)
        mschema = load_json_or_fail(res, C.MILESTONES_SCHEMA)
        if mdata is not None and mschema is not None:
            for e in C.validate(mdata, mschema)[:10]:
                res.fail(f"{C.MILESTONES}: {e}")
    res.summary = f"{len(rows)} rows"


def collect_field_map(doc: Any) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}

    def entries_of(node: Any) -> list[dict[str, Any]]:
        items = []
        if isinstance(node, dict) and "fields" in node:
            node = node["fields"]
        if isinstance(node, list):
            items = [e for e in node if isinstance(e, dict)]
        elif isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, dict):
                    items.append({"yaml": k, **v})
        norm = []
        for e in items:
            norm.append({
                "yaml": e.get("yaml", e.get("yaml_key", e.get("key"))),
                "record": e.get("record", e.get("record_field", e.get("field"))),
                "result_type": e.get("result_type", e.get("type")),
                "owner": e.get("owner", e.get("owner_side", e.get("side"))),
            })
        return norm

    def walk(node: Any, depth: int = 0) -> None:
        if not isinstance(node, dict) or depth > 2:
            return
        for k, v in node.items():
            if k in RECORD_FIELDS:
                out[k] = entries_of(v)
            else:
                walk(v, depth + 1)

    walk(doc)
    return out


def check_field_map_complete(res: Result) -> None:
    for rt, fields in RECORD_FIELDS.items():
        doc = load_json_or_fail(res, f"kit/records/{rt}.record-type.json")
        if doc is None:
            continue
        have = record_fields(doc)
        missing = [f for f in fields if f not in have]
        wrong = [f"{f} {have[f]}≠{t}" for f, t in fields.items() if f in have and have[f] != t]
        if missing:
            res.fail(f"kit/records/{rt}.record-type.json lacks §8.1 fields {missing}")
        if wrong:
            res.fail(f"kit/records/{rt}.record-type.json result_type differs from §8.1: {wrong}")
        if len(have) > 50:
            res.fail(f"kit/records/{rt}.record-type.json has {len(have)} fields (the limit is 50)")
    doc = load_yaml_or_fail(res, C.FIELD_MAP)
    if doc is None:
        return
    fm = collect_field_map(doc)
    for rt, fields in RECORD_FIELDS.items():
        entries = fm.get(rt)
        if entries is None:
            res.fail(f"{C.FIELD_MAP}: no section for {rt}")
            continue
        mapped = {str(e["record"]): e for e in entries if e.get("record")}
        for f, t in fields.items():
            e = mapped.get(f)
            if e is None:
                res.fail(f"{C.FIELD_MAP} {rt}: field {f} is not mapped")
            elif str(e.get("result_type") or "").upper() != t:
                res.fail(f"{C.FIELD_MAP} {rt}.{f}: result_type {e.get('result_type')!r} ≠ {t}")
        for e in entries:
            if e.get("owner") not in ("git", "tines", "tines-only"):
                res.fail(f"{C.FIELD_MAP} {rt}: {e.get('yaml') or e.get('record')} owner {e.get('owner')!r} (git | tines | tines-only)")
            if e.get("record") and str(e["record"]) not in fields:
                res.fail(f"{C.FIELD_MAP} {rt}: maps unknown Record field {e['record']!r}")
    schema = C.load_schema(C.BACKLOG_SCHEMA)
    row_schema = C._find_row_schema(schema) if schema else None
    if isinstance(row_schema, dict) and "$ref" in row_schema:
        row_schema = C._resolve_ref(row_schema["$ref"], schema)
    row_keys = list(((row_schema or {}).get("properties") or {}).keys())
    yaml_keys = {str(e.get("yaml")).split(".")[0] for e in fm.get("storyline_backlog", []) if e.get("yaml")}
    missing_keys = [k for k in row_keys if k not in yaml_keys]
    if missing_keys:
        res.fail(f"{C.FIELD_MAP} storyline_backlog: backlog row keys with no entry {missing_keys}")
    add_kit_problems(res, "kit_tracker", "field_map_problems", C.repo_root())
    res.summary = f"{sum(len(v) for v in fm.values())} entries over {len(fm)} Record types"


def check_touch_sets_resolve(res: Result) -> None:
    m = C.load_machine()
    touch = C.load_touch_sets()
    rules = C.load_rules()
    known_agents = set((rules.get("handoffs") or {}).keys())
    patches = touch.get("patches") or {}
    sets = touch.get("sets") or {}
    globs: list[tuple[str, str]] = []
    for g in touch.get("protected") or []:
        globs.append(("protected", g))
    for g in touch.get("local") or []:
        globs.append(("local", g))
    for name, spec in patches.items():
        if not isinstance(spec, dict) or not spec.get("file") or not spec.get("path"):
            res.fail(f"patches.{name} needs file and path")
            continue
        try:
            C.patch_shape(str(spec["path"]))
        except ScriptError as exc:
            res.fail(f"patches.{name}: {exc}")
    for ph, entry in (touch.get("phases") or {}).items():
        if ph not in m.phases:
            res.fail(f"phases.{ph} is not a phase")
        for g in (entry or {}).get("files") or []:
            globs.append((f"phases.{ph}", g))
        for p in (entry or {}).get("patches") or []:
            if p not in patches:
                res.fail(f"phases.{ph} names unknown patch {p!r}")
    for ag, entry in (touch.get("agents") or {}).items():
        entry = entry or {}
        if ag not in known_agents:
            res.fail(f"agents.{ag} is not a crew member in dispatch-rules.yaml handoffs")
        ph = entry.get("phase")
        if ph not in m.phases:
            res.fail(f"agents.{ag}.phase {ph!r} is not a phase")
            continue
        phase_files = ((touch.get("phases") or {}).get(ph) or {}).get("files") or []
        for g in entry.get("files") or []:
            globs.append((f"agents.{ag}", g))
            sample = C.expand_glob(g, "example-story", 0).replace("**", "x/y").replace("*", "x")
            if not C.path_allowed(sample, phase_files, "example-story", 0):
                res.fail(f"agents.{ag}: {g} is not inside phases.{ph}")
        for p in entry.get("patches") or []:
            if p not in patches:
                res.fail(f"agents.{ag} names unknown patch {p!r}")
            elif p not in (((touch.get("phases") or {}).get(ph) or {}).get("patches") or []):
                res.fail(f"agents.{ag}: patch {p} is not allowed in phases.{ph}")
    for name, entry in (touch.get("scripts") or {}).items():
        entry = entry or {}
        src = entry.get("files_from")
        if src and src not in ("agent", "phase") and not (isinstance(src, str) and src.startswith("set:") and src[4:] in sets):
            res.fail(f"scripts.{name}.files_from {src!r} is not agent | phase | set:<name>")
        for g in list(entry.get("files") or []) + list(entry.get("extra_files") or []):
            globs.append((f"scripts.{name}", g))
        for p in entry.get("patches") or []:
            if p not in patches:
                res.fail(f"scripts.{name} names unknown patch {p!r}")
    for name, entry in sets.items():
        for g in (entry or {}).get("files") or []:
            globs.append((f"sets.{name}", g))
        for p in (entry or {}).get("patches") or []:
            if p not in patches:
                res.fail(f"sets.{name} names unknown patch {p!r}")
    for where, g in globs:
        for prob in C.glob_problems(str(g)):
            res.fail(f"{where}: {g!r}: {prob}")
    for i, b in enumerate(touch.get("branches") or []):
        if not isinstance(b, dict) or not b.get("prefix") or not b.get("pattern"):
            res.fail(f"branches[{i}] needs prefix and pattern")
            continue
        if not str(b["pattern"]).startswith(str(b["prefix"])):
            res.fail(f"branches[{i}]: pattern does not start with its prefix")
        for ph in b.get("phases") or []:
            if ph not in (touch.get("phases") or {}):
                res.fail(f"branches[{i}] names phase {ph!r} with no touch set")
        if b.get("set") and b["set"] not in sets:
            res.fail(f"branches[{i}] names unknown set {b['set']!r}")
        if not b.get("phases") and not b.get("set"):
            res.fail(f"branches[{i}] names neither phases nor a set")
    res.summary = f"{len(globs)} globs, {len(touch.get('agents') or {})} agents, {len(touch.get('branches') or [])} branch rules"


SCHEMA_GLOBS = ["storyline/templates/*.schema.json", "storyline/observability/*.schema.json", "storyline/crew/contracts/*.schema.json",
                "storyline/crew/runtime/*/output-schema.json", "kit/tracker/*.schema.json",
                ".claude/skills/tines-review/references/findings-schema.json", "stories/*/agent/*schema.json"]
PLANNED_SCHEMAS = ["storyline/crew/contracts/baton.schema.json"] + [f"storyline/crew/contracts/{a}.schema.json" for a in EXPECTED_AGENTS] + \
                  [f"storyline/crew/runtime/{r}/output-schema.json" for r in ("planner", "brief-writer", "retro-writer")] + [C.BACKLOG_SCHEMA, C.MILESTONES_SCHEMA]


def check_contracts_valid_json_schema(res: Result) -> None:
    root = C.repo_root()
    files = sorted({str(p.relative_to(root)) for g in SCHEMA_GLOBS for p in root.glob(g)})
    try:
        import jsonschema  # type: ignore

        meta_check: Optional[Callable[[Any], None]] = jsonschema.Draft202012Validator.check_schema
    except Exception:  # noqa: BLE001 — optional
        meta_check = None
    for rel in files:
        try:
            schema = json.loads(C.rpath(rel).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            res.fail(f"{rel}: not valid JSON ({exc})")
            continue
        for prob in C.schema_problems(schema)[:5]:
            res.fail(f"{rel}: {prob}")
        if meta_check is not None:
            try:
                meta_check(schema)
            except Exception as exc:  # noqa: BLE001
                res.fail(f"{rel}: fails the 2020-12 meta-schema ({str(exc).splitlines()[0][:160]})")
        if rel.startswith("storyline/crew/contracts/"):
            defs = schema.get("$defs") or {}
            if not isinstance(defs.get("input"), dict) or not isinstance(defs.get("output"), dict):
                res.fail(f"{rel}: needs $defs.input and $defs.output (REPO-DESIGN.md §15.2)")
    for rel in PLANNED_SCHEMAS:
        if rel not in files:
            need(res, rel)
    event_schema = C.load_schema(C.EVENT_SCHEMA, from_config=True)
    contract_schema = C.load_schema(C.CONTRACT_SCHEMA, from_config=True)
    report_schema = C.load_schema(C.VERIFY_REPORT_SCHEMA, from_config=True)
    n_art = 0
    for base in (C.WORK_DIR, C.EXAMPLES_DIR):
        d = C.rpath(base)
        if not d.is_dir():
            continue
        for story in sorted(p for p in d.iterdir() if p.is_dir()):
            rel = f"{base}/{story.name}"
            ev = story / "events.jsonl"
            if ev.is_file() and event_schema:
                for n, line in enumerate(ev.read_text(encoding="utf-8").splitlines(), 1):
                    if not line.strip():
                        continue
                    n_art += 1
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        res.fail(f"{rel}/events.jsonl:{n}: not JSON")
                        continue
                    for e in C.validate(obj, event_schema)[:2]:
                        res.fail(f"{rel}/events.jsonl:{n}: {e}")
                    if isinstance(obj, dict) and obj.get("story_key") != story.name:
                        res.fail(f"{rel}/events.jsonl:{n}: story_key {obj.get('story_key')!r} ≠ {story.name}")
            vr = story / "verify-report.json"
            if vr.is_file() and report_schema:
                n_art += 1
                try:
                    for e in C.validate(json.loads(vr.read_text(encoding="utf-8")), report_schema)[:3]:
                        res.fail(f"{rel}/verify-report.json: {e}")
                except json.JSONDecodeError:
                    res.fail(f"{rel}/verify-report.json: not JSON")
            dm = story / "design.md"
            if dm.is_file() and contract_schema:
                n_art += 1
                contract, err = C.extract_contract(dm.read_text(encoding="utf-8"))
                if err:
                    res.fail(f"{rel}/design.md: {err}")
                else:
                    for e in C.validate(contract, contract_schema)[:3]:
                        res.fail(f"{rel}/design.md contract: {e}")
    res.summary = f"{len(files)} schema file(s){' (+ meta-schema)' if meta_check else ''}; {n_art} artifact(s) validated"


VOLATILE_KEYS = {"generated_at", "built_at", "git_sha", "source_sha", "bundled_at"}


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def check_bundle_fresh(res: Result) -> None:
    kit = need(res, "scripts/kit")
    bundle = need(res, "kit/bundle/kit-bundle.json")
    if kit is None or bundle is None:
        return
    root = C.repo_root()
    # The generator that judges freshness is THIS checker's own copy (scripts/kit_bundle.py beside this file — the BASE
    # branch's in storyline.yml), run against the PR's tree (cwd = root; kit_bundle finds the repository from the cwd), so a
    # PR that edits scripts/kit or kit_bundle.py cannot turn its own stale bundle green. Only when this checker has no
    # kit_bundle.py beside it (a PR that introduces the kit) is the tree's own copy used.
    here = Path(__file__).resolve().parent
    gen = here / "kit_bundle.py" if (here / "kit_bundle.py").is_file() else root / "scripts" / "kit_bundle.py"
    # The kit's own freshness check first (`kit_bundle.py --check`: 0 fresh, 1 stale); a generator without --check
    # (usage, exit 2) falls back to regenerating in a scratch copy of the tree and comparing.
    p = subprocess.run([sys.executable, str(gen), "--check"], cwd=str(root), capture_output=True, text=True, timeout=300)
    if p.returncode in (0, 1):
        if p.returncode == 1:
            lines = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip()]
            res.fail(C.truncate(lines[-1] if lines else "stale — run ./scripts/kit bundle", 300))
        res.summary = "./scripts/kit bundle --check: fresh"
        return
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "repo"
        shutil.copytree(root, copy, ignore=shutil.ignore_patterns(*SKIP_DIRS, "*.pyc"))
        p = subprocess.run([sys.executable, str(gen)], cwd=str(copy), capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            res.fail("./scripts/kit bundle failed in a scratch copy: " + C.truncate((p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else "?", 200))
            return
        stale = []
        for sub in ("kit/bundle", "kit/resources"):
            new_dir, old_dir = copy / sub, root / sub
            names = {q.relative_to(new_dir) for q in new_dir.rglob("*.json")} | ({q.relative_to(old_dir) for q in old_dir.rglob("*.json")} if old_dir.is_dir() else set())
            for name in sorted(names):
                a, b = old_dir / name, new_dir / name
                if not a.is_file() or not b.is_file():
                    stale.append(f"{sub}/{name} ({'missing in the repo' if not a.is_file() else 'no longer generated'})")
                    continue
                try:
                    same = C.canonical_json(_strip_volatile(json.loads(a.read_text(encoding='utf-8')))) == C.canonical_json(_strip_volatile(json.loads(b.read_text(encoding='utf-8'))))
                except json.JSONDecodeError:
                    same = a.read_bytes() == b.read_bytes()
                if not same:
                    stale.append(f"{sub}/{name}")
        if stale:
            res.fail("stale — run ./scripts/kit bundle and commit: " + ", ".join(stale[:8]))
    res.summary = "the bundle equals a fresh ./scripts/kit bundle"


LIBRARY_LINK_RE = re.compile(r"tines\.com/library/stories/(\d+)")


def check_catalog_ids_verified(res: Result) -> None:
    catalog = C.catalog_ids()
    cited: list[tuple[str, int]] = []
    starters = C.read_yaml(C.rpath(C.STARTER_STORIES), required=False)

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if re.search(r"(seed|library)", str(k)) and (isinstance(v, int) or (isinstance(v, str) and v.isdigit())):
                    if int(v) > 0:
                        cited.append((where, int(v)))
                elif re.search(r"(seed|library)", str(k)) and isinstance(v, list):
                    cited.extend((where, int(x)) for x in v if str(x).isdigit() and int(x) > 0)
                else:
                    walk(v, where)
        elif isinstance(node, list):
            for v in node:
                walk(v, where)

    if starters is not None:
        walk(starters, C.STARTER_STORIES)
    tracker = C.load_tracker(required=False)
    for r in (tracker.rows if tracker else []):
        sid = r.get("library_seed_id")
        if str(sid or "0").isdigit() and int(sid or 0) > 0:
            cited.append((f"{C.TRACKER}:{r.get('key')}", int(sid)))
    for base in (C.WORK_DIR, C.EXAMPLES_DIR):
        d = C.rpath(base)
        for f in sorted(d.glob("*/discovery.md")) if d.is_dir() else []:
            fm = C.read_front_matter(f) or {}
            cited.extend((C.rel(f), int(x)) for x in fm.get("cited_library_ids") or [] if str(x).isdigit())
            rd = fm.get("reuse_decision") if isinstance(fm.get("reuse_decision"), dict) else {}
            if rd.get("kind") == "import_seed" and str(rd.get("target") or "").isdigit():
                cited.append((C.rel(f), int(rd["target"])))
        for f in sorted(d.glob("*/intake.md")) if d.is_dir() else []:
            fm = C.read_front_matter(f) or {}
            cited.extend((C.rel(f), int(x)) for x in fm.get("candidate_seed_ids") or [] if str(x).isdigit())
    for rel in doc_scope():
        text = text_of(rel) or ""
        cited.extend((rel, int(x)) for x in LIBRARY_LINK_RE.findall(text))
    if catalog is None:
        need(res, C.CATALOG_SEEDS)
        if cited:
            res.notes.append(f"{len(cited)} citation(s) wait for the catalog")
        return
    for where, i in cited:
        if i not in catalog:
            res.fail(f"{where}: Library id {i} is not in {C.CATALOG_SEEDS}")
    res.summary = f"{len(cited)} citation(s) of {len({i for _, i in cited})} id(s); catalog holds {len(catalog)}"


def doc_scope() -> list[str]:
    """The documentation the lifecycle and the kit add (and the root files §3.3 edits to link them)."""
    out = []
    for rel in repo_files():
        if not rel.endswith((".md", ".mdc")):
            continue
        if rel.startswith(("storyline/", "kit/", "stories/kit-launch/", ".claude/skills/storyline/", ".claude/skills/storyline-gate/", ".cursor/rules/storyline")):
            out.append(rel)
        elif rel in ("README.md", "AGENTS.md", "REPO-DESIGN.md", "docs/README.md", ".claude/rules/storyline-work.md") or re.match(r"docs/0[89]-", rel):
            out.append(rel)
        elif rel.startswith(".claude/agents/") and Path(rel).stem in EXPECTED_AGENTS:
            out.append(rel)
        elif rel.startswith(("tines-skills/backlog-planning/", "tines-skills/story-brief-writing/", "tines-skills/story-retrospective/")):
            out.append(rel)
    return out


LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def check_doc_links_resolve(res: Result) -> None:
    n = 0
    for rel in doc_scope():
        text = text_of(rel)
        if text is None:
            continue
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        text = re.sub(r"`[^`\n]*`", "", text)
        base = Path(rel).parent
        for target in LINK_RE.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#") or any(ch in target for ch in "<>{}…*"):
                continue
            path = target.split("#")[0].split("?")[0]
            if not path:
                continue
            n += 1
            full = (C.repo_root() / base / path).resolve()
            try:
                norm = str(full.relative_to(C.repo_root()))
            except ValueError:
                res.fail(f"{rel}: link {target} leaves the repository")
                continue
            if full.exists():
                continue
            if is_planned(norm):
                res.plan(norm, f"linked from {rel}")
            else:
                res.fail(f"{rel}: link {target} does not resolve")
    res.planned = sorted(set(res.planned))
    res.summary = f"{n} relative link(s) in {len(doc_scope())} file(s)"


ENV_PY_RE = re.compile(r"(?:os\.environ\.get|os\.getenv|os\.environ\[|\benv)\(?\s*[\"']([A-Z][A-Z0-9_]+)[\"']")
ENV_SH_RE = re.compile(r"\$\{?([A-Z][A-Z0-9_]+)")


def check_env_example_matches_reads(res: Result) -> None:
    example = need(res, ".env.example")
    documented = set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\b", example.read_text(encoding="utf-8"))) if example else set()
    scope = [f for f in ("scripts/storyline", "scripts/kit", ".claude/hooks/phase-gate.sh") if C.rpath(f).is_file()]
    scope += [str(p.relative_to(C.repo_root())) for p in sorted(C.rpath("scripts").glob("storyline_*.py"))]
    scope += [str(p.relative_to(C.repo_root())) for p in sorted(C.rpath("scripts").glob("kit_*.py"))]
    for f in ("scripts/kit", ".claude/hooks/phase-gate.sh"):
        if not C.rpath(f).is_file():
            need(res, f)
    reads: dict[str, set[str]] = {}
    for rel in scope:
        text = C.rpath(rel).read_text(encoding="utf-8")
        rx = ENV_PY_RE if rel.endswith(".py") else ENV_SH_RE
        for name in rx.findall(text):
            reads.setdefault(name, set()).add(rel)
    shell_locals = set()
    for rel in scope:
        if not rel.endswith(".py"):
            shell_locals |= set(re.findall(r"^\s*(?:local\s+|readonly\s+|export\s+)?([A-Z][A-Z0-9_]+)=", C.rpath(rel).read_text(encoding="utf-8"), re.M))
    for name, where in sorted(reads.items()):
        if PLATFORM_ENV_RE.search(name) or name in CI_ONLY_ENV or name in shell_locals:
            continue
        if name in documented:
            continue
        if name in PLANNED_ENV:
            res.plan(".env.example", f"{name} ({PLANNED_ENV[name]})")
            continue
        res.fail(f"{name} is read by {', '.join(sorted(where))} but not named in .env.example")
    res.summary = f"{len(reads)} variable(s) read by {len(scope)} file(s)"


def _split_tools(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    out, depth, cur = [], 0, ""
    for ch in str(value or ""):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def check_agents_frontmatter_valid(res: Result) -> None:
    n = 0
    for f in sorted(C.rpath(".claude/agents").glob("*.md")):
        n += 1
        rel = C.rel(f)
        try:
            fm, _, body = C.split_front_matter(f.read_text(encoding="utf-8"))
        except ScriptError as exc:
            res.fail(f"{rel}: {exc}")
            continue
        if not fm:
            res.fail(f"{rel}: no frontmatter")
            continue
        if fm.get("name") != f.stem:
            res.fail(f"{rel}: name {fm.get('name')!r} ≠ file name")
        if not str(fm.get("description") or "").strip():
            res.fail(f"{rel}: no description")
        if fm.get("model") != "inherit":
            res.fail(f"{rel}: model must be inherit (with the tier in a comment), never a model id")
        tools = _split_tools(fm.get("tools"))
        if any(FORBIDDEN_TOOL_RE.match(t) for t in tools):
            res.fail(f"{rel}: a forbidden tool (Bash(yq *), Bash(jq *), Bash(git diff *) or tines ai-usage) — they write files, print the environment or bypass storyline estimate")
        exp = EXPECTED_AGENTS.get(f.stem)
        if exp:
            if sorted(tools) != sorted(exp["tools"]):
                res.fail(f"{rel}: tools {tools} ≠ REPO-DESIGN.md §5.1 {exp['tools']}")
            dis = _split_tools(fm.get("disallowedTools"))
            if not set(exp["disallowed"]) <= set(dis):
                res.fail(f"{rel}: disallowedTools {dis} must include {exp['disallowed']}")
            if fm.get("maxTurns") != exp["maxTurns"]:
                res.fail(f"{rel}: maxTurns {fm.get('maxTurns')!r} ≠ {exp['maxTurns']}")
            for key in ("mcpServers", "memory"):
                if key in fm:
                    res.fail(f"{rel}: a new crew member sets no {key} (REPO-DESIGN.md §5.2)")
            if not re.search(r"(?im)^#+\s*never\b|^\*\*never\b", body):
                res.fail(f"{rel}: no closing Never list")
        elif f.stem == "tines-builder" and "mcpServers" not in fm:
            res.fail(f"{rel}: the builder defines the tines server (mcpServers, §3.3 row 19)")
        elif f.stem not in ("tines-builder", "tines-reviewer") and "mcpServers" in fm:
            res.fail(f"{rel}: only tines-builder loads the Tines Stories MCP server")
    for a in EXPECTED_AGENTS:
        if not C.rpath(f".claude/agents/{a}.md").is_file():
            need(res, f".claude/agents/{a}.md")
    for f in sorted(C.rpath(".claude/skills").glob("*/SKILL.md")):
        n += 1
        rel = C.rel(f)
        try:
            fm = C.split_front_matter(f.read_text(encoding="utf-8"))[0] or {}
        except ScriptError as exc:
            res.fail(f"{rel}: {exc}")
            continue
        if fm.get("name") != f.parent.name:
            res.fail(f"{rel}: name {fm.get('name')!r} ≠ folder")
        if not str(fm.get("description") or "").strip():
            res.fail(f"{rel}: no description")
        if f.parent.name in HUMAN_ONLY_SKILLS and fm.get("disable-model-invocation") is not True:
            res.fail(f"{rel}: a side-effecting workflow is human-triggered (disable-model-invocation: true, P21)")
        if f.parent.name == "storyline-gate" and not fm.get("argument-hint"):
            res.fail(f"{rel}: argument-hint <slug> <gate> <decision>")
    for s in ("storyline", "storyline-gate"):
        if not C.rpath(f".claude/skills/{s}/SKILL.md").is_file():
            need(res, f".claude/skills/{s}/SKILL.md")
    for name in CURSOR_RULES:
        path = C.rpath(f".cursor/rules/{name}.mdc")
        if not path.is_file():
            need(res, f".cursor/rules/{name}.mdc")
            continue
        n += 1
        fm = C.split_front_matter(path.read_text(encoding="utf-8"))[0] or {}
        if not str(fm.get("description") or "").strip():
            res.fail(f".cursor/rules/{name}.mdc: no description (agent-requested rules attach by description)")
        if fm.get("alwaysApply") is not False:
            res.fail(f".cursor/rules/{name}.mdc: alwaysApply must be false")
        if fm.get("globs"):
            res.fail(f".cursor/rules/{name}.mdc: no globs (§6.3)")
    for f in sorted(C.rpath("tines-skills").glob("*/SKILL.md")):
        n += 1
        rel = C.rel(f)
        text = f.read_text(encoding="utf-8")
        try:
            fm, _, body = C.split_front_matter(text)
        except ScriptError as exc:
            res.fail(f"{rel}: {exc}")
            continue
        fm = fm or {}
        if fm.get("name") != f.parent.name:
            res.fail(f"{rel}: name {fm.get('name')!r} ≠ folder")
        if not str(fm.get("description") or "").strip() or len(str(fm.get("description"))) > 1024:
            res.fail(f"{rel}: description missing or longer than 1,024 characters")
        if len(body.splitlines()) >= 500:
            res.fail(f"{rel}: body is 500 lines or more")
        meta = fm.get("metadata")
        if meta is not None and (not isinstance(meta, dict) or any(not isinstance(v, str) for v in meta.values())):
            res.fail(f"{rel}: metadata must be a flat map of strings")
    for s in ("backlog-planning", "story-brief-writing", "story-retrospective"):
        if not C.rpath(f"tines-skills/{s}/SKILL.md").is_file():
            need(res, f"tines-skills/{s}/SKILL.md")
    res.summary = f"{n} file(s)"


HOST_RE = re.compile(r"(?<![A-Za-z0-9_.<>{}$@-])([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)\.tines\.com\b")
# Tenant ids only (§13 row 17). Library ids are public catalog ids (kit/catalog/library-seeds.yaml), not tenant ids.
ID_KEY_RE = re.compile(r"(^|_)(story|team|folder|action|record_type|resource|draft|app|dashboard|change_request|self|installation)_ids?$|^(rt|res)_[a-z0-9_]+$")


def _nonzero_ids(node: Any, where: str, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)) and ID_KEY_RE.search(str(k)) and v != 0:
                out.append(f"{where}.{k} = {v}")
            elif isinstance(v, list) and ID_KEY_RE.search(str(k)):
                out.extend(f"{where}.{k}[] = {x}" for x in v if isinstance(x, (int, float)) and not isinstance(x, bool) and x != 0)
            else:
                _nonzero_ids(v, f"{where}.{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _nonzero_ids(v, f"{where}[{i}]", out)


def check_template_hygiene(res: Result) -> None:
    files = repo_files()
    hosts, emails = [], []
    for rel in files:
        text = text_of(rel)
        if text is None:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for mh in HOST_RE.finditer(line):
                if mh.group(1) not in PUBLIC_TINES_HOSTS:
                    hosts.append(f"{rel}:{n} {mh.group(0)}")
            for me in EMAIL_RE.finditer(line):
                addr = me.group(0).lower()
                if not (addr.endswith("@example.invalid") or addr.endswith(".example.invalid")) and not addr.endswith("@users.noreply.github.com"):
                    emails.append(f"{rel}:{n}")
    for h in hosts[:10]:
        res.fail(f"tenant-looking host {h} (use <your-tenant>.tines.com)")
    for e in emails[:10]:
        res.fail(f"email outside *.example.invalid at {e}")
    provisioned = C.rpath(C.TENANT_CONFIG).is_file()
    if provisioned:
        res.notes.append(f"{C.TENANT_CONFIG} exists (a provisioned repository): the every-id-0 rule does not apply")
    else:
        bad: list[str] = []
        man = C.read_yaml(C.rpath(C.MANIFEST), required=False) or {}
        _nonzero_ids(man, "stories/_manifest.yaml", bad)
        nt = C.read_yaml(C.rpath("policies/never-touch.yml"), required=False) or {}
        if nt.get("story_ids"):
            bad.append(f"policies/never-touch.yml story_ids {nt['story_ids']}")
        _nonzero_ids({"teams": nt.get("teams")}, "policies/never-touch.yml", bad)
        if C.rpath(C.TENANT_CONFIG_EXAMPLE).is_file():
            _nonzero_ids(C.read_yaml(C.rpath(C.TENANT_CONFIG_EXAMPLE)) or {}, C.TENANT_CONFIG_EXAMPLE, bad)
        for f in sorted(C.rpath("kit/resources").glob("*.example.json")):
            try:
                _nonzero_ids(json.loads(f.read_text(encoding="utf-8")), C.rel(f), bad)
            except json.JSONDecodeError:
                res.fail(f"{C.rel(f)}: not valid JSON")
        tracker = C.load_tracker(required=False)
        for r in (tracker.rows if tracker else []):
            if int(r.get("prod_story_id") or 0) != 0:
                bad.append(f"{C.TRACKER}:{r.get('key')}.prod_story_id = {r.get('prod_story_id')}")
        for b in bad[:10]:
            res.fail(f"a real-looking id in the template: {b} (ids are 0 until known)")
    kf = C.rpath("stories/kit-launch/story.json")
    if kf.is_file():
        try:
            export = json.loads(kf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            res.fail("stories/kit-launch/story.json: not valid JSON")
            export = {}
        for a in (export.get("agents") or []) if isinstance(export, dict) else []:
            opts = (a or {}).get("options") if isinstance(a, dict) else None
            if not isinstance(opts, dict):
                continue
            for key in ("path", "secret"):
                v = opts.get(key)
                if isinstance(v, str) and v and not (v.startswith("<") and v.endswith(">")) and not ("<<" in v or v.lstrip().startswith("=")):
                    res.fail(f"stories/kit-launch/story.json: action {a.get('name')!r} carries a real {key} (empty or <assigned-on-import> only)")
    else:
        need(res, "stories/kit-launch/story.json")
    res.summary = f"{len(files)} file(s) scanned"


def check_release_not_skeleton(res: Result) -> None:
    for rel in ("stories/kit-launch/story.json", "kit/dashboard/dashboards/storyworks.dashboard.json"):
        p = C.rpath(rel)
        if not p.is_file():
            res.fail(f"{rel} does not exist (the §15.6 release builds and exports it)")
        elif "SKELETON" in p.read_text(encoding="utf-8"):
            res.fail(f"{rel} still carries the SKELETON label (§15.6)")
    res.summary = "the kit story and the dashboard are real exports"


def check_resources_in_sync(res: Result, snapshot: Optional[str]) -> None:
    if not snapshot:
        res.na = "not applicable: runs on the nightly snapshot (--snapshot FILE, tracker-pull.yml)"
        return
    data = json.loads(Path(snapshot).read_text(encoding="utf-8"))
    hashes: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and k.startswith("hash_") and isinstance(v, str):
                    hashes[k[5:]] = v
                elif k == "hashes" and isinstance(v, dict):
                    hashes.update({str(kk): str(vv) for kk, vv in v.items()})
                else:
                    walk(v)

    walk(data)
    kit_fn = kit_helper("kit_bundle", "resources_in_sync_problems")
    if kit_fn is not None:  # the kit's definition (bundle-form values), the one kit-sync.yml hashes
        for p in kit_fn(C.repo_root(), data):
            res.fail(p)
        res.summary = f"{len(hashes)} Resource hash(es) compared (kit_bundle.resources_in_sync_problems)"
        return
    bundle = need(res, "kit/bundle/kit-bundle.json")
    if bundle is None:
        return
    resources = json.loads(bundle.read_text(encoding="utf-8")).get("resources") or []
    generated = {str(r.get("name")): r.get("value") for r in resources if isinstance(r, dict) and r.get("name")}
    if not hashes:
        res.fail("the snapshot carries no kit_state.hash_<name> values")
    for name, h in sorted(hashes.items()):
        if name not in generated:
            res.notes.append(f"{name}: not generated from the repository (not compared)")
            continue
        if C.resource_hash(generated[name]) != h:
            res.fail(f"{name}: the tenant's Resource differs from main (open a tracker-drift PR; kit-sync.yml re-pushes it)")
    res.summary = f"{len(hashes)} Resource hash(es) compared"


REGISTRY: list[tuple[str, Callable[..., None]]] = [
    ("phase_enum_in_sync", check_phase_enum_in_sync),
    ("tracker_schema_valid", check_tracker_schema_valid),
    ("field_map_complete", check_field_map_complete),
    ("touch_sets_resolve", check_touch_sets_resolve),
    ("contracts_valid_json_schema", check_contracts_valid_json_schema),
    ("bundle_fresh", check_bundle_fresh),
    ("catalog_ids_verified", check_catalog_ids_verified),
    ("doc_links_resolve", check_doc_links_resolve),
    ("env_example_matches_reads", check_env_example_matches_reads),
    ("agents_frontmatter_valid", check_agents_frontmatter_valid),
    ("template_hygiene", check_template_hygiene),
    ("release_not_skeleton", check_release_not_skeleton),
    ("resources_in_sync", check_resources_in_sync),
]
MODE_BOUND = {"release_not_skeleton", "resources_in_sync"}


# --------------------------------------------------------------------------------------------------------------- #
# Pull-request checks
# --------------------------------------------------------------------------------------------------------------- #

STATE_KEYS = ("phase", "status", "open_gate")
STATE_EVENTS = ("transition", "gate_decision", "budget", "escalation")   # the event types that move a row


def _move_in_machine(machine: C.Machine, old_phase: str, new_phase: str) -> bool:
    """Some transition row of state-machine.yaml takes ``old_phase`` to ``new_phase`` ("*", "$same", "$previous")."""
    for t in machine.transitions:
        frm, to = t.get("from"), t.get("to")
        if frm == "*":
            if machine.is_terminal(old_phase):
                continue
        elif frm != old_phase:
            continue
        if to == new_phase or to == "$previous" or (to == "$same" and new_phase == old_phase):
            return True
    return False


def _event_explains(machine: C.Machine, e: dict[str, Any], old_phase: str, new_phase: str) -> bool:
    """An added event records this row's move: its from/to phases match, or (to_phase absent) its gate decision
    resolves in the machine from the old phase to the new one."""
    if e.get("event_type") not in STATE_EVENTS:
        return False
    if e.get("event_type") == "gate_decision" and e.get("actor_kind") != "human":
        return False
    if e.get("from_phase") not in (None, old_phase):
        return False
    if e.get("to_phase") is not None:
        return e.get("to_phase") == new_phase
    gate = e.get("gate")
    if not gate:
        return False
    t = machine.find(old_phase, gate=str(gate), decision=e.get("decision") if e.get("event_type") != "escalation" else None,
                     guard=lambda _when: True)
    return bool(t) and (t.get("to") in (new_phase, "$previous") or (t.get("to") == "$same" and new_phase == old_phase))


def tracker_transition_problems(machine: C.Machine, base_rows: dict[str, dict[str, Any]], head_rows: list[dict[str, Any]],
                                added_events: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Every new or changed tracker row's (phase, status, open_gate) is a legal state, reached by a transition of
    state-machine.yaml that an event added in the same PR records (REPO-DESIGN.md §4.2, §6.5). A new row — from
    ``./scripts/storyline intake`` or folded from Tines by ``tracker-pull.yml`` — starts intake / active / no gate / attempt 0,
    so no merge can put a row straight into build past G0, G1 and G2."""
    none = machine.open_gate_none
    problems: list[str] = []
    for row in head_rows:
        key = str(row.get("key"))
        phase, status = str(row.get("phase")), str(row.get("status"))
        gate = str(row.get("open_gate") if row.get("open_gate") is not None else none)
        if phase not in machine.all_phases:
            problems.append(f"{key}: phase {phase!r} is not in state-machine.yaml")
            continue
        if status not in machine.statuses_for(phase):
            problems.append(f"{key}: status {status!r} is not a status of {phase} (state-machine.yaml phase_info)")
        if gate not in machine.gate_values:
            problems.append(f"{key}: open_gate {gate!r} is not a gate (or {none})")
        old = base_rows.get(key)
        if old is None:
            if (phase, status, gate) != ("intake", "active", none) or int(row.get("attempt") or 0) != 0:
                problems.append(f"{key}: a new row starts intake/active with open_gate {none} and attempt 0; this one is "
                                f"{phase}/{status}, open_gate {gate}, attempt {row.get('attempt')}")
            continue
        old_phase, old_status = str(old.get("phase")), str(old.get("status"))
        old_gate = str(old.get("open_gate") if old.get("open_gate") is not None else none)
        if (old_phase, old_status, old_gate) == (phase, status, gate):
            continue
        move = f"{old_phase}/{old_status} ({old_gate}) → {phase}/{status} ({gate})"
        if not _move_in_machine(machine, old_phase, phase):
            problems.append(f"{key}: {move} is not a transition of state-machine.yaml")
            continue
        events = [e for e in added_events.get(key, []) if isinstance(e, dict)]
        explained = any(_event_explains(machine, e, old_phase, phase) for e in events)
        if not explained and old_phase == phase == "intake" and status == "awaiting_gate" and gate == "G0":
            # brief_writer opening G0 inside intake, folded by tracker-pull (kit_tracker: the D4 save_brief case)
            explained = any(e.get("event_type") == "specialist_run" and e.get("agent") in ("brief_writer", "brief-writer") for e in events)
        if not explained:
            problems.append(f"{key}: {move} has no transition, gate_decision, budget or escalation event added to "
                            f"storyline/work/{key}/events.jsonl in this PR that records it")
    return problems


def run_pr_checks(base: str, branch: str, pr: dict[str, Any]) -> list[Result]:
    touch = C.load_touch_sets()
    approvers = C.load_approvers()
    event_schema = C.load_schema(C.EVENT_SCHEMA, from_config=True) or {}
    changed = C.changed_paths(base, "HEAD")
    rule = C.branch_rule(touch, branch)
    slug = (rule or {}).get("slug")
    results: list[Result] = []

    r = Result("pr_touch_set")
    if rule is None:
        prot = [p for p in changed if C.path_allowed(p, touch.get("protected") or [])]
        for p in prot:
            r.fail(f"{p}: lifecycle state changes only on a lifecycle branch ({', '.join(b['prefix'] for b in touch.get('branches') or [])})")
        r.summary = f"{len(changed)} path(s); not a lifecycle branch"
    elif rule.get("malformed"):
        r.fail(f"branch {branch!r} starts with {rule['prefix']!r} but does not match {rule['pattern']!r}")
    else:
        files, patches = C.allowed_for(touch, phases=list(rule.get("phases") or []), set_name=rule.get("set"))
        for v in C.touch_violations(changed, slug=slug, files=files, patches=patches, touch=touch, base_ref=base, head_reader=C.read_head_file):
            r.fail(v)
        r.summary = f"{len(changed)} path(s) on {rule['prefix']}{slug or '*'} ({', '.join(rule.get('phases') or [rule.get('set')])})"
    results.append(r)

    r = Result("pr_tracker_rev")
    base_t = C.tracker_at(base)
    head_t = C.load_tracker(required=False)
    changed_rows = []
    if C.TRACKER in changed and head_t is not None:
        base_rows = {str(x.get("key")): x for x in (base_t.rows if base_t else [])}
        for row in head_t.rows:
            key = str(row.get("key"))
            old = base_rows.get(key)
            if old is not None and C.canonical_json(json.loads(json.dumps(old, default=str))) == C.canonical_json(json.loads(json.dumps(row, default=str))):
                continue
            changed_rows.append(key)
            want = (int(old.get("rev") or 0) if old else 0) + 1
            if row.get("rev") != want:
                r.fail(f"{key}: rev {row.get('rev')} ≠ main's rev + 1 = {want} (rebase; the scripts recompute it)")
        removed = sorted(set(base_rows) - {str(x.get("key")) for x in head_t.rows})
        for key in removed:
            r.fail(f"{key}: a tracker row was removed (rows are retired, never deleted)")
    r.summary = f"{len(changed_rows)} changed row(s)"
    results.append(r)

    r = Result("pr_events_append_only")
    added_decisions: list[dict[str, Any]] = []
    added_events: dict[str, list[dict[str, Any]]] = {}   # story key → the events this PR appends (pr_tracker_transitions)
    for path in changed:
        if not re.fullmatch(r"storyline/work/[^/]+/events\.jsonl", path):
            continue
        old = (C.git_show(base, path) or "").splitlines()
        head_text = C.read_head_file(path)
        if head_text is None:
            r.fail(f"{path}: deleted (append-only)")
            continue
        new = head_text.splitlines()
        if new[: len(old)] != old:
            r.fail(f"{path}: an existing line changed or was removed (append-only; correct with a new event)")
            continue
        for n, line in enumerate(new[len(old):], len(old) + 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                r.fail(f"{path}:{n}: not JSON")
                continue
            for e in C.validate(obj, event_schema)[:2]:
                r.fail(f"{path}:{n}: {e}")
            if isinstance(obj, dict):
                added_events.setdefault(path.split("/")[2], []).append(obj)
            if isinstance(obj, dict) and obj.get("event_type") == "gate_decision":
                added_decisions.append({**obj, "_where": f"{path}:{n}"})
    r.summary = f"{len(added_decisions)} gate_decision event(s) added"
    results.append(r)

    r = Result("pr_tracker_transitions")
    if C.TRACKER in changed and head_t is not None:
        base_rows_t = {str(x.get("key")): x for x in (base_t.rows if base_t else [])}
        for problem in tracker_transition_problems(C.load_machine(), base_rows_t, head_t.rows, added_events):
            r.fail(problem)
        r.summary = f"{len(head_t.rows)} row(s) checked against state-machine.yaml transitions"
    else:
        r.na = "the tracker is not changed"
    results.append(r)

    r = Result("pr_build_on_main")
    if rule and rule.get("prefix") == "story/" and slug:
        brow = base_t.row(slug) if base_t else None
        if brow is None or brow.get("phase") != "build":
            r.fail(f"{slug} is {'absent' if brow is None else brow.get('phase')} on main: a build PR needs G1 and G2 first (the row on main in build)")
        r.summary = f"{slug} on main: {brow.get('phase') if brow else 'absent'}"
    else:
        r.na = "not a build PR"
    results.append(r)

    hrow = head_t.row(slug) if (head_t and slug) else None
    r = Result("pr_design_ready")
    if rule and rule.get("prefix") == "design/" and slug:
        import storyline_ready

        ready = storyline_ready.run_ready(slug)
        for c in ready["checks"]:
            if c["result"] == "FAIL":
                r.fail(f"{c['id']} {c['name']}: {c['reason']}")
        if ready["gb"]["decision"] == "park":
            r.fail("GB would park the story: " + "; ".join(ready["gb"]["reasons"]))
        r.summary = f"G1 {ready['result']}"
    else:
        r.na = "not a design PR"
    results.append(r)

    g4 = bool(rule and rule.get("prefix") == "story/" and slug and hrow and hrow.get("phase") == "ship")
    r = Result("pr_cost_checks")
    if g4:
        import storyline_estimate

        cost = storyline_estimate.run_checks(str(slug), offline=True)
        for c in cost["results"]:
            if c["result"] == "FAIL":
                r.fail(f"{c['id']}: {c['detail']}")
        r.summary = "cost.4–cost.9"
    else:
        r.na = "not a G4 PR"
    results.append(r)

    r = Result("pr_qa_line")
    if g4:
        body = str(pr.get("body") or "")
        m = re.search(r"QA verification:\s*\**\s*(pass|fail)\b\s*\**\s*[·•|—-]\s*by\s+([A-Za-z0-9][^\n*`<]{0,80})", body, re.I)
        if not m:
            r.fail("the PR's Lifecycle section needs \"QA verification: pass · by <role>\" (the human's verdict on story-qa's verification prompt)")
        elif m.group(1).lower() != "pass":
            r.fail(f"QA verification says {m.group(1)} (by {m.group(2).strip()})")
        elif "@" in m.group(2):
            r.fail("QA verification names an email; a role only")
        else:
            r.summary = f"pass · by {m.group(2).strip()}"
    else:
        r.na = "not a G4 PR"
    results.append(r)

    r = Result("pr_gate_approvers")
    gates_cfg = approvers.get("gates") or {}
    reviews = [x for x in (pr.get("reviews") or []) if isinstance(x, dict)]
    author = str(((pr.get("author") or {}).get("login")) or "")
    head_oid = str(pr.get("headRefOid") or "")
    # A review counts only when it names the commit it approved and that commit is the head: a review with no commit oid
    # (or PR data with no headRefOid) cannot be tied to what merges, so it is not counted (fail closed).
    approving = {str((x.get("author") or {}).get("login")) for x in reviews
                 if str(x.get("state")).upper() == "APPROVED" and str((x.get("author") or {}).get("login")) not in ("", author)
                 and head_oid and str((x.get("commit") or {}).get("oid") or "") == head_oid}
    for ev in added_decisions:
        gate = str(ev.get("gate"))
        cfg = gates_cfg.get(gate)
        if not isinstance(cfg, dict):
            r.fail(f"{ev['_where']}: gate {gate} is not in {C.APPROVERS}")
            continue
        if not cfg.get("event_allowed"):
            r.fail(f"{ev['_where']}: {gate} is never recorded as a gate_decision event ({cfg.get('reaches_git_by')})")
            continue
        teams = list(cfg.get("teams") or [])
        need_n = len(teams) if cfg.get("require") == "all" else 1
        if not pr:
            r.fail(f"{ev['_where']}: {gate} needs approving review(s) from {teams} — no PR data was given (--pr-json)")
        elif len(approving) < need_n:
            r.fail(f"{ev['_where']}: {gate} needs {need_n} approving review(s) on the head commit from {', '.join((approvers.get('teams') or {}).get(t, t) for t in teams)} (not the author); found {len(approving)}")
    if added_decisions:
        r.notes.append("team membership of each approver is not read (no team-membership endpoint is named in REPO-DESIGN.md): "
                       "CODEOWNERS gives storyline/work/*/events.jsonl and ship.md to security-platform, so branch protection's "
                       "code-owner review holds the team — VERIFY both are on")
    r.summary = f"{len(added_decisions)} decision(s); {len(approving)} approving reviewer(s)"
    results.append(r)

    r = Result("pr_skill_held_out")
    skills = sorted({p.split("/")[1] for p in changed if re.match(r"tines-skills/[^/_][^/]*/", p)})
    for s in skills:
        cases = C.rpath(f"storyline/evals/skills/{s}.cases.yaml")
        if not cases.is_file():
            r.fail(f"tines-skills/{s}/ changed but storyline/evals/skills/{s}.cases.yaml (its held-out cases) does not exist")
    r.summary = f"{len(skills)} skill(s) changed"
    results.append(r)
    return results


# --------------------------------------------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------------------------------------------- #


def print_results(results: list[Result], strict: bool) -> int:
    rc = 0
    width = max(len(r.name) for r in results) if results else 10
    for r in results:
        status = r.status
        if status == "SKIP" and strict and r.planned:
            status = "FAIL"
        head = r.summary if status == "PASS" else (r.na or ("planned input(s) missing" if r.planned and not r.fails else f"{len(r.fails)} problem(s)"))
        print(f"{status:<4} {r.name:<{width}}  {head}")
        for msg in r.fails[:25]:
            print(f"       - {msg}")
        if len(r.fails) > 25:
            print(f"       … and {len(r.fails) - 25} more")
        for msg in r.planned[:12]:
            print(f"       ~ planned: {msg}")
        if len(r.planned) > 12:
            print(f"       ~ … and {len(r.planned) - 12} more planned")
        for msg in r.notes[:5]:
            print(f"       · {msg}")
        if status == "FAIL":
            rc = 1
    return rc


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="storyline check", description="The contract-checker registry (one PASS/FAIL line each).")
    C.add_root_args(p)
    p.add_argument("names", nargs="*", help="run only these checks")
    p.add_argument("--all", action="store_true", help="every registry check (the default)")
    p.add_argument("--strict", action="store_true", help="a SKIP for a planned input that is missing is a FAIL (storyline.yml)")
    p.add_argument("--release", action="store_true", help="add release_not_skeleton; every SKIP is a FAIL (§15.6)")
    p.add_argument("--snapshot", help="the nightly snapshot JSON for resources_in_sync")
    p.add_argument("--pr", action="store_true", help="the pull-request checks (storyline.yml)")
    p.add_argument("--base", help="--pr: the base commit")
    p.add_argument("--branch", help="--pr: the head branch name")
    p.add_argument("--pr-json", help="--pr: `gh pr view --json body,author,reviews,headRefOid` output")
    p.add_argument("--list", action="store_true", help="list the check names")
    args = p.parse_args(argv)
    C.apply_root_args(args)
    if args.list:
        for name, _ in REGISTRY:
            print(name + (" (mode-bound)" if name in MODE_BOUND else ""))
        return 0
    if args.pr:
        if not args.base or not args.branch:
            raise ScriptError("--pr needs --base and --branch")
        pr = json.loads(Path(args.pr_json).read_text(encoding="utf-8")) if args.pr_json else {}
        return print_results(run_pr_checks(args.base, args.branch, pr), strict=True)
    names = args.names or [n for n, _ in REGISTRY if n not in MODE_BOUND]
    if args.release and "release_not_skeleton" not in names:
        names.append("release_not_skeleton")
    if args.snapshot and "resources_in_sync" not in names:
        names.append("resources_in_sync")
    unknown = [n for n in names if n not in dict(REGISTRY)]
    if unknown:
        raise ScriptError(f"unknown check(s) {unknown}; --list shows them")
    results = []
    for name, fn in REGISTRY:
        if name not in names:
            continue
        res = Result(name)
        try:
            if name == "resources_in_sync":
                fn(res, args.snapshot)
            else:
                fn(res)
        except BaseScriptError as exc:  # printed its message on stderr already; keep it in the result too
            res.fail(getattr(exc, "message", None) or "stopped (see the error above)")
        results.append(res)
    return print_results(results, strict=args.strict or args.release)


if __name__ == "__main__":
    sys.exit(main())
