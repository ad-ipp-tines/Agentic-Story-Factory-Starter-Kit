# The provisioning token — `github_factory`

_Spec: REPO-DESIGN.md §13 rows 1–3 and 12, §7.2 (section A's GitHub calls), §6.5 (the `tracker-bot` App), §16 (K11–K13, K44). Every GitHub permission heading below is as GitHub documents it today and is **VERIFY K11** until you have created one token with it._

`[KIT] 00` writes to GitHub on **day 1 only**, in section A, with one short-lived, fine-grained token stored in Tines under the fixed credential name **`github_factory`**. After day 1 the kit story never writes to GitHub: changes made in Tines reach the repository because the repository's own Actions *pull* them and open pull requests (`tracker-pull.yml`, with the `tracker-bot` App). So the token can be narrow, short-lived and then revoked.

## What the token is used for

| Step | Call | Why |
|---|---|---|
| A10 `probe_template` | `GET /repos/{template_owner}/{template_repo}/contents/README.md` (raw) | Prove the token can read the template before anything is created |
| A11 `generate_repo` | `POST /repos/{template_owner}/{template_repo}/generate` with `private: true` | Create your repository from the template |
| A12 `fallback_repo` (only if A11 is refused) | `POST /orgs/{org}/repos` · `GET /repos/{template_owner}/{template_repo}/contents/{path}` · `PUT /repos/{org}/{repo}/contents/{path}` | Create an empty private repository and copy the template file by file (slow: one commit per file) |
| A13 `wait_for_repo` | `GET /repos/{org}/{repo}/contents/README.md` | Wait until the new repository is readable (K12) |
| A15 `read_bundle` | `GET /repos/{org}/{repo}/contents/kit/bundle/kit-bundle.json` (raw) | Read the new repository's own bundle |
| A16 `write_config` | `PUT /repos/{org}/{repo}/contents/kit/tenant/config.yaml` | The tenant config commit |
| A29 `write_report` | `PUT /repos/{org}/{repo}/contents/kit/tenant/setup-report.json` | The setup report |

The raw media type header string, and behaviour above 1 MB, are VERIFY K44. Files over 1 MB are listed in the report as `[BY HAND]` copies.

## The scopes

Create a **fine-grained** token.

| Setting | Value | Why |
|---|---|---|
| Resource owner | **the one organisation** that will own the new repository | The kit creates the repository there |
| Repository access | **All repositories** of that organisation | A token limited to selected repositories cannot reach a repository created after it (VERIFY K11). This is why the token is short-lived and revoked |
| *Administration* — write (the heading for repository creation may be *Repository creation* instead: VERIFY K11) | granted | `POST …/generate` and `POST /orgs/{org}/repos` |
| *Contents* — read and write | granted | Read the template and the bundle; commit the config and the report; the fallback copies |
| *Workflows* — write | granted when the fallback copies `.github/workflows/**`, and possibly for `/generate` of a template that contains workflow files (VERIFY K11) | Without it, each workflow file the fallback copies fails and is reported per file |
| *Metadata* — read | whatever GitHub requires alongside the permissions above (VERIFY K11) | — |
| **Pull requests, Actions, Secrets** | **not granted** | The kit story never opens a PR, runs a workflow or sets a secret. Secrets need a libsodium sealed box, which an HTTP Request action cannot produce, so the GitHub environments are always set by hand |
| **Expiry** | **7 days or less** | Revoked after day 1 in any case (a day-1 milestone) |

Other VERIFY K11 items: creating organisation repositories without an organisation policy that allows it; reading a public template owned by another account. If your organisation must approve fine-grained tokens, an organisation owner approves this one.

**The template must be readable by this token.** The published template is public, or a copy of it lives in your organisation. A private template owned by someone else must be copied into your organisation first.

## Store it in Tines

1. In the **ops team** (the prod team), create a credential named exactly **`github_factory`** holding the token. The name is fixed: the kickoff Page never asks for it, so no Page answer can point a credential at another host.
2. Set **`allowed_hosts`** to `api.github.com`.
3. Turn **Workbench access off** for it.
4. Never paste the token anywhere else — not on the kickoff Page (its `is_valid_input` Trigger rejects any answer shaped like a token, including a `github_pat_` prefix), not in a prompt, a file, a commit or a chat. `block-secrets.sh` refuses a write whose content looks like a fine-grained token, and gitleaks runs in CI.

## Revoke it after day 1

When the setup report is `ok`, or `partial` with every GitHub step done — the same day:

1. **Clear the `github_factory` credential's value in Tines right away.** Until then it is an organisation-wide token with repository-creation, contents and workflows write, readable by any story or Editor in the ops (prod) team. A later re-run of section A needs a new token anyway, and `[KIT] 00` stops a completed run before any GitHub call.
2. Revoke the token in GitHub (or confirm it expires within days).
3. Mark the day-1 criterion "the provisioning token is revoked or expiring" with the date.

A partial run resumes when the Page is submitted again, and a resumed run needs a valid token for the GitHub steps it has not finished.

## The other GitHub identities in this repository

`github_factory` is one of several, each with one job:

| Identity | Held in | Scope | Used by |
|---|---|---|---|
| `github_factory` (this page) | Tines credential, ops team | Fine-grained token, one organisation, ≤ 7 days | `[KIT] 00` section A, day 1 only |
| **`tracker-bot`** | A GitHub App installed on this repository only; its id and private key in the GitHub environment `tracker` | Write access to contents and pull requests (exact headings as for K11); an installation token per run through `POST /app/installations/{id}/access_tokens` | `tracker-pull.yml` and `kit.yml`, which open the tracker, tracker-drift and apply-config PRs. `GITHUB_TOKEN` is never used for them: GitHub starts no `pull_request` workflows for a PR opened with it, so `sdlc.yml` would never report |
| **`github_dispatch`** | Tines credential used by `[OPS] 10`, the ops sweep | This one repository, only what `repository_dispatch` and opening issues need (headings as for K11); `allowed_hosts` = `api.github.com`; owned by the ops role; rotated quarterly and whenever the sweep's GitHub calls return 401 | The ops sweep's fix proposals and GitHub issues |
| Workflow keys | GitHub environments (`production`, `prod-read`, `break-glass`, `kit-sync`, …) | Team-scoped Tines keys, never an approver key | The scaffold's and the kit's workflows (`scripts/README.md`, "GitHub configuration checklist") |

## Later: a GitHub App instead of a token

The v2 path replaces `github_factory` with a GitHub App installation token: Tines' `JWT_SIGN` signs an RS256 JWT for the App, and `POST /app/installations/{id}/access_tokens` exchanges it for a token that lives one hour and can be narrowed to the one repository. It is not built in v1; until it is, the short expiry and the day-1 revocation are what keep the token's reach small.

## Verify in your tenant before relying on it

| Item | What is assumed |
|---|---|
| K11 | The permission headings for `/generate` and organisation repository creation; creating organisation repositories without an organisation policy; reaching a repository created after the token; reading a public template owned by another account |
| K12 | How long until a generated repository is readable; whether Actions is enabled on it; the setting that lets workflows open pull requests |
| K13 | A Contents PUT into a repository with no commits; the status code for concurrent-commit conflicts; the maximum PUT size |
| K44 | The raw media type header string; behaviour above 1 MB |
