#!/usr/bin/env bash
# lint-on-write.sh — PostToolUse hook, matcher "Write|Edit".
#
# Gives the model a check it can run, immediately after every write:
#   stories/**/story.json      → ./scripts/lint-story.sh <file>   BLOCKING (exit 2 with the findings)
#   tines-skills/**/SKILL.md   → npx skills-ref validate <dir>    ADVISORY (exit 0 + additionalContext)
#
# Contract: stdin is the hook JSON; tool_input.file_path is the written file. On exit 0 the JSON
# printed to stdout may carry hookSpecificOutput.additionalContext, which the model sees in the
# same turn. On exit 2 stderr is shown to the model and the turn is blocked until it is fixed.
set -euo pipefail

input=$(cat)
file=$(jq -r '.tool_input.file_path // ""' <<<"$input")
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$root"
[[ -z "$file" ]] && exit 0
rel="${file#"$root"/}"

advise() { # exit 0 with additionalContext so the model fixes it in the same turn
  jq -n --arg ctx "$1" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$ctx}}'
  exit 0
}

case "$rel" in
  stories/*/story.json)
    if [[ ! -x scripts/lint-story.sh ]]; then
      advise "lint-on-write: scripts/lint-story.sh is missing or not executable, so the lint gate was skipped for $rel. Do not commit until lint runs."
    fi
    if ! out=$(./scripts/lint-story.sh "$rel" 2>&1); then
      echo "lint-on-write: $rel fails lint. Fix it through /tines-build-story and re-export with /tines-export — never hand-edit the export." >&2
      echo "$out" >&2
      exit 2
    fi
    ;;
  tines-skills/*/SKILL.md)
    dir=$(dirname "$rel")
    if command -v npx >/dev/null 2>&1; then
      # VERIFY: package name and CLI of the Agent Skills validator (docs/VERIFY.md #21). --no = never install from the network inside a hook.
      if ! out=$(npx --no skills-ref validate "$dir" 2>&1); then
        advise "$(printf 'lint-on-write (advisory): skills-ref validate reported problems in %s — fix them in this turn, or install the validator if it is missing:\n%s' "$dir" "$out")"
      fi
    else
      advise "lint-on-write (advisory): npx is not available; skills-ref validate was skipped for $dir. Check the frontmatter by hand against .claude/rules/tines-skills.md."
    fi
    ;;
esac

exit 0
