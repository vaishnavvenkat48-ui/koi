"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Empty, ErrorBox, Panel } from "@/components/ui";
import { api, type Json } from "@/lib/api";
import { pct } from "@/lib/format";

export default function ReportsPage() {
  const [reports, setReports] = useState<Json[] | null>(null);
  const [sel, setSel] = useState<number[]>([]);
  const [cmp, setCmp] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = () => api.reports().then((r) => setReports(r.reports)).catch((e) => setErr(e.message));
   
  useEffect(() => { load(); }, []);

  const toggle = (id: number) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-2)));
  const compare = async () => {
    const [a, b] = [...sel].sort((x, y) => x - y);
    try {
      setCmp(await api.compareReports(a, b));
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">Saved research reports</h1>
          <p className="text-[13px] text-ink-400">Select two reports (e.g. the same company at different dates) to see what changed.</p>
        </div>
        <button disabled={sel.length !== 2} onClick={compare} className="rounded bg-ink-700 px-3 py-1.5 text-[12px] hover:bg-ink-600 disabled:opacity-40">
          Compare selected ({sel.length}/2)
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {reports && reports.length === 0 && <Empty>No saved reports. Open a company, go to Research report and click Save.</Empty>}
      {reports && reports.length > 0 && (
        <Panel title={`${reports.length} report(s)`}>
          <ul className="divide-y divide-ink-800">
            {reports.map((r) => (
              <li key={r.id} className="flex items-center gap-3 py-2 text-[13px]">
                <input type="checkbox" checked={sel.includes(r.id)} onChange={() => toggle(r.id)} aria-label={`Select report ${r.id}`} className="accent-[var(--color-koi)]" />
                <Link href={`/reports/${r.id}`} className="flex-1 truncate hover:text-white">{r.title}</Link>
                <Badge>{r.outlook}</Badge>
                <span className="num text-[11px] text-ink-500">{new Date(r.created_at).toLocaleString()}</span>
                <button onClick={async () => { await api.deleteReport(r.id); load(); }} className="text-[11px] text-ink-500 hover:text-neg">delete</button>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {cmp && (
        <Panel title={`Comparison: #${cmp.old.id} (${cmp.old.symbol}) → #${cmp.new.id} (${cmp.new.symbol})`}>
          <p className="mb-3 text-[13px]">
            Outlook: <span className="text-ink-300">{cmp.old.outlook.label}</span> → <span className="text-ink-100">{cmp.new.outlook.label}</span>{" "}
            {cmp.outlook_changed ? <Badge tone="warn">changed</Badge> : <Badge>unchanged</Badge>}
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <table className="text-[12px]">
              <thead className="text-ink-400"><tr><th className="text-left font-normal">Score</th><th className="text-right font-normal">Old</th><th className="text-right font-normal">New</th><th className="text-right font-normal">Δ</th></tr></thead>
              <tbody className="num">
                {Object.entries(cmp.scores).map(([k, v]: [string, Json]) => (
                  <tr key={k} className="border-t border-ink-800">
                    <td className="py-1 font-sans capitalize text-ink-300">{k}</td>
                    <td className="py-1 text-right">{v.old ?? "—"}</td><td className="py-1 text-right">{v.new ?? "—"}</td>
                    <td className={`py-1 text-right ${v.change > 0 ? (k === "risk" ? "text-neg" : "text-pos") : v.change < 0 ? (k === "risk" ? "text-pos" : "text-neg") : ""}`}>{v.change ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="space-y-2 text-[12px]">
              <table className="w-full">
                <tbody className="num">
                  {Object.values(cmp.metrics).map((m: Json) => (
                    <tr key={m.label} className="border-t border-ink-800">
                      <td className="py-1 font-sans text-ink-300">{m.label}</td>
                      <td className="py-1 text-right">{m.unit === "pct" ? pct(m.old) : m.old?.toFixed?.(2) ?? "—"}</td>
                      <td className="py-1 text-right">{m.unit === "pct" ? pct(m.new) : m.new?.toFixed?.(2) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {cmp.new_findings.length > 0 && <p className="text-neg">New red flags: {cmp.new_findings.join("; ")}</p>}
              {cmp.resolved_findings.length > 0 && <p className="text-pos">Resolved: {cmp.resolved_findings.join("; ")}</p>}
            </div>
          </div>
        </Panel>
      )}
    </div>
  );
}
