#!/usr/bin/env python3
"""Read AI usage — and, with ``--check-ceilings``, compare it with policies/cost-ceilings.yml. Read-only.

Endpoint (DESIGN.md §3.5 ``ai-usage``, §5.3 "Credit usage", §6.1)
-----------------------------------------------------------------
``GET /api/v1/ai_usage`` with ``relative_date`` **or** ``start_date`` +
``end_date``, ``group_by`` (``story`` | ``team`` | ``action`` | ``day``; ``feature``
appears in DESIGN.md §10 #11) and ``story_id``. Row fields named in the
research: ``credits_used``, ``billed_cost``, input / output / cached tokens,
``usage_count``. Flag spellings follow the API parameters (``--relative_date``,
``--group_by``) and the hyphenated forms work too.

Credits and cost are different things: an AI Agent action on a custom provider
bypasses Tines AI credits but still bills externally (``billed_cost``). Both
columns are printed so the two are never confused (AGENTS.md §8).

``--check-ceilings`` — the budget job of ``.github/workflows/drift.yml``
-----------------------------------------------------------------------
Reads ``policies/cost-ceilings.yml`` (the single source of budgets) and makes
these calls, nothing else:

* stories, today:        ``relative_date=today&group_by=story`` vs
                         ``runtime.credit_budget_daily_default`` (per-story
                         overrides live in the ``ops_limits`` Resource in the
                         tenant, not in the repository)
* teams, month to date:  ``start_date=<1st>&end_date=<today>&group_by=team`` vs
                         ``teams.<name>.monthly_credits``; the tenant total vs
                         ``tenant.monthly_credit_budget`` when it is not 0
* agents, today:         for each ``agents.<slug>/<action>`` line whose slug has
                         a story id in ``--env``: ``story_id=<id>&relative_date=
                         today&group_by=action`` — tokens vs
                         ``daily_tokens_notify`` (the Status-tab alert should
                         already have fired; this is the cross-check)

A row at or above ``--threshold-pct`` (default: the first value of
``runtime.credit_alert_pct``, 80) is a breach; at or above the second value
(95) it is ``critical``. 80 % is the actionable alert because at 100 % the
platform stops the story. Output: a JSON object on stdout (``breaches``,
``stories``, ``teams``, ``agents``, ``tenant``, ``notes``) and, with
``--report-file``, a Markdown report for an issue body or a job summary.

Known unknowns (VERIFY, docs/VERIFY.md E5)
------------------------------------------
* The response baton, the identity keys of each row (``story_id`` /
  ``story_name``, ``team_id`` / ``team_name``, ``action_name``), the token key
  names, and the date format of ``start_date`` / ``end_date`` (``YYYY-MM-DD`` is
  sent). A team is matched by ``team_id`` when its ceiling entry carries one,
  then by the manifest environment of the same name, then by name.
* Which time zone ``relative_date=today`` uses (the tenant's, most likely).

Examples
--------
    ./scripts/tines ai-usage --relative_date today --group_by story
    ./scripts/tines ai-usage --start_date 2026-09-01 --end_date 2026-09-25 --group_by team --json
    ./scripts/tines ai-usage --story-id 123 --relative_date today --group_by action
    ./scripts/tines ai-usage --env prod --check-ceilings --report-file budget.md     # drift.yml, CI
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    POLICIES_DIR,
    ScriptError,
    client_from_env,
    eprint,
    find_repo_root,
    guard_prod,
    load_manifest,
    load_yaml_file,
    utc_now,
)
from tines_read import api_or_exit, default_env, extract_rows, fmt, markdown_table, num  # noqa: E402

PATH = "/api/v1/ai_usage"
ROW_KEYS = ("ai_usage", "usage", "results", "data")
IDENTITY_KEYS = ("story_id", "story_name", "team_id", "team_name", "action_id", "action_name", "date", "day", "feature", "name")
GROUP_BY = ("story", "team", "action", "day", "feature")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai_usage.py",
        description="Read AI usage; --check-ceilings compares it with policies/cost-ceilings.yml (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    parser.add_argument("--env", default=None, help="manifest environment, for the prod guard and story ids (default: $TINES_ENV or dev)")
    parser.add_argument("--relative_date", "--relative-date", dest="relative_date", help="e.g. today")
    parser.add_argument("--start_date", "--start-date", dest="start_date", help="YYYY-MM-DD (format VERIFY)")
    parser.add_argument("--end_date", "--end-date", dest="end_date", help="YYYY-MM-DD (format VERIFY)")
    parser.add_argument("--group_by", "--group-by", dest="group_by", choices=GROUP_BY, help="aggregation")
    parser.add_argument("--story-id", "--story_id", dest="story_id", type=int, help="limit to one story")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    parser.add_argument(
        "--check-ceilings",
        nargs="?",
        const=str(Path(POLICIES_DIR) / "cost-ceilings.yml"),
        metavar="PATH",
        help="compare today's and this month's usage with policies/cost-ceilings.yml (default path)",
    )
    parser.add_argument("--threshold-pct", type=float, help="breach threshold (default: runtime.credit_alert_pct[0], else 80)")
    parser.add_argument("--report-file", type=Path, help="with --check-ceilings: write a Markdown report here")
    parser.add_argument("--fail-on-breach", action="store_true", help="with --check-ceilings: exit 3 when anything is at or above the threshold")
    return parser


# --------------------------------------------------------------------------- #
# Rows
# --------------------------------------------------------------------------- #


def tokens_of(row: dict[str, Any]) -> Optional[float]:
    """Total tokens for a row: ``total_tokens`` if present, else input + output (key names VERIFY E5)."""
    total = num(row.get("total_tokens"))
    if total is not None:
        return total
    parts = [num(row.get(k)) for k in ("input_tokens", "output_tokens")]
    parts = [p for p in parts if p is not None]
    return sum(parts) if parts else None


def fetch(client: Any, **params: Any) -> list[dict[str, Any]]:
    query = {k: v for k, v in params.items() if v not in (None, "")}
    eprint(f"[ai-usage] GET {PATH} {query}")
    return extract_rows(api_or_exit(client.get, PATH, **query), ROW_KEYS)


def row_columns(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    present = [k for k in IDENTITY_KEYS if any(k in r for r in rows)]
    metrics = ["credits_used", "billed_cost", "usage_count"]
    token_keys = sorted({k for r in rows for k in r if "token" in k.lower()})
    return [(k, k) for k in present + metrics + token_keys]


# --------------------------------------------------------------------------- #
# Ceilings
# --------------------------------------------------------------------------- #


def _level(pct: float, warn: float, critical: float) -> Optional[str]:
    if pct >= critical:
        return "critical"
    if pct >= warn:
        return "warn"
    return None


def _manifest_team_ids(root: Path) -> dict[str, int]:
    try:
        manifest = load_manifest(root)
    except SystemExit:
        return {}
    out: dict[str, int] = {}
    for name, cfg in (manifest.get("environments") or {}).items():
        try:
            tid = int((cfg or {}).get("team_id") or 0)
        except (TypeError, ValueError):
            continue
        if tid > 0:
            out[str(name)] = tid
    return out


def _manifest_story_ids(root: Path, env_name: str) -> dict[str, int]:
    try:
        manifest = load_manifest(root)
    except SystemExit:
        return {}
    out: dict[str, int] = {}
    for slug, entry in (manifest.get("stories") or {}).items():
        try:
            sid = int((((entry or {}).get(env_name)) or {}).get("story_id") or 0)
        except (TypeError, ValueError):
            continue
        if sid > 0:
            out[str(slug)] = sid
    return out


def _match_team(rows: list[dict[str, Any]], key: str, cfg: dict[str, Any], env_team_ids: dict[str, int]) -> tuple[Optional[dict[str, Any]], str]:
    wanted_id = None
    how = ""
    try:
        if int(cfg.get("team_id") or 0) > 0:
            wanted_id, how = int(cfg["team_id"]), "ceiling team_id"
    except (TypeError, ValueError):
        pass
    if wanted_id is None and key in env_team_ids:
        wanted_id, how = env_team_ids[key], f"manifest environments.{key}.team_id"
    if wanted_id is not None:
        for r in rows:
            try:
                if int(r.get("team_id")) == wanted_id:
                    return r, how
            except (TypeError, ValueError):
                continue
        return None, how
    for r in rows:
        label = str(r.get("team_name") or r.get("name") or "").strip().casefold()
        if label and label == key.casefold():
            return r, "team name"
    return None, "team name"


def check_ceilings(client: Any, root: Path, env_name: str, ceilings_path: Path, threshold: Optional[float]) -> dict[str, Any]:
    if not ceilings_path.exists():
        raise ScriptError(f"{ceilings_path} not found")
    ceilings = load_yaml_file(ceilings_path) or {}
    runtime = ceilings.get("runtime") or {}
    alert = [num(x) for x in (runtime.get("credit_alert_pct") or [80, 95])]
    warn = threshold if threshold is not None else (alert[0] if alert and alert[0] is not None else 80.0)
    critical = alert[1] if len(alert) > 1 and alert[1] is not None else 100.0
    today = _dt.datetime.now(_dt.timezone.utc).date()
    start = today.replace(day=1)
    report: dict[str, Any] = {
        "checked_at": utc_now(),
        "env": env_name,
        "threshold_pct": warn,
        "critical_pct": critical,
        "window": {"today": today.isoformat(), "month_start": start.isoformat()},
        "stories": [],
        "teams": [],
        "agents": [],
        "tenant": None,
        "breaches": [],
        "notes": [],
    }

    # -- stories, today, vs the daily default ---------------------------------- #
    budget = num(runtime.get("credit_budget_daily_default"))
    story_rows = fetch(client, relative_date="today", group_by="story")
    if not budget or budget <= 0:
        report["notes"].append("runtime.credit_budget_daily_default is not set; per-story check skipped")
    for r in story_rows:
        used = num(r.get("credits_used")) or 0.0
        entry = {"scope": "story", "window": "today", "story_id": r.get("story_id"),
                 "name": r.get("story_name") or r.get("name"), "credits_used": used,
                 "billed_cost": num(r.get("billed_cost")), "budget": budget}
        if budget and budget > 0:
            entry["pct"] = round(used / budget * 100, 1)
            level = _level(entry["pct"], warn, critical)
            if level:
                entry["level"] = level
                report["breaches"].append(entry)
        report["stories"].append(entry)
    report["stories"].sort(key=lambda e: -(e.get("credits_used") or 0))

    # -- teams and tenant, month to date --------------------------------------- #
    team_rows = fetch(client, start_date=start.isoformat(), end_date=today.isoformat(), group_by="team")
    env_team_ids = _manifest_team_ids(root)
    for key, cfg in (ceilings.get("teams") or {}).items():
        cfg = cfg or {}
        monthly = num(cfg.get("monthly_credits"))
        row, how = _match_team(team_rows, str(key), cfg, env_team_ids)
        used = num((row or {}).get("credits_used")) or 0.0
        entry = {"scope": "team", "window": "month_to_date", "team": key, "matched_by": how if row else None,
                 "team_id": (row or {}).get("team_id"), "credits_used": used,
                 "billed_cost": num((row or {}).get("billed_cost")), "budget": monthly}
        if row is None:
            report["notes"].append(
                f"no usage row matched team '{key}' (by {how}); either it used nothing this month or the row shape "
                "differs — add `team_id:` to its entry in policies/cost-ceilings.yml (VERIFY E5)"
            )
        if monthly and monthly > 0:
            entry["pct"] = round(used / monthly * 100, 1)
            level = _level(entry["pct"], warn, critical)
            if level:
                entry["level"] = level
                report["breaches"].append(entry)
        report["teams"].append(entry)

    tenant = ceilings.get("tenant") or {}
    tenant_budget = num(tenant.get("monthly_credit_budget"))
    tenant_used = sum(num(r.get("credits_used")) or 0.0 for r in team_rows)
    tenant_entry: dict[str, Any] = {"scope": "tenant", "window": "month_to_date", "credits_used": tenant_used,
                                    "billed_cost": sum(num(r.get("billed_cost")) or 0.0 for r in team_rows),
                                    "budget": tenant_budget}
    if tenant_budget and tenant_budget > 0:
        tenant_alert = [num(x) for x in (tenant.get("alert_pct") or [80, 100])]
        t_warn = threshold if threshold is not None else (tenant_alert[0] or 80.0)
        t_crit = tenant_alert[1] if len(tenant_alert) > 1 and tenant_alert[1] is not None else 100.0
        tenant_entry["pct"] = round(tenant_used / tenant_budget * 100, 1)
        level = _level(tenant_entry["pct"], t_warn, t_crit)
        if level:
            tenant_entry["level"] = level
            report["breaches"].append(tenant_entry)
    else:
        report["notes"].append("tenant.monthly_credit_budget is 0 (unknown); tenant check skipped")
    report["tenant"] = tenant_entry

    # -- agents, today, tokens vs the Status-tab notify threshold -------------- #
    story_ids = _manifest_story_ids(root, env_name)
    by_story: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for ref, cfg in (ceilings.get("agents") or {}).items():
        slug, _, action = str(ref).partition("/")
        by_story.setdefault(slug, []).append((action, cfg or {}))
    for slug, agents in by_story.items():
        sid = story_ids.get(slug)
        if not sid:
            report["notes"].append(f"agents of {slug}: no story id in {env_name}; token cross-check skipped")
            continue
        rows = fetch(client, story_id=sid, relative_date="today", group_by="action")
        for action, cfg in agents:
            row = next((r for r in rows if str(r.get("action_name") or r.get("name") or "") == action), None)
            notify = num(cfg.get("daily_tokens_notify"))
            tokens = tokens_of(row) if row else None
            entry = {"scope": "agent", "window": "today", "agent": f"{slug}/{action}", "story_id": sid,
                     "tokens": tokens, "credits_used": num((row or {}).get("credits_used")),
                     "budget": notify, "budget_unit": "tokens"}
            if row is None:
                entry["note"] = "no usage row for this action today (or action_name differs — VERIFY E5)"
            elif tokens is not None and notify and notify > 0:
                entry["pct"] = round(tokens / notify * 100, 1)
                level = _level(entry["pct"], warn, critical)
                if level:
                    entry["level"] = level
                    report["breaches"].append(entry)
            report["agents"].append(entry)

    return report


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"## AI usage vs `policies/cost-ceilings.yml` — {report['window']['today']} ({report['env']})",
        "",
        f"Breach at ≥ {fmt(report['threshold_pct'])} % · critical at ≥ {fmt(report['critical_pct'])} %. "
        "80 % is the actionable alert: at 100 % the platform stops the story. "
        "Credits and `billed_cost` differ: a custom provider bypasses credits but still bills.",
        "",
        f"### Breaches ({len(report['breaches'])})",
        "",
    ]
    breach_cols = [("level", "level"), ("scope", "scope"), ("window", "window"), ("name", "story"), ("team", "team"),
                   ("agent", "agent"), ("credits_used", "credits"), ("tokens", "tokens"), ("budget", "budget"), ("pct", "%")]
    lines.append(markdown_table(report["breaches"], breach_cols) if report["breaches"] else "_None — every team, story and agent is below the threshold._\n")
    lines += [f"### Teams — month to date (from {report['window']['month_start']})", ""]
    lines.append(markdown_table(report["teams"], [("team", "team"), ("team_id", "team_id"), ("matched_by", "matched by"),
                                                  ("credits_used", "credits"), ("billed_cost", "billed_cost"),
                                                  ("budget", "monthly budget"), ("pct", "%")]))
    tenant = report.get("tenant") or {}
    lines += ["### Tenant — month to date", "",
              f"credits {fmt(tenant.get('credits_used'))} · billed_cost {fmt(tenant.get('billed_cost'))} · "
              f"budget {fmt(tenant.get('budget'))} · {fmt(tenant.get('pct'))} %", ""]
    lines += ["### Stories — today (top 20 by credits)", ""]
    lines.append(markdown_table(report["stories"][:20], [("story_id", "story_id"), ("name", "story"), ("credits_used", "credits"),
                                                        ("billed_cost", "billed_cost"), ("budget", "daily budget"), ("pct", "%")]))
    if report["agents"]:
        lines += ["### AI Agent actions — today, tokens vs `daily_tokens_notify`", ""]
        lines.append(markdown_table(report["agents"], [("agent", "agent"), ("tokens", "tokens"), ("credits_used", "credits"),
                                                      ("budget", "notify at"), ("pct", "%"), ("note", "note")]))
    if report["notes"]:
        lines += ["### Notes", ""] + [f"- {n}" for n in report["notes"]] + [""]
    lines.append(
        "_What has no API and is set by hand: per-team credit allocation and credit-usage alert thresholds (Admin → AI), "
        "and each AI Agent action's token alert (Status tab). Change a number here and in the tenant in the same PR._"
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_name = args.env or default_env()
    guard_prod(env_name)
    root = find_repo_root()

    if args.check_ceilings:
        if args.relative_date or args.start_date or args.end_date or args.group_by or args.story_id:
            eprint("[ai-usage] --check-ceilings chooses its own windows and grouping; the other filters are ignored")
        ceilings_path = Path(args.check_ceilings)
        if not ceilings_path.is_absolute():
            ceilings_path = root / ceilings_path
        client = client_from_env()
        report = check_ceilings(client, root, env_name, ceilings_path, args.threshold_pct)
        if args.report_file:
            args.report_file.parent.mkdir(parents=True, exist_ok=True)
            args.report_file.write_text(render_report(report), encoding="utf-8")
            eprint(f"[ai-usage] wrote {args.report_file}")
        print(json.dumps(report, indent=2))
        eprint(f"[ai-usage] {len(report['breaches'])} breach(es) at ≥ {fmt(report['threshold_pct'])} %")
        return 3 if (args.fail_on_breach and report["breaches"]) else 0

    if args.relative_date and (args.start_date or args.end_date):
        raise ScriptError("use --relative_date or --start_date/--end_date, not both")
    if bool(args.start_date) != bool(args.end_date):
        raise ScriptError("--start_date and --end_date go together")
    client = client_from_env()
    rows = fetch(client, relative_date=args.relative_date, start_date=args.start_date, end_date=args.end_date,
                 group_by=args.group_by, story_id=args.story_id)
    rows.sort(key=lambda r: -(num(r.get("credits_used")) or 0))
    totals = {
        "credits_used": sum(num(r.get("credits_used")) or 0 for r in rows),
        "billed_cost": sum(num(r.get("billed_cost")) or 0 for r in rows),
        "rows": len(rows),
    }
    if args.json:
        print(json.dumps({"env": env_name, "group_by": args.group_by, "totals": totals, "rows": rows}, indent=2))
        return 0
    window = args.relative_date or (f"{args.start_date} → {args.end_date}" if args.start_date else "default window")
    print(f"### AI usage — {env_name}, {window}, grouped by {args.group_by or 'none'}\n")
    print(markdown_table(rows, row_columns(rows)), end="")
    print(f"\ntotal credits_used: {fmt(totals['credits_used'])} · total billed_cost: {fmt(totals['billed_cost'])} · rows: {totals['rows']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
