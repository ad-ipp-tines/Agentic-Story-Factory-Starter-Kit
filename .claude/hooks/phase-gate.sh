#!/usr/bin/env bash
# phase-gate.sh — PreToolUse hook, matcher "mcp__tines__.*" (the Tines Stories MCP server, Mode 2). It is wired beside
# guard-mcp.sh on the same matcher. Claude Code runs matching hooks in PARALLEL, so neither may rely on the other having
# run: each denies on its own (exit 2 from either blocks the call), and this hook repeats the production checks it needs
# (step p). Spec: REPO-DESIGN.md §6.1 ("phase-gate.sh"), §4.4 (03 build), §6.2, §16 K2.
#
# /mcp opens for exactly one story, for exactly one caller, only while that story is in build ON MAIN:
#   p · production       TINES_ENV=prod is refused, and so is any number (or digits-only string) in the tool input that
#                        equals a production or never-touch story id, a never-touch team id, or the manifest's prod
#                        team_id / folder_id — the same input-based check as guard-mcp.sh 1 and 2a, applied here too
#                        (and before step 0, so STORYLINE_ENFORCE=0 never lifts it)
#   0 · STORYLINE_ENFORCE=0   the scratch-story escape hatch — logged, then allowed (guard-mcp.sh runs on the same call and
#                        still mirrors and checks it)
#   1 · active story     .storyline/active (local, written only by `./scripts/storyline start`) names a kebab-case story key
#   2 · state on main    that story's row in `git show origin/main:kit/tracker/backlog.yaml` — never the working tree —
#                        is build/active or build/rework. The editor's Write and Edit tools are denied on .storyline/**,
#                        kit/tracker/** and storyline/work/** (.claude/settings.json), so no file edit can open /mcp without
#                        G1 and G2 having merged
#   3 · the caller       the hook input identifies the `tines-builder` subagent. Whether a hook CAN tell which subagent
#                        is calling is VERIFY K2 — until it is confirmed, K2_CALLER_JQ below stays empty and EVERY
#                        mcp__tines__* call is denied. Day-1 check: run one builder call; .storyline/phase-gate.log records the
#                        hook input's top-level keys and scalar values (never tool_input); if a field names the subagent,
#                        set K2_CALLER_JQ to its jq path by PR (security-platform review) and record K2 in docs/VERIFY.md
#   4 · one story        no number (or digits-only string) in the tool input equals another slug's dev or prod story id
#                        in stories/_manifest.yaml. Then, by the slug's dev.story_id:
#                          dev id 0  → only the create-shaped call passes (VERIFY1_CREATE_TOOL_RE below); after it,
#                                      `./scripts/tines manifest-set-dev-id <slug> <id>` records the id the create call
#                                      returned, and every later call is checked against it
#                          dev id set → every story id the input addresses must be that id. Once scaffold VERIFY #1
#                                      records the /mcp input shapes, VERIFY1_STORY_ID_JQ below names those fields and
#                                      any other id is denied; until then the input-based fallback denies any `story_id`
#                                      key that carries another id
#
# Fails CLOSED: exit 2 when jq, yq or git is missing, when origin/main, the tracker, the manifest or the never-touch list
# cannot be read, or when the input cannot be parsed. Any other error under set -e is caught by the ERR trap below and also exits 2, and
# .claude/settings.json runs this file as `bash … || exit 2`, so a missing or crashing hook blocks (Claude Code treats
# every exit code other than 2 as a non-blocking error). Contract: stdin is the hook JSON ({session_id, tool_name,
# tool_input, ...}); exit 2 blocks the call and stderr is shown to the model; exit 0 allows it (guard-mcp.sh and the
# permission rules still apply).
set -euo pipefail
trap 'echo "phase-gate: internal error — refused" >&2; exit 2' ERR

# ---- VERIFY K2 -------------------------------------------------------------------------------------------------------
# The jq path, into the hook input, of the field that names the calling subagent (for example '.agent_type' — a GUESS
# until K2 is confirmed; do not fill it from a guess). Empty = not confirmed = every mcp__tines__* call is denied.
K2_CALLER_JQ=''
BUILDER='tines-builder'
# ---- scaffold VERIFY #1 (docs/VERIFY.md #1: the /mcp tool names and input shapes are unpublished) --------------------
# Fill both by PR (security-platform review) once #1 records the tenant's tool list and input shapes; never from a guess.
# VERIFY1_STORY_ID_JQ   jq over .tool_input yielding every story id the call addresses (for example
#                       '.. | objects | .story_id? // empty' — a GUESS until #1). Empty = the input-based fallback of step 4.
# VERIFY1_CREATE_TOOL_RE  an ERE over tool_name matching the one call that creates a story. Empty = unknown = while the
#                       slug's dev.story_id is 0 every call is denied (create the dev story by hand, then record its id).
VERIFY1_STORY_ID_JQ=''
VERIFY1_CREATE_TOOL_RE=''
# -----------------------------------------------------------------------------------------------------------------------

input=$(cat)
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$root"

log() { # $1 decision, $2 reason — to .storyline/phase-gate.log (local, gitignored); never tool_input values
  mkdir -p .storyline 2>/dev/null || return 0
  if command -v jq >/dev/null 2>&1; then
    jq -c --arg ts "$(date -u +%FT%TZ)" --arg decision "$1" --arg reason "$2" --arg slug "${slug:-}" \
      '{ts: $ts, decision: $decision, reason: $reason, slug: $slug, tool: (.tool_name // ""),
        input_keys: (keys? // []),
        scalars: (with_entries(select(.key != "tool_input" and .key != "tool_response" and ((.value | type) as $t | $t == "string" or $t == "number" or $t == "boolean")) | .value |= (tostring | .[0:120])) )}' \
      <<<"$input" >> .storyline/phase-gate.log 2>/dev/null || true
  fi
}

block() { log deny "$*"; echo "phase-gate: $*" >&2; exit 2; }

slug=""
command -v jq  >/dev/null 2>&1 || block "jq is not installed — the lifecycle gate cannot run, so the call is refused (install jq)"
command -v yq  >/dev/null 2>&1 || block "yq is not installed — the tracker cannot be read, so the call is refused (install yq)"
command -v git >/dev/null 2>&1 || block "git is not installed — the tracker on main cannot be read, so the call is refused"
jq -e 'type == "object"' >/dev/null 2>&1 <<<"$input" || block "unreadable hook input — refused (fail closed)"
tool=$(jq -r '.tool_name // ""' <<<"$input") || block "unreadable hook input — refused (fail closed)"

# p · production — this hook's own check; it never relies on guard-mcp.sh having run (hooks run in parallel)
[[ "${TINES_ENV:-dev}" != "prod" ]] || block "TINES_ENV=prod — authoring via /mcp is dev-only; use /tines-ship"
[[ -r stories/_manifest.yaml ]] || block "stories/_manifest.yaml is missing or unreadable — refused (fail closed)"
[[ -r policies/never-touch.yml ]] || block "policies/never-touch.yml is missing or unreadable — refused (fail closed)"
prod_protected=$( {
  yq -r '(.story_ids // [])[], (.teams // [])[]' policies/never-touch.yml
  yq -r '.stories[].prod.story_id, .environments.prod.team_id, .environments.prod.folder_id' stories/_manifest.yaml
} 2>/dev/null ) || block "could not read the production and never-touch ids with yq — refused (fail closed)"
prod_protected=$(grep -E '^[0-9]+$' <<<"$prod_protected" | grep -vx '0' | sort -u || true)   # 0 is the unfilled placeholder
ids=$(jq -r '[.tool_input | .. | ((numbers | tostring), (strings | select(test("^[0-9]+$"))))] | unique | .[]' <<<"$input" 2>/dev/null) \
  || block "could not read the tool input — refused (fail closed)"
if [[ -n "$prod_protected" ]]; then
  for id in $ids; do
    if grep -qx "$id" <<<"$prod_protected"; then
      block "id $id is write-protected (a production or never-touch story, a never-touch team, the prod team or the prod folder); build in the dev team"
    fi
  done
fi

# 0 · the scratch-story escape hatch
if [[ "${STORYLINE_ENFORCE:-1}" == "0" ]]; then
  log allow "STORYLINE_ENFORCE=0"
  echo "phase-gate: STORYLINE_ENFORCE=0 — the lifecycle gate is OFF for this call (scratch story only); the production check above still ran, and guard-mcp.sh still mirrors and checks the call" >&2
  exit 0
fi

# 1 · the active story
[[ -r .storyline/active ]] || block "no active story: /mcp opens only for the story in build — run /storyline <slug>, then ./scripts/storyline start <slug>"
slug=$(tr -d '[:space:]' < .storyline/active)
[[ "$slug" =~ ^[a-z0-9][a-z0-9-]{0,63}$ ]] || block ".storyline/active does not hold a story key — run ./scripts/storyline start <slug>"

# 2 · the row on origin/main (git wins; the working tree never opens /mcp)
git rev-parse --verify --quiet 'origin/main^{commit}' >/dev/null 2>&1 \
  || block "no origin/main ref — run: git fetch origin main (the gate reads the tracker from main, never the working tree)"
tracker=$(git show 'origin/main:kit/tracker/backlog.yaml' 2>/dev/null) \
  || block "kit/tracker/backlog.yaml is not on origin/main — refused (fail closed)"
state=$(yq -r ".stories[] | select(.key == \"$slug\") | ((.phase // \"\") + \"/\" + (.status // \"\"))" <<<"$tracker" 2>/dev/null) \
  || block "could not read $slug from the tracker on origin/main with yq — refused (fail closed)"
state=$(head -n1 <<<"$state")
[[ -n "$state" ]] || block "$slug has no row in the tracker on origin/main — run /storyline $slug"
case "$state" in
  build/active|build/rework) ;;
  *) block "$slug is in $state on origin/main; /mcp opens after G1 and G2 (the design PR merged) — run /storyline $slug" ;;
esac

# 3 · the caller must be tines-builder (VERIFY K2)
if [[ -z "$K2_CALLER_JQ" ]]; then
  block "VERIFY K2 is not confirmed: this hook cannot yet tell which subagent is calling, so it denies every mcp__tines__* call. Day-1 check: the hook input's top-level keys are in .storyline/phase-gate.log; once a field naming the subagent is confirmed, set K2_CALLER_JQ in .claude/hooks/phase-gate.sh by PR. STORYLINE_ENFORCE=0 is for a scratch story only."
fi
caller=$(jq -r "($K2_CALLER_JQ) // \"\" | tostring" <<<"$input" 2>/dev/null) || block "could not read the caller with K2_CALLER_JQ — refused (fail closed)"
[[ "$caller" == "$BUILDER" ]] || block "only $BUILDER may call the Tines Stories MCP server (this caller: ${caller:-unidentified}); delegate the build to the $BUILDER subagent"

# 4 · this story only: no other story id in the input
dev_id=$(yq -r ".stories[\"$slug\"].dev.story_id // 0" stories/_manifest.yaml 2>/dev/null) || block "could not read the manifest with yq — refused (fail closed)"
dev_id=$(head -n1 <<<"$dev_id")
[[ "$dev_id" =~ ^[0-9]+$ ]] || block "$slug's dev.story_id in stories/_manifest.yaml is not a number — refused (fail closed)"
others=$(yq -r ".stories | to_entries[] | select(.key != \"$slug\") | (.value.dev.story_id // 0), (.value.prod.story_id // 0)" stories/_manifest.yaml 2>/dev/null) \
  || block "could not read the manifest's story ids with yq — refused (fail closed)"
prod_id=$(yq -r ".stories[\"$slug\"].prod.story_id // 0" stories/_manifest.yaml 2>/dev/null || echo 0)
protected=$(printf '%s\n' "$others" "$(head -n1 <<<"$prod_id")" | grep -E '^[0-9]+$' | grep -vx '0' | grep -vx "$dev_id" | sort -u || true)
if [[ -n "$protected" ]]; then
  for id in $ids; do
    if grep -qx "$id" <<<"$protected"; then
      block "id $id belongs to another story (or to $slug in prod); a build session works on $slug's dev story only"
    fi
  done
fi
if [[ -n "$VERIFY1_STORY_ID_JQ" ]]; then
  addressed=$(jq -r "[.tool_input | ($VERIFY1_STORY_ID_JQ) | tostring] | unique | .[]" <<<"$input" 2>/dev/null) \
    || block "could not read the story ids with VERIFY1_STORY_ID_JQ — refused (fail closed)"
else
  addressed=""
fi
if [[ "$dev_id" == "0" ]]; then
  # no dev story recorded yet: only the create-shaped call, and it names no story id
  [[ -n "$VERIFY1_CREATE_TOOL_RE" ]] \
    || block "$slug has no dev story id yet (stories/_manifest.yaml dev.story_id is 0) and scaffold VERIFY #1 has not recorded which call creates a story, so no /mcp call is allowed for it: create the dev story in the Tines UI [BY HAND] with the export's exact name, then run ./scripts/tines manifest-set-dev-id $slug <id>"
  [[ "$tool" =~ $VERIFY1_CREATE_TOOL_RE ]] \
    || block "$slug has no dev story id yet: only the call that creates it is allowed; record the id it returns with ./scripts/tines manifest-set-dev-id $slug <id> before any other call"
  [[ -z "$addressed" ]] || block "the create call for $slug names story id(s) $(tr '\n' ' ' <<<"$addressed")— refused"
elif [[ -n "$VERIFY1_STORY_ID_JQ" ]]; then
  # VERIFY #1 recorded: every story id the call addresses must be the active dev id (the id the create call returned)
  for id in $addressed; do
    [[ "$id" == "$dev_id" ]] || block "story id $id is not $slug's dev story ($dev_id); a build session works on that one story only"
  done
else
  # input-based fallback until VERIFY #1: any `story_id` key must carry this slug's dev id
  wrong=$(jq -r --arg dev "$dev_id" 'first(.tool_input | .. | objects | .story_id? // empty | tostring | select(. != $dev)) // empty' <<<"$input" 2>/dev/null) || wrong=""
  [[ -z "$wrong" ]] || block "story_id $wrong is not $slug's dev story ($dev_id)"
fi

log allow "$slug $state"
exit 0
