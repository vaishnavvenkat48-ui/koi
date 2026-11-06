"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type Json } from "@/lib/api";
import { byUnit, inr } from "@/lib/format";
import { useMode } from "@/lib/mode";
import { Badge, Panel } from "../ui";
import { useEvidence } from "./Evidence";

export function ReportSections({ report }: { report: Json }) {
  const { atLeast } = useMode();
  const open = useEvidence();
  return (
    <div className="space-y-3">
      {report.sections.map((s: Json) => (
        <Panel key={s.id} title={s.title}>
          {s.summary && <p className="mb-2 text-[13px] text-ink-300">{s.summary}</p>}
          <ul className="space-y-1.5">
            {s.points.map((p: Json, k: number) => (
              <li key={k} className="text-[13px] leading-snug">
                <div className="flex items-start gap-2">
                  {p.severity && <Badge tone={p.severity === "concern" ? "neg" : "warn"}>{p.severity}</Badge>}
                  <div>
                    <span className="text-ink-100">{p.plain}</span>
                    {atLeast("intermediate") && p.detail && <span className="block text-[12px] text-ink-400">{p.detail}</span>}
                    {atLeast("advanced") && p.evidence?.length > 0 && (
                      <button onClick={() => open({ title: p.plain, detail: p.detail, formula: p.formula,
                        points: p.evidence[0]?.inputs ? p.evidence : undefined, inputs: p.evidence[0]?.inputs ? undefined : p.evidence })}
                        className="text-[11px] text-info hover:underline">evidence ({p.evidence.length})</button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {s.table && atLeast("intermediate") && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[560px] text-[12px]">
                <thead><tr className="text-ink-400"><th className="py-1 text-left font-normal">Company</th>
                  {s.table.columns.slice(1, 10).map((c: Json) => <th key={c.key} className="px-2 py-1 text-right font-normal">{c.label}</th>)}</tr></thead>
                <tbody className="num">
                  {s.table.rows.map((r: Json) => (
                    <tr key={r.symbol} className="border-t border-ink-800">
                      <td className="py-1 font-sans">{r.symbol}</td>
                      {s.table.columns.slice(1, 10).map((c: Json) => <td key={c.key} className="px-2 py-1 text-right">{byUnit(r[c.key], c.unit === "INR" ? "INR" : c.unit)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      ))}
    </div>
  );
}

export function ReportView({ symbol, report, onRefresh }: { symbol: string; report: Json; onRefresh: (llm: boolean) => Promise<void> }) {
  const { mode, atLeast } = useMode();
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [narrating, setNarrating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      const r = await api.saveReport(symbol);
      setSavedId(r.id);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  const narrate = async () => {
    setNarrating(true);
    try {
      await onRefresh(true);
    } finally {
      setNarrating(false);
    }
  };
  const download = () => {
    const blob = new Blob([toMarkdown(report)], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${symbol}_KOI_report_${mode}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const n = report.narrative;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={save} disabled={saving} className="rounded bg-ink-700 px-3 py-1.5 text-[12px] hover:bg-ink-600 disabled:opacity-50">
          {saving ? "Saving…" : "Save report"}
        </button>
        {savedId && <Link href={`/reports/${savedId}`} className="text-[12px] text-pos">Saved — open report #{savedId}</Link>}
        <button onClick={download} className="rounded border border-ink-600 px-3 py-1.5 text-[12px] hover:bg-ink-800">Download (.md)</button>
        <button onClick={narrate} disabled={narrating} className="rounded border border-ink-600 px-3 py-1.5 text-[12px] hover:bg-ink-800 disabled:opacity-50">
          {narrating ? "Asking local model…" : "Generate AI narrative (Ollama)"}
        </button>
        <span className="text-[11px] text-ink-500">Generated {new Date(report.generated_at).toLocaleString()} · {mode} mode</span>
        {err && <span className="text-[12px] text-neg">{err}</span>}
      </div>
      {n && n.reason !== "LLM narrative not requested" && (
        <Panel title="AI narrative" info="Written by a local open-weight model from KOI's computed facts only. Any number not present in those facts causes the narrative to be rejected.">
          {n.ok ? (
            <>
              <p className="whitespace-pre-line text-[13px] leading-relaxed text-ink-200">{n.text}</p>
              <p className="mt-2 text-[11px] text-ink-500">Model: {n.model} · numbers validated against computed facts</p>
            </>
          ) : (
            <p className="text-[12px] text-ink-400">Narrative unavailable: {n.reason}. The deterministic report below is complete without it.</p>
          )}
        </Panel>
      )}
      <ReportSections report={report} />
      {atLeast("advanced") && report.trace && <AgentTrace trace={report.trace} />}
    </div>
  );
}

export function AgentTrace({ trace }: { trace: Json[] }) {
  return (
    <Panel title="Agent execution trace" info="LangGraph nodes executed for this report, the tools each invoked, and timings. Investigations are chosen adaptively from detected signals.">
      <ol className="space-y-1 text-[12px]">
        {trace.map((t, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-3 border-t border-ink-800 py-1 first:border-0">
            <span className="num w-6 text-ink-500">{i + 1}</span>
            <span className="w-36 text-ink-100">{t.node}</span>
            <span className="text-ink-300">{t.tool ?? (t.tools ? [...new Set(t.tools)].join(", ") : "")}</span>
            {t.signal && <Badge tone={t.severity === "concern" ? "neg" : "warn"}>{t.signal}</Badge>}
            {t.signals && <span className="text-ink-400">signals: {t.signals.length ? t.signals.join(", ") : "none"}</span>}
            {t.queued_follow_ups?.length > 0 && <span className="text-info">queued follow-up: {t.queued_follow_ups.join(", ")}</span>}
            {t.reason && <span className="text-ink-500">{t.reason}</span>}
            <span className="num ml-auto text-ink-500">{t.ms} ms</span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

function toMarkdown(r: Json): string {
  const lines = [`# ${r.company.name} (${r.symbol}) — KOI research report`, "",
    `Generated ${r.generated_at}. Outlook: **${r.outlook.label}** · valuation ${r.outlook.valuation_verdict} · confidence ${r.confidence.level}.`, "",
    `Scores: ${Object.entries(r.scores).map(([k, v]) => `${k} ${v ?? "n/a"}`).join(", ")}`, "",
    `Market cap ${inr(r.company.market_cap)}.`, ""];
  for (const s of r.sections) {
    lines.push(`## ${s.title}`, "");
    if (s.summary) lines.push(s.summary, "");
    for (const p of s.points) lines.push(`- ${p.plain}${p.detail ? ` — ${p.detail}` : ""}`);
    lines.push("");
  }
  lines.push("---", "KOI is a research and decision-support tool, not personalised financial advice.");
  return lines.join("\n");
}
