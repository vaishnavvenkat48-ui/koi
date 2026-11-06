"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EvidenceProvider } from "@/components/company/Evidence";
import { AgentTrace, ReportSections } from "@/components/company/ReportView";
import { Badge, ErrorBox, Skeleton } from "@/components/ui";
import { api, type Json } from "@/lib/api";
import { useMode } from "@/lib/mode";

export default function SavedReportPage({ id }: { id: string }) {
  const { mode, atLeast } = useMode();
  const [r, setR] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.savedReport(id, mode).then(setR).catch((e) => setErr(e.message));
  }, [id, mode]);
  if (err) return <ErrorBox message={err} />;
  if (!r) return <Skeleton className="h-96" />;
  return (
    <EvidenceProvider>
      <div className="space-y-4">
        <div>
          <Link href="/reports" className="text-[12px] text-ink-400 hover:text-ink-200">← Reports</Link>
          <h1 className="text-[22px] font-semibold tracking-tight">{r.company.name} — research report #{r.id}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-ink-400">
            Saved {new Date(r.created_at).toLocaleString()} · <Badge tone="info">{r.outlook.label}</Badge>
            <Badge>valuation {r.outlook.valuation_verdict}</Badge> <Badge>confidence {r.confidence.level}</Badge>
            <Link href={`/company/${encodeURIComponent(r.symbol)}`} className="text-info hover:underline">open live analysis →</Link>
          </p>
          <p className="mt-1 text-[11px] text-ink-500">This is a snapshot. Figures reflect the data available when it was saved.</p>
        </div>
        <ReportSections report={r} />
        {atLeast("advanced") && r.trace && <AgentTrace trace={r.trace} />}
      </div>
    </EvidenceProvider>
  );
}
