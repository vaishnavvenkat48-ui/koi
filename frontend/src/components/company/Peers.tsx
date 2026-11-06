"use client";

import Link from "next/link";
import type { Json } from "@/lib/api";
import { byUnit, fy } from "@/lib/format";
import { useMode } from "@/lib/mode";
import { Badge, Panel } from "../ui";

const BEGINNER_COLS = ["revenue_cagr", "operating_margin", "roe", "debt_to_equity", "pe"];
const INTERMEDIATE_COLS = ["market_cap", "revenue_cagr", "revenue_growth", "net_income_cagr", "operating_margin", "net_margin", "roe", "roce", "debt_to_equity", "pe", "pb"];

const LOWER_BETTER = new Set(["debt_to_equity", "pe", "pb", "ev_ebitda"]);

export function PeerTable({ peers, symbol }: { peers: Json; symbol: string }) {
  const { mode } = useMode();
  const cols: Json[] = peers.columns.filter((c: Json) =>
    mode === "advanced" ? true : mode === "intermediate" ? INTERMEDIATE_COLS.includes(c.key) : BEGINNER_COLS.includes(c.key),
  );
  const rows: Json[] = [peers.company, ...peers.peers];
  const best = (key: string) => {
    const vals = rows.filter((r) => r.has_data && r[key] != null && (!LOWER_BETTER.has(key) || r[key] > 0)).map((r) => r[key]);
    if (vals.length < 2 || key === "market_cap" || key === "revenue") return null;
    return LOWER_BETTER.has(key) ? Math.min(...vals) : Math.max(...vals);
  };
  const bests = Object.fromEntries(cols.map((c) => [c.key, best(c.key)]));
  return (
    <Panel
      title="Peer comparison"
      info="Competitors are identified from KOI's sector map (P1: main peers, P2: wider sector) and loaded in the background. Highlighted cells are best in group."
      right={<span className="text-[11px] text-ink-500">{peers.loaded} of {peers.expected} peers loaded</span>}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-[12px]">
          <thead>
            <tr className="text-left text-ink-400">
              <th className="sticky left-0 bg-ink-900 py-1.5 pr-3 font-normal">Company</th>
              {cols.map((c) => <th key={c.key} className="px-2 py-1.5 text-right font-normal">{c.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const me = r.symbol === symbol;
              const tier = peers.p1.includes(r.symbol) ? "P1" : peers.p2.includes(r.symbol) ? "P2" : null;
              return (
                <tr key={r.symbol} className={`border-t border-ink-800 ${me ? "bg-koi-dim/40" : ""}`}>
                  <td className={`sticky left-0 py-1.5 pr-3 ${me ? "bg-[#1d1714]" : "bg-ink-900"}`}>
                    <Link href={`/company/${encodeURIComponent(r.symbol)}`} className="hover:text-white">
                      <span className={me ? "font-medium text-koi" : "text-ink-200"}>{r.symbol}</span>
                    </Link>
                    {tier && <span className="ml-1.5 text-[11px] text-ink-500">{tier}</span>}
                    {!r.has_data && <Badge tone="none">{r.status === "queued" || r.status === "running" ? "loading…" : r.status === "error" ? "unavailable" : "pending"}</Badge>}
                  </td>
                  {cols.map((c) => {
                    const v = r[c.key];
                    const isBest = r.has_data && v != null && bests[c.key] != null && v === bests[c.key];
                    return (
                      <td key={c.key} className={`num whitespace-nowrap px-2 py-1.5 text-right ${isBest ? "text-pos" : r.has_data ? "text-ink-200" : "text-ink-600"}`}>
                        {r.has_data ? byUnit(v, c.key === "market_cap" || c.key === "revenue" ? "INR" : c.unit) : "·"}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            <tr className="border-t border-ink-600 text-ink-400">
              <td className="sticky left-0 bg-ink-900 py-1.5 pr-3">Peer median</td>
              {cols.map((c) => (
                <td key={c.key} className="num whitespace-nowrap px-2 py-1.5 text-right">
                  {byUnit(peers.medians[c.key], c.key === "market_cap" || c.key === "revenue" ? "INR" : c.unit)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      {mode !== "beginner" && peers.company.latest_period && (
        <p className="mt-2 text-[11px] text-ink-500">
          Latest fiscal year for {symbol}: {fy(peers.company.latest_period)}. Peers may report different periods; P/E and P/B use
          trailing-twelve-month profit when four consecutive quarters are available.
        </p>
      )}
    </Panel>
  );
}
