"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Empty, ErrorBox, Panel } from "@/components/ui";
import { api, type Json } from "@/lib/api";
import { byUnit, fy } from "@/lib/format";

const LOWER_BETTER = new Set(["debt_to_equity", "pe", "pb", "ev_ebitda"]);

export default function ComparePage() {
  const [input, setInput] = useState("");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [data, setData] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("s");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- read initial selection from the URL
    if (q) setSymbols(q.split(",").filter(Boolean));
  }, []);

  useEffect(() => {
    if (symbols.length === 0) return;
    window.history.replaceState(null, "", `?s=${symbols.join(",")}`);
    let stop = false;
    const load = async () => {
      try {
        const d = await api.compare(symbols);
        if (stop) return;
        setData(d);
        setErr(null);
        if (d.rows.some((r: Json) => !r.has_data && r.status !== "error")) setTimeout(load, 4000);
      } catch (e) {
        if (!stop) setErr((e as Error).message);
      }
    };
    load();
    return () => { stop = true; };
  }, [symbols]);

  const add = () => {
    const s = input.trim().toUpperCase();
    if (s && !symbols.includes(s) && symbols.length < 6) setSymbols([...symbols, s]);
    setInput("");
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Compare companies</h1>
        <p className="text-[13px] text-ink-400">Side-by-side fundamentals for up to six NSE companies, across any sectors.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {symbols.map((s) => (
          <span key={s} className="flex items-center gap-1.5 rounded border border-ink-600 px-2 py-1 text-[12px]">
            {s}
            <button onClick={() => setSymbols(symbols.filter((x) => x !== s))} className="text-ink-500 hover:text-ink-200" aria-label={`Remove ${s}`}><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg></button>
          </span>
        ))}
        <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Add NSE symbol (e.g. INFY)" className="w-52 rounded border border-ink-700 bg-ink-900 px-2.5 py-1 text-[13px] outline-none focus:border-ink-500" />
        <button onClick={add} className="rounded bg-ink-700 px-3 py-1 text-[12px] hover:bg-ink-600">Add</button>
      </div>
      {err && <ErrorBox message={err} />}
      {symbols.length === 0 ? <Empty>Add two or more symbols to compare.</Empty> : data && (
        <Panel title="Comparison">
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-ink-400">
                  <th className="py-1.5 text-left font-normal">Metric</th>
                  {data.rows.map((r: Json) => (
                    <th key={r.symbol} className="px-3 py-1.5 text-right font-normal">
                      <Link href={`/company/${encodeURIComponent(r.symbol)}`} className="text-ink-100 hover:text-white">{r.symbol}</Link>
                      <span className="block text-[11px] text-ink-500">{r.has_data ? fy(r.latest_period) : r.status === "error" ? "unavailable" : "loading…"}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="num">
                {data.columns.map((c: Json) => {
                  const vals = data.rows.filter((r: Json) => r.has_data && r[c.key] != null).map((r: Json) => r[c.key]);
                  const best = vals.length > 1 && !["market_cap", "revenue"].includes(c.key)
                    ? (LOWER_BETTER.has(c.key) ? Math.min(...vals.filter((v: number) => v > 0)) : Math.max(...vals)) : null;
                  return (
                    <tr key={c.key} className="border-t border-ink-800">
                      <td className="py-1.5 font-sans text-ink-300">{c.label}</td>
                      {data.rows.map((r: Json) => (
                        <td key={r.symbol} className={`px-3 py-1.5 text-right ${best !== null && r[c.key] === best ? "text-pos" : "text-ink-200"}`}>
                          {r.has_data ? byUnit(r[c.key], c.unit) : "·"}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
