// The blind A/B comparison screen. Keyboard-first, no state loss on reload
// (sessions + judgments are persisted server-side and re-fetched), two-way
// and three-way (Original | A | B) views, and materially more per-side info
// than three checkmarks: per-tier gate logs, cost/tokens/wall-time (when the
// comparison axis allows it), and diff shape proxies.

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useDb } from "../db";
import { useCatalog, useFetch } from "../hooks";
import { AXIS_LABELS } from "../types";
import type { BlindSide, OriginalsResponse, Session } from "../types";
import { fmtSeconds, fmtTokens, fmtUsd } from "../api";
import { TwoWayDiff } from "../components/DiffView";
import type { TwoWayDiffHandle } from "../components/DiffView";
import { ThreeWayDiff } from "../components/ThreeWayView";
import { GateBadges } from "../components/GateBadges";
import { IdChip } from "../components/previews";

const CELL_KIND: Record<string, "task" | "methodology" | "repo_context" | "model" | "runner"> = {
  task_id: "task",
  methodology_id: "methodology",
  repo_context_id: "repo_context",
  model: "model",
  runner: "runner",
};

function SideHeader({ side }: { side: BlindSide }) {
  const gd = side.gate_detail;
  return (
    <div
      className="card"
      style={{
        padding: "var(--space-2) var(--space-3)",
        borderRadius: "var(--radius-1)",
        // Bottom-anchor the expander row: when one side's top row wraps and
        // the other's doesn't, the two cards' interior rows stay aligned
        // (grid stretch already equalizes the card heights themselves).
        display: "flex",
        flexDirection: "column",
      }}
      data-testid={`side-header-${side.label}`}
    >
      <div className="row wrap" style={{ gap: "var(--space-2)" }}>
        <strong style={{ fontSize: "var(--text-lg)" }}>{side.label}</strong>
        <GateBadges
          compilePassed={side.gate.compile_passed}
          visiblePassed={side.gate.visible_passed}
          hiddenPassed={side.gate.hidden_passed}
        />
        <span className="xsmall muted">
          {side.proxy.files_touched} file{side.proxy.files_touched === 1 ? "" : "s"} · +{side.proxy.lines_added} −{side.proxy.lines_removed}
          {side.proxy.new_deps.length > 0 && ` · new deps: ${side.proxy.new_deps.join(", ")}`}
        </span>
        {side.metrics ? (
          <span className="xsmall muted" data-testid={`metrics-${side.label}`}>
            {fmtUsd(side.metrics.usd)} · {fmtTokens(side.metrics.input_tokens)} in / {fmtTokens(side.metrics.output_tokens)} out · {fmtSeconds(side.metrics.wall_seconds)}
          </span>
        ) : (
          <span
            className="xsmall faint"
            title="Cost, tokens, and time are withheld during blind judging to avoid bias. They appear here after reveal, and anytime in Browse and Report."
            data-testid={`metrics-hidden-${side.label}`}
          >
            cost/time hidden (blind)
          </span>
        )}
      </div>
      {gd && (
        <div className="row wrap" style={{ gap: "var(--space-2)", marginTop: "auto", paddingTop: "var(--space-1)" }}>
          {(["compile", "visible", "hidden"] as const).map((tier) =>
            gd[tier].output ? (
              // Layout lives in CSS only: an inline flex style here would beat
              // the stylesheet's [open] full-width rule (the pass-10 bug).
              <details key={tier} className="logbox">
                <summary data-testid={`log-${side.label}-${tier}`}>
                  <span>{tier === "compile" ? "build" : tier} output{gd[tier].truncated ? " (truncated)" : ""}</span>
                  <span className="logmeta">{gd[tier].output!.length.toLocaleString()} chars</span>
                </summary>
                <pre>{gd[tier].output}</pre>
              </details>
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}

export function GradeSession() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { db } = useDb();
  const { catalog } = useCatalog();
  const navigate = useNavigate();

  const { data: fetched, error, loading } = useFetch<Session>(
    () => api.session(db, sessionId!),
    [db, sessionId],
  );
  // A failed refetch (e.g. the DB switched under an open session) keeps the
  // PREVIOUS session in `data` while the error view renders — the judge
  // path must treat that stale state as no-session, or a keypress behind
  // the error screen fires a write with mismatched db/session.
  const session = error ? null : fetched;

  const [index, setIndex] = useState<number | null>(null);
  const [choices, setChoices] = useState<Map<number, string>>(new Map());
  const [view, setView] = useState<"two" | "three">("two");
  const [sync, setSync] = useState(true);
  const [expandGaps, setExpandGaps] = useState(false);
  const [originals, setOriginals] = useState<Map<number, OriginalsResponse>>(new Map());
  const [judging, setJudging] = useState(false);
  const [judgeError, setJudgeError] = useState<string | null>(null);

  // Initialize position + judged map once the session arrives.
  useEffect(() => {
    if (!session) return;
    const judged = new Map(session.judged.map((j) => [j.pair_index, j.choice]));
    setChoices(judged);
    const firstUnjudged = session.pairs.findIndex((p) => !judged.has(p.pair_index));
    setIndex(firstUnjudged === -1 ? 0 : firstUnjudged);
  }, [session]);

  // Lazily fetch originals when the three-way view is opened for a pair.
  useEffect(() => {
    if (view !== "three" || index === null || !session) return;
    if (originals.has(index)) return;
    let cancelled = false;
    api
      .pairOriginals(db, session.session_id, index)
      .then((o) => {
        if (!cancelled) setOriginals((prev) => new Map(prev).set(index, o));
      })
      .catch(() => {
        if (!cancelled) {
          setOriginals((prev) =>
            new Map(prev).set(index, { pair_index: index, files: [], note: "Failed to load originals." }),
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [view, index, session, db, originals]);

  const pair = session && index !== null ? session.pairs[index] : null;
  const total = session?.total_pairs ?? 0;
  const nJudged = choices.size;
  const allJudged = total > 0 && nJudged >= total;

  // Union of files touched by either side (paths as rendered, i.e. redacted).
  const fileList = pair
    ? Array.from(new Set([...pair.left.proxy.file_list, ...pair.right.proxy.file_list])).sort()
    : [];

  const twoWayRef = useRef<TwoWayDiffHandle | null>(null);

  const jumpToFile = useCallback((path: string) => {
    // Two-way panes jump through the component's handle so pixel-sync
    // mirroring can't clobber each pane's own target offset.
    twoWayRef.current?.jumpToFile(path);
    const pane = document.querySelector<HTMLElement>('[data-testid="threeway-pane"]');
    const target = pane?.querySelector<HTMLElement>(`[data-file="${CSS.escape(path)}"]`);
    if (pane && target) {
      pane.scrollTop += target.getBoundingClientRect().top - pane.getBoundingClientRect().top;
    }
  }, []);

  const goto = useCallback(
    (next: number) => {
      if (!session) return;
      setIndex(Math.max(0, Math.min(session.pairs.length - 1, next)));
    },
    [session],
  );

  const closed = session?.revealed_at != null;

  const judge = useCallback(
    async (choice: "A" | "B" | "tie") => {
      if (!session || index === null || judging || closed) return;
      setJudging(true);
      setJudgeError(null);
      try {
        await api.judge(db, session.session_id, index, choice);
        const nextChoices = new Map(choices).set(index, choice);
        setChoices(nextChoices);
        // Advance to the next unjudged pair (wrapping); if none left, reveal.
        const n = session.pairs.length;
        let next = -1;
        for (let step = 1; step <= n; step++) {
          const cand = (index + step) % n;
          if (!nextChoices.has(cand)) {
            next = cand;
            break;
          }
        }
        if (next === -1) {
          navigate(`/grade/session/${session.session_id}/reveal${db ? `?db=${db}` : ""}`);
        } else {
          setIndex(next);
        }
      } catch (e) {
        setJudgeError(String((e as Error).message ?? e));
      } finally {
        setJudging(false);
      }
    },
    [session, index, judging, closed, choices, db, navigate],
  );

  // Keyboard-first flow.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key.toLowerCase()) {
        case "a":
          void judge("A");
          break;
        case "b":
          void judge("B");
          break;
        case "t":
          void judge("tie");
          break;
        case "arrowleft":
          if (index !== null) goto(index - 1);
          break;
        case "arrowright":
          if (index !== null) goto(index + 1);
          break;
        case "v":
          setView((v) => (v === "two" ? "three" : "two"));
          break;
        case "x":
          setExpandGaps((e) => !e);
          break;
        default:
          return;
      }
      e.preventDefault();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [judge, goto, index]);

  if (loading) return <main className="app-main"><div className="empty-state">Loading session…</div></main>;
  if (error) {
    return (
      <main className="app-main">
        <div className="page">
          <div className="error-banner">{error}</div>
          <p className="small muted">
            If this session exists, it may live in a different database — check the database selector in
            the top bar.
          </p>
          <Link className="btn" to={`/grade${db ? `?db=${db}` : ""}`}>← Back to the grading picker</Link>
        </div>
      </main>
    );
  }
  if (!session || !pair || index === null) return <main className="app-main"><div className="empty-state">Session is empty.</div></main>;

  // An llm-mode session is judged by the model, never here — its home is the
  // judge progress page (human verdicts must not mix into it).
  if (session.mode === "llm") {
    return (
      <main className="app-main">
        <div className="page" style={{ maxWidth: "44rem" }}>
          <div className="info-banner" data-testid="llm-session-redirect">
            This session is judged by the LLM judge ({session.judge_model ?? session.judge_provider}) —
            manual grading is disabled for it.{" "}
            <Link to={`/grade/judge/${session.session_id}${db ? `?db=${db}` : ""}`}>
              Open the judge progress page
            </Link>
            , or start a fresh manual session on the same cell from the{" "}
            <Link to={`/grade${db ? `?db=${db}` : ""}`}>picker</Link>.
          </div>
        </div>
      </main>
    );
  }

  const currentChoice = choices.get(index);

  return (
    <main className="app-main full-bleed">
      {/* header */}
      <div
        className="row wrap"
        style={{
          padding: "var(--space-2) var(--space-4)",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          flex: "none",
        }}
      >
        <Link to={`/grade${db ? `?db=${db}` : ""}`} className="btn ghost sm">← Picker</Link>
        <span className="badge accent" data-testid="session-axis">comparing: {AXIS_LABELS[session.axis] ?? session.axis}</span>
        <span className="row" style={{ gap: "var(--space-1)" }}>
          {Object.entries(session.cell).map(([k, v]) => (
            <IdChip key={k} catalog={catalog} kind={CELL_KIND[k] ?? "task"} id={v} />
          ))}
        </span>
        <span className="nav-spacer" style={{ flex: 1 }} />
        {pair.left.diff === pair.right.diff && (
          <span className="badge neutral" title="Both sides contain exactly the same changes — a tie by construction." data-testid="identical-note">
            sides are identical
          </span>
        )}
        <span className="small muted" data-testid="pair-progress">
          pair {index + 1} / {total} · {nJudged} judged
        </span>
        <span className="row" style={{ gap: "var(--space-2)" }}>
          <span className="segmented" role="group" aria-label="Diff view mode">
            <button
              className={view === "two" ? "active" : ""}
              onClick={() => setView("two")}
              aria-pressed={view === "two"}
              data-testid="view-two"
            >
              A | B
            </button>
            <button
              className={view === "three" ? "active" : ""}
              onClick={() => setView("three")}
              aria-pressed={view === "three"}
              data-testid="view-three"
            >
              Original | A | B
            </button>
          </span>
          {view === "two" && (
            <label className="row xsmall muted" style={{ gap: "var(--space-1)" }}>
              <input type="checkbox" checked={sync} onChange={(e) => setSync(e.target.checked)} />
              sync scroll
            </label>
          )}
        </span>
      </div>

      {/* side headers */}
      <div className="grid-2" style={{ padding: "var(--space-2) var(--space-4)", gap: "var(--space-3)", flex: "none" }}>
        <SideHeader side={pair.left} />
        <SideHeader side={pair.right} />
      </div>

      {/* file navigator — jump to a file in both panes at once */}
      {fileList.length > 1 && (
        <div
          className="row wrap"
          style={{ padding: "0 var(--space-4) var(--space-2)", gap: "var(--space-1)", flex: "none" }}
          data-testid="file-nav"
        >
          <span className="xsmall muted" style={{ marginRight: "var(--space-1)" }}>Files:</span>
          {fileList.map((f) => (
            <button key={f} className="btn sm ghost mono" onClick={() => jumpToFile(f)} title={f} data-testid="file-nav-item">
              {f.split("/").pop()}
            </button>
          ))}
        </div>
      )}

      {/* diff area */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", padding: "0 var(--space-4)" }}>
        {view === "two" ? (
          <TwoWayDiff aDiff={pair.left.diff} bDiff={pair.right.diff} sync={sync} apiRef={twoWayRef} />
        ) : (
          <ThreeWayDiff
            aDiff={pair.left.diff}
            bDiff={pair.right.diff}
            originals={originals.get(index) ?? null}
            expandAll={expandGaps}
          />
        )}
      </div>

      {/* judge bar */}
      {closed ? (
        <div
          className="row"
          style={{
            padding: "var(--space-2) var(--space-4)",
            borderTop: "1px solid var(--color-border)",
            background: "var(--color-surface)",
            flex: "none",
            justifyContent: "center",
            gap: "var(--space-3)",
          }}
          data-testid="session-closed-bar"
        >
          <span className="badge neutral">session closed</span>
          <span className="small muted">
            The gavel has struck — this session was revealed, so judging is disabled.
          </span>
          <Link className="btn primary sm" to={`/grade/session/${session.session_id}/reveal${db ? `?db=${db}` : ""}`}>
            View results
          </Link>
          <Link className="btn sm" to={`/grade${db ? `?db=${db}` : ""}`}>
            Grade this cell again (new session)
          </Link>
        </div>
      ) : (
      <div
        className="row"
        style={{
          padding: "var(--space-2) var(--space-4)",
          borderTop: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          flex: "none",
          justifyContent: "center",
          gap: "var(--space-3)",
        }}
        data-testid="judge-bar"
      >
        <button className="btn sm ghost" onClick={() => goto(index - 1)} disabled={index === 0} data-testid="prev-pair">
          ← prev
        </button>
        <button
          className={`btn ${currentChoice === "A" ? "primary" : ""}`}
          onClick={() => void judge("A")}
          disabled={judging}
          aria-pressed={currentChoice === "A"}
          data-testid="judge-a"
        >
          <kbd className="key">A</kbd> A wins
        </button>
        <button
          className={`btn ${currentChoice === "tie" ? "primary" : ""}`}
          onClick={() => void judge("tie")}
          disabled={judging}
          aria-pressed={currentChoice === "tie"}
          data-testid="judge-tie"
        >
          <kbd className="key">T</kbd> Tie
        </button>
        <button
          className={`btn ${currentChoice === "B" ? "primary" : ""}`}
          onClick={() => void judge("B")}
          disabled={judging}
          aria-pressed={currentChoice === "B"}
          data-testid="judge-b"
        >
          <kbd className="key">B</kbd> B wins
        </button>
        <button className="btn sm ghost" onClick={() => goto(index + 1)} disabled={index >= total - 1} data-testid="next-pair">
          next →
        </button>
        {allJudged && (
          <Link className="btn primary" to={`/grade/session/${session.session_id}/reveal${db ? `?db=${db}` : ""}`} data-testid="to-reveal">
            Reveal results →
          </Link>
        )}
        {judgeError && <span className="error-banner">{judgeError}</span>}
        <span className="xsmall faint">
          keys: <kbd className="key">A</kbd>/<kbd className="key">B</kbd>/<kbd className="key">T</kbd> judge ·{" "}
          <kbd className="key">←</kbd><kbd className="key">→</kbd> navigate · <kbd className="key">V</kbd> view
          {view === "three" && (
            <>
              {" "}· <kbd className="key">X</kbd> expand
            </>
          )}
        </span>
      </div>
      )}
    </main>
  );
}
