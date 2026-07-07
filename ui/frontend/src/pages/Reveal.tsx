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
import { api, fmtPct, fmtSeconds, fmtTokens, fmtUsd } from "../api";
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
    const nothingJudged = data.n_judged === 0;
    const isLlm = data.mode === "llm";
    const backTo = isLlm
      ? `/grade/judge/${sessionId}${db ? `?db=${db}` : ""}`
      : `/grade/session/${sessionId}${db ? `?db=${db}` : ""}`;
    return (
      <main className="app-main">
        <div className="page" style={{ maxWidth: "44rem" }}>
          <h1>Reveal the verdict?</h1>
          <div className="card" data-testid="reveal-confirm">
            {nothingJudged ? (
              <p className="small" style={{ marginTop: 0 }}>
                Nothing has been judged in this session yet — there is no verdict to reveal.{" "}
                {isLlm ? "Run the LLM judge first." : "Judge some pairs first."}
              </p>
            ) : (
              <p className="small" style={{ marginTop: 0 }}>
                Revealing unblinds the <strong>{data.n_judged}</strong> judged pair
                {data.n_judged === 1 ? "" : "s"} of this {AXIS_LABELS[data.axis] ?? data.axis}{" "}
                {isLlm ? "LLM-judged " : ""}session and <strong>permanently closes it</strong> — no
                further blind judging is possible afterward.
              </p>
            )}
            {data.n_unjudged > 0 && !nothingJudged && (
              <p className="small muted">
                {data.n_unjudged} of {data.total_pairs} pairs {data.n_unjudged === 1 ? "is" : "are"} still
                unjudged — {data.n_unjudged === 1 ? "it" : "they"} will stay blind forever and never enter
                the ranking. Consider resuming the {isLlm ? "judge run" : "session"} first.
              </p>
            )}
            <div className="row" style={{ marginTop: "var(--space-3)" }}>
              <button
                className="btn primary"
                onClick={() => void confirm()}
                disabled={confirming || nothingJudged}
                data-testid="confirm-reveal"
              >
                {confirming ? "Striking…" : "Strike the gavel — reveal"}
              </button>
              <Link className="btn" to={backTo}>
                {data.n_unjudged > 0
                  ? nothingJudged
                    ? isLlm ? "Run the judge" : "Start judging"
                    : isLlm ? `Resume the judge (${data.n_unjudged} left)` : `Keep judging (${data.n_unjudged} left)`
                  : isLlm ? "Back to the judge run" : "Back to the pairs"}
              </Link>
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
          {data.mode === "llm" && (
            <>
              {" "}This session was judged by <strong>an LLM</strong>
              {data.judge_stats?.model ? <> (<code>{data.judge_stats.model}</code>)</> : null}, not by you.
            </>
          )}
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

        {data.judge_stats && (
          <div className="card" data-testid="judge-stats">
            <div className="card-title">LLM judge — reliability &amp; spend</div>
            <div className="row wrap" style={{ gap: "var(--space-4)" }}>
              <div className="stack" style={{ gap: 0 }}>
                <span className="xsmall muted">Judge</span>
                <span className="small mono">
                  {data.judge_stats.provider} · {data.judge_stats.model} ·{" "}
                  {data.judge_stats.passes === 2 ? "double pass (position-debiased)" : "single pass"}
                </span>
              </div>
              <div className="stack" style={{ gap: 0 }}>
                <span className="xsmall muted">Position consistency</span>
                <span className="small" data-testid="judge-consistency">
                  {data.judge_stats.passes === 2
                    ? `${data.judge_stats.n_consistent}/${data.judge_stats.n_consistent + data.judge_stats.n_inconsistent} pairs agreed under side-swap`
                    : "n/a (single pass)"}
                </span>
              </div>
              <div className="stack" style={{ gap: 0 }}>
                <span className="xsmall muted">Calls · tokens</span>
                <span className="small">
                  {data.judge_stats.n_calls} calls · {fmtTokens(data.judge_stats.input_tokens)} in /{" "}
                  {fmtTokens(data.judge_stats.output_tokens)} out
                </span>
              </div>
              <div className="stack" style={{ gap: 0 }}>
                <span className="xsmall muted">Judge cost · time</span>
                <span className="small">
                  {data.judge_stats.usd_equiv > 0 ? fmtUsd(data.judge_stats.usd_equiv) : "$0"}
                  {data.judge_stats.provider === "claude-cli" && " (API-rate equiv. — subscription quota)"}
                  {" · "}
                  {fmtSeconds(data.judge_stats.wall_seconds)}
                </span>
              </div>
              {data.judge_stats.n_errors > 0 && (
                <div className="stack" style={{ gap: 0 }}>
                  <span className="xsmall muted">Retried calls</span>
                  <span className="small">{data.judge_stats.n_errors} (malformed replies re-asked)</span>
                </div>
              )}
            </div>
            {data.judge_stats.n_inconsistent > 0 && (
              <p className="xsmall muted" style={{ marginBottom: 0 }}>
                Pairs where the two side-swapped passes disagreed were recorded as ties — a
                position-dependent verdict carries no reliable signal.
              </p>
            )}
          </div>
        )}

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
                          {/* only crown a STRICT winner — an exact tie must not
                              invent a ranking the data doesn't support */}
                          {i === 0 && data.bt_scores!.length > 1 && s.elo - data.bt_scores![1].elo > 0.5 && (
                            <span className="badge accent">session winner</span>
                          )}
                          {i === 0 && data.bt_scores!.length > 1 && Math.abs(s.elo - data.bt_scores![1].elo) <= 0.5 && (
                            <span className="badge neutral">tied</span>
                          )}
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
                  <th>{data.mode === "llm" ? "Judge's choice" : "Your choice"}</th>
                  {data.mode === "llm" && <th>Why (judge's rationale)</th>}
                </tr>
              </thead>
              <tbody>
                {data.pairs.map((p) => (
                  <tr key={p.pair_index}>
                    <td className="num">{p.pair_index + 1}</td>
                    <td><IdChip catalog={catalog} kind={kind} id={p.left_value} /></td>
                    <td><IdChip catalog={catalog} kind={kind} id={p.right_value} /></td>
                    <td>
                      <span className="row" style={{ gap: "var(--space-1)" }}>
                        <span className="badge accent">{p.choice}</span>
                        {p.position_consistent === false && (
                          <span className="badge neutral" title="The two side-swapped judge passes disagreed — recorded as a tie">
                            swap-disagreed
                          </span>
                        )}
                        {p.truncated && (
                          <span
                            className="badge neutral"
                            title="One of the diffs exceeded the judge's budget — the verdict covers a truncated prefix"
                            data-testid="truncated-badge"
                          >
                            diff truncated
                          </span>
                        )}
                      </span>
                    </td>
                    {data.mode === "llm" && (
                      <td style={{ maxWidth: "28rem" }}>
                        <span className="xsmall" data-testid="judge-rationale">
                          {p.rationale ?? "—"}
                          {p.confidence !== null && (
                            <span className="muted"> (confidence {Math.round((p.confidence ?? 0) * 100)}%)</span>
                          )}
                        </span>
                      </td>
                    )}
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
