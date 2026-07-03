// Run launcher + live progress. Spend safety is structural: the runner
// defaults to a free self-test runner, the plan preview shows exactly what
// would execute, and a paid runner (claude-code) refuses to start until the
// user types the confirmation phrase next to a cost estimate.

import { useEffect, useMemo, useRef, useState } from "react";
import { api, fmtDate, fmtSeconds, fmtUsd } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import type { PlannedTrial, RunEvent, RunPlan, RunSnapshot } from "../types";
import { IdChip } from "../components/previews";

function MultiPicker({
  label,
  ids,
  value,
  onChange,
  kind,
}: {
  label: string;
  ids: string[];
  value: string;
  onChange: (v: string) => void;
  kind: "task" | "methodology" | "repo_context";
}) {
  const { catalog } = useCatalog();
  const selected = value === "all" ? new Set(ids) : new Set(value.split(",").filter(Boolean));

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next.size === ids.length ? "all" : Array.from(next).join(","));
  };

  return (
    <div className="field">
      <label>{label}</label>
      <div className="row wrap" style={{ gap: "var(--space-1)" }}>
        {ids.map((id) => (
          <button
            key={id}
            type="button"
            className={`btn sm ${selected.has(id) ? "primary" : ""}`}
            onClick={() => toggle(id)}
            data-testid={`pick-${kind}-${id}`}
          >
            {id}
          </button>
        ))}
      </div>
      <span className="xsmall faint">
        {selected.size === 0 ? "none selected" : value === "all" ? "all selected" : `${selected.size} selected`}
        {" — hover ids in the plan preview for details"}
      </span>
      <span style={{ display: "none" }}>
        {/* keep catalog referenced so previews stay warm */}
        {catalog ? "" : ""}
      </span>
    </div>
  );
}

function PlanPreview({ plan }: { plan: RunPlan }) {
  const { catalog } = useCatalog();
  const byTask = useMemo(() => {
    const m = new Map<string, PlannedTrial[]>();
    for (const t of plan.trials) {
      const arr = m.get(t.task_id) ?? [];
      arr.push(t);
      m.set(t.task_id, arr);
    }
    return m;
  }, [plan]);

  return (
    <div data-testid="plan-preview">
      <div className="row wrap" style={{ marginBottom: "var(--space-2)" }}>
        <span className="badge accent">{plan.n_trials} trial{plan.n_trials === 1 ? "" : "s"}</span>
        {plan.paid ? (
          <span className="badge warn">spends real API budget</span>
        ) : (
          <span className="badge ok">free (no API spend)</span>
        )}
      </div>
      <div className="table-wrap" style={{ maxHeight: "16rem", overflowY: "auto" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Methodology</th>
              <th>Context</th>
              <th>Model</th>
              <th className="num">Reps</th>
            </tr>
          </thead>
          <tbody>
            {Array.from(byTask.entries()).flatMap(([task, trials]) => {
              const byCombo = new Map<string, PlannedTrial[]>();
              for (const t of trials) {
                const key = `${t.methodology_id}|${t.repo_context_id}|${t.model}`;
                const arr = byCombo.get(key) ?? [];
                arr.push(t);
                byCombo.set(key, arr);
              }
              return Array.from(byCombo.entries()).map(([key, combo]) => (
                <tr key={`${task}|${key}`}>
                  <td><IdChip catalog={catalog} kind="task" id={task} /></td>
                  <td><IdChip catalog={catalog} kind="methodology" id={combo[0].methodology_id} /></td>
                  <td><IdChip catalog={catalog} kind="repo_context" id={combo[0].repo_context_id} /></td>
                  <td><IdChip catalog={catalog} kind="model" id={combo[0].model} /></td>
                  <td className="num">{combo.length}</td>
                </tr>
              ));
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LiveRun({ runId, onDone }: { runId: string; onDone: () => void }) {
  const [snap, setSnap] = useState<RunSnapshot | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.run(runId).then((s) => {
      if (!cancelled) setSnap(s);
    });
    const es = new EventSource(`/api/runs/${runId}/events`);
    esRef.current = es;
    es.onmessage = (msg) => {
      const ev = JSON.parse(msg.data) as RunEvent;
      if (ev.type === "end") {
        es.close();
        api.run(runId).then((s) => {
          if (!cancelled) setSnap(s);
        });
        onDone();
        return;
      }
      setEvents((prev) => [...prev, ev]);
    };
    es.onerror = () => {
      // server went away or stream closed — fall back to a snapshot
      es.close();
    };
    return () => {
      cancelled = true;
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const progressByTrial = useMemo(() => {
    const m = new Map<string, RunEvent>();
    for (const e of events) if (e.type === "progress" && e.trial_id) m.set(e.trial_id, e);
    return m;
  }, [events]);

  if (!snap) return <p className="muted small">Connecting…</p>;

  const trials = snap.trials ?? [];
  const nDone = progressByTrial.size;
  const statusEvent = events.find((e) => e.type === "status");
  const status = statusEvent?.status ?? snap.status;

  return (
    <div data-testid="live-run">
      <div className="row wrap" style={{ marginBottom: "var(--space-2)" }}>
        <span className={`badge ${status === "running" ? "accent" : status === "done" ? "ok" : "warn"}`} data-testid="run-status">
          {status}
        </span>
        <span className="small muted">
          {nDone}/{trials.length || snap.n_trials} trials · started {fmtDate(snap.created_at)}
        </span>
        {status === "running" && (
          <button className="btn sm danger" onClick={() => void api.runCancel(runId)} data-testid="cancel-run">
            Stop after current trial
          </button>
        )}
        {snap.error && <span className="error-banner">{snap.error}</span>}
      </div>
      <div className="table-wrap" style={{ maxHeight: "24rem", overflowY: "auto" }}>
        <table className="table" data-testid="run-progress-table">
          <thead>
            <tr>
              <th>Trial</th>
              <th>Status</th>
              <th>Gate</th>
              <th className="num">USD</th>
              <th className="num">Tokens</th>
              <th className="num">Wall</th>
            </tr>
          </thead>
          <tbody>
            {trials.map((t) => {
              const ev = progressByTrial.get(t.id);
              const s = ev?.summary;
              return (
                <tr key={t.id}>
                  <td className="mono xsmall">{t.id}</td>
                  <td>
                    {!ev ? (
                      <span className="badge neutral">pending</span>
                    ) : s?.skipped ? (
                      <span className="badge neutral">skipped (exists)</span>
                    ) : s?.error ? (
                      <span className="badge fail" title={s.error ?? undefined}>error</span>
                    ) : (
                      <span className="badge ok">done</span>
                    )}
                  </td>
                  <td>
                    {s && !s.skipped && s.passed !== null && s.passed !== undefined ? (
                      <span className={`badge ${s.passed ? "ok" : "fail"}`}>{s.passed ? "PASS" : "FAIL"}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="num">{s && !s.skipped ? fmtUsd(s.usd ?? null) : ""}</td>
                  <td className="num">{s && !s.skipped && s.tokens ? s.tokens.toLocaleString() : ""}</td>
                  <td className="num">{s && !s.skipped ? fmtSeconds(s.wall_seconds ?? null) : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Runs() {
  const { db } = useDb();
  const { catalog } = useCatalog();
  const [task, setTask] = useState("all");
  const [methodology, setMethodology] = useState("all");
  const [repoContext, setRepoContext] = useState("all");
  const [model, setModel] = useState("");
  const [runner, setRunner] = useState("oracle");
  const [reps, setReps] = useState(1);
  const [targetDb, setTargetDb] = useState("");
  const [plan, setPlan] = useState<RunPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [confirmPhrase, setConfirmPhrase] = useState("");
  const [startError, setStartError] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const { data: runList, reload: reloadRuns } = useFetch(() => api.runs(), []);
  const { data: dbList } = useFetch(() => api.dbs(), [db]);
  const activeDbName = db || dbList?.find((d) => d.is_default)?.name || "server default";

  useEffect(() => {
    const running = (runList ?? []).find((r) => r.status === "running");
    if (running && !activeRunId) setActiveRunId(running.id);
  }, [runList, activeRunId]);

  const localTasks = (catalog?.tasks ?? []).filter((t) => t.available_locally).map((t) => t.id);
  const localMeths = (catalog?.methodologies ?? []).filter((m) => m.available_locally).map((m) => m.id);
  const localCtxs = (catalog?.repo_contexts ?? []).filter((c) => c.available_locally).map((c) => c.id);
  // Only real runners belong in the launcher (db-only ids like a demo
  // runner aren't executable); unlaunchable ones stay visible but disabled
  // so the axis is fully explained.
  const KNOWN_RUNNERS = ["oracle", "nop", "claude-code", "manual", "copilot-cli"];
  const runners = KNOWN_RUNNERS
    .map((id) => (catalog?.runners ?? []).find((r) => r.id === id))
    .filter((r): r is NonNullable<typeof r> => r !== undefined);

  const doPlan = async () => {
    setPlanError(null);
    setPlan(null);
    if (runner === "claude-code" && !model.trim()) {
      setPlanError("Model is required for claude-code (e.g. claude-haiku-4-5) — see the Models list on the Grade page for priced ids.");
      return;
    }
    try {
      const p = await api.runsPlan(db, {
        task,
        methodology,
        repo_context: repoContext,
        model: model || (runner === "oracle" || runner === "nop" ? "self-test" : ""),
        runner,
        reps: String(reps),
      });
      setPlan(p);
    } catch (e) {
      setPlanError(String((e as Error).message ?? e));
    }
  };

  const doStart = async () => {
    if (!plan) return;
    setStartError(null);
    try {
      const resp = await api.runsStart({
        task,
        methodology,
        repo_context: repoContext,
        model: model || (runner === "oracle" || runner === "nop" ? "self-test" : ""),
        runner,
        reps,
        db: targetDb || db,
        confirm_phrase: plan.paid ? confirmPhrase : undefined,
      });
      setActiveRunId(resp.run_id);
      setPlan(null);
      setConfirmPhrase("");
      reloadRuns();
    } catch (e) {
      setStartError(String((e as Error).message ?? e));
    }
  };

  const selectedRunner = catalog?.runners.find((r) => r.id === runner);
  const needsPhrase = plan?.paid ?? false;
  const phraseOk = !needsPhrase || confirmPhrase === plan?.confirm_phrase;

  return (
    <main className="app-main">
      <div className="page">
        <h1>Runs</h1>

        <div className="card">
          <div className="card-title">Launch trials</div>
          <div className="stack">
            <MultiPicker label="Tasks" ids={localTasks} value={task} onChange={setTask} kind="task" />
            <MultiPicker label="Methodologies" ids={localMeths} value={methodology} onChange={setMethodology} kind="methodology" />
            <MultiPicker label="Repo contexts" ids={localCtxs} value={repoContext} onChange={setRepoContext} kind="repo_context" />
            <div className="row wrap" style={{ alignItems: "flex-end" }}>
              <div className="field">
                <label>Runner</label>
                <select className="control" value={runner} onChange={(e) => { setRunner(e.target.value); setPlan(null); }} data-testid="runner-select">
                  {runners.map((r) => (
                    <option key={r.id} value={r.id} disabled={!r.browser_launchable}>
                      {r.id}
                      {r.paid ? " — PAID" : " — free"}
                      {!r.browser_launchable ? (r.id === "manual" ? " (terminal only)" : " (not runnable)") : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Model{runner === "oracle" || runner === "nop" ? " (label only for self-tests)" : ""}</label>
                <input
                  className="control"
                  value={model}
                  placeholder={runner === "claude-code" ? "e.g. claude-haiku-4-5" : "self-test"}
                  onChange={(e) => setModel(e.target.value)}
                  data-testid="model-input"
                />
              </div>
              <div className="field">
                <label>Reps</label>
                <input
                  className="control"
                  style={{ minWidth: "5rem", width: "5rem" }}
                  type="number"
                  min={1}
                  max={20}
                  value={reps}
                  onChange={(e) => setReps(parseInt(e.target.value || "1", 10))}
                />
              </div>
              <div className="field">
                <label>Write results to</label>
                <input
                  className="control"
                  value={targetDb}
                  placeholder={`${activeDbName} (active)`}
                  onChange={(e) => setTargetDb(e.target.value)}
                  data-testid="target-db"
                />
              </div>
              <button className="btn" onClick={() => void doPlan()} data-testid="plan-run">
                Preview plan
              </button>
            </div>
            {selectedRunner && (
              <p className="xsmall muted" style={{ margin: 0 }}>
                {selectedRunner.description}
              </p>
            )}
            {planError && <div className="error-banner">{planError}</div>}
          </div>

          {plan && (
            <div style={{ marginTop: "var(--space-4)" }}>
              <PlanPreview plan={plan} />

              {plan.paid && (
                <div className="notice-banner" style={{ marginTop: "var(--space-3)" }} data-testid="spend-gate">
                  <strong>This run spends real API money.</strong>{" "}
                  {plan.estimate?.estimated_total_usd !== null && plan.estimate !== null ? (
                    <>
                      Estimated total: <strong>{fmtUsd(plan.estimate.estimated_total_usd)}</strong>{" "}
                      ({plan.estimate.estimate_covers_all_trials
                        ? "based on historical trials of the same task × model"
                        : `historical data covers only ${plan.estimate.n_with_estimate}/${plan.estimate.n_trials} trials — the real total will be higher`})
                    </>
                  ) : (
                    <>No historical cost data for this combination — the estimate is unknown.</>
                  )}
                  {plan.estimate?.pricing_rates && (
                    <div className="xsmall" style={{ marginTop: "var(--space-1)" }}>
                      {Object.entries(plan.estimate.pricing_rates).map(([m, r]) => (
                        <div key={m}>
                          {m}: ${r.input_per_mtok}/MTok in · ${r.output_per_mtok}/MTok out
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="row" style={{ marginTop: "var(--space-2)" }}>
                    <label className="xsmall">
                      Type <strong>{plan.confirm_phrase}</strong> to enable launch:
                    </label>
                    <input
                      className="control"
                      style={{ minWidth: "8rem", width: "8rem" }}
                      value={confirmPhrase}
                      onChange={(e) => setConfirmPhrase(e.target.value)}
                      data-testid="confirm-phrase"
                    />
                  </div>
                </div>
              )}

              <div className="row" style={{ marginTop: "var(--space-3)" }}>
                <button
                  className="btn primary"
                  onClick={() => void doStart()}
                  disabled={!plan.launchable || !phraseOk || plan.n_trials === 0}
                  data-testid="start-run"
                >
                  {plan.paid ? "Launch (spends money)" : "Launch (free)"}
                </button>
                {!plan.launchable && <span className="small muted">{plan.launch_blocked_reason}</span>}
              </div>
              {startError && <div className="error-banner" style={{ marginTop: "var(--space-2)" }}>{startError}</div>}
            </div>
          )}
        </div>

        {activeRunId && (
          <div className="card">
            <div className="card-title">Run {activeRunId}</div>
            <LiveRun runId={activeRunId} onDone={reloadRuns} />
          </div>
        )}

        <div className="card">
          <div className="card-title">Runs this server session</div>
          {(runList ?? []).length === 0 ? (
            <p className="small muted" style={{ margin: 0 }}>
              No runs launched from the browser yet. Terminal runs (python cli.py run) appear in Browse once
              finished.
            </p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Status</th>
                    <th className="num">Trials</th>
                    <th>DB</th>
                    <th>Started</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {(runList ?? []).map((r) => (
                    <tr key={r.id}>
                      <td className="mono xsmall">{r.id}</td>
                      <td>
                        <span className={`badge ${r.status === "running" ? "accent" : r.status === "done" ? "ok" : "warn"}`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="num">{r.n_done}/{r.n_trials}</td>
                      <td className="mono xsmall">{r.db}</td>
                      <td className="xsmall">{fmtDate(r.created_at)}</td>
                      <td>
                        <button className="btn sm" onClick={() => setActiveRunId(r.id)}>
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
