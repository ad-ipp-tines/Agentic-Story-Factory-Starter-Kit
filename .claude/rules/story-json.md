---
paths: ["stories/**/story.json"]
---

# `story.json` is an export, not a source file

- This file is produced by `/tines-export` from `GET /api/v1/stories/{id}/export` and normalised by `scripts/normalize.jq`. It is never typed and never hand-edited.
- To change the story, change it in the **dev team** through the Tines Stories MCP server with `/tines-build-story <slug> "<change>"`, then run `/tines-export <slug>`.
- Never edit `guid`, `links`, `diagram_layout` or the order of `agents[]` by hand: `links` reference agents **by index**, so a reorder or a removed entry silently rewires the story.
- Recipients are cleared on export (`clear_recipients=true`) and set from `stories/_manifest.yaml` by `ship.yml`; do not add them here.
- Credentials and Resources appear **by name only**. If a value that looks like a token, a secret, a resource body or an email address appears in this file: stop, do not commit, and report it — an export never contains one.
- The single sanctioned exception is `/tines-propose-fix` (headless, one allow-listed option key on one named action, never links or agent order). Everything else goes back through `/mcp`.
