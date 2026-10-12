# `workflows/` — 3B workflows as directories

A workflow in 3B is a folder, not an export. This directory is the space-clone layout the pivot uses. Cloning a folder out of a real space, editing it, and pushing a draft branch has not been done from this repository. That round trip is **VERIFY** (task #19). Do not invent the CLI or MCP call that would perform it.

## Layout

```
workflows/<name>/
├── workflow.toml          # has an id; preserve it; never copy it onto another workflow
├── README.md              # purpose, inputs, outputs
└── <step>/
    ├── config.toml
    ├── Dockerfile         # first line is exactly: FROM 3b/base
    ├── README.md
    └── <code>             # TypeScript by default (Bun)
```

`<name>` is the directory. The slug in [`_manifest.yaml`](_manifest.yaml) points at it. The workflow `id` inside `workflow.toml` is assigned by the space. A copy of a workflow is a different workflow only after it has its own id.

## Rules that already hold

- One workflow per pull request once builds start. This layout PR adds the template only.
- No secrets in code, chat, or volumes. Credentials go through connectors only.
- No hard-coded hostnames. A workflow builds its own URLs from `_3B_WORKFLOW_BASE_URL`.
- A route defaults to space auth. `public` only when a person explicitly asks. Any `route_type` needs a `title`.
- Do not add an endpoint in the template. A later task designs routes; this folder does not.

## What is VERIFY here

Key names in `workflow.toml` and `config.toml` other than the ones named in [`3b/PIVOT.md`](../3b/PIVOT.md), which file each key lives in, the TypeScript entry filename, and how a space clone is pushed. The files in `_template/` use the names the brief gives and say so in comments.

## Start

Copy [`_template/`](_template/README.md). Replace `workflow.toml`'s `id` before that copy is a second workflow. Then fill the slug's space ids in `_manifest.yaml`. Leave them empty until a space assigns them.
