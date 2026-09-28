/**
 * lib/tracker.ts — the ONLY file in the App that touches `@tines/apps`.
 *
 * REPO-DESIGN.md §9.2. The App is React 19 + Tailwind in a sandboxed iframe, with App.tsx as the entry and routes
 * through TinesRouter. It reads Records and Resources DIRECTLY through the read-only `@tines/apps` hooks —
 * `useRecords` (20 per page by default, 500 max), `useRecordsQuery` (up to 1,000 rows per query), `useResource`
 * (and `useCase`, unused here) — which run AS THE VIEWER, with the viewer's own permissions. Writes and external
 * calls go only through app endpoints (a Webhook entry + a message-only Event Transform exit in [KIT] 00 section C;
 * see ../endpoints.md). Sandbox: no network calls from app code, no localStorage or cookies, no
 * crypto.randomUUID, no embedding outside Tines, no anonymous access.
 *
 * VERIFY K18. The design's sources name the hooks and TinesRouter; they do not give their argument or result
 * shapes, whether nested file paths are accepted, or the primitive an App uses to call an app endpoint. Every
 * line below that assumes one of those is marked "VERIFY K18". When K18 is resolved, change ONLY this file: the
 * routes and components receive plain typed rows (BacklogRow, EventRow, MilestoneRow) and never see a platform
 * object. Record fields are read by the names in kit/records/*.record-type.json (kit/tracker/field-map.yaml).
 */
import * as React from "react";
import * as TinesApps from "@tines/apps"; // VERIFY K18: the package name and its exports, as REPO-DESIGN.md §9.2 names them
import { useRecords, useRecordsQuery, useResource } from "@tines/apps"; // VERIFY K18: argument and result shapes

// ─── Record types, Resources and Pages the App reads ────────────────────────────────────────────────────────────

export const RECORD_TYPES = {
  backlog: "sdlc_backlog",
  events: "sdlc_events",
  milestones: "sdlc_milestones",
} as const;

export const RESOURCES = {
  stateMachine: "sdlc_state_machine",
  catalog: "kit_catalog",
  config: "kit_config",
} as const;

/** The tracker_home root Page's URL identifier (stories/kit-factory/pages/tracker-home.md). Mid-story Pages
 * (gate_decision, add_use_case) have per-run URLs, so the App links to this root Page instead. Whether the
 * identifier survives story import is VERIFY K8. */
export const TRACKER_HOME_PAGE = "story-factory-tracker";

export const TINES_SIDE_GATES = ["G0", "G6", "G7", "GX"] as const; // decided on the gate_decision Page (§7.8)

// ─── Plain row types ─────────────────────────────────────────────────────────────────────────────────────────────

export interface BacklogRow {
  recordId: string;
  story_key: string;
  title: string;
  use_case: string;
  library_seed_id: number | null;
  mode: string;
  owner: string;
  tier: string;
  phase: string;
  status: string;
  open_gate: string;
  attempt: number;
  target_date: string | null;
  credit_estimate_monthly: number | null;
  credit_estimate_basis: string;
  provider: string;
  prod_story_id: number | null;
  live_since: string | null;
  design_pr: string;
  build_pr: string;
  change_request_id: string;
  rev: number;
  pending_repo_sync: boolean;
  specialist_due: string;
  specialist_status: string;
  proposal: unknown;
  brief: string;
  retro: string;
  last_actor: string;
  last_transition_at: string | null;
}

export interface EventRow {
  recordId: string;
  created_at: string | null;
  story_key: string;
  event_type: string;
  from_phase: string;
  to_phase: string;
  gate: string;
  decision: string;
  actor: string; // a role; actor_ref (the approver's email) is never rendered
  actor_kind: string;
  agent: string;
  model: string;
  credits_used: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  summary: string;
  ref: string;
  tracker_rev: number | null;
}

export interface MilestoneRow {
  recordId: string;
  milestone_id: string;
  title: string;
  criteria: string[];
  status: string;
  due_date: string | null;
  evidence_ref: string;
  owner: string;
  pending_repo_sync: boolean;
}

/** The parts of the sdlc_state_machine Resource the App reads (kit/resources/sdlc_state_machine.example.json). */
export interface StateMachine {
  phases: string[];
  all_phases: string[];
  gates: string[];
  gate_decided_by: Record<string, string>;
  gate_types: Record<string, string>;
  page_gates: string[];
  enums: Record<string, string[]>;
}

/** The parts of the kit_config Resource the App reads (kit/resources/kit_config.example.json). */
export interface KitConfig {
  tenant_host?: string;
  entitlements?: Record<string, boolean>;
  llm?: { choice?: string; provider_name?: string };
}

/** The parts of the kit_catalog Resource the App reads (kit/resources/kit_catalog.example.json). */
export interface KitCatalog {
  library_seeds: { id: number; name: string; reference_only: boolean }[];
}

export interface Loaded<T> {
  rows: T[];
  loading: boolean;
  error: string | null;
}

export interface LoadedValue<T> {
  value: T | null;
  loading: boolean;
  error: string | null;
}

// ─── Coercion helpers (Records return TEXT/NUMBER/TIMESTAMP/BOOLEAN/TEXT_ENUM/JSON/ARTIFACT values) ────────────

const str = (v: unknown): string => (v === null || v === undefined ? "" : String(v));
const num = (v: unknown): number | null => {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
};
const bool = (v: unknown): boolean => v === true || v === "true";
const ts = (v: unknown): string | null => (v ? String(v) : null);
const enumValue = (v: unknown): string => (v === null || v === undefined || v === "" ? "none" : String(v));

/**
 * VERIFY K18: the shape of one record as the hooks return it. Accepted, in order: a map under `fields`, a map
 * under `field_values`, an array of `{ name, value }` under either key, or the field names at the top level.
 */
function fieldsOf(record: unknown): Record<string, unknown> {
  if (!record || typeof record !== "object") return {};
  const r = record as Record<string, unknown>;
  for (const key of ["fields", "field_values", "values"]) {
    const inner = r[key];
    if (Array.isArray(inner)) {
      const out: Record<string, unknown> = {};
      for (const item of inner) {
        if (item && typeof item === "object") {
          const entry = item as Record<string, unknown>;
          const name = str(entry.name ?? entry.field_name ?? entry.key);
          if (name) out[name] = entry.value;
        }
      }
      return { ...r, ...out };
    }
    if (inner && typeof inner === "object") return { ...r, ...(inner as Record<string, unknown>) };
  }
  return r;
}

const recordIdOf = (f: Record<string, unknown>, index: number): string => str(f.id ?? f.record_id ?? f.story_key ?? index);

/** VERIFY K18: the hook result. Accepted: an array, or an object carrying the rows under records / data / rows. */
function resultRows(result: unknown): unknown[] {
  if (Array.isArray(result)) return result;
  if (result && typeof result === "object") {
    const r = result as Record<string, unknown>;
    for (const key of ["records", "data", "rows", "items"]) {
      if (Array.isArray(r[key])) return r[key] as unknown[];
    }
  }
  return [];
}

function resultState(result: unknown): { loading: boolean; error: string | null } {
  if (!result || typeof result !== "object" || Array.isArray(result)) return { loading: false, error: null };
  const r = result as Record<string, unknown>;
  const loading = Boolean(r.isLoading ?? r.loading ?? false);
  const err = r.error;
  return { loading, error: err ? str((err as { message?: unknown }).message ?? err) : null };
}

/** VERIFY K18: a Resource hook result. Accepted: `{ value }`, `{ data }`, or the value itself. */
function resourceValue<T>(result: unknown): T | null {
  if (result === null || result === undefined) return null;
  if (typeof result === "object" && !Array.isArray(result)) {
    const r = result as Record<string, unknown>;
    if ("value" in r) return (typeof r.value === "string" ? safeJson(r.value) : r.value) as T;
    if ("data" in r) return r.data as T;
  }
  return (typeof result === "string" ? safeJson(result) : result) as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function toBacklogRow(record: unknown, index: number): BacklogRow {
  const f = fieldsOf(record);
  return {
    recordId: recordIdOf(f, index),
    story_key: str(f.story_key),
    title: str(f.title),
    use_case: str(f.use_case),
    library_seed_id: num(f.library_seed_id),
    mode: enumValue(f.mode),
    owner: str(f.owner),
    tier: str(f.tier),
    phase: str(f.phase),
    status: str(f.status),
    open_gate: enumValue(f.open_gate),
    attempt: num(f.attempt) ?? 0,
    target_date: ts(f.target_date),
    credit_estimate_monthly: num(f.credit_estimate_monthly),
    credit_estimate_basis: str(f.credit_estimate_basis),
    provider: enumValue(f.provider),
    prod_story_id: num(f.prod_story_id),
    live_since: ts(f.live_since),
    design_pr: str(f.design_pr),
    build_pr: str(f.build_pr),
    change_request_id: str(f.change_request_id),
    rev: num(f.rev) ?? 0,
    pending_repo_sync: bool(f.pending_repo_sync),
    specialist_due: enumValue(f.specialist_due),
    specialist_status: str(f.specialist_status),
    proposal: typeof f.proposal === "string" ? safeJson(f.proposal) : f.proposal ?? null,
    brief: str(f.brief),
    retro: str(f.retro),
    last_actor: str(f.last_actor),
    last_transition_at: ts(f.last_transition_at),
  };
}

function toEventRow(record: unknown, index: number): EventRow {
  const f = fieldsOf(record);
  return {
    recordId: recordIdOf(f, index),
    created_at: ts(f.created_at ?? f.CREATED_AT ?? f.createdAt), // VERIFY K18: the name of the creation-time column
    story_key: str(f.story_key),
    event_type: str(f.event_type),
    from_phase: enumValue(f.from_phase),
    to_phase: enumValue(f.to_phase),
    gate: enumValue(f.gate),
    decision: str(f.decision),
    actor: str(f.actor),
    actor_kind: str(f.actor_kind),
    agent: str(f.agent),
    model: str(f.model),
    credits_used: num(f.credits_used),
    input_tokens: num(f.input_tokens),
    output_tokens: num(f.output_tokens),
    summary: str(f.summary),
    ref: str(f.ref),
    tracker_rev: num(f.tracker_rev),
  };
}

function toMilestoneRow(record: unknown, index: number): MilestoneRow {
  const f = fieldsOf(record);
  return {
    recordId: recordIdOf(f, index),
    milestone_id: str(f.milestone_id),
    title: str(f.title),
    criteria: str(f.criteria)
      .split("\n")
      .map((line) => line.replace(/^\s*[-*]\s+/, "").trim())
      .filter(Boolean),
    status: str(f.status),
    due_date: ts(f.due_date),
    evidence_ref: str(f.evidence_ref),
    owner: str(f.owner),
    pending_repo_sync: bool(f.pending_repo_sync),
  };
}

// ─── The hooks the routes use ────────────────────────────────────────────────────────────────────────────────────

/** VERIFY K18: how a record type is addressed (by name here; if the hooks take an id, read it from the kit_state
 * Resource's rt_<type> key, which [KIT] 00 A18 writes) and the page-size option's name. */
const recordsArgs = (recordType: string) => ({ recordType, perPage: 500 });

export function useBacklog(): Loaded<BacklogRow> {
  const result: unknown = (useRecords as (args: unknown) => unknown)(recordsArgs(RECORD_TYPES.backlog)); // VERIFY K18
  return React.useMemo(
    () => ({ rows: resultRows(result).map(toBacklogRow).filter((r) => r.story_key), ...resultState(result) }),
    [result],
  );
}

export function useMilestones(): Loaded<MilestoneRow> {
  const result: unknown = (useRecords as (args: unknown) => unknown)(recordsArgs(RECORD_TYPES.milestones)); // VERIFY K18
  return React.useMemo(() => {
    const order = ["day-1", "week-1", "week-4"];
    const rows = resultRows(result)
      .map(toMilestoneRow)
      .sort((a, b) => order.indexOf(a.milestone_id) - order.indexOf(b.milestone_id));
    return { rows, ...resultState(result) };
  }, [result]);
}

/** One story's events. The query is server-side where useRecordsQuery supports the filter; the rows are also
 * filtered here, so a query shape that K18 corrects cannot show another story's events. */
export function useStoryEvents(storyKey: string): Loaded<EventRow> {
  const result: unknown = (useRecordsQuery as (args: unknown) => unknown)({
    // VERIFY K18: the query shape (record type, a field filter, the 1,000-row limit)
    recordType: RECORD_TYPES.events,
    filters: [{ field: "story_key", value: storyKey }],
    limit: 1000,
  });
  return React.useMemo(() => {
    const rows = resultRows(result)
      .map(toEventRow)
      .filter((e) => e.story_key === storyKey)
      .sort((a, b) => str(a.created_at).localeCompare(str(b.created_at)));
    return { rows, ...resultState(result) };
  }, [result, storyKey]);
}

function useJsonResource<T>(name: string): LoadedValue<T> {
  const result: unknown = (useResource as (name: unknown) => unknown)(name); // VERIFY K18: addressed by name
  return React.useMemo(() => ({ value: resourceValue<T>(result), ...resultState(result) }), [result]);
}

export const useStateMachine = () => useJsonResource<StateMachine>(RESOURCES.stateMachine);
export const useKitConfig = () => useJsonResource<KitConfig>(RESOURCES.config);
export const useCatalog = () => useJsonResource<KitCatalog>(RESOURCES.catalog);

/** The phases in board order: the state machine's own list, else the tracker's fixed order. */
export function phaseOrder(sm: StateMachine | null): string[] {
  return sm?.all_phases?.length
    ? sm.all_phases
    : ["intake", "discover", "design", "build", "verify", "ship", "operate", "improve", "parked", "rejected", "retired"];
}

/** https://<tenant>/pages/<identifier>, from the in-tenant kit_config.tenant_host; null when unknown. */
export function pageLink(config: KitConfig | null, identifier: string = TRACKER_HOME_PAGE): string | null {
  const host = config?.tenant_host ?? "";
  if (!/^[a-z0-9-]+\.tines\.com$/.test(host)) return null;
  return `https://${host}/pages/${identifier}`;
}

// ─── App endpoints (writes and external calls) ──────────────────────────────────────────────────────────────────

export type AppEndpoint = "app_add_use_case" | "app_gate_decision" | "app_costs";

export interface EndpointResult<T = unknown> {
  ok: boolean;
  data: T | null;
  message: string;
}

/**
 * Call one of the three app endpoints (../endpoints.md). VERIFY K18: the primitive an App uses to call an app
 * endpoint is not in the kit's sources, so v1 looks for no function by guessing a name; it reports "not wired"
 * and every caller falls back to a Page. Wire the documented primitive here once K18 confirms it — the callers'
 * contract (`EndpointResult`) stays the same.
 */
export async function callAppEndpoint<T = unknown>(name: AppEndpoint, body: Record<string, unknown>): Promise<EndpointResult<T>> {
  void TinesApps;
  void body;
  return {
    ok: false,
    data: null,
    message: `The app endpoint ${name} is not wired in this App yet (VERIFY K18). Use the tracker Page instead.`,
  };
}

export interface CostActual {
  story_key: string; // optional in the endpoint's answer: "" when it did not map the story id to a tracker key
  story_id: number | null;
  credits_used: number | null;
  billed_cost: number | null;
}

/** Credits used month to date per story, through app_costs (GET /api/v1/ai_usage with start_date = the 1st,
 * end_date = today and group_by=story, using the tines_api_readonly key — it sees only what that key may see, K38).
 * Empty with a message until the endpoint call is wired (K18). */
export function useCostActuals(): Loaded<CostActual> & { message: string } {
  const [state, setState] = React.useState<Loaded<CostActual> & { message: string }>({
    rows: [],
    loading: true,
    error: null,
    message: "",
  });
  React.useEffect(() => {
    let live = true;
    callAppEndpoint<{ rows?: CostActual[] }>("app_costs", { period: "month_to_date", group_by: "story" }).then((res) => {
      if (!live) return;
      setState({ rows: res.ok ? res.data?.rows ?? [] : [], loading: false, error: null, message: res.message });
    });
    return () => {
      live = false;
    };
  }, []);
  return state;
}

// ─── Routing ─────────────────────────────────────────────────────────────────────────────────────────────────────

export interface RouteDef {
  path: string; // "/", "/story/:key", "/gates", "/milestones", "/costs"
  title: string;
  element: React.ReactNode;
  inNav: boolean;
}

/**
 * "tines" routes through TinesRouter (REPO-DESIGN.md §9.2). VERIFY K18: its props are assumed to be a
 * `routes` array of `{ path, element }`, and in-app links are assumed to be hash links. If K18 shows otherwise,
 * set ROUTER_MODE to "hash" — the built-in switch below uses only standard DOM APIs — and adjust `href`.
 */
export const ROUTER_MODE: "tines" | "hash" = "tines";

type RouterComponent = React.ComponentType<{ routes: { path: string; element: React.ReactNode }[] }>;

export function AppRouter({ routes }: { routes: RouteDef[] }): React.ReactElement {
  const tinesRouter = (TinesApps as unknown as Record<string, unknown>)["TinesRouter"] as RouterComponent | undefined;
  const path = useRoutePath();
  if (ROUTER_MODE === "tines" && tinesRouter) {
    // VERIFY K18: TinesRouter's props (a routes array of { path, element } is assumed). This file is .ts, so no JSX.
    return React.createElement(tinesRouter, { routes: routes.map(({ path: p, element }) => ({ path: p, element })) });
  }
  const match = routes.find((r) => matchPath(r.path, path) !== null) ?? routes[0];
  return React.createElement(React.Fragment, null, match.element);
}

/** An in-app link target. VERIFY K18: hash links assumed for both modes. */
export function href(path: string): string {
  return `#${path.startsWith("/") ? path : `/${path}`}`;
}

function currentPath(): string {
  const hash = typeof window !== "undefined" ? window.location.hash : "";
  if (hash.startsWith("#/")) return decodeURIComponent(hash.slice(1));
  const pathname = typeof window !== "undefined" ? window.location.pathname : "/";
  return pathname || "/";
}

export function useRoutePath(): string {
  const [path, setPath] = React.useState<string>(currentPath());
  React.useEffect(() => {
    const onChange = () => setPath(currentPath());
    window.addEventListener("hashchange", onChange);
    window.addEventListener("popstate", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
      window.removeEventListener("popstate", onChange);
    };
  }, []);
  return path;
}

function matchPath(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split("/").filter(Boolean);
  const a = path.split("?")[0].split("/").filter(Boolean);
  if (p.length !== a.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i += 1) {
    if (p[i].startsWith(":")) params[p[i].slice(1)] = a[i];
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

/** A route parameter (e.g. "key" in /story/:key) from the current location. VERIFY K18 in "tines" mode. */
export function useRouteParam(pattern: string, name: string): string | null {
  const path = useRoutePath();
  return matchPath(pattern, path)?.[name] ?? null;
}

// ─── Formatting shared by the routes ─────────────────────────────────────────────────────────────────────────────

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export function formatCredits(value: number | null): string {
  if (value === null) return "set at design";
  return `${Math.round(value).toLocaleString()} cr`;
}

export const MODE_LABELS: Record<string, string> = {
  none: "none",
  "sub-story": "sub-story",
  "mode-1-preset": "Mode 1",
  "mode-3-agent": "Mode 3",
  "mode-4-server": "Mode 4",
};
