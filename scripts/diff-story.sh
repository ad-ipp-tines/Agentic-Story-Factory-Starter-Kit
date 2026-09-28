#!/usr/bin/env bash
# Thin shim so DESIGN.md's paths keep working (skills and settings call ./scripts/diff-story.sh).
# The implementation is scripts/diff_story.py.
set -euo pipefail
exec "${PYTHON:-python3}" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/diff_story.py" "$@"
