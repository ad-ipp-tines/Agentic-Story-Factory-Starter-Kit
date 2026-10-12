# `_template` — one TypeScript step

Copy this folder to start a workflow. It is not a workflow that runs in a space: `workflow.toml` still says `REPLACE_ON_CLONE`, and [`../_manifest.yaml`](../_manifest.yaml) has no space id for it.

## What it does

One step, `echo`. It reads JSON on stdin and writes one JSON object on stdout. It has no trigger, so it publishes no URL and no endpoint.

## What you change on a copy

1. Give the copy its own directory name and its own `workflow.toml` `id`. Never reuse `REPLACE_ON_CLONE` or another workflow's id.
2. Write the slug and the empty-until-assigned space ids in `workflows/_manifest.yaml`.
3. Replace `echo` when the workflow needs a different step. Keep `Dockerfile`'s first line as `FROM 3b/base`.

## Inputs and outputs

| | |
|---|---|
| Input | JSON on stdin. Empty stdin is treated as no value. Non-JSON stdin is a failure (nonzero exit, nothing on stdout). |
| Output | One line: `{"status":"ok","echoed": ...}` |
| Downstream | None. `links` is empty. Empty stdout would stop downstream steps; this step writes stdout on success. |

Stdin handling on the TypeScript (Bun) template is **VERIFY** until a step test pins it.

## Not in this template

No route, no cron, no email trigger, no connector, no volume, no secret, no hostname. Adding any of those is a later change with its own review. A route needs a `route_type` and a `title`, and `route_auth` stays `space` unless a person asks to widen it.
