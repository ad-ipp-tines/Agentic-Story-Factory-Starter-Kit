#!/usr/bin/env bash
# stop-gate.sh — Stop hook (no matcher). The turn cannot end while either holds:
#   (a) a changed stories/<slug>/story.json fails ./scripts/lint-story.sh
#   (b) a story touched through /mcp in THIS session has no export newer than the last MCP call
#       (story.meta.yaml: exported_from.at  <  the last matching row's ts in .tines/mcp-activity.jsonl)
#
# Contract: stdin is the hook JSON ({session_id, stop_hook_active, ...}); exit 2 blocks the stop and
# the stderr text is shown to the model, so the message lists exactly what to run. Claude Code lifts
# the block after 8 consecutive refusals (VERIFY), which is why the message is precise rather than loud.
# Timestamps on both sides are UTC ISO 8601 (%FT%TZ), so a plain string comparison is correct.
set -euo pipefail

input=$(cat)
session=$(jq -r '.session_id // ""' <<<"$input")
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$root"
problems=()

# (a) lint every changed export
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if [[ -x scripts/lint-story.sh ]] && ! ./scripts/lint-story.sh "$f" >/dev/null 2>&1; then
      slug=$(basename "$(dirname "$f")")
      problems+=("$f fails lint — fix through /tines-build-story $slug, then /tines-export $slug")
    fi
  done < <(git status --porcelain -- stories/ 2>/dev/null | awk '{print $NF}' | grep -E '^stories/[^/]+/story\.json$' || true)
fi

# (b) stale export after MCP activity in this session
log=.tines/mcp-activity.jsonl
if [[ -f "$log" && -f stories/_manifest.yaml && -n "$session" ]] && command -v yq >/dev/null 2>&1; then
  while IFS=$'\t' read -r slug sid; do
    [[ -z "$slug" || -z "$sid" || "$sid" == "0" || "$sid" == "null" ]] && continue
    last=$(jq -r --arg s "$session" --arg id "$sid" \
      'select(.session==$s) | select(.input | test("(^|[^0-9])"+$id+"([^0-9]|$)")) | .ts' "$log" 2>/dev/null | sort | tail -n1)
    [[ -z "$last" ]] && continue
    meta="stories/$slug/story.meta.yaml"
    at=""
    if [[ -f "$meta" ]]; then at=$(yq '.exported_from.at // ""' "$meta" 2>/dev/null || echo ""); fi
    if [[ -z "$at" || "$at" == "null" || "$at" < "$last" ]]; then
      problems+=("stories/$slug changed through /mcp at $last but exported_from.at is '${at:-unset}' — run /tines-export $slug")
    fi
  done < <(yq '.stories | to_entries[] | [.key, (.value.dev.story_id // 0)] | @tsv' stories/_manifest.yaml 2>/dev/null || true)
fi

if (( ${#problems[@]} > 0 )); then
  echo "stop-gate: the turn cannot end yet. Fix exactly these:" >&2
  printf ' - %s\n' "${problems[@]}" >&2
  exit 2
fi

exit 0
