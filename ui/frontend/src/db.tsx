// Active-DB selection: honored from ?db= on first load, persisted to
// localStorage, exposed via context. Every API call reads from here.

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

interface DbState {
  db: string; // "" = server default
  setDb: (db: string) => void;
}

const DbContext = createContext<DbState>({ db: "", setDb: () => {} });

const STORAGE_KEY = "tiltyard.db";

export function DbProvider({ children }: { children: ReactNode }) {
  const [db, setDbState] = useState<string>(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("db");
    if (fromUrl !== null) return fromUrl;
    return localStorage.getItem(STORAGE_KEY) ?? "";
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, db);
  }, [db]);

  return <DbContext.Provider value={{ db, setDb: setDbState }}>{children}</DbContext.Provider>;
}

export function useDb(): DbState {
  return useContext(DbContext);
}
