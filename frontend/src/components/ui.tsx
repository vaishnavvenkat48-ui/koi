"use client";

import { useEffect, useRef, useState } from "react";
import { scoreTone, toneBg } from "@/lib/format";

export function Panel({ title, right, children, className = "", info }: {
  title?: React.ReactNode; right?: React.ReactNode; children: React.ReactNode; className?: string; info?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-ink-700 px-4 py-2.5">
          <h2 className="flex items-center gap-1.5 text-[14px] font-semibold text-ink-100">
            {title}
            {info && <InfoTip text={info} />}
          </h2>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-label="What does this mean?"
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-ink-600 text-[11px] leading-none text-ink-300 hover:border-ink-300"
      >
        i
      </button>
      {open && (
        <span className="absolute left-1/2 top-5 z-50 w-64 -translate-x-1/2 rounded-md bg-ink-800 p-2.5 text-[12px] font-normal leading-snug text-ink-100 shadow-[0_12px_28px_rgba(0,0,0,.35)]">
          {text}
        </span>
      )}
    </span>
  );
}

export function Badge({ tone = "none", children }: { tone?: string; children: React.ReactNode }) {
  const map: Record<string, string> = {
    pos: "bg-pos-dim text-pos border-pos/30",
    neg: "bg-neg-dim text-neg border-neg/30",
    warn: "bg-warn-dim text-warn border-warn/30",
    info: "bg-info-dim text-info border-info/30",
    koi: "bg-koi-dim text-koi border-koi/30",
    none: "bg-ink-800 text-ink-300 border-transparent",
  };
  return <span className={`inline-flex flex-none items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[12px] font-medium ${map[tone]}`}>{children}</span>;
}

// One score row: name, a word that says what the number means, the number, and a 2px track.
// The fill is ink; only a weak result (or a high risk) takes the negative colour, as a signal.
export function ScoreBar({ label, value, invert = false, info, hint, word }: {
  label: string; value: number | null | undefined; invert?: boolean; info?: string; hint?: string; word?: string;
}) {
  const tone = scoreTone(value, invert);
  const weak = tone === "neg";
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-1.5 text-[13px] text-ink-200">
          {label}
          {info && <InfoTip text={info} />}
        </span>
        <span className="flex items-baseline gap-2">
          {word && <span className={`text-[13px] ${weak ? "text-neg" : "text-ink-300"}`}>{word}</span>}
          <span className="num w-[52px] text-right text-[14px] text-ink-100">
            {value === null || value === undefined ? <span className="text-ink-400">—</span> : Math.round(value)}
            <span className="text-[12px] text-ink-400">/100</span>
          </span>
        </span>
      </div>
      <div className="mt-1.5 h-0.5 bg-ink-750">
        <div className={`h-full ${weak ? "bg-neg" : "bg-ink-200"}`} style={{ width: `${value ?? 0}%` }} />
      </div>
      {hint && <p className="mt-1 text-[12px] text-ink-400">{hint}</p>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`rounded bg-ink-800 ${className}`} aria-hidden />;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="panel flex items-start justify-between gap-4 border-neg/40 p-4 text-[13px]">
      <div>
        <p className="font-medium text-neg">Something went wrong</p>
        <p className="mt-1 text-ink-300">{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="rounded border border-ink-600 px-2.5 py-1 text-[12px] hover:bg-ink-800">Retry</button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md border border-dashed border-ink-700 p-4 text-center text-[12px] text-ink-400">{children}</div>;
}

export function Tabs<T extends string>({ tabs, value, onChange }: {
  tabs: { key: T; label: string }[]; value: T; onChange: (k: T) => void;
}) {
  return (
    <div className="flex gap-6 overflow-x-auto border-b border-ink-700" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={value === t.key}
          onClick={() => onChange(t.key)}
          className={`relative whitespace-nowrap py-2.5 text-[14px] transition-colors ${
            value === t.key ? "text-ink-100" : "text-ink-400 hover:text-ink-200"
          }`}
        >
          {t.label}
          {/* the selection: a 1px accent line exactly as wide as the label, on the rule */}
          {value === t.key && <span className="absolute inset-x-0 -bottom-px h-px bg-koi" />}
        </button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange, size = "sm" }: {
  options: { key: T; label: string }[]; value: T; onChange: (k: T) => void; size?: "sm" | "xs";
}) {
  return (
    <div className="inline-flex gap-4" role="radiogroup">
      {options.map((o) => (
        <button
          key={o.key}
          role="radio"
          aria-checked={value === o.key}
          onClick={() => onChange(o.key)}
          className={`relative ${size === "xs" ? "py-1 text-[12px]" : "py-1.5 text-[13px]"} transition-colors ${
            value === o.key ? "text-ink-100 after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-koi" : "text-ink-400 hover:text-ink-200"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Dot({ tone }: { tone: string }) {
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${toneBg[tone] ?? "bg-ink-500"}`} />;
}

export function Modal({ open, onClose, title, children }: {
  open: boolean; onClose: () => void; title: React.ReactNode; children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[8vh]" onClick={onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        className="max-h-[80vh] w-full max-w-3xl overflow-auto rounded-md bg-ink-900 shadow-[0_12px_28px_rgba(0,0,0,.45)] outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 flex items-center justify-between border-b border-ink-700 bg-ink-900 px-5 py-3">
          <h3 className="text-[14px] font-medium">{title}</h3>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-100" aria-label="Close"><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg></button>
        </header>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
