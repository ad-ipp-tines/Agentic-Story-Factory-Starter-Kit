/**
 * App.tsx — the entry file of the "Story factory" App (the name of this file cannot change).
 *
 * REPO-DESIGN.md §9.1–§9.2. Created by [KIT] 00 A24 (POST /api/v1/apps, then PUT /api/v1/apps/{id}/files with
 * kit/bundle/kit-bundle.json app_files — every draft file is replaced, and App.tsx must be present). Publishing the
 * App and wiring its three endpoints are [BY HAND] (Interfaces → App endpoints), or publishing through Mode 2,
 * whose App tools the MCP docs page does not list yet (VERIFY K18).
 *
 * What it is: the working surface over the tracker for tenants with Records + Apps. It reads sdlc_backlog,
 * sdlc_events and sdlc_milestones and the sdlc_state_machine, kit_catalog and kit_config Resources directly, as the
 * viewer (read-only hooks, lib/tracker.ts). It never writes a Record, runs on no schedule, shows nothing the viewer
 * may not read, and notifies nobody — the kit story does the notifying. Gate decisions deep-link to the tracker Page
 * until K18 confirms that an app endpoint receives the viewer's identity.
 *
 * Git is the system of record (kit/tracker/backlog.yaml); what this App shows is the Records projection as of the
 * last tracker sync. Files: routes/ (one per view), components/ (board, SVG bar chart, timeline), lib/tracker.ts
 * (the only file that touches @tines/apps). Whether nested paths are accepted in PUT …/files is VERIFY K18; if they
 * are not, flatten the tree and update the imports below.
 */
import * as React from "react";
import Backlog from "./routes/Backlog";
import Costs from "./routes/Costs";
import Gates from "./routes/Gates";
import Milestones from "./routes/Milestones";
import StoryDetail from "./routes/StoryDetail";
import { AppRouter, href, useRoutePath, type RouteDef } from "./lib/tracker";

const ROUTES: RouteDef[] = [
  { path: "/", title: "Backlog", element: <Backlog />, inNav: true },
  { path: "/story/:key", title: "Story", element: <StoryDetail />, inNav: false },
  { path: "/gates", title: "Gates", element: <Gates />, inNav: true },
  { path: "/milestones", title: "Milestones", element: <Milestones />, inNav: true },
  { path: "/costs", title: "Costs", element: <Costs />, inNav: true },
];

function Nav() {
  const path = useRoutePath();
  const active = (routePath: string) =>
    routePath === "/" ? path === "/" || path === "" || path.startsWith("/story/") : path.startsWith(routePath);
  return (
    <nav aria-label="Story factory" className="flex gap-1">
      {ROUTES.filter((r) => r.inNav).map((r) => (
        <a
          key={r.path}
          href={href(r.path)}
          aria-current={active(r.path) ? "page" : undefined}
          className={`rounded px-3 py-1.5 text-sm ${
            active(r.path) ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          {r.title}
        </a>
      ))}
    </nav>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="flex flex-wrap items-center gap-4 border-b border-slate-200 px-4 py-3">
        <h1 className="text-base font-semibold">Story factory</h1>
        <Nav />
      </header>
      <main className="px-4 py-4">
        <AppRouter routes={ROUTES} />
      </main>
      <footer className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
        Read-only, as you. Decisions happen at gates — the tracker Page, a PR merge, or a change request — and reach git
        by pull request. Git is the system of record.
      </footer>
    </div>
  );
}
