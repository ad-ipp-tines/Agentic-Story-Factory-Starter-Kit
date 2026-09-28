# Prompt pack — literal prompts that work against `/mcp`, one per action, in build order

_Loaded by `/tines-build-story` step 3. Every prompt has the same shape: **story name + action type + action name + field names + "then validate"**. Replace every `<placeholder>`. Never name a `/mcp` tool; the server chooses its own tools from what you ask for. Never paste a value — credentials and Resources are referenced by name and must already exist in the dev team._

## The shape of every prompt

```
In the story "<[PREFIX] NN · Verb noun (sub)>" (team <dev team name>), <do one thing to one named action of one named type, naming the fields>. Then validate.
```

- One action per prompt. A prompt that adds two actions is two prompts.
- Name the field paths the way Tines will see them: the Send to Story payload arrives at the entry action's body; downstream actions reference `<<normalize.ip>>`-style paths, not the raw payload.
- End with "Then validate" so the server runs its validation pass after each change.
- If the story does not exist yet, P1 creates it; every later prompt names it.

## P0 — read first (always)

```
Read the story "<name>" in team <team>. List every action with its type and name, the links between them, the credentials and Resources it references by name, and the most recent error logs. Do not change anything.
```

## P1 — create the story and the entry

```
In the Tines team <team>, in the folder "<folder>", create a new story named "[<PREFIX>] <NN> · <Verb noun> (sub)" with the description "<one sentence: purpose, inputs, outputs>". Add a Send to Story entry action that expects a payload with the fields <a>, <b>. Then add an Event Transform in message-only mode named normalize that outputs { a: DEFAULT(<entry>.body.a, ""), b: DEFAULT(<entry>.body.b, "") }. Then validate.
```

For a webhook-driven story replace the entry with: `Add a Webhook entry action named receive that responds immediately with 200 and passes the body through.` For a scheduled story: `Add a schedule action named every_15m with the cron "*/15 * * * *".`

## P2 — the guard before any lookup or AI step

```
In "<story>", after normalize, add a Trigger named is_protected whose rule is true when normalize.a is inside any range listed in the Resource named never_block (use IN_CIDR). On the true branch add an Event Transform in message-only mode named refused that outputs { status: "refused", reason: "protected range" }. The false branch continues. Then validate.
```

## P3 — integrate by named credential

```
In "<story>", on the false branch of is_protected, add the <vendor> "<template name>" template action named <vendor>_lookup using the credential named <credential_name> from this team. Send it <<normalize.a>>. Then validate.
```

If the vendor has no template: `add an HTTP Request action named <vendor>_lookup that GETs https://<documented API host>/<path> with the header Authorization set from the credential named <credential_name>` — the header value is a credential reference, never a literal.

## P4 — the verdict with fallbacks

```
In "<story>", after the lookups, add an Event Transform in message-only mode named verdict that outputs { verdict: <rule over the lookup fields with DEFAULT() on every path>, score: DEFAULT(<path to a numeric score>, 0), sources: [ "<vendor1>", "<vendor2>" ] }. Then validate.
```

## P5 — branch on an explicit field

```
In "<story>", after verdict, add a Trigger named is_<condition> that is true when verdict.verdict equals "<value>". On the true branch add the Slack "Send message" template action named notify_<channel> using the credential named <slack_credential_name>, posting to the channel from the Resource named ops_routing, with the text "<short message using <<verdict.verdict>> and <<verdict.score>>>". Then validate.
```

Triggers branch on **explicit fields**, never on prose, confidence or sentiment.

## P6 — finish: `result` and `error`

```
In "<story>", add a final Event Transform in message-only mode named result that emits exactly { verdict: <<verdict.verdict>>, score: <<verdict.score>>, sources: <<verdict.sources>>, summary: "<one line>" } and connect every success branch to it. Add an Event Transform in message-only mode named error that emits { status: "error", error_category: "<auth|rate_limit|upstream_5xx|validation|permission|unknown>", retryable: <true|false>, message: "<what failed>" } and connect every failure branch to it. Then validate.
```

A sub-story's description must state the `result` shape — tool responses carry no output schema, so the description is the contract.

## P7 — hardening on every HTTP Request action

```
In "<story>", on every HTTP Request action: set retry on status to 429 and 500-599, set retries to 6, set emit failure event to Always, and connect the failure output to the error action. On <vendor>_lookup also set a log-error rule for a 200 response whose body reports an error. Then validate.
```

Exclude expected non-2xx codes (a lock's 422, an empty lookup's 404) from error logging in the same prompt when they apply. Export key names for these options are VERIFY (`docs/VERIFY.md` #8) — read them from the first real export.

## P8 — the Note

```
In "<story>", add a Note that states: purpose (<one sentence>), inputs (<fields>), outputs (the result shape and the error shape), the credentials and Resources used by name, and the mode badge "<Mode 1|2|3|4|none>". Then validate.
```

## P9 — an AI Agent action (Task mode), one tool first

```
In "<story>", after <guard trigger>, add an AI Agent action named triage in Task mode. System instructions: "<from stories/<slug>/agent/system-instructions.md>". Prompt: the fields <<normalize.*>> and the evidence gathered so far. Output schema: <paste stories/<slug>/agent/output-schema.json>. Temperature 0.2. Add exactly one tool: the Send to Story "<[PREFIX] NN · Verb noun (sub)>" with a Timeout Duration of <seconds> and the description "<3–4 sentences: what it returns, when to call it, one example argument>". Then validate.
```

Then, as a separate prompt: `add a Trigger named needs_human after triage that is true when triage.needs_human is true or triage.severity is "high" or "critical"` — the Trigger reads the schema field, never the prose. Add further tools **one at a time**, each with its own prompt, never more than five. The token alert on the Status tab and the skill attachment are [BY HAND].

## P10 — wiring tools on a Mode 4 server (after the MCP server action is on the canvas)

```
In "<story>", on the MCP server action, add a Send to Story tool named <domain>_get_<thing> pointing at "<[PREFIX] NN · Verb noun (sub)>" with the description "<3–4 sentences: what it returns and the field names, when to use it, what it does not do, one example argument value>". Mark its Tool hints as Read only. Set the server action's description to: "<server instructions: who the assistant is, fetch before recommend, request tools only request>". Then validate.
```

Whether Tool hints can be set through `/mcp` is unpublished (VERIFY #25); if the server cannot, set them [BY HAND] under each tool's **Tool hints**.

## P11 — export is the script, not the editor

Never ask the server to "export the story to a file". Run `/tines-export <slug>` — it calls `GET /api/v1/stories/{id}/export?randomize_urls=false&clear_recipients=true`, normalises, lints, stamps `story.meta.yaml` and prints the semantic diff.

## Correction habits

| What you see | What it means | What to say |
|---|---|---|
| A reference resolves to nothing / empty output | The path is wrong — the payload arrives at the entry action's body | "The payload arrives at the Send to Story action's body; fix the reference to <<entry.body.a>> and validate again." |
| "credential not found" | Wrong team, or a different name | Fix the name in the prompt, or create it in the dev team [BY HAND] once. Never paste a value. |
| Validation reports the same issue twice | The prompt is ambiguous | Stop. Clear the context and restart with a prompt that names the action type and the exact fields. |
| The server proposes a second action you did not ask for | Scope creep | "Only <action name>; leave everything else unchanged." |
| An action was renamed or reordered | Links are index-based; a reorder can rewire the story | Ask it to restore the original order and names; check the canvas before exporting. |
| The story is in the wrong team or folder | The manifest and the prompt disagree | Fix the manifest first; never move a story through prompts. |

## What not to say to the server

- Any `/mcp` tool name (unpublished; `docs/VERIFY.md` #1).
- Any credential value, Resource body, token, webhook URL or email address.
- "Import the Library story <id>" — it cannot; import into the 90 Seeds folder [BY HAND].
- "Deploy / promote / push to production" — production is reached only by `/tines-ship` → change request → a named approver.
