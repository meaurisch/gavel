import logging
import math
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.db import (
    connect,
    grading_readiness,
    get_grading_session,
    insert_grading_session,
    list_judgments,
    upsert_judgment,
    list_passing_trials,
    list_cell_trials,
    list_grading_cells,
    get_cost_record,
    get_gate_result,
    get_run_result,
    get_trial,
)
from core.matrix import HARNESS_MAP
from core.methodology_loader import load_methodology
from core.models import GradingSession, Judgment
from core.repo_context_loader import load_repo_context

from grading.pairwise import generate_pairs, anonymize_diff, compute_proxy, DiffProxy, AXIS_FIELDS
from grading.bradley_terry import fit_bradley_terry, bootstrap_ci, bt_scores_to_elo
from grading.analyzer import analyze, AnalyzerFlags

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB path management
# ---------------------------------------------------------------------------

_db_path: Path = Path("results.db")


def set_db_path(path: Path) -> None:
    global _db_path
    _db_path = path


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

_conn = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn
    _conn = connect(_db_path)
    yield
    _conn.close()


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    session_id: str
    axis: str
    cell: dict[str, str]          # task_id + the three pinned axis values
    pairs: list[tuple[str, str]]  # (left_trial_id, right_trial_id)
    judgments_made: set[int] = field(default_factory=set)


_sessions: dict[str, SessionState] = {}


def _get_session(session_id: str) -> SessionState | None:
    """In-memory cache first, then the grading_session table — a session must
    survive a server restart (its judgments are already persisted)."""
    session = _sessions.get(session_id)
    if session is not None:
        return session

    stored = get_grading_session(_conn, session_id)
    if stored is None:
        return None

    # Rebuild judgments_made from the persisted judgments.
    index_by_pair = {pair: i for i, pair in enumerate(stored.pairs)}
    made = {
        index_by_pair[(j.left_trial_id, j.right_trial_id)]
        for j in list_judgments(_conn, session_id)
        if (j.left_trial_id, j.right_trial_id) in index_by_pair
    }
    session = SessionState(
        session_id=stored.id,
        axis=stored.axis,
        cell=stored.cell,
        pairs=list(stored.pairs),
        judgments_made=made,
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

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="setup-bench grading", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)

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


class BlindDiffResponse(BaseModel):
    label: str
    diff: str
    proxy: DiffProxy
    gate: GateScorecard


class PairResponse(BaseModel):
    pair_index: int
    total_pairs: int
    left: BlindDiffResponse
    right: BlindDiffResponse


class SessionResponse(BaseModel):
    session_id: str
    axis: str
    cell: dict[str, str]
    total_pairs: int
    pairs: list[PairResponse]


class JudgeRequest(BaseModel):
    session_id: str
    pair_index: int
    choice: str
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
    pairs: list[RevealPair]
    summary: dict[str, AxisValueRecord]
    axis: str
    cell: dict[str, str]
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
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/axes")
async def get_axes() -> list[AxisInfo]:
    result: list[AxisInfo] = []
    for axis in AXIS_FIELDS:
        cells = list_grading_cells(_conn, axis)
        if cells:
            result.append(AxisInfo(axis=axis, n_cells=len(cells)))
    return result


@app.get("/api/grading-status")
async def get_grading_status() -> GradingStatusResponse:
    return GradingStatusResponse(**grading_readiness(_conn))


@app.get("/api/cells")
async def get_cells(axis: str) -> list[dict]:
    if axis not in AXIS_FIELDS:
        raise HTTPException(400, f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")
    return list_grading_cells(_conn, axis)


@app.get("/api/pairs")
async def get_pairs(
    axis: str,
    task: str,
    methodology: str = "",
    repo_context: str = "",
    model: str = "",
    runner: str = "",
) -> SessionResponse:
    if axis not in AXIS_FIELDS:
        raise HTTPException(400, f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")

    comparison_col = AXIS_FIELDS[axis]

    # Build pinned kwargs: the three non-comparison axes whose values are non-empty
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

    trials = list_passing_trials(_conn, task_id=task, **pinned)

    run_results: dict[str, object] = {}
    gate_results: dict[str, object] = {}
    for t in trials:
        rr = get_run_result(_conn, t.id)
        if rr is not None:
            run_results[t.id] = rr
        gr = get_gate_result(_conn, t.id)
        if gr is not None:
            gate_results[t.id] = gr

    # A passing trial with no run_result has no diff to show — drop it rather
    # than 500 on a KeyError below.
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

    # Build cell dict for the session
    cell: dict[str, str] = {"task_id": task}
    for param_name, val in param_values.items():
        kwarg_name = _PARAM_TO_KWARG[param_name]
        if kwarg_name != comparison_col and val:
            cell[kwarg_name] = val

    session = SessionState(
        session_id=session_id,
        axis=axis,
        cell=cell,
        pairs=id_pairs,
    )
    _sessions[session_id] = session
    insert_grading_session(_conn, GradingSession(
        id=session_id,
        axis=axis,
        cell=cell,
        pairs=id_pairs,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))

    # Blind all axis ids across all four axes, minus causally-inert ones —
    # ids that lay down no files can't leak into a diff, and redacting them
    # mangles incidental code like Python's `None`.
    skip_ids = _inert_axis_ids(trials)
    axis_ids_by_axis: dict[str, list[str]] = {
        k: sorted({getattr(t, AXIS_FIELDS[k]) for t in trials} - skip_ids)
        for k in AXIS_FIELDS
    }

    _default_gate = GateScorecard(compile_passed=None, visible_passed=None, hidden_passed=None)

    pair_responses: list[PairResponse] = []
    for i, (left, right) in enumerate(trial_pairs):
        left_rr = run_results[left.id]
        right_rr = run_results[right.id]

        left_diff = anonymize_diff(left_rr.diff, axis_ids_by_axis)
        right_diff = anonymize_diff(right_rr.diff, axis_ids_by_axis)

        left_gr = gate_results.get(left.id)
        right_gr = gate_results.get(right.id)
        left_gate = GateScorecard(
            compile_passed=left_gr.compile_passed,
            visible_passed=left_gr.visible_passed,
            hidden_passed=left_gr.hidden_passed,
        ) if left_gr else _default_gate
        right_gate = GateScorecard(
            compile_passed=right_gr.compile_passed,
            visible_passed=right_gr.visible_passed,
            hidden_passed=right_gr.hidden_passed,
        ) if right_gr else _default_gate

        pair_responses.append(PairResponse(
            pair_index=i,
            total_pairs=len(trial_pairs),
            left=BlindDiffResponse(
                label="A",
                diff=left_diff,
                proxy=compute_proxy(left_rr.diff),
                gate=left_gate,
            ),
            right=BlindDiffResponse(
                label="B",
                diff=right_diff,
                proxy=compute_proxy(right_rr.diff),
                gate=right_gate,
            ),
        ))

    return SessionResponse(
        session_id=session_id,
        axis=axis,
        cell=cell,
        total_pairs=len(trial_pairs),
        pairs=pair_responses,
    )


@app.post("/api/judge")
async def judge(req: JudgeRequest) -> JudgeResponse:
    session = _get_session(req.session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

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

    upsert_judgment(_conn, judgment)
    session.judgments_made.add(req.pair_index)

    remaining = len(session.pairs) - len(session.judgments_made)
    return JudgeResponse(ok=True, remaining=remaining)


@app.get("/api/reveal")
async def reveal(session_id: str) -> RevealResponse:
    session = _get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    field = AXIS_FIELDS[session.axis]

    judgments = list_judgments(_conn, session_id)
    judgment_by_pair: dict[tuple[str, str], Judgment] = {}
    for j in judgments:
        judgment_by_pair[(j.left_trial_id, j.right_trial_id)] = j

    reveal_pairs: list[RevealPair] = []
    summary: dict[str, AxisValueRecord] = defaultdict(lambda: AxisValueRecord(wins=0, losses=0, ties=0))
    comparisons: list[tuple[str, str, str]] = []

    for i, (left_id, right_id) in enumerate(session.pairs):
        left_trial = get_trial(_conn, left_id)
        right_trial = get_trial(_conn, right_id)
        left_value = getattr(left_trial, field)
        right_value = getattr(right_trial, field)

        j = judgment_by_pair.get((left_id, right_id))
        choice = j.choice if j else None

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
    pass_rates, flags = _cell_pass_rates_and_flags(session.axis, session.cell)

    return RevealResponse(
        pairs=reveal_pairs,
        summary=dict(summary),
        axis=session.axis,
        cell=session.cell,
        bt_scores=bt_scores,
        analyzer_flags=flags,
        pass_rates=pass_rates,
    )


def _cell_trials(cell: dict[str, str]):
    """Re-query every trial in a session's cell (passing and failing)."""
    kwargs = {k: v for k, v in cell.items() if k != "task_id"}
    return list_cell_trials(_conn, task_id=cell["task_id"], **kwargs)


def _cell_pass_rates_and_flags(
    axis: str, cell: dict[str, str]
) -> tuple[dict[str, float], AnalyzerFlagsModel]:
    field = AXIS_FIELDS[axis]
    trials = _cell_trials(cell)
    gate_results = {}
    cost_records = {}
    passed: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for t in trials:
        gr = get_gate_result(_conn, t.id)
        cr = get_cost_record(_conn, t.id)
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

    trials = list_cell_trials(_conn, task_id=task, **pinned)

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
        gr = get_gate_result(_conn, t.id)
        # Pass rate is passers over trials WITH a gate verdict — the same
        # denominator /api/reveal and the analyzer use, so the two endpoints
        # can't disagree about the same cell.
        if gr is not None:
            gated[value] += 1
            if gr.passed:
                passed[value] += 1
        cr = get_cost_record(_conn, t.id)
        if cr is not None:
            cost_sum[value] += cr.usd_equiv
            cost_n[value] += 1
        rr = get_run_result(_conn, t.id)
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
