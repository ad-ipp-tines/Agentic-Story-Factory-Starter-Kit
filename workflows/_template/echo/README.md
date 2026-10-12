# `echo`

Reads JSON from stdin and writes `{"status":"ok","echoed": ...}` to stdout.

| | |
|---|---|
| Template | typescript (Bun). Default for this kit. |
| Trigger | none. This step does not receive HTTP, cron, or email. |
| Failure | Non-JSON stdin exits nonzero and writes nothing to stdout. |
| Links | none |

`Dockerfile` starts with `FROM 3b/base`. `timeout` is 30 seconds (allowed range 1–300). No credential, no volume, no hostname.

The entry filename `index.ts`, the `CMD`, and the stdin API are **VERIFY** until a step is run in a space and a step test pins the input and output.
