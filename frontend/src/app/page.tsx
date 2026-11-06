"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SearchBox } from "@/components/SearchBox";
import { Badge, Empty, ErrorBox, Panel, Skeleton } from "@/components/ui";
import { api, type Json } from "@/lib/api";
import { ago, inr, pct, price } from "@/lib/format";

const OUTLOOK: Record<number, { word: string; tone: string }> = {
  1: { word: "Strong", tone: "pos" }, 2: { word: "Positive", tone: "pos" }, 3: { word: "Mixed", tone: "warn" },
  4: { word: "Weakening", tone: "neg" }, 5: { word: "Concerns", tone: "neg" },
};

export default function Home() {
  const [home, setHome] = useState<Json | null>(null);
  const [market, setMarket] = useState<Json | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api.home().then(setHome).catch((e) => setError(e.message));
    api.market().then(setMarket).catch(() => setMarket({ indices: [] }));
  };
  // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load
  useEffect(load, []);

  const recentSyms = new Set<string>((home?.recent ?? []).map((c: Json) => c.symbol as string));
  return (
    <div className="space-y-6">
      <section className="grid items-end gap-6 lg:grid-cols-[1fr_1fr]">
        <div>
          <h1 className="text-[26px] font-semibold leading-tight">Research a company</h1>
          <p className="mt-1 max-w-[52ch] text-[14px] text-ink-300">
            Is it financially strong, and is the price sensible? KOI checks the results, compares competitors and shows
            the numbers behind every answer.
          </p>
        </div>
        <div>
          <SearchBox large autoFocus />
          <p className="mt-2 text-[12px] text-ink-400">Company name, NSE symbol or ISIN. Press / to search from any page.</p>
        </div>
      </section>

      {error && <ErrorBox message={error} onRetry={load} />}

      <section aria-label="Market overview" className="panel grid grid-cols-2 divide-ink-700 lg:grid-cols-4 lg:divide-x">
        {!market
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="p-4"><Skeleton className="h-3 w-20" /><Skeleton className="mt-2 h-5 w-28" /></div>
            ))
          : market.indices.length === 0
            ? <p className="col-span-full p-4 text-[13px] text-ink-400">Market data is unavailable right now.</p>
            : market.indices.map((ix: Json) => (
                <div key={ix.key} className="p-4">
                  <p className="text-[13px] text-ink-400">{ix.name}</p>
                  {ix.available ? (
                    <>
                      <p className="num mt-0.5 text-[20px]">{ix.last.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</p>
                      <p className="num text-[12px] text-ink-300">
                        {pct(ix.change_1d, 2, true)} <span className="text-ink-400">today</span>
                        <span className="mx-1.5 text-ink-600">·</span>
                        {pct(ix.change_1y, 1, true)} <span className="text-ink-400">1 year</span>
                      </p>
                    </>
                  ) : <p className="mt-1 text-[13px] text-ink-400">—</p>}
                </div>
              ))}
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_360px]">
        <Panel className="min-w-0" title="Popular and recent companies" right={<Link href="/sectors" className="text-[12px] text-ink-400 hover:text-ink-100">Browse all by sector</Link>}>
          {!home ? <TableSkeleton /> : <CompanyTable rows={[...home.recent, ...home.popular.filter((c: Json) => !recentSyms.has(c.symbol))].slice(0, 13)} />}
        </Panel>
        <div className="min-w-0 space-y-6">
          <Panel title="Watchlist">
            {!home ? <Skeleton className="h-16" /> : home.watchlist.length === 0 ? (
              <Empty>Nothing on your watchlist yet. Use “Add to watchlist” on any company.</Empty>
            ) : <CompanyList rows={home.watchlist} />}
          </Panel>
          <Panel title="Saved reports" right={<Link href="/reports" className="text-[12px] text-ink-400 hover:text-ink-100">View all</Link>}>
            {!home ? <Skeleton className="h-16" /> : home.reports.length === 0 ? (
              <Empty>No saved reports yet. Save one from a company&apos;s report tab.</Empty>
            ) : (
              <ul className="divide-y divide-ink-700">
                {home.reports.slice(0, 5).map((r: Json) => (
                  <li key={r.id}>
                    <Link href={`/reports/${r.id}`} className="flex items-baseline justify-between gap-3 py-2 text-[13px] hover:text-ink-100">
                      <span className="truncate text-ink-200">{r.title.replace(" research report", "")}</span>
                      <span className="shrink-0 text-[12px] text-ink-400">{ago(r.created_at)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Browse by sector" right={<Link href="/sectors" className="text-[12px] text-ink-400 hover:text-ink-100">All sectors</Link>}>
            <ul className="columns-2 gap-4 text-[13px]">
              {(home?.sectors ?? []).map((s: Json) => (
                <li key={s.key} className="break-inside-avoid">
                  <Link href={`/sectors/${s.key}`} className="block py-1 text-ink-200 hover:text-ink-100 hover:underline hover:decoration-ink-600 hover:underline-offset-4">
                    {s.name}
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function CompanyTable({ rows }: { rows: Json[] }) {
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="w-full min-w-[620px] text-[13px]">
        <thead>
          <tr className="text-left text-[12px] text-ink-400">
            <th className="px-4 py-2 font-normal">Company</th>
            <th className="px-2 py-2 font-normal">Sector</th>
            <th className="px-2 py-2 text-right font-normal">Price</th>
            <th className="px-2 py-2 text-right font-normal">Market value</th>
            <th className="px-4 py-2 text-right font-normal">KOI outlook</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.symbol} className="group border-t border-ink-700 hover:bg-ink-850">
              <td className="px-4 py-2.5">
                <Link href={`/company/${encodeURIComponent(c.symbol)}`} className="block">
                  <span className="text-ink-100 group-hover:underline group-hover:decoration-ink-600 group-hover:underline-offset-4">{shortName(c.name)}</span>
                  <span className="num ml-2 text-[12px] text-ink-400">{c.symbol}</span>
                </Link>
              </td>
              <td className="max-w-[200px] truncate px-2 py-2.5 text-ink-300">{c.industry ?? c.sector ?? <span className="text-ink-400">—</span>}</td>
              <td className="num whitespace-nowrap px-2 py-2.5 text-right">{c.price ? price(c.price) : <span className="text-ink-400">—</span>}</td>
              <td className="num whitespace-nowrap px-2 py-2.5 text-right" title="1 lakh crore = ₹1 trillion">{c.market_cap ? inr(c.market_cap, { compact: true }) : <span className="text-ink-400">—</span>}</td>
              <td className="whitespace-nowrap px-4 py-2.5 text-right">
                {c.summary ? <Badge tone={OUTLOOK[c.summary.code]?.tone}>{OUTLOOK[c.summary.code]?.word}</Badge>
                  : <span className="text-[12px] text-ink-400">not analysed yet</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Editorial short name: the suffix every row shares adds nothing.
function shortName(name: string): string {
  return name.replace(/\s+(Limited|Ltd\.?)$/i, "");
}

function CompanyList({ rows }: { rows: Json[] }) {
  return (
    <ul className="divide-y divide-ink-700">
      {rows.map((c) => (
        <li key={c.symbol}>
          <Link href={`/company/${encodeURIComponent(c.symbol)}`} className="flex items-baseline justify-between gap-3 py-2 text-[13px]">
            <span className="truncate text-ink-100">{shortName(c.name)}</span>
            <span className="num shrink-0 text-ink-300">{c.price ? price(c.price) : "—"}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-5" />)}
    </div>
  );
}
