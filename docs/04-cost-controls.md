# 04 · Cost controls → read `03-cost-controls.md`

_This path is the name `DESIGN.md` §2.2 gives this document (also linked from `policies/POLICY.md`). The content lives in `03-cost-controls.md`; this file exists so that link resolves._

`DESIGN.md` §3.9 asks for §6 as a table — control · mechanism (editor / repo / CI / tenant) · enforced by · verify status. That table is `03-cost-controls.md` §2. Around it: what costs Tines AI credits and what does not (§1), credits (§3), token alerts (§4), model routing (§5), tool counts (§6), the sandbox team (§7), IDE-side limits (§8), a worked month (§9) and what to measure from day one (§10).

## Verify in your tenant before presenting

Items 10, 11 and 13 of `07-verify-before-you-rely-on-it.md` gate every cost figure; the worked month in `03-cost-controls.md` §9 is arithmetic on placeholders, to be replaced with a week of your own `GET /api/v1/ai_usage` rows.
