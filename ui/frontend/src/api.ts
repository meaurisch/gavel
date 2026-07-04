// Typed fetch layer. Every call carries the active DB (?db=...), which lives
// in the URL search params so sessions/links stay shareable and reload-safe.

import type {
  Catalog,
  Cell,
  DbInfo,
  GradingStatus,
  OriginalsResponse,
  Report,
  RevealResponse,
  RunPlan,
  RunSnapshot,
  Session,
  SessionSummary,
  TrialDetail,
  TrialRow,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function request<T>(path: string, params: Record<string, string> = {}, init?: RequestInit): Promise<T> {
  const url = new URL(path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== "") url.searchParams.set(k, v);
  }
  const resp = await fetch(url.toString(), init);
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export const api = {
  dbs: () => request<DbInfo[]>("/api/dbs"),

  catalog: (db: string) => request<Catalog>("/api/catalog", { db }),

  axes: (db: string) => request<{ axis: string; n_cells: number }[]>("/api/axes", { db }),

  gradingStatus: (db: string) => request<GradingStatus>("/api/grading-status", { db }),

  cells: (db: string, axis: string) => request<Cell[]>("/api/cells", { db, axis }),

  startSession: (db: string, axis: string, cell: Record<string, string>) =>
    request<Session>("/api/pairs", { db, axis, ...cell }),

  sessions: (db: string) => request<SessionSummary[]>("/api/sessions", { db }),

  session: (db: string, sessionId: string) =>
    request<Session>(`/api/session/${encodeURIComponent(sessionId)}`, { db }),

  pairOriginals: (db: string, sessionId: string, pairIndex: number) =>
    request<OriginalsResponse>("/api/pair-originals", {
      db,
      session_id: sessionId,
      pair_index: String(pairIndex),
    }),

  judge: (db: string, sessionId: string, pairIndex: number, choice: string) =>
    request<{ ok: boolean; remaining: number }>("/api/judge", {}, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ db, session_id: sessionId, pair_index: pairIndex, choice }),
    }),

  reveal: (db: string, sessionId: string) =>
    request<RevealResponse>("/api/reveal", { db, session_id: sessionId }),

  revealConfirm: (db: string, sessionId: string) =>
    request<RevealResponse>("/api/reveal", {}, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ db, session_id: sessionId }),
    }),

  trials: (db: string) => request<TrialRow[]>("/api/trials", { db }),

  trialDetail: (db: string, trialId: string) =>
    request<TrialDetail>(`/api/trials/${encodeURIComponent(trialId)}`, { db }),

  report: (db: string, axis: string, pins: Record<string, string>) =>
    request<Report>("/api/report", { db, axis, ...pins }),

  runsPlan: (db: string, params: Record<string, string>) =>
    request<RunPlan>("/api/runs/plan", { db, ...params }),

  runsStart: (body: Record<string, unknown>) =>
    request<{ run_id: string; n_trials: number; status: string }>("/api/runs", {}, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  runs: () => request<RunSnapshot[]>("/api/runs"),

  run: (runId: string) => request<RunSnapshot>(`/api/runs/${encodeURIComponent(runId)}`),

  runCancel: (runId: string) =>
    request<{ ok: boolean }>(`/api/runs/${encodeURIComponent(runId)}/cancel`, {}, { method: "POST" }),
};

// --- formatting helpers shared across pages --------------------------------

export function fmtUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v >= 10 ? `$${v.toFixed(2)}` : `$${v.toFixed(3)}`;
}

export function fmtTokens(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return String(v);
}

export function fmtSeconds(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v >= 90) return `${Math.round(v / 60)}m ${Math.round(v % 60)}s`;
  return `${v.toFixed(1)}s`;
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${Math.round(v * 100)}%`;
}

export function fmtDate(iso: string | number | null | undefined): string {
  if (iso === null || iso === undefined) return "—";
  const d = typeof iso === "number" ? new Date(iso * 1000) : new Date(iso);
  if (isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}
