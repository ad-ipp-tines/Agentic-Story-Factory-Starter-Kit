#!/usr/bin/env python3
"""Build ``kit/bundle/kit-bundle.json`` — the one file the kit story reads from the repository.

Spec: REPO-DESIGN.md §2 (``kit/bundle/``), §7.2 A12 (the fallback copy reads its file manifest), A15 (``read_bundle``:
``{skills[], record_types[], resources[], dashboard, app_files[], file_manifest[], state_machine, catalog}``),
A17–A24 (what each part provisions), §8.2 (the Resources), §9.2 (App file rules), §15.4 (this builder).

``./scripts/kit bundle [--check] [--out FILE]``

Generates, deterministically (no timestamps, no commit SHA — the same sources always give the same bytes):

* ``skills[]``        every ``tines-skills/<name>/SKILL.md``, parsed and validated exactly as ``push_skills.py`` does
                      (A17 creates each one in the ops team, never overwriting a customer's skill)
* ``record_types[]``  the three ``kit/records/*.record-type.json`` bodies for ``POST /api/v1/record_types`` (A18)
* ``resources[]``     every Resource A19 creates, with its initial value: ``kit_catalog``, ``sdlc_state_machine`` and
                      ``sdlc_limits`` generated here; ``sdlc_approvers``, ``sdlc_sync_lock`` and ``kit_tracker_view`` as
                      empty shapes; ``kit_config`` built at run time from the Page; the ops trio's four Resources
                      from ``stories/ops-story-health-monitor/resources/*.example.json`` (created only when absent)
* ``dashboard``       ``kit/dashboard/dashboards/story-factory.dashboard.json`` (A23; a SKELETON until §15.6)
* ``app_files[]``     ``kit/dashboard/app/**`` — tsx/ts/jsx/js/json only (``endpoints.md`` is documentation), each
                      ≤ 128 KB, ≤ 5 MB in all, ``App.tsx`` present (A24: ``PUT /api/v1/apps/{id}/files``)
* ``file_manifest[]`` the files A12's Contents-API fallback copies from the template (paths only; ``over_1mb``
                      marks a ``[BY HAND]`` copy). In a provisioned repository (``kit/tenant/config.yaml`` exists)
                      the manifest is carried over unchanged: the fallback copy is a template-only concern, and a
                      customer's new stories must not make the bundle stale
* ``state_machine``   the ``sdlc_state_machine`` Resource value, generated from ``sdlc/lifecycle/state-machine.yaml``
* ``catalog``         the ``kit_catalog`` Resource value, generated from ``kit/catalog/`` and the milestone catalog

It also writes the generated examples in ``kit/resources/`` (``kit_catalog``, ``sdlc_state_machine``,
``sdlc_limits``, ``kit_config``, ``kit_state``). ``--check`` writes nothing and exits 1 when the committed bundle or
an example differs from what the sources produce (``kit.yml`` on PRs; ``./scripts/sdlc check`` ``bundle_fresh``).

Importable: ``build_bundle(root)``, ``bundle_problems(root)``, ``bundle_resource_values(root, config)`` (the four
synced Resources in bundle form — what ``kit_state.hash_<name>`` fingerprints), ``generated_resource_values(root,
config, tenant_host)`` (what kit-sync.yml writes), ``resource_hash(value)`` (= ``sdlc_common.resource_hash``),
``snapshot_hashes(snapshot)``, ``resources_in_sync_problems(root, snapshot)``, ``kit_config_value``.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import ScriptError, dump_json, eprint, find_repo_root  # noqa: E402
from kit_tracker import (  # noqa: E402
    CATALOG_SEEDS,
    CATALOG_STARTERS,
    MILESTONES,
    RECORDS_DIR,
    all_phases,
    canonical,
    load_state_machine,
    read_json,
    read_yaml,
    record_enum,
    untrusted_problems,
)

BUNDLE = Path("kit/bundle/kit-bundle.json")
APP_DIR = Path("kit/dashboard/app")
DASHBOARD = Path("kit/dashboard/dashboards/story-factory.dashboard.json")
RESOURCES_DIR = Path("kit/resources")
TENANT_CONFIG = Path("kit/tenant/config.yaml")
TENANT_CONFIG_EXAMPLE = Path("kit/tenant/config.example.yaml")
COST_CEILINGS = Path("policies/cost-ceilings.yml")
OPS_RESOURCES_DIR = Path("stories/ops-story-health-monitor/resources")
SKILLS_DIR = Path("tines-skills")

APP_EXTENSIONS = {".tsx", ".ts", ".jsx", ".js", ".json"}
APP_FILE_MAX = 128 * 1024
APP_TOTAL_MAX = 5 * 1024 * 1024
RESOURCE_MAX = 5 * 1024 * 1024
BUNDLE_WARN = 900 * 1024            # GitHub raw reads above 1 MB are K44
LARGE_FILE = 1024 * 1024            # A12: files over 1 MB are [BY HAND] copies

RECORD_TYPES = ("sdlc_backlog", "sdlc_events", "sdlc_milestones")
SYNCED_RESOURCES = ("sdlc_state_machine", "kit_catalog", "kit_config", "sdlc_limits")   # kit-sync.yml keeps these current
LIMITS_HUMAN_KEYS = ("enabled", "guards_confirmed")   # only people set these two; kit-sync.yml never writes them
RUNTIME_DEFAULTS = {                                   # REPO-DESIGN.md §8.2; policies/cost-ceilings.yml wins when present
    "planner": {"runs_per_day_max": 4, "credits_per_run_max": 2},
    "brief_writer": {"runs_per_day_max": 20, "credits_per_run_max": 2},
    "retro_writer": {"runs_per_day_max": 5, "credits_per_run_max": 3},
}
PENDING_RESET_HOURS = 24
MILESTONE_DEFAULT_OWNER = "platform"
# The step_* keys section A writes into kit_state (stories/kit-factory/sections/A-kickoff-and-provisioning.md is the
# authority for the list; kit/tenant/README.md maps them to the setup report).
STEP_KEYS = ("step_teams", "step_providers", "step_github", "step_repo", "step_bundle", "step_config", "step_skills",
             "step_record_types", "step_resources", "step_seed", "step_dashboard", "step_app", "step_probe",
             "step_report")
KIT_RESOURCES = ("kit_config", "kit_catalog", "sdlc_state_machine", "sdlc_limits", "sdlc_approvers", "sdlc_sync_lock",
                 "kit_tracker_view", "ops_limits", "ops_lock", "ops_responders", "ops_routing")
MANIFEST_EXCLUDE_DIRS = {".git", ".sdlc", ".tines", "__pycache__", "node_modules", ".terraform", ".obsidian"}
MANIFEST_EXCLUDE_FILES = {".DS_Store", ".env", ".mcp.json", "CLAUDE.local.md", ".terraform.lock.hcl"}
MANIFEST_EXCLUDE_PATHS = {"kit/tenant/config.yaml", "kit/tenant/setup-report.json", ".cursor/mcp.json",
                          ".claude/settings.local.json"}


# --------------------------------------------------------------------------- #
# Generated Resource values
# --------------------------------------------------------------------------- #


def build_state_machine_resource(root: Path) -> dict[str, Any]:
    """The sdlc_state_machine Resource: what sections B, C and D read (B3 enums, C5 apply_decision, D dispatch)."""
    sm = load_state_machine(root)
    info = sm.get("phase_info") or {}
    gate_info = sm.get("gate_info") or {}
    page_gates = list((sm.get("instruments") or {}).get("gate_decision_page") or [])
    page_options = {g: list((gate_info.get(g) or {}).get("decisions") or []) for g in page_gates}
    page_options["unpark"] = ["unpark"]
    table: dict[str, list[dict[str, Any]]] = {}
    for t in sm.get("transitions") or []:
        gate, decision = t.get("gate"), t.get("decision")
        if not gate or not decision:
            continue
        if gate == "GB" and decision == "unpark":
            key = "unpark"
        elif gate in page_gates:
            key = f"{gate}:{decision}"
        else:
            continue
        to = t.get("to")
        status = t.get("status")
        if status is None and to in info:
            status = ((info.get(to) or {}).get("statuses") or [None])[0]
        entry: dict[str, Any] = {"from": t.get("from"), "to": to, "status": status}
        for extra in ("when", "reset_attempt", "then"):
            if t.get(extra) is not None:
                entry[extra] = t[extra]
        table.setdefault(key, []).append(entry)
    enums = {
        "mode": record_enum(root, "sdlc_backlog", "mode"),
        "tier": record_enum(root, "sdlc_backlog", "tier"),
        "provider": record_enum(root, "sdlc_backlog", "provider"),
        "specialist_due": record_enum(root, "sdlc_backlog", "specialist_due"),
        "specialist_status": record_enum(root, "sdlc_backlog", "specialist_status"),
        "event_type": record_enum(root, "sdlc_events", "event_type"),
        "actor_kind": record_enum(root, "sdlc_events", "actor_kind"),
        "milestone_id": record_enum(root, "sdlc_milestones", "milestone_id"),
        "milestone_status": record_enum(root, "sdlc_milestones", "status"),
    }
    return {
        "version": sm.get("version", 1),
        "source": "sdlc/lifecycle/state-machine.yaml — generated by ./scripts/kit bundle and kept current by "
                  "kit-sync.yml; never edit this Resource by hand",
        "phases": list(sm.get("phases") or []),
        "holding": list(sm.get("holding") or []),
        "terminal": list(sm.get("terminal") or []),
        "all_phases": all_phases(sm),
        "statuses": list(sm.get("statuses") or []),
        "gates": list(sm.get("gates") or []),
        "open_gate_none": sm.get("open_gate_none", "none"),
        "open_gate_values": [sm.get("open_gate_none", "none")] + list(sm.get("gates") or []),
        "caps": sm.get("caps") or {},
        "timers": sm.get("timers") or {},
        "thresholds": sm.get("thresholds") or {},
        "phase_statuses": {p: list((v or {}).get("statuses") or []) for p, v in info.items()},
        "gate_decisions": {g: list((v or {}).get("decisions") or []) for g, v in gate_info.items()},
        "gate_types": {g: (v or {}).get("type") for g, v in gate_info.items()},
        "gate_decided_by": {g: (v or {}).get("decided_by") for g, v in gate_info.items()},
        "page_gates": page_gates,
        "page_options": page_options,
        "page_decision_table": table,
        "transitions": list(sm.get("transitions") or []),
        "runtime_dispatch": sm.get("runtime_dispatch") or {},
        "enums": enums,
    }


def build_catalog_resource(root: Path) -> dict[str, Any]:
    """The kit_catalog Resource: A2 (picks), A21/A22 (seeding), C (Option lists), D4 (the seed-id filter)."""
    seeds = read_yaml(root / CATALOG_SEEDS)
    starters = read_yaml(root / CATALOG_STARTERS)
    milestones = read_yaml(root / MILESTONES)
    seed_list = [s for s in seeds.get("seeds") or [] if isinstance(s, dict)]
    stories = []
    for s in starters.get("stories") or []:
        credit = s.get("credit_estimate") or {}
        stories.append({
            "n": s.get("n"), "key": s.get("key"), "title": s.get("title"), "use_case": s.get("use_case"),
            "library_seed_id": s.get("library_seed_id"), "mode": s.get("mode"), "tier": s.get("tier"),
            "owner": s.get("owner"), "milestone": s.get("milestone"), "target_offset_days": s.get("target_offset_days"),
            "credit_estimate_monthly": credit.get("monthly"), "credit_estimate_basis": credit.get("basis"),
            "needs_entitlements": list(((s.get("needs") or {}).get("entitlements")) or []),
            "page_pick": bool(s.get("page_pick")),
        })
    return {
        "version": 1,
        "source": ["kit/catalog/starter-stories.yaml", "kit/catalog/library-seeds.yaml",
                   "kit/tracker/milestones.yaml (id, title, criteria, due_offset_days)"],
        "starter_stories": stories,
        "always_seeded": list(starters.get("always_seeded") or []),
        "page_pick_options": [s["key"] for s in stories if s["page_pick"]] + ["custom", "none"],
        "target_offset_days_by_milestone": starters.get("target_offset_days_by_milestone") or {},
        "library_seeds": [{"id": s.get("id"), "name": s.get("name"), "url": s.get("url"),
                           "reference_only": bool(s.get("reference_only")), "role": s.get("role")} for s in seed_list],
        "seed_ids": [int(s["id"]) for s in seed_list],
        "milestones": [{"id": m.get("id"), "title": m.get("title"), "criteria": list(m.get("criteria") or []),
                        "due_offset_days": m.get("due_offset_days")}
                       for m in milestones.get("milestones") or [] if isinstance(m, dict)],
        "milestone_default_owner": MILESTONE_DEFAULT_OWNER,
    }


def build_limits_resource(root: Path) -> dict[str, Any]:
    """The sdlc_limits Resource. Mirrors policies/cost-ceilings.yml (kit-factory/* lines) and state-machine timers."""
    sm = load_state_machine(root)
    ceilings = read_yaml(root / COST_CEILINGS) if (root / COST_CEILINGS).exists() else {}
    agents = (ceilings or {}).get("agents") or {}
    runtime: dict[str, dict[str, Any]] = {}
    for agent, defaults in RUNTIME_DEFAULTS.items():
        line = agents.get(f"kit-factory/{agent}") or {}
        entry = dict(defaults)
        for key in ("runs_per_day_max", "credits_per_run_max"):
            if isinstance(line.get(key), (int, float)) and not isinstance(line.get(key), bool):
                entry[key] = line[key]
        runtime[agent] = entry
    debounce = (((sm.get("runtime_dispatch") or {}).get("on_backlog_change")) or {}).get("debounce_minutes", 60)
    runtime["planner"]["debounce_minutes"] = debounce
    timers = sm.get("timers") or {}
    return {
        "enabled": False,
        "guards_confirmed": False,
        "runtime": runtime,
        "gate_nudge_days": timers.get("gate_nudge_days", 3),
        "retro_cadence_days": timers.get("retro_cadence_days", 30),
        "shadow_days": timers.get("shadow_days", 7),
        "pending_reset_hours": PENDING_RESET_HOURS,
    }


def load_config(root: Path, path: Optional[Path] = None) -> dict[str, Any]:
    target = root / (path or TENANT_CONFIG)
    data = read_yaml(target)
    if not isinstance(data, dict):
        raise ScriptError(f"{target} must be a mapping (the shape is kit/tenant/config.example.yaml)")
    return data


def kit_config_value(config: dict[str, Any], tenant_host: Optional[str], environment: str = "prod") -> dict[str, Any]:
    """The kit_config Resource: the config commit + tenant_host (in-tenant only) + environment + the ops type ids."""
    value = copy.deepcopy(config)
    ops = value.pop("ops_record_types", None) or {}
    value["rt_ops_findings"] = int(ops.get("ops_findings") or 0)
    value["rt_ops_alerts"] = int(ops.get("ops_alerts") or 0)
    value["environment"] = environment
    value["tenant_host"] = tenant_host or "<your-tenant>.tines.com"
    return value


def bundle_resource_values(root: Path, config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """The four Resources kit-sync.yml keeps current, IN BUNDLE FORM — exactly the ``resources[].value`` that
    ``./scripts/kit bundle`` writes for them, and therefore what ``resource_hash`` is computed over.

    Bundle form means: ``sdlc_limits`` with ``enabled`` and ``guards_confirmed`` at their created value (false) —
    kit-sync.yml never writes those two keys, but the fingerprint covers the generated value as a whole; and
    ``kit_config`` with the ``<your-tenant>.tines.com`` placeholder for ``tenant_host``, because the real host lives only
    in the tenant and never in git. ``kit_config`` is present only when a config is given or ``kit/tenant/config.yaml``
    exists (a provisioned repository); in the template it is built at run time by A19.
    """
    values: dict[str, Any] = {
        "sdlc_state_machine": build_state_machine_resource(root),
        "kit_catalog": build_catalog_resource(root),
        "sdlc_limits": build_limits_resource(root),
    }
    if config is None and (root / TENANT_CONFIG).exists():
        config = load_config(root)
    if config is not None:
        values["kit_config"] = kit_config_value(config, None)
    return values


def generated_resource_values(root: Path, config: Optional[dict[str, Any]] = None,
                              tenant_host: Optional[str] = None) -> dict[str, Any]:
    """What kit-sync.yml WRITES: the bundle-form values, with the real ``tenant_host`` in ``kit_config`` and only the
    keys kit-sync.yml owns in ``sdlc_limits`` (never ``enabled`` / ``guards_confirmed``)."""
    values = bundle_resource_values(root, config)
    values["sdlc_limits"] = {k: v for k, v in values["sdlc_limits"].items() if k not in LIMITS_HUMAN_KEYS}
    if "kit_config" in values and tenant_host:
        values["kit_config"] = {**values["kit_config"], "tenant_host": tenant_host}
    return values


def resource_hash(value: Any) -> str:
    """The value recorded as ``kit_state.hash_<name>``: the sha256 hex of the canonical JSON (sorted keys, no
    whitespace, UTF-8 kept) of the Resource's BUNDLE-FORM value (``bundle_resource_values``).

    This is ``sdlc_common.resource_hash`` — the definition ``./scripts/sdlc check resources_in_sync`` recomputes over
    ``kit/bundle/kit-bundle.json`` ``resources[].value`` — so the writer (kit-sync.yml) and both checkers agree. The
    fallback below is the same formula for a checkout without the lifecycle scripts.
    """
    try:
        from sdlc_common import resource_hash as sdlc_resource_hash  # the single definition
    except ImportError:
        return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()
    return sdlc_resource_hash(value)


def snapshot_hashes(snapshot: Any) -> dict[str, str]:
    """``{name: hash}`` from a snapshot answer: every ``hash_<name>`` key anywhere in it (E5 returns kit_state's)."""
    found: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.startswith("hash_") and isinstance(value, str):
                    found[key[5:]] = value
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(snapshot)
    return found


def resources_in_sync_problems(root: Path, snapshot: Any) -> list[str]:
    """Compare the snapshot's kit_state.hash_<name> values with the Resources generated from main (bundle form)."""
    problems: list[str] = []
    hashes = snapshot_hashes(snapshot)
    values = bundle_resource_values(root)
    if not hashes:
        return ["the snapshot carries no kit_state.hash_<name> values (kit-sync.yml has not run since provisioning)"]
    for name in SYNCED_RESOURCES:
        if name not in values:
            continue  # kit_config in a repository without kit/tenant/config.yaml: nothing to compare
        actual = hashes.get(name)
        if not actual:
            problems.append(f"{name}: kit_state has no hash_{name} (kit-sync.yml has not run since provisioning)")
        elif actual != resource_hash(values[name]):
            problems.append(f"{name}: the tenant's Resource differs from main (run kit-sync.yml)")
    return problems


def build_kit_state_example(root: Path) -> dict[str, Any]:
    value: dict[str, Any] = {
        "status": "complete",
        "run_guid": "<run-guid>",
        "self_id": 0,
        "repo": "<org>/<repo>",
        "records_seeded": "<run-guid>",
        "planner_last_run": "",
        "app_id": 0,
        "dashboard_id": 0,
    }
    for step in STEP_KEYS:
        value[step] = {"status": "ok", "http_status": 200, "message": ""}
    for name in RECORD_TYPES:
        value[f"rt_{name}"] = 0
        fields = read_json(root / RECORDS_DIR / f"{name}.record-type.json").get("fields") or []
        value[f"fields_{name}"] = {f["name"]: 0 for f in fields}
    for name in KIT_RESOURCES:
        value[f"res_{name}"] = 0
    for name in SYNCED_RESOURCES:
        value[f"hash_{name}"] = ""
    return value


# --------------------------------------------------------------------------- #
# The other parts of the bundle
# --------------------------------------------------------------------------- #


def build_skills(root: Path) -> list[dict[str, Any]]:
    from push_skills import discover_skills, load_skill  # the same parser and rules as skills.yml

    skills = []
    problems = []
    for skill_dir in discover_skills(root / SKILLS_DIR, []):
        item = load_skill(skill_dir)
        if item["problems"]:
            problems += [f"{skill_dir.name}: {p}" for p in item["problems"]]
            continue
        payload = item["payload"]
        skills.append({"name": payload["name"], "description": payload["description"], "body": payload["body"],
                       "license": payload["license"], "compatibility": payload["compatibility"],
                       "metadata": payload["metadata"], "repo_path": f"{SKILLS_DIR.as_posix()}/{skill_dir.name}/SKILL.md"})
    if problems:
        raise ScriptError("tines-skills/ is not valid (./scripts/tines skills-push --validate-only):\n  " + "\n  ".join(problems))
    return skills


def build_record_types(root: Path) -> list[dict[str, Any]]:
    out = []
    for name in RECORD_TYPES:
        rel = RECORDS_DIR / f"{name}.record-type.json"
        body = read_json(root / rel)
        if body.get("name") != name:
            raise ScriptError(f"{rel}: name must be {name!r}")
        out.append({
            "name": name,
            "file": rel.as_posix(),
            "skip_on_records_tier": ["starter"] if name == "sdlc_events" else [],   # A18: Starter holds 5 types
            "body": body,
        })
    return out


def build_resources(root: Path, state_machine: dict[str, Any], catalog: dict[str, Any],
                    limits: dict[str, Any], kit_config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    def ops_example(name: str) -> Any:
        return read_json(root / OPS_RESOURCES_DIR / f"{name}.example.json")

    empty_view = read_json(root / RESOURCES_DIR / "kit_tracker_view.example.json")
    for key in ("stories", "open_gates", "milestones"):
        empty_view[key] = []
    empty_view["counts_by_phase"] = {p: 0 for p in state_machine["all_phases"]}
    empty_view["stories_csv"] = "key,title,phase,status,open_gate,owner,target_date,credit_estimate_monthly\n"
    empty_view["milestones_csv"] = "id,title,status,due_date\n"
    empty_view["source_sha"] = ""
    resources = [
        {"name": "kit_config", "create": "always", "value": kit_config,
         "built_at_run_time": "A19: config (A2) + tenant_host + environment: prod; no email. In a provisioned "
                              "repository the value here is kit/tenant/config.yaml in bundle form (tenant_host is a "
                              "placeholder; kit-sync.yml writes the real one)",
         "description": "The kit's config: Page answers (no emails), team ids, entitlements, LLM choice. Kept current by kit-sync.yml."},
        {"name": "kit_catalog", "create": "always", "value": catalog,
         "description": "Starter stories, verified Library ids and milestones, from kit/catalog/. Kept current by kit-sync.yml."},
        {"name": "sdlc_state_machine", "create": "always", "value": state_machine,
         "description": "Phases, statuses, gates, transitions and runtime_dispatch, from sdlc/lifecycle/. Kept current by kit-sync.yml."},
        {"name": "sdlc_limits", "create": "always", "value": limits,
         "description": "Kill switch, guards flag, per-agent caps and timers. enabled and guards_confirmed are set by people only."},
        {"name": "sdlc_approvers", "create": "always", "value": {"G0": [], "G6": [], "G7": [], "GX": [], "unpark": []},
         "built_at_run_time": "A19: G0, G6 and G7 from the kickoff Page approver emails; GX and unpark by hand",
         "description": "Who may decide each Tines-side gate (emails; never committed)."},
        {"name": "sdlc_sync_lock", "create": "always", "value": {"lock": "free"},
         "description": "The compare-and-swap lock for Flow 1 (section B) and kit-sync.yml."},
        {"name": "kit_tracker_view", "create": "records_not_entitled", "value": empty_view,
         "description": "The tracker mirror the Page fallback renders when Records are not entitled (section B writes it)."},
    ]
    for name in ("ops_limits", "ops_lock", "ops_responders", "ops_routing"):
        resources.append({"name": name, "create": "when_absent", "value": ops_example(name),
                          "built_at_run_time": "A19: responders = the Page approvers" if name == "ops_responders" else None,
                          "description": f"The ops trio's {name} Resource, from the scaffold's example (created only when absent)."})
    for r in resources:
        size = len(canonical(r["value"]).encode("utf-8")) if r["value"] is not None else 0
        if size > RESOURCE_MAX:
            raise ScriptError(f"Resource {r['name']} is {size} bytes; Resources hold at most 5 MB")
        r["read_access"] = "TEAM"
        if r.get("built_at_run_time") is None:
            r.pop("built_at_run_time", None)
    return resources


def build_app_files(root: Path) -> list[dict[str, Any]]:
    base = root / APP_DIR
    if not base.exists():
        raise ScriptError(f"{APP_DIR} is missing")
    files = []
    total = 0
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = path.relative_to(base).as_posix()
        if path.suffix not in APP_EXTENSIONS:
            continue  # endpoints.md and other documentation stay out: Apps accept tsx, ts, jsx, js and json only
        content = path.read_text(encoding="utf-8")
        size = len(content.encode("utf-8"))
        if size > APP_FILE_MAX:
            raise ScriptError(f"{APP_DIR / rel} is {size} bytes; an App file holds at most 128 KB")
        total += size
        files.append({"path": rel, "content": content})
    if total > APP_TOTAL_MAX:
        raise ScriptError(f"the App files total {total} bytes; an App build holds at most 5 MB")
    if not any(f["path"] == "App.tsx" for f in files):
        raise ScriptError("kit/dashboard/app/App.tsx is required (the entry file's name cannot change)")
    return files


def _gitignore_rules(root: Path) -> list[tuple[bool, str]]:
    """(negated, pattern) from the repository's .gitignore — the subset of gitignore syntax the file uses."""
    path = root / ".gitignore"
    rules: list[tuple[bool, str]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            negated = line.startswith("!")
            rules.append((negated, line[1:] if negated else line))
    return rules


def _ignored(rel: str, rules: list[tuple[bool, str]]) -> bool:
    parts = rel.split("/")
    ignored = False
    for negated, pattern in rules:
        directory = pattern.endswith("/")
        pat = pattern.rstrip("/").lstrip("/")
        if "/" in pat:
            hit = fnmatch.fnmatch(rel, pat) or (directory and rel.startswith(pat + "/"))
        elif directory:
            hit = any(fnmatch.fnmatch(part, pat) for part in parts[:-1])
        else:
            hit = any(fnmatch.fnmatch(part, pat) for part in parts)
        if hit:
            ignored = not negated
    return ignored


def _manifest_candidates(root: Path) -> list[str]:
    """Every file of the working tree that git would carry: a walk that honours .gitignore and skips local state.

    A walk (not ``git ls-files``) so the result is the same in a clean checkout, in CI, and in the scratch copy
    ``./scripts/sdlc check`` (bundle_fresh) builds without ``.git``.
    """
    rules = _gitignore_rules(root)
    paths = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in MANIFEST_EXCLUDE_DIRS for part in rel.parts):
            continue
        rel_posix = rel.as_posix()
        if _ignored(rel_posix, rules):
            continue
        paths.append(rel_posix)
    return sorted(paths)


def build_file_manifest(root: Path, committed: Optional[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    if (root / TENANT_CONFIG).exists() and committed and isinstance(committed.get("file_manifest"), list):
        return committed["file_manifest"], True
    manifest = []
    for rel in _manifest_candidates(root):
        name = rel.rsplit("/", 1)[-1]
        if rel in MANIFEST_EXCLUDE_PATHS or name in MANIFEST_EXCLUDE_FILES or name.endswith(".pyc"):
            continue
        if name.startswith(".env.") and name != ".env.example":
            continue
        if rel.startswith("terraform/") and (".tfstate" in name or name.endswith(".tfvars") and not name.endswith(".example.tfvars")):
            continue
        if rel.startswith("sdlc/work/") and rel != "sdlc/work/README.md":
            continue  # per-story artifacts are the customer's, never the template's
        entry: dict[str, Any] = {"path": rel}
        if rel == BUNDLE.as_posix():
            entry["self"] = True
        elif (root / rel).stat().st_size > LARGE_FILE:
            entry["over_1mb"] = True
        if rel.startswith(".github/workflows/"):
            entry["workflow"] = True    # copying it needs the token's Workflows permission (K11)
        manifest.append(entry)
    if not any(e["path"] == BUNDLE.as_posix() for e in manifest):
        manifest.append({"path": BUNDLE.as_posix(), "self": True})
        manifest.sort(key=lambda e: e["path"])
    return manifest, False


def generated_examples(root: Path, state_machine: dict[str, Any], catalog: dict[str, Any],
                       limits: dict[str, Any]) -> dict[Path, Any]:
    example_config = load_config(root, TENANT_CONFIG_EXAMPLE)
    return {
        RESOURCES_DIR / "kit_catalog.example.json": catalog,
        RESOURCES_DIR / "sdlc_state_machine.example.json": state_machine,
        RESOURCES_DIR / "sdlc_limits.example.json": limits,
        RESOURCES_DIR / "kit_config.example.json": kit_config_value(example_config, None),
        RESOURCES_DIR / "kit_state.example.json": build_kit_state_example(root),
    }


def build_bundle(root: Path) -> tuple[dict[str, Any], dict[Path, Any]]:
    committed = None
    if (root / BUNDLE).exists():
        try:
            committed = read_json(root / BUNDLE)
        except (json.JSONDecodeError, ScriptError):
            committed = None
    values = bundle_resource_values(root)
    state_machine = values["sdlc_state_machine"]
    catalog = values["kit_catalog"]
    limits = values["sdlc_limits"]
    dashboard = read_json(root / DASHBOARD)
    file_manifest, frozen = build_file_manifest(root, committed)
    bundle = {
        "bundle_version": 1,
        "description": "Generated by ./scripts/kit bundle — never edit by hand (kit/bundle/README.md). Read by "
                       "[KIT] 00 A15 from the new repository, and by A12's fallback copy from the template.",
        "generated_from": ["tines-skills/*/SKILL.md", "kit/records/*.record-type.json", "kit/catalog/*.yaml",
                           "kit/tracker/milestones.yaml", "sdlc/lifecycle/state-machine.yaml",
                           "policies/cost-ceilings.yml", "stories/ops-story-health-monitor/resources/*.example.json",
                           "kit/dashboard/app/**", "kit/dashboard/dashboards/story-factory.dashboard.json"],
        "skills": build_skills(root),
        "record_types": build_record_types(root),
        "resources": build_resources(root, state_machine, catalog, limits, values.get("kit_config")),
        "dashboard": dashboard,
        "dashboard_skeleton": str(dashboard.get("description", "")).startswith("SKELETON"),
        "app_entry": "App.tsx",
        "app_files": build_app_files(root),
        "file_manifest": file_manifest,
        "file_manifest_frozen": frozen,
        "state_machine": state_machine,
        "catalog": catalog,
    }
    problems = untrusted_problems(bundle)
    if problems:
        raise ScriptError("the bundle would carry secret-looking values or real email addresses:\n  " + "\n  ".join(problems[:20]))
    return bundle, generated_examples(root, state_machine, catalog, limits)


def bundle_problems(root: Path) -> list[str]:
    """What differs between the committed bundle / generated examples and what the sources produce (bundle_fresh)."""
    bundle, examples = build_bundle(root)
    problems = []
    targets = {BUNDLE: bundle, **examples}
    for rel, value in targets.items():
        path = root / rel
        if not path.exists():
            problems.append(f"{rel} is missing (run ./scripts/kit bundle)")
            continue
        try:
            current = read_json(path)
        except json.JSONDecodeError:
            problems.append(f"{rel} is not valid JSON (run ./scripts/kit bundle)")
            continue
        if canonical(current) != canonical(value):
            if isinstance(value, dict) and isinstance(current, dict):
                keys = sorted(k for k in set(value) | set(current) if canonical(value.get(k)) != canonical(current.get(k)))
                problems.append(f"{rel} is stale in {', '.join(keys)} (run ./scripts/kit bundle)")
            else:
                problems.append(f"{rel} is stale (run ./scripts/kit bundle)")
        elif path.read_text(encoding="utf-8") != dump_json(value):
            problems.append(f"{rel} is not in canonical form (run ./scripts/kit bundle)")
    return problems


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="kit bundle", description="Build kit/bundle/kit-bundle.json and the generated Resource examples.")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when anything is stale")
    parser.add_argument("--out", type=Path, help=f"write the bundle here instead of {BUNDLE}")
    args = parser.parse_args(argv)
    root = find_repo_root()
    if args.check:
        problems = bundle_problems(root)
        for p in problems:
            print(f"FAIL bundle_fresh: {p}")
        if not problems:
            print("PASS bundle_fresh: kit/bundle/kit-bundle.json and the generated examples match their sources")
        return 1 if problems else 0
    bundle, examples = build_bundle(root)
    if not args.out:
        # write the generated examples first, so a newly generated file is already in the file manifest
        for rel, value in examples.items():
            (root / rel).write_text(dump_json(value), encoding="utf-8")
        bundle, examples = build_bundle(root)
    out = args.out or (root / BUNDLE)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump_json(bundle)
    out.write_text(text, encoding="utf-8")
    size = len(text.encode("utf-8"))
    eprint(f"[kit] wrote {out.relative_to(root) if out.is_relative_to(root) else out} ({size} bytes; "
           f"{len(bundle['skills'])} skills, {len(bundle['record_types'])} record types, "
           f"{len(bundle['resources'])} resources, {len(bundle['app_files'])} app files, "
           f"{len(bundle['file_manifest'])} manifest entries{', frozen' if bundle['file_manifest_frozen'] else ''})")
    if size > BUNDLE_WARN:
        eprint("[kit] warning: the bundle is close to 1 MB; GitHub's raw read above 1 MB is VERIFY K44")
    if bundle["dashboard_skeleton"]:
        eprint("[kit] note: the dashboard is still the SKELETON (the §15.6 maintainer release replaces it)")
    if not args.out:
        eprint(f"[kit] wrote {len(examples)} generated examples in {RESOURCES_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
