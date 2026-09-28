/**
 * routes/Milestones.tsx — the day-1 / week-1 / week-4 onboarding checklist (REPO-DESIGN.md §11.1).
 *
 * §9.2 row "Milestones": data = useRecords(sdlc_milestones). The criteria are the ARTIFACT field (Markdown bullet
 * lines, from kit/tracker/milestones.yaml through the tracker sync). Status and evidence are updated in Tines or by
 * PR, and reach git through the tracker PR; kit/ONBOARDING.md is the runbook behind each item.
 */
import * as React from "react";
import { formatDate, useMilestones, type MilestoneRow } from "../lib/tracker";

const STATUS_STYLE: Record<string, string> = {
  not_started: "bg-slate-100 text-slate-700",
  in_progress: "bg-sky-100 text-sky-900",
  done: "bg-emerald-100 text-emerald-900",
  blocked: "bg-rose-100 text-rose-900",
};

function Milestone({ m }: { m: MilestoneRow }) {
  const overdue = m.status !== "done" && m.due_date !== null && m.due_date < new Date().toISOString();
  return (
    <section className="rounded-lg border border-slate-200 p-3">
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{m.title || m.milestone_id}</h3>
        <span className={`rounded px-1.5 py-0.5 text-[11px] ${STATUS_STYLE[m.status] ?? "bg-slate-100"}`}>{m.status || "—"}</span>
        <span className={`text-xs ${overdue ? "font-medium text-rose-700" : "text-slate-500"}`}>
          due {formatDate(m.due_date)}
          {overdue ? " · overdue" : ""}
        </span>
        <span className="ml-auto text-xs text-slate-500">owner: {m.owner || "—"}</span>
      </header>
      <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-slate-700">
        {m.criteria.map((c, i) => (
          <li key={`${m.milestone_id}-${i}`}>{c}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">
        Evidence: {m.evidence_ref ? <span className="font-mono">{m.evidence_ref}</span> : "none recorded yet"}
        {m.pending_repo_sync ? " · a change is waiting for its tracker PR" : ""}
      </p>
    </section>
  );
}

export default function Milestones() {
  const milestones = useMilestones();
  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Onboarding milestones</h2>
      <p className="mb-4 text-sm text-slate-600">Day 1, week 1 and week 4, counted from provisioning (UTC).</p>
      {milestones.loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
      {milestones.error ? <p className="text-sm text-rose-800">Milestones could not be read: {milestones.error}</p> : null}
      {!milestones.loading && milestones.rows.length === 0 ? (
        <p className="text-sm text-slate-500">No milestones yet — [KIT] 00 seeds them during provisioning (A22).</p>
      ) : null}
      <div className="space-y-3">
        {milestones.rows.map((m) => (
          <Milestone key={m.milestone_id || m.recordId} m={m} />
        ))}
      </div>
    </div>
  );
}
