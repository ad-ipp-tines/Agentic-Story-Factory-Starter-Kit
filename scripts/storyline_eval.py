#!/usr/bin/env python3
"""``./scripts/storyline eval-run <slug> [--k 3]`` — run a story's eval cases against its DEV copy. Never production.

Spec: REPO-DESIGN.md §5.3.8 (story-qa: how cases run), §5.3.3 (the case shape), storyline/evals/README.md (pass^k,
capability vs regression), §15.2 (storyline-evals.yml runs the runtime-agent and skill cases through this command against the
dev copy of kit-launch). Verify never needs ``/mcp``: nothing here edits a story.

How a case runs
---------------
* **The entry.** ``contract.entry.type`` decides. A **Webhook** entry: each case is posted to the story's own dev entry
  Webhook. A **Send to Story** entry (or any entry that is not a Webhook): each case is posted to the dev-only **wrapper
  story** (a Webhook entry → Send to Story into the story under test → Exit), whose dev story id is given with
  ``--entry-story-id`` — the wrapper is built with the story in the dev team and never shipped, so it has no manifest
  entry. Runtime-agent cases (``--cases storyline/evals/agents/runtime-*.cases.yaml``) go to the dev copy of ``kit-launch``
  with ``--entry-action specialist_test`` (D10).
* **The URL.** Committed exports carry ``<assigned-on-import>`` instead of a Webhook's path and secret, so the entry
  story's export is read from the dev team IN MEMORY (``export_story.entry_webhook``, the reader behind
  ``./scripts/tines webhook-url``), which returns only the entry Webhook's ``path`` and ``secret`` — no raw export is
  written to disk (``export --raw`` is refused outside GitHub Actions). The URL is built as
  ``https://<your-tenant>.tines.com/webhook/<path>/<secret>`` — **VERIFY K37** (the exact form, and draft addressing). The URL
  carries a secret: it is never printed, logged or written.
* **The run.** After each post, ``./scripts/tines runs <slug> --env dev --since <post time> --json`` finds the new run of
  the story UNDER TEST, and ``./scripts/tines runs … --events <guid>`` reads its events (secrets redacted by that
  script). How an event names its action is read defensively (``agent_name`` · ``action_name`` · ``agent.name`` · an id
  mapped through the export) — VERIFY together with K37.
* **Grading.** Deterministic cases are graded here: ``actions_fired_min``, ``must_fire``, ``must_not_fire``,
  ``result_fields`` (the keys of the ``result`` exit), ``result_field_values`` (the last exit among result / error /
  refused), ``no_error_on`` (only when action ids are known; otherwise reported as not checked). Model-graded cases run
  ``k`` trials and are **recorded, not graded**: ``story-qa`` grades them against the rubric and the reference output.
* **Credits.** Per AI Agent event, ``credits_used``, tokens and model when the event metadata carries them.

* **Inputs are confined.** Every ``input_ref`` resolves (symlinks followed) inside ``stories/<slug>/tests/`` — or, for a
  ``#variants.<name>`` ref, to the ``--cases`` file being run — with no absolute path, ``..`` or dotfile; a payload that
  matches ``tines_common.SECRET_PATTERNS`` is refused before anything is posted.

Output: ``.storyline/out/<slug>/qa-<UTC time>.json`` (local, gitignored) —
``{story_key, generated_at, entry, cases_file, k, results[{eval_id, suite, kind, should_trigger, trials, passes, pass,
observed_summary, observations[]}], credits_observed[], notes[]}``. ``--dry-run`` resolves the cases, inputs and entry
and prints the plan with no network call.

Refuses ``TINES_ENV=prod``, and any story whose dev story id is 0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import storyline_common as C  # noqa: E402
from storyline_common import ScriptError  # noqa: E402
from storyline_ready import confine_input_path  # noqa: E402
from tines_common import eprint, looks_like_secret, requests, utc_now  # noqa: E402

WEBHOOK_TYPE = "Agents::WebhookAgent"   # scripts/lint_story.py WEBHOOK_TYPE
LLM_TYPE = "Agents::LLMAgent"           # scripts/lint_story.py LLM_TYPE
EXITS = ("result", "error", "refused")


def webhook_url(tenant: str, path: str, secret: str) -> str:
    """VERIFY K37: the Webhook URL form built from an export's path and secret."""
    return f"https://{tenant}.tines.com/webhook/{path}/{secret}"


def load_cases(path: Path) -> dict[str, Any]:
    doc = C.read_yaml(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list):
        raise ScriptError(f"{C.rel(path)} has no `cases:` list")
    return doc


def load_input(slug: str, ref: str, cases_path: Optional[Path] = None) -> Any:
    """The payload an input_ref names — confined to stories/<slug>/tests/ (or, for a ``#variants.<name>`` ref, the
    cases file being run), and refused when it looks like a secret: it is POSTed to a dev Webhook."""
    ref = str(ref or "").split("  #")[0].strip()
    if "#" in ref:
        path, frag = ref.split("#", 1)
        full, why = confine_input_path(slug, path, also=cases_path)
        if why or full is None:
            raise ScriptError(f"input {ref}: {why}")
        doc = C.read_yaml(full) or {}
        m = re.fullmatch(r"variants\.([A-Za-z0-9_-]+)", frag)
        if not m:
            raise ScriptError(f"{ref}: only #variants.<name> is supported")
        variants = doc.get("variants")
        entry = variants.get(m.group(1)) if isinstance(variants, dict) else next((v for v in (variants or []) if isinstance(v, dict) and v.get("name") == m.group(1)), None)
        if not isinstance(entry, dict) or "event" not in entry:
            raise ScriptError(f"{ref}: the variant has no `event`")
        payload = entry["event"]
    else:
        full, why = confine_input_path(slug, ref)
        if why or full is None:
            raise ScriptError(f"input {ref}: {why}")
        text = full.read_text(encoding="utf-8")
        payload = json.loads(text) if full.suffix == ".json" else (C.yaml.safe_load(text) if C.yaml else text)
    pattern = looks_like_secret(json.dumps(payload, ensure_ascii=False, default=str))
    if pattern:
        raise ScriptError(f"input {ref} looks like it holds a secret ({pattern}); it is never posted")
    return payload


def run_tines(*args: str) -> tuple[int, str, str]:
    p = subprocess.run([str(C.rpath("scripts/tines")), *args], cwd=str(C.repo_root()), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def action_name_of(event: dict[str, Any], id_to_name: dict[Any, str]) -> Optional[str]:
    for key in ("agent_name", "action_name", "name"):
        if isinstance(event.get(key), str):
            return event[key]
    for key in ("agent", "action"):
        v = event.get(key)
        if isinstance(v, dict) and isinstance(v.get("name"), str):
            return v["name"]
    for key in ("agent_id", "action_id"):
        if event.get(key) in id_to_name:
            return id_to_name[event[key]]
    return None


def event_payload(event: dict[str, Any]) -> Any:
    for key in ("payload", "data", "event"):
        if key in event:
            return event[key]
    return event


def run_events(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [e for e in response if isinstance(e, dict)]
    if isinstance(response, dict):
        for key in ("events", "story_run_events", "data"):
            if isinstance(response.get(key), list):
                return [e for e in response[key] if isinstance(e, dict)]
    return []


def grade(case: dict[str, Any], fired: list[Optional[str]], exits: dict[str, Any]) -> tuple[bool, list[str]]:
    expect = case.get("expect") or {}
    names = {n for n in fired if n}
    fails = []
    if "actions_fired_min" in expect and len(names) < int(expect["actions_fired_min"]):
        fails.append(f"{len(names)} actions fired < {expect['actions_fired_min']}")
    for n in expect.get("must_fire") or []:
        if n not in names:
            fails.append(f"{n} did not fire")
    for n in expect.get("must_not_fire") or []:
        if n in names:
            fails.append(f"{n} fired")
    if "result_fields" in expect:
        payload = exits.get("result")
        keys = sorted(payload.keys()) if isinstance(payload, dict) else None
        if keys != sorted(str(k) for k in expect["result_fields"]):
            fails.append(f"result fields {keys} != {sorted(expect['result_fields'])}")
    if "result_field_values" in expect:
        last = exits.get("_last")
        for k, v in (expect["result_field_values"] or {}).items():
            if not isinstance(last, dict) or last.get(k) != v:
                fails.append(f"exit {k} = {None if not isinstance(last, dict) else last.get(k)!r}, expected {v!r}")
    return not fails, fails


def cmd_eval_run(args: argparse.Namespace) -> int:
    slug = C.check_slug(args.slug)
    if (os.environ.get("TINES_ENV") or "dev") == "prod":
        raise ScriptError("eval-run refuses TINES_ENV=prod: cases run against the DEV story only")
    machine = C.load_machine()
    cases_path = C.rpath(args.cases) if args.cases else C.work_dir(slug) / "evals" / "cases.yaml"
    doc = load_cases(cases_path)
    k_default = int(args.k or (doc.get("defaults") or {}).get("k") or machine.thresholds.get("eval_k_default", 3))
    cases = [c for c in doc["cases"] if isinstance(c, dict) and (not args.case or c.get("id") in args.case)]
    contract = C.load_contract(slug)[0] if (C.work_dir(slug) / "design.md").is_file() else None
    entry_type = ((contract or {}).get("entry") or {}).get("type") or ("webhook" if args.entry_action else None)
    entry_action = args.entry_action or ((contract or {}).get("entry") or {}).get("action")
    manifest_entry = C.manifest_entry(slug) or {}
    dev_id = int(((manifest_entry.get("dev") or {}).get("story_id")) or 0)
    entry_story = args.entry_story_id or (dev_id if entry_type == "webhook" else None)
    plan = {
        "story_key": slug, "cases_file": C.rel(cases_path), "k": k_default,
        "entry": {"type": entry_type, "action": entry_action, "post_to_story_id": entry_story, "story_under_test_id": dev_id,
                  "via": "the story's own Webhook" if entry_type == "webhook" and not args.entry_story_id else "a dev-only wrapper story's Webhook"},
        "cases": [],
    }
    for c in cases:
        try:
            load_input(slug, str(c.get("input_ref") or ""), cases_path)
            ok = True
        except (ScriptError, json.JSONDecodeError, SystemExit) as exc:
            ok = str(exc) or "unreadable"
        plan["cases"].append({"id": c.get("id"), "kind": c.get("kind"), "suite": c.get("suite"),
                              "trials": int(c.get("k") or k_default) if c.get("kind") == "model_graded" else 1,
                              "input": c.get("input_ref"), "input_ok": ok is True, **({} if ok is True else {"input_error": ok})})
    if args.dry_run:
        C.print_json(plan)
        return 0
    if entry_type is None:
        raise ScriptError(f"no contract entry type for {slug} (storyline/work/{slug}/design.md) — pass --entry-action for a kit-launch agent case file")
    if not dev_id:
        raise ScriptError(f"{slug} has no dev story id in stories/_manifest.yaml (the builder records it); nothing to run against")
    if not entry_story:
        raise ScriptError(f"a {entry_type} entry is reached through the dev-only wrapper story: pass --entry-story-id <its dev id> (VERIFY K37)")
    if any(not c["input_ok"] for c in plan["cases"]):
        raise ScriptError("some inputs do not resolve: " + "; ".join(f"{c['id']}: {c.get('input_error')}" for c in plan["cases"] if not c["input_ok"]))
    tenant = os.environ.get("TINES_TENANT") or ""
    if not tenant or not os.environ.get("TINES_API_KEY"):
        raise ScriptError("TINES_TENANT and a dev-team TINES_API_KEY are required (source .env)")
    if requests is None:
        raise ScriptError("the 'requests' package is required (pip install -r scripts/requirements.txt)")

    import export_story  # noqa: WPS433 — ./scripts/tines webhook-url's in-memory reader; no raw export touches disk

    try:
        hook = export_story.entry_webhook(slug, "dev", int(entry_story),
                                          prefer=entry_action if args.entry_story_id is None else None,
                                          name=args.entry_action)
    except SystemExit:  # tines_common.ScriptError has printed the reason
        raise ScriptError("could not read the entry Webhook from the dev export (see the error above; use --entry-action)") from None
    path, secret = hook["path"], hook["secret"]
    if not path or path.startswith("<"):
        raise ScriptError("the entry Webhook's path is not in the dev export (VERIFY K37)")
    url = webhook_url(tenant, path, secret)
    export_ids: dict[Any, str] = hook["action_names"] if args.entry_story_id is None else {}
    del hook, path, secret

    results, credits, notes = [], [], []
    seen_runs: set[str] = set()
    for c in cases:
        trials = int(c.get("k") or k_default) if c.get("kind") == "model_graded" else 1
        passes, observations = 0, []
        for n in range(trials):
            payload = load_input(slug, str(c.get("input_ref")), cases_path)  # confined + secret-scanned before every post
            posted = time.time()
            since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(posted - 2))
            try:
                requests.post(url, json=payload, timeout=30)
            except requests.RequestException as exc:  # type: ignore[union-attr]
                observations.append({"trial": n + 1, "error": f"post failed: {exc.__class__.__name__}"})
                continue
            guid = None
            deadline = posted + args.timeout
            while time.time() < deadline and guid is None:
                time.sleep(3)
                rc, out, _ = run_tines("runs", slug, "--env", "dev", "--since", since, "--json")
                if rc == 0:
                    rows = (json.loads(out or "{}") or {}).get("rows") or []
                    fresh = [r for r in rows if r.get("guid") and r["guid"] not in seen_runs]
                    if fresh:
                        guid = sorted(fresh, key=lambda r: str(r.get("start_time") or ""))[0]["guid"]
            if guid is None:
                observations.append({"trial": n + 1, "error": f"no new run of {slug} within {args.timeout}s"})
                continue
            seen_runs.add(guid)
            time.sleep(args.settle)
            rc, out, _ = run_tines("runs", slug, "--env", "dev", "--events", guid)
            events = run_events(json.loads(out) if rc == 0 and out.strip() else None)
            fired = [action_name_of(e, export_ids) for e in events]
            exits: dict[str, Any] = {}
            for e, name in zip(events, fired):
                if name in EXITS:
                    exits[name] = event_payload(e)
                    exits["_last"] = event_payload(e)
            for e, name in zip(events, fired):
                meta = e.get("meta") if isinstance(e.get("meta"), dict) else (event_payload(e) or {}).get("meta") if isinstance(event_payload(e), dict) else None
                if isinstance(meta, dict) and ("credits_used" in meta or "model" in meta):
                    credits.append({k: meta[k] for k in ("credits_used", "input_tokens", "output_tokens", "model") if k in meta} | {"action": name or "?", "eval_id": c.get("id")})
            obs: dict[str, Any] = {"trial": n + 1, "run": guid[:8] + "…", "fired": sorted({x for x in fired if x}), "unnamed_events": sum(1 for x in fired if not x)}
            if c.get("kind") == "model_graded":
                target = next((x for x in (c.get("expect") or {}).get("must_fire") or []), None)
                out_payload = next((event_payload(e) for e, name in zip(events, fired) if name == target), None)
                text = json.dumps(out_payload, ensure_ascii=False)[:4000] if out_payload is not None else None
                obs["agent_output"] = "[redacted: secret-looking]" if text and looks_like_secret(text) else text
            else:
                ok, why = grade(c, fired, exits)
                obs["pass"], obs["why"] = ok, why
                passes += 1 if ok else 0
            if "no_error_on" in (c.get("expect") or {}):
                obs["no_error_on"] = "not checked here (action ids and run correlation in action-logs are VERIFY); story-qa reads ./scripts/tines action-logs"
            observations.append(obs)
        graded = c.get("kind") != "model_graded"
        summary = "; ".join(sorted({w for o in observations for w in (o.get("why") or [])} | {o["error"] for o in observations if o.get("error")})) or ("all trials met the expectations" if graded else "recorded for story-qa to grade")
        results.append({"eval_id": c.get("id"), "suite": c.get("suite"), "kind": c.get("kind"), "should_trigger": c.get("should_trigger"),
                        "trials": trials, "passes": passes if graded else None, "pass": (passes == trials) if graded else None,
                        "observed_summary": C.truncate(summary, 600), "observations": observations})
    if any(r["pass"] is None for r in results):
        notes.append("model-graded cases are recorded, not graded: story-qa grades them with the rubric and the reference output")
    out = {"story_key": slug, "generated_at": utc_now(), "entry": {k: v for k, v in plan["entry"].items()}, "cases_file": plan["cases_file"],
           "k": k_default, "results": results, "credits_observed": credits, "notes": notes}
    d = C.out_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    target = d / f"qa-{utc_now().replace(':', '').replace('-', '')}.json"
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for r in results if r["pass"] is True)
    print(f"storyline eval-run {slug}: {passed}/{len(results)} deterministic case(s) passed; results in {C.rel(target)}")
    return 0 if all(r["pass"] is not False for r in results) else 1


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="storyline eval-run", description="Run eval cases against the DEV story (never prod).")
    C.add_root_args(p)
    p.add_argument("slug")
    p.add_argument("--k", type=int, help="trials per model-graded case (default: the cases file, else 3)")
    p.add_argument("--cases", help="another cases file (e.g. storyline/evals/agents/runtime-planner.cases.yaml)")
    p.add_argument("--case", action="append", help="run only this case id (repeatable)")
    p.add_argument("--entry-story-id", type=int, help="the dev story whose Webhook receives the cases (the wrapper for a Send to Story entry)")
    p.add_argument("--entry-action", help="the entry Webhook's action name (e.g. specialist_test in the dev copy of kit-launch)")
    p.add_argument("--timeout", type=int, default=60, help="seconds to wait for each run to appear (default 60)")
    p.add_argument("--settle", type=int, default=5, help="seconds to let a run finish before reading its events (default 5)")
    p.add_argument("--dry-run", action="store_true", help="resolve cases, inputs and the entry; no network")
    args = p.parse_args(argv)
    C.apply_root_args(args)
    return cmd_eval_run(args)


if __name__ == "__main__":
    sys.exit(main())
