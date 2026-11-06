"use client";

import { useEffect, useState } from "react";
import { api, type Json } from "@/lib/api";
import { byUnit, fy, quarter } from "@/lib/format";
import { ErrorBox, Panel, Segmented, Skeleton } from "../ui";

const TITLES: Record<string, string> = { income: "Income statement", balance: "Balance sheet", cashflow: "Cash flow statement" };

export function FinancialsView({ symbol }: { symbol: string }) {
  const [period, setPeriod] = useState<"annual" | "quarterly">("annual");
  const [data, setData] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({ income: true, balance: false, cashflow: false });

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset while loading a new period
    setData(null);
    api.financials(symbol, period).then((d) => !cancelled && setData(d)).catch((e) => !cancelled && setErr(e.message));
    return () => {
      cancelled = true;
    };
  }, [symbol, period]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented value={period} onChange={setPeriod} options={[{ key: "annual", label: "Annual" }, { key: "quarterly", label: "Quarterly" }]} />
        <div className="flex items-center gap-3 text-[12px]">
          <span className="text-ink-500">Values in ₹ crore unless stated · consolidation basis: {data?.statements?.income?.[0]?.consolidation ?? "—"}</span>
          <a href={api.exportUrl(symbol, period)} className="rounded border border-ink-600 px-2.5 py-1 hover:bg-ink-800">Export CSV</a>
        </div>
      </div>
      {err && <ErrorBox message={err} />}
      {!data && !err && <Skeleton className="h-64" />}
      {data && data.periods.length === 0 && <p className="text-[13px] text-ink-400">No {period} statements stored.</p>}
      {data && data.periods.length > 0 && ["income", "balance", "cashflow"].map((st) => data.statements[st] && (
        <Panel key={st} title={
          <button onClick={() => setOpen({ ...open, [st]: !open[st] })} className="flex items-center gap-2">
            <span className="text-ink-500">{open[st] ? "▾" : "▸"}</span>{TITLES[st]}
          </button>
        }>
          {open[st] ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-[12px]">
                <thead>
                  <tr className="text-ink-400">
                    <th className="sticky left-0 bg-ink-900 py-1.5 pr-4 text-left font-normal">Line item (source label)</th>
                    {data.periods.map((p: string) => (
                      <th key={p} className="px-2 py-1.5 text-right font-normal">{period === "annual" ? fy(p) : quarter(p)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="num">
                  {data.statements[st].map((m: Json) => (
                    <tr key={m.metric} className="border-t border-ink-800 hover:bg-ink-850">
                      <td className="sticky left-0 bg-ink-900 py-1.5 pr-4 font-sans text-ink-200">
                        {m.label}
                        <span className="ml-1.5 text-[11px] text-ink-500">{m.metric}</span>
                      </td>
                      {data.periods.map((p: string) => (
                        <td key={p} className="px-2 py-1.5 text-right text-ink-200">
                          {m.values[p] === undefined ? <span className="text-ink-600" title="Not reported by source">n/r</span>
                            : byUnit(m.values[p], m.unit === "INR" ? "INR" : m.unit)}
                          {m.revisions[p] ? <sup className="ml-0.5 text-warn" title={`Revised ${m.revisions[p]} time(s) by source`}>r</sup> : null}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[11px] text-ink-500">
                n/r = not reported by the source (never treated as zero). <sup className="text-warn">r</sup> = value was restated by the
                source after first retrieval; the earlier value is kept in the revision log. Source: {data.statements[st][0]?.source}.
              </p>
            </div>
          ) : (
            <p className="text-[12px] text-ink-500">{data.statements[st].length} line items · click to expand</p>
          )}
        </Panel>
      ))}
    </div>
  );
}
