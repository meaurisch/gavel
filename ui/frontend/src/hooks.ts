// Small data-fetch hooks with a per-DB in-memory cache for the catalog
// (hover previews use it on every screen — no point refetching per page).

import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Catalog } from "./types";
import { useDb } from "./db";

const catalogCache = new Map<string, Catalog>();

export function useCatalog(): { catalog: Catalog | null; error: string | null } {
  const { db } = useDb();
  const [catalog, setCatalog] = useState<Catalog | null>(catalogCache.get(db) ?? null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const cached = catalogCache.get(db);
    if (cached) {
      setCatalog(cached);
      return;
    }
    setCatalog(null);
    api
      .catalog(db)
      .then((c) => {
        catalogCache.set(db, c);
        if (!cancelled) setCatalog(c);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e.message ?? e));
      });
    return () => {
      cancelled = true;
    };
  }, [db]);

  return { catalog, error };
}

export function invalidateCatalog(db: string) {
  catalogCache.delete(db);
}

/** Generic "fetch on mount / on deps change" hook with error + loading. */
export function useFetch<T>(fn: () => Promise<T>, deps: unknown[]): {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fnRef
      .current()
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e.message ?? e));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}
