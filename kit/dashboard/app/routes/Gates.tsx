/**
 * routes/Gates.tsx — every open gate, who decides it, and where.
 *
 * REPO-DESIGN.md §9.2 row "Gates": data = useRecords(storyline_backlog, open_gate ≠ none) — filtered here as well, so
 * the view is right whatever filter syntax the hook accepts (VERIFY K18). Each gate has ONE instrument (§4.5 rule 3):
 *   G0, G6, G7, GX and the GB release (unpark) → the gate_decision Page. "Decide" deep-links to the tracker Page
 *     ("Decide a gate") until K18 confirms that an app endpoint receives the viewer's identity; the Page checks the
 *     submitter's email against the storyline_approvers Resource on every decision.
 *   G1 → ./scripts/storyline ready on the design PR · G2 → the merge of the design PR · G3 → /storyline-gate in the build
 *   session · G4 → the merge of the build PR · G5a → the GitHub production environment's required reviewer ·
 *   G5b → the change request in Tines, approved and pushed by a named approver.
 */
import * as React from "react";
import {
  href,
  pageLink,
  TINES_SIDE_GATES,
  useBacklog,
  useKitConfig,
  useStateMachine,
  type BacklogRow,
  type KitConfig,
} from "../lib/tracker";

const INSTRUMENT: Record<string, string> = {
  G0: "the gate_decision Page",
  G1: "./scripts/storyline ready — the storyline check on the design PR",
  G2: "the merge of the design PR (a CODEOWNER who is not the author)",
  G3: "/storyline-gate <slug> G3 approve — in the build session",
  G4: "the merge of the build PR (CI green, QA verification line, a CODEOWNER, a human merge)",
  G5a: "the GitHub production environment's required reviewer releases ship.yml's first import",
  G5b: "the change request in Tines — a named approver approves and pushes",
  G6: "the gate_decision Page",
  G7: "the gate_decision Page",
  GB: "the gate_decision Page (unpark)",
  GX: "the gate_decision Page",
};

function Action({ row, config }: { row: BacklogRow; config: KitConfig | null }) {
  const gate = row.phase === "parked" && row.open_gate === "none" ? "GB" : row.open_gate;
  const trackerPage = pageLink(config);
  if ((TINES_SIDE_GATES as readonly string[]).includes(gate) || gate === "GB") {
    return trackerPage ? (
      <a
        className="rounded bg-sky-700 px-2 py-1 text-xs font-medium text-white hover:bg-sky-800"
        href={trackerPage}
        target="_blank"
        rel="noreferrer"
        title="Opens the tracker Page; choose Decide a gate. Your email is checked against the approvers list."
      >
        Decide on the tracker Page
      </a>
    ) : (
      <span className="text-xs text-slate-500">Open the tracker_home Page and choose Decide a gate</span>
    );
  }
  const pr = gate === "G2" ? row.design_pr : gate === "G4" ? row.build_pr : "";
  if (pr.startsWith("https://github.com/")) {
    return (
      <a className="text-xs text-sky-700 underline" href={pr} target="_blank" rel="noreferrer">
        Open the PR
      </a>
    );
  }
  if (gate === "G5b" && row.change_request_id) {
    return <span className="font-mono text-xs">change request {row.change_request_id}</span>;
  }
  return <span className="text-xs text-slate-500">decided outside the App</span>;
}

export default function Gates() {
  const backlog = useBacklog();
  const sm = useStateMachine();
  const config = useKitConfig();
  const open = backlog.rows.filter((r) => r.open_gate !== "none" || r.phase === "parked");
  const byGate = new Map<string, BacklogRow[]>();
  for (const row of open) {
    const gate = row.open_gate !== "none" ? row.open_gate : "GB";
    if (!byGate.has(gate)) byGate.set(gate, []);
    byGate.get(gate)?.push(row);
  }
  const order = sm.value?.gates ?? ["G0", "G1", "G2", "G3", "G4", "G5a", "G5b", "G6", "G7", "GB", "GX"];
  const gates = Array.from(byGate.keys()).sort((a, b) => order.indexOf(a) - order.indexOf(b));

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Open gates</h2>
      <p className="mb-4 text-sm text-slate-600">
        One open gate per story. Authority comes from versioned files and the approvers Resource, never from a chat
        reply. A decision made on the Page is provisional until its tracker PR merges.
      </p>
      {backlog.loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
      {gates.length === 0 && !backlog.loading ? <p className="text-sm text-slate-500">No gate is open.</p> : null}
      <div className="space-y-5">
        {gates.map((gate) => (
          <section key={gate}>
            <h3 className="text-sm font-semibold">
              {gate} <span className="font-normal text-slate-500">— decided by {sm.value?.gate_decided_by?.[gate] ?? "see storyline/gates/README.md"}</span>
            </h3>
            <p className="mb-2 text-xs text-slate-500">Instrument: {INSTRUMENT[gate] ?? "see storyline/gates/README.md"}</p>
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className="py-1 pr-3 font-medium">Story</th>
                  <th className="py-1 pr-3 font-medium">Phase / status</th>
                  <th className="py-1 pr-3 font-medium">Owner</th>
                  <th className="py-1 font-medium">Where to decide</th>
                </tr>
              </thead>
              <tbody>
                {(byGate.get(gate) ?? []).map((row) => (
                  <tr key={row.story_key} className="border-t border-slate-100">
                    <td className="py-1.5 pr-3">
                      <a className="text-sky-700 underline" href={href(`/story/${encodeURIComponent(row.story_key)}`)}>
                        {row.title || row.story_key}
                      </a>
                      {row.pending_repo_sync ? <span className="ml-2 text-xs text-sky-800">provisional</span> : null}
                    </td>
                    <td className="py-1.5 pr-3 text-slate-700">
                      {row.phase} / {row.status}
                    </td>
                    <td className="py-1.5 pr-3 text-slate-700">{row.owner || "unassigned"}</td>
                    <td className="py-1.5">
                      <Action row={row} config={config.value} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  );
}
