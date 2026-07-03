"""FastAPI backend for the Tiltyard web UI (dashboard, grading, runs, reports).

DB access is per-request: every endpoint takes an optional ``db`` query param
(a plain ``*.db`` filename resolved against the project root); empty means the
default set via set_db_path (the ``--db`` CLI flag). Grading sessions are
persisted in their DB, so any session survives a server restart.

Blinding invariant (see CLAUDE.md): once a grading session serves an A/B pair,
nothing in the payload may reveal the value of the comparison axis. Diffs, gate
logs, and reconstructed originals all pass through
grading.pairwise.redact_axis_ids; cost/tokens/wall-time are withheld entirely
when the comparison axis is model or runner (they fingerprint the value).
"""

import asyncio
import json
import logging
import math
import re
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.db import (
    connect,
    grading_readiness,
    get_grading_session,
    insert_grading_session,
    mark_session_revealed,
    list_judgments,
    upsert_judgment,
    list_passing_trials,
    list_cell_trials,
    list_grading_cells,
    list_grading_sessions,
    get_cost_record,
    get_gate_result,
    get_run_result,
    get_trial,
)
from core.matrix import HARNESS_MAP
from core.methodology_loader import load_methodology
from core.models import GradingSession, Judgment, Trial
from core.repo_context_loader import load_repo_context

from grading.pairwise import (
    AXIS_FIELDS,
    DiffProxy,
    anonymize_diff,
    compute_proxy,
    generate_pairs,
    redact_axis_ids,
)
from grading.bradley_terry import fit_bradley_terry, bootstrap_ci, bt_scores_to_elo
from grading.analyzer import analyze, AnalyzerFlags

from ui import runs as run_manager
from ui.catalog import build_catalog
from ui.originals import diff_file_entries, get_resolver

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
REPORTS_DIR = ROOT / "reports"

# Cap on a single gate-tier log served to the browser (chars, after redaction).
TIER_OUTPUT_CAP = 100_000

# Axes whose value a cost/token/wall-time readout would fingerprint during
# blind comparison. For methodology/repo_context, cost is a legitimate part of
# the judgment ("same quality, 4x the tokens"); for model/runner it IS the id.
METRICS_HIDDEN_AXES = {"model", "runner"}

# ---------------------------------------------------------------------------
# DB path management
# ---------------------------------------------------------------------------

_db_path: Path = Path("results.db")

_DB_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.db$")


def set_db_path(path: Path) -> None:
    global _db_path
    _db_path = path


def _resolve_db_path(db: str, must_exist: bool = True) -> Path:
    """Resolve the ``db`` query param to a real path. Empty -> the default.
    Otherwise a bare filename under the project root (no traversal)."""
    if not db:
        return _db_path
    if not _DB_NAME_RE.match(db):
        raise HTTPException(400, f"Invalid db name {db!r}: expected a bare *.db filename")
    path = ROOT / db
    if must_exist and not path.exists():
        raise HTTPException(404, f"No database named {db!r} in the project root")
    return path


def _open(db: str = "") -> sqlite3.Connection:
    return connect(_resolve_db_path(db))


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

class SessionState:
    def __init__(self, session_id: str, axis: str, cell: dict[str, str],
                 pairs: list[tuple[str, str]], judgments_made: set[int] | None = None,
                 revealed_at: str | None = None):
        self.session_id = session_id
        self.axis = axis
        self.cell = cell
        self.pairs = pairs
        self.judgments_made: set[int] = judgments_made or set()
        self.revealed_at = revealed_at


_sessions: dict[str, SessionState] = {}


def _get_session(conn: sqlite3.Connection, session_id: str) -> SessionState | None:
    """In-memory cache first, then the grading_session table — a session must
    survive a server restart (its judgments are already persisted)."""
    session = _sessions.get(session_id)
    if session is not None:
        return session

    stored = get_grading_session(conn, session_id)
    if stored is None:
        return None

    index_by_pair = {pair: i for i, pair in enumerate(stored.pairs)}
    made = {
        index_by_pair[(j.left_trial_id, j.right_trial_id)]
        for j in list_judgments(conn, session_id)
        if (j.left_trial_id, j.right_trial_id) in index_by_pair
    }
    session = SessionState(
        session_id=stored.id,
        axis=stored.axis,
        cell=stored.cell,
        pairs=list(stored.pairs),
        judgments_made=made,
        revealed_at=stored.revealed_at,
    )
    _sessions[session_id] = session
    return session


@lru_cache(maxsize=256)
def _spec_is_inert(kind: str, spec_id: str, harness: str) -> bool:
    """True when the spec lays down zero files for this harness. Inertness is
    a static property of (spec, harness), so cache it — /api/pairs shouldn't
    re-parse YAML on every session. A spec that fails to load is NOT inert:
    when in doubt, keep redacting."""
    loader = load_methodology if kind == "methodology" else load_repo_context
    try:
        return not loader(spec_id, harness).files
    except Exception as e:
        logger.warning("Could not load %s %r (harness %s) for inertness check: %s",
                       kind, spec_id, harness, e)
        return False


def _inert_axis_ids(trials) -> set[str]:
    """Axis ids whose spec lays down zero files (e.g. the ``none`` context,
    the ``baseline`` methodology). They have no causal path into diff content,
    so redacting them only mangles incidental code (``none`` would clobber
    Python's ``None``)."""
    harnesses = {HARNESS_MAP.get(t.runner, "claude-code") for t in trials}
    inert: set[str] = set()
    for mid in {t.methodology_id for t in trials}:
        if all(_spec_is_inert("methodology", mid, h) for h in harnesses):
            inert.add(mid)
    for cid in {t.repo_context_id for t in trials}:
        if all(_spec_is_inert("repo_context", cid, h) for h in harnesses):
            inert.add(cid)
    return inert


def _axis_ids_for_blinding(trials) -> dict[str, list[str]]:
    """The redaction map for one session: every axis id across its trials,
    minus causally-inert ones."""
    skip_ids = _inert_axis_ids(trials)
    return {
        k: sorted({getattr(t, AXIS_FIELDS[k]) for t in trials} - skip_ids)
        for k in AXIS_FIELDS
    }


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="tiltyard (setup-bench ui)")
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR), check_dir=False), name="reports")
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AxisInfo(BaseModel):
    axis: str
    n_cells: int


class AxisReadiness(BaseModel):
    distinct_passing_values: int
    gradeable_cells: int


class GradingStatusResponse(BaseModel):
    total_hidden_gate_passers: int
    axes: dict[str, AxisReadiness]


class GateScorecard(BaseModel):
    compile_passed: bool | None
    visible_passed: bool | None
    hidden_passed: bool | None


class TierDetail(BaseModel):
    passed: bool | None
    output: str | None            # redacted; None when the tier didn't run
    truncated: bool = False


class GateDetail(BaseModel):
    passed: bool
    compile: TierDetail
    visible: TierDetail
    hidden: TierDetail


class SideMetrics(BaseModel):
    usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    wall_seconds: float | None = None


class BlindDiffResponse(BaseModel):
    label: str
    diff: str
    proxy: DiffProxy
    gate: GateScorecard
    gate_detail: GateDetail | None = None
    metrics: SideMetrics | None = None


class PairResponse(BaseModel):
    pair_index: int
    total_pairs: int
    left: BlindDiffResponse
    right: BlindDiffResponse
    metrics_hidden: bool = False
    metrics_hidden_reason: str | None = None


class JudgedPair(BaseModel):
    pair_index: int
    choice: str


class SessionResponse(BaseModel):
    session_id: str
    axis: str
    cell: dict[str, str]
    total_pairs: int
    pairs: list[PairResponse]
    judged: list[JudgedPair] = []
    created_at: str | None = None
    revealed_at: str | None = None


class SessionSummary(BaseModel):
    session_id: str
    axis: str
    cell: dict[str, str]
    total_pairs: int
    n_judged: int
    created_at: str
    revealed_at: str | None = None


class JudgeRequest(BaseModel):
    session_id: str
    pair_index: int
    choice: str
    db: str = ""
    rubric_correctness: str | None = None
    rubric_minimality: str | None = None
    rubric_readability: str | None = None
    rubric_overengineering: str | None = None


class JudgeResponse(BaseModel):
    ok: bool
    remaining: int


class RevealPair(BaseModel):
    pair_index: int
    left_value: str
    right_value: str
    choice: str | None


class AxisValueRecord(BaseModel):
    wins: int
    losses: int
    ties: int


class BTScore(BaseModel):
    axis_value: str
    elo: float
    ci_lower: float
    ci_upper: float


class AnalyzerFlagsModel(BaseModel):
    non_discriminating_tasks: list[str]
    flaky_tasks: list[str]
    cost_quality_notes: list[str]


class RevealResponse(BaseModel):
    pairs: list[RevealPair]           # judged pairs ONLY — unjudged stay blind
    summary: dict[str, AxisValueRecord]
    axis: str
    cell: dict[str, str]
    n_unjudged: int = 0
    revealed_at: str | None = None
    bt_scores: list[BTScore] | None = None
    analyzer_flags: AnalyzerFlagsModel | None = None
    pass_rates: dict[str, float] | None = None


class AxisValueStats(BaseModel):
    axis_value: str
    pass_rate: float | None      # passers / trials with a gate verdict (None if no verdicts)
    mean_cost_usd: float | None
    mean_wall_seconds: float | None
    n_trials: int


class StatsResponse(BaseModel):
    axis: str
    cell: dict[str, str]
    stats: list[AxisValueStats]


class OriginalFile(BaseModel):
    path: str                     # redacted path, matching the served diffs
    status: str                   # ok | new | unavailable | differs
    content: str | None = None    # redacted original; None for new/unavailable
    left_content: str | None = None   # only when status == differs
    right_content: str | None = None


class OriginalsResponse(BaseModel):
    pair_index: int
    files: list[OriginalFile]
    note: str | None = None


class DbInfo(BaseModel):
    name: str
    is_default: bool
    n_trials: int
    n_passers: int
    n_judgments: int
    n_sessions: int
    modified_at: float


# ---------------------------------------------------------------------------
# Query-param name → list_passing_trials kwarg name
# ---------------------------------------------------------------------------

_PARAM_TO_KWARG = {
    "methodology": "methodology_id",
    "repo_context": "repo_context_id",
    "model": "model",
    "runner": "runner",
}

# ---------------------------------------------------------------------------
# Grading endpoints
# ---------------------------------------------------------------------------


@app.get("/api/axes")
async def get_axes(db: str = "") -> list[AxisInfo]:
    conn = _open(db)
    try:
        result: list[AxisInfo] = []
        for axis in AXIS_FIELDS:
            cells = list_grading_cells(conn, axis)
            if cells:
                result.append(AxisInfo(axis=axis, n_cells=len(cells)))
        return result
    finally:
        conn.close()


@app.get("/api/grading-status")
async def get_grading_status(db: str = "") -> GradingStatusResponse:
    conn = _open(db)
    try:
        return GradingStatusResponse(**grading_readiness(conn))
    finally:
        conn.close()


@app.get("/api/cells")
async def get_cells(axis: str, db: str = "") -> list[dict]:
    if axis not in AXIS_FIELDS:
        raise HTTPException(400, f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")
    conn = _open(db)
    try:
        return list_grading_cells(conn, axis)
    finally:
        conn.close()


@app.get("/api/dbs")
async def get_dbs() -> list[DbInfo]:
    """Every *.db in the project root (plus the configured default), with
    enough stats to pick one from the dashboard."""
    paths: dict[str, Path] = {p.name: p for p in sorted(ROOT.glob("*.db"))}
    default = _db_path
    if default.exists():
        # The configured default always wins its name slot — it's what an
        # empty ?db= actually reads.
        paths[default.name] = default

    infos: list[DbInfo] = []
    for name, path in paths.items():
        try:
            conn = connect(path)
        except Exception:
            continue
        try:
            n_trials = conn.execute("SELECT COUNT(*) FROM trial").fetchone()[0]
            n_passers = conn.execute("SELECT COUNT(*) FROM gate_result WHERE passed = 1").fetchone()[0]
            n_judgments = conn.execute("SELECT COUNT(*) FROM judgment").fetchone()[0]
            n_sessions = conn.execute("SELECT COUNT(*) FROM grading_session").fetchone()[0]
        finally:
            conn.close()
        infos.append(DbInfo(
            name=name,
            is_default=(path.resolve() == default.resolve()),
            n_trials=n_trials,
            n_passers=n_passers,
            n_judgments=n_judgments,
            n_sessions=n_sessions,
            modified_at=path.stat().st_mtime,
        ))
    return infos


@app.get("/api/catalog")
async def get_catalog(db: str = "") -> dict:
    conn = _open(db)
    try:
        return build_catalog(conn)
    finally:
        conn.close()


def _coarse(v: float | int | None) -> float | int | None:
    """Round to ~2 significant figures. Metrics shown during comparison must
    stay useful for judgment ("4x the tokens for the same quality") but not
    be joinable 1:1 against the unblinded Browse table — a unique exact cost
    identifies the trial and would deblind the pair."""
    if v is None or v == 0:
        return v
    exp = math.floor(math.log10(abs(v)))
    factor = 10.0 ** (exp - 1)
    out = round(v / factor) * factor
    if isinstance(v, int):
        return int(out)
    return round(out, max(0, -(exp - 1)))


def _tier_detail(passed: bool | None, output: str | None,
                 axis_ids: dict[str, list[str]]) -> TierDetail:
    if output is None:
        return TierDetail(passed=passed, output=None)
    redacted = redact_axis_ids(output, axis_ids)
    truncated = len(redacted) > TIER_OUTPUT_CAP
    if truncated:
        redacted = redacted[:TIER_OUTPUT_CAP] + f"\n… [truncated {len(redacted) - TIER_OUTPUT_CAP} chars]"
    return TierDetail(passed=passed, output=redacted, truncated=truncated)


def _build_pair_responses(
    conn: sqlite3.Connection,
    axis: str,
    trial_pairs: list[tuple[Trial, Trial]],
    run_results: dict,
    axis_ids: dict[str, list[str]],
) -> list[PairResponse]:
    metrics_hidden = axis in METRICS_HIDDEN_AXES
    hidden_reason = (
        f"cost/tokens/time are withheld while comparing the {axis} axis — they would fingerprint the value"
        if metrics_hidden else None
    )
    _default_gate = GateScorecard(compile_passed=None, visible_passed=None, hidden_passed=None)

    responses: list[PairResponse] = []
    for i, (left, right) in enumerate(trial_pairs):
        sides: list[BlindDiffResponse] = []
        for label, trial in (("A", left), ("B", right)):
            rr = run_results[trial.id]
            gr = get_gate_result(conn, trial.id)
            cr = get_cost_record(conn, trial.id)

            gate = GateScorecard(
                compile_passed=gr.compile_passed,
                visible_passed=gr.visible_passed,
                hidden_passed=gr.hidden_passed,
            ) if gr else _default_gate

            gate_detail = GateDetail(
                passed=gr.passed,
                compile=_tier_detail(gr.compile_passed, gr.compile_output, axis_ids),
                visible=_tier_detail(gr.visible_passed, gr.visible_output, axis_ids),
                hidden=_tier_detail(gr.hidden_passed, gr.hidden_output, axis_ids),
            ) if gr else None

            metrics = None
            if not metrics_hidden:
                metrics = SideMetrics(
                    usd=_coarse(cr.usd_equiv) if cr else None,
                    input_tokens=_coarse(cr.input_tokens) if cr else None,
                    output_tokens=_coarse(cr.output_tokens) if cr else None,
                    cache_read_tokens=_coarse(cr.cache_read_tokens) if cr else None,
                    wall_seconds=_coarse(rr.wall_seconds),
                )

            sides.append(BlindDiffResponse(
                label=label,
                diff=anonymize_diff(rr.diff, axis_ids),
                proxy=compute_proxy(rr.diff),
                gate=gate,
                gate_detail=gate_detail,
                metrics=metrics,
            ))

        responses.append(PairResponse(
            pair_index=i,
            total_pairs=len(trial_pairs),
            left=sides[0],
            right=sides[1],
            metrics_hidden=metrics_hidden,
            metrics_hidden_reason=hidden_reason,
        ))
    return responses


@app.get("/api/pairs")
async def get_pairs(
    axis: str,
    task: str,
    methodology: str = "",
    repo_context: str = "",
    model: str = "",
    runner: str = "",
    db: str = "",
) -> SessionResponse:
    if axis not in AXIS_FIELDS:
        raise HTTPException(400, f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")

    comparison_col = AXIS_FIELDS[axis]
    param_values = {
        "methodology": methodology,
        "repo_context": repo_context,
        "model": model,
        "runner": runner,
    }
    pinned: dict[str, str] = {}
    for param_name, val in param_values.items():
        kwarg_name = _PARAM_TO_KWARG[param_name]
        if kwarg_name != comparison_col and val:
            pinned[kwarg_name] = val

    conn = _open(db)
    try:
        trials = list_passing_trials(conn, task_id=task, **pinned)

        run_results: dict[str, object] = {}
        for t in trials:
            rr = get_run_result(conn, t.id)
            if rr is not None:
                run_results[t.id] = rr

        # A passing trial with no run_result has no diff to show — drop it
        # rather than 500 on a KeyError below.
        missing = [t.id for t in trials if t.id not in run_results]
        if missing:
            logger.warning("Excluding %d gate-passing trial(s) with no run_result: %s", len(missing), missing)
            trials = [t for t in trials if t.id in run_results]

        distinct_values = {getattr(t, comparison_col) for t in trials}
        if len(distinct_values) < 2:
            raise HTTPException(400, "Not enough passing values for this axis in the selected cell")

        trial_pairs = generate_pairs(trials, run_results, axis)

        session_id = uuid.uuid4().hex
        id_pairs = [(left.id, right.id) for left, right in trial_pairs]

        cell: dict[str, str] = {"task_id": task, **pinned}

        session = SessionState(
            session_id=session_id,
            axis=axis,
            cell=cell,
            pairs=id_pairs,
        )
        _sessions[session_id] = session
        created_at = datetime.now(timezone.utc).isoformat()
        insert_grading_session(conn, GradingSession(
            id=session_id,
            axis=axis,
            cell=cell,
            pairs=id_pairs,
            created_at=created_at,
        ))

        axis_ids = _axis_ids_for_blinding(trials)
        pair_responses = _build_pair_responses(conn, axis, trial_pairs, run_results, axis_ids)

        return SessionResponse(
            session_id=session_id,
            axis=axis,
            cell=cell,
            total_pairs=len(trial_pairs),
            pairs=pair_responses,
            judged=[],
            created_at=created_at,
        )
    finally:
        conn.close()


@app.get("/api/sessions")
async def get_sessions(db: str = "") -> list[SessionSummary]:
    """Past grading sessions with progress, newest first — the dashboard's
    'resume where you left off' list."""
    conn = _open(db)
    try:
        out: list[SessionSummary] = []
        for s in reversed(list_grading_sessions(conn)):
            judged = {
                (j.left_trial_id, j.right_trial_id)
                for j in list_judgments(conn, s.id)
            }
            n_judged = sum(1 for p in s.pairs if p in judged)
            out.append(SessionSummary(
                session_id=s.id,
                axis=s.axis,
                cell=s.cell,
                total_pairs=len(s.pairs),
                n_judged=n_judged,
                created_at=s.created_at,
                revealed_at=s.revealed_at,
            ))
        return out
    finally:
        conn.close()


@app.get("/api/session/{session_id}")
async def get_session(session_id: str, db: str = "") -> SessionResponse:
    """Rebuild a persisted session with full pair payloads — page reloads and
    resumed sessions must not lose state."""
    conn = _open(db)
    try:
        stored = get_grading_session(conn, session_id)
        if stored is None:
            raise HTTPException(404, "Session not found")

        trial_pairs: list[tuple[Trial, Trial]] = []
        run_results: dict[str, object] = {}
        for left_id, right_id in stored.pairs:
            left, right = get_trial(conn, left_id), get_trial(conn, right_id)
            if left is None or right is None:
                raise HTTPException(500, f"Session references missing trial(s): {left_id}, {right_id}")
            trial_pairs.append((left, right))
            for t in (left, right):
                if t.id not in run_results:
                    rr = get_run_result(conn, t.id)
                    if rr is None:
                        raise HTTPException(500, f"Session trial {t.id} has no run_result")
                    run_results[t.id] = rr

        # Redact with the same id set the original session used: every passing
        # trial in the cell (a superset of the sampled pairs), unioned with the
        # pair trials themselves for safety.
        kwargs = {k: v for k, v in stored.cell.items() if k != "task_id"}
        cell_trials = list_passing_trials(conn, task_id=stored.cell.get("task_id", ""), **kwargs)
        by_id = {t.id: t for t in cell_trials}
        for pair in trial_pairs:
            for t in pair:
                by_id.setdefault(t.id, t)
        axis_ids = _axis_ids_for_blinding(list(by_id.values()))

        pair_responses = _build_pair_responses(conn, stored.axis, trial_pairs, run_results, axis_ids)

        index_by_pair = {pair: i for i, pair in enumerate(stored.pairs)}
        judged = [
            JudgedPair(pair_index=index_by_pair[(j.left_trial_id, j.right_trial_id)], choice=j.choice)
            for j in list_judgments(conn, session_id)
            if (j.left_trial_id, j.right_trial_id) in index_by_pair
        ]
        judged.sort(key=lambda j: j.pair_index)

        return SessionResponse(
            session_id=stored.id,
            axis=stored.axis,
            cell=stored.cell,
            total_pairs=len(stored.pairs),
            pairs=pair_responses,
            judged=judged,
            created_at=stored.created_at,
            revealed_at=stored.revealed_at,
        )
    finally:
        conn.close()


@app.get("/api/pair-originals")
async def get_pair_originals(session_id: str, pair_index: int, db: str = "") -> OriginalsResponse:
    """Pre-agent ("original") content for every file touched by either side of
    a pair — the third column of the three-way view. Paths and contents are
    redacted with the session's blinding map before serving."""
    conn = _open(db)
    try:
        session = _get_session(conn, session_id)
        if session is None:
            raise HTTPException(404, "Session not found")
        if pair_index < 0 or pair_index >= len(session.pairs):
            raise HTTPException(400, "pair_index out of range")

        left_id, right_id = session.pairs[pair_index]
        left, right = get_trial(conn, left_id), get_trial(conn, right_id)
        if left is None or right is None:
            raise HTTPException(500, "Pair references missing trial(s)")

        trials_for_blinding: dict[str, Trial] = {left.id: left, right.id: right}
        kwargs = {k: v for k, v in session.cell.items() if k != "task_id"}
        for t in list_passing_trials(conn, task_id=session.cell.get("task_id", ""), **kwargs):
            trials_for_blinding.setdefault(t.id, t)
        axis_ids = _axis_ids_for_blinding(list(trials_for_blinding.values()))

        from grading.pairwise import _is_instruction_file  # single source of truth

        files: dict[str, dict] = {}
        for side, trial in (("left", left), ("right", right)):
            rr = get_run_result(conn, trial.id)
            if rr is None:
                continue
            resolver = get_resolver(trial.task_id, trial.methodology_id,
                                    trial.repo_context_id, trial.runner)
            for old_path, new_path in diff_file_entries(rr.diff):
                display_path = new_path or old_path
                if display_path is None or _is_instruction_file(display_path):
                    continue
                entry = files.setdefault(display_path, {})
                if old_path is None:
                    entry[side] = ("new", None)
                elif not resolver.available:
                    entry[side] = ("unavailable", None)
                else:
                    content = resolver.content(old_path)
                    entry[side] = ("ok", content) if content is not None else ("new", None)

        out: list[OriginalFile] = []
        for path in sorted(files):
            entry = files[path]
            sides = list(entry.values())
            statuses = {s for s, _ in sides}
            contents = {c for _, c in sides}
            red_path = redact_axis_ids(path, axis_ids)
            if len(contents) > 1 and "ok" in statuses:
                lc = entry.get("left", (None, None))[1]
                rc = entry.get("right", (None, None))[1]
                out.append(OriginalFile(
                    path=red_path, status="differs",
                    left_content=redact_axis_ids(lc, axis_ids) if lc is not None else None,
                    right_content=redact_axis_ids(rc, axis_ids) if rc is not None else None,
                ))
            else:
                status, content = sides[0]
                out.append(OriginalFile(
                    path=red_path, status=status,
                    content=redact_axis_ids(content, axis_ids) if content is not None else None,
                ))

        # Only flag unavailability when it actually affects a shown file —
        # a pair of purely-created files has no original by definition and
        # needs no warning.
        note = None
        if any(f.status == "unavailable" for f in out):
            resolver = get_resolver(left.task_id, left.methodology_id, left.repo_context_id, left.runner)
            note = f"Some originals could not be reconstructed: {resolver.reason or 'unknown reason'}"

        return OriginalsResponse(pair_index=pair_index, files=out, note=note)
    finally:
        conn.close()


@app.post("/api/judge")
async def judge(req: JudgeRequest) -> JudgeResponse:
    conn = _open(req.db)
    try:
        session = _get_session(conn, req.session_id)
        if session is None:
            raise HTTPException(404, "Session not found")

        # Once a session has been revealed the grader knows every pair's
        # assignment — a judgment after that would not be blind. Refuse
        # permanently (blind-grading invariant).
        if session.revealed_at is not None:
            raise HTTPException(
                409, "Session was revealed and is closed — start a new session to grade this cell again"
            )

        if req.choice not in ("A", "B", "tie"):
            raise HTTPException(400, "Choice must be A, B, or tie")

        if req.pair_index < 0 or req.pair_index >= len(session.pairs):
            raise HTTPException(400, "pair_index out of range")

        left_trial_id, right_trial_id = session.pairs[req.pair_index]

        judgment = Judgment(
            id=uuid.uuid4().hex,
            session_id=session.session_id,
            task_id=session.cell.get("task_id", ""),
            model=session.cell.get("model", ""),
            left_trial_id=left_trial_id,
            right_trial_id=right_trial_id,
            choice=req.choice,
            rubric_correctness=req.rubric_correctness,
            rubric_minimality=req.rubric_minimality,
            rubric_readability=req.rubric_readability,
            rubric_overengineering=req.rubric_overengineering,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        upsert_judgment(conn, judgment)
        session.judgments_made.add(req.pair_index)

        remaining = len(session.pairs) - len(session.judgments_made)
        return JudgeResponse(ok=True, remaining=remaining)
    finally:
        conn.close()


@app.get("/api/reveal")
async def reveal(session_id: str, db: str = "") -> RevealResponse:
    conn = _open(db)
    try:
        session = _get_session(conn, session_id)
        if session is None:
            raise HTTPException(404, "Session not found")

        # Revealing closes the session for good (see /api/judge). The first
        # reveal's timestamp sticks; later loads of the reveal page are reads.
        if session.revealed_at is None:
            revealed_at = datetime.now(timezone.utc).isoformat()
            mark_session_revealed(conn, session_id, revealed_at)
            session.revealed_at = revealed_at

        field = AXIS_FIELDS[session.axis]

        judgments = list_judgments(conn, session_id)
        judgment_by_pair: dict[tuple[str, str], Judgment] = {}
        for j in judgments:
            judgment_by_pair[(j.left_trial_id, j.right_trial_id)] = j

        reveal_pairs: list[RevealPair] = []
        summary: dict[str, AxisValueRecord] = defaultdict(lambda: AxisValueRecord(wins=0, losses=0, ties=0))
        comparisons: list[tuple[str, str, str]] = []
        n_unjudged = 0

        for i, (left_id, right_id) in enumerate(session.pairs):
            j = judgment_by_pair.get((left_id, right_id))
            choice = j.choice if j else None

            # Unjudged pairs stay blind forever: the session is closed now,
            # but their assignments still say which trial (= which diff) maps
            # to which axis value — knowledge that could deblind a future
            # session over the same trials. Expose only what was judged.
            if choice is None:
                n_unjudged += 1
                continue

            left_trial = get_trial(conn, left_id)
            right_trial = get_trial(conn, right_id)
            left_value = getattr(left_trial, field)
            right_value = getattr(right_trial, field)

            reveal_pairs.append(RevealPair(
                pair_index=i,
                left_value=left_value,
                right_value=right_value,
                choice=choice,
            ))

            if choice == "A":
                comparisons.append((left_value, right_value, "win"))
            elif choice == "B":
                comparisons.append((left_value, right_value, "loss"))
            elif choice == "tie":
                comparisons.append((left_value, right_value, "tie"))

            if choice == "A":
                rec = summary[left_value]
                summary[left_value] = AxisValueRecord(wins=rec.wins + 1, losses=rec.losses, ties=rec.ties)
                rec = summary[right_value]
                summary[right_value] = AxisValueRecord(wins=rec.wins, losses=rec.losses + 1, ties=rec.ties)
            elif choice == "B":
                rec = summary[right_value]
                summary[right_value] = AxisValueRecord(wins=rec.wins + 1, losses=rec.losses, ties=rec.ties)
                rec = summary[left_value]
                summary[left_value] = AxisValueRecord(wins=rec.wins, losses=rec.losses + 1, ties=rec.ties)
            elif choice == "tie":
                rec = summary[left_value]
                summary[left_value] = AxisValueRecord(wins=rec.wins, losses=rec.losses, ties=rec.ties + 1)
                rec = summary[right_value]
                summary[right_value] = AxisValueRecord(wins=rec.wins, losses=rec.losses, ties=rec.ties + 1)

        # Bradley-Terry ranking — only when there's enough signal.
        bt_scores: list[BTScore] | None = None
        if len(comparisons) >= 3:
            strengths = fit_bradley_terry(comparisons)
            elos = bt_scores_to_elo(strengths)
            cis = bootstrap_ci(comparisons, seed=0)
            scale = 400.0 / math.log(10)
            rows: list[BTScore] = []
            for value, elo in elos.items():
                lo, _med, hi = cis.get(value, (strengths[value], strengths[value], strengths[value]))
                rows.append(BTScore(
                    axis_value=value,
                    elo=elo,
                    ci_lower=1000.0 + scale * lo,
                    ci_upper=1000.0 + scale * hi,
                ))
            bt_scores = sorted(rows, key=lambda r: r.elo, reverse=True)

        # Objective stats over the whole cell (passing + failing reps).
        pass_rates, flags = _cell_pass_rates_and_flags(conn, session.axis, session.cell)

        return RevealResponse(
            pairs=reveal_pairs,
            summary=dict(summary),
            axis=session.axis,
            cell=session.cell,
            n_unjudged=n_unjudged,
            revealed_at=session.revealed_at,
            bt_scores=bt_scores,
            analyzer_flags=flags,
            pass_rates=pass_rates,
        )
    finally:
        conn.close()


def _cell_trials(conn: sqlite3.Connection, cell: dict[str, str]):
    """Re-query every trial in a session's cell (passing and failing)."""
    kwargs = {k: v for k, v in cell.items() if k != "task_id"}
    return list_cell_trials(conn, task_id=cell["task_id"], **kwargs)


def _cell_pass_rates_and_flags(
    conn: sqlite3.Connection, axis: str, cell: dict[str, str]
) -> tuple[dict[str, float], AnalyzerFlagsModel]:
    field = AXIS_FIELDS[axis]
    trials = _cell_trials(conn, cell)
    gate_results = {}
    cost_records = {}
    passed: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for t in trials:
        gr = get_gate_result(conn, t.id)
        cr = get_cost_record(conn, t.id)
        if gr is not None:
            gate_results[t.id] = gr
            value = getattr(t, field)
            total[value] += 1
            if gr.passed:
                passed[value] += 1
        if cr is not None:
            cost_records[t.id] = cr

    pass_rates = {v: passed[v] / total[v] for v in total}
    flags = analyze(trials, gate_results, cost_records, axis=axis)
    return pass_rates, AnalyzerFlagsModel(
        non_discriminating_tasks=flags.non_discriminating_tasks,
        flaky_tasks=flags.flaky_tasks,
        cost_quality_notes=flags.cost_quality_notes,
    )


@app.get("/api/stats")
async def get_stats(
    axis: str,
    task: str,
    methodology: str = "",
    repo_context: str = "",
    model: str = "",
    runner: str = "",
    db: str = "",
) -> StatsResponse:
    if axis not in AXIS_FIELDS:
        raise HTTPException(400, f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")

    comparison_col = AXIS_FIELDS[axis]
    param_values = {
        "methodology": methodology,
        "repo_context": repo_context,
        "model": model,
        "runner": runner,
    }
    pinned: dict[str, str] = {}
    for param_name, val in param_values.items():
        kwarg_name = _PARAM_TO_KWARG[param_name]
        if kwarg_name != comparison_col and val:
            pinned[kwarg_name] = val

    conn = _open(db)
    try:
        trials = list_cell_trials(conn, task_id=task, **pinned)

        passed: dict[str, int] = defaultdict(int)
        total: dict[str, int] = defaultdict(int)
        gated: dict[str, int] = defaultdict(int)
        cost_sum: dict[str, float] = defaultdict(float)
        cost_n: dict[str, int] = defaultdict(int)
        wall_sum: dict[str, float] = defaultdict(float)
        wall_n: dict[str, int] = defaultdict(int)
        for t in trials:
            value = getattr(t, comparison_col)
            total[value] += 1
            gr = get_gate_result(conn, t.id)
            # Pass rate is passers over trials WITH a gate verdict — the same
            # denominator /api/reveal and the analyzer use, so the two endpoints
            # can't disagree about the same cell.
            if gr is not None:
                gated[value] += 1
                if gr.passed:
                    passed[value] += 1
            cr = get_cost_record(conn, t.id)
            if cr is not None:
                cost_sum[value] += cr.usd_equiv
                cost_n[value] += 1
            rr = get_run_result(conn, t.id)
            if rr is not None:
                wall_sum[value] += rr.wall_seconds
                wall_n[value] += 1

        stats = [
            AxisValueStats(
                axis_value=value,
                pass_rate=(passed[value] / gated[value]) if gated[value] else None,
                mean_cost_usd=(cost_sum[value] / cost_n[value]) if cost_n[value] else None,
                mean_wall_seconds=(wall_sum[value] / wall_n[value]) if wall_n[value] else None,
                n_trials=total[value],
            )
            for value in sorted(total)
        ]

        cell = {"task_id": task, **pinned}
        return StatsResponse(axis=axis, cell=cell, stats=stats)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Trials browser
# ---------------------------------------------------------------------------


@app.get("/api/trials")
async def get_trials(db: str = "") -> list[dict]:
    """Every trial with its gate scorecard, cost, and wall time — the Browse
    screen. Nothing here is blind (no active comparison)."""
    conn = _open(db)
    try:
        rows = conn.execute(
            """SELECT t.*,
                      g.passed, g.compile_passed, g.visible_passed, g.hidden_passed,
                      c.usd_equiv, c.input_tokens, c.output_tokens, c.cache_read_tokens,
                      r.wall_seconds, r.exit_status, r.error
               FROM trial t
               LEFT JOIN gate_result g ON g.trial_id = t.id
               LEFT JOIN cost_record c ON c.trial_id = t.id
               LEFT JOIN run_result r ON r.trial_id = t.id
               ORDER BY t.task_id, t.methodology_id, t.repo_context_id, t.model, t.runner, t.rep"""
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for col in ("passed", "compile_passed", "visible_passed", "hidden_passed"):
                if d.get(col) is not None:
                    d[col] = bool(d[col])
            out.append(d)
        return out
    finally:
        conn.close()


@app.get("/api/trials/{trial_id}")
async def get_trial_detail(trial_id: str, db: str = "") -> dict:
    """Full unblinded detail for one trial: diff, per-tier gate logs, cost."""
    conn = _open(db)
    try:
        trial = get_trial(conn, trial_id)
        if trial is None:
            raise HTTPException(404, "Trial not found")
        rr = get_run_result(conn, trial_id)
        gr = get_gate_result(conn, trial_id)
        cr = get_cost_record(conn, trial_id)
        return {
            "trial": trial.__dict__,
            "run_result": rr.__dict__ if rr else None,
            "gate_result": gr.__dict__ if gr else None,
            "cost_record": cr.__dict__ if cr else None,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@app.get("/api/report")
async def get_report(
    axis: str = "methodology",
    task: str = "",
    methodology: str = "",
    repo_context: str = "",
    model: str = "",
    runner: str = "",
    db: str = "",
) -> dict:
    """The full ranking report as JSON (grading.aggregate.build_report), plus
    any HTML artifacts already written to reports/."""
    if axis not in AXIS_FIELDS:
        raise HTTPException(400, f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")

    from grading.aggregate import build_report, flag_lines
    from grading.bradley_terry import strength_to_elo

    cell = {
        "task_id": task,
        "methodology_id": methodology,
        "repo_context_id": repo_context,
        "model": model,
        "runner": runner,
    }
    dropped = cell.pop(AXIS_FIELDS[axis], None)

    conn = _open(db)
    try:
        data = build_report(conn, axis, cell)
        orphans = conn.execute(
            "SELECT COUNT(*) FROM judgment WHERE session_id NOT IN (SELECT id FROM grading_session)"
        ).fetchone()[0]
    finally:
        conn.close()

    payload = asdict(data)
    for s in payload["summaries"]:
        if s["bt_ci"] is not None:
            lo, hi = s["bt_ci"]
            s["bt_ci_elo"] = [strength_to_elo(lo), strength_to_elo(hi)]
        else:
            s["bt_ci_elo"] = None
    payload["flag_lines"] = flag_lines(data.flags)
    payload["orphan_judgments"] = orphans
    payload["ignored_pin"] = dropped or None

    artifacts = []
    if REPORTS_DIR.is_dir():
        for p in sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
            artifacts.append({"name": p.name, "modified_at": p.stat().st_mtime, "url": f"/reports/{p.name}"})
    payload["artifacts"] = artifacts
    return payload


# ---------------------------------------------------------------------------
# Run launcher
# ---------------------------------------------------------------------------


@app.get("/api/runs/plan")
async def runs_plan(
    task: str = "all",
    methodology: str = "all",
    repo_context: str = "all",
    model: str = "",
    runner: str = "oracle",
    reps: int = 1,
    full_matrix: bool = False,
    db: str = "",
) -> dict:
    params = {
        "task": task, "methodology": methodology, "repo_context": repo_context,
        "model": model, "runner": runner, "reps": reps, "full_matrix": full_matrix,
    }
    conn = _open(db)
    try:
        return run_manager.plan_run(conn, params)
    except run_manager.RunRequestError as e:
        raise HTTPException(e.status, str(e))
    finally:
        conn.close()


@app.post("/api/runs")
async def runs_start(body: dict = Body(...)) -> dict:
    db_name = body.get("db") or _db_path.name
    db_path = _resolve_db_path(body.get("db", ""), must_exist=False)
    params = {
        "task": body.get("task", "all"),
        "methodology": body.get("methodology", "all"),
        "repo_context": body.get("repo_context", "all"),
        "model": body.get("model", ""),
        "runner": body.get("runner", ""),
        "reps": body.get("reps", 1),
        "full_matrix": body.get("full_matrix", False),
        "delay": body.get("delay", 0.0),
    }
    try:
        handle = run_manager.start_run(db_name, db_path, params, body.get("confirm_phrase"))
    except run_manager.RunRequestError as e:
        raise HTTPException(e.status, str(e))
    return {"run_id": handle.id, "n_trials": len(handle.trials), "status": handle.status}


@app.get("/api/runs")
async def runs_list() -> list[dict]:
    return run_manager.list_runs()


@app.get("/api/runs/{run_id}")
async def runs_get(run_id: str) -> dict:
    handle = run_manager.get_run(run_id)
    if handle is None:
        raise HTTPException(404, "Run not found")
    return handle.snapshot()


@app.post("/api/runs/{run_id}/cancel")
async def runs_cancel(run_id: str) -> dict:
    if not run_manager.request_cancel(run_id):
        raise HTTPException(409, "Run is not running")
    return {"ok": True, "note": "run stops after the current trial finishes"}


@app.get("/api/runs/{run_id}/events")
async def runs_events(run_id: str) -> StreamingResponse:
    """SSE stream of a run's progress events (replays history, then follows)."""
    handle = run_manager.get_run(run_id)
    if handle is None:
        raise HTTPException(404, "Run not found")

    async def stream():
        idx = 0
        while True:
            while idx < len(handle.events):
                yield f"data: {json.dumps(handle.events[idx])}\n\n"
                idx += 1
            if handle.status != "running":
                yield f"data: {json.dumps({'type': 'end', 'status': handle.status})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------------------
# SPA serving (must stay the LAST route: catch-all)
# ---------------------------------------------------------------------------

_NOT_BUILT_PAGE = """<!doctype html>
<html><head><title>tiltyard — frontend not built</title></head>
<body style="font-family: system-ui; max-width: 40rem; margin: 4rem auto;">
<h1>Frontend not built yet</h1>
<p>The API server is running, but <code>ui/frontend/dist/</code> does not exist.</p>
<p>Build it once with:</p>
<pre>python cli.py setup</pre>
<p>or directly:</p>
<pre>cd ui/frontend
npm install
npm run build</pre>
</body></html>"""


@app.get("/{full_path:path}", include_in_schema=False)
async def spa(full_path: str):
    if full_path.startswith(("api/", "assets/", "reports/")):
        raise HTTPException(404, "Not found")
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(_NOT_BUILT_PAGE, status_code=503)
