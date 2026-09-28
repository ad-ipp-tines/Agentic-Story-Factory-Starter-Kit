#!/usr/bin/env bash
# block-secrets.sh — PreToolUse hook, matchers "Write|Edit|MultiEdit|NotebookEdit|Bash" and "mcp__tines__.*".
#
# Refuses any write whose content looks like a secret. Credentials live in Tines and are referenced
# by name; the router webhook URL and API keys live in .env (gitignored) or GitHub environment
# secrets. This hook is a backstop, not the rule — the rule is "no secrets, ever" in AGENTS.md.
#
# Contract: stdin is the hook JSON. The text inspected is every write-carrying field the editor's
# tools use: tool_input.content (Write), tool_input.new_string (Edit), tool_input.edits[].new_string
# (batched edits), tool_input.new_source (notebook edits) and tool_input.command (Bash — a file
# written through the shell, a commit message). For a Tines Stories MCP call (tool_name mcp__…) it is
# EVERY string anywhere in tool_input, values and keys — an action's options, a formula, a story description — because the
# /mcp tool names and input shapes are unpublished (docs/VERIFY.md #1); that text becomes story content,
# so it is judged as a story export is (the X-User-Token header name counts). On that matcher
# .claude/settings.json runs this file as `bash … || exit 2`, so a crash blocks the call.
# exit 2 blocks the call and shows stderr to the model.
#
# The patterns are GENERATED from scripts/tines_common.py SECRET_PATTERNS (the single list
# lint_story.py and lint.yml use) by a small Python helper, so this hook cannot drift from CI. The
# bash checks below the helper are the fallback when python3 or the module is unavailable.
#
# Patterns are deliberately value-shaped (a header NAME or a documented placeholder such as
# <api-key> never matches) so documentation and this file itself can be written. As in lint.yml, the
# bare `X-User-Token` header-name pattern is only a finding inside stories/ and tines-skills/.
set -euo pipefail

input=$(cat)
tool=$(jq -r '.tool_name // ""' <<<"$input")
scoped=0
if [[ "$tool" == mcp__* ]]; then
  # every string in the MCP tool input, at any depth — values and object keys (a header name such as X-User-Token can
  # arrive as a key of an action's headers map)
  content=$(jq -r '[.tool_input | .. | (strings, (objects | keys[]))] | join("\n")' <<<"$input")
  file="<the input of $tool>"
  scoped=1
else
  content=$(jq -r '[.tool_input.content, .tool_input.new_string, (.tool_input.edits // [] | .[]? | .new_string),
                    .tool_input.new_source, .tool_input.command] | map(select(type == "string")) | join("\n")' <<<"$input")
  file=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // (if .tool_input.command then "<shell command>" else "<unknown file>" end)' <<<"$input")
fi
[[ -z "$content" ]] && exit 0

refuse() { # $1 = pattern name
  echo "block-secrets: refusing to write $file — content matches the secret pattern '$1'." >&2
  echo "Reference credentials by name; keep values in Tines, in .env (gitignored) or in GitHub environment secrets. If this is a false positive, rephrase the text so it does not look like a live value." >&2
  exit 2
}

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# 1 · the canonical list (scripts/tines_common.py SECRET_PATTERNS), generated — not copied
if command -v python3 >/dev/null 2>&1 && [[ -f "$root/scripts/tines_common.py" ]]; then
  set +e
  hit=$(BS_CONTENT="$content" BS_FILE="$file" BS_SCOPED="$scoped" python3 - "$root/scripts" <<'PY'
import os, sys
sys.path.insert(0, sys.argv[1])
try:
    from tines_common import SECRET_PATTERNS
except Exception:            # module unreadable → let the bash fallback run
    sys.exit(3)
text, path = os.environ.get("BS_CONTENT", ""), os.environ.get("BS_FILE", "")
scoped = (os.environ.get("BS_SCOPED") == "1" or path.startswith(("stories/", "tines-skills/"))
          or "/stories/" in path or "/tines-skills/" in path)
for name, pattern in SECRET_PATTERNS:
    if name == "x-user-token-header" and not scoped:
        continue  # a header NAME is only a finding inside an export or a skill body (same rule as lint.yml)
    if pattern.search(text):
        print(name)
        sys.exit(2)
sys.exit(0)
PY
)
  rc=$?
  set -e
  if [[ $rc -eq 2 ]]; then refuse "$hit"; fi
fi

# 2 · fallback and extras (value-shaped; also run when the helper passed)
q="[\"']"   # a single or double quote
check() { # $1 = pattern name, $2 = extended regex
  if grep -Eq -- "$2" <<<"$content"; then refuse "$1"; fi
}
check 'X-User-Token header with a value'   "X-User-Token[[:space:]]*[:=][[:space:]]*${q}?[A-Za-z0-9._-]{16,}"
check 'Bearer token'                        'Bearer [A-Za-z0-9._-]{16,}'
check 'Slack token'                         'xox[abps]-[A-Za-z0-9-]{10,}'
check 'Slack app-level token'               'xapp-[A-Za-z0-9-]{10,}'
check 'AWS access key id'                   'AKIA[0-9A-Z]{16}'
check 'sk- style API key'                   'sk-[A-Za-z0-9_-]{16,}'
check 'GitHub token'                        'gh[pousr]_[A-Za-z0-9]{20,}'
check 'GitHub fine-grained token'           'github_pat_[A-Za-z0-9_]{20,}'
check 'private key block'                   '-----BEGIN [A-Z ]*PRIVATE KEY-----'
check 'api_key with an inline value'        "api[_-]?key[[:space:]]*[=:][[:space:]]*${q}[^\"'<\$][^\"']{7,}"

# a user_credentials-shaped object carrying an inline "value"
if grep -Eq 'user_credentials' <<<"$content" && grep -Eq '"value"[[:space:]]*:[[:space:]]*"[^"]{8,}"' <<<"$content"; then
  echo "block-secrets: refusing to write $file — a user_credentials-shaped object carries an inline \"value\". Exports never contain credential values; reference the credential by name." >&2
  exit 2
fi

exit 0
