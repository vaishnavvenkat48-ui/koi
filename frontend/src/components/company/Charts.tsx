"use client";

import { AreaSeries, ColorType, createChart, LineStyle } from "lightweight-charts";
import { useEffect, useRef } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Json } from "@/lib/api";
import { byUnit, fy } from "@/lib/format";

// Axis ticks stay short: the unit (₹ crore) is named in the panel header, so ticks carry the number only.
function axisTick(v: number, unit: string): string {
  if (unit === "INR") {
    const cr = v / 1e7;
    return Math.abs(cr) >= 1e5 ? `${(cr / 1e5).toFixed(1)}L` : Math.abs(cr) >= 1000 ? `${Math.round(cr / 1000)}k` : `${Math.round(cr)}`;
  }
  if (unit === "pct") return `${Math.round(v * 100)}%`;
  if (unit === "x") return `${Number(v.toFixed(1))}x`;
  if (unit === "days") return `${Math.round(v)}d`;
  return String(v);
}

const AXIS = { stroke: "#8a8c92", fontSize: 12, tickLine: false, axisLine: false } as const;
const GRID = <CartesianGrid stroke="#222224" vertical={false} />;

function tip(unit: string) {
  return (
    <Tooltip
      cursor={{ fill: "#ffffff08" }}
      contentStyle={{ background: "#212023", border: "1px solid #3a3a3e", borderRadius: 6, fontSize: 12 }}
      labelStyle={{ color: "#8a8c92" }}
      formatter={(v) => [byUnit(Number(v), unit), ""]}
      separator=""
    />
  );
}

// Annual bars for a reported metric (e.g. revenue). Missing years are omitted, never zero-filled.
export function MetricBars({ points, unit, height = 160 }: { points: Json[]; unit: string; height?: number }) {
  const data = points.filter((p) => p.value !== null).map((p) => ({ name: fy(p.period), v: p.value }));
  if (data.length === 0) return <p className="text-[12px] text-ink-500">No data</p>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 4, left: 4, bottom: 0 }}>
        {GRID}
        <XAxis dataKey="name" {...AXIS} />
        <YAxis {...AXIS} width={64} tickFormatter={(v) => axisTick(v, unit)} />
        {tip(unit)}
        <ReferenceLine y={0} stroke="#3a3a3e" />
        <Bar dataKey="v" radius={[3, 3, 0, 0]} maxBarSize={38} isAnimationActive={false}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.v < 0 ? "var(--color-neg)" : i === data.length - 1 ? "var(--color-koi)" : "#5c5d63"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Lines for one or more ratio series sharing a unit.
export function MetricLines({ series, unit, height = 180 }: {
  series: { key: string; label: string; points: Json[]; color: string }[]; unit: string; height?: number;
}) {
  const periods = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.period)))).sort();
  const data = periods.map((p) => {
    const row: Record<string, string | number | null> = { name: fy(p) };
    for (const s of series) row[s.key] = s.points.find((x) => x.period === p)?.value ?? null;
    return row;
  });
  return (
    <div>
      {series.length > 1 && (
        <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-300" aria-label="Legend">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-3" style={{ background: s.color }} />
              {s.label}
            </li>
          ))}
        </ul>
      )}
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 8, left: 4, bottom: 0 }}>
        {GRID}
        <XAxis dataKey="name" {...AXIS} />
        <YAxis {...AXIS} width={56} tickFormatter={(v) => axisTick(v, unit)} />
        <Tooltip
          contentStyle={{ background: "#212023", border: "1px solid #3a3a3e", borderRadius: 6, fontSize: 12 }}
          formatter={(v, name) => [byUnit(Number(v), unit), series.find((s) => s.key === name)?.label ?? String(name)]}
        />
        {series.map((s) => (
          <Line key={s.key} type="linear" dataKey={s.key} stroke={s.color} strokeWidth={2} dot={false} activeDot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
    </div>
  );
}

export function PriceChart({ prices, height = 260 }: { prices: Json[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || prices.length === 0) return;
    const chart = createChart(ref.current, {
      height,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8a8c92", fontSize: 11,
                attributionLogo: false },
      grid: { vertLines: { visible: false }, horzLines: { color: "#222224" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { vertLine: { color: "#5c5d63", style: LineStyle.Dashed }, horzLine: { color: "#5c5d63", style: LineStyle.Dashed } },
      autoSize: true,
    });
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#e0784f", topColor: "rgba(224,120,79,0.18)", bottomColor: "rgba(224,120,79,0)", lineWidth: 2,
    });
    series.setData(prices.map((p) => ({ time: p.date, value: p.close })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [prices, height]);
  return <div ref={ref} style={{ height }} className="w-full" />;
}

export function ScenarioChart({ forecast, unit = "INR", height = 220 }: { forecast: Json; unit?: string; height?: number }) {
  if (!forecast?.available) return <p className="text-[12px] text-ink-500">{forecast?.reason ?? "Unavailable"}</p>;
  const hist = forecast.history as Json[];
  const last = hist[hist.length - 1];
  const lastYear = Number(last.period.slice(0, 4));
  const rows: Json[] = hist.map((h) => ({ name: fy(h.period), actual: h.value }));
  rows[rows.length - 1] = { ...rows[rows.length - 1], bear: last.value, base: last.value, bull: last.value };
  for (let h = 0; h < forecast.scenarios.base.path.length; h++) {
    rows.push({
      name: `FY${String(lastYear + h + 1).slice(2)}E`,
      bear: forecast.scenarios.bear.path[h],
      base: forecast.scenarios.base.path[h],
      bull: forecast.scenarios.bull.path[h],
    });
  }
  const colors: Record<string, string> = { actual: "#ffffff", bear: "#8a8c92", base: "var(--color-koi)", bull: "#b4b5b9" };
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 6, right: 8, left: 4, bottom: 0 }}>
        {GRID}
        <XAxis dataKey="name" {...AXIS} />
        <YAxis {...AXIS} width={64} tickFormatter={(v) => axisTick(v, unit)} />
        <Tooltip
          contentStyle={{ background: "#212023", border: "1px solid #3a3a3e", borderRadius: 6, fontSize: 12 }}
          formatter={(v, name) => [byUnit(Number(v), unit), String(name)]}
        />
        {["actual", "bear", "base", "bull"].map((k) => (
          <Line key={k} type="linear" dataKey={k} stroke={colors[k]} strokeWidth={k === "actual" ? 2 : 1.6}
                strokeDasharray={k === "actual" ? undefined : "4 3"} dot={false} activeDot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
