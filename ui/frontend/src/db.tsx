// Active-DB selection: honored from ?db= on first load, persisted to
// localStorage, exposed via context. Every API call reads from here.

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

interface DbState {
  db: string; // "" = server default
  setDb: (db: string) => void;
}

const DbContext = createContext<DbState>({ db: "", setDb: () => {} });

const STORAGE_KEY = "gavel.db";
const LEGACY_KEY = "tiltyard.db"; // pre-rename builds — migrate, then drop

export function DbProvider({ children }: { children: ReactNode }) {
  const [db, setDbState] = useState<string>(() => {
    const legacy = localStorage.getItem(LEGACY_KEY);
    localStorage.removeItem(LEGACY_KEY); // always drop the stale key
    const fromUrl = new URLSearchParams(window.location.search).get("db");
    if (fromUrl !== null) return fromUrl;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) return stored;
    return legacy ?? "";
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, db);
    // Keep the URL truthful: a stale ?db= param while the switcher shows a
    // different database misleads on reload and when sharing links.
    const url = new URL(window.location.href);
    const current = url.searchParams.get("db") ?? "";
    if (current !== db) {
      if (db) url.searchParams.set("db", db);
      else url.searchParams.delete("db");
      window.history.replaceState(null, "", url);
    }
  }, [db]);

  return <DbContext.Provider value={{ db, setDb: setDbState }}>{children}</DbContext.Provider>;
}

export function useDb(): DbState {
  return useContext(DbContext);
}
