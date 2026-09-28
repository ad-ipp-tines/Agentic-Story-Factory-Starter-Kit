#!/usr/bin/env bash
# guard-mcp.sh — PreToolUse hook, matcher "mcp__tines__.*" (the Tines Stories MCP server, Mode 2).
#
# Deterministic guard on every authoring call, in this order:
#   0 · audit mirror  — every call is appended to .tines/mcp-activity.jsonl (the tenant records the
#                       same call in its audit logs as "MCP activity"; this is the local copy the
#                       reviewer and stop-gate.sh read)
#   1 · prod refusal  — TINES_ENV=prod blocks all authoring; production changes only through /tines-ship
#   2 · never-touch block — input-based on purpose: /mcp tool names are unpublished (docs/VERIFY.md #1),
#                       so the guard cannot key on them. The call is blocked when its INPUT carries:
#                         a · a protected id — any number, or any string made only of digits, equal to a
#                             production or never-touch story id, a never-touch team id, or the manifest's
#                             prod team_id / folder_id (a create or an edit addressed by team or folder)
#                         b · a never-touch folder name (`folders[]`, for example "90 Seeds")
#                         c · any string matching a never-touch name pattern (`name_patterns[]`, for example
#                             ^\[OPS\]). The ops stories themselves are built in the dev team by their owner
#                             with TINES_ALLOW_OPS_BUILD=1 (dev only; ids, teams and folders stay blocked).
#   3 · destructive-name block — a regex over the tool name. VERIFY against the tenant's real tool
#                       list after /tines-connect, then replace the regex with an explicit deny list.
#
# Fails CLOSED: exit 2 when jq or yq is missing, or when policies/never-touch.yml or
# stories/_manifest.yaml is missing or unreadable — a guard that cannot read its list must not allow.
# Any other error (a failed mkdir or audit append under set -e) is caught by the ERR trap below and also
# exits 2; .claude/settings.json runs this file as `bash … || exit 2`, so a missing or crashing hook blocks too
# (Claude Code treats every exit code other than 2 as a non-blocking error).
#
# Contract: stdin is the hook JSON ({session_id, tool_name, tool_input, ...}); exit 2 blocks the
# call and the stderr text is shown to the model; exit 0 allows it. Exit 2 is used instead of the
# JSON permissionDecision field because the third decision value was reported inconsistently
# (ask vs request) — VERIFY (docs/VERIFY.md #15) before switching.
set -euo pipefail
trap 'echo "guard-mcp: internal error — refused" >&2; exit 2' ERR

block() { echo "guard-mcp: $*" >&2; exit 2; }

command -v jq >/dev/null 2>&1 || block "jq is not installed — the production guard cannot run, so the call is refused (install jq)"
command -v yq >/dev/null 2>&1 || block "yq is not installed — the never-touch list cannot be read, so the call is refused (install yq)"

input=$(cat)
tool=$(jq -r '.tool_name // ""' <<<"$input") || block "unreadable hook input — refused"
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$root"
mkdir -p .tines

# 0 · audit mirror — before any decision, so blocked calls are logged too
jq -c --arg ts "$(date -u +%FT%TZ)" \
  '{ts:$ts, tool:.tool_name, session:.session_id, input:(.tool_input|tostring|.[0:400])}' <<<"$input" \
  >> .tines/mcp-activity.jsonl

# 1 · production is changed only through ship
if [[ "${TINES_ENV:-dev}" == "prod" ]]; then
  block "TINES_ENV=prod — authoring via /mcp is dev-only; use /tines-ship"
fi

# 2 · input-based never-touch block (does not depend on tool names)
never=policies/never-touch.yml
manifest=stories/_manifest.yaml
[[ -r "$never" ]]    || block "$never is missing or unreadable — refused (fail closed)"
[[ -r "$manifest" ]] || block "$manifest is missing or unreadable — refused (fail closed)"

read_yaml() { # $1 = expression, $2 = file; fails closed on a parse error
  yq -r "$1" "$2" 2>/dev/null || block "could not read $1 from $2 with yq — refused (fail closed)"
}

never_story_ids=$(read_yaml '(.story_ids // [])[]' "$never")
never_team_ids=$(read_yaml '(.teams // [])[]' "$never")
never_folders=$(read_yaml '(.folders // [])[]' "$never")
never_patterns=$(read_yaml '(.name_patterns // [])[]' "$never")
prod_story_ids=$(read_yaml '.stories[].prod.story_id' "$manifest")
prod_team_id=$(read_yaml '.environments.prod.team_id' "$manifest")
prod_folder_id=$(read_yaml '.environments.prod.folder_id' "$manifest")

# 0 is the unfilled placeholder everywhere; it is never a protected id (it would match any zero in an input)
protected=$(printf '%s\n' "$never_story_ids" "$prod_story_ids" "$never_team_ids" "$prod_team_id" "$prod_folder_id" \
  | grep -E '^[0-9]+$' | grep -vx '0' | sort -u || true)

# 2a · numbers, and strings made only of digits, anywhere in the input
ids=$(jq -r '[.tool_input | .. | ((numbers | tostring), (strings | select(test("^[0-9]+$"))))] | unique | .[]' <<<"$input" 2>/dev/null) \
  || block "could not read the tool input — refused (fail closed)"
if [[ -n "$protected" ]]; then
  for id in $ids; do
    if grep -qx "$id" <<<"$protected"; then
      block "id $id is write-protected (a production or never-touch story, the prod team or the prod folder); build in the dev team"
    fi
  done
fi

# 2b · never-touch folder names, compared exactly with every string in the input
if [[ -n "$never_folders" ]]; then
  folders_json=$(printf '%s\n' "$never_folders" | jq -R . | jq -s 'map(select(length > 0))')
  hit=$(jq -r --argjson f "$folders_json" \
    'first(.tool_input | .. | strings | select(. as $s | any($f[]; . == $s))) // empty' <<<"$input" 2>/dev/null) \
    || block "could not match folder names — refused (fail closed)"
  [[ -z "$hit" ]] || block "the input names the never-touch folder '$hit' (policies/never-touch.yml folders); never edit or export from it"
fi

# 2c · never-touch name patterns, matched against every string in the input
if [[ -n "$never_patterns" ]]; then
  if [[ "${TINES_ALLOW_OPS_BUILD:-}" == "1" && "${TINES_ENV:-dev}" == "dev" ]]; then
    echo "guard-mcp: TINES_ALLOW_OPS_BUILD=1 — name patterns not enforced for this call (dev team, ops owner); ids, teams and folders still are" >&2
  else
    patterns_json=$(printf '%s\n' "$never_patterns" | jq -R . | jq -s 'map(select(length > 0))')
    hit=$(jq -r --argjson p "$patterns_json" \
      'first(.tool_input | .. | strings | . as $s | $p[] | select(. as $re | $s | test($re)) ) // empty' <<<"$input" 2>/dev/null) \
      || block "could not match name patterns — refused (fail closed)"
    [[ -z "$hit" ]] || block "the input matches the never-touch name pattern '$hit' (policies/never-touch.yml name_patterns); those stories change only through their own change request — their owner builds them in the dev team with TINES_ALLOW_OPS_BUILD=1"
  fi
fi

# 3 · destructive-looking names — VERIFY against the real tool list; replace with an explicit deny list once known
if [[ "$tool" =~ (delete|destroy|remove|purge|batch_delete) ]] && [[ "${TINES_ALLOW_DESTRUCTIVE:-}" != "1" ]]; then
  block "'$tool' looks destructive; re-run with TINES_ALLOW_DESTRUCTIVE=1 after confirming with the story owner"
fi

exit 0
