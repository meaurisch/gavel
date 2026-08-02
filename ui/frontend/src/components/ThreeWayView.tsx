// Three-way Original | A | B view: one table per file, rows anchored on
// old-file line numbers, so all three panes are inherently scroll-locked.
// Unchanged regions collapse into expandable gap rows.

import { useMemo, useState } from "react";
import { buildThreeWay, parseUnifiedDiff } from "../lib/diff";
import type { ThreeWayCell } from "../lib/diff";
import type { OriginalsResponse } from "../types";
import { BreakablePath } from "./DiffView";
import "../diff.css";

function splitLines(content: string): string[] {
  const lines = content.split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  return lines;
}

function Cell({ cell, changed, sep }: { cell: ThreeWayCell; changed?: boolean; sep?: boolean }) {
  let cls = "code";
  let text: string = cell.text ?? "";
  if (cell.kind === "add") cls += " cell-add";
  else if (cell.kind === "absent") {
    cls += " cell-absent";
    text = ""; // the red deletion styling already says "removed"
  } else if (cell.kind === "empty") {
    cls += " cell-empty";
    text = "";
  } else if (cell.text === null) {
    cls += " cell-unknown";
    text = "(line unchanged — original not available)";
  } else if (changed) {
    cls += " cell-orig-changed";
  }
  return (
    <>
      <td className={`lineno${sep ? " pane-sep" : ""}`}>{cell.lineNo ?? ""}</td>
      <td className={cls}>{text || " "}</td>
    </>
  );
}

function ThreeWayFileTable({
  path,
  aDiff,
  bDiff,
  original,
  originalNote,
  expandAll,
}: {
  path: string;
  aDiff: string;
  bDiff: string;
  original: string | null;
  originalNote: string | null;
  expandAll: boolean;
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const model = useMemo(() => {
    const aFile = parseUnifiedDiff(aDiff).find((f) => f.displayPath === path);
    const bFile = parseUnifiedDiff(bDiff).find((f) => f.displayPath === path);
    const origLines = original !== null ? splitLines(original) : null;
    return buildThreeWay(path, aFile, bFile, origLines, expanded, expandAll);
  }, [path, aDiff, bDiff, original, expanded, expandAll]);

  return (
    <table className="threeway" data-testid="threeway-file" data-file={path}>
      <colgroup>
        <col className="lineno-col" />
        <col />
        <col className="lineno-col" />
        <col />
        <col className="lineno-col" />
        <col />
      </colgroup>
      <thead>
        <tr>
          <th colSpan={6} className="file-path">
            <BreakablePath path={model.displayPath} />
            {model.status && <span className="muted" style={{ marginLeft: "1em", fontWeight: 400 }}>{model.status}</span>}
            {originalNote && <span className="muted" style={{ marginLeft: "1em", fontWeight: 400 }}>{originalNote}</span>}
          </th>
        </tr>
        <tr>
          <th colSpan={2}>Original</th>
          <th colSpan={2} className="pane-sep">A</th>
          <th colSpan={2} className="pane-sep">B</th>
        </tr>
      </thead>
      <tbody>
        {model.rows.map((row, i) => {
          if (row.kind === "gap") {
            const expandable = original !== null && row.gapStart !== undefined;
            return (
              <tr key={i} className="gap">
                <td colSpan={6}>
                  {expandable ? (
                    <button
                      onClick={() =>
                        setExpanded((prev) => new Set(prev).add(row.gapStart!))
                      }
                    >
                      ▸ unchanged region — {row.gapSize} aligned row{row.gapSize === 1 ? "" : "s"} collapsed · click or <kbd className="key">X</kbd> to expand
                    </button>
                  ) : (
                    <>⋯ unchanged region — {row.gapSize} row{row.gapSize === 1 ? "" : "s"} (original not available) ⋯</>
                  )}
                </td>
              </tr>
            );
          }
          const changed =
            row.a.kind === "absent" ||
            row.b.kind === "absent" ||
            row.a.kind === "add" ||
            row.b.kind === "add";
          return (
            <tr key={i}>
              <Cell cell={row.original} changed={changed && row.original.kind === "context"} />
              <Cell cell={row.a} sep />
              <Cell cell={row.b} sep />
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function ThreeWayDiff({
  aDiff,
  bDiff,
  originals,
  expandAll = false,
}: {
  aDiff: string;
  bDiff: string;
  originals: OriginalsResponse | null;
  expandAll?: boolean;
}) {
  const paths = useMemo(() => {
    const set = new Set<string>();
    for (const f of parseUnifiedDiff(aDiff)) set.add(f.displayPath);
    for (const f of parseUnifiedDiff(bDiff)) set.add(f.displayPath);
    return Array.from(set).sort();
  }, [aDiff, bDiff]);

  const originalByPath = useMemo(() => {
    const map = new Map<string, { content: string | null; note: string | null }>();
    for (const f of originals?.files ?? []) {
      if (f.status === "differs") {
        // The two sides started from different content for this file (only
        // possible when a laid-down file differs between cells). Show A's
        // baseline and say so.
        map.set(f.path, {
          content: f.left_content,
          note: "⚠ sides had different starting content — showing A's",
        });
      } else {
        map.set(f.path, {
          content: f.content,
          note:
            f.status === "unavailable"
              ? "original unavailable"
              : f.status === "new"
                ? "new file — did not exist before the change"
                : null,
        });
      }
    }
    return map;
  }, [originals]);

  return (
    <div className="threeway-pane" data-testid="threeway-pane">
      {originals?.note && <div className="notice-banner" style={{ margin: "var(--space-2)" }}>{originals.note}</div>}
      {paths.length === 0 ? (
        <div className="diff-empty">Empty diffs — no changes outside instruction files.</div>
      ) : (
        paths.map((p) => {
          const orig = originalByPath.get(p);
          return (
            <ThreeWayFileTable
              key={p}
              path={p}
              aDiff={aDiff}
              bDiff={bDiff}
              original={orig?.content ?? null}
              originalNote={orig?.note ?? null}
              expandAll={expandAll}
            />
          );
        })
      )}
    </div>
  );
}
