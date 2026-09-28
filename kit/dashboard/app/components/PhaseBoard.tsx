/**
 * components/PhaseBoard.tsx — one column per phase, one card per story (REPO-DESIGN.md §9.2, the Backlog route).
 *
 * Each card shows key · title · mode badge · owner · target date · open gate, and links to the story's detail
 * route. The eight lifecycle phases are always shown in order; the holding and terminal columns (parked,
 * rejected, retired) appear only when a story is in them. Read-only: the board never moves a card — a phase
 * changes only through a gate (a Page decision, a merge, a change request) and reaches git by PR.
 */
import * as React from "react";
import { href, formatDate, MODE_LABELS, type BacklogRow } from "../lib/tracker";

const ALWAYS_SHOWN = ["intake", "discover", "design", "build", "verify", "ship", "operate", "improve"];

interface PhaseBoardProps {
  phases: string[];
  rows: BacklogRow[];
}

function GateBadge({ gate }: { gate: string }) {
  if (!gate || gate === "none") return null;
  return (
    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-900" title="open gate">
      {gate}
    </span>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  return (
    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700" title="mode badge">
      {MODE_LABELS[mode] ?? mode}
    </span>
  );
}

function StoryCard({ row }: { row: BacklogRow }) {
  return (
    <li>
      <a
        href={href(`/story/${encodeURIComponent(row.story_key)}`)}
        className="block rounded-md border border-slate-200 bg-white p-2 shadow-sm hover:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400"
      >
        <div className="flex items-start justify-between gap-2">
          <span className="font-mono text-[11px] text-slate-500">{row.story_key}</span>
          <GateBadge gate={row.open_gate} />
        </div>
        <div className="mt-1 text-sm font-medium leading-snug text-slate-900">{row.title || row.story_key}</div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-600">
          <ModeBadge mode={row.mode} />
          <span title="owner (a role)">{row.owner || "unassigned"}</span>
          <span aria-hidden="true">·</span>
          <span title="target date (UTC)">{formatDate(row.target_date)}</span>
          {row.status && row.status !== "active" ? (
            <span className="rounded bg-violet-100 px-1.5 py-0.5 text-violet-900" title="status">
              {row.status}
            </span>
          ) : null}
          {row.pending_repo_sync ? (
            <span
              className="rounded bg-sky-100 px-1.5 py-0.5 text-sky-900"
              title="A Tines-side change is waiting for its tracker PR to merge; it is provisional until then."
            >
              provisional
            </span>
          ) : null}
        </div>
      </a>
    </li>
  );
}

export function PhaseBoard({ phases, rows }: PhaseBoardProps) {
  const grouped = React.useMemo(() => {
    const map = new Map<string, BacklogRow[]>();
    for (const phase of phases) map.set(phase, []);
    for (const row of rows) {
      if (!map.has(row.phase)) map.set(row.phase, []);
      map.get(row.phase)?.push(row);
    }
    for (const list of map.values()) list.sort((a, b) => a.story_key.localeCompare(b.story_key));
    return map;
  }, [phases, rows]);

  const columns = Array.from(grouped.keys()).filter(
    (phase) => ALWAYS_SHOWN.includes(phase) || (grouped.get(phase)?.length ?? 0) > 0,
  );

  return (
    <div className="flex gap-3 overflow-x-auto pb-2" role="list" aria-label="Stories by phase">
      {columns.map((phase) => {
        const list = grouped.get(phase) ?? [];
        return (
          <section key={phase} role="listitem" className="w-64 shrink-0 rounded-lg bg-slate-50 p-2" aria-label={phase}>
            <header className="mb-2 flex items-center justify-between px-1">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">{phase}</h3>
              <span className="rounded-full bg-white px-2 text-xs text-slate-500">{list.length}</span>
            </header>
            {list.length === 0 ? (
              <p className="px-1 text-xs text-slate-400">—</p>
            ) : (
              <ul className="space-y-2">
                {list.map((row) => (
                  <StoryCard key={row.story_key} row={row} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

export default PhaseBoard;
