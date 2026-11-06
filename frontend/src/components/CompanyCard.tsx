import Link from "next/link";
import type { Json } from "@/lib/api";
import { inr, price } from "@/lib/format";
import { Badge } from "./ui";

const OUTLOOK_TONE: Record<number, string> = { 1: "pos", 2: "pos", 3: "warn", 4: "neg", 5: "neg" };

export function CompanyCard({ c }: { c: Json }) {
  return (
    <Link
      href={`/company/${encodeURIComponent(c.symbol)}`}
      className="panel-2 group flex flex-col gap-2 p-3 transition-colors hover:border-ink-500"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium text-ink-100 group-hover:text-white">{c.name}</p>
          <p className="truncate text-[11px] text-ink-400">{c.industry ?? c.sector ?? "—"}</p>
        </div>
        <span className="num shrink-0 text-[11px] text-ink-300">{c.symbol}</span>
      </div>
      <div className="flex items-end justify-between">
        <div className="num text-[12px] text-ink-300">
          {c.price ? price(c.price) : <span className="text-ink-500">not loaded</span>}
          {c.market_cap ? <span className="ml-2 text-ink-500">{inr(c.market_cap, { compact: true })}</span> : null}
        </div>
        {c.summary && <Badge tone={OUTLOOK_TONE[c.summary.code] ?? "none"}>{shortOutlook(c.summary.code)}</Badge>}
      </div>
    </Link>
  );
}

export function shortOutlook(code: number): string {
  return ({ 1: "Strong", 2: "Positive", 3: "Mixed", 4: "Weakening", 5: "Concerns" } as Record<number, string>)[code] ?? "—";
}
export { OUTLOOK_TONE };
