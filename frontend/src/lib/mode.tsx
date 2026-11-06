"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Mode } from "./api";

type Ctx = { mode: Mode; setMode: (m: Mode) => void; atLeast: (m: Mode) => boolean };

const ORDER: Mode[] = ["beginner", "intermediate", "advanced"];
const ModeContext = createContext<Ctx>({ mode: "beginner", setMode: () => {}, atLeast: () => false });

export function ModeProvider({ children }: { children: React.ReactNode }) {
  // Beginner is the default for first-time users; the choice persists locally.
  const [mode, setModeState] = useState<Mode>("beginner");
  useEffect(() => {
    // A ?mode= link (shared or bookmarked) wins over the stored choice.
    const fromUrl = new URLSearchParams(window.location.search).get("mode") as Mode | null;
    const saved = (fromUrl && ORDER.includes(fromUrl) ? fromUrl : localStorage.getItem("koi.mode")) as Mode | null;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from localStorage after mount
    if (saved && ORDER.includes(saved)) setModeState(saved);
  }, []);
  const setMode = useCallback((m: Mode) => {
    setModeState(m);
    localStorage.setItem("koi.mode", m);
  }, []);
  const atLeast = useCallback((m: Mode) => ORDER.indexOf(mode) >= ORDER.indexOf(m), [mode]);
  return <ModeContext.Provider value={{ mode, setMode, atLeast }}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);
