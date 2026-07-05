// Full unblinded detail for one trial: the five axis values, the complete
// gate scorecard with raw per-tier logs, cost breakdown, and the diff.

import { Link, useParams } from "react-router-dom";
import { api, fmtSeconds, fmtTokens, fmtUsd } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import { UnifiedDiffPane } from "../components/DiffView";
import { TierBadge } from "../components/GateBadges";
import { IdChip } from "../components/previews";

export function TrialDetailPage() {
  const { trialId } = useParams<{ trialId: string }>();
  const { db } = useDb();
  const { catalog } = useCatalog();
  const { data, error, loading } = useFetch(() => api.trialDetail(db, trialId!), [db, trialId]);

  if (loading) return <main className="app-main"><div className="empty-state">Loading…</div></main>;
  if (error) {
    return (
      <main className="app-main">
        <div className="page">
          <div className="error-banner">{error}</div>
          <p className="small muted">
            If this trial exists, it may live in a different database — check the database selector in the
            top bar.
          </p>
          <Link className="btn" to={`/browse${db ? `?db=${db}` : ""}`}>← Back to Browse</Link>
        </div>
      </main>
    );
  }
  if (!data) return null;

  const { trial, run_result, gate_result, cost_record } = data;

  const tiers = [
    { key: "compile", label: "Build", passed: gate_result?.compile_passed ?? null, output: gate_result?.compile_output ?? null },
    { key: "visible", label: "Visible tests", passed: gate_result?.visible_passed ?? null, output: gate_result?.visible_output ?? null },
    { key: "hidden", label: "Hidden tests", passed: gate_result?.hidden_passed ?? null, output: gate_result?.hidden_output ?? null },
  ];

  return (
    <main className="app-main">
      <div className="page-wide">
        <div className="spread">
          <h1 className="mono" style={{ fontSize: "var(--text-lg)" }}>{trial.id}</h1>
          <Link className="btn sm" to={`/browse${db ? `?db=${db}` : ""}`}>← All trials</Link>
        </div>

        <div className="card">
          <div className="card-title">Axes</div>
          <div className="row wrap">
            <IdChip catalog={catalog} kind="task" id={trial.task_id} />
            <IdChip catalog={catalog} kind="methodology" id={trial.methodology_id} />
            <IdChip catalog={catalog} kind="repo_context" id={trial.repo_context_id} />
            <IdChip catalog={catalog} kind="model" id={trial.model} />
            <IdChip catalog={catalog} kind="runner" id={trial.runner} />
            <span className="badge neutral">rep {trial.rep}</span>
          </div>
        </div>

        <div className="grid-2">
          <div className="card">
            <div className="card-title">Gate scorecard</div>
            {gate_result === null ? (
              <p className="small muted" style={{ margin: 0 }}>No gate verdict recorded for this trial.</p>
            ) : (
              <div className="stack" data-testid="gate-tiers">
                <div className="row">
                  <span className={`badge ${gate_result.passed ? "ok" : "fail"}`} style={{ fontSize: "var(--text-sm)" }}>
                    {gate_result.passed ? "HIDDEN GATE PASSED" : "HIDDEN GATE FAILED"}
                  </span>
                  <span className="xsmall muted">(the hidden tier is the definitive quality gate)</span>
                </div>
                {tiers.map((t) => (
                  <div key={t.key}>
                    <div className="row" style={{ marginBottom: "var(--space-1)" }}>
                      <TierBadge label={t.label} passed={t.passed} />
                    </div>
                    {t.output ? (
                      <details className="logbox">
                        <summary>raw output ({t.output.length.toLocaleString()} chars)</summary>
                        <pre data-testid={`tier-log-${t.key}`}>{t.output}</pre>
                      </details>
                    ) : (
                      <span className="xsmall faint">no output recorded{t.passed === null ? " (tier not run)" : ""}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-title">Execution & cost</div>
            <div className="table-wrap">
              <table className="table">
                <tbody>
                  <tr><td className="muted">Wall time</td><td>{fmtSeconds(run_result?.wall_seconds ?? null)}</td></tr>
                  <tr><td className="muted">Exit status</td><td>{run_result?.exit_status ?? "—"}</td></tr>
                  <tr><td className="muted">Error</td><td className="small">{run_result?.error ?? "—"}</td></tr>
                  <tr><td className="muted">Cost (API-rate)</td><td>{fmtUsd(cost_record?.usd_equiv ?? null)}</td></tr>
                  <tr>
                    <td className="muted">Self-reported</td>
                    <td>
                      {cost_record
                        ? cost_record.native_unit === "usd_self_reported"
                          ? `${fmtUsd(cost_record.native_amount)} (reported by the CLI)`
                          : `${fmtUsd(cost_record.native_amount)} (${cost_record.native_unit})`
                        : "—"}
                    </td>
                  </tr>
                  <tr>
                    <td className="muted">Tokens</td>
                    <td>
                      {cost_record
                        ? `${fmtTokens(cost_record.input_tokens)} in · ${fmtTokens(cost_record.output_tokens)} out · ${fmtTokens(cost_record.cache_read_tokens)} cache`
                        : "—"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Diff (as captured, unblinded)</div>
          {run_result ? (
            <div style={{ height: "32rem", display: "flex", flexDirection: "column" }}>
              <UnifiedDiffPane diff={run_result.diff} testId="trial-diff" />
            </div>
          ) : (
            <p className="small muted" style={{ margin: 0 }}>No run result recorded.</p>
          )}
        </div>
      </div>
    </main>
  );
}
