// Grading picker. Fixes the old flow's complaints head-on:
//  - all five dimensions are visible up front (catalog reference below the
//    picker), not hidden behind choosing an axis first;
//  - every id everywhere has a hover preview;
//  - gradeable cells are listed as concrete rows (what will actually be
//    compared), not as cascading dropdowns you must guess through.

import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, fmtTokens, fmtUsd } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import { AXES, AXIS_CELL_KEYS, AXIS_LABELS } from "../types";
import type { Axis, Cell, JudgeProviderInfo } from "../types";
import { IdChip, PreviewBody } from "../components/previews";
import { HoverPreview } from "../components/HoverPreview";

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), max - 20))}…`;
}

const CELL_KIND: Record<string, "task" | "methodology" | "repo_context" | "model" | "runner"> = {
  task_id: "task",
  methodology_id: "methodology",
  repo_context_id: "repo_context",
  model: "model",
  runner: "runner",
};

const AXIS_NOUNS: Record<Axis, [string, string]> = {
  methodology: ["methodology", "methodologies"],
  model: ["model", "models"],
  repo_context: ["repo context", "repo contexts"],
  runner: ["runner", "runners"],
};

function CellRow({
  axis,
  cell,
  onStart,
  onJudge,
  judgeSelected,
  catalog,
  starting,
}: {
  axis: Axis;
  cell: Cell;
  onStart: () => void;
  onJudge: () => void;
  judgeSelected: boolean;
  catalog: ReturnType<typeof useCatalog>["catalog"];
  starting: boolean;
}) {
  const pinned = Object.entries(cell).filter(([k]) => k !== "n_values" && k !== "n_pairs");
  const noun = AXIS_NOUNS[axis][cell.n_values === 1 ? 0 : 1];
  return (
    <tr data-testid="cell-row">
      <td>
        <span className="row wrap" style={{ gap: "var(--space-1)" }}>
          {pinned.map(([k, v]) => (
            <IdChip key={k} catalog={catalog} kind={CELL_KIND[k]} id={String(v)} />
          ))}
        </span>
      </td>
      <td>{cell.n_values} {noun}</td>
      <td className="num">{cell.n_pairs}</td>
      <td style={{ textAlign: "right" }}>
        <span className="row" style={{ gap: "var(--space-1)", justifyContent: "flex-end" }}>
          <button className="btn sm primary" onClick={onStart} disabled={starting} data-testid="start-session">
            {starting ? "Starting…" : "Grade myself"}
          </button>
          <button
            className={`btn sm${judgeSelected ? " primary" : ""}`}
            onClick={onJudge}
            aria-pressed={judgeSelected}
            data-testid="start-llm-judge"
            title="Have an LLM judge this cell's blind pairs for you"
          >
            LLM judge
          </button>
        </span>
      </td>
    </tr>
  );
}

// Cell dict -> the query params /api/judge/plan and /api/judge-sessions take.
function cellParams(axis: Axis, cell: Cell): Record<string, string> {
  const params: Record<string, string> = { task: cell.task_id };
  for (const [param, key] of Object.entries({
    methodology: "methodology_id",
    repo_context: "repo_context_id",
    model: "model",
    runner: "runner",
  })) {
    const v = (cell as unknown as Record<string, string>)[key];
    if (v !== undefined && key !== AXIS_CELL_KEYS[axis]) params[param] = v;
  }
  return params;
}

function JudgeConfigPanel({ axis, cell, onClose }: { axis: Axis; cell: Cell; onClose: () => void }) {
  const { db } = useDb();
  const navigate = useNavigate();
  const { data: providers } = useFetch(() => api.judgeProviders(), []);
  const [providerId, setProviderId] = useState<string | null>(null);
  const [model, setModel] = useState<string>("");
  const [passes, setPasses] = useState<2 | 1>(2);
  const [phrase, setPhrase] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  // Default to the first AVAILABLE provider (claude-cli first, mock last).
  useEffect(() => {
    if (!providers || providerId !== null) return;
    const first = providers.find((p) => p.available) ?? providers[0];
    if (first) {
      setProviderId(first.id);
      setModel(first.default_model);
    }
  }, [providers, providerId]);

  const provider: JudgeProviderInfo | undefined = providers?.find((p) => p.id === providerId);

  const { data: plan, error: planError } = useFetch(
    () =>
      providerId
        ? api.judgePlan(db, {
            axis,
            ...cellParams(axis, cell),
            provider: providerId,
            judge_model: model,
            passes: String(passes),
          })
        : Promise.resolve(null),
    [db, axis, JSON.stringify(cell), providerId, model, passes],
  );

  const needsPhrase = Boolean(provider && provider.confirm_phrase);
  const armed = !needsPhrase || phrase === provider?.confirm_phrase;

  const start = async () => {
    if (!providerId) return;
    setStarting(true);
    setStartError(null);
    try {
      const started = await api.judgeStart({
        db,
        axis,
        ...cellParams(axis, cell),
        provider: providerId,
        judge_model: model,
        passes,
        confirm_phrase: needsPhrase ? phrase : undefined,
      });
      navigate(`/grade/judge/${started.session_id}${db ? `?db=${db}` : ""}`);
    } catch (e) {
      setStartError(String((e as Error).message ?? e));
      setStarting(false);
    }
  };

  return (
    <div className="card" data-testid="judge-config" style={{ borderColor: "var(--color-accent)" }}>
      <div className="spread">
        <div className="card-title" style={{ marginBottom: 0 }}>LLM judge — configure &amp; launch</div>
        <button className="btn sm ghost" onClick={onClose} data-testid="judge-config-close">✕ close</button>
      </div>
      <p className="small muted">
        The judge grades the same blind pairs you would see — anonymized diffs plus the gate
        scorecard, never identities or spend. Each pair is judged twice with sides swapped
        (position-bias control); if the passes disagree, the pair is scored a tie.
      </p>

      <div className="stack" style={{ gap: "var(--space-2)" }}>
        <div className="row wrap" data-testid="judge-providers">
          {(providers ?? []).map((p) => (
            <button
              key={p.id}
              className={`btn sm${p.id === providerId ? " primary" : ""}`}
              disabled={!p.available}
              onClick={() => {
                setProviderId(p.id);
                setModel(p.default_model);
                setPhrase("");
              }}
              aria-pressed={p.id === providerId}
              title={p.available ? p.label : `${p.label} — unavailable: ${p.reason}`}
              data-testid={`judge-provider-${p.id}`}
            >
              {p.label}
              <span className={`badge ${p.billing === "free" ? "neutral" : "accent"}`}>{p.billing}</span>
            </button>
          ))}
        </div>
        {provider && !provider.available && (
          <div className="error-banner">{provider.label} is unavailable: {provider.reason}</div>
        )}

        {provider && (
          <div className="row wrap" style={{ gap: "var(--space-3)" }}>
            <label className="row" style={{ gap: "var(--space-1)" }}>
              <span className="xsmall muted">Judge model</span>
              <select
                className="control"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                data-testid="judge-model"
              >
                {provider.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
            <label className="row" style={{ gap: "var(--space-1)" }}>
              <span className="xsmall muted">Passes</span>
              <select
                className="control"
                value={passes}
                onChange={(e) => setPasses(Number(e.target.value) === 1 ? 1 : 2)}
                data-testid="judge-passes"
              >
                <option value={2}>Double, position-debiased (recommended)</option>
                <option value={1}>Single (half the calls, keeps position bias)</option>
              </select>
            </label>
          </div>
        )}

        {planError && <div className="error-banner">{planError}</div>}
        {plan && (
          <div className="info-banner" data-testid="judge-plan">
            <strong>{plan.n_pairs}</strong> blind pair{plan.n_pairs === 1 ? "" : "s"} →{" "}
            <strong>{plan.n_calls}</strong> judge call{plan.n_calls === 1 ? "" : "s"} · est.{" "}
            {fmtTokens(plan.est_input_tokens)} tokens in / {fmtTokens(plan.est_output_tokens)} out
            {" · "}
            {plan.billing === "free" && "zero spend"}
            {plan.billing === "subscription" && (
              <>est. {plan.est_usd !== null ? fmtUsd(plan.est_usd) : "n/a"} at API rates — billed against
                your Claude subscription quota, not in dollars</>
            )}
            {plan.billing === "metered" && "billed by GitHub against your account/org tier"}
          </div>
        )}

        {needsPhrase && (
          <label className="row" style={{ gap: "var(--space-2)" }}>
            <span className="small">
              This spends your {provider?.billing} budget — type{" "}
              <code>{provider?.confirm_phrase}</code> to arm:
            </span>
            <input
              className="control"
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              placeholder={provider?.confirm_phrase ?? ""}
              data-testid="judge-confirm-input"
              style={{ width: "8rem" }}
            />
          </label>
        )}

        <div className="row">
          <button
            className="btn primary"
            onClick={() => void start()}
            disabled={!provider?.available || !armed || starting || !plan}
            data-testid="judge-launch"
          >
            {starting ? "Launching…" : "Launch the LLM judge"}
          </button>
          {!armed && needsPhrase && (
            <span className="xsmall muted">the launch button arms once the phrase matches</span>
          )}
        </div>
        {startError && <div className="error-banner">{startError}</div>}
      </div>
    </div>
  );
}

function AxisCells({ axis }: { axis: Axis }) {
  const { db } = useDb();
  const navigate = useNavigate();
  const { catalog } = useCatalog();
  const { data: cells, error, loading } = useFetch(() => api.cells(db, axis), [db, axis]);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [judgeCellIdx, setJudgeCellIdx] = useState<number | null>(null);

  const start = async (cell: Cell) => {
    setStarting(true);
    setStartError(null);
    try {
      const cellParams: Record<string, string> = { task: cell.task_id };
      for (const [param, key] of Object.entries({
        methodology: "methodology_id",
        repo_context: "repo_context_id",
        model: "model",
        runner: "runner",
      })) {
        const v = (cell as unknown as Record<string, string>)[key];
        if (v !== undefined && key !== AXIS_CELL_KEYS[axis]) cellParams[param] = v;
      }
      const session = await api.startSession(db, axis, cellParams);
      navigate(`/grade/session/${session.session_id}${db ? `?db=${db}` : ""}`);
    } catch (e) {
      setStartError(String((e as Error).message ?? e));
      setStarting(false);
    }
  };

  if (loading) return <p className="muted small">Loading cells…</p>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!cells || cells.length === 0) {
    return (
      <div className="empty-state" data-testid="no-cells">
        No gradeable cells for the {AXIS_LABELS[axis]} axis in this database.
        <br />
        <span className="xsmall">
          A cell is gradeable when ≥2 different {AXIS_LABELS[axis].toLowerCase()} values passed the hidden
          gate with every other axis held fixed.
        </span>
      </div>
    );
  }

  return (
    <>
      {startError && <div className="error-banner" style={{ marginBottom: "var(--space-2)" }}>{startError}</div>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Cell (pinned axes)</th>
              <th>Contenders</th>
              <th className="num">Pairs</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {cells.map((cell, i) => (
              <CellRow
                key={i}
                axis={axis}
                cell={cell}
                catalog={catalog}
                onStart={() => start(cell)}
                onJudge={() => setJudgeCellIdx(judgeCellIdx === i ? null : i)}
                judgeSelected={judgeCellIdx === i}
                starting={starting}
              />
            ))}
          </tbody>
        </table>
      </div>
      <p className="xsmall muted" style={{ marginBottom: 0 }}>
        Hover any id for details. The <strong>{AXIS_LABELS[axis]}</strong> contenders vary inside the
        session — their identities stay hidden until you finish and reveal. <em>Grade myself</em> is
        the blind manual mode; <em>LLM judge</em> hands the same blind pairs to a model.
      </p>
      {judgeCellIdx !== null && cells[judgeCellIdx] && (
        <JudgeConfigPanel
          axis={axis}
          cell={cells[judgeCellIdx]}
          onClose={() => setJudgeCellIdx(null)}
        />
      )}
    </>
  );
}

function CatalogReference() {
  const { catalog } = useCatalog();
  if (!catalog) return null;

  const sections: { title: string; kind: "task" | "methodology" | "repo_context" | "model" | "runner"; entries: { id: string; blurb: string | null }[] }[] = [
    {
      title: "Tasks",
      kind: "task",
      entries: catalog.tasks.map((t) => ({
        id: t.id,
        // Normalize the YAML line folds, then truncate on a word boundary
        // with a real ellipsis — never a mid-sentence hard cut.
        blurb: t.instruction
          ? `${t.difficulty ? `[${t.difficulty}] ` : ""}${truncate(t.instruction.replace(/\s+/g, " "), 110)}`
          : null,
      })),
    },
    {
      title: "Methodologies",
      kind: "methodology",
      entries: catalog.methodologies.map((m) => ({ id: m.id, blurb: m.description })),
    },
    {
      title: "Repo contexts",
      kind: "repo_context",
      entries: catalog.repo_contexts.map((c) => ({ id: c.id, blurb: c.description })),
    },
    {
      title: "Models",
      kind: "model",
      entries: catalog.models.map((m) => ({
        id: m.id,
        blurb: m.pricing ? `${m.pricing.vendor} · $${m.pricing.input_per_mtok}/MTok in · $${m.pricing.output_per_mtok}/MTok out` : null,
      })),
    },
    {
      title: "Runners",
      kind: "runner",
      entries: catalog.runners.map((r) => ({ id: r.id, blurb: r.description })),
    },
  ];

  return (
    <div className="card" data-testid="catalog-reference">
      <div className="card-title">The five axes — everything available</div>
      <div className="grid-2">
        {sections.map((sec) => (
          <div key={sec.title}>
            <h3>{sec.title}</h3>
            <div className="stack" style={{ gap: "var(--space-1)" }}>
              {sec.entries.map((e) => (
                <div key={e.id} className="row small" style={{ alignItems: "baseline" }}>
                  <HoverPreview anchor={<span className="badge neutral mono">{e.id}</span>}>
                    <PreviewBody catalog={catalog} kind={sec.kind} id={e.id} />
                  </HoverPreview>
                  {/* flex items default to min-width:auto — without minWidth:0
                      the ellipsis never engages and the card overflows the page */}
                  <span
                    className="muted xsmall"
                    style={{ flex: "1 1 0", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {e.blurb ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResumeCard() {
  const { db } = useDb();
  const { data: sessions } = useFetch(() => api.sessions(db), [db]);
  const unfinished = (sessions ?? []).filter(
    (s) => s.n_judged < s.total_pairs && s.revealed_at === null,
  );
  if (unfinished.length === 0) return null;
  return (
    <div className="info-banner" style={{ marginBottom: "var(--space-4)" }} data-testid="picker-resume">
      <div className="spread">
        <span>
          You have {unfinished.length} unfinished session{unfinished.length === 1 ? "" : "s"} — starting a
          new one on the same cell fragments your judgments.
        </span>
      </div>
      <div className="stack" style={{ gap: "var(--space-1)", marginTop: "var(--space-2)" }}>
        {unfinished.slice(0, 4).map((s) => (
          <div key={s.session_id} className="row small">
            <span className="badge accent">{AXIS_LABELS[s.axis] ?? s.axis}</span>
            {s.mode === "llm" && <span className="badge neutral" title={`judged by ${s.judge_model ?? "an LLM"}`}>LLM</span>}
            <span className="mono xsmall">{Object.values(s.cell).join(" · ")}</span>
            <span className="muted xsmall">{s.n_judged}/{s.total_pairs} judged</span>
            <Link
              className="btn sm"
              to={s.mode === "llm"
                ? `/grade/judge/${s.session_id}${db ? `?db=${db}` : ""}`
                : `/grade/session/${s.session_id}${db ? `?db=${db}` : ""}`}
            >
              Resume
            </Link>
          </div>
        ))}
        {unfinished.length > 4 && (
          <span className="xsmall muted">
            +{unfinished.length - 4} more — the <Link to={`/${db ? `?db=${db}` : ""}`}>dashboard</Link> lists
            them all.
          </span>
        )}
      </div>
    </div>
  );
}

export function GradePicker() {
  const { db } = useDb();
  const { data: axes } = useFetch(() => api.axes(db), [db]);
  const [params, setParams] = useSearchParams();
  const axisParam = params.get("axis");
  const axis: Axis = AXES.includes(axisParam as Axis) ? (axisParam as Axis) : "methodology";
  const setAxis = (a: Axis) => {
    const next = new URLSearchParams(params);
    next.set("axis", a);
    setParams(next, { replace: true });
  };

  const gradeable = new Map((axes ?? []).map((a) => [a.axis, a.n_cells]));

  return (
    <main className="app-main">
      <div className="page">
        <h1>Pick a contest</h1>
        <ResumeCard />
        <div className="card">
          <div className="card-title">Comparison axis</div>
          <div className="row wrap" data-testid="axis-picker">
            {AXES.map((a) => {
              // axes not loaded yet -> show a placeholder, not a false "0"
              const n = axes === null ? null : gradeable.get(a) ?? 0;
              return (
                <button
                  key={a}
                  className={`btn ${axis === a ? "primary" : ""}`}
                  onClick={() => setAxis(a)}
                  aria-pressed={axis === a}
                  data-testid={`axis-${a}`}
                >
                  {AXIS_LABELS[a]}
                  <span className={`badge ${(n ?? 0) > 0 ? (axis === a ? "neutral" : "accent") : "neutral"}`}>
                    {n ?? "…"}
                  </span>
                </button>
              );
            })}
          </div>
          <p className="xsmall muted" style={{ marginBottom: 0 }}>
            The chosen axis varies inside a session; every other axis is pinned to one value (the “cell”).
          </p>
        </div>

        <div className="card">
          <div className="card-title">Gradeable cells</div>
          <AxisCells axis={axis} />
        </div>

        <CatalogReference />
      </div>
    </main>
  );
}
