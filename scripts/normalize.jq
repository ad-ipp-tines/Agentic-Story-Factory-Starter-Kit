# scripts/normalize.jq — make a Tines story export diff-stable and safe to commit without changing what it means.
# Spec: DESIGN.md §3.5 "scripts/normalize.jq". Builder: ci.
#
#   jq -S -f scripts/normalize.jq export.json > stories/<slug>/story.json
#
# This file is the ONE definition of what normalisation removes or replaces. Everything that reads it:
#   scripts/export_story.py   pipes every export through it when jq is on PATH (`--normalizer auto`, the
#                             default); without jq it falls back to tines_common.normalize_export, which mirrors
#                             BOTH steps below (`exported_at` and the ingress identifiers). The Python side always
#                             writes the file (two-space indent, sorted keys), so the committed formatting never
#                             depends on which normaliser ran.
#   scripts/lint-story.sh     re-applies it to every export it lints and reports `not_normalised` when it would
#                             change anything beyond `exported_at` (lint_story.py already reports that key, and
#                             reports a real ingress identifier as `webhook_secret_in_export`, severity error).
#   .github/workflows/drift.yml compares production and `main` only after both went through this file.
#
# What it does
#   1. Drops the top-level keys in volatile_top_level_keys. Today that is `exported_at` only — the one key
#      confirmed to change on every export of an unchanged story (real exports, schema_version 28–30).
#      When a real export shows another field that changes with no story change, add it here, re-export,
#      and record it in docs/VERIFY.md #8. Never add a key that carries meaning.
#   2. Replaces the INGRESS IDENTIFIERS — `options.path` and `options.secret` — on EVERY action that carries
#      them, by key name and never by action type, with "<assigned-on-import>". A Webhook action's path and
#      secret are in the export (randomize_urls=false, observed), and so is an MCP server action's path; left
#      in, anyone who can read the repository could post to the router, the approval callback or the Mode 4
#      server. Skipped: a `path` that is a formula (an Event Transform explode path such as
#      <<findings.anomalies>>) and a value that is already a `<…>` placeholder. Whether an import into an
#      existing story keeps that story's own path and secret is VERIFY #6; if stable production URLs are
#      needed, keep them in GitHub environment secrets and re-apply them at ship time — never in the export.
#   3. Sorts object keys recursively (jq -S does the same at call time; doing it here keeps the output
#      stable even when a caller forgets -S).
#   4. Leaves every ARRAY in its original order. `links[]` reference `agents[]` BY INDEX
#      (`{"source": 0, "receiver": 6}`), so reordering agents would silently rewire the story.
#      `guid` values are kept. `diagram_layout` is kept: it is a JSON string (noisy but harmless — reviewers
#      read scripts/diff-story.sh and cr-view for the semantic diff, not the raw JSON).
#
# It never adds or renames a key, never rewrites any value other than the two ingress identifiers, and it
# refuses anything that is not a story export.

def volatile_top_level_keys: ["exported_at"];
def ingress_keys: ["path", "secret"];
def ingress_placeholder: "<assigned-on-import>";

def is_formula: test("<<") or test("^\\s*=");
def is_placeholder: test("^\\s*<[^<].*>\\s*$");

def redact_ingress:
  if (.options | type) == "object" then
    .options |= reduce ingress_keys[] as $k (.;
      if (.[$k] | type) == "string" and .[$k] != ""
         and (($k != "path") or ((.[$k] | is_formula) | not))
         and ((.[$k] | is_placeholder) | not)
      then .[$k] = ingress_placeholder
      else . end)
  else . end;

def sort_keys_recursively:
  if type == "object" then
    to_entries | sort_by(.key) | map(.value |= sort_keys_recursively) | from_entries
  elif type == "array" then
    map(sort_keys_recursively)          # element order preserved; only keys inside elements are sorted
  else . end;

if type != "object" then
  error("normalize.jq: expected a story export object, got \(type)")
elif (has("agents") | not) or ((.agents | type) != "array") then
  error("normalize.jq: not a story export (no agents[] array)")
else
  reduce volatile_top_level_keys[] as $key (.; del(.[$key]))
  | .agents |= map(if type == "object" then redact_ingress else . end)
  | sort_keys_recursively
end
