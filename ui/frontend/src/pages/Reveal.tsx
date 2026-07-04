// Post-session reveal: which axis values were behind A/B, win/loss/tie
// records, Bradley-Terry ranking (when enough judgments exist), objective
// pass rates, and analyzer flags.
//
// Revealing is IRREVERSIBLE (it closes the session), so an unrevealed
// session shows an explicit confirmation step first — a bare page load
// (URL autocomplete, a slipped keystroke on the last pair) must never
// destroy blind judging on its own.

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fmtPct } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import { AXIS_LABELS } from "../types";
import type { RevealResponse } from "../types";
import { IdChip } from "../components/previews";

const AXIS_TO_KIND: Record<string, "methodology" | "model" | "repo_context" | "runner"> = {
  methodology: "methodology",
  model: "model",
  repo_context: "repo_context",
  runner: "runner",
};

export function RevealPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { db } = useDb();
  const { catalog } = useCatalog();
  const { data: fetched, error, loading } = useFetch(() => api.reveal(db, sessionId!), [db, sessionId]);
  const [confirmed, setConfirmed] = useState<RevealResponse | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const data = confirmed ?? fetched;

  const confirm = async () => {
    setConfirming(true);
    setConfirmError(null);
    try {
      setConfirmed(await api.revealConfirm(db, sessionId!));
    } catch (e) {
      setConfirmError(String((e as Error).message ?? e));
    } finally {
      setConfirming(false);
    }
  };

  if (loading) return <main className="app-main"><div className="empty-state">Loading…</div></main>;
  if (error) return <main className="app-main"><div className="error-banner">{error}</div></main>;
  if (!data) return null;

  if (!data.revealed) {
    return (
      <main className="app-main">
        <div className="page" style={{ maxWidth: "44rem" }}>
          <h1>Reveal the verdict?</h1>
          <div className="card" data-testid="reveal-confirm">
            <p className="small" style={{ marginTop: 0 }}>
              Revealing unblinds the <strong>{data.n_judged}</strong> judged pair
              {data.n_judged === 1 ? "" : "s"} of this {AXIS_LABELS[data.axis] ?? data.axis} session and{" "}
              <strong>permanently closes it</strong> — no further blind judging is possible afterward.
            </p>
            {data.n_unjudged > 0 && (
              <p className="small muted">
                {data.n_unjudged} of {data.total_pairs} pairs {data.n_unjudged === 1 ? "is" : "are"} still
                unjudged — {data.n_unjudged === 1 ? "it" : "they"} will stay blind forever and never enter
                the ranking. Consider resuming the session first.
              </p>
            )}
            <div className="row" style={{ marginTop: "var(--space-3)" }}>
              <button className="btn primary" onClick={() => void confirm()} disabled={confirming} data-testid="confirm-reveal">
                {confirming ? "Striking…" : "Strike the gavel — reveal"}
              </button>
              {data.n_unjudged > 0 && (
                <Link className="btn" to={`/grade/session/${sessionId}${db ? `?db=${db}` : ""}`}>
                  Keep judging ({data.n_unjudged} left)
                </Link>
              )}
            </div>
            {confirmError && <div className="error-banner" style={{ marginTop: "var(--space-2)" }}>{confirmError}</div>}
          </div>
        </div>
      </main>
    );
  }

  const kind = AXIS_TO_KIND[data.axis] ?? "methodology";

  return (
    <main className="app-main">
      <div className="page">
        <div className="spread">
          <h1>The verdict — {AXIS_LABELS[data.axis] ?? data.axis}</h1>
          <span className="row">
            <Link className="btn" to={`/grade${db ? `?db=${db}` : ""}`}>Grade another cell</Link>
            <Link className="btn primary" to={`/report${db ? `?db=${db}` : ""}`}>Full report</Link>
          </span>
        </div>

        <div className="info-banner" style={{ marginBottom: "var(--space-4)" }} data-testid="session-closed-note">
          The gavel has struck — this session is closed. Revealing ends blind judging permanently.
          {data.n_unjudged > 0 && (
            <>
              {" "}
              <strong>
                {data.n_unjudged} unjudged pair{data.n_unjudged === 1 ? "" : "s"} stayed blind
              </strong>{" "}
              and {data.n_unjudged === 1 ? "is" : "are"} not shown — start a new session to grade this cell
              further.
            </>
          )}
        </div>

        {data.bt_scores && (
          <div className="card" data-testid="bt-table">
            <div className="card-title">Bradley-Terry ranking (this session)</div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{AXIS_LABELS[data.axis]}</th>
                    <th className="num">Elo</th>
                    <th className="num">95% CI</th>
                    <th className="num">Hidden-gate pass rate</th>
                  </tr>
                </thead>
                <tbody>
                  {data.bt_scores.map((s, i) => (
                    <tr key={s.axis_value}>
                      <td>{i + 1}</td>
                      <td>
                        <span className="row" style={{ gap: "var(--space-2)" }}>
                          <IdChip catalog={catalog} kind={kind} id={s.axis_value} />
                          {i === 0 && <span className="badge accent">session winner</span>}
                        </span>
                      </td>
                      <td className="num">{s.elo.toFixed(0)}</td>
                      <td className="num">{s.ci_lower.toFixed(0)} – {s.ci_upper.toFixed(0)}</td>
                      <td className="num">{fmtPct(data.pass_rates?.[s.axis_value] ?? null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="card">
          <div className="card-title">Win / loss / tie per value</div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>{AXIS_LABELS[data.axis]}</th>
                  <th className="num">Wins</th>
                  <th className="num">Losses</th>
                  <th className="num">Ties</th>
                  <th className="num">Hidden-gate pass rate</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.summary).map(([value, rec]) => (
                  <tr key={value}>
                    <td><IdChip catalog={catalog} kind={kind} id={value} /></td>
                    <td className="num">{rec.wins}</td>
                    <td className="num">{rec.losses}</td>
                    <td className="num">{rec.ties}</td>
                    <td className="num">{fmtPct(data.pass_rates?.[value] ?? null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!data.bt_scores && (
            <p className="xsmall muted">
              Bradley-Terry needs ≥3 judged pairs — grade more pairs (or more cells) to get a ranking.
            </p>
          )}
        </div>

        <div className="card">
          <div className="card-title">Judged pairs, unblinded</div>
          <div className="table-wrap">
            <table className="table" data-testid="reveal-pairs">
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>A was</th>
                  <th>B was</th>
                  <th>Your choice</th>
                </tr>
              </thead>
              <tbody>
                {data.pairs.map((p) => (
                  <tr key={p.pair_index}>
                    <td className="num">{p.pair_index + 1}</td>
                    <td><IdChip catalog={catalog} kind={kind} id={p.left_value} /></td>
                    <td><IdChip catalog={catalog} kind={kind} id={p.right_value} /></td>
                    <td>
                      <span className="badge accent">{p.choice}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {data.analyzer_flags &&
          (data.analyzer_flags.non_discriminating_tasks.length > 0 ||
            data.analyzer_flags.flaky_tasks.length > 0 ||
            data.analyzer_flags.cost_quality_notes.length > 0) && (
            <div className="card">
              <div className="card-title">Analyzer flags</div>
              <ul className="small" style={{ margin: 0, paddingLeft: "1.4em" }}>
                {data.analyzer_flags.non_discriminating_tasks.map((t) => (
                  <li key={`nd-${t}`}>non-discriminating task: {t}</li>
                ))}
                {data.analyzer_flags.flaky_tasks.map((t) => (
                  <li key={`fl-${t}`}>flaky task: {t}</li>
                ))}
                {data.analyzer_flags.cost_quality_notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          )}
      </div>
    </main>
  );
}
