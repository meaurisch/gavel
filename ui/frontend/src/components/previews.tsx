// Axis-value preview cards: hovering any task/methodology/context/model/runner
// id anywhere in the app answers "what is this?" without navigating away.
// (This is the fix for "I do not know which task cosmos-B is".)

import type { Catalog, ModelEntry, RunnerEntry, SpecEntry, TaskEntry } from "../types";
import { fmtUsd } from "../api";
import { HoverPreview } from "./HoverPreview";

/** Task specs are YAML-folded at ~75 columns; re-flow the hard wraps so the
 * card wraps at its own width, keeping paragraph breaks and list items. */
function flowText(text: string): string {
  return text
    .split(/\n\s*\n/)
    .map((para) =>
      para
        .split("\n")
        .reduce<string[]>((acc, line) => {
          const trimmed = line.trim();
          if (!trimmed) return acc;
          if (trimmed.startsWith("-") || acc.length === 0) acc.push(trimmed);
          else acc[acc.length - 1] += ` ${trimmed}`;
          return acc;
        }, [])
        .join("\n"),
    )
    .join("\n\n");
}

function TaskPreviewBody({ t }: { t: TaskEntry }) {
  return (
    <>
      <span className="preview-kicker">Task</span>
      <span className="preview-title">
        {t.id}
        {t.difficulty && <span className="badge neutral" style={{ marginLeft: "0.5em" }}>{t.difficulty}</span>}
      </span>
      {t.instruction ? (
        <span className="preview-body">{flowText(t.instruction)}</span>
      ) : (
        <span className="preview-body faint">
          No local task spec (id exists only in this DB — e.g. synthetic demo data).
        </span>
      )}
      <dl>
        {t.repo && (<><dt>repo</dt><dd>{t.repo}</dd></>)}
        {t.build_cmd && (<><dt>build</dt><dd className="mono">{t.build_cmd}</dd></>)}
        {t.run_cmd && (<><dt>hidden gate</dt><dd className="mono">{t.run_cmd}</dd></>)}
        {t.visible_test_cmd && (<><dt>visible gate</dt><dd className="mono">{t.visible_test_cmd}</dd></>)}
        {t.observe_cmd && (<><dt>observed (non-gating)</dt><dd className="mono">{t.observe_cmd}</dd></>)}
        <dt>trials</dt><dd>{t.n_trials} ({t.n_passers} passed hidden gate)</dd>
      </dl>
    </>
  );
}

function SpecPreviewBody({ s, kind }: { s: SpecEntry; kind: string }) {
  return (
    <>
      <span className="preview-kicker">{kind}</span>
      <span className="preview-title">
        {s.id}
        {s.noop && <span className="badge neutral" style={{ marginLeft: "0.5em" }}>no-op control</span>}
      </span>
      {s.description ? (
        <span className="preview-body">{s.description}</span>
      ) : (
        <span className="preview-body faint">
          No local manifest (id exists only in this DB — e.g. synthetic demo data).
        </span>
      )}
      <dl>
        {s.source && (<><dt>source</dt><dd>{s.source.repo} @ {s.source.commit.slice(0, 10)}</dd></>)}
        {Object.entries(s.harnesses).map(([h, files]) => (
          <span key={h} style={{ display: "contents" }}>
            <dt>{h} files</dt>
            <dd className="mono">{files.join(", ") || "(none)"}</dd>
          </span>
        ))}
        {s.task_affinity.length > 0 && (<><dt>task affinity</dt><dd>{s.task_affinity.join(", ")}</dd></>)}
        <dt>trials</dt><dd>{s.n_trials} ({s.n_passers} passed hidden gate)</dd>
      </dl>
    </>
  );
}

function ModelPreviewBody({ m }: { m: ModelEntry }) {
  return (
    <>
      <span className="preview-kicker">Model</span>
      <span className="preview-title">{m.id}</span>
      {m.pricing ? (
        <dl>
          <dt>vendor</dt><dd>{m.pricing.vendor}</dd>
          <dt>input</dt><dd>{fmtUsd(m.pricing.input_per_mtok)} / MTok</dd>
          <dt>output</dt><dd>{fmtUsd(m.pricing.output_per_mtok)} / MTok</dd>
          <dt>cache read</dt><dd>{fmtUsd(m.pricing.cache_read_per_mtok)} / MTok</dd>
          <dt>trials</dt><dd>{m.n_trials} ({m.n_passers} passed hidden gate)</dd>
        </dl>
      ) : (
        <>
          <span className="preview-body faint">Not in the pricing table (cost/pricing.toml).</span>
          <dl><dt>trials</dt><dd>{m.n_trials} ({m.n_passers} passed hidden gate)</dd></dl>
        </>
      )}
    </>
  );
}

function RunnerPreviewBody({ r }: { r: RunnerEntry }) {
  return (
    <>
      <span className="preview-kicker">Runner</span>
      <span className="preview-title">
        {r.id}
        <span className={`badge ${r.paid ? "warn" : "ok"}`} style={{ marginLeft: "0.5em" }}>
          {r.paid ? "spends API budget" : "free"}
        </span>
      </span>
      <span className="preview-body">{r.description}</span>
      <dl>
        <dt>trials</dt><dd>{r.n_trials} ({r.n_passers} passed hidden gate)</dd>
      </dl>
    </>
  );
}

export type AxisKind = "task" | "methodology" | "repo_context" | "model" | "runner";

export function findEntry(catalog: Catalog, kind: AxisKind, id: string) {
  switch (kind) {
    case "task": return catalog.tasks.find((t) => t.id === id);
    case "methodology": return catalog.methodologies.find((m) => m.id === id);
    case "repo_context": return catalog.repo_contexts.find((c) => c.id === id);
    case "model": return catalog.models.find((m) => m.id === id);
    case "runner": return catalog.runners.find((r) => r.id === id);
  }
}

export function PreviewBody({ catalog, kind, id }: { catalog: Catalog; kind: AxisKind; id: string }) {
  const entry = findEntry(catalog, kind, id);
  if (!entry) {
    return (
      <>
        <span className="preview-kicker">{kind}</span>
        <span className="preview-title">{id}</span>
        <span className="preview-body faint">Unknown id.</span>
      </>
    );
  }
  switch (kind) {
    case "task": return <TaskPreviewBody t={entry as TaskEntry} />;
    case "methodology": return <SpecPreviewBody s={entry as SpecEntry} kind="Methodology" />;
    case "repo_context": return <SpecPreviewBody s={entry as SpecEntry} kind="Repo context" />;
    case "model": return <ModelPreviewBody m={entry as ModelEntry} />;
    case "runner": return <RunnerPreviewBody r={entry as RunnerEntry} />;
  }
}

/** An id rendered as a chip with a hover/focus preview card. */
export function IdChip({
  catalog,
  kind,
  id,
  className,
}: {
  catalog: Catalog | null;
  kind: AxisKind;
  id: string;
  className?: string;
}) {
  const chip = <span className={`badge neutral mono ${className ?? ""}`}>{id}</span>;
  if (!catalog) return chip;
  return (
    <HoverPreview anchor={chip}>
      <PreviewBody catalog={catalog} kind={kind} id={id} />
    </HoverPreview>
  );
}
