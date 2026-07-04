// Two-way diff rendering: each side's anonymized unified diff, rendered as
// per-file tables with inline line numbers, inside independently scrollable
// panes that can optionally scroll in lockstep.

import { useMemo, useRef } from "react";
import type { UIEvent } from "react";
import { parseUnifiedDiff } from "../lib/diff";
import type { FileDiff } from "../lib/diff";
import "../diff.css";

function FileTable({ file }: { file: FileDiff }) {
  return (
    <div data-testid="diff-file" data-file={file.displayPath}>
      <div className="diff-file-header">
        <span className="path">{file.displayPath}</span>
        {file.status !== "modified" && <span className="badge neutral">{file.status}</span>}
        <span className="badge ok">+{file.linesAdded}</span>
        <span className="badge fail">−{file.linesRemoved}</span>
      </div>
      {file.binary ? (
        <div className="diff-empty">Binary file — no text diff.</div>
      ) : (
        <table className="diff">
          <tbody>
            {file.hunks.map((hunk, hi) => (
              <HunkRows key={hi} header={hunk.header} lines={hunk.lines} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function HunkRows({ header, lines }: { header: string; lines: FileDiff["hunks"][0]["lines"] }) {
  return (
    <>
      <tr className="hunk">
        <td className="lineno" />
        <td className="lineno" />
        <td className="marker" />
        <td className="code">{header}</td>
      </tr>
      {lines.map((line, i) => (
        <tr key={i} className={line.kind} data-old={line.oldLine ?? ""} data-new={line.newLine ?? ""}>
          <td className="lineno" data-testid="lineno-old">{line.oldLine ?? ""}</td>
          <td className="lineno" data-testid="lineno-new">{line.newLine ?? ""}</td>
          <td className="marker">{line.kind === "add" ? "+" : line.kind === "del" ? "−" : ""}</td>
          <td className="code">{line.text || " "}</td>
        </tr>
      ))}
    </>
  );
}

export function UnifiedDiffPane({
  diff,
  testId,
  onScroll,
  scrollRef,
}: {
  diff: string;
  testId?: string;
  onScroll?: (e: UIEvent<HTMLDivElement>) => void;
  scrollRef?: (el: HTMLDivElement | null) => void;
}) {
  const files = useMemo(() => parseUnifiedDiff(diff), [diff]);
  return (
    <div className="diff-pane" data-testid={testId} onScroll={onScroll} ref={scrollRef}>
      {files.length === 0 ? (
        <div className="diff-empty">Empty diff — no changes outside instruction files.</div>
      ) : (
        files.map((f) => <FileTable key={f.displayPath} file={f} />)
      )}
    </div>
  );
}

/** Two panes with optional lockstep scrolling. */
export function TwoWayDiff({
  aDiff,
  bDiff,
  sync,
}: {
  aDiff: string;
  bDiff: string;
  sync: boolean;
}) {
  const panes = useRef<(HTMLDivElement | null)[]>([null, null]);
  const syncing = useRef(false);

  const mirror = (from: number) => () => {
    if (!sync || syncing.current) return;
    const src = panes.current[from];
    const dst = panes.current[1 - from];
    if (!src || !dst) return;
    syncing.current = true;
    dst.scrollTop = src.scrollTop;
    dst.scrollLeft = src.scrollLeft;
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  return (
    <div className="diff-columns" data-testid="diff-columns">
      <UnifiedDiffPane
        diff={aDiff}
        testId="pane-a"
        scrollRef={(el) => (panes.current[0] = el)}
        onScroll={mirror(0)}
      />
      <UnifiedDiffPane
        diff={bDiff}
        testId="pane-b"
        scrollRef={(el) => (panes.current[1] = el)}
        onScroll={mirror(1)}
      />
    </div>
  );
}
