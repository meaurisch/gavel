// Browse every trial in the DB: filterable table with the full gate
// scorecard, cost, tokens, wall time. Click-through to full trial detail.
// Nothing here is blind — browsing happens outside grading sessions.

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtSeconds, fmtTokens, fmtUsd } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import type { TrialRow } from "../types";
import { GateTriplet } from "../components/GateBadges";
import { IdChip } from "../components/previews";

const FILTER_KEYS = ["task_id", "methodology_id", "repo_context_id", "model", "runner"] as const;
type FilterKey = (typeof FILTER_KEYS)[number];

const FILTER_LABELS: Record<FilterKey, string> = {
  task_id: "Task",
  methodology_id: "Methodology",
  repo_context_id: "Repo context",
  model: "Model",
  runner: "Runner",
};

export function Browse() {
  const { db } = useDb();
  const { catalog } = useCatalog();
  const navigate = useNavigate();
  const { data: trials, error, loading } = useFetch(() => api.trials(db), [db]);
  const [filters, setFilters] = useState<Partial<Record<FilterKey, string>>>({});
  const [gateFilter, setGateFilter] = useState<string>("");

  const values = useMemo(() => {
    const m: Record<FilterKey, Set<string>> = {
      task_id: new Set(),
      methodology_id: new Set(),
      repo_context_id: new Set(),
      model: new Set(),
      runner: new Set(),
    };
    for (const t of trials ?? []) for (const k of FILTER_KEYS) m[k].add(t[k]);
    return m;
  }, [trials]);

  const filtered = useMemo(() => {
    return (trials ?? []).filter((t) => {
      for (const k of FILTER_KEYS) {
        const f = filters[k];
        if (f && t[k] !== f) return false;
      }
      if (gateFilter === "pass" && t.passed !== true) return false;
      if (gateFilter === "fail" && t.passed !== false) return false;
      if (gateFilter === "none" && t.passed !== null) return false;
      return true;
    });
  }, [trials, filters, gateFilter]);

  if (loading) return <main className="app-main"><div className="empty-state">Loading trials…</div></main>;
  if (error) return <main className="app-main"><div className="error-banner">{error}</div></main>;

  return (
    <main className="app-main">
      <div className="page-wide">
        <div className="spread">
          <h1>Browse trials</h1>
          <span className="muted small">
            {filtered.length} of {(trials ?? []).length} trials
          </span>
        </div>

        <div className="card">
          <div className="row wrap" data-testid="browse-filters">
            {FILTER_KEYS.map((k) => (
              <div className="field" key={k}>
                <label>{FILTER_LABELS[k]}</label>
                <select
                  className="control"
                  value={filters[k] ?? ""}
                  onChange={(e) => setFilters((f) => ({ ...f, [k]: e.target.value || undefined }))}
                >
                  <option value="">(all)</option>
                  {Array.from(values[k]).sort().map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </div>
            ))}
            <div className="field">
              <label>Hidden gate</label>
              <select className="control" value={gateFilter} onChange={(e) => setGateFilter(e.target.value)}>
                <option value="">(all)</option>
                <option value="pass">passed</option>
                <option value="fail">failed</option>
                <option value="none">no verdict</option>
              </select>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="table-wrap">
            <table className="table" data-testid="trials-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Methodology</th>
                  <th>Context</th>
                  <th>Model</th>
                  <th>Runner</th>
                  <th className="num">Rep</th>
                  <th>Gate</th>
                  <th className="num">USD</th>
                  <th className="num">Tokens</th>
                  <th className="num">Wall</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t: TrialRow) => (
                  <tr
                    key={t.id}
                    className="clickable"
                    onClick={() => navigate(`/browse/${encodeURIComponent(t.id)}${db ? `?db=${db}` : ""}`)}
                    data-testid="trial-row"
                  >
                    <td><IdChip catalog={catalog} kind="task" id={t.task_id} /></td>
                    <td><IdChip catalog={catalog} kind="methodology" id={t.methodology_id} /></td>
                    <td><IdChip catalog={catalog} kind="repo_context" id={t.repo_context_id} /></td>
                    <td><IdChip catalog={catalog} kind="model" id={t.model} /></td>
                    <td><IdChip catalog={catalog} kind="runner" id={t.runner} /></td>
                    <td className="num">{t.rep}</td>
                    <td>
                      <GateTriplet
                        compilePassed={t.compile_passed}
                        visiblePassed={t.visible_passed}
                        hiddenPassed={t.hidden_passed}
                      />
                    </td>
                    <td className="num">{fmtUsd(t.usd_equiv)}</td>
                    <td className="num">
                      {t.input_tokens !== null
                        ? `${fmtTokens(t.input_tokens)} / ${fmtTokens(t.output_tokens)}`
                        : "—"}
                    </td>
                    <td className="num">{fmtSeconds(t.wall_seconds)}</td>
                    <td className="xsmall muted" style={{ maxWidth: "16rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.error ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 && (
            <div className="empty-state">No trials match the filters.</div>
          )}
        </div>
      </div>
    </main>
  );
}
