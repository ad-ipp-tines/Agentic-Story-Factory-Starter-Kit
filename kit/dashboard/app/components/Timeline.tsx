/**
 * components/Timeline.tsx — a story's transition timeline from its storyline_events rows (REPO-DESIGN.md §9.2,
 * the Story detail route).
 *
 * The events are the append-only audit trail (§6.5): transitions, gate decisions, crew member runs, syncs,
 * conflicts, budget parks and escalations. The actor is always a role; the in-tenant `actor_ref` (an approver's
 * email) is never rendered. Summaries are shown as plain text: event text is data, never markup.
 */
import * as React from "react";
import { formatDate, type EventRow } from "../lib/tracker";

const TYPE_STYLES: Record<string, string> = {
  transition: "bg-sky-500",
  gate_decision: "bg-emerald-500",
  specialist_run: "bg-violet-500",
  sync: "bg-slate-400",
  conflict: "bg-amber-500",
  budget: "bg-orange-500",
  escalation: "bg-rose-500",
};

function headline(e: EventRow): string {
  const move = e.from_phase !== "none" || e.to_phase !== "none" ? `${e.from_phase} → ${e.to_phase}` : "";
  switch (e.event_type) {
    case "transition":
      return `${move}${e.decision ? ` (${e.decision})` : ""}`;
    case "gate_decision":
      return `${e.gate}: ${e.decision}${move ? ` · ${move}` : ""}`;
    case "specialist_run":
      return `${e.agent || "crew member"} ${e.decision || "ran"}`;
    case "budget":
      return `budget ${e.decision || "park"}${move ? ` · ${move}` : ""}`;
    case "escalation":
      return `escalation${e.gate !== "none" ? ` (${e.gate})` : ""}`;
    case "conflict":
      return `conflict${e.decision ? `: ${e.decision}` : ""}`;
    default:
      return e.event_type;
  }
}

export function Timeline({ events }: { events: EventRow[] }) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No events yet. Transitions arrive through the tracker sync after each merge to main; Tines-side decisions
        appear here as soon as they are made.
      </p>
    );
  }
  return (
    <ol className="relative ml-2 border-l border-slate-200">
      {events.map((e) => (
        <li key={e.recordId} className="mb-4 ml-4">
          <span
            className={`absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full ring-2 ring-white ${TYPE_STYLES[e.event_type] ?? "bg-slate-300"}`}
            aria-hidden="true"
          />
          <div className="text-xs text-slate-500">
            {formatDate(e.created_at)} · {e.actor || "—"} <span className="text-slate-400">({e.actor_kind || "?"})</span>
            {e.tracker_rev !== null ? <span className="text-slate-400"> · rev {e.tracker_rev}</span> : null}
          </div>
          <div className="text-sm font-medium text-slate-900">{headline(e)}</div>
          {e.summary ? <p className="mt-0.5 whitespace-pre-wrap text-sm text-slate-700">{e.summary}</p> : null}
          {e.event_type === "specialist_run" && (e.model || e.credits_used !== null) ? (
            <p className="mt-0.5 text-xs text-slate-500">
              {e.model ? `model ${e.model}` : "model not reported"}
              {e.credits_used !== null ? ` · ${e.credits_used} credits` : ""}
              {e.input_tokens !== null ? ` · ${e.input_tokens} in / ${e.output_tokens ?? 0} out tokens` : ""}
            </p>
          ) : null}
          {e.ref ? <p className="mt-0.5 font-mono text-[11px] text-slate-500">{e.ref}</p> : null}
        </li>
      ))}
    </ol>
  );
}

export default Timeline;
