// Grading picker. Fixes the old flow's complaints head-on:
//  - all five dimensions are visible up front (catalog reference below the
//    picker), not hidden behind choosing an axis first;
//  - every id everywhere has a hover preview;
//  - gradeable cells are listed as concrete rows (what will actually be
//    compared), not as cascading dropdowns you must guess through.

import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import { AXES, AXIS_CELL_KEYS, AXIS_LABELS } from "../types";
import type { Axis, Cell } from "../types";
import { IdChip, PreviewBody } from "../components/previews";
import { HoverPreview } from "../components/HoverPreview";

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
  catalog,
  starting,
}: {
  axis: Axis;
  cell: Cell;
  onStart: () => void;
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
        <button className="btn sm primary" onClick={onStart} disabled={starting} data-testid="start-session">
          {starting ? "Starting…" : "Grade"}
        </button>
      </td>
    </tr>
  );
}

function AxisCells({ axis }: { axis: Axis }) {
  const { db } = useDb();
  const navigate = useNavigate();
  const { catalog } = useCatalog();
  const { data: cells, error, loading } = useFetch(() => api.cells(db, axis), [db, axis]);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

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
                starting={starting}
              />
            ))}
          </tbody>
        </table>
      </div>
      <p className="xsmall muted" style={{ marginBottom: 0 }}>
        Hover any id for details. The <strong>{AXIS_LABELS[axis]}</strong> contenders vary inside the
        session — their identities stay hidden until you finish and reveal.
      </p>
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
        blurb: t.instruction ? `${t.difficulty ? `[${t.difficulty}] ` : ""}${t.instruction.split("\n")[0]}` : null,
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
            <span className="mono xsmall">{Object.values(s.cell).join(" · ")}</span>
            <span className="muted xsmall">{s.n_judged}/{s.total_pairs} judged</span>
            <Link className="btn sm" to={`/grade/session/${s.session_id}${db ? `?db=${db}` : ""}`}>
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
              const n = gradeable.get(a) ?? 0;
              return (
                <button
                  key={a}
                  className={`btn ${axis === a ? "primary" : ""}`}
                  onClick={() => setAxis(a)}
                  aria-pressed={axis === a}
                  data-testid={`axis-${a}`}
                >
                  {AXIS_LABELS[a]}
                  <span className={`badge ${n > 0 ? (axis === a ? "neutral" : "accent") : "neutral"}`}>{n}</span>
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
