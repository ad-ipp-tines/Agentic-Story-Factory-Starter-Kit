#!/usr/bin/env python3
"""Shared helpers for the tines-stories-as-code scripts.

Every script in this directory imports this module for four things:

1. **The API client** (`TinesClient`) — one audited code path for every call the
   repository makes against the Tines API. Base URL is
   ``https://<TINES_TENANT>.tines.com``; authentication is the
   ``Authorization: Bearer <TINES_API_KEY>`` header with a **team-scoped** key
   (see DESIGN.md §3.1 and §7.3). The client retries on 429 with backoff, never
   prints the key, and turns a non-2xx response into ``ApiError`` with the
   body's error text. A 404 on a write is named for what it usually is: an
   underprivileged key.

2. **Environment resolution** — ``stories/_manifest.yaml`` maps an environment
   (``dev``, ``prod``, optionally ``staging``) to a team, a folder and a list of
   monitoring recipients, and a story slug to its story id per environment.
   Explicit CLI arguments beat environment variables (``TINES_TEAM_ID``,
   ``TINES_FOLDER_ID``), which beat the manifest. Production is refused unless
   ``TINES_ALLOW_PROD=1`` (CI sets it; the editor never does).

3. **Export normalisation** — ``normalize_export`` (the mirror of
   ``scripts/normalize.jq``) drops ``exported_at``, replaces every action's
   ingress identifiers (``options.path`` / ``options.secret``) with
   ``<assigned-on-import>``, and the caller writes the JSON with sorted keys. Agent order is preserved on purpose:
   ``links`` reference agents by index (confirmed on real exports, schema 28/30).

4. **Secret patterns** — the single list ``SECRET_PATTERNS`` that
   ``lint_story.py`` enforces on exports and that ``.claude/hooks/block-secrets.sh``
   and ``lint.yml`` mirror.

Dependencies: Python 3 standard library plus ``requests``. ``PyYAML`` is
optional and only needed to read ``stories/_manifest.yaml``,
``stories/<slug>/story.meta.yaml`` and ``policies/*.yml``; every script says so
clearly when it is missing and, where it can, keeps working with explicit ids.

Conventions (DESIGN.md §9): placeholders such as ``<your-tenant>`` are never
real values; anything not confirmed on a Tines page or a real export is marked
``VERIFY`` in a comment; no secrets, ever — credentials are referenced by name.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

try:  # requests is the one third-party dependency the scripts need
    import requests  # type: ignore
except ImportError:  # pragma: no cover - reported at call time
    requests = None  # type: ignore

try:  # PyYAML is optional: manifest, meta and policy files only
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

MANIFEST_RELATIVE = Path("stories") / "_manifest.yaml"
STORIES_DIR = "stories"
SKILLS_DIR = "tines-skills"
POLICIES_DIR = "policies"

# Tenant host prefix only: the scripts build https://<tenant>.tines.com from it.
TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

# Rate limits stated in DESIGN.md §6.6: 5,000 req/min default, actions 100/min,
# audit_logs 1,000/min, records 400/min. The client backs off on 429 and sleeps
# briefly between write calls in the workflows (``sleep 1`` between stories).
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 5

# Secret-looking strings that must never appear in a committed export.
# Mirrors DESIGN.md §3.3 ``block-secrets.sh`` and §7.2. The negative look-ahead
# on the Bearer pattern lets ``Bearer <<CREDENTIAL.x>>`` and ``Bearer <api-key>``
# placeholders through: those are references, not values.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("x-user-token-header", re.compile(r"X-User-Token", re.IGNORECASE)),
    ("bearer-literal", re.compile(r"Bearer\s+(?![<{=$])[A-Za-z0-9._\-]{16,}")),
    ("basic-auth-literal", re.compile(r"Basic\s+(?![<{=$])[A-Za-z0-9+/=]{20,}")),
    ("slack-token", re.compile(r"\bxox[abps]-[A-Za-z0-9\-]{10,}")),
    ("slack-app-token", re.compile(r"\bxapp-[A-Za-z0-9\-]{10,}")),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("sk-style-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github-fine-grained-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "api-key-assignment",
        re.compile(r"api[_\-]?key\s*[=:]\s*[\"'](?![<{=$])[^\"']{8,}[\"']", re.IGNORECASE),
    ),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Documentation-only domains that are allowed in committed files (DESIGN.md §9.1).
PLACEHOLDER_EMAIL_SUFFIXES = (".invalid", "@example.com", "@example.org", "@example.net")

# Formula reference forms confirmed on real exports: ``<<CREDENTIAL.name>>`` and
# ``=... CREDENTIAL.name ...``; resources as ``RESOURCE.name`` or ``RESOURCE[expr]``.
CREDENTIAL_REF_RE = re.compile(r"\bCREDENTIAL\.([A-Za-z0-9_]+)")
RESOURCE_REF_RE = re.compile(r"\bRESOURCE\.([A-Za-z0-9_]+)")
RESOURCE_DYNAMIC_RE = re.compile(r"\bRESOURCE\[")
STORY_REF_RE = re.compile(r"\bSTORY\.([A-Za-z0-9_]+)")


# --------------------------------------------------------------------------- #
# Errors and small utilities
# --------------------------------------------------------------------------- #


class ScriptError(SystemExit):
    """Exit with a message on stderr and a non-zero status (default 1)."""

    def __init__(self, message: str, code: int = 1) -> None:
        print(f"error: {message}", file=sys.stderr)
        super().__init__(code)


class NeedsYaml(ScriptError):
    """Raised when a YAML file must be read but PyYAML is not installed."""

    def __init__(self, path: Path | str) -> None:
        super().__init__(
            f"reading {path} needs PyYAML (pip install pyyaml) — or pass the ids "
            "explicitly with --story-id / --team-id / --folder-id"
        )


def eprint(*args: Any, **kwargs: Any) -> None:
    """Print to stderr (all human-facing progress goes there; stdout is data)."""
    print(*args, file=sys.stderr, **kwargs)


def env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Read an environment variable; never echo its value in an error."""
    value = os.environ.get(name, default)
    if required and not value:
        raise ScriptError(f"environment variable {name} is required (source .env first)")
    return value


def utc_now() -> str:
    """Current time as an ISO-8601 UTC string with second precision."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def git_sha(short: bool = True) -> Optional[str]:
    """Return the current commit SHA (short by default), or None outside git."""
    args = ["git", "rev-parse", "--short=7" if short else "--verify", "HEAD"]
    try:
        out = subprocess.run(args, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def expand_env_refs(value: str) -> str:
    """Expand ``${VAR}`` references from the environment.

    Used for manifest recipients such as ``${OPS_ROUTER_URL}`` — the router
    webhook URL carries a secret, so it lives in the environment, never in the
    manifest (DESIGN.md §7.2). A missing variable is an error that names the
    variable, never its value.
    """

    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        val = os.environ.get(name)
        if val is None or val == "":
            raise ScriptError(f"manifest references ${{{name}}} but it is not set")
        return val

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", _sub, value)


def redact(text: str, keep: int = 4) -> str:
    """Return a length-preserving redaction for log lines (``abcd…(32 chars)``)."""
    if len(text) <= keep:
        return "…"
    return f"{text[:keep]}…({len(text)} chars)"


# --------------------------------------------------------------------------- #
# Repository layout
# --------------------------------------------------------------------------- #


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Walk upwards from ``start`` (default: cwd) until ``stories/_manifest.yaml``.

    Falls back to the directory that contains this ``scripts/`` folder, so the
    scripts also work when invoked from anywhere inside the repository.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / MANIFEST_RELATIVE).exists():
            return candidate
    scripts_parent = Path(__file__).resolve().parent.parent
    if (scripts_parent / MANIFEST_RELATIVE).exists():
        return scripts_parent
    return scripts_parent


def story_dir(root: Path, slug: str) -> Path:
    """``<root>/stories/<slug>`` — the folder that holds story.json and story.meta.yaml."""
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        raise ScriptError(f"slug {slug!r} must be lowercase letters, digits and hyphens")
    return root / STORIES_DIR / slug


def load_yaml_file(path: Path) -> Any:
    """Load a YAML file with PyYAML, or raise ``NeedsYaml``."""
    if yaml is None:
        raise NeedsYaml(path)
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_json_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Manifest resolution
# --------------------------------------------------------------------------- #


@dataclass
class StoryTarget:
    """Everything a script needs to know about one story in one environment."""

    slug: str
    env: str
    story_id: int
    team_id: int
    folder_id: Optional[int]
    tier: str = "production"
    new: bool = False
    recipients: list[str] = field(default_factory=list)
    locked: bool = False
    name: Optional[str] = None  # from story.meta.yaml when available


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_RELATIVE
    if not path.exists():
        raise ScriptError(f"manifest not found at {path}")
    data = load_yaml_file(path)
    if not isinstance(data, dict) or "environments" not in data:
        raise ScriptError(f"{path} must contain an 'environments' map (see DESIGN.md §3.6)")
    return data


def _as_int(value: Any, what: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ScriptError(f"{what} must be an integer, got {value!r}") from None


def resolve_target(
    root: Path,
    slug: str,
    env_name: str,
    *,
    story_id: Optional[int] = None,
    team_id: Optional[int] = None,
    folder_id: Optional[int] = None,
    manifest: Optional[dict[str, Any]] = None,
    expand_recipients: bool = True,
) -> StoryTarget:
    """Resolve ids for ``slug`` in ``env_name``.

    Precedence: explicit arguments > ``TINES_TEAM_ID`` / ``TINES_FOLDER_ID`` /
    ``TINES_STORY_ID`` environment variables > manifest. A manifest value of
    ``0`` is the committed placeholder (DESIGN.md §9.1) and counts as unset.
    """
    manifest = manifest or load_manifest(root)
    envs = manifest.get("environments") or {}
    if env_name not in envs:
        raise ScriptError(f"environment {env_name!r} is not defined in stories/_manifest.yaml")
    env_cfg = envs[env_name] or {}
    stories = manifest.get("stories") or {}
    entry = stories.get(slug)
    if entry is None:
        raise ScriptError(f"slug {slug!r} is not in stories/_manifest.yaml (add it, new: true if unshipped)")
    per_env = entry.get(env_name) or {}

    def pick(explicit: Optional[int], var: str, manifest_value: Any) -> Optional[int]:
        if explicit is not None:
            return explicit
        from_env = os.environ.get(var)
        if from_env:
            return _as_int(from_env, var)
        if manifest_value in (None, 0, "0", ""):
            return None
        return _as_int(manifest_value, f"{slug}.{env_name}")

    resolved_team = pick(team_id, "TINES_TEAM_ID", env_cfg.get("team_id"))
    resolved_folder = pick(folder_id, "TINES_FOLDER_ID", env_cfg.get("folder_id"))
    resolved_story = pick(story_id, "TINES_STORY_ID", per_env.get("story_id"))
    is_new = bool(entry.get("new", False))

    if resolved_team is None:
        raise ScriptError(
            f"no team id for environment {env_name!r}: set it in the manifest, "
            "TINES_TEAM_ID, or --team-id"
        )
    if resolved_story is None and not is_new:
        raise ScriptError(
            f"no story id for {slug!r} in {env_name!r} and the slug is not marked new: true "
            "(commit the id after the first import, or pass --story-id)"
        )

    recipients: list[str] = []
    for raw in env_cfg.get("recipients") or []:
        recipients.append(expand_env_refs(str(raw)) if expand_recipients else str(raw))

    locked = slug in (env_cfg.get("locked_slugs") or [])
    return StoryTarget(
        slug=slug,
        env=env_name,
        story_id=resolved_story or 0,
        team_id=resolved_team,
        folder_id=resolved_folder,
        tier=str(entry.get("tier", "production")),
        new=is_new,
        recipients=recipients,
        locked=locked,
    )


def load_story_meta(root: Path, slug: str) -> Optional[dict[str, Any]]:
    """Return ``stories/<slug>/story.meta.yaml`` as a dict, or None if absent."""
    path = story_dir(root, slug) / "story.meta.yaml"
    if not path.exists():
        return None
    data = load_yaml_file(path)
    return data if isinstance(data, dict) else {}


def stamp_exported_from(
    meta_path: Path,
    *,
    env_name: str,
    story_id: int,
    draft_id: str,
    at: str,
    sha: str,
) -> None:
    """Rewrite the ``exported_from:`` line of story.meta.yaml in place.

    Text-level replacement on purpose: it keeps the operator's comments and
    ordering intact and needs no YAML writer. The line is written in flow style,
    exactly as the template in DESIGN.md §3.6 shows it.
    """
    line = (
        "exported_from: { env: %s, story_id: %d, draft_id: %s, at: %s, sha: %s }"
        % (env_name, story_id, json.dumps(draft_id), json.dumps(at), json.dumps(sha))
    )
    if meta_path.exists():
        text = meta_path.read_text(encoding="utf-8")
        pattern = re.compile(r"^exported_from:.*(?:\n(?:[ \t]+.*|\s*$))*", re.MULTILINE)
        if pattern.search(text):
            text = pattern.sub(line, text, count=1)
        else:
            text = text.rstrip("\n") + "\n" + line + "\n"
    else:
        text = line + "\n"
    meta_path.write_text(text, encoding="utf-8")


def guard_prod(env_name: str) -> None:
    """Refuse production outside CI unless TINES_ALLOW_PROD=1 (DESIGN.md §3.1)."""
    if env_name == "prod" and os.environ.get("TINES_ALLOW_PROD") != "1":
        raise ScriptError(
            "environment 'prod' is refused unless TINES_ALLOW_PROD=1 — production is "
            "changed only by the deploy workflow through a draft and a change request"
        )


# --------------------------------------------------------------------------- #
# Export helpers
# --------------------------------------------------------------------------- #


INGRESS_KEYS = ("path", "secret")
INGRESS_PLACEHOLDER = "<assigned-on-import>"


def _ingress_value_to_replace(key: str, value: Any) -> bool:
    """Mirror of scripts/normalize.jq ``redact_ingress``: a real ingress identifier, not a formula or placeholder."""
    if not isinstance(value, str) or value == "":
        return False
    if key == "path" and ("<<" in value or value.lstrip().startswith("=")):
        return False  # an Event Transform explode path is a formula, not an ingress id
    text = value.strip()
    if text.startswith("<") and not text.startswith("<<") and text.endswith(">"):
        return False  # already a placeholder
    return True


def normalize_export(data: dict[str, Any]) -> dict[str, Any]:
    """Make an export diff-stable and safe to commit without changing its meaning.

    The Python mirror of ``scripts/normalize.jq`` (used when jq is not on PATH):
    drops ``exported_at`` (a timestamp that changes on every export) and replaces
    the ingress identifiers ``options.path`` / ``options.secret`` on EVERY action
    that carries them — by key name, never by action type — with
    ``<assigned-on-import>``, so a Webhook or MCP server action's live URL
    components are never committed. Keeps ``guid`` and ``diagram_layout``; keeps
    agent order because ``links`` refer to agents by index. Keys are sorted by
    ``dump_json`` at write time.
    """
    out = dict(data)
    out.pop("exported_at", None)
    agents = out.get("agents")
    if isinstance(agents, list):
        cleaned = []
        for agent in agents:
            if isinstance(agent, dict) and isinstance(agent.get("options"), dict):
                options = dict(agent["options"])
                for key in INGRESS_KEYS:
                    if _ingress_value_to_replace(key, options.get(key)):
                        options[key] = INGRESS_PLACEHOLDER
                agent = {**agent, "options": options}
            cleaned.append(agent)
        out["agents"] = cleaned
    return out


def dump_json(data: Any) -> str:
    """Canonical JSON text: two-space indent, sorted keys, trailing newline."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def walk_strings(obj: Any, path: str = "$") -> Iterator[tuple[str, str]]:
    """Yield ``(json_path, value)`` for every string inside a JSON structure."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield from walk_strings(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from walk_strings(value, f"{path}[{index}]")


def looks_like_secret(text: str) -> Optional[str]:
    """Return the name of the first secret pattern that matches, else None."""
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return name
    return None


def is_placeholder_email(address: str) -> bool:
    lowered = address.lower()
    return any(lowered.endswith(suffix) for suffix in PLACEHOLDER_EMAIL_SUFFIXES)


# --------------------------------------------------------------------------- #
# The API client
# --------------------------------------------------------------------------- #


class ApiError(RuntimeError):
    """A non-2xx response from the Tines API, with the body's error text."""

    def __init__(self, status: int, method: str, path: str, message: str) -> None:
        self.status = status
        self.method = method
        self.path = path
        super().__init__(f"{method} {path} -> HTTP {status}: {message}")


class TinesClient:
    """Minimal client over the Tines REST API used by this repository.

    Only the endpoints listed in DESIGN.md §3.5 / §4 / §5 are called by the
    scripts; this class does not know or invent any others.
    """

    def __init__(
        self,
        tenant: str,
        api_key: str,
        *,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        dry_run: bool = False,
    ) -> None:
        if requests is None:
            raise ScriptError("the 'requests' package is required (pip install requests)")
        if not TENANT_RE.match(tenant or ""):
            raise ScriptError(
                "TINES_TENANT must be the host prefix only (e.g. <your-tenant>), "
                "not a full hostname or URL"
            )
        if not api_key:
            raise ScriptError("TINES_API_KEY is required (a TEAM-scoped key; never a personal key)")
        self.tenant = tenant
        self._api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "tines-stories-as-code/1.0 (+scripts)",
            }
        )

    @property
    def base_url(self) -> str:
        # TINES_BASE_URL exists for tests against a LOCAL mock server only. The Authorization header carries
        # TINES_API_KEY, so the override is accepted only for http://localhost or http://127.0.0.1 and is
        # refused outright in CI (GITHUB_ACTIONS=true) — a stray or planted value can never send a key elsewhere.
        override = os.environ.get("TINES_BASE_URL")
        if override:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                raise ScriptError("TINES_BASE_URL is refused in CI; the scripts talk only to https://<tenant>.tines.com")
            if not re.match(r"^http://(localhost|127\.0\.0\.1)(:[0-9]{1,5})?(/.*)?$", override):
                raise ScriptError("TINES_BASE_URL may only point at http://localhost or http://127.0.0.1 (a local mock server)")
            return override.rstrip("/")
        return f"https://{self.tenant}.tines.com"

    def __repr__(self) -> str:  # never leak the key
        return f"TinesClient(tenant={self.tenant!r}, key={redact(self._api_key)})"

    # -- core --------------------------------------------------------------- #

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> tuple[int, Any]:
        """Perform one call; returns ``(status, parsed_json_or_text)``.

        In ``dry_run`` mode, write calls (POST/PUT/DELETE) are printed and
        skipped; read calls still go out so a dry run can show what exists.
        """
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        is_write = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        if self.dry_run and is_write:
            eprint(f"[dry-run] {method.upper()} {path} params={params or {}} body={_summarise_body(json_body)}")
            return 0, {"dry_run": True}

        delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.request(
                    method.upper(), url, params=params, json=json_body, timeout=self.timeout
                )
            except requests.RequestException as exc:  # network-level failure
                if attempt == self.max_retries:
                    raise ApiError(0, method.upper(), path, f"network error: {exc.__class__.__name__}")
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue

            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                if attempt == self.max_retries:
                    raise ApiError(resp.status_code, method.upper(), path, _error_text(resp))
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                eprint(f"[retry] {method.upper()} {path} -> {resp.status_code}; waiting {wait:.0f}s")
                time.sleep(wait)
                delay = min(delay * 2, 30)
                continue

            if 200 <= resp.status_code < 300:
                if not resp.content:
                    return resp.status_code, {}
                try:
                    return resp.status_code, resp.json()
                except ValueError:
                    return resp.status_code, resp.text

            message = _error_text(resp)
            if resp.status_code == 404 and is_write:
                message += " (a 404 on a write usually means the API key lacks the permission or team)"
            if resp.status_code in (401, 403):
                message += " (check the key is team-scoped for this team and not expired)"
            raise ApiError(resp.status_code, method.upper(), path, message)
        raise ApiError(0, method.upper(), path, "exhausted retries")  # pragma: no cover

    # -- verbs -------------------------------------------------------------- #

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params={k: v for k, v in params.items() if v is not None})[1]

    def post(self, path: str, body: Optional[dict[str, Any]] = None, **params: Any) -> Any:
        return self.request("POST", path, params=params or None, json_body=body)[1]

    def put(self, path: str, body: Optional[dict[str, Any]] = None, **params: Any) -> Any:
        return self.request("PUT", path, params=params or None, json_body=body)[1]

    def delete(self, path: str, body: Optional[dict[str, Any]] = None, **params: Any) -> Any:
        return self.request("DELETE", path, params=params or None, json_body=body)[1]


def _error_text(resp: Any) -> str:
    """Best-effort error text from a response body, bounded in length."""
    try:
        data = resp.json()
        if isinstance(data, dict):
            for key in ("error", "errors", "message", "detail"):
                if key in data:
                    return str(data[key])[:500]
        return json.dumps(data)[:500]
    except ValueError:
        return (resp.text or "")[:500]


def _summarise_body(body: Optional[dict[str, Any]]) -> str:
    """Describe a request body for dry-run output without dumping large blobs."""
    if not body:
        return "{}"
    shown: dict[str, Any] = {}
    for key, value in body.items():
        if key == "data" and isinstance(value, str):
            shown[key] = f"<story export, {len(value)} chars>"
        elif key == "data" and isinstance(value, dict):
            agents = value.get("agents") if isinstance(value.get("agents"), list) else []
            shown[key] = f"<story export {value.get('name')!r}, {len(agents)} action(s)>"
        elif key == "body" and isinstance(value, str):
            shown[key] = f"<skill body, {len(value)} chars>"
        elif key == "description" and isinstance(value, str) and len(value) > 160:
            shown[key] = value[:157] + "…"
        elif isinstance(value, str) and looks_like_secret(value):
            shown[key] = redact(value)
        elif isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False)
            shown[key] = value if len(text) <= 300 else f"<{type(value).__name__}, {len(text)} chars>"
        else:
            shown[key] = value
    return json.dumps(shown, ensure_ascii=False)


def client_from_env(dry_run: bool = False) -> TinesClient:
    """Build a client from ``TINES_TENANT`` and ``TINES_API_KEY``."""
    tenant = env("TINES_TENANT", required=True) or ""
    key = env("TINES_API_KEY", required=True) or ""
    return TinesClient(tenant, key, dry_run=dry_run)


# --------------------------------------------------------------------------- #
# Frontmatter (for tines-skills/**/SKILL.md)
# --------------------------------------------------------------------------- #


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split a SKILL.md into ``(frontmatter_yaml, body)``; frontmatter may be empty."""
    if not text.startswith("---"):
        return "", text
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        return "", text
    front = parts[0][3:].lstrip("\n")
    body = parts[1]
    if body.startswith("\n"):
        body = body[1:]
    return front, body


def parse_frontmatter(front: str) -> dict[str, Any]:
    """Parse frontmatter YAML.

    Uses PyYAML when available. Otherwise a deliberately small parser handles
    the shapes the Agent Skills spec and DESIGN.md §3.7 use: flat ``key: value``
    scalars, one level of indented nested map (``metadata:``), and flow maps
    ``{ owner: ops, version: "1" }``. Anything else raises so the author
    installs PyYAML rather than trusting a guess.
    """
    if yaml is not None:
        data = yaml.safe_load(front) or {}
        if not isinstance(data, dict):
            raise ScriptError("frontmatter must be a mapping")
        return data

    result: dict[str, Any] = {}
    current_key: Optional[str] = None
    for raw in front.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if ":" not in line:
            raise ScriptError(f"cannot parse frontmatter line without PyYAML: {line!r}")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if indent == 0:
            current_key = key
            if value == "":
                result[key] = {}
            else:
                result[key] = _parse_scalar_or_flow(value)
        else:
            if current_key is None or not isinstance(result.get(current_key), dict):
                raise ScriptError(f"unexpected nested frontmatter line: {line!r}")
            result[current_key][key] = _parse_scalar_or_flow(value)
    return result


def _parse_scalar_or_flow(value: str) -> Any:
    value = value.strip()
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        out: dict[str, Any] = {}
        if inner:
            for item in _split_top_level(inner):
                k, _, v = item.partition(":")
                out[k.strip()] = _parse_scalar_or_flow(v)
        return out
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [_parse_scalar_or_flow(x) for x in _split_top_level(inner)] if inner else []
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if re.match(r"^-?\d+$", value):
        return int(value)
    return value


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside quotes or nested brackets."""
    items, depth, quote, current = [], 0, "", []
    for ch in text:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        items.append("".join(current).strip())
    return items


__all__ = [
    "ApiError",
    "CREDENTIAL_REF_RE",
    "EMAIL_RE",
    "INGRESS_KEYS",
    "INGRESS_PLACEHOLDER",
    "NeedsYaml",
    "RESOURCE_DYNAMIC_RE",
    "RESOURCE_REF_RE",
    "SECRET_PATTERNS",
    "STORY_REF_RE",
    "ScriptError",
    "StoryTarget",
    "TinesClient",
    "client_from_env",
    "dump_json",
    "env",
    "eprint",
    "expand_env_refs",
    "find_repo_root",
    "git_sha",
    "guard_prod",
    "is_placeholder_email",
    "load_json_file",
    "load_manifest",
    "load_story_meta",
    "load_yaml_file",
    "looks_like_secret",
    "normalize_export",
    "parse_frontmatter",
    "redact",
    "resolve_target",
    "split_frontmatter",
    "stamp_exported_from",
    "story_dir",
    "utc_now",
    "walk_strings",
]
