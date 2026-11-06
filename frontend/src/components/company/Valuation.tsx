"use client";

import { useState } from "react";
import { api, type Json } from "@/lib/api";
import { fy, inr, pct, price, times } from "@/lib/format";
import { useMode } from "@/lib/mode";
import { Badge, Panel } from "../ui";
import { MetricLines } from "./Charts";
import { useEvidence } from "./Evidence";

const MULT_INFO: Record<string, string> = {
  pe: "Price-to-earnings: how many years of current profit you pay for. Lower is cheaper, but compare with growth and peers.",
  pb: "Price-to-book: price relative to the company's net worth. Most useful for banks and asset-heavy businesses.",
  ev_ebitda: "Enterprise value (market cap + debt − cash) relative to operating cash profit. Accounts for debt.",
  earnings_yield: "Profit as a percentage of market value (inverse of P/E). Compare with fixed-deposit or bond yields.",
  ps: "Price relative to sales. Useful when profits are temporarily depressed.",
};

export function ValuationView({ a, symbol }: { a: Json; symbol: string }) {
  const { atLeast } = useMode();
  const open = useEvidence();
  const cur = a.valuation.current;
  const hist = a.valuation.historical;
  const med = a.peers.medians;
  return (
    <div className="space-y-4">
      <Panel title="Current valuation" right={<span className="text-[11px] text-ink-500">market data {cur.as_of?.slice(0, 10)} · {cur.source}</span>}>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          {["pe", "pb", "ev_ebitda", "earnings_yield", "ps"].map((k) => {
            const m = cur[k];
            if (!m) return null;
            const v = k === "earnings_yield" ? pct(m.value) : times(m.value, 1);
            const peer = med[k];
            return (
              <button key={k} disabled={!m.available}
                onClick={() => open({ title: m.label, plain: MULT_INFO[k], formula: m.formula, inputs: m.inputs })}
                className="panel-2 p-3 text-left enabled:hover:border-ink-500">
                <p className="text-[12px] text-ink-300">{m.label}</p>
                <p className="num text-[18px]">{m.available ? v : "—"}</p>
                <p className="text-[11px] text-ink-500">
                  {m.available ? (peer ? `peer median ${times(peer, 1)}` : "no peer median") : m.reason}
                </p>
              </button>
            );
          })}
        </div>
        <p className="mt-3 text-[12px] text-ink-400">
          Valuation verdict: <Badge tone={{ attractive: "pos", reasonable: "info", expensive: "neg" }[a.outlook.valuation_verdict as string] ?? "none"}>{a.outlook.valuation_verdict}</Badge>{" "}
          (score {a.scores.valuation.value ?? "n/a"}/100). Valuation is assessed separately from business quality.
        </p>
      </Panel>

      {hist.points?.length > 0 && (
        <Panel title="Historical valuation" info={hist.method}>
          <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
            <MetricLines unit="x" height={190} series={[
              { key: "pe", label: "P/E", color: "var(--color-koi)", points: hist.points.map((p: Json) => ({ period: p.period, value: p.pe })) },
              { key: "pb", label: "P/B", color: "var(--color-ink-300)", points: hist.points.map((p: Json) => ({ period: p.period, value: p.pb })) },
            ]} />
            <div className="space-y-2 text-[12px]">
              <p className="text-ink-400">Median P/E <span className="num ml-1 text-ink-100">{times(hist.median_pe, 1)}</span></p>
              <p className="text-ink-400">Median P/B <span className="num ml-1 text-ink-100">{times(hist.median_pb, 1)}</span></p>
              <p className="text-ink-400">Current P/E <span className="num ml-1 text-ink-100">{times(cur.pe?.value, 1)}</span></p>
              {hist.points.some((p: Json) => p.excluded) && (
                <p className="text-[11px] text-warn">
                  Excluded from medians: {hist.points.filter((p: Json) => p.excluded).map((p: Json) => fy(p.period)).join(", ")} (share count changed &gt;15%).
                </p>
              )}
            </div>
          </div>
        </Panel>
      )}

      {atLeast("intermediate") && <DCFPanel initial={a.valuation.dcf} symbol={symbol} editable={atLeast("advanced")} />}
    </div>
  );
}

const round2 = (v: number) => Math.round(v * 100) / 100;

function DCFPanel({ initial, symbol, editable }: { initial: Json; symbol: string; editable: boolean }) {
  const [dcf, setDcf] = useState<Json>(initial);
  const [form, setForm] = useState(() => ({
    risk_free: round2((initial.assumptions?.risk_free ?? 0.07) * 100),
    erp: round2((initial.assumptions?.equity_risk_premium ?? 0.06) * 100),
    terminal_growth: round2((initial.assumptions?.terminal_growth ?? 0.05) * 100),
    beta: round2(initial.assumptions?.beta_used ?? 1),
  }));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!initial.available) {
    return <Panel title="Discounted cash flow (DCF)"><p className="text-[13px] text-ink-400">Not available: {initial.reason}</p></Panel>;
  }
  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      setDcf(await api.dcf(symbol, { risk_free: form.risk_free / 100, erp: form.erp / 100, terminal_growth: form.terminal_growth / 100, beta: form.beta }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const as = dcf.assumptions ?? {};
  return (
    <Panel title="Discounted cash flow (DCF)" info={dcf.caveat ?? initial.caveat}>
      {!dcf.available ? <p className="text-[13px] text-ink-400">Not available: {dcf.reason}</p> : (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            <div className="flex items-end gap-6">
              <div>
                <p className="label">Estimated value / share</p>
                <p className="num text-[22px]">{price(dcf.value_per_share)}</p>
              </div>
              <div>
                <p className="label">Price</p>
                <p className="num text-[16px] text-ink-300">{price(dcf.price)}</p>
              </div>
              <div>
                <p className="label">Gap</p>
                <p className={`num text-[16px] ${dcf.margin_of_safety >= 0 ? "text-pos" : "text-neg"}`}>{pct(dcf.margin_of_safety, 1, true)}</p>
              </div>
            </div>
            <table className="w-full text-[12px]">
              <tbody className="[&_td]:py-1">
                {[
                  ["Base free cash flow", inr(as.base_fcf), as.base_fcf_method],
                  ["Stage-1 growth", pct(as.growth_stage1), as.growth_source],
                  ["Years high growth / fade", `${as.years_high_growth} / ${as.years_fade}`, ""],
                  ["Terminal growth", pct(as.terminal_growth), ""],
                  ["Cost of equity", pct(as.cost_of_equity), `rf ${pct(as.risk_free)} + β ${as.beta_used?.toFixed(2)} × ERP ${pct(as.equity_risk_premium)}`],
                  ["WACC", pct(as.wacc), `pre-tax cost of debt ${pct(as.cost_of_debt_pre_tax)}`],
                  ["Terminal value share of EV", pct(dcf.pv_terminal_share), ""],
                ].map(([l, v, n]) => (
                  <tr key={l} className="border-t border-ink-800">
                    <td className="text-ink-400">{l}</td>
                    <td className="num text-right text-ink-100">{v}</td>
                    <td className="pl-3 text-[11px] text-ink-500">{n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-ink-500">{as.beta_note}</p>
          </div>
          <div className="space-y-3">
            {editable && (
              <div className="panel-2 grid grid-cols-2 gap-2 p-3 sm:grid-cols-4">
                {([["risk_free", "Risk-free %"], ["erp", "Equity premium %"], ["terminal_growth", "Terminal g %"], ["beta", "Beta"]] as const).map(([k, l]) => (
                  <label key={k} className="text-[11px] text-ink-400">
                    {l}
                    <input type="number" step={k === "beta" ? 0.05 : 0.25} value={form[k]}
                      onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })}
                      className="num mt-1 w-full rounded border border-ink-600 bg-ink-900 px-2 py-1 text-[13px] text-ink-100 outline-none focus:border-ink-400" />
                  </label>
                ))}
                <button onClick={run} disabled={busy} className="col-span-full rounded bg-ink-700 py-1.5 text-[12px] hover:bg-ink-600 disabled:opacity-50">
                  {busy ? "Recalculating…" : "Recalculate DCF"}
                </button>
                {err && <p className="col-span-full text-[11px] text-neg">{err}</p>}
              </div>
            )}
            <p className="label">Sensitivity — value per share</p>
            <table className="num w-full text-[12px]">
              <thead>
                <tr className="text-ink-400">
                  <th className="py-1 text-left font-sans font-normal">WACC \ terminal g</th>
                  {[...new Set(dcf.sensitivity.map((x: Json) => x.terminal_growth))].map((g) => (
                    <th key={String(g)} className="py-1 text-right font-normal">{pct(g as number)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...new Set(dcf.sensitivity.map((x: Json) => x.wacc))].map((w) => (
                  <tr key={String(w)} className="border-t border-ink-800">
                    <td className="py-1 text-ink-400">{pct(w as number)}</td>
                    {dcf.sensitivity.filter((x: Json) => x.wacc === w).map((x: Json, i: number) => (
                      <td key={i} className={`py-1 text-right ${x.value_per_share && dcf.price && x.value_per_share > dcf.price ? "text-pos" : "text-ink-200"}`}>
                        {price(x.value_per_share)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-ink-500">{dcf.caveat}</p>
          </div>
        </div>
      )}
    </Panel>
  );
}
