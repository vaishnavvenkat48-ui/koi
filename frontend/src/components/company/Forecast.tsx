"use client";

import type { Json } from "@/lib/api";
import { inr, pct, times } from "@/lib/format";
import { useMode } from "@/lib/mode";
import { Badge, Panel } from "../ui";
import { ScenarioChart } from "./Charts";

export function ForecastView({ a }: { a: Json }) {
  const { atLeast } = useMode();
  const fc = a.forecast;
  const r = fc.revenue;
  const e = fc.earnings;
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-warn/30 bg-warn-dim px-4 py-2.5 text-[12px] text-ink-200">{fc.disclaimer}</div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Revenue scenarios" info="Base case uses the model with the lowest backtest error. Bear and bull shift growth by one standard deviation of historical growth.">
          <ScenarioChart forecast={r} />
          {r.available && <ScenarioTable rows={["bear", "base", "bull"].map((k) => ({ k, growth: r.scenarios[k].growth, end: r.scenarios[k].path.at(-1) }))} />}
        </Panel>
        <Panel title="Profit scenarios" info="Profit = revenue scenario × margin scenario (bear: lowest historical net margin; base: 3-year average; bull: highest).">
          {e.available ? (
            <>
              <ScenarioChart forecast={{ available: true, history: a.series.net_income.filter((p: Json) => p.value != null).map((p: Json) => ({ period: p.period, value: p.value })), scenarios: e.scenarios }} />
              <ScenarioTable rows={["bear", "base", "bull"].map((k) => ({ k, margin: e.margins[k], end: e.scenarios[k].path.at(-1) }))} />
            </>
          ) : <p className="text-[12px] text-ink-500">{e.reason}</p>}
        </Panel>
      </div>
      {atLeast("intermediate") && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Cash flow & leverage scenarios">
            <table className="w-full text-[12px]">
              <thead className="text-ink-400">
                <tr><th className="py-1 text-left font-normal">Scenario</th><th className="py-1 text-right font-normal">Operating cash flow (yr {fc.horizon_years})</th><th className="py-1 text-right font-normal">Debt-to-equity (yr {fc.horizon_years})</th></tr>
              </thead>
              <tbody className="num">
                {["bear", "base", "bull"].map((k) => (
                  <tr key={k} className="border-t border-ink-800">
                    <td className="py-1 font-sans capitalize text-ink-300">{k}</td>
                    <td className="py-1 text-right">{fc.cash_flow.available ? inr(fc.cash_flow.scenarios[k].path.at(-1)) : "—"}</td>
                    <td className="py-1 text-right">{fc.leverage.available ? times(fc.leverage.scenarios[k].path.at(-1)) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="mt-3 space-y-1 text-[11px] text-ink-500">
              {fc.cash_flow.available && <li>• {fc.cash_flow.assumptions.all}</li>}
              {fc.leverage.available && <li>• Debt {fc.leverage.assumptions.debt}; equity {fc.leverage.assumptions.equity}.</li>}
              {!fc.cash_flow.available && <li>• Cash flow: {fc.cash_flow.reason}</li>}
              {!fc.leverage.available && <li>• Leverage: {fc.leverage.reason}</li>}
            </ul>
          </Panel>
          {r.available && (
            <Panel title="Model backtest" info="Rolling-origin one-step-ahead forecasts on past data. MAPE = mean absolute percentage error. Naive = 'next year equals this year'.">
              <table className="w-full text-[12px]">
                <thead className="text-ink-400">
                  <tr><th className="py-1 text-left font-normal">Model</th><th className="py-1 text-right font-normal">Revenue MAPE</th><th className="py-1 text-right font-normal">Profit MAPE</th></tr>
                </thead>
                <tbody className="num">
                  {["naive", "drift", "trend"].map((m) => (
                    <tr key={m} className="border-t border-ink-800">
                      <td className="py-1 font-sans text-ink-300">{m}{m === r.model && <Badge tone="koi">selected</Badge>}</td>
                      <td className="py-1 text-right">{pct(r.backtest.mape[m])}</td>
                      <td className="py-1 text-right">{fc.earnings_direct.available ? pct(fc.earnings_direct.backtest.mape[m]) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[11px] text-ink-400">
                {r.backtest.n_tests} backtest point(s); reliability <span className="text-warn">{r.reliability}</span>. {r.reliability_note}{" "}
                {r.beats_naive ? "Selected model beat the naive baseline." : "Selected model did not beat the naive baseline; treat trends with extra caution."}
              </p>
              <p className="mt-1 text-[11px] text-ink-500">{r.assumptions.base}. {r.assumptions.bear_bull}.</p>
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}

function ScenarioTable({ rows }: { rows: { k: string; growth?: number; margin?: number; end: number }[] }) {
  const tone: Record<string, string> = { bear: "text-neg", base: "text-koi", bull: "text-pos" };
  return (
    <div className="mt-3 grid grid-cols-3 gap-2">
      {rows.map((r) => (
        <div key={r.k} className="panel-2 p-2">
          <p className={`text-[11px] capitalize ${tone[r.k]}`}>{r.k}</p>
          <p className="num text-[14px]">{inr(r.end)}</p>
          <p className="num text-[11px] text-ink-500">
            {r.growth !== undefined ? `${pct(r.growth, 1, true)} / yr` : `margin ${pct(r.margin)}`}
          </p>
        </div>
      ))}
    </div>
  );
}
