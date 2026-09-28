# 05 · Security controls → read `04-security-model.md`

_This path is the name `DESIGN.md` §2.2 gives this document (also linked from `policies/POLICY.md`). The content lives in `04-security-model.md`; this file exists so that link resolves._

`DESIGN.md` §3.9 asks for §7 as a table — control · mechanism (editor / repo / CI / tenant) · enforced by (hook, permission rule, workflow, policy, Resource, Tines setting) · verify status. That is `04-security-model.md` §3 (threats → controls, with the verify column) together with §2 (identities and least privilege), §4 (secrets), §5 (change control), §6 (least-privilege tool lists), §7 (hooks), §8 (review in fresh context), §9 (audit), §10 (data policy) and §11 (residual risks). The governance contract in prose is `policies/POLICY.md`.

## Verify in your tenant before presenting

A security reviewer should get four files for four questions — least privilege → `policies/POLICY.md`; cost ceiling → `policies/cost-ceilings.yml`; auditability → a real change-request description carrying the commit SHA plus a story version plus one audit-log row of MCP activity; rollback → `.github/workflows/rollback.yml` run once against the dev team. Items 1, 2, 18 and 25 of `07-verify-before-you-rely-on-it.md` first.
