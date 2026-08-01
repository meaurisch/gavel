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

type Grader = "all" | "human" | "llm";

const GRADER_LABELS: Record<Grader, string> = {
  all: "All judgments",
  human: "Human only",
  llm: "LLM judge only",
};

export function ReportPage() {
  const { db } = useDb();
  const { catalog } = useCatalog();
  const [axis, setAxis] = useState<Axis>("methodology");
  const [taskPin, setTaskPin] = useState("");
  const [grader, setGrader] = useState<Grader>("all");
  const { data, error, loading } = useFetch(
    () => api.report(db, axis, { ...(taskPin ? { task: taskPin } : {}), grader }),
    [db, axis, taskPin, grader],
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
            <div className="field">
              <label>Judged by</label>
              <div className="row" style={{ gap: "var(--space-1)" }} data-testid="grader-filter">
                {(Object.keys(GRADER_LABELS) as Grader[]).map((g) => (
                  <button
                    key={g}
                    className={`btn sm ${grader === g ? "primary" : ""}`}
                    onClick={() => setGrader(g)}
                    aria-pressed={grader === g}
                    data-testid={`grader-${g}`}
                  >
                    {GRADER_LABELS[g]}
                  </button>
                ))}
              </div>
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
                  {data.grader !== "all" && (
                    <span className="badge neutral" style={{ marginLeft: "var(--space-1)" }}>
                      {data.grader === "human" ? "human verdicts only" : "LLM verdicts only"}
                    </span>
                  )}
                </span>
              </div>
              {data.n_judgments === 0 && (
                <div className="info-banner" style={{ marginBottom: "var(--space-3)" }}>
                  No blind judgments for this axis yet — the ranking columns stay empty until you grade.
                </div>
              )}
              {data.n_judgments > 0 && ranked.every((s) => s.elo === null) && (
                <div className="info-banner" style={{ marginBottom: "var(--space-3)" }} data-testid="bt-underpowered-note">
                  {data.n_judgments} blind judgment{data.n_judgments === 1 ? "" : "s"} recorded — the
                  Bradley-Terry fit needs at least 3, so Elo, CI, and frontier stay “—” until you grade more
                  pairs.
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
                        {/* no cost records → both columns say "unknown", not "$0" */}
                        <td className="num">{s.mean_usd === null ? "—" : fmtUsd(s.total_usd)}</td>
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
                  <strong>Quality pick</strong> (high-stakes work): {data.picks.high_stakes} ·{" "}
                  <strong>Budget pick</strong> (routine work): {data.picks.routine}
                  <span className="xsmall muted"> — budget = cheapest value statistically indistinguishable from the winner</span>
                </p>
              )}
            </div>

            {data.agreement.n_shared > 0 && (
              <div className="card" data-testid="agreement-card">
                <div className="card-title">Human ↔ LLM judge agreement</div>
                <p className="small" style={{ marginTop: 0 }}>
                  Over the <strong>{data.agreement.n_shared}</strong> trial pair
                  {data.agreement.n_shared === 1 ? "" : "s"} both a human and the LLM judge graded, they
                  agreed on <strong>{data.agreement.n_agree}</strong> ({fmtPct(data.agreement.rate)})
                  {data.agreement.kappa !== null && (
                    <> — Cohen's κ = <strong>{data.agreement.kappa.toFixed(2)}</strong></>
                  )}
                  .
                </p>
                <p className="xsmall muted" style={{ marginBottom: 0 }}>
                  κ corrects raw agreement for chance: ≥0.6 is substantial (the LLM judge is a usable
                  stand-in for you on this data), ≤0.2 means its verdicts diverge from yours — trust your
                  own grading and treat the LLM ranking as a rough draft. Grade a few cells yourself to
                  grow this comparison.
                </p>
              </div>
            )}

            {data.probe_stats && data.probe_stats.n_evaluated > 0 && (
              <div className="card" data-testid="probe-stats-card">
                <div className="card-title">Judge consistency — repeat probes</div>
                <p className="small" style={{ marginTop: 0 }}>
                  Across <strong>{data.probe_stats.n_evaluated}</strong> evaluated probe
                  {data.probe_stats.n_evaluated === 1 ? "" : "s"} (deliberate side-swapped repeat
                  pairs, excluded from the ranking): self-agreement{" "}
                  <strong>{fmtPct(data.probe_stats.self_agreement)}</strong> (
                  {data.probe_stats.n_agree}/{data.probe_stats.n_evaluated}), side-swap flips{" "}
                  <strong>{fmtPct(data.probe_stats.flip_rate)}</strong> (
                  {data.probe_stats.n_flips}/{data.probe_stats.n_evaluated}).
                </p>
                <p className="xsmall muted" style={{ marginBottom: 0 }}>
                  Self-agreement is the judging instrument's own noise floor — an LLM judge earns
                  scaled duty only by agreeing with the human at least this often.
                </p>
              </div>
            )}

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
                <>
                  <div className="stack" style={{ gap: "var(--space-1)" }}>
                    {data.artifacts.map((a) => (
                      <div key={a.name} className="row small">
                        <a href={a.url} target="_blank" rel="noreferrer">{a.name}</a>
                      </div>
                    ))}
                  </div>
                  <p className="xsmall faint" style={{ marginBottom: 0 }}>
                    Newest first; the timestamp in the filename is UTC. Artifacts are files under
                    <code> reports/</code> — the list is not scoped to the selected database.
                  </p>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
