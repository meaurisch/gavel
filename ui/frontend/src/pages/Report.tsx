// Ranking report: Bradley-Terry scores with CIs, tier pass rates, cost
// rollup, Pareto frontier and stakes picks — the same data as
// `python cli.py report`, plus links to generated HTML artifacts.

import { useState } from "react";
import { api, fmtPct, fmtUsd } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import { AXES, AXIS_LABELS } from "../types";
import type { Axis } from "../types";
import { IdChip } from "../components/previews";

const AXIS_TO_KIND: Record<string, "methodology" | "model" | "repo_context" | "runner"> = {
  methodology: "methodology",
  model: "model",
  repo_context: "repo_context",
  runner: "runner",
};

export function ReportPage() {
  const { db } = useDb();
  const { catalog } = useCatalog();
  const [axis, setAxis] = useState<Axis>("methodology");
  const [taskPin, setTaskPin] = useState("");
  const { data, error, loading } = useFetch(
    () => api.report(db, axis, taskPin ? { task: taskPin } : {}),
    [db, axis, taskPin],
  );

  const kind = AXIS_TO_KIND[axis];
  const ranked = (data?.summaries ?? [])
    .slice()
    .sort((a, b) => (b.bt_strength ?? -Infinity) - (a.bt_strength ?? -Infinity));

  return (
    <main className="app-main">
      <div className="page-wide">
        <h1>Report</h1>

        <div className="card">
          <div className="row wrap">
            <div className="field">
              <label>Comparison axis</label>
              <div className="row" style={{ gap: "var(--space-1)" }}>
                {AXES.map((a) => (
                  <button key={a} className={`btn sm ${axis === a ? "primary" : ""}`} onClick={() => setAxis(a)}>
                    {AXIS_LABELS[a]}
                  </button>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Pin to task (optional)</label>
              <select className="control" value={taskPin} onChange={(e) => setTaskPin(e.target.value)}>
                <option value="">(all tasks)</option>
                {(catalog?.tasks ?? [])
                  .filter((t) => t.n_trials > 0)
                  .map((t) => (
                    <option key={t.id} value={t.id}>{t.id}</option>
                  ))}
              </select>
            </div>
          </div>
        </div>

        {loading && <div className="empty-state">Computing ranking…</div>}
        {error && <div className="error-banner">{error}</div>}

        {data && (
          <>
            <div className="card">
              <div className="spread" style={{ marginBottom: "var(--space-2)" }}>
                <div className="card-title" style={{ margin: 0 }}>
                  {AXIS_LABELS[axis]} ranking — Bradley-Terry
                </div>
                <span className="xsmall muted">
                  {data.n_judgments} blind judgment{data.n_judgments === 1 ? "" : "s"} across {data.n_sessions} session{data.n_sessions === 1 ? "" : "s"}
                </span>
              </div>
              {data.n_judgments === 0 && (
                <div className="notice-banner" style={{ marginBottom: "var(--space-3)" }}>
                  No blind judgments for this axis yet — the ranking columns stay empty until you grade.
                </div>
              )}
              {data.orphan_judgments > 0 && (
                <div className="notice-banner" style={{ marginBottom: "var(--space-3)" }}>
                  {data.orphan_judgments} judgment(s) predate session persistence and can't be attributed —
                  re-grade those cells to include them.
                </div>
              )}
              <div className="table-wrap">
                <table className="table" data-testid="report-table">
                  <thead>
                    <tr>
                      <th>{AXIS_LABELS[axis]}</th>
                      <th />
                      <th className="num">Elo</th>
                      <th className="num">95% CI</th>
                      <th className="num">Comps</th>
                      <th className="num">Build</th>
                      <th className="num">Visible</th>
                      <th className="num">Hidden</th>
                      <th className="num">Trials</th>
                      <th className="num">Mean $</th>
                      <th className="num">Total $</th>
                      <th>Frontier</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranked.map((s) => (
                      <tr key={s.value}>
                        <td><IdChip catalog={catalog} kind={kind} id={s.value} /></td>
                        <td>
                          {s.value === data.picks.high_stakes && <span className="badge accent">quality pick</span>}{" "}
                          {s.value === data.picks.routine && <span className="badge ok">budget pick</span>}
                        </td>
                        <td className="num">{s.elo !== null ? s.elo.toFixed(0) : "—"}</td>
                        <td className="num">
                          {s.bt_ci_elo ? `${s.bt_ci_elo[0].toFixed(0)} – ${s.bt_ci_elo[1].toFixed(0)}` : "—"}
                        </td>
                        <td className="num">{s.n_comparisons}</td>
                        <td className="num">{fmtPct(s.tier_pass_rates["compile"] ?? null)}</td>
                        <td className="num">{fmtPct(s.tier_pass_rates["visible"] ?? null)}</td>
                        <td className="num">{fmtPct(s.tier_pass_rates["hidden"] ?? null)}</td>
                        <td className="num">{s.n_trials}</td>
                        <td className="num">{fmtUsd(s.mean_usd)}</td>
                        <td className="num">{fmtUsd(s.total_usd)}</td>
                        <td>
                          {s.on_frontier ? (
                            <span className="badge ok">yes</span>
                          ) : s.bt_strength !== null ? (
                            <span className="badge neutral">no</span>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.picks.high_stakes && (
                <p className="small" style={{ marginBottom: 0 }}>
                  <strong>High-stakes pick:</strong> {data.picks.high_stakes} · <strong>Routine pick:</strong>{" "}
                  {data.picks.routine}
                  <span className="xsmall muted"> (routine = cheapest value statistically indistinguishable from the winner)</span>
                </p>
              )}
            </div>

            {data.flag_lines.length > 0 && (
              <div className="card">
                <div className="card-title">Analyzer flags</div>
                <ul className="small" style={{ margin: 0, paddingLeft: "1.4em" }}>
                  {data.flag_lines.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="card">
              <div className="card-title">Generated HTML artifacts (reports/)</div>
              {data.artifacts.length === 0 ? (
                <p className="small muted" style={{ margin: 0 }}>
                  None yet — <code>python cli.py report</code> writes a self-contained HTML artifact with the
                  Pareto frontier chart.
                </p>
              ) : (
                <div className="stack" style={{ gap: "var(--space-1)" }}>
                  {data.artifacts.map((a) => (
                    <div key={a.name} className="row small">
                      <a href={a.url} target="_blank" rel="noreferrer">{a.name}</a>
                      <span className="xsmall faint">(timestamp in the name is UTC; newest first)</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
