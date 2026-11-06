"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AdvancedAnalytics, MetricsGrid } from "@/components/company/Metrics";
import { EvidenceProvider } from "@/components/company/Evidence";
import { FinancialsView } from "@/components/company/Financials";
import { ForecastView } from "@/components/company/Forecast";
import { Factors, Findings, OutlookCard, Performance, Statements, Thesis, WhatItMeans } from "@/components/company/Overview";
import { PeerTable } from "@/components/company/Peers";
import { ReportView } from "@/components/company/ReportView";
import { ValuationView } from "@/components/company/Valuation";
import { Badge, Dot, ErrorBox, Panel, Skeleton, Tabs } from "@/components/ui";
import { api, type Json, type Mode } from "@/lib/api";
import { ago, fy, inr, price } from "@/lib/format";
import { useMode } from "@/lib/mode";

type Tab = "overview" | "performance" | "metrics" | "valuation" | "peers" | "forecast" | "financials" | "report";

const TABS: { key: Tab; label: string; min: Mode }[] = [
  { key: "overview", label: "Overview", min: "beginner" },
  { key: "performance", label: "Performance", min: "beginner" },
  { key: "metrics", label: "Metrics", min: "intermediate" },
  { key: "valuation", label: "Valuation", min: "beginner" },
  { key: "peers", label: "Peers", min: "beginner" },
  { key: "forecast", label: "Scenarios", min: "beginner" },
  { key: "financials", label: "Financial statements", min: "advanced" },
  { key: "report", label: "Research report", min: "beginner" },
];

export default function CompanyPage({ symbol: routeParam }: { symbol: string }) {
  const symbol = decodeURIComponent(routeParam).toUpperCase();
  const { mode, atLeast } = useMode();
  const [tab, setTabState] = useState<Tab>("overview");
  // The open tab lives in the URL (?tab=) so a view can be linked or reloaded.
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab") as Tab | null;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- read the initial tab from the URL
    if (t && TABS.some((x) => x.key === t)) setTabState(t);
  }, []);
  const setTab = (t: Tab) => {
    setTabState(t);
    const u = new URL(window.location.href);
    u.searchParams.set("tab", t);
    window.history.replaceState(null, "", u);
  };
  const [status, setStatus] = useState<Json | null>(null);
  const [analysis, setAnalysis] = useState<Json | null>(null);
  const [report, setReport] = useState<Json | null>(null);
  const [prices, setPrices] = useState<Json[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watched, setWatched] = useState(false);
  const peersLoaded = useRef(-1);
  const modeRef = useRef(mode);
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  const loadAnalysis = useCallback(async () => {
    const [a, r] = await Promise.all([api.analysis(symbol), api.report(symbol, modeRef.current)]);
    setAnalysis(a);
    setReport(r);
    return a;
  }, [symbol]);

  // Kick off ingestion (P0 + peer prefetch) and poll until the company and its peers are loaded.
  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset when the symbol changes
    setAnalysis(null);
    setReport(null);
    setPrices(null);
    setError(null);
    setStatus(null);
    peersLoaded.current = -1;

    const poll = async () => {
      try {
        const st = await api.status(symbol);
        if (stop) return;
        setStatus(st);
        const job = st.job?.status;
        const loaded = st.peers.filter((p: Json) => p.has_data).length;
        if (st.freshness.has_data && (peersLoaded.current !== loaded)) {
          peersLoaded.current = loaded;
          await loadAnalysis();
          api.prices(symbol).then((p) => !stop && setPrices(p.prices)).catch(() => setPrices([]));
        }
        if (job === "error" && !st.freshness.has_data) {
          setError(st.job?.result?.message ?? "Data source returned no data for this symbol.");
          return;
        }
        const peersBusy = st.peers.some((p: Json) => ["queued", "running"].includes(p.job?.status));
        if (!st.freshness.has_data || ["queued", "running"].includes(job) || peersBusy) {
          timer = setTimeout(poll, 3000);
        }
      } catch (e) {
        if (!stop) setError((e as Error).message);
      }
    };
    api.analyze(symbol).then(poll).catch((e) => setError(e.message));
    api.watchlist().then((w) => !stop && setWatched(w.items.some((i: Json) => i.symbol === symbol))).catch(() => {});
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [symbol, loadAnalysis]);

  // Reports adapt to the interface mode.
  useEffect(() => {
    if (!analysis?.ready) return;
    api.report(symbol, mode).then(setReport).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // Keep the selected tab valid when switching to a simpler mode.
  const visibleTabs = TABS.filter((t) => atLeast(t.min));
  const tabVisible = visibleTabs.some((t) => t.key === tab);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fall back to a tab available in this mode
    if (!tabVisible) setTabState("overview");
  }, [tabVisible]);

  const refresh = async () => {
    setError(null);
    await api.analyze(symbol, true);
    peersLoaded.current = -1;
    setStatus(await api.status(symbol));
    const wait = async () => {
      const st = await api.status(symbol);
      setStatus(st);
      if (["queued", "running"].includes(st.job?.status)) setTimeout(wait, 2500);
      else await loadAnalysis();
    };
    setTimeout(wait, 1500);
  };

  const toggleWatch = async () => {
    if (watched) await api.watchRemove(symbol);
    else await api.watchAdd(symbol);
    setWatched(!watched);
  };

  const c = analysis?.company;
  return (
    <EvidenceProvider>
      <div className="space-y-6">
        <Header symbol={symbol} c={c} a={analysis} status={status} watched={watched} onWatch={toggleWatch} onRefresh={refresh} />
        {error && <ErrorBox message={error} onRetry={refresh} />}
        {!analysis?.ready && !error && <Loading status={status} analysis={analysis} />}
        {analysis?.ready && (
          <>
            <Tabs tabs={visibleTabs} value={tab} onChange={setTab} />
            {tab === "overview" && (
              <div className="space-y-6">
                <OutlookCard a={analysis} report={report} />
                <Factors a={analysis} />
                <div className="grid items-start gap-6 lg:grid-cols-2">
                  <div className="space-y-6">
                    {mode === "beginner" && <WhatItMeans a={analysis} report={report} />}
                    <Findings report={report} />
                  </div>
                  <Statements report={report} />
                </div>
                <Thesis report={report} />
              </div>
            )}
            {tab === "performance" && (
              <div className="space-y-4">
                <Performance a={analysis} prices={prices} />
                {atLeast("advanced") && <AdvancedAnalytics a={analysis} />}
              </div>
            )}
            {tab === "metrics" && <MetricsGrid a={analysis} />}
            {tab === "valuation" && <ValuationView a={analysis} symbol={symbol} />}
            {tab === "peers" && <PeerTable peers={analysis.peers} symbol={symbol} />}
            {tab === "forecast" && <ForecastView a={analysis} />}
            {tab === "financials" && <FinancialsView symbol={symbol} />}
            {tab === "report" && report?.ready && (
              <ReportView symbol={symbol} report={report} onRefresh={async (llm) => setReport(await api.report(symbol, mode, llm))} />
            )}
            <DataFooter a={analysis} />
          </>
        )}
      </div>
    </EvidenceProvider>
  );
}

function Header({ symbol, c, a, status, watched, onWatch, onRefresh }: {
  symbol: string; c: Json; a: Json; status: Json; watched: boolean; onWatch: () => void; onRefresh: () => void;
}) {
  const fresh = a?.freshness ?? status?.freshness;
  const job = status?.job?.status;
  const busy = job === "queued" || job === "running";
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-[22px] font-semibold leading-tight sm:text-[26px]">{c?.name ?? symbol}</h1>
          <Badge tone="none">NSE: {symbol}</Badge>
          {c?.isin && <span className="num text-[11px] text-ink-500">{c.isin}</span>}
        </div>
        <p className="mt-1 text-[12px] text-ink-400">
          {[c?.sector, c?.industry].filter(Boolean).join(" · ") || "Sector pending"}
          {a?.profile && <span className="ml-2 text-ink-500">analysis profile: {a.profile.replace("_", " ")}</span>}
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-5">
        {c?.price != null && (
          <div>
            <p className="label">Price</p>
            <p className="num text-[18px]">{price(c.price)}</p>
          </div>
        )}
        {c?.market_cap != null && (
          <div>
            <p className="label">Market cap</p>
            <p className="num text-[18px]">{inr(c.market_cap, { compact: true })}</p>
          </div>
        )}
        <div>
          <p className="label">Latest period</p>
          <p className="num text-[13px]">{fy(fresh?.latest_annual_period)} <span className="text-ink-500">annual</span></p>
          {fresh?.latest_quarterly_period && <p className="num text-[11px] text-ink-500">{fresh.latest_quarterly_period} quarterly</p>}
        </div>
        <div>
          <p className="label">Data freshness</p>
          <p className="flex items-center gap-1.5 text-[12px]">
            <Dot tone={busy ? "info" : fresh?.stale ? "warn" : fresh?.has_data ? "pos" : "none"} />
            {busy ? "Updating…" : fresh?.has_data ? `retrieved ${ago(fresh.retrieved_at)}` : "not loaded"}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={onWatch} className={`rounded border px-2.5 py-1 text-[12px] ${watched ? "border-koi/50 text-koi" : "border-ink-600 hover:bg-ink-800"}`}>
            {watched ? "On watchlist" : "Add to watchlist"}
          </button>
          <button onClick={onRefresh} disabled={busy} className="rounded border border-ink-600 px-2.5 py-1 text-[12px] hover:bg-ink-800 disabled:opacity-50">
            Refresh data
          </button>
        </div>
      </div>
    </div>
  );
}

function Loading({ status, analysis }: { status: Json; analysis: Json }) {
  const job = status?.job?.status;
  const steps = [
    { label: "Identify company & sector", done: !!status },
    { label: "Retrieve financial statements (P0)", done: !!status?.freshness?.has_data, active: job === "queued" || job === "running" },
    { label: "Prefetch competitors in background (P1/P2)", done: false, active: !!status?.freshness?.has_data },
    { label: "Run analysis engine & research agent", done: !!analysis?.ready },
  ];
  return (
    <Panel title="Analysing…">
      <ol className="space-y-2">
        {steps.map((s) => (
          <li key={s.label} className="flex items-center gap-2 text-[13px]">
            <Dot tone={s.done ? "pos" : s.active ? "info" : "none"} />
            <span className={s.done ? "text-ink-200" : s.active ? "text-ink-100" : "text-ink-500"}>{s.label}</span>
            {s.active && !s.done && <span className="text-[11px] text-ink-500">working…</span>}
          </li>
        ))}
      </ol>
      {analysis && !analysis.ready && analysis.reason && <p className="mt-3 text-[12px] text-ink-400">{analysis.reason}</p>}
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        <Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" />
      </div>
    </Panel>
  );
}

function DataFooter({ a }: { a: Json }) {
  return (
    <details className="panel px-4 py-3 text-[12px] text-ink-400">
      <summary className="cursor-pointer text-ink-300">Data sources & limitations</summary>
      <ul className="mt-2 space-y-1">
        {a.data_limitations.map((l: string) => <li key={l}>• {l}</li>)}
        <li>• Periods: {a.periods.annual.map(fy).join(", ")} (annual); {a.periods.quarterly.length} quarterly period(s). Consolidation: {a.consolidation.join(", ")}.</li>
        <li>• Market data as of {a.company.price_as_of} ({a.company.market_source}).</li>
      </ul>
    </details>
  );
}
