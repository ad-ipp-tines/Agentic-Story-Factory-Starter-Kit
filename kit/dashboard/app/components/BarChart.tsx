/**
 * components/BarChart.tsx — a grouped bar chart drawn as hand-written SVG.
 *
 * REPO-DESIGN.md §9.2: no chart dependency is assumed (which packages an App may use is VERIFY K18), so the Costs
 * route draws its own bars. Values are plain numbers; a null value is drawn as a hollow "n/a" marker rather than a
 * zero bar, so "not metered" is never mistaken for "free".
 */
import * as React from "react";

export interface BarSeries {
  key: string;
  label: string;
  /** Tailwind fill class for the bars, e.g. "fill-sky-600". */
  fillClass: string;
  /** Tailwind background class for the legend swatch, e.g. "bg-sky-600". */
  swatchClass: string;
}

export interface BarDatum {
  label: string;
  values: Record<string, number | null>;
}

interface BarChartProps {
  title: string;
  data: BarDatum[];
  series: BarSeries[];
  height?: number;
  format?: (value: number) => string;
  emptyText?: string;
}

const PLOT_TOP = 16;
const PLOT_LEFT = 56;
const LABEL_SPACE = 72;

function niceStep(raw: number): number {
  if (raw <= 0) return 1;
  const exponent = Math.floor(Math.log10(raw));
  const fraction = raw / 10 ** exponent;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return nice * 10 ** exponent;
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function BarChart({ title, data, series, height = 280, format = (v) => String(v), emptyText }: BarChartProps) {
  if (data.length === 0) {
    return <p className="text-sm text-slate-500">{emptyText ?? "Nothing to chart yet."}</p>;
  }
  const groupWidth = Math.max(36, series.length * 20 + 16);
  const width = Math.max(360, PLOT_LEFT + data.length * groupWidth + 16);
  const plotBottom = height - LABEL_SPACE;
  const plotHeight = plotBottom - PLOT_TOP;
  const maxValue = Math.max(
    0,
    ...data.flatMap((d) => series.map((s) => (typeof d.values[s.key] === "number" ? (d.values[s.key] as number) : 0))),
  );
  const step = niceStep(maxValue / 4 || 1);
  const top = Math.max(step, Math.ceil(maxValue / step) * step);
  const ticks: number[] = [];
  for (let t = 0; t <= top + step / 2; t += step) ticks.push(t);
  const y = (value: number) => plotBottom - (value / top) * plotHeight;
  const barWidth = Math.min(22, (groupWidth - 12) / series.length);

  return (
    <figure className="w-full">
      <div className="overflow-x-auto">
        <svg
          role="img"
          aria-label={title}
          viewBox={`0 0 ${width} ${height}`}
          width={width}
          height={height}
          className="max-w-none"
        >
          <title>{title}</title>
          {ticks.map((t) => (
            <g key={`tick-${t}`}>
              <line x1={PLOT_LEFT} x2={width - 8} y1={y(t)} y2={y(t)} className="stroke-slate-200" strokeWidth={1} />
              <text x={PLOT_LEFT - 6} y={y(t) + 3} textAnchor="end" className="fill-slate-500" fontSize={10}>
                {format(t)}
              </text>
            </g>
          ))}
          <line x1={PLOT_LEFT} x2={width - 8} y1={plotBottom} y2={plotBottom} className="stroke-slate-400" strokeWidth={1} />
          {data.map((d, i) => {
            const groupX = PLOT_LEFT + i * groupWidth + (groupWidth - barWidth * series.length) / 2;
            const labelX = groupX + (barWidth * series.length) / 2;
            return (
              <g key={`group-${d.label}-${i}`}>
                {series.map((s, j) => {
                  const value = d.values[s.key];
                  const x = groupX + j * barWidth;
                  if (typeof value !== "number") {
                    return (
                      <g key={s.key}>
                        <rect
                          x={x + 1}
                          y={plotBottom - 10}
                          width={barWidth - 2}
                          height={10}
                          className="fill-none stroke-slate-400"
                          strokeDasharray="2 2"
                        />
                        <title>{`${d.label} · ${s.label}: n/a`}</title>
                      </g>
                    );
                  }
                  const barHeight = Math.max(value > 0 ? 1 : 0, plotBottom - y(value));
                  return (
                    <rect
                      key={s.key}
                      x={x + 1}
                      y={plotBottom - barHeight}
                      width={barWidth - 2}
                      height={barHeight}
                      className={s.fillClass}
                    >
                      <title>{`${d.label} · ${s.label}: ${format(value)}`}</title>
                    </rect>
                  );
                })}
                <text
                  x={labelX}
                  y={plotBottom + 12}
                  textAnchor="end"
                  transform={`rotate(-35 ${labelX} ${plotBottom + 12})`}
                  className="fill-slate-600"
                  fontSize={10}
                >
                  {truncate(d.label, 24)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption className="mt-2 flex flex-wrap gap-4 text-xs text-slate-600">
        {series.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1">
            <span className={`inline-block h-3 w-3 rounded-sm ${s.swatchClass}`} aria-hidden="true" />
            {s.label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-sm border border-dashed border-slate-400" aria-hidden="true" />
          n/a (not metered, or not reported yet)
        </span>
      </figcaption>
    </figure>
  );
}

export default BarChart;
