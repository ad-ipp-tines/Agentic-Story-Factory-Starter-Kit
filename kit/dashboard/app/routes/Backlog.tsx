/**
 * routes/Backlog.tsx — the board: one column per phase, filters by owner, tier and mode, and the intake form.
 *
 * REPO-DESIGN.md §9.2 row "Backlog": data = useRecords(storyline_backlog); phase names from
 * useResource(storyline_state_machine). Adding a use case is a write, so it goes through the app_add_use_case endpoint
 * (../endpoints.md), which runs the same chain as the add_use_case Page (C4). Until the App's endpoint call is
 * wired (VERIFY K18), the form says so and links to the tracker Page, where "Add a use case" does the same thing.
 * A new row is provisional until its tracker PR merges (Flow 2).
 */
import * as React from "react";
import { PhaseBoard } from "../components/PhaseBoard";
import {
  callAppEndpoint,
  MODE_LABELS,
  pageLink,
  phaseOrder,
  useBacklog,
  useCatalog,
  useKitConfig,
  useStateMachine,
  type KitCatalog,
  type KitConfig,
} from "../lib/tracker";

const ALL = "all";
const MODE_HINTS = ["none", "sub-story", "mode-1-preset", "mode-3-agent", "mode-4-server", "unknown"];
const TOKEN_LIKE = /(ghp_|github_pat_|gho_|ghs_|xox[bp]-|sk-|AKIA|Bearer\s)/;

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col text-xs text-slate-600">
      {label}
      <select
        className="mt-1 rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value={ALL}>all</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {MODE_LABELS[o] && label === "Mode" ? MODE_LABELS[o] : o}
          </option>
        ))}
      </select>
    </label>
  );
}

function AddUseCase({ config, catalog }: { config: KitConfig | null; catalog: KitCatalog | null }) {
  const [open, setOpen] = React.useState(false);
  const [title, setTitle] = React.useState("");
  const [useCase, setUseCase] = React.useState("");
  const [owner, setOwner] = React.useState("");
  const [targetDate, setTargetDate] = React.useState("");
  const [seed, setSeed] = React.useState("none");
  const [modeHint, setModeHint] = React.useState("unknown");
  const [message, setMessage] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const trackerPage = pageLink(config);

  const problems: string[] = [];
  if (!title.trim()) problems.push("a title");
  if (!useCase.trim()) problems.push("the use case");
  if (!owner.trim() || owner.includes("@")) problems.push("an owner role (a role, never a person or an email)");
  const tokenLike = TOKEN_LIKE.test(`${title} ${useCase} ${owner}`);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (problems.length || tokenLike) return;
    setBusy(true);
    const result = await callAppEndpoint("app_add_use_case", {
      title: title.trim(),
      use_case: useCase.trim(),
      owner_role: owner.trim(),
      target_date: targetDate ? `${targetDate}T00:00:00Z` : "",
      library_seed_id: seed === "none" ? null : Number(seed),
      mode_hint: modeHint,
    });
    setBusy(false);
    setMessage(
      result.ok
        ? "Added in intake. The brief writer drafts the intake brief, and the row reaches git with the next tracker PR."
        : result.message,
    );
  }

  return (
    <section className="mt-6 rounded-lg border border-slate-200 p-3">
      <button
        type="button"
        className="text-sm font-medium text-sky-700 hover:underline"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? "Hide" : "Add a use case"}
      </button>
      {open ? (
        <form className="mt-3 grid gap-3 md:grid-cols-2" onSubmit={submit}>
          <label className="flex flex-col text-xs text-slate-600">
            Title
            <input className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm" value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Owner role
            <input className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm" value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="security-automation" />
          </label>
          <label className="flex flex-col text-xs text-slate-600 md:col-span-2">
            Use case (what happens today, what should happen)
            <textarea className="mt-1 h-24 rounded border border-slate-300 px-2 py-1 text-sm" value={useCase} onChange={(e) => setUseCase(e.target.value)} />
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Target date (UTC)
            <input type="date" className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Library seed (verified catalog ids only)
            <select className="mt-1 rounded border border-slate-300 bg-white px-2 py-1 text-sm" value={seed} onChange={(e) => setSeed(e.target.value)}>
              <option value="none">none</option>
              {(catalog?.library_seeds ?? [])
                .filter((s) => !s.reference_only)
                .map((s) => (
                  <option key={s.id} value={String(s.id)}>
                    {s.id} · {s.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-600">
            Mode hint
            <select className="mt-1 rounded border border-slate-300 bg-white px-2 py-1 text-sm" value={modeHint} onChange={(e) => setModeHint(e.target.value)}>
              {MODE_HINTS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-col justify-end gap-1 text-xs text-slate-600 md:col-span-2">
            {tokenLike ? (
              <p className="text-rose-700">That looks like a token. Never paste a token, key or password here.</p>
            ) : null}
            {problems.length ? <p>Still needed: {problems.join(", ")}.</p> : null}
            <button
              type="submit"
              disabled={busy || problems.length > 0 || tokenLike}
              className="w-fit rounded bg-sky-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            >
              {busy ? "Adding…" : "Add in intake"}
            </button>
            {message ? (
              <p className="text-slate-700">
                {message}{" "}
                {trackerPage ? (
                  <a className="text-sky-700 underline" href={trackerPage} target="_blank" rel="noreferrer">
                    Open the tracker Page → Add a use case
                  </a>
                ) : null}
              </p>
            ) : null}
          </div>
        </form>
      ) : null}
    </section>
  );
}

export default function Backlog() {
  const backlog = useBacklog();
  const sm = useStateMachine();
  const config = useKitConfig();
  const catalog = useCatalog();
  const [owner, setOwner] = React.useState(ALL);
  const [tier, setTier] = React.useState(ALL);
  const [mode, setMode] = React.useState(ALL);

  const unique = (values: string[]) => Array.from(new Set(values.filter(Boolean))).sort();
  const owners = unique(backlog.rows.map((r) => r.owner));
  const tiers = unique(backlog.rows.map((r) => r.tier));
  const modes = sm.value?.enums?.mode ?? unique(backlog.rows.map((r) => r.mode));
  const rows = backlog.rows.filter(
    (r) => (owner === ALL || r.owner === owner) && (tier === ALL || r.tier === tier) && (mode === ALL || r.mode === mode),
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <h2 className="mr-auto text-lg font-semibold">Backlog</h2>
        <Select label="Owner" value={owner} options={owners} onChange={setOwner} />
        <Select label="Tier" value={tier} options={tiers} onChange={setTier} />
        <Select label="Mode" value={mode} options={modes} onChange={setMode} />
      </div>
      {backlog.error ? (
        <p className="mb-3 rounded bg-rose-50 p-2 text-sm text-rose-800">
          The backlog could not be read: {backlog.error}. The App reads as you; ask for access to the ops team, or
          open the tracker in git (kit/tracker/backlog.yaml).
        </p>
      ) : null}
      {backlog.loading ? <p className="text-sm text-slate-500">Loading the backlog…</p> : null}
      <PhaseBoard phases={phaseOrder(sm.value)} rows={rows} />
      <p className="mt-2 text-xs text-slate-500">
        {rows.length} of {backlog.rows.length} stories. Git is the system of record; this board is the Records
        projection, current as of the last tracker sync.
      </p>
      <AddUseCase config={config.value} catalog={catalog.value} />
    </div>
  );
}
