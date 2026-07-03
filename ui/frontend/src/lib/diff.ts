// Unified-diff parsing + row building for the diff screens.
//
// Rendering contract that fixes the old UI's bugs by construction:
//  - every rendered row carries its own line numbers in the same table row as
//    the code text, so numbers cannot desync from scroll;
//  - the three-way view is ONE table per file whose rows span
//    Original | A | B, anchored on old-file line numbers, so the three panes
//    are inherently scroll-locked.

export interface DiffLine {
  kind: "context" | "add" | "del" | "meta";
  text: string; // without the +/-/space prefix
  oldLine: number | null;
  newLine: number | null;
}

export interface Hunk {
  header: string;
  oldStart: number;
  oldCount: number;
  newStart: number;
  newCount: number;
  lines: DiffLine[];
}

export interface FileDiff {
  oldPath: string | null; // null = created
  newPath: string | null; // null = deleted
  displayPath: string;
  status: "modified" | "created" | "deleted" | "renamed";
  binary: boolean;
  hunks: Hunk[];
  linesAdded: number;
  linesRemoved: number;
}

function stripPrefix(p: string): string | null {
  if (p === "/dev/null") return null;
  if (p.startsWith("a/") || p.startsWith("b/")) return p.slice(2);
  return p;
}

export function parseUnifiedDiff(diff: string): FileDiff[] {
  const files: FileDiff[] = [];
  const lines = diff.split("\n");
  let file: FileDiff | null = null;
  let hunk: Hunk | null = null;
  let oldLine = 0;
  let newLine = 0;

  const flushFile = () => {
    if (file) files.push(file);
    file = null;
    hunk = null;
  };

  for (const raw of lines) {
    if (raw.startsWith("diff --git ")) {
      flushFile();
      // "diff --git a/x b/y" — paths may contain spaces; recover them from the
      // ---/+++ lines below instead, and keep a provisional guess here.
      const m = raw.match(/^diff --git a\/(.*) b\/(.*)$/);
      file = {
        oldPath: m ? m[1] : null,
        newPath: m ? m[2] : null,
        displayPath: m ? m[2] : raw.slice("diff --git ".length),
        status: "modified",
        binary: false,
        hunks: [],
        linesAdded: 0,
        linesRemoved: 0,
      };
      continue;
    }
    if (!file) continue;

    if (raw.startsWith("--- ")) {
      file.oldPath = stripPrefix(raw.slice(4).split("\t")[0]);
      continue;
    }
    if (raw.startsWith("+++ ")) {
      file.newPath = stripPrefix(raw.slice(4).split("\t")[0]);
      continue;
    }
    if (raw.startsWith("Binary files ") || raw.startsWith("GIT binary patch")) {
      file.binary = true;
      continue;
    }
    const hm = raw.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$/);
    if (hm) {
      hunk = {
        header: raw,
        oldStart: parseInt(hm[1], 10),
        oldCount: hm[2] === undefined ? 1 : parseInt(hm[2], 10),
        newStart: parseInt(hm[3], 10),
        newCount: hm[4] === undefined ? 1 : parseInt(hm[4], 10),
        lines: [],
      };
      oldLine = hunk.oldStart;
      newLine = hunk.newStart;
      file.hunks.push(hunk);
      continue;
    }
    if (!hunk) continue; // extended headers (index, mode, rename from/to, …)

    if (raw.startsWith("+")) {
      hunk.lines.push({ kind: "add", text: raw.slice(1), oldLine: null, newLine: newLine++ });
      file.linesAdded++;
    } else if (raw.startsWith("-")) {
      hunk.lines.push({ kind: "del", text: raw.slice(1), oldLine: oldLine++, newLine: null });
      file.linesRemoved++;
    } else if (raw.startsWith(" ")) {
      hunk.lines.push({ kind: "context", text: raw.slice(1), oldLine: oldLine++, newLine: newLine++ });
    } else if (raw.startsWith("\\")) {
      hunk.lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null });
    }
    // anything else between hunks is ignored
  }
  flushFile();

  for (const f of files) {
    if (f.oldPath === null) f.status = "created";
    else if (f.newPath === null) f.status = "deleted";
    else if (f.oldPath !== f.newPath) f.status = "renamed";
    f.displayPath = f.newPath ?? f.oldPath ?? f.displayPath;
  }
  return files;
}

// ---------------------------------------------------------------------------
// Three-way (Original | A | B) row model
// ---------------------------------------------------------------------------

export interface ThreeWayCell {
  kind: "context" | "add" | "del" | "absent" | "empty";
  text: string | null;
  lineNo: number | null;
}

export interface ThreeWayRow {
  kind: "line" | "gap";
  original: ThreeWayCell;
  a: ThreeWayCell;
  b: ThreeWayCell;
  gapSize?: number; // for kind === "gap": how many unchanged lines are hidden
  gapStart?: number; // first hidden old-file line number
}

export interface ThreeWayFile {
  displayPath: string;
  status: string; // per-side statuses joined for the header
  rows: ThreeWayRow[];
  aTouched: boolean;
  bTouched: boolean;
}

interface SideAnnotation {
  // old line number -> the side removed this line
  removed: Set<number>;
  // old line anchor -> lines the side inserted AFTER that old line
  // (anchor 0 = inserted before the first line)
  inserts: Map<number, string[]>;
  // old line number -> context text this side's diff knows
  contextText: Map<number, string>;
  touched: boolean;
}

function annotate(file: FileDiff | undefined): SideAnnotation {
  const ann: SideAnnotation = {
    removed: new Set(),
    inserts: new Map(),
    contextText: new Map(),
    touched: !!file,
  };
  if (!file) return ann;
  for (const hunk of file.hunks) {
    // Anchor for insertions: the old line they follow (0 = before the first
    // line). Git's zero-count convention differs: "@@ -N,0 +... @@" means
    // "insert after old line N", so the anchor is N itself; with a non-zero
    // count the hunk's first line sits AT oldStart, so the anchor starts one
    // before it.
    let lastOld = hunk.oldCount === 0 ? hunk.oldStart : Math.max(0, hunk.oldStart - 1);
    for (const line of hunk.lines) {
      if (line.kind === "del") {
        ann.removed.add(line.oldLine!);
        ann.contextText.set(line.oldLine!, line.text);
        lastOld = line.oldLine!;
      } else if (line.kind === "context") {
        ann.contextText.set(line.oldLine!, line.text);
        lastOld = line.oldLine!;
      } else if (line.kind === "add") {
        const arr = ann.inserts.get(lastOld) ?? [];
        arr.push(line.text);
        ann.inserts.set(lastOld, arr);
      }
    }
  }
  return ann;
}

/**
 * Build the aligned Original | A | B row model for one file.
 *
 * `originalLines` is the reconstructed pre-agent content when available
 * (fills otherwise-invisible unchanged regions); null means unavailable —
 * regions not covered by either diff collapse into gap rows either way,
 * so the view works without it. `expanded` holds gapStart line numbers the
 * user has expanded; `expandAll` opens every gap (only honored when the
 * original is available).
 */
export function buildThreeWay(
  displayPath: string,
  aFile: FileDiff | undefined,
  bFile: FileDiff | undefined,
  originalLines: string[] | null,
  expanded: Set<number> = new Set(),
  expandAll = false,
): ThreeWayFile {
  const a = annotate(aFile);
  const b = annotate(bFile);

  // Total old-file length: known exactly from the original; otherwise the
  // highest old line either diff references.
  let maxOld = originalLines ? originalLines.length : 0;
  for (const ann of [a, b]) {
    for (const n of ann.contextText.keys()) maxOld = Math.max(maxOld, n);
    for (const n of ann.inserts.keys()) maxOld = Math.max(maxOld, n);
  }

  const textOf = (oldNo: number): string | null => {
    const fromDiff = a.contextText.get(oldNo) ?? b.contextText.get(oldNo);
    if (fromDiff !== undefined) return fromDiff;
    if (originalLines && oldNo >= 1 && oldNo <= originalLines.length) {
      return originalLines[oldNo - 1];
    }
    return null;
  };

  const rows: ThreeWayRow[] = [];
  let aNew = 1;
  let bNew = 1;

  const pushInserts = (anchor: number) => {
    const ai = a.inserts.get(anchor) ?? [];
    const bi = b.inserts.get(anchor) ?? [];
    const n = Math.max(ai.length, bi.length);
    for (let k = 0; k < n; k++) {
      rows.push({
        kind: "line",
        original: { kind: "empty", text: null, lineNo: null },
        a: k < ai.length
          ? { kind: "add", text: ai[k], lineNo: aNew++ }
          : { kind: "empty", text: null, lineNo: null },
        b: k < bi.length
          ? { kind: "add", text: bi[k], lineNo: bNew++ }
          : { kind: "empty", text: null, lineNo: null },
      });
    }
  };

  const isInteresting = (oldNo: number): boolean =>
    a.removed.has(oldNo) ||
    b.removed.has(oldNo) ||
    a.inserts.has(oldNo) ||
    b.inserts.has(oldNo) ||
    a.contextText.has(oldNo) ||
    b.contextText.has(oldNo);

  pushInserts(0);

  let gapRun: number[] = [];
  const flushGap = () => {
    if (!gapRun.length) return;
    // Small gaps render as plain context if we know their text; big or
    // unknown gaps collapse (expandable when the original is available).
    const canExpand = originalLines !== null;
    if (canExpand && (gapRun.length <= 3 || expandAll || expanded.has(gapRun[0]))) {
      for (const oldNo of gapRun) {
        const text = textOf(oldNo);
        rows.push({
          kind: "line",
          original: { kind: "context", text, lineNo: oldNo },
          a: { kind: "context", text, lineNo: aNew++ },
          b: { kind: "context", text, lineNo: bNew++ },
        });
      }
    } else {
      rows.push({
        kind: "gap",
        gapSize: gapRun.length,
        gapStart: gapRun[0],
        original: { kind: "empty", text: null, lineNo: null },
        a: { kind: "empty", text: null, lineNo: null },
        b: { kind: "empty", text: null, lineNo: null },
      });
      aNew += gapRun.length;
      bNew += gapRun.length;
    }
    gapRun = [];
  };

  for (let oldNo = 1; oldNo <= maxOld; oldNo++) {
    if (!isInteresting(oldNo)) {
      gapRun.push(oldNo);
      continue;
    }
    flushGap();

    const text = textOf(oldNo);
    const aRemoved = a.removed.has(oldNo);
    const bRemoved = b.removed.has(oldNo);
    rows.push({
      kind: "line",
      original: { kind: "context", text, lineNo: oldNo },
      a: aRemoved
        ? { kind: "absent", text: null, lineNo: null }
        : { kind: "context", text, lineNo: aNew++ },
      b: bRemoved
        ? { kind: "absent", text: null, lineNo: null }
        : { kind: "context", text, lineNo: bNew++ },
    });
    pushInserts(oldNo);
  }
  flushGap();

  const statusBits: string[] = [];
  if (aFile) statusBits.push(`A: ${aFile.status} +${aFile.linesAdded} −${aFile.linesRemoved}`);
  if (bFile) statusBits.push(`B: ${bFile.status} +${bFile.linesAdded} −${bFile.linesRemoved}`);

  return {
    displayPath,
    status: statusBits.join("   ·   "),
    rows,
    aTouched: a.touched,
    bTouched: b.touched,
  };
}
