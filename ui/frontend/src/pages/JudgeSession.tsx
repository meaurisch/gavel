// LLM judge progress screen. While the judge runs, the page stays BLIND:
// verdicts appear as A/B/tie letters only — no axis values, no cost, no
// tokens (spend metrics live behind the reveal, same as human sessions).
//
// Run handles live in server memory; after a server restart this page falls
// back to the persisted session state (judgments survive in the DB) and
// offers to resume any unjudged pairs.

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useDb } from "../db";
import { useFetch } from "../hooks";
import { AXIS_LABELS } from "../types";
import type { JudgeRunSnapshot, Session } from "../types";

function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div
      style={{
        height: "0.5rem",
        borderRadius: "var(--radius-sm)",
        background: "var(--color-surface-inset)",
        overflow: "hidden",
      }}
      role="progressbar"
      aria-valuenow={done}
      aria-valuemin={0}
      aria-valuemax={total}
      data-testid="judge-progress"
    >
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          background: "var(--color-accent)",
          transition: "width 0.3s ease",
        }}
      />
    </div>
  );
}

export function JudgeSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { db } = useDb();
  const [run, setRun] = useState<JudgeRunSnapshot | null>(null);
  const [runMissing, setRunMissing] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  // Session state from the DB — the durable source of truth for judged counts.
  const {
    data: session,
    error: sessionError,
    reload: reloadSession,
  } = useFetch<Session>(() => api.session(db, sessionId!), [db, sessionId]);

  const attach = useCallback(async () => {
    try {
      const snap = await api.judgeRunForSession(sessionId!);
      setRun(snap);
      setRunMissing(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setRunMissing(true);
      else setActionError(String((e as Error).message ?? e));
    }
  }, [sessionId]);

  useEffect(() => {
    void attach();
  }, [attach]);

  // Poll while running; refresh the session once when the run settles.
  useEffect(() => {
    if (!run || run.status !== "running") return;
    pollRef.current = window.setInterval(async () => {
      try {
        const snap = await api.judgeRun(run.id);
        setRun(snap);
        if (snap.status !== "running") {
          reloadSession();
        }
      } catch {
        /* transient poll failure — next tick retries */
      }
    }, 700);
    return () => {
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
    };
  }, [run, reloadSession]);

  const resume = async () => {
    setResuming(true);
    setActionError(null);
    try {
      await api.judgeStart({ db, session_id: sessionId });
      await attach();
      reloadSession();
    } catch (e) {
      setActionError(String((e as Error).message ?? e));
    } finally {
      setResuming(false);
    }
  };

  const cancel = async () => {
    if (!run) return;
    try {
      await api.judgeRunCancel(run.id);
    } catch (e) {
      setActionError(String((e as Error).message ?? e));
    }
  };

  if (sessionError) {
    return (
      <main className="app-main">
        <div className="error-banner">{sessionError}</div>
      </main>
    );
  }
  if (!session) {
    return (
      <main className="app-main">
        <div className="empty-state">Loading…</div>
      </main>
    );
  }

  if (session.mode !== "llm") {
    return (
      <main className="app-main">
        <div className="page" style={{ maxWidth: "44rem" }}>
          <div className="info-banner">
            This is a manual grading session — it has no judge run.{" "}
            <Link to={`/grade/session/${sessionId}${db ? `?db=${db}` : ""}`}>Open it for blind judging</Link>.
          </div>
        </div>
      </main>
    );
  }

  // The session payload is fetched once (it's heavy — full diffs); live pair
  // events from the run fill in progress between session refreshes. Union the
  // two by pair index so the bar advances DURING a run and stays exact across
  // resumes (a resumed run only emits events for the remaining pairs).
  const livePairEvents = (run?.events ?? []).filter((e) => e.type === "pair");
  const judgedIdx = new Set<number>(session.judged.map((j) => j.pair_index));
  for (const e of livePairEvents) if (e.index !== undefined) judgedIdx.add(e.index);
  const nJudged = Math.min(judgedIdx.size, session.total_pairs);
  const total = session.total_pairs;
  const allJudged = nJudged >= total;
  const running = run?.status === "running";
  const pairEvents = livePairEvents;
  const revealTo = `/grade/session/${sessionId}/reveal${db ? `?db=${db}` : ""}`;

  return (
    <main className="app-main">
      <div className="page" style={{ maxWidth: "52rem" }}>
        <div className="spread">
          <h1>LLM judge — {AXIS_LABELS[session.axis] ?? session.axis}</h1>
          <span className="badge accent" data-testid="judge-mode-badge">LLM-judged session</span>
        </div>

        <div className="card" data-testid="judge-run-card">
          <div className="card-title">
            {session.judge_provider} · {session.judge_model}
          </div>
          <p className="small muted" style={{ marginTop: 0 }}>
            The judge sees exactly what you would in a blind session: anonymized diffs and the gate
            scorecard — never identities, cost, or timing. Verdicts below are blind letters; reveal to
            unblind them.
          </p>

          <ProgressBar done={nJudged} total={total} />
          <div className="spread" style={{ marginTop: "var(--space-2)" }}>
            <span className="small" data-testid="judge-progress-text">
              {nJudged}/{total} pairs judged
              {run && run.passes === 2 && pairEvents.length > 0 && (
                <span className="muted">
                  {" "}· {pairEvents.filter((e) => e.position_consistent).length}/{pairEvents.length} swap-consistent
                </span>
              )}
            </span>
            <span className="row">
              {running && (
                <button className="btn sm" onClick={() => void cancel()} data-testid="judge-cancel">
                  Cancel after this pair
                </button>
              )}
              {!running && !allJudged && (
                <button
                  className="btn sm primary"
                  onClick={() => void resume()}
                  disabled={resuming}
                  data-testid="judge-resume"
                >
                  {resuming ? "Resuming…" : `Resume judging (${total - nJudged} left)`}
                </button>
              )}
            </span>
          </div>

          {run?.status === "error" && (
            <div className="error-banner" style={{ marginTop: "var(--space-2)" }} data-testid="judge-error">
              Judge run failed: {run.error}
            </div>
          )}
          {run?.status === "cancelled" && (
            <div className="info-banner" style={{ marginTop: "var(--space-2)" }}>
              Judge run cancelled — already-judged pairs are kept; resume any time.
            </div>
          )}
          {runMissing && !allJudged && nJudged > 0 && (
            <div className="info-banner" style={{ marginTop: "var(--space-2)" }}>
              The judging process from a previous server session isn't running anymore — its verdicts are
              saved. Resume to judge the remaining pairs.
            </div>
          )}
          {actionError && (
            <div className="error-banner" style={{ marginTop: "var(--space-2)" }}>{actionError}</div>
          )}
        </div>

        {(pairEvents.length > 0 || allJudged) && (
          <div className="card">
            <div className="card-title">Blind verdicts</div>
            <div className="table-wrap">
              <table className="table" data-testid="judge-verdicts">
                <thead>
                  <tr>
                    <th className="num">Pair</th>
                    <th>Verdict (blind)</th>
                    <th>Side-swap check</th>
                  </tr>
                </thead>
                <tbody>
                  {pairEvents.length > 0
                    ? pairEvents.map((e) => (
                        <tr key={e.index}>
                          <td className="num">{(e.index ?? 0) + 1}</td>
                          <td><span className="badge accent">{e.choice}</span></td>
                          <td className="small">
                            {e.position_consistent === null || e.position_consistent === undefined
                              ? "single pass"
                              : e.position_consistent
                                ? "consistent"
                                : "disagreed → tie"}
                            {e.truncated && <span className="muted"> · diff truncated</span>}
                          </td>
                        </tr>
                      ))
                    : session.judged.map((j) => (
                        <tr key={j.pair_index}>
                          <td className="num">{j.pair_index + 1}</td>
                          <td><span className="badge accent">{j.choice}</span></td>
                          <td className="small muted">from a previous run</td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {allJudged && !running && (
          <div className="card" data-testid="judge-done">
            <div className="card-title">All pairs judged</div>
            <p className="small" style={{ marginTop: 0 }}>
              The verdicts are in but still blind. Reveal to see which {AXIS_LABELS[session.axis]?.toLowerCase() ?? session.axis}{" "}
              was behind each letter, the judge's rationale per pair, and the Bradley-Terry ranking.
            </p>
            <Link className="btn primary" to={revealTo} data-testid="judge-reveal-link">
              Reveal the verdict →
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
