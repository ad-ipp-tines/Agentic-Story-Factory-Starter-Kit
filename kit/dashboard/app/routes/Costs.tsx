/**
 * routes/Costs.tsx — monthly credit estimate vs actual, per story.
 *
 * REPO-DESIGN.md §9.2 row "Costs": estimates from Records (storyline_backlog.credit_estimate_monthly, set at design from
 * credits observed in dev); actuals from the app_costs endpoint → GET /api/v1/ai_usage?group_by=story with the
 * tines_api_readonly key, which sees only what that key may see (K38). The chart is hand-written SVG (no chart
 * dependency is assumed, K18). Until the App's endpoint call is wired (K18), actuals show as "n/a" and the Tines
 * Dashboard and drift.yml's budget job are the places to read them.
 *
 * Credits and billed cost are never summed: a story on a custom or local provider spends no Tines AI credits and
 * bills outside Tines (`billed_cost`, which for custom and local providers is K25), so it shows "not metered in
 * credits". 1 credit = $0.01 on Tines-provided models.
 */
import * as React from "react";
import { BarChart, type BarDatum, type BarSeries } from "../components/BarChart";
import { formatCredits, href, useBacklog, useCostActuals } from "../lib/tracker";

const SERIES: BarSeries[] = [
  { key: "estimate", label: "Monthly estimate (credits)", fillClass: "fill-slate-400", swatchClass: "bg-slate-400" },
  { key: "actual", label: "Used this month (credits)", fillClass: "fill-sky-600", swatchClass: "bg-sky-600" },
];

export default function Costs() {
  const backlog = useBacklog();
  const actuals = useCostActuals();
  const actualByStoryId = new Map<number, number | null>();
  const actualByKey = new Map<string, number | null>();
  for (const a of actuals.rows) {
    if (a.story_id !== null) actualByStoryId.set(a.story_id, a.credits_used);
    if (a.story_key) actualByKey.set(a.story_key, a.credits_used);
  }
  const rows = backlog.rows.filter((r) => r.phase !== "rejected");
  const actualFor = (key: string, prodId: number | null): number | null =>
    actualByKey.get(key) ?? (prodId ? actualByStoryId.get(prodId) ?? null : null);

  const data: BarDatum[] = rows
    .filter((r) => r.credit_estimate_monthly !== 0 || actualFor(r.story_key, r.prod_story_id))
    .map((r) => ({
      label: r.story_key,
      values: {
        estimate: r.credit_estimate_monthly,
        actual: r.provider === "custom" || r.provider === "local" ? null : actualFor(r.story_key, r.prod_story_id),
      },
    }));

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Credits: estimate vs actual</h2>
      <p className="mb-4 text-sm text-slate-600">
        Stories with no AI Agent action, Workbench or Workbench for Storyboard use no credits and are left out of the
        chart. An improve trigger fires at 1.5 × the estimate.
      </p>
      {actuals.message ? <p className="mb-3 rounded bg-amber-50 p-2 text-xs text-amber-900">{actuals.message}</p> : null}
      <BarChart
        title="Monthly credit estimate and credits used, per story"
        data={data}
        series={SERIES}
        format={(v) => `${Math.round(v)}`}
        emptyText="No story has a credit estimate yet — estimates are set at design from credits observed in dev."
      />
      <table className="mt-6 w-full text-left text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className="py-1 pr-3 font-medium">Story</th>
            <th className="py-1 pr-3 font-medium">Provider</th>
            <th className="py-1 pr-3 font-medium">Estimate</th>
            <th className="py-1 pr-3 font-medium">Used this month</th>
            <th className="py-1 font-medium">Basis</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const external = r.provider === "custom" || r.provider === "local";
            const used = actualFor(r.story_key, r.prod_story_id);
            const ratio = !external && used !== null && r.credit_estimate_monthly ? used / r.credit_estimate_monthly : null;
            return (
              <tr key={r.story_key} className="border-t border-slate-100">
                <td className="py-1.5 pr-3">
                  <a className="text-sky-700 underline" href={href(`/story/${encodeURIComponent(r.story_key)}`)}>
                    {r.story_key}
                  </a>
                </td>
                <td className="py-1.5 pr-3 text-slate-700">{r.provider}</td>
                <td className="py-1.5 pr-3 text-slate-700">{formatCredits(r.credit_estimate_monthly)}</td>
                <td className={`py-1.5 pr-3 ${ratio !== null && ratio >= 1.5 ? "font-medium text-rose-700" : "text-slate-700"}`}>
                  {external ? "not metered in credits (billed_cost)" : used === null ? "n/a" : `${Math.round(used)} cr`}
                  {ratio !== null && ratio >= 1.5 ? " · ≥ 1.5 × estimate" : ""}
                </td>
                <td className="py-1.5 text-xs text-slate-500">{r.credit_estimate_basis || "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
