import type { Metadata } from "next";
import { IBM_Plex_Mono, Public_Sans } from "next/font/google";
import { Suspense } from "react";
import { Rail, TopBar } from "@/components/TopBar";
import { ModeProvider } from "@/lib/mode";
import "./globals.css";

const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"], weight: ["400", "500", "600", "700"] });
const plexMono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "KOI — research Indian companies",
  description: "Evidence-backed research on NSE-listed companies: fundamentals, valuation, peers, risks and scenarios.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${publicSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="min-h-full">
        <ModeProvider>
          {/* usePathname() is runtime data in Next 16; the shell streams in after the static frame. */}
          <Suspense fallback={null}>
            <Rail />
          </Suspense>
          <div className="flex min-h-screen flex-col pb-14 md:pb-0 md:pl-[55px]">
            <Suspense fallback={<div className="h-12 border-b border-ink-700" />}>
              <TopBar />
            </Suspense>
            <main className="w-full max-w-[1376px] flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
            <footer className="px-4 py-5 text-[12px] text-ink-400 md:px-8">
              KOI is a research and decision-support tool, not personalised financial advice. Figures come from Yahoo Finance
              and NSE; verify them against the company&apos;s filings before you invest.
            </footer>
          </div>
        </ModeProvider>
      </body>
    </html>
  );
}
