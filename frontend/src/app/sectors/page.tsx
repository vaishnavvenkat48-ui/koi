"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBox, Panel, Skeleton } from "@/components/ui";
import { api, type Json } from "@/lib/api";

export default function SectorsPage() {
  const [data, setData] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.sectors().then(setData).catch((e) => setErr(e.message));
  }, []);
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight">Sector discovery</h1>
        <p className="mt-1 text-[13px] text-ink-400">
          Each sector uses its own analysis profile. Banks are judged on returns and capital, not debt-to-equity; IT on margins
          and cash generation; manufacturers on capital efficiency and working capital.
        </p>
      </div>
      {err && <ErrorBox message={err} />}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {!data && Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        {data?.sectors.map((s: Json) => (
          <Link key={s.key} href={`/sectors/${s.key}`} className="panel p-4 transition-colors hover:border-ink-500">
            <div className="flex items-center justify-between">
              <p className="text-[14px] font-medium">{s.name}</p>
              <span className="text-[11px] text-ink-500">{s.companies} companies</span>
            </div>
            <p className="mt-1 text-[12px] text-ink-400">{s.description}</p>
            <p className="mt-2 text-[11px] text-ink-500">profile: {s.profile.replace("_", " ")}</p>
          </Link>
        ))}
      </div>
      <Panel title="About sector classification">
        <p className="text-[12px] text-ink-400">
          Sector groups and peer lists are a curated classification maintained in KOI (backend/koi/reference.py). Companies
          outside these groups are classified from the data source&apos;s industry field and compared with companies in the same
          industry that are already stored locally.
        </p>
      </Panel>
    </div>
  );
}
