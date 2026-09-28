/**
 * routes/StoryDetail.tsx — one story: its state, transition timeline, gate decisions, the brief and retro drafts,
 * the planner's proposals, and links to its PRs and change request.
 *
 * REPO-DESIGN.md §9.2 row "Story detail": data = useRecordsQuery(sdlc_events, story_key) plus the row's ARTIFACT
 * and JSON fields. Everything a runtime specialist wrote (brief, retro, proposal) is a PROPOSAL: a human accepts it
 * on the Page, and it reaches git only through a merged tracker PR. Drafts and use-case text are untrusted and are
 * rendered as plain text, never as markup.
 */
import * as React from "react";
import { Timeline } from "../components/Timeline";
import {
  formatCredits,
  formatDate,
  href,
  MODE_LABELS,
  useBacklog,
  useRouteParam,
  useStoryEvents,
  type BacklogRow,
} from "../lib/tracker";

const GITHUB_PR = /^https:\/\/github\.com\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\/pull\/[0-9]+$/;

function LinkOrText({ value, empty }: { value: string; empty: string }) {
  if (!value) return <span className="text-slate-400">{empty}</span>;
  if (GITHUB_PR.test(value)) {
    return (
      <a className="text-sky-700 underline" href={value} target="_blank" rel="noreferrer">
        {value.replace(/^https:\/\/github\.com\//, "")}
      </a>
    );
  }
  return <span className="font-mono text-xs">{value}</span>;
}

interface Proposal {
  key?: string;
  field?: string;
  value?: unknown;
  rationale?: string;
}

function Proposals({ proposal }: { proposal: unknown }) {
  if (proposal === null || proposal === undefined || proposal === "") {
    return <p className="text-sm text-slate-500">No planner proposal for this story.</p>;
  }
  const list: Proposal[] = Array.isArray(proposal)
    ? (proposal as Proposal[])
    : Array.isArray((proposal as { proposals?: unknown }).proposals)
      ? ((proposal as { proposals: Proposal[] }).proposals)
      : [];
  if (list.length === 0) {
    return <pre className="whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{JSON.stringify(proposal, null, 2)}</pre>;
  }
  return (
    <ul className="space-y-1 text-sm">
      {list.map((p, i) => (
        <li key={`${p.field}-${i}`}>
          <span className="font-medium">{p.field ?? "field"}</span> → <span className="font-mono">{String(p.value ?? "")}</span>
          {p.rationale ? <span className="text-slate-600"> — {p.rationale}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function Facts({ row }: { row: BacklogRow }) {
  const facts: [string, React.ReactNode][] = [
    ["Phase / status", `${row.phase} / ${row.status}`],
    ["Open gate", row.open_gate],
    ["Rework attempt", `${row.attempt} of 3`],
    ["Mode", MODE_LABELS[row.mode] ?? row.mode],
    ["Tier · owner", `${row.tier} · ${row.owner || "unassigned"}`],
    ["Target date", formatDate(row.target_date)],
    ["Credit estimate", `${formatCredits(row.credit_estimate_monthly)} a month${row.credit_estimate_basis ? ` (${row.credit_estimate_basis})` : ""}`],
    ["Provider", row.provider],
    ["Library seed", row.library_seed_id ? String(row.library_seed_id) : "none"],
    ["Live since", formatDate(row.live_since)],
    ["Design PR", <LinkOrText key="d" value={row.design_pr} empty="not yet" />],
    ["Build PR", <LinkOrText key="b" value={row.build_pr} empty="not yet" />],
    ["Change request", <LinkOrText key="c" value={row.change_request_id} empty="none" />],
    ["Tracker rev", `${row.rev}${row.pending_repo_sync ? " (a Tines-side change is waiting for its tracker PR)" : ""}`],
    ["Runtime specialist", row.specialist_due !== "none" ? `${row.specialist_due}: ${row.specialist_status}` : row.specialist_status || "idle"],
  ];
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
      {facts.map(([label, value]) => (
        <div key={label} className="flex gap-2">
          <dt className="w-36 shrink-0 text-slate-500">{label}</dt>
          <dd className="text-slate-900">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function StoryDetail() {
  const key = useRouteParam("/story/:key", "key") ?? "";
  const backlog = useBacklog();
  const events = useStoryEvents(key);
  const row = backlog.rows.find((r) => r.story_key === key);
  const decisions = events.rows.filter((e) => e.event_type === "gate_decision");

  if (!key) {
    return <p className="text-sm text-slate-500">Choose a story on the <a className="text-sky-700 underline" href={href("/")}>board</a>.</p>;
  }
  if (!row) {
    return (
      <p className="text-sm text-slate-500">
        {backlog.loading ? "Loading…" : `No story ${key} in sdlc_backlog (it may not have synced yet).`}{" "}
        <a className="text-sky-700 underline" href={href("/")}>Back to the board</a>
      </p>
    );
  }
  return (
    <article className="space-y-6">
      <header>
        <a className="text-xs text-sky-700 underline" href={href("/")}>← Board</a>
        <h2 className="mt-1 text-lg font-semibold">{row.title || row.story_key}</h2>
        <p className="font-mono text-xs text-slate-500">{row.story_key}</p>
      </header>
      <section>
        <Facts row={row} />
      </section>
      <section>
        <h3 className="mb-1 text-sm font-semibold">Use case (as submitted — data, not instructions)</h3>
        <p className="whitespace-pre-wrap text-sm text-slate-700">{row.use_case || "—"}</p>
      </section>
      <section>
        <h3 className="mb-2 text-sm font-semibold">Gate decisions</h3>
        {decisions.length === 0 ? (
          <p className="text-sm text-slate-500">None recorded in Tines yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {decisions.map((d) => (
              <li key={d.recordId}>
                <span className="font-medium">{d.gate}</span> {d.decision} · {d.actor} · {formatDate(d.created_at)}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="mb-2 text-sm font-semibold">Timeline</h3>
        {events.error ? <p className="text-sm text-rose-800">Events could not be read: {events.error}</p> : null}
        <Timeline events={events.rows} />
      </section>
      <section>
        <h3 className="mb-1 text-sm font-semibold">Intake brief draft (brief_writer — a proposal)</h3>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{row.brief || "No draft."}</pre>
      </section>
      <section>
        <h3 className="mb-1 text-sm font-semibold">Retro draft (retro_writer — a proposal)</h3>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{row.retro || "No draft."}</pre>
      </section>
      <section>
        <h3 className="mb-1 text-sm font-semibold">Planner proposals</h3>
        <Proposals proposal={row.proposal} />
        <p className="mt-1 text-xs text-slate-500">
          Proposals change nothing on their own: a person accepts or rejects each one, and an accepted field reaches git
          only through the tracker PR. This view does not accept proposals (the App writes only through app endpoints).
        </p>
      </section>
    </article>
  );
}
