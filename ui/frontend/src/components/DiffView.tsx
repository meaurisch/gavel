// Two-way diff rendering: each side's anonymized unified diff, rendered as
// per-file tables with inline line numbers, inside independently scrollable
// panes that can optionally scroll in lockstep.

import { useEffect, useMemo, useRef } from "react";
import type { UIEvent } from "react";
import { parseUnifiedDiff } from "../lib/diff";
import type { FileDiff } from "../lib/diff";
import "../diff.css";

/** Path with soft break opportunities after each separator — long .NET
 * namespaces wrap between segments, never mid-word. */
export function BreakablePath({ path }: { path: string }) {
  const segs = path.split("/");
  return (
    <>
      {segs.map((seg, i) => (
        <span key={i}>
          {i > 0 && "/"}
          {i > 0 && <wbr />}
          {seg}
        </span>
      ))}
    </>
  );
}

function FileTable({ file }: { file: FileDiff }) {
  return (
    <div className="diff-file" data-testid="diff-file" data-file={file.displayPath}>
      {/* outer band spans the full (possibly overflowing) content width;
          the inner sticky span keeps the label readable while the pane
          scrolls horizontally */}
      <div className="diff-file-header">
        <span className="diff-file-inner">
          <span className="path"><BreakablePath path={file.displayPath} /></span>
          {file.status !== "modified" && <span className="badge neutral">{file.status}</span>}
          <span className="badge ok">+{file.linesAdded}</span>
          <span className="badge fail">−{file.linesRemoved}</span>
        </span>
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
        <td className="code"><span className="hunk-inner">{header}</span></td>
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
        // One shared inner container spanning max-content: every file
        // section (and its header band) is as wide as the widest line in
        // ANY file, so sticky header labels have slack in every section.
        <div className="diff-pane-inner">
          {files.map((f) => <FileTable key={f.displayPath} file={f} />)}
        </div>
      )}
    </div>
  );
}

export interface TwoWayDiffHandle {
  /** Scroll BOTH panes to a file, each to its own copy — with sync
   * mirroring suppressed, so the panes don't clobber each other's
   * (differently-offset) target positions. */
  jumpToFile(path: string): void;
}

/** Two panes with optional lockstep scrolling. */
export function TwoWayDiff({
  aDiff,
  bDiff,
  sync,
  apiRef,
}: {
  aDiff: string;
  bDiff: string;
  sync: boolean;
  apiRef?: { current: TwoWayDiffHandle | null };
}) {
  const panes = useRef<(HTMLDivElement | null)[]>([null, null]);
  const syncing = useRef(false);

  useEffect(() => {
    if (!apiRef) return;
    apiRef.current = {
      jumpToFile(path: string) {
        syncing.current = true;
        for (const pane of panes.current) {
          if (!pane) continue;
          const target = pane.querySelector<HTMLElement>(`[data-file="${CSS.escape(path)}"]`);
          if (!target) continue;
          pane.scrollTop += target.getBoundingClientRect().top - pane.getBoundingClientRect().top;
        }
        // scroll events dispatch on the next frame — release the guard after
        window.setTimeout(() => {
          syncing.current = false;
        }, 60);
      },
    };
    return () => {
      apiRef.current = null;
    };
  }, [apiRef]);

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
