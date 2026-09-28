#!/usr/bin/env python3
"""``./scripts/sdlc apply <slug> <agent|verify-merge> <out.json|->`` — apply one specialist output, or merge the verdicts.

Spec: REPO-DESIGN.md §5.2 (the envelope), §4.6 (touch sets), §6.1 (apply), §4.4 (04 verify: the merge rule and the rework
package), P6 (hand off through persisted artifacts), P8 (schema-validated outputs), P16 (inputs are data).

For an agent
------------
1. **Read** the output: with ``-`` from stdin (the orchestrator pipes the subagent's final message), else from a file.
   The message must be exactly one JSON object, or exactly one fenced ```json block with nothing else around it — the
   orchestrator never extracts JSON from prose, and neither does this script.
   ``tines-builder`` is the exception: its report is prose, saved verbatim as ``build-log.md`` and never parsed.
   ``tines-reviewer`` returns the reused findings JSON (``--schema findings``, the default for it), not an envelope.
2. **Save** it as ``.sdlc/out/<slug>/<agent>-<attempt>.json`` (local, gitignored). An invalid output is saved as
   ``<agent>-<attempt>.invalid-<n>.json``; the second invalid output for the same attempt opens GX.
3. **Validate** the envelope (``sdlc/agents/contracts/envelope.schema.json`` ``$defs.output`` when it exists, else the
   §5.2 shape built in here), then the payload (``sdlc/agents/contracts/<agent>.schema.json`` ``$defs.output`` when it
   exists), then consistency: agent, story key, phase, attempt, summary ≤ 1,500 characters.
4. **Touch set**: every file must match the agent's entry AND its phase's entry in ``touch-sets.yaml``; every patch must
   be one of the agent's allow-listed patches, addressed by its exact path. No secret-looking value and no real email
   address may be written.
5. **Write** the files and the patches (manifest entry merge, the story's budget lines, the story's own tracker row —
   comment-preserving, and re-parsed to prove nothing else changed).
6. **Event**: one ``specialist_run`` line (or one ``escalation`` when the verdict is ``needs_human``, or ``blocked`` outside
   verify) — then the tracker row (rev = main's rev + 1).

``verify-merge``
----------------
Reads ``tines-reviewer-<attempt>.json``, ``security-reviewer-<attempt>.json`` (when its dispatch condition holds),
``story-qa-<attempt>.json`` and runs the cost checks (``sdlc estimate --check``, offline). The rule is deterministic:
a source that returned ``needs_human`` or ``blocked``, or failed its schema twice → **blocked** (GX); otherwise any
``blocker`` or ``major`` finding — a reviewer's, a failing case (``eval.case_failed``), a FAIL cost check (``cost.N``) —
→ **changes_requested**, a rework package ``.sdlc/out/<slug>/rework-<n>.json`` and ``build/rework`` (attempt + 1) while
attempt < ``rework_cap``, GX at the cap; otherwise **pass**. The result is ``sdlc/work/<slug>/verify-report.json``,
validated against ``sdlc/templates/verify-report.schema.json``. Where consistency matters (side effects, a Page or an MCP
server entry, a Page wider than none), a model-graded case that did not pass all k trials is ``major``; elsewhere
``minor`` unless it never passed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sdlc_common as C  # noqa: E402
from sdlc_common import ScriptError  # noqa: E402
import sdlc_estimate as E  # noqa: E402
import sdlc_state as S  # noqa: E402
from tines_common import EMAIL_RE, eprint, is_placeholder_email, looks_like_secret, utc_now  # noqa: E402

VERIFY_AGENTS = ("tines-reviewer", "security-reviewer", "story-qa")
SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2, "info": 3}

# REPO-DESIGN.md §5.2, used when sdlc/agents/contracts/envelope.schema.json does not exist yet.
FALLBACK_OUTPUT_ENVELOPE: dict[str, Any] = {
    "type": "object",
    "required": ["envelope_version", "agent", "story_key", "phase", "attempt", "verdict", "summary", "files", "patches",
                 "findings", "payload", "needs_human", "next", "telemetry"],
    "properties": {
        "envelope_version": {"const": 1},
        "agent": {"type": "string"},
        "story_key": {"type": "string", "pattern": "^[a-z0-9-]{1,64}$"},
        "phase": {"type": "string"},
        "attempt": {"type": "integer", "minimum": 0},
        "verdict": {"enum": ["done", "changes_requested", "needs_human", "blocked"]},
        "summary": {"type": "string", "maxLength": 1500},
        "files": {"type": "array", "items": {"type": "object", "required": ["path", "content"],
                                             "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}},
        "patches": {"type": "array", "items": {"type": "object", "required": ["file", "set", "value"],
                                               "properties": {"file": {"type": "string"}, "set": {"type": "string"}}}},
        "findings": {"type": "array"},
        "payload": {"type": "object"},
        "needs_human": {"type": ["object", "null"]},
        "next": {"type": ["object", "null"]},
        "telemetry": {"type": ["object", "null"]},
    },
}


# --------------------------------------------------------------------------------------------------------------- #
# Reading and validating an output
# --------------------------------------------------------------------------------------------------------------- #


def parse_strict(text: str) -> Any:
    """Exactly one JSON object, or exactly one fenced ```json block and nothing else. Never extracted from prose."""
    body = text.strip()
    if body.startswith("{"):
        return json.loads(body)
    m = re.fullmatch(r"```(?:json)?[ \t]*\n(.*)\n```", body, re.S)
    if m:
        data = json.loads(m.group(1))  # the whole block must be ONE JSON value (file contents may quote fences inside strings)
        if isinstance(data, dict):
            return data
    raise ValueError("the output is not exactly one JSON object or one fenced ```json block")


def envelope_schema() -> dict[str, Any]:
    schema = C.load_schema(C.ENVELOPE_SCHEMA, from_config=True)
    if schema:
        out = ((schema.get("$defs") or {}).get("output"))
        if isinstance(out, dict):
            return {**out, "$defs": schema.get("$defs") or {}}
        return schema
    return FALLBACK_OUTPUT_ENVELOPE


def payload_schema(agent: str) -> Optional[dict[str, Any]]:
    schema = C.load_schema(f"{C.AGENT_CONTRACTS_DIR}/{agent}.schema.json", from_config=True)
    if not schema:
        return None
    out = (schema.get("$defs") or {}).get("output")
    return {**out, "$defs": schema.get("$defs") or {}} if isinstance(out, dict) else None


def invalid_count(slug: str, agent: str, attempt: int) -> int:
    d = C.out_dir(slug)
    return len(list(d.glob(f"{agent}-{attempt}.invalid-*.json"))) if d.is_dir() else 0


def save_invalid(slug: str, agent: str, attempt: int, raw: str) -> Path:
    d = C.out_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    n = invalid_count(slug, agent, attempt) + 1
    path = d / f"{agent}-{attempt}.invalid-{n}.json"
    path.write_text(raw, encoding="utf-8")
    return path


def content_problems(text: str, where: str) -> list[str]:
    out = []
    name = looks_like_secret(text)
    if name:
        out.append(f"{where}: looks like a secret ({name}) — names only, never values")
    for m in EMAIL_RE.finditer(text):
        if not is_placeholder_email(m.group(0)):
            out.append(f"{where}: a real-looking email address — placeholders (*.example.invalid) only")
            break
    return out


PATCH_SET_RX = {
    "manifest_entry": lambda s: re.compile(rf"^\.stories\.{re.escape(s)}$"),
    "manifest_dev_id": lambda s: re.compile(rf"^\.stories\.{re.escape(s)}\.dev\.story_id$"),
    "budget_lines": lambda s: re.compile(rf'^\.agents\."{re.escape(s)}/([a-z0-9_]{{1,64}})"$'),
    "tracker_row": lambda s: re.compile(rf'^\.stories\[\] \| select\(\.key == "{re.escape(s)}"\)$'),
}


def classify_patch(touch: dict[str, Any], allowed: list[str], slug: str, patch: dict[str, Any]) -> tuple[str, Optional[str]]:
    """(patch name, the budget line's action) for an envelope patch, or a ScriptError."""
    file, target = str(patch.get("file") or ""), str(patch.get("set") or "").strip()
    for name in allowed:
        spec = C.patch_spec(touch, name)
        if spec.get("file") != file:
            continue
        shape = C.patch_shape(str(spec.get("path")))
        m = PATCH_SET_RX[shape](slug).match(target)
        if m:
            return name, (m.group(1) if shape == "budget_lines" else None)
    raise ScriptError(f"patch {file} {target!r} is not allow-listed for this specialist (allowed: {allowed})")


def apply_patch(name: str, shape: str, slug: str, patch: dict[str, Any], action: Optional[str], tracker: C.Tracker, row: dict[str, Any]) -> dict[str, Any]:
    """Apply one allow-listed patch; returns the (possibly updated) tracker row."""
    value = patch.get("value")
    file = C.rpath(str(patch.get("file")))
    if shape == "manifest_entry":
        if not isinstance(value, dict):
            raise ScriptError("a manifest patch value must be a mapping")
        current = C.manifest_entry(slug) or {}
        C.set_mapping_child(file, "stories", slug, C.deep_merge(current, value))
    elif shape == "manifest_dev_id":
        if not isinstance(value, int) or value < 0:
            raise ScriptError("the dev story id must be a non-negative integer")
        current = C.manifest_entry(slug) or {}
        merged = C.deep_merge(current, {"dev": {"story_id": value}})
        C.set_mapping_child(file, "stories", slug, merged)
    elif shape == "budget_lines":
        if not isinstance(value, dict):
            raise ScriptError("a budget line must be a mapping (daily_tokens_notify, daily_tokens_disable, …)")
        C.set_mapping_child(file, "agents", f"{slug}/{action}", value)
    elif shape == "tracker_row":
        if not isinstance(value, dict):
            raise ScriptError("a tracker-row patch value must be a mapping")
        bad = sorted(set(value) - C.ROW_PATCHABLE)
        if bad:
            raise ScriptError(f"a tracker-row patch may set only {sorted(C.ROW_PATCHABLE)}; refused: {bad}")
        row = C.deep_merge(row, value)
    return row


# --------------------------------------------------------------------------------------------------------------- #
# apply <agent>
# --------------------------------------------------------------------------------------------------------------- #


def escalate(slug: str, tracker: C.Tracker, row: dict[str, Any], machine: C.Machine, agent: str, reason: str) -> dict[str, Any]:
    t = machine.find(str(row.get("phase")), gate="GX", decision=None, guard=S.make_guard(slug, row, machine))
    if t is None:
        raise ScriptError("the machine has no GX row")
    contract = C.load_contract(slug)[0] if (C.work_dir(slug) / "design.md").is_file() else None
    new = S.bump(slug, S.transition_row(slug, row, t, machine, C.read_events(slug), contract))
    event = C.make_event(slug, "escalation", from_phase=row.get("phase"), to_phase=new["phase"], gate="GX", decision="opened",
                         actor="sdlc apply", actor_kind="ci", agent=agent, summary=f"GX opened ({agent}): {reason}", tracker_rev=new["rev"])
    S.commit(slug, tracker, new, event)
    return new


def apply_builder(slug: str, raw: str, tracker: C.Tracker, row: dict[str, Any], machine: C.Machine) -> int:
    attempt = int(row.get("attempt") or 0)
    if row.get("phase") != "build":
        raise ScriptError(f"the builder's report belongs to build; {slug} is {row.get('phase')}")
    report = raw.rstrip("\n")
    if not report.strip():
        raise ScriptError("the builder's report is empty")
    problems = content_problems(report, "the builder's report")
    if problems:
        raise ScriptError("; ".join(problems))
    d = C.out_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"tines-builder-{attempt}.json").write_text(json.dumps({"agent": "tines-builder", "attempt": attempt, "report": report}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    events = C.read_events(slug)
    start = S.build_start_event(events)
    rework = f"`.sdlc/out/{slug}/rework-{attempt}.json` (local)" if row.get("status") == "rework" else "none"
    header = (
        f"# Build log — `{slug}` · attempt {attempt}\n\n"
        f"_Template: `sdlc/templates/build-log.md` · Phase: 03 build · Saved by `./scripts/sdlc apply {slug} tines-builder -` from the builder's final report, "
        "**verbatim**. **Never parsed**: the phase exit is the check `build_evidence`, and G3 is the `gate_decision` event `/sdlc-gate` recorded._\n\n"
        "| | |\n|---|---|\n"
        f"| Story | `{slug}` · `{row.get('title') or ''}` |\n| Attempt | {attempt} |\n| Branch | `{C.current_branch() or 'story/' + slug + '/<short>'}` |\n"
        f"| Rework package | {rework} |\n| Build start event | {start.get('ts') if start else '—'} |\n\n"
        "## The builder's report (verbatim, below this line)\n\n"
    )
    touch = C.load_touch_sets()
    target = f"{C.WORK_DIR}/{slug}/build-log.md"
    agent_files = (C.agent_touch(touch, "tines-builder") or {}).get("files") or []
    if not C.path_allowed(target, agent_files, slug):
        raise ScriptError(f"{target} is not in the tines-builder touch set")
    (C.work_dir(slug) / "build-log.md").write_text(header + report + "\n", encoding="utf-8")
    new = S.bump(slug, row)
    event = C.make_event(slug, "specialist_run", agent="tines-builder", decision="finished", actor="tines-builder", actor_kind="agent",
                         model_tier="strong", model_reported="as the client shows it",
                         summary=f"tines-builder finished attempt {attempt}; report saved verbatim (never parsed).",
                         tracker_rev=new["rev"], refs=[target], sha=C.head_sha())
    S.commit(slug, tracker, new, event)
    print(f"sdlc apply {slug} tines-builder: build-log.md written; the exit is ./scripts/sdlc advance {slug} (build_evidence)")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    slug = C.check_slug(args.slug)
    agent = args.agent
    if agent == "verify-merge":
        return verify_merge(slug)
    lc = C.load_lifecycle()
    machine, touch = lc.machine, lc.touch
    tracker = C.load_tracker()
    row = C.require_row(tracker, slug)
    attempt = int(row.get("attempt") or 0)
    entry = C.agent_touch(touch, agent)
    if entry is None:
        raise ScriptError(f"{agent!r} has no entry in {C.TOUCH_SETS} agents: (known: {sorted((touch.get('agents') or {}).keys())})")
    raw = sys.stdin.read() if args.out == "-" else Path(args.out).read_text(encoding="utf-8")
    if row.get("status") == "blocked":
        raise ScriptError(f"{slug} is blocked (GX): nothing is applied until a person decides")
    if agent == "tines-builder":
        return apply_builder(slug, raw, tracker, row, machine)
    if row.get("phase") != entry.get("phase"):
        raise ScriptError(f"{agent} works in {entry.get('phase')}; {slug} is in {row.get('phase')}")

    schema_kind = args.schema or ("findings" if agent == "tines-reviewer" else "envelope")
    problems: list[str] = []
    data: Any = None
    try:
        data = parse_strict(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        problems.append(str(exc))
    if not problems:
        if schema_kind == "findings":
            schema = C.load_schema(C.FINDINGS_SCHEMA, from_config=True)
            problems += C.validate(data, schema) if schema else [f"{C.FINDINGS_SCHEMA} not found"]
            if not problems and data.get("verdict") == "pass" and any(f.get("severity") in ("blocker", "major") for f in data.get("findings") or []):
                problems.append("verdict pass with a blocker or major finding")
        else:
            problems += C.validate(data, envelope_schema())
            if not problems:
                for key, want in (("agent", agent), ("story_key", slug), ("phase", row.get("phase")), ("attempt", attempt)):
                    if data.get(key) != want:
                        problems.append(f"{key} is {data.get(key)!r}, expected {want!r}")
                ps = payload_schema(agent)
                if ps is not None:
                    problems += [f"payload{p[1:]}" for p in C.validate(data.get("payload"), ps)]
                elif agent in ("story-scout", "story-architect", "eval-author", "security-reviewer", "story-qa", "eval-curator", "skill-curator"):
                    eprint(f"sdlc apply: {C.AGENT_CONTRACTS_DIR}/{agent}.schema.json not found — the payload is not schema-checked (planned, REPO-DESIGN.md §15.2)")
                findings_schema = C.load_schema(C.FINDINGS_SCHEMA, from_config=True)
                if findings_schema and data.get("findings"):
                    item = ((findings_schema.get("properties") or {}).get("findings") or {}).get("items")
                    for i, f in enumerate(data.get("findings") or []):
                        problems += [f"findings[{i}]{p[1:]}" for p in C.validate(f, item or {}, findings_schema)]
    if problems:
        path = save_invalid(slug, agent, attempt, raw)
        n = invalid_count(slug, agent, attempt)
        if n >= 2:
            new = escalate(slug, tracker, row, machine, agent, f"the output failed its schema twice ({'; '.join(problems[:2])})")
            raise ScriptError(f"invalid output ({C.rel(path)}), the second for attempt {attempt}: GX opened ({new['phase']}/{new['status']})")
        raise ScriptError(f"invalid output, saved as {C.rel(path)} — ask the specialist once more (a second invalid output opens GX):\n  " + "\n  ".join(problems[:8]))

    d = C.out_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    saved = d / f"{agent}-{attempt}.json"
    saved.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if schema_kind == "findings":
        new = S.bump(slug, row)
        counts = {s: sum(1 for f in data.get("findings") or [] if f.get("severity") == s) for s in SEVERITY_ORDER}
        event = C.make_event(slug, "specialist_run", agent=agent, decision=str(data.get("verdict")), actor=agent, actor_kind="agent",
                             model_reported="as the client shows it",
                             summary=f"{agent}: {data.get('verdict')}, " + ", ".join(f"{v} {k}" for k, v in counts.items() if v) if any(counts.values()) else f"{agent}: {data.get('verdict')}, no findings",
                             tracker_rev=new["rev"], sha=C.head_sha())
        S.commit(slug, tracker, new, event)
        print(f"sdlc apply {slug} {agent}: {data.get('verdict')} — saved {C.rel(saved)}")
        return 0

    verdict = str(data.get("verdict"))
    if verdict == "needs_human" or (verdict == "blocked" and agent not in VERIFY_AGENTS):
        reason = (data.get("needs_human") or {}).get("reason") if isinstance(data.get("needs_human"), dict) else None
        new = escalate(slug, tracker, row, machine, agent, C.truncate(reason or data.get("summary") or verdict, 600))
        print(f"sdlc apply {slug} {agent}: {verdict} — GX opened ({new['phase']}/{new['status']}); the owner decides")
        return 0

    agent_files = list(entry.get("files") or [])
    phase_files = list(C.phase_touch(touch, str(row.get("phase"))).get("files") or [])
    allowed_patches = [p for p in (entry.get("patches") or []) if p in (C.phase_touch(touch, str(row.get("phase"))).get("patches") or [])]
    writes: list[tuple[str, str]] = []
    errors: list[str] = []
    for f in data.get("files") or []:
        path = C.safe_relpath(str(f.get("path")))
        if not (C.path_allowed(path, agent_files, slug, attempt) and C.path_allowed(path, phase_files, slug, attempt)):
            errors.append(f"{path}: outside the {agent} touch set ({', '.join(C.expand_glob(g, slug) for g in agent_files) or 'none'})")
            continue
        content = str(f.get("content") or "")
        errors += content_problems(content, path)
        writes.append((path, content))
    patches = []
    for p in data.get("patches") or []:
        try:
            name, action = classify_patch(touch, allowed_patches, slug, p)
        except ScriptError as exc:
            errors.append(str(exc).replace("error: ", ""))
            continue
        errors += content_problems(json.dumps(p.get("value"), ensure_ascii=False), f"patch {p.get('file')}")
        patches.append((name, C.patch_shape(str(C.patch_spec(touch, name).get("path"))), p, action))
    if errors:
        raise ScriptError(f"{agent}'s output was not applied (nothing written):\n  " + "\n  ".join(errors[:10]))

    for path, content in writes:
        full = C.rpath(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    for name, shape, p, action in patches:
        row = apply_patch(name, shape, slug, p, action, tracker, row)
    if agent == "eval-curator" and (C.work_dir(slug) / "retro.md").is_file():
        C.set_front_matter_key(C.work_dir(slug) / "retro.md", "curated", True)

    telemetry = data.get("telemetry") or {}
    tier = telemetry.get("model_tier") if telemetry.get("model_tier") in ("strong", "standard", "fast", "smart") else None
    new = S.bump(slug, row)
    event = C.make_event(
        slug, "specialist_run", agent=agent, decision=verdict, actor=agent, actor_kind="agent", model_tier=tier,
        model_reported=C.truncate(str(telemetry.get("model_reported") or "as the client shows it"), 128),
        turns=telemetry.get("turns") if isinstance(telemetry.get("turns"), int) else None,
        summary=f"{agent}: " + str(data.get("summary") or verdict), tracker_rev=new["rev"],
        refs=[p for p, _ in writes] + [str(p.get("file")) for _, _, p, _ in patches],
    )
    S.commit(slug, tracker, new, event)
    print(f"sdlc apply {slug} {agent}: {verdict} — {len(writes)} file(s), {len(patches)} patch(es); saved {C.rel(saved)}")
    return 0


# --------------------------------------------------------------------------------------------------------------- #
# verify-merge
# --------------------------------------------------------------------------------------------------------------- #


def consistency_matters(contract: Optional[dict[str, Any]]) -> bool:
    c = contract or {}
    page = (((c.get("access") or {}).get("page") or {}).get("level")) or "none"
    return bool((c.get("risk") or {}).get("side_effects")) or (c.get("entry") or {}).get("type") in ("page", "mcp_server") or page != "none"


def _finding(source: str, f: dict[str, Any]) -> dict[str, Any]:
    out = {
        "source": source,
        "path": C.truncate(str(f.get("path") or "?"), 300),
        "rule": C.truncate(str(f.get("rule") or "unspecified"), 80),
        "severity": f.get("severity") if f.get("severity") in SEVERITY_ORDER else "major",
        "message": C.truncate(str(f.get("message") or "(no message)"), 600),
    }
    if f.get("suggested_fix"):
        out["suggested_fix"] = C.truncate(str(f["suggested_fix"]), 1000)
    if f.get("suggested_prompt"):
        out["suggested_prompt"] = C.truncate(str(f["suggested_prompt"]), 1500)
    return out


def load_output(slug: str, agent: str, attempt: int) -> tuple[Optional[dict[str, Any]], str]:
    path = C.out_dir(slug) / f"{agent}-{attempt}.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8")), C.rel(path)
        except json.JSONDecodeError:
            return None, C.rel(path)
    return None, C.rel(path)


def verify_merge(slug: str) -> int:
    lc = C.load_lifecycle()
    machine = lc.machine
    tracker = C.load_tracker()
    row = C.require_row(tracker, slug)
    if row.get("phase") != "verify" or row.get("status") != "active":
        raise ScriptError(f"verify-merge runs in verify/active; {slug} is {row.get('phase')}/{row.get('status')}")
    attempt = int(row.get("attempt") or 0)
    ctx = S.Context(slug)
    contract = ctx.contract
    sources: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    blocked: list[str] = []
    missing: list[str] = []

    for agent in VERIFY_AGENTS:
        if agent == "security-reviewer" and not ctx.security_reviewer_needed():
            sources.append({"source": agent, "status": "skipped", "findings_count": 0,
                            "reason": "not dispatched: its condition does not hold (dispatch-rules.yaml conditional)"})
            continue
        data, ref = load_output(slug, agent, attempt)
        if data is None:
            if invalid_count(slug, agent, attempt) >= 2:
                sources.append({"source": agent, "status": "schema_failed", "out_ref": ref, "findings_count": 0, "reason": "failed its schema twice"})
                blocked.append(f"{agent} failed its schema twice")
            else:
                missing.append(agent)
            continue
        if agent == "tines-reviewer" and "envelope_version" not in data:
            status = str(data.get("verdict"))
            items = data.get("findings") or []
        else:
            verdict = str(data.get("verdict"))
            payload_verdict = (data.get("payload") or {}).get("verdict") if isinstance(data.get("payload"), dict) else None
            if verdict in ("needs_human", "blocked"):
                status = verdict
            elif payload_verdict in ("pass", "changes_requested"):
                status = str(payload_verdict)  # the reviewer's own verdict (security-reviewer, story-qa payloads)
            else:
                status = {"done": "pass"}.get(verdict, verdict)
            items = list(data.get("findings") or []) + list(((data.get("payload") or {}).get("findings")) or [])
        these = [_finding(agent, f) for f in items if isinstance(f, dict)]
        if status in ("needs_human", "blocked"):
            blocked.append(f"{agent} returned {status}")
        sources.append({"source": agent, "status": status if status in ("pass", "changes_requested", "needs_human", "blocked") else "changes_requested",
                        "out_ref": ref, "findings_count": len(these)})
        findings += these
    if missing:
        raise ScriptError(f"not applied yet for attempt {attempt}: {missing} — ./scripts/sdlc next {slug}")

    qa_data, _ = load_output(slug, "story-qa", attempt)
    payload = (qa_data or {}).get("payload") or {}
    results = [r for r in (payload.get("results") or []) if isinstance(r, dict)]
    matters = consistency_matters(contract)
    failing_cases = []
    for r in results:
        if r.get("pass") is True:
            continue
        trials, passes = int(r.get("trials") or 1), int(r.get("passes") or 0)
        if r.get("kind") == "model_graded" and passes > 0 and not matters:
            sev = "minor"
        else:
            sev = "major"
        cid = str(r.get("case_id"))
        failing_cases.append({"case_id": cid, "suite": r.get("suite") if r.get("suite") in ("capability", "regression") else "capability",
                              "kind": r.get("kind") if r.get("kind") in ("deterministic", "model_graded") else "deterministic",
                              "trials": max(trials, 1), "passes": max(passes, 0), "observed_summary": C.truncate(str(r.get("observed_summary") or ""), 600)})
        findings.append({"source": "story-qa", "path": f"{C.WORK_DIR}/{slug}/evals/cases.yaml#{cid}", "rule": "eval.case_failed", "severity": sev,
                         "message": C.truncate(f"{cid} ({r.get('kind')}, {r.get('suite')}) passed {passes} of {trials} trial(s): {r.get('observed_summary') or ''}", 600),
                         "suggested_prompt": C.truncate(f'/tines-build-story {slug} "Make eval case {cid} pass: see sdlc/work/{slug}/evals/cases.yaml ({r.get("observed_summary") or "observed output differs"}). Then validate and run the test event."', 1500)})
    pass_k = payload.get("pass_k") if isinstance(payload.get("pass_k"), dict) else {}
    k = int(pass_k.get("k") or machine.thresholds.get("eval_k_default", 3))
    value = pass_k.get("value") if isinstance(pass_k.get("value"), (int, float)) else None

    cost = E.run_checks(slug, offline=True)
    cost_status = "pass"
    for r in cost["results"]:
        if r["result"] == "FAIL":
            cost_status = "changes_requested"
            findings.append({"source": "cost-checks", "path": f"{C.WORK_DIR}/{slug}/design.md#cost_estimate", "rule": r["id"], "severity": "major",
                             "message": C.truncate(r["detail"], 600),
                             "suggested_fix": "Change the design (a pinned fast model, fewer runs, a Trigger before the agent) or the budget line, by PR."})
    sources.append({"source": "cost-checks", "status": cost_status, "findings_count": sum(1 for r in cost["results"] if r["result"] == "FAIL"),
                    "reason": f"./scripts/sdlc estimate {slug} --check"})

    findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
    if blocked:
        verdict = "blocked"
    elif any(f["severity"] in ("blocker", "major") for f in findings):
        verdict = "changes_requested"
    else:
        verdict = "pass"
    title = str(row.get("title") or slug)
    for f in findings:
        if f["severity"] in ("blocker", "major") and not f.get("suggested_prompt"):
            f["suggested_prompt"] = C.truncate(f'/tines-build-story {slug} "In {title}, fix: {f["message"]} ({f["path"]}). Then validate."', 1500)
    next_attempt = attempt + 1
    at_cap = verdict == "changes_requested" and attempt >= machine.cap("rework_cap", 3)
    rework_ref = f".sdlc/out/{slug}/rework-{next_attempt}.json" if verdict == "changes_requested" and not at_cap else None
    report = {
        "report_version": 1, "story_key": slug, "attempt": attempt, "sha": C.head_sha() or "0000000", "generated_at": utc_now(),
        "verdict": verdict, "sources": sources, "findings": findings,
        "cost_checks": {"results": [{"id": r["id"], "result": r["result"], "detail": r["detail"]} for r in cost["results"]],
                        "projection": cost["projection"], "budget_fit": cost["budget_fit"]},
        "qa": {"cases_total": len(results), "cases_passed": sum(1 for r in results if r.get("pass") is True),
               "pass_k": {"k": max(k, 1), "value": value}, "failing_cases": failing_cases,
               "credits_observed": [
                   {kk: vv for kk, vv in c.items() if kk in ("action", "credits_used", "input_tokens", "output_tokens", "model")}
                   for c in (payload.get("credits_observed") or []) if isinstance(c, dict) and "action" in c and "credits_used" in c]},
        "rework_package_ref": rework_ref,
    }
    if verdict == "pass":
        report["rework_package_ref"] = None
    schema = C.load_schema(C.VERIFY_REPORT_SCHEMA, from_config=True)
    problems = C.validate(report, schema) if schema else [f"{C.VERIFY_REPORT_SCHEMA} not found"]
    if problems:
        raise ScriptError("the merged report does not validate: " + "; ".join(problems[:6]))
    target = C.work_dir(slug) / "verify-report.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    new = S.bump(slug, row)
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    run_event = C.make_event(slug, "specialist_run", agent="verify-merge", decision=verdict, actor="sdlc apply verify-merge", actor_kind="ci",
                             summary=f"verify-merge: {verdict} (" + ", ".join(f"{v} {k2}" for k2, v in counts.items() if v) + ")" if any(counts.values()) else f"verify-merge: {verdict} (no findings)",
                             tracker_rev=new["rev"], refs=[f"{C.WORK_DIR}/{slug}/verify-report.json"], sha=report["sha"] if report["sha"] != "0000000" else None)
    S.commit(slug, tracker, new, run_event)
    tracker = C.load_tracker()
    row = C.require_row(tracker, slug)
    if verdict == "blocked" or at_cap:
        reason = "; ".join(blocked) if blocked else f"changes_requested at the rework cap ({attempt})"
        new = escalate(slug, tracker, row, machine, "verify-merge", reason)
        print(f"sdlc apply {slug} verify-merge: {verdict} — GX opened ({reason})")
        return 0
    if verdict == "changes_requested":
        t = machine.find("verify", gate="G4", decision="changes_requested", guard=S.make_guard(slug, row, machine))
        if t is None:
            raise ScriptError("the machine has no verify → build row for G4 changes_requested")
        moved = S.bump(slug, S.transition_row(slug, row, t, machine, C.read_events(slug), contract))
        must_fix = [{k2: v for k2, v in f.items()} for f in findings if f["severity"] in ("blocker", "major")]
        cases = [{"case_id": c["case_id"], "kind": c["kind"], "expected": "the case's expectations in sdlc/work/{}/evals/cases.yaml".format(slug),
                  "observed_summary": c["observed_summary"] or "(not recorded)"} for c in failing_cases]
        S.write_rework_package(slug, moved["attempt"], "G4", f"{C.WORK_DIR}/{slug}/verify-report.json", must_fix, cases)
        event = C.make_event(slug, "transition", from_phase="verify", to_phase="build", gate="G4", decision="changes_requested", actor="sdlc apply verify-merge",
                             actor_kind="ci", summary=f"G4 changes_requested at attempt {attempt} (below the cap of {machine.cap('rework_cap', 3)}): back to build with status rework, attempt {moved['attempt']}.",
                             tracker_rev=moved["rev"])
        S.commit(slug, tracker, moved, event)
        print(f"sdlc apply {slug} verify-merge: changes_requested — rework-{moved['attempt']}.json written; back to build/rework")
        return 0
    print(f"sdlc apply {slug} verify-merge: pass — {C.rel(target)}; next: ./scripts/sdlc advance {slug} (verify → ship), then the build PR")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="sdlc apply", description="Apply a specialist output, or merge the verify verdicts.")
    C.add_root_args(p)
    p.add_argument("slug")
    p.add_argument("agent", help="a specialist name from touch-sets.yaml agents:, or verify-merge")
    p.add_argument("out", nargs="?", default="-", help="the output file, or - for stdin (default)")
    p.add_argument("--schema", choices=["envelope", "findings"], help="findings = the reused /tines-review findings JSON (tines-reviewer's default)")
    args = p.parse_args(argv)
    C.apply_root_args(args)
    return cmd_apply(args)


if __name__ == "__main__":
    sys.exit(main())
