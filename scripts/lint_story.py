#!/usr/bin/env python3
"""Deterministic convention checks over ``stories/<slug>/story.json`` (+ meta).

One code path for the PostToolUse hook, the ``/tines-review`` skill and
``lint.yml``: the rules are the ones ``policies/lint-rules.yml`` names
(DESIGN.md §3.2), and every check is written against **what a real export
exposes**. Each rule below is tagged:

* **confirmed** — the key was read on real exports (schema_version 28 / 30):
  ``agents[].type`` (``Agents::LLMAgent``, ``Agents::HTTPRequestAgent``,
  ``Agents::EventTransformationAgent``, ``Agents::TriggerAgent``,
  ``Agents::SendToStoryAgent``, ``Agents::WebhookAgent``, ``Agents::GroupAgent``),
  ``agents[].options``, ``agents[].monitoring`` =
  ``{monitor_all_events, monitor_failures, monitor_no_events_emitted,
  ai_monitoring_thresholds[]}``, ``agents[].tools[]`` on AI Agent actions
  (``Agents::McpRequestAgent`` for MCP tools, with ``options.tool_name`` /
  ``tool_description``), ``options.output_structure`` (the AI Agent output
  schema), ``options.retry_on_status`` (a list of status strings),
  ``links[] = {source, receiver}`` by agent index, ``diagram_notes[]``,
  ``keep_events_for`` in seconds, ``recipients[]``, ``send_to_story_*`` flags,
  and the reference forms ``CREDENTIAL.<name>`` / ``RESOURCE.<name>``.
* **VERIFY** — the key was *not* observed and the check degrades to an
  informational finding until a real export confirms it: ``retries``,
  ``emit_failure_event`` and ``log_error_on_status`` on HTTP Request actions,
  the ``schedule`` object shape, the MCP server action's type string and its
  Tool-hints keys, and a per-tool Timeout Duration key.

Severities: ``error`` fails the run; ``warning`` and ``info`` are reported;
``skipped`` names a check that could not run (no meta file, no PyYAML).
``--strict`` promotes warnings to failures. ``policies/lint-rules.yml`` can
override any rule's severity — either as the committed list
(``rules: [{id, severity, params, key}]``) or as a map
(``rules: {<id>: {severity: error|warning|info|off}}``) — and the
``keep_events_min_days_prod`` threshold (``params: {days_min: 30}``). A rule
whose export key is still VERIFY here is capped at ``warning`` even when the
policy says ``error``: nothing unconfirmed blocks a PR or a hook.

Examples
--------
    ./scripts/lint_story.py stories/example-enrich-ip/story.json
    ./scripts/lint_story.py stories/                       # every */story.json
    ./scripts/lint_story.py stories/x/story.json --format json | jq .summary
    ./scripts/lint_story.py stories/x/story.json --format github   # CI annotations
    ./scripts/lint_story.py /tmp/export.json --meta /tmp/story.meta.yaml --no-policies
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tines_common import (  # noqa: E402
    CREDENTIAL_REF_RE,
    EMAIL_RE,
    POLICIES_DIR,
    RESOURCE_DYNAMIC_RE,
    RESOURCE_REF_RE,
    ScriptError,
    eprint,
    find_repo_root,
    is_placeholder_email,
    load_json_file,
    load_yaml_file,
    looks_like_secret,
    walk_strings,
)

# --------------------------------------------------------------------------- #
# Rule registry: id -> (default severity, confirmed|VERIFY, one-line intent)
# --------------------------------------------------------------------------- #

RULES: dict[str, tuple[str, str, str]] = {
    "valid_export": ("error", "confirmed", "schema_version, name, agents[], links[] present"),
    "not_normalised": ("error", "confirmed", "exported_at must be stripped (run export_story.py)"),
    "links_valid": ("error", "confirmed", "links reference agent indices in range"),
    "unique_agent_names": ("error", "confirmed", "no duplicate action names"),
    "agent_name_required": ("error", "confirmed", "every action has a name"),
    "agent_description_required": ("warning", "confirmed", "every action has a description"),
    "naming": ("error", "confirmed", "story name matches '[PREFIX] NN · Verb noun'"),
    "substory_suffix": ("warning", "confirmed", "Send to Story-enabled stories end in '(sub)'"),
    "substory_result_et": ("error", "confirmed", "sub-stories end on a message-only Event Transform named 'result'"),
    "substory_error_et": ("warning", "confirmed", "sub-stories carry an Event Transform named 'error' on the failure path"),
    "sts_timeout_required": ("warning", "VERIFY", "Send to Story tools carry a Timeout Duration"),
    "http_retry_bounds": ("error", "confirmed", "HTTP Request actions set retry_on_status covering 429 and 5xx; retries <= 8"),
    "http_emit_failure_event_always": ("info", "VERIFY", "HTTP Request actions emit a failure event Always"),
    "expected_status_excluded": ("warning", "VERIFY", "expected non-2xx (lock 422, empty 404) excluded from error logging"),
    "agent_output_schema_required": ("error", "confirmed", "every AI Agent action has an output schema"),
    "agent_token_alert_required": ("error", "confirmed", "every AI Agent action has an enabled token-usage Notify alert (+ Disable)"),
    "agent_post_trigger_required": ("error", "confirmed", "a Trigger follows every AI Agent action"),
    "agent_tool_count": ("warning", "confirmed", "at most five tools per AI Agent action"),
    "agent_meta_declared": ("error", "confirmed", "every AI Agent action is listed in story.meta.yaml ai.agents"),
    "ai_agent_budget_line_present": ("error", "confirmed", "every AI Agent action has a budget line in policies/cost-ceilings.yml"),
    "tool_description_min_sentences": ("warning", "confirmed", "tool descriptions are at least three sentences"),
    "tool_name_format": ("warning", "confirmed", "tool names are snake_case and <= 64 characters"),
    "tools_are_requests": ("error", "confirmed", "destructive-sounding tools are request_* tools"),
    "mcp_server_tool_hints": ("warning", "VERIFY", "MCP server action tools have Tool hints set (lookups Read only)"),
    "no_inline_secret": ("error", "confirmed", "no secret-looking strings anywhere in the export"),
    "email_in_export": ("error", "confirmed", "no real email addresses in the export"),
    "webhook_secret_in_export": ("error", "confirmed", "no action carries a real ingress path or secret (normalize.jq writes <assigned-on-import>)"),
    "recipients_not_cleared": ("warning", "confirmed", "recipients are cleared on export and set by ship"),
    "credentials_declared": ("error", "confirmed", "every CREDENTIAL.<name> reference is listed in story.meta.yaml"),
    "resources_declared": ("error", "confirmed", "every RESOURCE.<name> reference is listed in story.meta.yaml"),
    "meta_name_matches": ("error", "confirmed", "story.meta.yaml name equals the export name"),
    "monitoring_required_for_prod": ("error", "confirmed", "tier production: monitor_failures, recipients and a watchdog"),
    "keep_events_min_days_prod": ("error", "confirmed", "tier production: keep_events_for >= 30 days"),
    "change_control_required_for_prod": ("warning", "confirmed", "tier production: change_control: required"),
    "note_required": ("warning", "confirmed", "a Note on the canvas states purpose and mode"),
    "mode_badge": ("info", "confirmed", "a Note carries the Mode badge (Mode 1-4 or none)"),
    "schedule_sanity": ("error", "VERIFY", "schedules are 5-field cron and never inside a Group"),
    "disabled_actions": ("info", "confirmed", "disabled actions are listed for the reviewer"),
}

SEVERITY_ORDER = {"error": 3, "warning": 2, "info": 1, "skipped": 0}
NAME_RE = re.compile(r"^\[[A-Z]+\] [0-9]{2} · .+")
SUB_SUFFIX = "(sub)"
DESTRUCTIVE_TOOL_RE = re.compile(r"(block|delete|isolate|disable|suspend|quarantine|revoke|remove|purge|reset)", re.I)
LOOKUP_TOOL_RE = re.compile(r"(^|_)(get|list|lookup|search|read|fetch|describe)(_|$)", re.I)
SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
CRON_FIELDS = 5

LLM_TYPE = "Agents::LLMAgent"
HTTP_TYPE = "Agents::HTTPRequestAgent"
ET_TYPE = "Agents::EventTransformationAgent"
TRIGGER_TYPE = "Agents::TriggerAgent"
STS_TYPE = "Agents::SendToStoryAgent"
WEBHOOK_TYPE = "Agents::WebhookAgent"
# Ingress identifiers scripts/normalize.jq replaces on every action, by key name (mirror its ingress_keys).
INGRESS_KEYS = ("path", "secret")
INGRESS_PLACEHOLDER = "<assigned-on-import>"


def _is_formula(value: str) -> bool:
    return "<<" in value or value.lstrip().startswith("=")


def _is_placeholder(value: str) -> bool:
    """``<assigned-on-import>`` or another single ``<…>`` placeholder (never a formula)."""
    text = value.strip()
    return text == INGRESS_PLACEHOLDER or (text.startswith("<") and text.endswith(">") and not text.startswith("<<"))
MCP_TOOL_TYPE = "Agents::McpRequestAgent"
# The MCP server action's export type string was not observed; match defensively. VERIFY.
MCP_SERVER_TYPE_RE = re.compile(r"Agents::Mcp(?!Request).*Agent$|McpServer", re.I)
HINT_KEYS_READ_ONLY = ("read_only_hint", "readOnlyHint", "read_only", "readOnly")
HINT_KEYS_DESTRUCTIVE = ("destructive_hint", "destructiveHint", "destructive")
HINT_CONTAINERS = ("tool_hints", "hints", "annotations")


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    agent: Optional[str] = None
    path: Optional[str] = None
    verify: bool = False


@dataclass
class Context:
    file: Path
    export: dict[str, Any]
    meta: Optional[dict[str, Any]]
    cost_ceilings: Optional[dict[str, Any]]
    severities: dict[str, str]
    min_keep_days: int
    findings: list[Finding] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    # -- helpers ------------------------------------------------------------ #

    def add(self, rule: str, message: str, agent: Optional[str] = None, path: Optional[str] = None, severity: Optional[str] = None) -> None:
        sev = severity or self.severities.get(rule, RULES[rule][0])
        if sev == "off":
            return
        self.findings.append(Finding(rule, sev, message, agent, path, RULES[rule][1] == "VERIFY"))

    def skip(self, rule: str, why: str) -> None:
        self.skipped.append(f"{rule}: {why}")

    @property
    def agents(self) -> list[dict[str, Any]]:
        return [a for a in (self.export.get("agents") or []) if isinstance(a, dict)]

    @property
    def tier(self) -> str:
        return str((self.meta or {}).get("tier", "")).strip().lower()

    @property
    def is_substory(self) -> bool:
        return str(self.export.get("name", "")).rstrip().endswith(SUB_SUFFIX)


def sentence_count(text: str) -> int:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return sum(1 for part in parts if len(part.split()) >= 2)


def tool_display_name(tool: dict[str, Any]) -> str:
    options = tool.get("options") or {}
    return str(options.get("tool_name") or tool.get("name") or "?")


def tool_description(tool: dict[str, Any]) -> str:
    options = tool.get("options") or {}
    return str(options.get("tool_description") or tool.get("description") or "").strip()


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# --------------------------------------------------------------------------- #
# Checks — structural
# --------------------------------------------------------------------------- #


def check_structure(ctx: Context) -> bool:
    export = ctx.export
    ok = True
    for key in ("schema_version", "name"):
        if key not in export or export[key] in (None, ""):
            ctx.add("valid_export", f"missing top-level '{key}'")
            ok = False
    if not isinstance(export.get("agents"), list):
        ctx.add("valid_export", "'agents' must be a list")
        return False
    if not isinstance(export.get("links"), list):
        ctx.add("valid_export", "'links' must be a list")
        ok = False
    if "exported_at" in export:
        ctx.add("not_normalised", "export contains exported_at; run export_story.py (normalises) before committing")

    count = len(ctx.agents)
    for index, link in enumerate(export.get("links") or []):
        if not isinstance(link, dict):
            ctx.add("links_valid", f"links[{index}] is not an object")
            continue
        for end in ("source", "receiver"):
            value = link.get(end)
            if not isinstance(value, int) or value < 0 or value >= count:
                ctx.add("links_valid", f"links[{index}].{end}={value!r} is out of range (0..{count - 1})")

    seen: dict[str, int] = {}
    for index, agent in enumerate(ctx.agents):
        name = agent.get("name")
        if not name:
            ctx.add("agent_name_required", f"agents[{index}] ({agent.get('type')}) has no name", path=f"$.agents[{index}]")
            continue
        if name in seen:
            ctx.add("unique_agent_names", f"duplicate action name {name!r} (agents[{seen[name]}] and agents[{index}])", agent=name)
        seen.setdefault(name, index)
        if not (agent.get("description") or "").strip() and agent.get("type") != "Agents::GroupAgent":
            ctx.add("agent_description_required", "no description (state what the action does)", agent=name)
        if agent.get("disabled"):
            ctx.add("disabled_actions", "action is disabled in this export", agent=name)
    return ok


# --------------------------------------------------------------------------- #
# Checks — naming and sub-story contract
# --------------------------------------------------------------------------- #


def check_naming(ctx: Context) -> None:
    name = str(ctx.export.get("name") or "")
    if not NAME_RE.match(name):
        ctx.add("naming", f"story name {name!r} must match '[PREFIX] NN · Verb noun' (middle dot, two-digit number)")
    if ctx.export.get("send_to_story_enabled") and not ctx.is_substory:
        ctx.add("substory_suffix", "Send to Story is enabled but the name does not end in '(sub)'")
    if ctx.is_substory:
        ets = {a.get("name"): a for a in ctx.agents if a.get("type") == ET_TYPE}
        result = ets.get("result")
        if result is None:
            ctx.add("substory_result_et", "sub-story has no Event Transform named 'result'")
        elif (result.get("options") or {}).get("mode") != "message_only":
            ctx.add("substory_result_et", "'result' Event Transform must be in message-only mode", agent="result")
        else:
            payload = (result.get("options") or {}).get("payload")
            if isinstance(payload, dict) and not 3 <= len(payload) <= 5:
                ctx.add("substory_result_et", f"'result' emits {len(payload)} fields; the contract is 3-5", agent="result", severity="warning")
        if "error" not in ets:
            ctx.add("substory_error_et", "sub-story has no Event Transform named 'error' ({status, error_category, retryable, message})")
        if not ctx.export.get("send_to_story_timeout_enabled"):
            ctx.add("sts_timeout_required", "send_to_story_timeout_enabled is false; set a Timeout Duration on the sub-story")


# --------------------------------------------------------------------------- #
# Checks — HTTP Request hardening
# --------------------------------------------------------------------------- #


def _covers(statuses: Iterable[Any], wanted: str) -> bool:
    for status in statuses:
        text = str(status).strip()
        if text == wanted:
            return True
        if wanted.startswith("5") and (text in ("5xx", "500-599", "500..599") or re.match(r"^5\d\d$", text)):
            return True
    return False


def check_http(ctx: Context) -> None:
    for agent in ctx.agents:
        if agent.get("type") != HTTP_TYPE:
            continue
        name = agent.get("name")
        options = agent.get("options") or {}
        retry = options.get("retry_on_status")
        if retry is None:
            ctx.add("http_retry_bounds", "no retry_on_status; set it to [429, 500-599] (retries 5-8, not the default 25)", agent=name)
        else:
            statuses = retry if isinstance(retry, list) else [retry]
            missing = [w for w in ("429", "5xx") if not _covers(statuses, w)]
            if missing:
                ctx.add("http_retry_bounds", f"retry_on_status={statuses!r} does not cover {', '.join(missing)}", agent=name, severity="warning")
        retries = options.get("retries")  # VERIFY: key name in exports
        if retries is not None:
            try:
                if int(retries) > 8:
                    ctx.add("http_retry_bounds", f"retries={retries} exceeds 8 (25 retries ~ 3 h 20 min of silence)", agent=name)
            except (TypeError, ValueError):
                ctx.add("http_retry_bounds", f"retries={retries!r} is not an integer", agent=name, severity="warning")
        emit = options.get("emit_failure_event")  # VERIFY: observed on Run Script actions only
        if emit is None:
            ctx.add("http_emit_failure_event_always", "emit_failure_event not present in export (key VERIFY); set 'Emit failure event: Always' in the UI", agent=name)
        elif str(emit).lower() not in ("always", "true"):
            ctx.add("http_emit_failure_event_always", f"emit_failure_event={emit!r}; the house rule is Always (timeouts and DNS failures are missed otherwise)", agent=name, severity="error")
        log_on = options.get("log_error_on_status")  # VERIFY
        url = str(options.get("url") or "")
        if log_on is not None and "global_resources/" in url and "/replace" in url and _covers(log_on if isinstance(log_on, list) else [log_on], "422"):
            ctx.add("expected_status_excluded", "compare-and-swap lock logs 422 as an error; exclude it (422 = already running)", agent=name)


# --------------------------------------------------------------------------- #
# Checks — AI Agent actions and their tools
# --------------------------------------------------------------------------- #


def _meta_agents(ctx: Context) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in (((ctx.meta or {}).get("ai") or {}).get("agents") or []):
        if isinstance(entry, dict) and entry.get("name"):
            out[slugify(str(entry["name"]))] = entry
    return out


def _budget_refs(ctx: Context) -> set[str]:
    agents = ((ctx.cost_ceilings or {}).get("agents") or {})
    return {str(k) for k in agents} if isinstance(agents, dict) else set()


def check_ai_agents(ctx: Context) -> None:
    links = [l for l in (ctx.export.get("links") or []) if isinstance(l, dict)]
    meta_agents = _meta_agents(ctx) if ctx.meta is not None else None
    budget_refs = _budget_refs(ctx) if ctx.cost_ceilings is not None else None
    slug = str((ctx.meta or {}).get("slug") or ctx.file.parent.name)

    for index, agent in enumerate(ctx.agents):
        if agent.get("type") != LLM_TYPE:
            continue
        name = str(agent.get("name") or f"agents[{index}]")
        options = agent.get("options") or {}
        mode = options.get("mode", "task")

        schema = options.get("output_structure")
        if not isinstance(schema, dict) or not schema:
            ctx.add("agent_output_schema_required", f"AI Agent action ({mode} mode) has no output schema (options.output_structure)", agent=name)
        elif "properties" not in schema and "type" not in schema:
            ctx.add("agent_output_schema_required", "output_structure is not a JSON schema object (no type/properties)", agent=name, severity="warning")

        thresholds = (agent.get("monitoring") or {}).get("ai_monitoring_thresholds") or []
        enabled = [t for t in thresholds if isinstance(t, dict) and t.get("enabled")]
        notify = [t for t in enabled if t.get("threshold_type") == "notify"]
        disable = [t for t in enabled if t.get("threshold_type") == "disable_action"]
        if not notify:
            ctx.add("agent_token_alert_required", "no enabled token-usage Notify alert on the Status tab (monitoring.ai_monitoring_thresholds)", agent=name)
        if not disable:
            ctx.add("agent_token_alert_required", "no enabled 'Disable action' token threshold; add one above the Notify threshold", agent=name, severity="warning")
        for n in notify:
            for d in disable:
                if n.get("period") == d.get("period") and isinstance(n.get("threshold"), (int, float)) and isinstance(d.get("threshold"), (int, float)) and d["threshold"] <= n["threshold"]:
                    ctx.add("agent_token_alert_required", f"Disable threshold ({d['threshold']}) is not above Notify ({n['threshold']}) for period {n.get('period')}", agent=name, severity="warning")

        successors = [ctx.agents[l["receiver"]] for l in links if l.get("source") == index and isinstance(l.get("receiver"), int) and 0 <= l["receiver"] < len(ctx.agents)]
        if not any(s.get("type") == TRIGGER_TYPE for s in successors):
            ctx.add("agent_post_trigger_required", "no Trigger directly after the AI Agent action (branch on an explicit schema field, never on prose)", agent=name)

        tools = [t for t in (agent.get("tools") or []) if isinstance(t, dict)]
        if len(tools) > 5:
            ctx.add("agent_tool_count", f"{len(tools)} tools; the house rule is one first, at most five — split the job across agents", agent=name)
        for tool in tools:
            _check_tool(ctx, tool, owner=name, server=False)

        if meta_agents is not None:
            entry = meta_agents.get(slugify(name))
            if entry is None:
                ctx.add("agent_meta_declared", f"not listed in story.meta.yaml ai.agents (expected name {name!r})", agent=name)
            else:
                if not entry.get("output_schema"):
                    ctx.add("agent_meta_declared", "meta entry lacks output_schema: true", agent=name, severity="warning")
                if not entry.get("token_alert"):
                    ctx.add("agent_meta_declared", "meta entry lacks token_alert: {notify, disable}", agent=name)
                ref = entry.get("budget_ref") or f"{slug}/{slugify(name)}"
                if budget_refs is not None and ref not in budget_refs:
                    ctx.add("ai_agent_budget_line_present", f"budget_ref {ref!r} is not in policies/cost-ceilings.yml agents", agent=name)
        elif budget_refs is not None:
            ref = f"{slug}/{slugify(name)}"
            if ref not in budget_refs:
                ctx.add("ai_agent_budget_line_present", f"no budget line {ref!r} in policies/cost-ceilings.yml (no meta to map a different ref)", agent=name)


def _hint_value(tool: dict[str, Any], keys: tuple[str, ...]) -> Optional[bool]:
    """Find a Tool-hint flag on a tool object (key names VERIFY)."""
    containers: list[dict[str, Any]] = [tool, tool.get("options") or {}]
    for base in (tool, tool.get("options") or {}):
        for holder in HINT_CONTAINERS:
            if isinstance(base.get(holder), dict):
                containers.append(base[holder])
    for container in containers:
        for key in keys:
            if key in container and isinstance(container[key], bool):
                return container[key]
    return None


def _check_tool(ctx: Context, tool: dict[str, Any], owner: str, server: bool) -> None:
    tname = tool_display_name(tool)
    label = f"{owner} → {tname}"
    desc = tool_description(tool)
    sentences = sentence_count(desc)
    if sentences < 3:
        ctx.add(
            "tool_description_min_sentences",
            f"tool description has {sentences} sentence(s); write 3-4: what it does, when to use it, parameters, an example argument"
            + (" (descriptions are the API for Mode 4 consumers)" if server else ""),
            agent=label,
            severity="error" if server else None,
        )
    if DESTRUCTIVE_TOOL_RE.search(tname) and not tname.lower().startswith("request_"):
        ctx.add("tools_are_requests", f"tool {tname!r} sounds destructive; expose it as request_<verb> that posts an approval and returns approval_id", agent=label)
    if server or tool.get("type") == MCP_TOOL_TYPE:
        if not SNAKE_RE.match(tname) or len(tname) > 64:
            ctx.add("tool_name_format", f"tool name {tname!r} should be snake_case and <= 64 characters (namespace it, e.g. ops_get_error_logs)", agent=label)
    if tool.get("type") == STS_TYPE:
        options = tool.get("options") or {}
        if not any("timeout" in str(k).lower() for k in options):
            ctx.add("sts_timeout_required", "Send to Story tool shows no timeout key in the export (key VERIFY); confirm a Timeout Duration is set", agent=label)
    if server:
        read_only = _hint_value(tool, HINT_KEYS_READ_ONLY)
        destructive = _hint_value(tool, HINT_KEYS_DESTRUCTIVE)
        if read_only is None and destructive is None:
            ctx.add("mcp_server_tool_hints", "no Tool hints found in the export (key names VERIFY); set Read only on every lookup", agent=label)
        else:
            is_lookup = bool(LOOKUP_TOOL_RE.search(tname))
            if is_lookup and read_only is not True:
                ctx.add("mcp_server_tool_hints", "lookup tool is not marked Read only (Claude clients will prompt on every call)", agent=label, severity="error")
            if tname.lower().startswith("request_") and read_only is True:
                ctx.add("mcp_server_tool_hints", "request tool is marked Read only; it must keep the Destructive hint so clients confirm", agent=label, severity="error")


def check_mcp_servers(ctx: Context) -> None:
    for agent in ctx.agents:
        atype = str(agent.get("type") or "")
        if not MCP_SERVER_TYPE_RE.search(atype) or atype == MCP_TOOL_TYPE:
            continue
        name = str(agent.get("name") or "?")
        tools = [t for t in (agent.get("tools") or []) if isinstance(t, dict)]
        if not tools:
            ctx.add("mcp_server_tool_hints", f"MCP server action ({atype}) exposes no tools in the export (shape VERIFY)", agent=name)
        if not (agent.get("description") or "").strip():
            ctx.add("agent_description_required", "MCP server action description is exposed to clients as instructions; write it", agent=name, severity="error")
        if len(tools) > 8:
            ctx.add("agent_tool_count", f"{len(tools)} tools on one server; house rule is 3-8 per server, one server per use case", agent=name)
        for tool in tools:
            _check_tool(ctx, tool, owner=name, server=True)


# --------------------------------------------------------------------------- #
# Checks — secrets, references, recipients
# --------------------------------------------------------------------------- #


def check_secrets_and_refs(ctx: Context) -> None:
    export = ctx.export
    creds: set[str] = set()
    resources: set[str] = set()
    dynamic_resource = False
    for path, value in walk_strings(export):
        if path.startswith("$.recipients"):
            continue
        pattern = looks_like_secret(value)
        if pattern:
            ctx.add("no_inline_secret", f"value at {path} matches secret pattern '{pattern}'; reference a credential by name instead", path=path)
        for match in EMAIL_RE.finditer(value):
            if not is_placeholder_email(match.group(0)):
                ctx.add("email_in_export", f"email address at {path}; use a Resource or a *.invalid placeholder", path=path)
                break
        creds.update(CREDENTIAL_REF_RE.findall(value))
        resources.update(RESOURCE_REF_RE.findall(value))
        if RESOURCE_DYNAMIC_RE.search(value):
            dynamic_resource = True

    # Ingress identifiers, by KEY NAME on every action type (a Webhook action and an MCP server action both carry
    # a path; a Webhook action, and an MCP server action in secret mode, a secret). scripts/normalize.jq replaces
    # them with INGRESS_PLACEHOLDER; anything else here is a live URL component anyone with the repo could post to.
    for index, agent in enumerate(ctx.agents):
        options = agent.get("options") or {}
        for key in INGRESS_KEYS:
            value = options.get(key)
            if not isinstance(value, str) or value == "":
                continue
            if key == "path" and _is_formula(value):
                continue  # an Event Transform explode path such as <<findings.anomalies>> is not an ingress id
            if _is_placeholder(value):
                continue
            ctx.add(
                "webhook_secret_in_export",
                f"options.{key} carries a real ingress identifier; re-export (scripts/normalize.jq writes {INGRESS_PLACEHOLDER!r}) — "
                "stable production URLs live in environment secrets and are re-applied at ship time, never in the export",
                agent=agent.get("name"),
                path=f"$.agents[{index}].options.{key}",
            )

    if export.get("recipients"):
        ctx.add("recipients_not_cleared", f"{len(export['recipients'])} recipient(s) in the export; export with clear_recipients=true and let ship set them from the manifest")

    if ctx.meta is None:
        if creds or resources:
            ctx.skip("credentials_declared", f"no story.meta.yaml to compare against (refs: credentials={sorted(creds)}, resources={sorted(resources)})")
        return
    declared_creds = {str(c) for c in (ctx.meta.get("credentials") or [])}
    declared_res = {str(r) for r in (ctx.meta.get("resources") or [])}
    for cred in sorted(creds - declared_creds):
        ctx.add("credentials_declared", f"CREDENTIAL.{cred} is referenced but not listed in story.meta.yaml credentials")
    for cred in sorted(declared_creds - creds):
        ctx.add("credentials_declared", f"credential {cred!r} is listed in meta but never referenced", severity="info")
    for res in sorted(resources - declared_res):
        ctx.add("resources_declared", f"RESOURCE.{res} is referenced but not listed in story.meta.yaml resources")
    if dynamic_resource:
        ctx.add("resources_declared", "dynamic RESOURCE[...] references found; the reviewer must confirm the names in meta by hand", severity="info")


# --------------------------------------------------------------------------- #
# Checks — meta, monitoring, retention, notes, schedules
# --------------------------------------------------------------------------- #


def check_meta_and_prod(ctx: Context) -> None:
    export = ctx.export
    if ctx.meta is None:
        for rule in ("meta_name_matches", "monitoring_required_for_prod", "keep_events_min_days_prod", "change_control_required_for_prod", "agent_meta_declared"):
            ctx.skip(rule, "no story.meta.yaml next to the export (or PyYAML missing)")
        return
    meta = ctx.meta
    if meta.get("name") and meta["name"] != export.get("name"):
        ctx.add("meta_name_matches", f"story.meta.yaml name {meta['name']!r} != export name {export.get('name')!r}")
    if ctx.tier != "production":
        return
    monitoring = meta.get("monitoring") or {}
    if monitoring.get("monitor_failures") is not True:
        ctx.add("monitoring_required_for_prod", "meta monitoring.monitor_failures must be true for tier production")
    recipients = monitoring.get("recipients")
    if recipients not in ("manifest",) and not (isinstance(recipients, list) and recipients):
        ctx.add("monitoring_required_for_prod", "meta monitoring.recipients must be 'manifest' (resolved by ship) or a non-empty list")
    watchdog = monitoring.get("no_events_watchdog") or {}
    action_name, seconds = watchdog.get("action"), watchdog.get("seconds")
    names = {a.get("name") for a in ctx.agents}
    if not action_name or not seconds:
        ctx.add("monitoring_required_for_prod", "meta monitoring.no_events_watchdog {action, seconds} is required (≈ 2× the entry/schedule interval)")
    elif action_name not in names:
        ctx.add("monitoring_required_for_prod", f"watchdog action {action_name!r} does not exist in the export")
    else:
        agent = next(a for a in ctx.agents if a.get("name") == action_name)
        current = (agent.get("monitoring") or {}).get("monitor_no_events_emitted")
        if current in (None, 0):
            ctx.add("monitoring_required_for_prod", f"watchdog on {action_name!r} is not set in the export yet (ship sets monitor_no_events_emitted={seconds})", severity="info")
    if export.get("monitor_failures") is not True:
        ctx.add("monitoring_required_for_prod", "export monitor_failures is false (ship sets it on the draft; fine before first ship)", severity="info")

    keep = export.get("keep_events_for")
    min_seconds = ctx.min_keep_days * 86400
    try:
        if keep is None or int(keep) < min_seconds:
            ctx.add("keep_events_min_days_prod", f"keep_events_for={keep!r} seconds is below {ctx.min_keep_days} days ({min_seconds}); raise event retention by hand")
    except (TypeError, ValueError):
        ctx.add("keep_events_min_days_prod", f"keep_events_for={keep!r} is not a number of seconds", severity="warning")
    if str(meta.get("change_control", "")).lower() != "required":
        ctx.add("change_control_required_for_prod", "meta change_control should be 'required' for tier production")


def check_notes_and_schedules(ctx: Context) -> None:
    notes = [n for n in (ctx.export.get("diagram_notes") or []) if isinstance(n, dict)]
    if not notes:
        ctx.add("note_required", "no Note on the canvas; add one stating purpose, inputs, outputs and mode")
    elif not any(
        re.search(
            # 'Mode 3', 'mode: none' / 'mode: sub-story' (meta style), and the prompt pack's
            # 'Mode badge: none' / 'Mode badge: sub-story' / 'Mode badge: **Mode 4**'
            r"\bMode\s*[1-4]\b|\bmode:\s*(none|sub-story|mode-[34])|\bMode badge:\s*\**\s*(none|sub-story|Mode\s*[1-4])\b",
            str(n.get("content") or ""),
            re.I,
        )
        for n in notes
    ):
        ctx.add("mode_badge", "no Note carries a Mode badge ('Mode badge: none | sub-story | Mode 1-4', or 'Mode: none')")

    for index, agent in enumerate(ctx.agents):
        schedule = agent.get("schedule")
        if not schedule:
            continue
        name = agent.get("name")
        if agent.get("group"):
            ctx.add("schedule_sanity", "scheduled action sits inside a Group; schedules never go inside Groups", agent=name)
        entries = schedule if isinstance(schedule, list) else [schedule]
        for entry in entries:
            cron = entry.get("cron") if isinstance(entry, dict) else None
            if cron is None:
                ctx.add("schedule_sanity", f"schedule shape {type(entry).__name__} without 'cron' (shape VERIFY)", agent=name, severity="info")
                continue
            fields = str(cron).split()
            if len(fields) != CRON_FIELDS:
                ctx.add("schedule_sanity", f"cron {cron!r} does not have {CRON_FIELDS} fields", agent=name)
        watchdog = (agent.get("monitoring") or {}).get("monitor_no_events_emitted")
        if ctx.tier == "production" and watchdog in (None, 0):
            ctx.add("monitoring_required_for_prod", "scheduled action has no 'notify if no events emitted' watchdog", agent=name, severity="warning")


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


# policies/lint-rules.yml ids that this script implements under a different name.
POLICY_RULE_ALIASES: dict[str, str] = {
    "unique_action_names": "unique_agent_names",
    "agent_tool_cap": "agent_tool_count",
    "mode4_read_only_hints": "mcp_server_tool_hints",
}
# Policy ids with no implementation in this script (documented in scripts/README.md):
#   http_failure_path_connected — how failure links appear in links[] is VERIFY
#   never_touch_targets         — enforced at write time by set_monitoring.py / guard-mcp.sh
#   manifest_consistency        — checked by lint.yml against stories/_manifest.yaml
POLICY_RULES_NOT_IMPLEMENTED = {"http_failure_path_connected", "never_touch_targets", "manifest_consistency"}


def load_policies(root: Path, no_policies: bool, rules_path: Optional[Path], ceilings_path: Optional[Path]) -> tuple[dict[str, str], int, Optional[dict[str, Any]], list[str]]:
    """Read severities and thresholds from ``policies/lint-rules.yml`` and ``cost-ceilings.yml``.

    ``rules:`` is accepted in both shapes — the committed list of
    ``{id, severity, params, key}`` entries and a map ``{<id>: {severity: …}}``
    or ``{<id>: "error"}``. A policy may raise or lower any rule's severity,
    with one guard: a rule whose export key is still **VERIFY** in this script
    is capped at ``warning`` even if the policy says ``error``, so nothing
    unconfirmed can block a PR or a hook (DESIGN.md §9.2, docs/VERIFY.md #8).
    """
    severities: dict[str, str] = {}
    min_days = 30
    ceilings: Optional[dict[str, Any]] = None
    notes: list[str] = []
    if no_policies:
        return severities, min_days, ceilings, notes
    rules_file = rules_path or (root / POLICIES_DIR / "lint-rules.yml")
    ceilings_file = ceilings_path or (root / POLICIES_DIR / "cost-ceilings.yml")
    for label, path in (("lint-rules", rules_file), ("cost-ceilings", ceilings_file)):
        if not path.exists():
            notes.append(f"{label}: {path} not found")
            continue
        try:
            data = load_yaml_file(path)
        except SystemExit:
            notes.append(f"{label}: PyYAML missing; defaults used")
            continue
        if label == "cost-ceilings":
            ceilings = data if isinstance(data, dict) else {}
            continue

        rules = data.get("rules", data) if isinstance(data, dict) else {}
        entries: list[tuple[str, Any]] = []
        if isinstance(rules, list):
            for item in rules:
                if isinstance(item, dict) and item.get("id"):
                    entries.append((str(item["id"]), item))
        elif isinstance(rules, dict):
            entries = [(str(k), v) for k, v in rules.items()]

        capped: list[str] = []
        unknown: list[str] = []
        for raw_id, cfg in entries:
            rule_id = POLICY_RULE_ALIASES.get(raw_id, raw_id)
            if rule_id not in RULES:
                if raw_id not in POLICY_RULES_NOT_IMPLEMENTED:
                    unknown.append(raw_id)
                continue
            sev: Optional[str] = None
            if isinstance(cfg, dict):
                sev = str(cfg.get("severity", "")).lower() or None
                if cfg.get("enabled") is False:
                    sev = "off"
                params = cfg.get("params") if isinstance(cfg.get("params"), dict) else {}
                if rule_id == "keep_events_min_days_prod":
                    for key in ("days_min", "min_days"):
                        if isinstance(cfg.get(key), int):
                            min_days = cfg[key]
                        if isinstance(params.get(key), int):
                            min_days = params[key]
            elif isinstance(cfg, str):
                sev = cfg.lower()
            elif isinstance(cfg, int) and rule_id == "keep_events_min_days_prod":
                min_days = cfg
                continue
            if sev not in ("error", "warning", "info", "off"):
                continue
            if sev == "error" and RULES[rule_id][1] == "VERIFY":
                capped.append(raw_id)
                sev = "warning"
            severities[rule_id] = sev
        if capped:
            notes.append(
                "lint-rules: capped at 'warning' until one real export confirms the key (docs/VERIFY.md #8): "
                + ", ".join(capped)
            )
        if unknown:
            notes.append("lint-rules: no implementation here for: " + ", ".join(unknown) + " (see scripts/README.md)")
    return severities, min_days, ceilings, notes


def lint_file(file: Path, meta_path: Optional[Path], severities: dict[str, str], min_days: int, ceilings: Optional[dict[str, Any]]) -> Context:
    try:
        export = load_json_file(file)
    except json.JSONDecodeError as exc:
        ctx = Context(file, {}, None, ceilings, severities, min_days)
        ctx.add("valid_export", f"invalid JSON: {exc}")
        return ctx
    if not isinstance(export, dict):
        ctx = Context(file, {}, None, ceilings, severities, min_days)
        ctx.add("valid_export", "top level is not an object")
        return ctx

    meta: Optional[dict[str, Any]] = None
    candidate = meta_path or file.parent / "story.meta.yaml"
    meta_note: Optional[str] = None
    if candidate.exists():
        try:
            loaded = load_yaml_file(candidate)
            meta = loaded if isinstance(loaded, dict) else {}
        except SystemExit:
            meta_note = "PyYAML missing"
    ctx = Context(file, export, meta, ceilings, severities, min_days)
    if meta_note:
        ctx.skip("story.meta.yaml", meta_note)

    if check_structure(ctx):
        check_naming(ctx)
        check_http(ctx)
        check_ai_agents(ctx)
        check_mcp_servers(ctx)
        check_secrets_and_refs(ctx)
        check_meta_and_prod(ctx)
        check_notes_and_schedules(ctx)
    ctx.findings.sort(key=lambda f: (-SEVERITY_ORDER.get(f.severity, 0), f.rule, f.agent or ""))
    return ctx


def collect_targets(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        if path.is_dir():
            out.extend(sorted(p for p in path.glob("*/story.json") if "_template" not in p.parts))
        elif path.exists():
            out.append(path)
        else:
            raise ScriptError(f"not found: {path}")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lint_story.py",
        description="Deterministic convention checks over story exports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Rules:\n" + "\n".join(f"  {k:34s} {v[0]:8s} {v[1]:10s} {v[2]}" for k, v in RULES.items()),
    )
    parser.add_argument("paths", nargs="+", type=Path, help="story.json files or directories containing */story.json")
    parser.add_argument("--meta", type=Path, help="story.meta.yaml to use (default: next to the export)")
    parser.add_argument("--rules", type=Path, help="policies/lint-rules.yml (default: auto-detected)")
    parser.add_argument("--cost-ceilings", type=Path, help="policies/cost-ceilings.yml (default: auto-detected)")
    parser.add_argument("--no-policies", action="store_true", help="ignore policies/*.yml and use built-in defaults")
    parser.add_argument("--format", choices=("text", "json", "github"), default="text")
    parser.add_argument("--strict", action="store_true", help="warnings also fail the run")
    parser.add_argument("--quiet", action="store_true", help="print only errors (text/github formats)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = find_repo_root()
    severities, min_days, ceilings, notes = load_policies(root, args.no_policies, args.rules, args.cost_ceilings)
    for note in notes:
        if not args.quiet or "not found" in note:
            eprint(f"[lint] {note}")

    targets = collect_targets(args.paths)
    if not targets:
        raise ScriptError("no story.json files found")

    contexts = [lint_file(path, args.meta, severities, min_days, ceilings) for path in targets]
    total_errors = total_warnings = 0
    report: list[dict[str, Any]] = []
    for ctx in contexts:
        errors = sum(1 for f in ctx.findings if f.severity == "error")
        warnings = sum(1 for f in ctx.findings if f.severity == "warning")
        total_errors += errors
        total_warnings += warnings
        rel = ctx.file.relative_to(root) if ctx.file.is_relative_to(root) else ctx.file
        if args.format == "json":
            report.append(
                {
                    "path": str(rel),
                    "findings": [asdict(f) for f in ctx.findings],
                    "skipped": ctx.skipped,
                    "summary": {"errors": errors, "warnings": warnings, "info": len(ctx.findings) - errors - warnings},
                }
            )
            continue
        for f in ctx.findings:
            if args.quiet and f.severity != "error":
                continue
            where = f" [{f.agent}]" if f.agent else ""
            verify = " (VERIFY)" if f.verify else ""
            if args.format == "github":
                level = {"error": "error", "warning": "warning"}.get(f.severity, "notice")
                print(f"::{level} file={rel},title={f.rule}::{f.message}{where}{verify}")
            else:
                print(f"{rel}: {f.rule}: {f.severity}:{where} {f.message}{verify}")
        for item in ctx.skipped:
            if not args.quiet:
                print(f"{rel}: skipped: {item}")
        eprint(f"[lint] {rel}: {errors} error(s), {warnings} warning(s), {len(ctx.findings) - errors - warnings} info")

    if args.format == "json":
        print(json.dumps({"files": report, "summary": {"errors": total_errors, "warnings": total_warnings}}, indent=2))

    if total_errors or (args.strict and total_warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
