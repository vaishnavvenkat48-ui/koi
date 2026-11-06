"use client";

import { useEffect, useState } from "react";
import { ErrorBox, Panel, Skeleton } from "@/components/ui";
import { api, type Json } from "@/lib/api";

export default function MethodologyPage() {
  const [m, setM] = useState<Json | null>(null);
  const [health, setHealth] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.methodology().then(setM).catch((e) => setErr(e.message));
    api.health().then(setHealth).catch(() => {});
  }, []);
  if (err) return <ErrorBox message={err} />;
  if (!m) return <Skeleton className="h-96" />;
  const s = m.scoring;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Methodology</h1>
        <p className="text-[13px] text-ink-400">
          Every score and conclusion in KOI comes from documented, deterministic rules applied to stored source data. The
          optional language model only rephrases computed facts and is checked for invented numbers.
        </p>
      </div>
      {health && (
        <Panel title="System status">
          <ul className="space-y-1 text-[12px] text-ink-300">
            <li>Companies in master list: <span className="num">{health.companies}</span>{health.master_stale ? " (refresh pending)" : ""}</li>
            <li>Background worker: {health.worker.alive ? "running" : "stopped"} · queued {health.worker.queued.length}</li>
            <li>Local LLM: {health.llm.available ? `${health.llm.model} available` : `unavailable — ${health.llm.reason}`}</li>
          </ul>
        </Panel>
      )}
      <Panel title="Scores">
        <ul className="space-y-1.5 text-[13px] text-ink-200">
          {Object.entries(s.sub_scores).map(([k, v]) => <li key={k}><span className="text-ink-400 capitalize">{k}: </span>{v as string}</li>)}
          <li><span className="text-ink-400">Component scoring: </span>{s.component_scoring}</li>
          <li><span className="text-ink-400">Missing data: </span>{s.missing_data}</li>
          <li><span className="text-ink-400">Composite: </span>{s.fundamentals_composite}</li>
          <li><span className="text-ink-400">Confidence: </span>{s.confidence}</li>
        </ul>
      </Panel>
      <Panel title="Outlook rules (evaluated in order)">
        <ol className="list-decimal space-y-1 pl-5 text-[13px] text-ink-200">{s.outlook_rules.map((r: string) => <li key={r}>{r}</li>)}</ol>
        <p className="mt-2 text-[12px] text-ink-400">{s.valuation_verdict}</p>
      </Panel>
      <Panel title="Sector profiles and thresholds" info="Each rule: signal, label, bad threshold (score 0), good threshold (score 100), weight.">
        <div className="grid gap-3 md:grid-cols-2">
          {Object.entries(m.profiles).map(([p, rules]: [string, Json]) => (
            <details key={p} className="panel-2 p-3">
              <summary className="cursor-pointer text-[13px] capitalize">{p.replace("_", " ")}</summary>
              {Object.entries(rules).map(([score, rs]: [string, Json]) => (
                <div key={score} className="mt-2">
                  <p className="label">{score}</p>
                  <table className="num w-full text-[11px]">
                    <tbody>
                      {rs.map((r: Json) => (
                        <tr key={r[0]} className="border-t border-ink-800">
                          <td className="py-0.5 font-sans text-ink-300">{r[1]}</td>
                          <td className="py-0.5 text-right">{r[2]}</td><td className="py-0.5 text-right">{r[3]}</td>
                          <td className="py-0.5 text-right text-ink-500">w{r[4]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </details>
          ))}
        </div>
      </Panel>
      <Panel title="Metric definitions">
        <table className="w-full text-[12px]">
          <tbody>
            {Object.values(m.metrics).map((d: Json) => (
              <tr key={d.key} className="border-t border-ink-800 align-top">
                <td className="py-1.5 pr-3 text-ink-100">{d.label}</td>
                <td className="num py-1.5 pr-3 text-ink-300">{d.formula}</td>
                <td className="py-1.5 text-ink-400">{d.plain}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <Panel title="Data sources">
        <ul className="space-y-3 text-[12px]">
          {m.data_sources.map((d: Json) => (
            <li key={d.key}>
              <p className="text-ink-100">{d.name}</p>
              <p className="text-ink-400">{d.coverage}</p>
              <p className="text-ink-500">{d.terms_note}</p>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
