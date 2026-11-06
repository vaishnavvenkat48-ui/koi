"use client";

import type { Json, Mode } from "@/lib/api";
import { byUnit, fy, pct } from "@/lib/format";
import { useMode } from "@/lib/mode";
import { InfoTip, Panel } from "../ui";
import { MetricLines } from "./Charts";
import { useEvidence } from "./Evidence";

const CATEGORIES: { key: string; title: string }[] = [
  { key: "growth", title: "Revenue & growth" },
  { key: "profitability", title: "Profitability" },
  { key: "health", title: "Financial health" },
  { key: "bank", title: "Lender metrics" },
  { key: "cashflow", title: "Cash flow" },
  { key: "efficiency", title: "Efficiency & working capital" },
];

const LEVELS: Mode[] = ["beginner", "intermediate", "advanced"];

function MetricCell({ m, series }: { m: Json; series: Json[] }) {
  const open = useEvidence();
  const tr = m.trend;
  const arrow =
    !tr || tr.direction === "stable" || tr.direction === "unknown" ? "" : tr.direction === "improving" ? "▲" : "▼";
  const good = m.better === "neutral" ? null : (tr?.direction === "improving") === (m.better === "higher");
  return (
    <button
      disabled={!m.available}
      onClick={() => open({ title: m.label, plain: m.plain, formula: m.formula, unit: m.unit, points: series })}
      className="panel-2 flex flex-col gap-1 p-3 text-left transition-colors enabled:hover:border-ink-500 disabled:cursor-default"
    >
      <span className="flex items-center gap-1.5 text-[12px] text-ink-300">
        {m.label}
        <InfoTip text={`${m.plain} Formula: ${m.formula}.`} />
      </span>
      {m.available ? (
        <>
          <span className="num text-[17px] text-ink-100">
            {byUnit(m.value, m.unit)}
            {arrow && <span className={`ml-1.5 text-[11px] ${good === null ? "text-ink-400" : good ? "text-pos" : "text-neg"}`}>{arrow}</span>}
          </span>
          <span className="text-[11px] text-ink-500">{fy(m.period)}{m.note ? ` · ${m.note}` : ""}</span>
        </>
      ) : (
        <span className="text-[12px] text-ink-500">{m.applicable === false ? "Not applicable" : "Unavailable"} — {m.reason}</span>
      )}
    </button>
  );
}

export function MetricsGrid({ a }: { a: Json }) {
  const { mode } = useMode();
  const allowed = LEVELS.slice(0, LEVELS.indexOf(mode) + 1);
  return (
    <div className="space-y-4">
      {CATEGORIES.filter((c) => c.key !== "bank" || ["bank", "nbfc", "insurance"].includes(a.profile)).map((c) => {
        const items = Object.values(a.headline as Record<string, Json>).filter(
          (m) => m.category === c.key && allowed.includes(m.level) && (m.applicable !== false || mode === "advanced"),
        );
        if (!items.length) return null;
        return (
          <Panel key={c.key} title={c.title}>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4">
              {items.map((m) => <MetricCell key={m.key} m={m} series={a.series[m.key] ?? []} />)}
            </div>
          </Panel>
        );
      })}
      {a.unavailable_sector_metrics?.length > 0 && (
        <Panel title="Sector metrics not available from the current data source">
          <p className="mb-2 text-[12px] text-ink-400">
            These are the right metrics for a {a.profile} but the free source does not provide them. KOI will not substitute
            or estimate them. Check the company&apos;s investor presentations or exchange filings.
          </p>
          <div className="flex flex-wrap gap-1.5">
            {a.unavailable_sector_metrics.map((m: string) => (
              <span key={m} className="rounded border border-ink-700 px-2 py-0.5 text-[12px] text-ink-300">{m}</span>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

export function AdvancedAnalytics({ a }: { a: Json }) {
  const s = a.series;
  const lender = ["bank", "nbfc", "insurance"].includes(a.profile);
  const growth = (k: string) => a.cagr[k]?.value;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {!lender && (
        <Panel title="DuPont analysis" info="ROE = Net margin × Asset turnover × Equity multiplier. Shows whether returns come from profitability, efficiency or leverage.">
          <div className="grid grid-cols-3 gap-2 pb-3 text-center">
            {[["net_margin", "Net margin"], ["asset_turnover", "Asset turnover"], ["equity_multiplier", "Equity multiplier"]].map(([k, l]) => (
              <div key={k} className="panel-2 p-2">
                <p className="text-[11px] text-ink-400">{l}</p>
                <p className="num text-[15px]">{byUnit(a.headline[k]?.value, a.headline[k]?.unit ?? "x")}</p>
              </div>
            ))}
          </div>
          <MetricLines unit="x" height={150} series={[
            { key: "asset_turnover", label: "Asset turnover", color: "var(--color-koi)", points: s.asset_turnover ?? [] },
            { key: "equity_multiplier", label: "Equity multiplier", color: "var(--color-ink-300)", points: s.equity_multiplier ?? [] },
          ]} />
        </Panel>
      )}
      {!lender && (
        <Panel title="Working capital cycle" info="Days of cash tied up in receivables and inventory, less days of supplier credit.">
          <MetricLines unit="days" height={190} series={[
            { key: "receivable_days", label: "Receivable days", color: "var(--color-ink-100)", points: s.receivable_days ?? [] },
            { key: "inventory_days", label: "Inventory days", color: "var(--color-ink-400)", points: s.inventory_days ?? [] },
            { key: "payable_days", label: "Payable days", color: "var(--color-ink-600)", points: s.payable_days ?? [] },
            { key: "cash_conversion_cycle", label: "Cash conversion cycle", color: "var(--color-koi)", points: s.cash_conversion_cycle ?? [] },
          ]} />
        </Panel>
      )}
      <Panel title="Earnings quality" info="Cash conversion near or above 1.0x and a low accruals ratio mean profits are backed by cash.">
        <MetricLines unit="x" height={170} series={[
          { key: "cash_conversion", label: "Cash conversion (OCF / profit)", color: "var(--color-koi)", points: s.cash_conversion ?? [] },
        ]} />
        <p className="mt-2 text-[12px] text-ink-400">
          Accruals ratio (latest): <span className="num text-ink-200">{pct(a.headline.accruals_ratio?.value)}</span>
        </p>
      </Panel>
      <Panel title="Returns on capital" info="ROIC uses after-tax EBIT over average invested capital (debt + equity).">
        <MetricLines unit="pct" height={170} series={[
          { key: "roic", label: "ROIC", color: "var(--color-koi)", points: s.roic ?? [] },
          { key: "roce", label: "ROCE", color: "var(--color-ink-100)", points: s.roce ?? [] },
          { key: "roe", label: "ROE", color: "var(--color-ink-400)", points: s.roe ?? [] },
        ].filter((x) => x.points.length)} />
      </Panel>
      <Panel title="Growth (CAGR over available history)">
        <table className="w-full text-[12px]">
          <tbody>
            {[["revenue", "Revenue"], ["net_income", "Net profit"], ["eps_diluted", "Diluted EPS"], ["operating_cf", "Operating cash flow"], ["total_equity", "Equity"]].map(([k, l]) => (
              <tr key={k} className="border-t border-ink-800 first:border-0">
                <td className="py-1.5 text-ink-300">{l}</td>
                <td className="num py-1.5 text-right">{pct(growth(k))}</td>
                <td className="py-1.5 pl-3 text-right text-[11px] text-ink-500">
                  {a.cagr[k]?.value != null ? `${fy(a.cagr[k].from)} → ${fy(a.cagr[k].to)}` : a.cagr[k]?.note}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <Panel title="Ownership" info={a.ownership.note}>
        <div className="grid grid-cols-2 gap-2">
          <div className="panel-2 p-3">
            <p className="text-[11px] text-ink-400">Insiders (≈ promoters)</p>
            <p className="num text-[16px]">{a.ownership.insiders_pct != null ? `${a.ownership.insiders_pct.toFixed(2)}%` : "—"}</p>
          </div>
          <div className="panel-2 p-3">
            <p className="text-[11px] text-ink-400">Institutions (FII + DII)</p>
            <p className="num text-[16px]">{a.ownership.institutions_pct != null ? `${a.ownership.institutions_pct.toFixed(2)}%` : "—"}</p>
          </div>
        </div>
        <p className="mt-2 text-[11px] text-ink-500">Unavailable from current source: {a.ownership.unavailable.join(", ")}.</p>
      </Panel>
    </div>
  );
}
