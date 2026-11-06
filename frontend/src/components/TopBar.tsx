"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMode } from "@/lib/mode";
import { SearchBox } from "./SearchBox";

// Icon rail destinations. Each icon has a visible tooltip and an accessible name.
const NAV = [
  { href: "/", label: "Discover", d: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm9 16-3.5-3.5" },
  { href: "/sectors", label: "Sectors", d: "M4 5h7v7H4zM13 5h7v4h-7zM13 11h7v8h-7zM4 14h7v5H4z" },
  { href: "/compare", label: "Compare", d: "M6 20V9M12 20V4M18 20v-7" },
  { href: "/reports", label: "Saved reports", d: "M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5" },
];
const UTIL = [{ href: "/methodology", label: "Methodology", d: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-5v.01M12 8a2 2 0 0 1 1 3.7c-.6.4-1 .8-1 1.3" }];

export function Logo({ withName = false }: { withName?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2" aria-label="KOI home">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden>
        <path d="M6 17c3.5-7 10.5-9.5 16.5-5.8C20.2 12.5 19 14.6 19 17s1.2 4.5 3.5 5.8C16.5 26.5 9.5 24 6 17Z" fill="var(--color-koi)" />
        <circle cx="11" cy="16" r="1.3" fill="var(--color-ink-950)" />
        <path d="M22.5 11.2 27 8v18l-4.5-3.2" fill="none" stroke="var(--color-koi)" strokeWidth="1.6" strokeLinejoin="round" />
      </svg>
      {withName && <span className="text-[15px] font-semibold">KOI</span>}
    </Link>
  );
}

function RailLink({ href, label, d, active }: { href: string; label: string; d: string; active: boolean }) {
  return (
    <Link
      href={href}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      className="group relative flex h-11 w-full items-center justify-center"
    >
      {/* the selection mark: a 1px accent line on the rail's edge */}
      {active && <span className="absolute right-0 top-2 h-7 w-px bg-koi" />}
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
           strokeLinecap="round" strokeLinejoin="round" aria-hidden
           className={active ? "text-ink-100" : "text-ink-400 group-hover:text-ink-200"}>
        <path d={d} />
      </svg>
      <span className="pointer-events-none absolute left-full z-50 ml-2 hidden whitespace-nowrap rounded bg-ink-800 px-2 py-1 text-[12px] text-ink-100 shadow-[var(--shadow,0_12px_28px_rgba(0,0,0,.2))] group-hover:block group-focus-visible:block">
        {label}
      </span>
    </Link>
  );
}

export function Rail() {
  const path = usePathname();
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <>
      <nav aria-label="Main" className="fixed inset-y-0 left-0 z-40 hidden w-[55px] flex-col items-center border-r border-ink-700 bg-ink-950 py-3 md:flex">
        <Logo />
        <div className="mt-6 flex w-full flex-col">
          {NAV.map((n) => <RailLink key={n.href} {...n} active={isActive(n.href)} />)}
        </div>
        <div className="mt-auto flex w-full flex-col">
          {UTIL.map((n) => <RailLink key={n.href} {...n} active={isActive(n.href)} />)}
        </div>
      </nav>
      {/* Phone: the rail becomes a bottom bar with short labels. */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-ink-700 bg-ink-950 md:hidden">
        {[...NAV, ...UTIL].map((n) => {
          const active = isActive(n.href);
          return (
            <Link key={n.href} href={n.href} aria-current={active ? "page" : undefined}
                  className={`relative flex h-14 flex-col items-center justify-center gap-0.5 text-[11px] ${active ? "text-ink-100" : "text-ink-400"}`}>
              {active && <span className="absolute inset-x-5 top-0 h-px bg-koi" />}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d={n.d} />
              </svg>
              {n.label.replace("Saved reports", "Reports").replace("Methodology", "Method")}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

const MODES = [
  { key: "beginner", label: "Beginner" },
  { key: "intermediate", label: "Intermediate" },
  { key: "advanced", label: "Advanced" },
] as const;

export function TopBar() {
  const { mode, setMode } = useMode();
  const path = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-ink-700 bg-ink-950">
      <div className="flex h-12 items-center gap-4 px-4 md:px-8">
        <span className="md:hidden"><Logo withName /></span>
        <span className="hidden text-[13px] text-ink-400 md:block">KOI · NSE research</span>
        <div className="ml-auto w-full max-w-[420px]">{path !== "/" && <SearchBox />}</div>
        <label className="shrink-0 sm:hidden">
          <span className="sr-only">Detail level</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}
                  className="h-8 rounded-full border border-ink-600 bg-ink-950 px-3 text-[13px] text-ink-100">
            {MODES.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </label>
        <div role="radiogroup" aria-label="Detail level" className="hidden shrink-0 items-center gap-3 sm:flex">
          {MODES.map((m) => (
            <button
              key={m.key}
              role="radio"
              aria-checked={mode === m.key}
              onClick={() => setMode(m.key)}
              className={`relative h-12 text-[13px] transition-colors ${mode === m.key ? "text-ink-100" : "text-ink-400 hover:text-ink-200"}`}
            >
              {m.label}
              {mode === m.key && <span className="absolute inset-x-0 bottom-0 h-px bg-koi" />}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
