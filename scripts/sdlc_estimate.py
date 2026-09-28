#!/usr/bin/env python3
"""``./scripts/sdlc estimate <slug> [--check]`` — the credit estimate and the cost checks (a script, not an agent).

Spec: REPO-DESIGN.md §5.3.7 (the cost checks), §12 (cost controls) rows 1, 7 and 8, §4.5 (GB). The checks run inside
G1 (``./scripts/sdlc ready``) and again at G4 (``sdlc.yml`` and ``verify-merge``). They never call a model.

The estimate
------------
``runs/day × credits/run × 30``, where
  runs/day      ``contract.cost_estimate.runs_per_day`` (or ``--runs-per-day`` before the contract exists), and never
                fewer than the schedule implies (86,400 ÷ ``schedule_interval_seconds``)
  credits/run   observed in dev by ``story-qa`` (``credits_observed`` in ``.sdlc/out/<slug>/story-qa-<attempt>.json``, or
                the newest ``qa-*.json`` from ``eval-run``) → else ``contract.cost_estimate.credits_per_run_est`` → else the
                comparables (below) → else ``--credits-per-run`` → else 0
  comparables   with a dev-team key in the environment and without ``--offline``: ``./scripts/tines ai-usage --group_by
                action`` over the last 30 days, read-only; credits per run = ``credits_used ÷ usage_count`` per AI Agent
                action row (whether ``usage_count`` counts runs is VERIFY, docs/VERIFY.md E5). CI never has a key, so
                ``sdlc.yml`` is always offline.
plus the verify-phase eval-run cost: Σ over ``sdlc/work/<slug>/evals/cases.yaml`` of (k for a model-graded case, else 1)
× credits/run, against the dev team's ceiling (cost.9).

Budget lines: ``policies/cost-ceilings.yml`` ``teams:``. Production stories run in the prod team, which is the ops team
(REPO-DESIGN.md §7.1): the entry whose ``team_id`` equals ``stories/_manifest.yaml`` ``environments.prod.team_id``, else
the one named ``prod``, else ``ops``. The eval run spends the ``dev`` entry. Committed = the other tracker rows'
``credit_estimate.monthly`` in discover … improve (not intake, parked, rejected or retired).

The checks (``--check``; one PASS/FAIL line each, exit 1 on any FAIL)
  cost.4  an AI Agent action with agentic capabilities (tools, code analysis, web search or skills) is estimated at the
          smart model unless a model is pinned; a fast-tier agent that carries a skill has the fast model pinned
          (``model_pinned: true`` in the contract) and recorded in ``story.meta.yaml`` (``ai.agents[].model``)
  cost.5  the runs a day the schedule implies do not exceed ``contract.cost_estimate.runs_per_day``
  cost.6  the monthly projection fits the team's remaining ceiling
  cost.7  on a custom or local provider the result notes ``billed_cost`` (credits bypassed), and no credits are counted
  cost.8  every AI Agent action has a Trigger (or another deterministic pre-filter) upstream — from the export's links
          when a real export exists, else from the order of ``contract.actions_outline``
  cost.9  the verify-phase eval-run cost fits the dev team's ceiling
Already gated elsewhere and cited, not repeated: the budget line per AI Agent action (lint's
``ai_agent_budget_line_present``), the token alert in meta (the reviewer), the tool count (the contract schema).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sdlc_common as C  # noqa: E402
from sdlc_common import ScriptError  # noqa: E402
from tines_common import eprint  # noqa: E402

LLM_TYPE = "Agents::LLMAgent"          # scripts/lint_story.py LLM_TYPE (confirmed on real exports there)
TRIGGER_TYPE = "Agents::TriggerAgent"  # scripts/lint_story.py TRIGGER_TYPE
COMMITTED_PHASES = ("discover", "design", "build", "verify", "ship", "operate", "improve")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def team_keys(ceilings: dict[str, Any], manifest: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    teams = ceilings.get("teams") or {}
    envs = manifest.get("environments") or {}
    prod_id = int(_num(((envs.get("prod") or {}).get("team_id")), 0))
    prod_key = None
    if prod_id:
        prod_key = next((k for k, v in teams.items() if isinstance(v, dict) and int(_num(v.get("team_id"), 0)) == prod_id), None)
    prod_key = prod_key or ("prod" if "prod" in teams else ("ops" if "ops" in teams else None))
    dev_id = int(_num(((envs.get("dev") or {}).get("team_id")), 0))
    dev_key = None
    if dev_id:
        dev_key = next((k for k, v in teams.items() if isinstance(v, dict) and int(_num(v.get("team_id"), 0)) == dev_id), None)
    dev_key = dev_key or ("dev" if "dev" in teams else None)
    return prod_key, dev_key


def observed_credits(slug: str, attempt: int) -> tuple[Optional[float], list[dict[str, Any]], str]:
    """Credits per run observed in dev: from story-qa's output for this attempt, else the newest eval-run result."""
    sources = []
    qa_out = C.out_dir(slug) / f"story-qa-{attempt}.json"
    if qa_out.is_file():
        try:
            data = json.loads(qa_out.read_text(encoding="utf-8"))
            payload = data.get("payload") if isinstance(data, dict) and "payload" in data else data
            sources.append((payload or {}, C.rel(qa_out)))
        except json.JSONDecodeError:
            pass
    latest = C.latest_qa_result(slug)
    if latest:
        sources.append((latest, latest.get("_file", "qa")))
    for payload, where in sources:
        rows = [r for r in (payload.get("credits_observed") or []) if isinstance(r, dict)]
        if not rows:
            continue
        trials = sum(int(_num(r.get("trials"), 1)) for r in (payload.get("results") or []) if isinstance(r, dict)) or len(rows)
        total = sum(_num(r.get("credits_used")) for r in rows)
        return total / max(trials, 1), rows, where
    return None, [], ""


def comparables(offline: bool) -> tuple[Optional[float], str]:
    """Median credits per run of the tenant's AI Agent actions over 30 days (read-only, dev-team key)."""
    if offline or not (os.environ.get("TINES_TENANT") and os.environ.get("TINES_API_KEY")):
        return None, "comparables skipped (offline, or no dev-team key in the environment)"
    if (os.environ.get("TINES_ENV") or "dev") == "prod":
        return None, "comparables skipped (TINES_ENV=prod)"
    end = dt.date.today()
    start = end - dt.timedelta(days=30)
    cmd = [str(C.rpath("scripts/tines")), "ai-usage", "--start_date", start.isoformat(), "--end_date", end.isoformat(), "--group_by", "action", "--json"]
    try:
        p = subprocess.run(cmd, cwd=str(C.repo_root()), capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None, "comparables unavailable (ai-usage did not run)"
    if p.returncode != 0:
        return None, "comparables unavailable (ai-usage failed: " + C.truncate(p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "?", 120) + ")"
    try:
        rows = (json.loads(p.stdout) or {}).get("rows") or []
    except json.JSONDecodeError:
        return None, "comparables unavailable (ai-usage output was not JSON)"
    per_run = [_num(r.get("credits_used")) / _num(r.get("usage_count"), 0) for r in rows if isinstance(r, dict) and _num(r.get("usage_count"), 0) > 0]
    if not per_run:
        return None, "no comparable AI Agent action in the last 30 days"
    return statistics.median(per_run), f"median of {len(per_run)} action(s) over 30 days (usage_count as runs — VERIFY E5)"


def eval_trials(slug: str, machine: C.Machine) -> tuple[int, int, int]:
    """(cases, model-graded cases, total trials) from sdlc/work/<slug>/evals/cases.yaml."""
    path = C.work_dir(slug) / "evals" / "cases.yaml"
    doc = C.read_yaml(path, required=False) or {}
    cases = [c for c in (doc.get("cases") or []) if isinstance(c, dict)]
    k_default = int(_num(((doc.get("defaults") or {}).get("k")), machine.thresholds.get("eval_k_default", 3)))
    graded = [c for c in cases if c.get("kind") == "model_graded"]
    trials = sum(int(_num(c.get("k"), k_default)) if c.get("kind") == "model_graded" else 1 for c in cases)
    return len(cases), len(graded), trials


def schedule_interval(contract: Optional[dict[str, Any]], meta: Optional[dict[str, Any]]) -> int:
    entry = (contract or {}).get("entry") or {}
    value = entry.get("schedule_interval_seconds") if entry.get("type") == "schedule" else None
    if not value:
        value = (meta or {}).get("schedule_interval_seconds")
    return int(_num(value, 0))


def committed_estimates(slug: str) -> float:
    tracker = C.load_tracker(required=False)
    if tracker is None:
        return 0.0
    total = 0.0
    for row in tracker.rows:
        if row.get("key") == slug or row.get("phase") not in COMMITTED_PHASES:
            continue
        total += _num(((row.get("credit_estimate") or {}) if isinstance(row.get("credit_estimate"), dict) else {}).get("monthly"))
    return total


def estimate(slug: str, *, offline: bool = False, runs_per_day: Optional[float] = None, credits_per_run: Optional[float] = None,
             provider: Optional[str] = None) -> dict[str, Any]:
    C.check_slug(slug)
    machine = C.load_machine()
    contract, contract_errors = C.load_contract(slug) if (C.work_dir(slug) / "design.md").is_file() else (None, [])
    meta = C.load_story_meta(slug)
    ceilings = C.load_ceilings()
    manifest = C.load_manifest()
    tracker = C.load_tracker(required=False)
    row = tracker.row(slug) if tracker else None
    attempt = int((row or {}).get("attempt") or 0)
    ce = (contract or {}).get("cost_estimate") or {}

    interval = schedule_interval(contract, meta)
    implied = 86400.0 / interval if interval > 0 else 0.0
    rpd = runs_per_day if runs_per_day is not None else _num(ce.get("runs_per_day"), implied)
    rpd = max(rpd, implied)

    obs, obs_rows, obs_where = observed_credits(slug, attempt)
    comp, comp_note = (None, "") if obs is not None or ce.get("credits_per_run_est") is not None else comparables(offline)
    if obs is not None:
        cpr, basis = obs, f"{C.truncate(str(round(obs, 4)), 12)} credits/run observed in dev ({obs_where})"
    elif ce.get("credits_per_run_est") is not None:
        cpr, basis = _num(ce.get("credits_per_run_est")), "contract.cost_estimate.credits_per_run_est (not yet observed)"
    elif comp is not None:
        cpr, basis = comp, comp_note
    elif credits_per_run is not None:
        cpr, basis = credits_per_run, "--credits-per-run (given)"
    else:
        cpr, basis = 0.0, "no AI Agent action" if not ((contract or {}).get("ai_agents") or ((meta or {}).get("ai") or {}).get("agents")) else "no observation and no estimate yet"
    prov = provider or str(ce.get("provider") or ("none" if not (contract or {}).get("ai_agents") else "tines_provided"))
    monthly = round(rpd * cpr * 30, 4)
    credits_counted = monthly if prov in ("tines_provided",) else (0.0 if prov in ("custom", "local") else monthly)

    prod_key, dev_key = team_keys(ceilings, manifest)
    teams = ceilings.get("teams") or {}
    ceiling = _num((teams.get(prod_key) or {}).get("monthly_credits")) if prod_key else 0.0
    committed = committed_estimates(slug)
    cases, graded, trials = eval_trials(slug, machine)
    eval_cost = round(trials * cpr, 4)
    dev_ceiling = _num((teams.get(dev_key) or {}).get("monthly_credits")) if dev_key else 0.0
    return {
        "story_key": slug,
        "contract_valid": contract is not None and not contract_errors,
        "estimate": {
            "runs_per_day": round(rpd, 4),
            "credits_per_run_est": round(cpr, 4),
            "monthly_credits_est": credits_counted,
            "provider": prov,
            "basis": C.truncate(f"{round(rpd, 2)} runs/day × {basis} × 30" if cpr else basis, 300),
        },
        "projection": {
            "runs_per_day": round(rpd, 4),
            "credits_per_run_observed": round(obs if obs is not None else cpr, 4),
            "monthly_credits": credits_counted,
            "provider": prov if prov in ("tines_provided", "custom", "local", "none") else "none",
            "billed_cost_note": ("custom or local provider: Tines AI credits are bypassed; the bill is billed_cost or the host" if prov in ("custom", "local")
                                 else "not applicable: Tines AI credits" if cpr else "not applicable: no model in the loop"),
        },
        "budget_fit": {"team": prod_key or "unknown", "ceiling": ceiling, "committed": round(committed, 4),
                       "remaining_after": round(ceiling - committed - credits_counted, 4)},
        "eval_run": {"cases": cases, "model_graded": graded, "trials": trials, "credits": eval_cost,
                     "team": dev_key or "unknown", "ceiling": dev_ceiling},
        "schedule": {"interval_seconds": interval, "implied_runs_per_day": round(implied, 4)},
        "comparables": comp_note or None,
        "credits_observed": obs_rows,
    }


# --------------------------------------------------------------------------------------------------------------- #
# The checks
# --------------------------------------------------------------------------------------------------------------- #


def _meta_agents(meta: Optional[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    agents = (((meta or {}).get("ai") or {}).get("agents")) or []
    return {str(a.get("name")): a for a in agents if isinstance(a, dict) and a.get("name")}


def _export(slug: str) -> Optional[dict[str, Any]]:
    path = C.rpath(f"stories/{slug}/story.json")
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or str(data.get("description") or "").startswith("SKELETON"):
        return None
    return data


def prefiltered_from_export(export: dict[str, Any]) -> dict[str, bool]:
    agents = [a for a in (export.get("agents") or [])]
    links = [l for l in (export.get("links") or []) if isinstance(l, dict)]
    preds: dict[int, set[int]] = {}
    for l in links:
        s, r = l.get("source"), l.get("receiver")
        if isinstance(s, int) and isinstance(r, int):
            preds.setdefault(r, set()).add(s)
    out = {}
    for i, a in enumerate(agents):
        if not isinstance(a, dict) or a.get("type") != LLM_TYPE:
            continue
        seen, stack, found = set(), list(preds.get(i, ())), False
        while stack:
            j = stack.pop()
            if j in seen:
                continue
            seen.add(j)
            if 0 <= j < len(agents) and isinstance(agents[j], dict) and agents[j].get("type") == TRIGGER_TYPE:
                found = True
                break
            stack.extend(preds.get(j, ()))
        out[str(a.get("name") or i)] = found
    return out


def run_checks(slug: str, *, offline: bool = True, est: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """The cost checks cost.4–cost.9 as structured results (used by --check, ready and verify-merge)."""
    est = est or estimate(slug, offline=offline)
    contract = C.load_contract(slug)[0] if (C.work_dir(slug) / "design.md").is_file() else None
    meta = C.load_story_meta(slug)
    agents = [a for a in ((contract or {}).get("ai_agents") or []) if isinstance(a, dict)]
    meta_agents = _meta_agents(meta)
    results: list[dict[str, str]] = []

    def add(cid: str, ok: bool, detail: str) -> None:
        results.append({"id": cid, "result": "PASS" if ok else "FAIL", "detail": C.truncate(detail, 400)})

    # cost.4
    if not agents:
        add("cost.4", True, "no AI Agent action")
    else:
        bad = []
        for a in agents:
            name = str(a.get("name"))
            m = meta_agents.get(name, {})
            agentic = bool(a.get("tools")) or bool(a.get("skills")) or bool(m.get("code_analysis")) or bool(m.get("web_search"))
            tier, pinned = a.get("model_tier"), bool(a.get("model_pinned"))
            if agentic and tier == "fast" and not pinned:
                bad.append(f"{name}: agentic ({'tools' if a.get('tools') else 'skills'}) on fast without a pinned model — it would default to smart")
            if agentic and tier == "fast" and pinned and not m.get("model"):
                bad.append(f"{name}: fast model pinned in the contract but not recorded in story.meta.yaml ai.agents[].model")
        add("cost.4", not bad, "; ".join(bad) or f"{len(agents)} agent(s): model tiers consistent with their capabilities")
    # cost.5
    implied = est["schedule"]["implied_runs_per_day"]
    stated = _num(((contract or {}).get("cost_estimate") or {}).get("runs_per_day"), est["estimate"]["runs_per_day"])
    if implied == 0:
        add("cost.5", True, "event-driven (schedule_interval_seconds 0); no schedule implies runs")
    else:
        add("cost.5", implied <= stated + 1e-9, f"schedule implies {implied:g} runs/day; contract says {stated:g}")
    # cost.6
    fit = est["budget_fit"]
    monthly = est["projection"]["monthly_credits"]
    if monthly == 0:
        add("cost.6", True, "0 credits a month")
    elif fit["ceiling"] <= 0:
        add("cost.6", False, f"no monthly_credits ceiling for team {fit['team']!r} in policies/cost-ceilings.yml")
    else:
        add("cost.6", fit["remaining_after"] >= 0, f"{monthly:g} credits/month vs {fit['ceiling']:g} − {fit['committed']:g} committed on {fit['team']}")
    # cost.7
    prov = est["estimate"]["provider"]
    counted = _num(((contract or {}).get("cost_estimate") or {}).get("monthly_credits_est"), 0)
    if prov in ("custom", "local"):
        add("cost.7", counted == 0, "custom/local provider: billed_cost, credits bypassed" + ("" if counted == 0 else f" — but the contract counts {counted:g} credits"))
    else:
        add("cost.7", True, f"provider {prov}")
    # cost.8
    if not agents:
        add("cost.8", True, "no AI Agent action to pre-filter")
    else:
        export = _export(slug)
        missing = []
        if export is not None:
            pf = prefiltered_from_export(export)
            missing = [n for n, ok in pf.items() if not ok]
            where = "the export's links"
        else:
            outline = [a for a in ((contract or {}).get("actions_outline") or []) if isinstance(a, dict)]
            names = [str(a.get("name")) for a in outline]
            for a in agents:
                name = str(a.get("name"))
                if name not in names:
                    missing.append(f"{name} (not in actions_outline)")
                    continue
                idx = names.index(name)
                if not any("trigger" in str(o.get("type", "")).lower() for o in outline[:idx]):
                    missing.append(name)
            where = "contract.actions_outline order"
        add("cost.8", not missing, (f"no Trigger upstream of: {', '.join(missing)}" if missing else "every AI Agent action has a Trigger upstream") + f" ({where})")
    # cost.9
    ev = est["eval_run"]
    if ev["credits"] == 0:
        add("cost.9", True, "the eval run costs 0 credits" + (" (no model-graded case)" if ev["model_graded"] == 0 else ""))
    elif ev["ceiling"] <= 0:
        add("cost.9", False, f"no monthly_credits ceiling for the dev team ({ev['team']!r})")
    else:
        add("cost.9", ev["credits"] <= ev["ceiling"], f"{ev['trials']} trial(s) × {est['estimate']['credits_per_run_est']:g} = {ev['credits']:g} credits vs the dev ceiling {ev['ceiling']:g}")
    return {"story_key": slug, "results": results, "projection": est["projection"], "budget_fit": est["budget_fit"],
            "passed": all(r["result"] == "PASS" for r in results)}


def gb_budget(slug: str, est: dict[str, Any], machine: C.Machine) -> dict[str, Any]:
    """GB at the design → build boundary: warn at budget_warn_pct, park at budget_park_pct."""
    warn = _num(machine.thresholds.get("budget_warn_pct"), 80)
    park = _num(machine.thresholds.get("budget_park_pct"), 100)
    reasons, warnings = [], []
    fit = est["budget_fit"]
    monthly = est["projection"]["monthly_credits"]
    if monthly > 0:
        if fit["ceiling"] <= 0:
            reasons.append(f"no monthly_credits ceiling for team {fit['team']!r}")
        else:
            pct = 100.0 * (fit["committed"] + monthly) / fit["ceiling"]
            if pct >= park:
                reasons.append(f"{fit['team']}: {pct:.0f}% of {fit['ceiling']:g} credits with this story (park at {park:g}%)")
            elif pct >= warn:
                warnings.append(f"{fit['team']}: {pct:.0f}% of {fit['ceiling']:g} credits with this story (warn at {warn:g}%)")
    ev = est["eval_run"]
    if ev["credits"] > 0:
        if ev["ceiling"] <= 0:
            reasons.append(f"no monthly_credits ceiling for the dev team ({ev['team']!r})")
        else:
            pct = 100.0 * ev["credits"] / ev["ceiling"]
            if pct >= park:
                reasons.append(f"the eval run ({ev['credits']:g} credits) is {pct:.0f}% of the dev ceiling")
            elif pct >= warn:
                warnings.append(f"the eval run ({ev['credits']:g} credits) is {pct:.0f}% of the dev ceiling")
    return {"decision": "park" if reasons else ("warn" if warnings else "ok"), "reasons": reasons, "warnings": warnings}


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="sdlc estimate", description="Credit estimate; --check runs the cost checks cost.4–cost.9.")
    C.add_root_args(p)
    p.add_argument("slug")
    p.add_argument("--check", action="store_true", help="run the cost checks; exit 1 on any FAIL")
    p.add_argument("--json", action="store_true", help="with --check: print the full result as JSON")
    p.add_argument("--offline", action="store_true", help="do not read ai-usage comparables")
    p.add_argument("--runs-per-day", type=float, help="before the contract exists")
    p.add_argument("--credits-per-run", type=float, help="before anything is observed")
    p.add_argument("--provider", choices=["tines_provided", "custom", "local", "none"])
    args = p.parse_args(argv)
    C.apply_root_args(args)
    est = estimate(args.slug, offline=args.offline or args.check, runs_per_day=args.runs_per_day,
                   credits_per_run=args.credits_per_run, provider=args.provider)
    if not args.check:
        C.print_json(est)
        return 0
    result = run_checks(args.slug, est=est)
    if args.json:
        C.print_json(result)
    else:
        for r in result["results"]:
            print(f"{r['result']:<4} {r['id']:<7} {r['detail']}")
        print(json.dumps({"projection": result["projection"], "budget_fit": result["budget_fit"]}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScriptError:
        raise
    except KeyboardInterrupt:  # pragma: no cover
        eprint("interrupted")
        sys.exit(130)
