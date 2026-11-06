"use client";

import { useState } from "react";
import type { Json } from "@/lib/api";
import { pct, scoreTone, toneText } from "@/lib/format";
import { useMode } from "@/lib/mode";
import { Badge, InfoTip, Modal, Panel, ScoreBar } from "../ui";
import { MetricBars, MetricLines, PriceChart } from "./Charts";
import { Statement, useEvidence } from "./Evidence";

const OUTLOOK_TONE: Record<number, string> = { 1: "pos", 2: "pos", 3: "warn", 4: "neg", 5: "neg" };

// Score names in plain words for beginners; the technical name stays in the tooltip.
const SCORE_INFO: Record<string, { label: string; beginner: string; plain: string; invert?: boolean }> = {
  quality: { label: "Business quality", beginner: "How good the business is", plain: "How profitable and efficient the business is: returns on capital and margins." },
  health: { label: "Financial health", beginner: "How safe its finances are", plain: "How safe the balance sheet is: debt, interest cover, liquidity and cash backing." },
  growth: { label: "Growth", beginner: "How fast it has grown", plain: "How fast and how consistently sales, profits and EPS have grown." },
  valuation: { label: "Valuation", beginner: "How cheap the share price is", plain: "How the share price compares with profits, competitors and the company's own history. Higher means cheaper." },
  risk: { label: "Risk", beginner: "How many warning signs", plain: "Warning signs such as rising debt, falling margins or weak cash flow. Higher means riskier.", invert: true },
};

function scoreWord(key: string, v: number | null | undefined, pending?: boolean): string {
  if (pending) return "waiting for competitors";
  if (v === null || v === undefined) return "not enough data";
  if (key === "risk") return v <= 30 ? "few" : v <= 55 ? "some" : "many";
  if (key === "valuation") return v >= 65 ? "cheap" : v >= 40 ? "fair" : "expensive";
  return v >= 70 ? "strong" : v >= 45 ? "average" : "weak";
}

const SCALE = [5, 4, 3, 2, 1];
const SCALE_LABEL: Record<number, string> = { 5: "Serious problems", 4: "Weakening", 3: "Mixed", 2: "Positive", 1: "Strong" };

// Signature element: where this company sits on KOI's five-step outlook scale.
function OutlookScale({ code, capped }: { code: number; capped: boolean }) {
  return (
    <div aria-label={`Outlook ${SCALE_LABEL[code]} on a five-step scale${capped ? ", held back by limited evidence" : ""}`}>
      <div className="grid grid-cols-5 gap-1">
        {SCALE.map((c) => (
          <div key={c} className={`h-1.5 ${c === code ? (c >= 4 ? "bg-neg" : c === 3 ? "bg-warn" : "bg-koi") : "bg-ink-750"}`} />
        ))}
      </div>
      <div className="mt-1.5 grid grid-cols-5 gap-1 text-[12px]">
        {SCALE.map((c) => (
          // On a phone only the company's own step is named; the others keep their place unlabelled.
          <span key={c} className={c === code ? "text-ink-100" : "hidden text-ink-400 sm:inline"}>
            {SCALE_LABEL[c]}
            {capped && c === code && <span className="text-ink-400"> · held back by missing data</span>}
          </span>
        ))}
      </div>
    </div>
  );
}

const CONF_PLAIN: Record<string, string> = {
  High: "We have enough data to be fairly sure.",
  Medium: "Treat this as a first view, not a final answer.",
  Low: "Very little data: this is only a rough guide.",
};

export function OutlookCard({ a, report }: { a: Json; report: Json | null }) {
  const { mode, atLeast } = useMode();
  const [open, setOpen] = useState<string | null>(null);
  const o = a.outlook;
  const conf = a.confidence;
  const s = a.summary;
  const sic = report?.thesis?.should_i_consider;
  const lines = [
    { k: "Main reason", v: s?.main_reason, tone: "text-ink-100" },
    { k: "Main worry", v: s?.main_worry, tone: "text-ink-100" },
    { k: "The price", v: s?.price ?? o.valuation_plain, tone: "text-ink-100" },
  ].filter((l) => l.v);
  return (
    <section className="panel overflow-hidden">
      <div className="grid lg:grid-cols-[1.35fr_1fr]">
        <div className="border-b border-ink-700 p-6 lg:border-b-0 lg:border-r">
          <p className="text-[13px] text-ink-400">
            KOI outlook · {s?.years ?? a.periods.annual.length} years of results
            {s?.first_year && ` (${s.first_year.slice(0, 4)}–${s.last_year.slice(0, 4)})`}
          </p>
          <h2 className={`mt-1 text-[26px] font-semibold leading-tight ${OUTLOOK_TONE[o.code] === "neg" ? "text-neg" : "text-ink-100"}`}>
            {mode === "beginner" ? o.plain_label : o.label}
          </h2>
          {mode !== "beginner" && <p className="mt-0.5 text-[13px] text-ink-400">{o.plain_label}</p>}
          <div className="mt-4"><OutlookScale code={o.code} capped={!!o.capped} /></div>
          <dl className="mt-5 divide-y divide-ink-700 border-y border-ink-700">
            {lines.map((l) => (
              <div key={l.k} className="grid gap-1 py-2.5 sm:grid-cols-[112px_1fr] sm:gap-4">
                <dt className="text-[13px] text-ink-400">{l.k}</dt>
                <dd className={`text-[14px] leading-snug ${l.tone}`}>{l.v}</dd>
              </div>
            ))}
            <div className="grid gap-1 py-2.5 sm:grid-cols-[112px_1fr] sm:gap-4">
              <dt className="text-[13px] text-ink-400">How sure</dt>
              <dd className="text-[14px] leading-snug text-ink-100">
                <span className={conf.level === "Low" ? "text-neg" : ""}>{conf.level} confidence.</span>{" "}
                <span className="text-ink-300">{CONF_PLAIN[conf.level]}</span>
                {atLeast("intermediate") && conf.notes?.length > 0 && (
                  <span className="mt-1 block text-[13px] text-ink-400">{conf.notes.join(" ")}</span>
                )}
              </dd>
            </div>
          </dl>
          {sic && atLeast("intermediate") && (
            <div className="mt-4">
              <p className="text-[13px] text-ink-400">Should I consider it for the long term?</p>
              <p className="mt-1 text-[14px] leading-relaxed text-ink-100">{sic.plain}</p>
              {atLeast("advanced") && <p className="mt-1.5 text-[12px] text-ink-400">{sic.detail}</p>}
            </div>
          )}
          <p className="mt-4 text-[13px] text-ink-300">
            Based on past results only. Not a buy or sell recommendation, and the past does not guarantee the future.
            <span className="ml-1 inline-flex align-middle"><InfoTip text={o.rule} /></span>
          </p>
        </div>
        <div className="p-6">
          <div className="flex items-baseline justify-between">
            <h3 className="text-[14px] font-semibold">Scores</h3>
            <span className="text-[12px] text-ink-400">select a score to see how it was calculated</span>
          </div>
          <div className="mt-2 divide-y divide-ink-700">
            {Object.entries(SCORE_INFO).map(([k, info]) => (
              <ScoreRow key={k} onSelect={() => setOpen(k)}>
                <ScoreBar label={mode === "beginner" ? info.beginner : info.label} value={a.scores[k].value} invert={info.invert}
                          info={info.plain} word={scoreWord(k, a.scores[k].value, a.scores[k].pending)} />
              </ScoreRow>
            ))}
            {atLeast("intermediate") && (
              <ScoreRow onSelect={() => setOpen("fundamentals")}>
                <ScoreBar label="Fundamentals (quality, health, growth)" value={a.scores.fundamentals.value}
                          info={`${a.scores.fundamentals.formula} Valuation and risk are kept separate on purpose.`}
                          word={scoreWord("fundamentals", a.scores.fundamentals.value)} />
              </ScoreRow>
            )}
          </div>
          <p className="mt-3 text-[12px] text-ink-400">
            Scores run from 0 to 100. For risk, lower is better. A good company can still be a poor buy at a high price,
            so price is scored separately.
          </p>
        </div>
      </div>
      <Modal open={!!open && open !== "fundamentals"} onClose={() => setOpen(null)} title={open ? `${SCORE_INFO[open]?.label} — how it is calculated` : ""}>
        {open && open !== "fundamentals" && <ScoreComponents score={a.scores[open]} invert={!!SCORE_INFO[open]?.invert} />}
      </Modal>
      <Modal open={open === "fundamentals"} onClose={() => setOpen(null)} title="Fundamentals composite">
        <p className="text-[13px] text-ink-300">{a.scores.fundamentals.formula}</p>
      </Modal>
    </section>
  );
}

// Clickable score row. Not a <button>, because ScoreBar contains an InfoTip button and
// buttons cannot nest. role/tabIndex/keys keep it keyboard-accessible.
function ScoreRow({ onSelect, children }: { onSelect: () => void; children: React.ReactNode }) {
  return (
    <div
      role="button"
      tabIndex={0}
      className="block w-full cursor-pointer text-left hover:bg-ink-850 focus-visible:outline focus-visible:outline-1 focus-visible:outline-ink-300"
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.target !== e.currentTarget) return;
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(); }
      }}
    >
      {children}
    </div>
  );
}

function fmtSignal(key: string, v: number | null): string {
  if (v === null || v === undefined) return "n/a";
  if (["debt_to_equity", "interest_coverage", "current_ratio", "cash_conversion_avg", "pe_vs_peers", "pe_vs_history",
       "pb_vs_peers", "ev_ebitda", "pb"].includes(key)) return `${v.toFixed(2)}x`;
  if (key === "data_years") return `${v} yrs`;
  if (key === "margin_change" || key === "roa_change") return `${(v * 100).toFixed(1)} pp`;
  if (key === "leverage_change") return `${v >= 0 ? "+" : ""}${v.toFixed(2)}`;
  return pct(v);
}

function ScoreComponents({ score, invert }: { score: Json; invert: boolean }) {
  return (
    <div className="space-y-3">
      <p className="text-[12px] text-ink-400">
        Each component maps its metric linearly from the &quot;bad&quot; threshold (0) to the &quot;good&quot; threshold (100).
        {invert && " Risk = 100 − weighted safety score."} Data coverage: {Math.round(score.coverage * 100)}% of weight.
      </p>
      <table className="w-full text-[12px]">
        <thead className="text-left text-ink-400">
          <tr>
            <th className="py-1 font-normal">Component</th>
            <th className="py-1 text-right font-normal">Value</th>
            <th className="py-1 text-right font-normal">Bad → Good</th>
            <th className="py-1 text-right font-normal">Weight</th>
            <th className="py-1 text-right font-normal">Score</th>
          </tr>
        </thead>
        <tbody>
          {score.components.map((c: Json) => (
            <tr key={c.signal} className="border-t border-ink-800 align-top">
              <td className="py-1.5 pr-2">
                <span className="text-ink-200">{c.label}</span>
                <span className="block text-[11px] text-ink-500">{c.evidence}</span>
              </td>
              <td className="num py-1.5 text-right">{fmtSignal(c.signal, c.value)}</td>
              <td className="num py-1.5 text-right text-ink-400">{fmtSignal(c.signal, c.bad)} → {fmtSignal(c.signal, c.good)}</td>
              <td className="num py-1.5 text-right text-ink-400">{c.weight}</td>
              <td className={`num py-1.5 text-right ${toneText[scoreTone(c.score)]}`}>{c.score === null ? "—" : Math.round(c.score)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Factors({ a }: { a: Json }) {
  const open = useEvidence();
  const { mode, atLeast } = useMode();
  const col = (title: string, items: Json[], tone: "pos" | "neg") => (
    <div>
      <h3 className="flex items-center gap-2 text-[13px] text-ink-300">
        <span className={`h-1.5 w-1.5 rounded-full ${tone === "pos" ? "bg-pos" : "bg-neg"}`} />
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-[13px] text-ink-400">{tone === "pos" ? "No standout strengths in the available data." : "No major concerns flagged by the scoring rules."}</p>
      ) : (
        <ul className="mt-1 divide-y divide-ink-700">
          {items.map((f) => (
            <li key={f.signal}>
              <button
                onClick={() => open({ title: f.label, plain: f.plain, detail: `${f.evidence}. Component score ${f.score}/100 (thresholds: bad ${f.thresholds.bad}, good ${f.thresholds.good}).`, inputs: f.inputs })}
                className="group w-full py-2.5 text-left"
              >
                <span className="text-[14px] text-ink-100 group-hover:underline group-hover:decoration-ink-600 group-hover:underline-offset-4">{f.plain}</span>
                {atLeast("intermediate") && <span className="mt-0.5 block text-[12px] text-ink-400">{f.label}: {f.evidence}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
  return (
    <Panel title={mode === "beginner" ? "Good signs and warning signs" : "Key factors"}
           info="The three strongest positives and three biggest concerns, ranked from KOI's scoring rules. Select one to see the numbers.">
      <div className="grid gap-6 md:grid-cols-2">
        {col("Strongest positives", a.factors.positives, "pos")}
        {col("Biggest concerns", a.factors.concerns, "neg")}
      </div>
    </Panel>
  );
}

function Block({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <h3 className="text-[13px] text-ink-400">{title}</h3>
      <ul className="mt-1.5 space-y-1.5 text-[14px] leading-snug text-ink-100">
        {items.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
    </div>
  );
}

export function Thesis({ report }: { report: Json | null }) {
  const { mode } = useMode();
  if (!report?.thesis) return null;
  const t = report.thesis;
  const beginner = mode === "beginner";
  return (
    <Panel title={beginner ? "Why it might be worth it, and what could go wrong" : "Investment thesis"}
           info="Written by KOI's research agent from the calculated figures and its risk checks.">
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-5">
          <Block title={beginner ? "Reasons to consider it" : "Why might it be worth considering?"} items={t.why_consider} />
          <Block title={beginner ? "What kind of business it is" : "What makes this business attractive?"} items={[t.what_makes_it_attractive]} />
          <Block title="Weaknesses" items={t.weaknesses.length ? t.weaknesses : ["No major weaknesses flagged."]} />
        </div>
        <div className="space-y-5">
          <Block title={beginner ? "What could change the picture" : "What could affect future performance?"}
                 items={t.future_drivers.length ? t.future_drivers : ["No forecast available."]} />
          <Block title={beginner ? "What to keep an eye on" : "What should an investor monitor?"}
                 items={t.monitor.map((m: Json) => (beginner ? m.label : `${m.label} — ${m.why}`))} />
          {t.conflicts.length > 0 && (
            <div className="rounded-md bg-warn-dim p-3">
              <h3 className="text-[13px] font-medium text-warn">Signals that point different ways</h3>
              <ul className="mt-1 space-y-1 text-[13px] text-ink-100">
                {t.conflicts.map((c: string) => <li key={c}>{c}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}

// Beginner only: what to do with the verdict, as a short checklist built from this company's data.
export function WhatItMeans({ a, report }: { a: Json; report: Json | null }) {
  if (!report?.thesis) return null;
  const t = report.thesis;
  const watch = t.monitor.filter((m: Json) => m.metric).slice(0, 3).map((m: Json) => m.label.toLowerCase());
  const steps = [
    t.should_i_consider.plain,
    a.outlook.valuation_verdict === "expensive"
      ? "Even a strong company can be a poor investment if you pay too much. Waiting for a lower price is a valid choice."
      : null,
    watch.length ? `If you invest, check ${watch.join(", ")} each time the company reports results.` : null,
    "Read the latest annual report or results presentation on nseindia.com before you decide.",
    "Only invest money you will not need for at least five years, and spread it across several companies.",
  ].filter(Boolean) as string[];
  return (
    <Panel title="What does this mean for me?">
      <ul className="space-y-2 text-[14px] leading-snug text-ink-100">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-3">
            <span className="mt-[7px] h-1 w-1 flex-none rounded-full bg-ink-400" />
            <span>{s}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function Findings({ report }: { report: Json | null }) {
  const { mode, atLeast } = useMode();
  const open = useEvidence();
  const fs: Json[] = report?.findings ?? [];
  return (
    <Panel title={mode === "beginner" ? "Warning signs we checked" : "Risk investigations"}
           info="Warning signals found in the numbers, each followed up by a deeper check. Every check uses only calculated figures.">
      {fs.length === 0 ? (
        <p className="text-[14px] text-ink-300">No warning signals were triggered by the available data.</p>
      ) : (
        <ul className="divide-y divide-ink-700">
          {fs.map((f, i) => (
            <li key={i}>
              <button
                onClick={() => open({ title: f.title, plain: f.explanation, detail: `Triggered by: ${f.trigger}`, inputs: f.evidence })}
                className="group grid w-full gap-1 py-3 text-left sm:grid-cols-[112px_1fr]"
              >
                <span><Badge tone={f.severity === "concern" ? "neg" : "warn"}>{f.severity === "concern" ? "concern" : "watch"}</Badge></span>
                <span>
                  <span className="text-[14px] text-ink-100 group-hover:underline group-hover:decoration-ink-600 group-hover:underline-offset-4">{f.title}</span>
                  <span className="mt-0.5 block text-[13px] text-ink-300">{f.explanation}</span>
                  {atLeast("advanced") && <span className="mt-0.5 block text-[12px] text-ink-400">tool {f.tool} · trigger: {f.trigger}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function Statements({ report }: { report: Json | null }) {
  const { atLeast } = useMode();
  const ss: Json[] = report?.statements ?? [];
  if (!ss.length) return null;
  return (
    <Panel title="What the numbers say" info="Select any line to see the figures, periods and formula behind it.">
      <div className="-mx-2">
        {ss.map((s, i) => <Statement key={i} s={s} showDetail={atLeast("intermediate")} />)}
      </div>
    </Panel>
  );
}

export function Performance({ a, prices }: { a: Json; prices: Json[] | null }) {
  const s = a.series;
  const lender = ["bank", "nbfc", "insurance"].includes(a.profile);
  // One hue: the accent goes on the main series; the others are ink and grey.
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel title="Revenue" right={<span className="text-[12px] text-ink-400">{a.periods.annual.length} fiscal years · ₹ crore</span>}
             info="Total sales as reported. Bars appear only for years with reported data; the latest year is highlighted.">
        <MetricBars points={s.revenue ?? []} unit="INR" />
      </Panel>
      <Panel title="Net profit" right={<span className="text-[12px] text-ink-400">₹ crore</span>}
             info="Profit for shareholders after all costs, interest and tax.">
        <MetricBars points={s.net_income ?? []} unit="INR" />
      </Panel>
      <Panel title={lender ? "Returns" : "Margins and returns"} info="Percentages over time. Rising lines generally mean improving profitability.">
        <MetricLines
          unit="pct"
          series={(lender
            ? [{ key: "roe", label: "ROE", color: "var(--color-koi)" }, { key: "roa", label: "ROA", color: "var(--color-ink-300)" }]
            : [
                { key: "roce", label: "ROCE", color: "var(--color-koi)" },
                { key: "roe", label: "ROE", color: "var(--color-ink-100)" },
                { key: "operating_margin", label: "Operating margin", color: "var(--color-ink-400)" },
              ]
          ).map((x) => ({ ...x, points: s[x.key] ?? [] }))}
        />
      </Panel>
      <Panel title="Share price" right={<span className="text-[12px] text-ink-400">daily close · Yahoo Finance</span>}>
        {prices === null ? <div className="h-[180px] rounded bg-ink-800" /> : prices.length ? <PriceChart prices={prices} height={180} /> : <p className="text-[13px] text-ink-400">No price history stored.</p>}
      </Panel>
    </div>
  );
}