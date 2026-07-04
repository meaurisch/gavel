// The single entry point: what's in the active DB, what you can do next,
// and a resume list for unfinished grading sessions. Everything else is one
// click away — no dead ends back to a bare terminal.

import { Link } from "react-router-dom";
import { api } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import { AXIS_LABELS, AXES } from "../types";
import type { Axis } from "../types";
import { IdChip } from "../components/previews";

function CellChips({ cell, catalog }: { cell: Record<string, string>; catalog: ReturnType<typeof useCatalog>["catalog"] }) {
  const kindByKey: Record<string, "task" | "methodology" | "repo_context" | "model" | "runner"> = {
    task_id: "task",
    methodology_id: "methodology",
    repo_context_id: "repo_context",
    model: "model",
    runner: "runner",
  };
  return (
    <span className="row wrap" style={{ gap: "var(--space-1)" }}>
      {Object.entries(cell).map(([k, v]) => (
        <IdChip key={k} catalog={catalog} kind={kindByKey[k] ?? "task"} id={v} />
      ))}
    </span>
  );
}

export function Dashboard() {
  const { db } = useDb();
  const { catalog } = useCatalog();
  const { data: status } = useFetch(() => api.gradingStatus(db), [db]);
  const { data: sessions } = useFetch(() => api.sessions(db), [db]);
  const { data: dbs } = useFetch(() => api.dbs(), [db]);
  const { data: runs } = useFetch(() => api.runs(), [db]);

  const active = dbs?.find((d) => (db === "" ? d.is_default : d.name === db));
  // The dashboard is the canonical resume surface — list them all.
  const unfinished = (sessions ?? []).filter(
    (s) => s.n_judged < s.total_pairs && s.revealed_at === null,
  );
  const activeRun = (runs ?? []).find((r) => r.status === "running");
  const empty = active !== undefined && active.n_trials === 0;

  return (
    <main className="app-main">
      <div className="page">
        <div className="spread" style={{ marginBottom: "var(--space-4)" }}>
          <h1 style={{ margin: 0 }}>Dashboard</h1>
          <span className="muted small" data-testid="active-db">
            {active ? `${active.name} · ${active.n_trials} trials · ${active.n_passers} gate passers · ${active.n_judgments} judgments` : "…"}
          </span>
        </div>

        {active && (
          <div className="stat-strip" style={{ marginBottom: "var(--space-6)" }} data-testid="stat-strip">
            <div className="stat">
              <div className="value">{active.n_trials}</div>
              <div className="label">trials</div>
            </div>
            <div className="stat">
              <div className="value">{active.n_passers}</div>
              <div className="label">gate passers</div>
            </div>
            <div className="stat">
              <div className="value">{active.n_judgments}</div>
              <div className="label">judgments</div>
            </div>
            <div className="stat">
              <div className="value">${active.total_usd.toFixed(2)}</div>
              <div className="label">total spend</div>
            </div>
          </div>
        )}

        {activeRun && (
          <div className="notice-banner" style={{ marginBottom: "var(--space-4)" }}>
            A run is in progress ({activeRun.n_done}/{activeRun.n_trials} trials) —{" "}
            <Link to="/runs">watch it live</Link>.
          </div>
        )}

        {empty && (
          <div className="card" data-testid="getting-started">
            <div className="card-title">Getting started</div>
            <p className="small muted" style={{ marginTop: 0 }}>
              This database has no trials yet. Three ways to get some:
            </p>
            <ol className="small" style={{ margin: 0, paddingLeft: "1.4em" }}>
              <li>
                Seed the synthetic demo (zero API spend): <code>python cli.py demo</code>, then switch the
                database picker (top right) to <code>results-demo.db</code>.
              </li>
              <li>
                <Link to="/runs">Launch a free pipeline self-test run</Link> (oracle/nop runners — no API
                spend).
              </li>
              <li>
                Run real trials from the terminal: <code>python cli.py run --task … --model …</code>.
              </li>
            </ol>
          </div>
        )}

        <div className="grid-2" style={{ marginTop: "var(--space-4)" }}>
          <div className="card">
            <div className="card-title">Grade — blind pairwise comparison</div>
            <p className="small muted" style={{ marginTop: 0 }}>
              Pick a comparison axis and a cell, then judge anonymized A/B diffs. Only hidden-gate passers
              enter grading.
            </p>
            <div className="stack" style={{ gap: "var(--space-1)", marginBottom: "var(--space-3)" }}>
              {status &&
                AXES.map((axis) => {
                  const s = status.axes[axis];
                  if (!s) return null;
                  return (
                    <div key={axis} className="row small" style={{ justifyContent: "space-between" }}>
                      <span>{AXIS_LABELS[axis as Axis]}</span>
                      <span className={s.gradeable_cells > 0 ? "" : "faint"}>
                        {s.gradeable_cells > 0
                          ? `${s.gradeable_cells} gradeable cell${s.gradeable_cells === 1 ? "" : "s"}`
                          : "nothing to compare yet"}
                      </span>
                    </div>
                  );
                })}
            </div>
            <Link className="btn primary" to="/grade" data-testid="go-grade">
              Start grading
            </Link>
          </div>

          <div className="card">
            <div className="card-title">Resume a session</div>
            {unfinished.length === 0 ? (
              <p className="small muted" style={{ margin: 0 }}>
                No unfinished grading sessions in this database.
              </p>
            ) : (
              <div className="stack" style={{ gap: "var(--space-2)" }} data-testid="resume-list">
                {unfinished.map((s) => (
                  <div key={s.session_id} className="spread small">
                    <span className="row wrap" style={{ gap: "var(--space-1)" }}>
                      <span className="badge accent">{AXIS_LABELS[s.axis] ?? s.axis}</span>
                      <CellChips cell={s.cell} catalog={catalog} />
                    </span>
                    <span className="row" style={{ gap: "var(--space-2)" }}>
                      <span className="progress" title={`${s.n_judged} of ${s.total_pairs} judged`}>
                        <span style={{ width: `${Math.round((s.n_judged / s.total_pairs) * 100)}%` }} />
                      </span>
                      <span className="muted xsmall mono">
                        {s.n_judged}/{s.total_pairs}
                      </span>
                      <Link className="btn sm" to={`/grade/session/${s.session_id}`}>
                        Resume
                      </Link>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-title">Runs — execute trials</div>
            <p className="small muted" style={{ marginTop: 0 }}>
              Launch new trials with live progress. Free self-test runners by default; real agent runs
              (claude-code) sit behind an explicit spend confirmation.
            </p>
            <Link className="btn" to="/runs">
              Open run launcher
            </Link>
          </div>

          <div className="card">
            <div className="card-title">Results</div>
            <p className="small muted" style={{ marginTop: 0 }}>
              Browse every trial (gate logs, diffs, costs) or view the Bradley-Terry ranking with the
              cost/quality frontier.
            </p>
            <div className="row">
              <Link className="btn" to="/browse">
                Browse trials
              </Link>
              <Link className="btn" to="/report">
                View report
              </Link>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
