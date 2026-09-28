#!/usr/bin/env python3
"""Read-side helpers shared by the observability subcommands.

``live_activity.py``, ``action_logs.py``, ``story_runs.py``, ``ai_usage.py`` and
``audit_logs.py`` read lists from the Tines API and print them for a person, a
workflow or a skill. This module holds what they share, so ``tines_common.py``
stays the single home of the client, the manifest and the secret patterns:

* ``default_env``      — ``--env`` default for read commands: ``TINES_ENV`` or ``dev``.
* ``parse_when``       — accept ``2026-09-25T03:00:00Z``, ``2026-09-25``, an ISO
                         time with an offset, or a relative ``15m`` / ``1h`` /
                         ``2d`` / ``1w`` (also ``now-1h``) and return a UTC
                         ``YYYY-MM-DDTHH:MM:SSZ`` string.
* ``extract_rows``     — pull the list out of a response envelope. The envelope
                         key of each list endpoint is **VERIFY** (the research
                         names the fields inside the rows, not the wrapper), so
                         the caller passes the likely keys and this falls back to
                         the first list-valued key.
* ``fetch_pages``      — ``page`` / ``per_page`` pagination with a page cap and a
                         pause between pages (rate limits in DESIGN.md §6.6).
                         Follows ``meta.next_page`` when the response carries it
                         (VERIFY #27), otherwise stops at the first short page.
* ``scrub``            — redact anything matching ``tines_common.SECRET_PATTERNS``
                         before it is printed. Error logs, audit rows and run
                         events are attacker-influenceable and can echo a token.
* ``markdown_table``   — a bounded Markdown table for job summaries and PR bodies.

No function here calls an endpoint of its own: callers pass the path, and every
path they pass is one DESIGN.md §3.5 / §4 / §5 names.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import statistics
import time
from typing import Any, Iterable, Optional, Sequence

from tines_common import SECRET_PATTERNS, ApiError, ScriptError, eprint

RELATIVE_RE = re.compile(r"^(?:now-)?(\d+)\s*([smhdw])$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
GUID_RE = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def default_env() -> str:
    """The manifest environment a read command uses when ``--env`` is not given."""
    return os.environ.get("TINES_ENV") or "dev"


def utc_iso(moment: _dt.datetime) -> str:
    return moment.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_when(text: str, *, now: Optional[_dt.datetime] = None) -> str:
    """Return a UTC ISO-8601 timestamp for an absolute or relative time.

    Raises ``ScriptError`` with the accepted forms when the text is neither.
    """
    raw = (text or "").strip()
    if not raw:
        raise ScriptError("a time is required (ISO 8601 like 2026-09-25T03:00:00Z, or relative like 1h, 2d)")
    current = now or _dt.datetime.now(_dt.timezone.utc)
    rel = RELATIVE_RE.match(raw)
    if rel:
        seconds = int(rel.group(1)) * _UNIT_SECONDS[rel.group(2).lower()]
        return utc_iso(current - _dt.timedelta(seconds=seconds))
    candidate = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
    try:
        parsed = _dt.datetime.fromisoformat(candidate)
    except ValueError:
        raise ScriptError(
            f"cannot read the time {raw!r}: use ISO 8601 (2026-09-25T03:00:00Z, 2026-09-25) "
            "or a relative age (15m, 1h, 2d, 1w)"
        ) from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return utc_iso(parsed)


def extract_rows(response: Any, preferred_keys: Sequence[str] = ()) -> list[dict[str, Any]]:
    """Return the list of row objects inside a list response (envelope key VERIFY)."""
    if isinstance(response, list):
        return [r for r in response if isinstance(r, dict)]
    if not isinstance(response, dict):
        return []
    for key in preferred_keys:
        value = response.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    for key, value in response.items():
        if key != "meta" and isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []


def _next_page(response: Any) -> Optional[int]:
    """``meta.next_page`` when present (VERIFY #27); None otherwise."""
    if not isinstance(response, dict):
        return None
    meta = response.get("meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("next_page")
    try:
        return int(value) if value not in (None, "", False) else None
    except (TypeError, ValueError):
        return None


def _has_meta(response: Any) -> bool:
    return isinstance(response, dict) and isinstance(response.get("meta"), dict)


def fetch_pages(
    client: Any,
    path: str,
    params: dict[str, Any],
    *,
    preferred_keys: Sequence[str] = (),
    per_page: int = 100,
    max_pages: int = 20,
    pause_seconds: float = 0.1,
) -> tuple[list[dict[str, Any]], bool]:
    """GET ``path`` page by page. Returns ``(rows, truncated)``.

    ``truncated`` is True when ``max_pages`` stopped the walk while more pages
    were indicated — callers say so rather than presenting a partial list as whole.
    """
    rows: list[dict[str, Any]] = []
    page = 1
    for index in range(max_pages):
        query = {**params, "per_page": per_page, "page": page}
        response = client.get(path, **query)
        batch = extract_rows(response, preferred_keys)
        rows.extend(batch)
        following = _next_page(response)
        if following is not None:
            more = True
            page = following
        elif _has_meta(response):
            more = False  # a meta block without next_page: this was the last page
        else:
            more = len(batch) >= per_page
            page += 1
        if not more:
            return rows, False
        if index + 1 < max_pages and pause_seconds:
            time.sleep(pause_seconds)
    return rows, True


def scrub(text: Any) -> str:
    """Return ``text`` as a string with every secret-looking span redacted."""
    out = "" if text is None else str(text)
    for name, pattern in SECRET_PATTERNS:
        out = pattern.sub(f"[redacted:{name}]", out)
    return out


def scrub_obj(obj: Any) -> Any:
    """Recursively scrub every string inside a JSON structure."""
    if isinstance(obj, str):
        return scrub(obj)
    if isinstance(obj, dict):
        return {k: scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_obj(v) for v in obj]
    return obj


def one_line(value: Any, limit: int = 160) -> str:
    """Collapse whitespace, scrub secrets and truncate — for table cells and titles."""
    text = re.sub(r"\s+", " ", scrub(value)).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def num(value: Any) -> Optional[float]:
    """A number from an API value, or None when it is not numeric."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def median(values: Iterable[float]) -> Optional[float]:
    data = [v for v in values if v is not None]
    return statistics.median(data) if data else None


def fmt(value: Any) -> str:
    """Render a cell: booleans lowercase, floats trimmed, None as an em dash."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def markdown_table(rows: Sequence[dict[str, Any]], columns: Sequence[tuple[str, str]], *, limit: int = 200, cell_limit: int = 120) -> str:
    """A Markdown table of ``rows`` with ``columns`` = [(key, header), …]."""
    if not rows:
        return "_no rows_\n"
    head = "| " + " | ".join(h for _, h in columns) + " |"
    rule = "|" + "|".join("---" for _ in columns) + "|"
    lines = [head, rule]
    for row in rows[:limit]:
        cells = [one_line(fmt(row.get(key)), cell_limit).replace("|", "\\|") for key, _ in columns]
        lines.append("| " + " | ".join(cells) + " |")
    if len(rows) > limit:
        lines.append(f"\n_{len(rows) - limit} more row(s) not shown._")
    return "\n".join(lines) + "\n"


def check_guid(value: str, what: str = "run guid") -> str:
    if not GUID_RE.match(value or ""):
        raise ScriptError(f"{what} {value!r} does not look like a Tines guid (letters, digits, hyphens)")
    return value


def api_or_exit(call, *args: Any, **kwargs: Any) -> Any:
    """Run a client call and turn ``ApiError`` into a clean ``ScriptError``."""
    try:
        return call(*args, **kwargs)
    except ApiError as exc:
        raise ScriptError(str(exc)) from None


__all__ = [
    "api_or_exit",
    "check_guid",
    "default_env",
    "eprint",
    "extract_rows",
    "fetch_pages",
    "fmt",
    "markdown_table",
    "median",
    "num",
    "one_line",
    "parse_when",
    "scrub",
    "scrub_obj",
    "utc_iso",
]
