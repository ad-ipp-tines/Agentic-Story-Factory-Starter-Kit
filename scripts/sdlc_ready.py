#!/usr/bin/env python3
"""``./scripts/sdlc ready <slug>`` — G1 (readiness, deterministic) and GB (budget and WIP) at the design → build boundary.

Spec: REPO-DESIGN.md §4.5 (the G1 checks), §4.4 (02 design), §5.3.7 (the cost checks), sdlc/gates/G1-readiness.md (the
twelve checks, numbered as there) and sdlc/gates/GB-budget.md. Run by the person (allow) and by ``sdlc.yml`` on the
design PR. Exit 0 when every check passes, 1 otherwise; the JSON result names each check and its reason.

  1  the contract block validates (sdlc/templates/story-contract.schema.json)
  2  at least one testable acceptance criterion
  3  every criterion maps to at least one case; at least one should-not case; every model-graded case has a rubric and a
     reference output; every input_ref resolves (a file in stories/<slug>/tests/, or tests/expectations.yaml#variants.<name>)
     and stays inside stories/<slug>/tests/ once resolved (no absolute path, no '..', no dotfile, no symlink out)
  4  the contract's credentials and Resources are named in stories/<slug>/story.meta.yaml
  5  every AI Agent action has a budget_ref and the line exists in policies/cost-ceilings.yml
  6  stories/_manifest.yaml has an entry (new: true until the first ship commits a prod id)
  7  the contract's needs fit the tenant's entitlements (kit/tenant/config.yaml)
  8  the touch set is respected: the branch's changes sit inside the discover + design touch sets, the patch files change
     only inside their allow-listed paths, and contract.touch_set sits inside the design and build touch sets
  9  ./scripts/sdlc estimate --check passes (cost.4–cost.9)
 10  GB: this story's estimate plus the committed estimates fit the team's ceiling, and the eval run fits the dev team's
 11  every spike under sdlc/work/<slug>/spikes/ has decision go or no_go
 12  WIP: the owner has fewer than wip_limit_per_owner stories in build or verify on main
A failing 10 or 12 opens GB (``gb.decision: park``) — ``./scripts/sdlc advance`` then parks the story — rather than just
failing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sdlc_common as C  # noqa: E402
import sdlc_estimate as E  # noqa: E402

NAMES = {
    1: "contract validates", 2: "testable acceptance criterion", 3: "cases cover every criterion", 4: "names in meta",
    5: "budget lines", 6: "manifest entry", 7: "entitlements fit", 8: "touch set respected", 9: "cost checks",
    10: "budget (GB)", 11: "spikes decided", 12: "WIP (GB)",
}


def _names(items: Any) -> set[str]:
    out = set()
    for item in items or []:
        if isinstance(item, str):
            out.add(item.split("#")[0].strip())
        elif isinstance(item, dict) and item.get("name"):
            out.add(str(item["name"]))
    return out


def confine_input_path(slug: str, path: str, also: Optional[Path] = None) -> tuple[Optional[Path], Optional[str]]:
    """(the resolved file, None) when ``path`` may be read as an eval input, else (None, why not).

    An input is posted to a dev Webhook by ``eval-run``, so it is confined: a relative path with no ``..`` and no
    dotfile component, whose resolved location (symlinks followed) sits inside ``stories/<slug>/tests/`` — or, when
    ``also`` is given, is exactly that file (``eval-run --cases``: a ``#variants.<name>`` ref into the cases file being
    run). An absolute path, ``stories/<slug>/tests/../../../.env`` or a symlink out of ``tests/`` is refused.
    """
    raw = str(path or "").strip()
    if not raw:
        return None, "empty path"
    parts = Path(raw).parts
    if Path(raw).is_absolute() or raw.startswith(("/", "\\", "~")):
        return None, f"{raw}: an absolute path is not an input (inputs live in stories/{slug}/tests/)"
    if any(p == ".." or p.startswith(".") for p in parts):
        return None, f"{raw}: '..' and dotfiles are not inputs (inputs live in stories/{slug}/tests/)"
    full = C.rpath(raw).resolve()
    tests = C.rpath(f"stories/{slug}/tests").resolve()
    allowed = full.is_relative_to(tests) or (also is not None and full == also.resolve())
    if not allowed:
        return None, f"{raw}: inputs live in stories/{slug}/tests/"
    if not full.is_file():
        return None, f"{raw} does not exist"
    return full, None


def resolve_input_ref(slug: str, ref: str) -> Optional[str]:
    """None when the input_ref resolves (inside stories/<slug>/tests/, never outside it), else why not."""
    ref = str(ref or "").strip()
    if not ref:
        return "empty input_ref"
    if "#" in ref:
        path, frag = ref.split("#", 1)
        full, why = confine_input_path(slug, path)
        if why or full is None:
            return why
        m = re.fullmatch(r"variants\.([A-Za-z0-9_-]+)", frag)
        if not m:
            return f"{ref}: only #variants.<name> is supported"
        doc = C.read_yaml(full, required=False) or {}
        variants = doc.get("variants")
        names = set(variants) if isinstance(variants, dict) else {str(v.get("name")) for v in (variants or []) if isinstance(v, dict)}
        return None if m.group(1) in names else f"{ref}: no such variant"
    return confine_input_path(slug, ref)[1]


def sample_path(glob: str) -> str:
    return glob.replace("**", "x/y").replace("*", "x")


def run_ready(slug: str) -> dict[str, Any]:
    C.check_slug(slug)
    lc = C.load_lifecycle()
    machine, touch = lc.machine, lc.touch
    checks: list[dict[str, Any]] = []

    def add(n: int, ok: bool, reason: str) -> None:
        checks.append({"id": f"G1.{n}", "name": NAMES[n], "result": "PASS" if ok else "FAIL", "reason": C.truncate(reason, 600)})

    contract, errors = C.load_contract(slug)
    add(1, contract is not None and not errors, "; ".join(errors[:4]) or "the contract validates")
    c = contract or {}
    acs = [a for a in (c.get("acceptance_criteria") or []) if isinstance(a, dict)]
    testable = [a for a in acs if str(a.get("then") or "").strip()]
    add(2, bool(testable), f"{len(testable)} acceptance criteria" if testable else "no acceptance criterion with a `then`")

    cases_doc = C.read_yaml(C.work_dir(slug) / "evals" / "cases.yaml", required=False) or {}
    cases = [x for x in (cases_doc.get("cases") or []) if isinstance(x, dict)]
    problems = []
    if not cases:
        problems.append("sdlc/work/<slug>/evals/cases.yaml has no cases")
    covered = {str(cv) for x in cases for cv in (x.get("covers") or [])}
    missing = [str(a.get("id")) for a in acs if str(a.get("id")) not in covered]
    if missing:
        problems.append(f"no case covers {missing}")
    if cases and not any(x.get("should_trigger") is False for x in cases):
        problems.append("no should-not case (should_trigger: false)")
    for x in cases:
        if x.get("kind") == "model_graded" and not (x.get("rubric") and x.get("reference_output") is not None):
            problems.append(f"{x.get('id')}: model-graded without rubric and reference_output")
        why = resolve_input_ref(slug, str(x.get("input_ref") or ""))
        if why:
            problems.append(f"{x.get('id')}: {why}")
    add(3, not problems, "; ".join(problems[:6]) or f"{len(cases)} cases cover {len(acs)} criteria")

    meta = C.load_story_meta(slug)
    if meta is None:
        add(4, False, f"stories/{slug}/story.meta.yaml does not exist")
    else:
        miss = sorted(set(c.get("credentials") or []) - _names(meta.get("credentials"))) + sorted(set(c.get("resources") or []) - _names(meta.get("resources")))
        add(4, not miss, f"not named in story.meta.yaml: {miss}" if miss else "credentials and Resources named in meta")

    ceilings = C.load_ceilings()
    lines = set((ceilings.get("agents") or {}).keys())
    agents = [a for a in (c.get("ai_agents") or []) if isinstance(a, dict)]
    bad = [f"{a.get('name')} (budget_ref {a.get('budget_ref')!r})" for a in agents if not a.get("budget_ref") or a.get("budget_ref") not in lines]
    add(5, not bad, f"no budget line for: {bad}" if bad else (f"{len(agents)} agent(s) with budget lines" if agents else "no AI Agent action"))

    entry = C.manifest_entry(slug)
    if entry is None:
        add(6, False, f"stories/_manifest.yaml has no entry for {slug} (the architect's manifest patch sets new: true)")
    else:
        prod_id = int(((entry.get("prod") or {}).get("story_id")) or 0)
        add(6, bool(entry.get("new")) or prod_id > 0, "entry present" + (" (new: true)" if entry.get("new") else f" (prod id {prod_id})") if (entry.get("new") or prod_id) else "entry has neither new: true nor a prod story id")

    config = C.load_tenant_config()
    if config is None:
        add(7, False, f"{C.TENANT_CONFIG} does not exist, so entitlements cannot be checked (the kit's config commit, or filled by hand on the Community path)")
    else:
        ent = C.entitlements(config)
        needs = []
        if c.get("records"):
            needs.append("records")
        if agents:
            needs.append("ai_agent_action")
        page_level = ((c.get("access") or {}).get("page") or {}).get("level")
        if (c.get("entry") or {}).get("type") == "page" or page_level not in (None, "none"):
            needs.append("pages")
        lacking = [n for n in needs if ent.get(n) is not True]
        note = " (mode-1-preset: whether Workbench is an add-on is VERIFY K28)" if (c.get("mode") or {}).get("value") == "mode-1-preset" else ""
        add(7, not lacking, (f"not entitled (or not stated) in {C.TENANT_CONFIG}: {lacking}" if lacking else f"needs {needs or 'nothing extra'} fit") + note)

    ref = C.main_ref()
    if ref is None:
        add(8, False, "not a git checkout with a main ref: the branch diff cannot be checked (fail closed)")
    else:
        branch = C.current_branch() or ""
        rule = C.branch_rule(touch, branch)
        if rule and rule.get("slug") == slug and rule.get("phases"):
            files, patches = C.allowed_for(touch, phases=list(rule["phases"]))
        else:
            files, patches = C.allowed_for(touch, phases=["discover", "design"])
        changed = C.working_changes(ref)
        viol = C.touch_violations(changed, slug=slug, files=files, patches=patches, touch=touch, base_ref=ref, head_reader=C.read_head_file)
        design_build = C.allowed_for(touch, phases=["design", "build"])[0]
        outside = [g for g in (c.get("touch_set") or []) if not C.path_allowed(sample_path(str(g).replace("<slug>", slug)), design_build, slug)]
        if outside:
            viol.append(f"contract.touch_set entries outside the design and build touch sets: {outside}")
        add(8, not viol, "; ".join(viol[:6]) or f"{len(changed)} changed path(s) inside the design touch set")

    est = E.estimate(slug, offline=True)
    cost = E.run_checks(slug, offline=True, est=est)
    failing = [f"{r['id']}: {r['detail']}" for r in cost["results"] if r["result"] == "FAIL"]
    add(9, cost["passed"], "; ".join(failing) or "cost.4–cost.9 PASS")

    gb = E.gb_budget(slug, est, machine)
    add(10, gb["decision"] != "park", "; ".join(gb["reasons"] + gb["warnings"]) or "within the ceilings")

    spikes_dir = C.work_dir(slug) / "spikes"
    undecided = []
    for f in sorted(spikes_dir.glob("*.md")) if spikes_dir.is_dir() else []:
        fm = C.read_front_matter(f) or {}
        if fm.get("decision") not in ("go", "no_go"):
            undecided.append(f.name)
    add(11, not undecided, f"undecided: {undecided}" if undecided else "no open spike")

    tracker = C.load_tracker(required=False)
    row = tracker.row(slug) if tracker else None
    wip_reasons = []
    if row is not None:
        limit = (tracker.wip_limit if tracker else None) or machine.cap("wip_limit_per_owner", 1)
        mt = C.tracker_at(ref) if ref else None
        rows = mt.rows if mt else (tracker.rows if tracker else [])
        busy = [r.get("key") for r in rows if r.get("owner") == row.get("owner") and r.get("key") != slug and r.get("phase") in ("build", "verify")]
        if len(busy) >= limit:
            wip_reasons.append(f"owner {row.get('owner')} has {len(busy)} stor(y/ies) in build or verify ({', '.join(map(str, busy))}); limit {limit}")
    add(12, not wip_reasons, "; ".join(wip_reasons) or "within the WIP limit")

    gb_reasons = list(gb["reasons"]) + wip_reasons
    result = {
        "story_key": slug,
        "gate": "G1",
        "result": "pass" if all(x["result"] == "PASS" for x in checks) else "fail",
        "checks": checks,
        "gb": {"decision": "park" if gb_reasons else gb["decision"], "reasons": gb_reasons, "warnings": gb["warnings"]},
        "cost": {"projection": cost["projection"], "budget_fit": cost["budget_fit"]},
    }
    return result


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="sdlc ready", description="G1 readiness + GB at the design → build boundary.")
    C.add_root_args(p)
    p.add_argument("slug")
    args = p.parse_args(argv)
    C.apply_root_args(args)
    result = run_ready(args.slug)
    C.print_json(result)
    return 0 if result["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
