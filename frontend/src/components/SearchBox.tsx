"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type Json } from "@/lib/api";

const RECENT_KEY = "koi.recentSearches";

export function SearchBox({ large = false, autoFocus = false }: { large?: boolean; autoFocus?: boolean }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Json[]>([]);
  const [recent, setRecent] = useState<Json[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from localStorage after mount
      setRecent(JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]"));
    } catch {
      setRecent([]);
    }
  }, []);

  // "/" focuses the global search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const term = q.trim();
    if (!term) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clear stale results when the query is emptied
      setResults([]);
      return;
    }
    const ctrl = { cancelled: false };
    const t = setTimeout(async () => {
      try {
        const r = await api.search(term);
        if (!ctrl.cancelled) {
          setResults(r.results);
          setActive(0);
          setError(null);
        }
      } catch (e) {
        if (!ctrl.cancelled) setError((e as Error).message);
      }
    }, 160);
    return () => {
      ctrl.cancelled = true;
      clearTimeout(t);
    };
  }, [q]);

  function go(item: Json) {
    const next = [item, ...recent.filter((r) => r.symbol !== item.symbol)].slice(0, 6);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next.map((r) => ({ symbol: r.symbol, name: r.name }))));
    setRecent(next);
    setOpen(false);
    setQ("");
    router.push(`/company/${encodeURIComponent(item.symbol)}`);
  }

  const list = q.trim() ? results : recent;

  return (
    <div className="relative w-full">
      <div
        className={`flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-900 px-3 transition-colors focus-within:border-koi ${
          large ? "h-12" : "h-9"
        }`}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="shrink-0 text-ink-400" aria-hidden>
          <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
          <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          ref={inputRef}
          autoFocus={autoFocus}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, list.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && list[active]) {
              go(list[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
              inputRef.current?.blur();
            }
          }}
          placeholder="Search company, NSE symbol or ISIN"
          aria-label="Search companies"
          className={`w-full bg-transparent outline-none focus-visible:outline-none placeholder:text-ink-400 ${large ? "text-[15px]" : "text-[13px]"}`}
        />
        {!large && <kbd className="hidden rounded border border-ink-600 px-1.5 text-[11px] text-ink-400 sm:block">/</kbd>}
      </div>
      {open && (list.length > 0 || error) && (
        <ul className="absolute z-40 mt-1 max-h-96 w-full overflow-auto rounded-lg border border-ink-600 bg-ink-850 py-1 shadow-2xl">
          {!q.trim() && <li className="label px-3 py-1.5">Recent searches</li>}
          {error && <li className="px-3 py-2 text-[12px] text-neg">{error}</li>}
          {list.map((r, i) => (
            <li key={r.symbol}>
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => go(r)}
                onMouseEnter={() => setActive(i)}
                className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left ${i === active ? "bg-ink-750" : ""}`}
              >
                <span className="min-w-0">
                  <span className="block truncate text-[13px] text-ink-100">{r.name}</span>
                  <span className="block truncate text-[11px] text-ink-400">
                    {[r.industry ?? r.sector, r.isin].filter(Boolean).join(" · ") || "NSE"}
                  </span>
                </span>
                <span className="num shrink-0 text-[12px] text-ink-300">{r.symbol}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
