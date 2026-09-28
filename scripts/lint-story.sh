#!/usr/bin/env bash
# Thin shim so DESIGN.md's paths keep working: the hooks (.claude/hooks/lint-on-write.sh,
# stop-gate.sh), the skills and .claude/settings.json all call ./scripts/lint-story.sh.
# The implementation is scripts/lint_story.py (Python 3, standard library; PyYAML optional).
#
# One check lives here because it belongs to scripts/normalize.jq, the single definition of what
# normalisation removes: every export named on the command line is re-run through normalize.jq and
# compared, key-order-insensitively, with itself minus `exported_at` (lint_story.py already reports
# that key as `not_normalised`). Today normalize.jq drops `exported_at` and replaces every action's
# ingress `path`/`secret` with <assigned-on-import>, so a committed export that still carries a live
# ingress identifier fails here as `not_normalised` (and in lint_story.py as `webhook_secret_in_export`);
# the day a volatile key is added to normalize.jq (docs/VERIFY.md #8), every committed export that
# still carries it fails here with the same rule name, without a Python change.
# Skipped when jq is missing, and for --format json (whose stdout must stay one JSON document).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
py="${PYTHON:-python3}"
filter="$here/normalize.jq"

format=text
paths=()
args=("$@")
i=0
while [ "$i" -lt "${#args[@]}" ]; do
  a="${args[$i]}"
  case "$a" in
    --format)                         format="${args[$((i + 1))]:-text}"; i=$((i + 2)); continue ;;
    --format=*)                       format="${a#--format=}" ;;
    --meta|--rules|--cost-ceilings)   i=$((i + 2)); continue ;;
    --*)                              ;;
    *)                                paths+=("$a") ;;
  esac
  i=$((i + 1))
done

norm_fail=0
if [ "$format" != "json" ] && [ -f "$filter" ] && command -v jq >/dev/null 2>&1 && [ "${#paths[@]}" -gt 0 ]; then
  files=()
  for p in "${paths[@]}"; do
    if [ -d "$p" ]; then
      for f in "$p"/*/story.json; do
        [ -f "$f" ] || continue
        case "$f" in *_template/*) continue ;; esac
        files+=("$f")
      done
    elif [ -f "$p" ]; then
      files+=("$p")
    fi
  done
  for f in ${files[@]+"${files[@]}"}; do
    # Both sides must parse; a broken export or a non-export is lint_story.py's finding, not this one.
    want=$(jq -S -f "$filter" "$f" 2>/dev/null) || continue
    have=$(jq -S 'del(.exported_at)' "$f" 2>/dev/null) || continue
    if [ "$want" != "$have" ]; then
      extra=$(comm -23 <(jq -r 'del(.exported_at) | keys[]' "$f" | sort) <(jq -r 'keys[]' <<<"$want" | sort) | paste -sd, - || true)
      slug=$(basename "$(dirname "$f")")
      msg="normalize.jq removes [${extra:-nested changes}] from this export — re-run ./scripts/tines export ${slug} (never hand-edit story.json)"
      if [ "$format" = "github" ]; then
        echo "::error file=${f},title=not_normalised::${msg}"
      else
        echo "${f}: not_normalised: error: ${msg}"
      fi
      norm_fail=1
    fi
  done
fi

rc=0
"$py" "$here/lint_story.py" "$@" || rc=$?
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
exit "$norm_fail"
