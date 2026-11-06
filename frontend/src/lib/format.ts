// Display formatting only. Values arrive from the backend already computed.

const CRORE = 1e7;

export function inr(v: number | null | undefined, opts: { compact?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const cr = v / CRORE;
  // 1 lakh crore = ₹1,00,000 crore = ₹1 trillion. Spelled out so beginners can read it.
  if (opts.compact && Math.abs(cr) >= 100000) return `₹${(cr / 100000).toLocaleString("en-IN", { maximumFractionDigits: 2 })} lakh Cr`;
  return `₹${cr.toLocaleString("en-IN", { maximumFractionDigits: Math.abs(cr) < 100 ? 1 : 0 })} Cr`;
}

export function price(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `₹${v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function pct(v: number | null | undefined, digits = 1, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = (v * 100).toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s}%`;
}

export function times(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}x`;
}

export function byUnit(v: number | null | undefined, unit: string): string {
  switch (unit) {
    case "pct":
      return pct(v);
    case "x":
      return times(v);
    case "days":
      return v === null || v === undefined ? "—" : `${Math.round(v)} d`;
    case "INR":
      return inr(v);
    case "INR/share":
      return price(v);
    case "shares":
      return v === null || v === undefined ? "—" : `${(v / CRORE).toLocaleString("en-IN", { maximumFractionDigits: 2 })} Cr`;
    default:
      return v === null || v === undefined ? "—" : v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }
}

export function fy(period: string | null | undefined): string {
  if (!period) return "—";
  const [y, m] = period.split("-");
  // Indian fiscal year ends in March: 2026-03-31 => FY26.
  if (m === "03") return `FY${y.slice(2)}`;
  return period;
}

export function quarter(period: string): string {
  const [y, m] = period.split("-").map(Number);
  // Indian FY quarters: Apr-Jun = Q1 ... Jan-Mar = Q4
  const q = m <= 3 ? 4 : m <= 6 ? 1 : m <= 9 ? 2 : 3;
  const fyYear = m <= 3 ? y : y + 1;
  return `Q${q} FY${String(fyYear).slice(2)}`;
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const h = (Date.now() - new Date(iso).getTime()) / 3.6e6;
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min ago`;
  if (h < 48) return `${Math.round(h)} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

export function scoreTone(v: number | null | undefined, invert = false): "pos" | "warn" | "neg" | "none" {
  if (v === null || v === undefined) return "none";
  const x = invert ? 100 - v : v;
  return x >= 65 ? "pos" : x >= 40 ? "warn" : "neg";
}

export const toneText: Record<string, string> = {
  pos: "text-pos",
  warn: "text-warn",
  neg: "text-neg",
  none: "text-ink-400",
  info: "text-info",
};
export const toneBg: Record<string, string> = {
  pos: "bg-pos",
  warn: "bg-warn",
  neg: "bg-neg",
  none: "bg-ink-600",
  info: "bg-info",
};
