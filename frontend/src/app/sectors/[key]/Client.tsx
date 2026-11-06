"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge, ErrorBox, Panel, Skeleton } from "@/components/ui";
import { api, type Json } from "@/lib/api";
import { byUnit } from "@/lib/format";

const COLS = [
  ["market_cap", "Market cap", "INR"], ["revenue_cagr", "Revenue CAGR", "pct"], ["operating_margin", "Op. margin", "pct"],
  ["roe", "ROE", "pct"], ["roce", "ROCE", "pct"], ["debt_to_equity", "D/E", "x"], ["pe", "P/E", "x"], ["pb", "P/B", "x"],
] as const;

export default function SectorPage({ sectorKey: key }: { sectorKey: string }) {
  const [data, setData] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => api.sector(key).then(setData).catch((e) => setErr(e.message)), [key]);
   
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!loading) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [loading, load]);

  const missing = data?.companies.filter((c: Json) => !c.has_data).length ?? 0;
  return (
    <div className="space-y-4">
      {err && <ErrorBox message={err} />}
      {!data ? <Skeleton className="h-64" /> : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <Link href="/sectors" className="text-[12px] text-ink-400 hover:text-ink-200">← Sectors</Link>
              <h1 className="text-[22px] font-semibold tracking-tight">{data.sector.name}</h1>
              <p className="text-[13px] text-ink-400">{data.sector.description} Analysis profile: {data.sector.profile.replace("_", " ")}.</p>
            </div>
            {missing > 0 && (
              <button
                onClick={async () => { setLoading(true); await api.sectorLoad(key); }}
                disabled={loading}
                className="rounded border border-ink-600 px-3 py-1.5 text-[12px] hover:bg-ink-800 disabled:opacity-60"
              >
                {loading ? `Loading in background… (${missing} remaining)` : `Load data for ${missing} companies`}
              </button>
            )}
          </div>
          <Panel title="Companies">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-[12px]">
                <thead><tr className="text-left text-ink-400">
                  <th className="py-1.5 font-normal">Company</th>
                  {COLS.map(([k, l]) => <th key={k} className="px-2 py-1.5 text-right font-normal">{l}</th>)}
                </tr></thead>
                <tbody className="num">
                  {data.companies.map((c: Json) => (
                    <tr key={c.symbol} className="border-t border-ink-800 hover:bg-ink-850">
                      <td className="py-1.5 font-sans">
                        <Link href={`/company/${encodeURIComponent(c.symbol)}`} className="text-ink-100 hover:text-white">{c.name}</Link>
                        <span className="num ml-1.5 text-[12px] text-ink-400">{c.symbol}</span>
                        {!c.has_data && <span className="ml-1.5"><Badge>{c.status === "error" ? "unavailable" : "not loaded"}</Badge></span>}
                      </td>
                      {COLS.map(([k, , u]) => <td key={k} className="px-2 py-1.5 text-right text-ink-200">{c.has_data ? byUnit(c[k], u) : "·"}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
