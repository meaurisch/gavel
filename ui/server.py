import logging
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.db import (
    connect,
    insert_judgment,
    list_judgments,
    list_passing_trials,
    list_grading_tasks,
    get_run_result,
    get_trial,
)
from core.models import Judgment

from grading.pairwise import generate_pairs, anonymize_diff, compute_proxy, DiffProxy

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
    task_id: str
    model: str
    pairs: list[tuple[str, str]]
    judgments_made: set[int] = field(default_factory=set)


_sessions: dict[str, SessionState] = {}

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


class TaskInfo(BaseModel):
    task_id: str
    models: list[str]


class BlindDiffResponse(BaseModel):
    label: str
    diff: str
    proxy: DiffProxy


class PairResponse(BaseModel):
    pair_index: int
    total_pairs: int
    left: BlindDiffResponse
    right: BlindDiffResponse


class SessionResponse(BaseModel):
    session_id: str
    task_id: str
    model: str
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
    left_methodology_id: str
    right_methodology_id: str
    choice: str | None


class MethodologyRecord(BaseModel):
    wins: int
    losses: int
    ties: int


class RevealResponse(BaseModel):
    pairs: list[RevealPair]
    summary: dict[str, MethodologyRecord]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/tasks")
async def get_tasks() -> list[TaskInfo]:
    rows = list_grading_tasks(_conn)
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[row["task_id"]].append(row["model"])
    return [TaskInfo(task_id=tid, models=models) for tid, models in grouped.items()]


@app.get("/api/pairs")
async def get_pairs(task: str, model: str) -> SessionResponse:
    trials = list_passing_trials(_conn, task, model)

    methodology_ids = {t.methodology_id for t in trials}
    if len(methodology_ids) < 2:
        raise HTTPException(400, "Not enough passing methodologies")

    run_results: dict[str, object] = {}
    for t in trials:
        rr = get_run_result(_conn, t.id)
        if rr is not None:
            run_results[t.id] = rr

    trial_pairs = generate_pairs(trials, run_results)

    session_id = uuid.uuid4().hex
    id_pairs = [(left.id, right.id) for left, right in trial_pairs]
    session = SessionState(
        session_id=session_id,
        task_id=task,
        model=model,
        pairs=id_pairs,
    )
    _sessions[session_id] = session

    all_methodology_ids = list(methodology_ids)
    pair_responses: list[PairResponse] = []
    for i, (left, right) in enumerate(trial_pairs):
        left_rr = run_results[left.id]
        right_rr = run_results[right.id]

        left_diff = anonymize_diff(left_rr.diff, all_methodology_ids)
        right_diff = anonymize_diff(right_rr.diff, all_methodology_ids)

        pair_responses.append(PairResponse(
            pair_index=i,
            total_pairs=len(trial_pairs),
            left=BlindDiffResponse(
                label="A",
                diff=left_diff,
                proxy=compute_proxy(left_rr.diff),
            ),
            right=BlindDiffResponse(
                label="B",
                diff=right_diff,
                proxy=compute_proxy(right_rr.diff),
            ),
        ))

    return SessionResponse(
        session_id=session_id,
        task_id=task,
        model=model,
        total_pairs=len(trial_pairs),
        pairs=pair_responses,
    )


@app.post("/api/judge")
async def judge(req: JudgeRequest) -> JudgeResponse:
    session = _sessions.get(req.session_id)
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
        task_id=session.task_id,
        model=session.model,
        left_trial_id=left_trial_id,
        right_trial_id=right_trial_id,
        choice=req.choice,
        rubric_correctness=req.rubric_correctness,
        rubric_minimality=req.rubric_minimality,
        rubric_readability=req.rubric_readability,
        rubric_overengineering=req.rubric_overengineering,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    insert_judgment(_conn, judgment)
    session.judgments_made.add(req.pair_index)

    remaining = len(session.pairs) - len(session.judgments_made)
    return JudgeResponse(ok=True, remaining=remaining)


@app.get("/api/reveal")
async def reveal(session_id: str) -> RevealResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    judgments = list_judgments(_conn, session_id)
    judgment_by_pair: dict[tuple[str, str], Judgment] = {}
    for j in judgments:
        judgment_by_pair[(j.left_trial_id, j.right_trial_id)] = j

    reveal_pairs: list[RevealPair] = []
    summary: dict[str, MethodologyRecord] = defaultdict(lambda: MethodologyRecord(wins=0, losses=0, ties=0))

    for i, (left_id, right_id) in enumerate(session.pairs):
        left_trial = get_trial(_conn, left_id)
        right_trial = get_trial(_conn, right_id)
        left_methodology = left_trial.methodology_id
        right_methodology = right_trial.methodology_id

        j = judgment_by_pair.get((left_id, right_id))
        choice = j.choice if j else None

        reveal_pairs.append(RevealPair(
            pair_index=i,
            left_methodology_id=left_methodology,
            right_methodology_id=right_methodology,
            choice=choice,
        ))

        if choice == "A":
            rec = summary[left_methodology]
            summary[left_methodology] = MethodologyRecord(wins=rec.wins + 1, losses=rec.losses, ties=rec.ties)
            rec = summary[right_methodology]
            summary[right_methodology] = MethodologyRecord(wins=rec.wins, losses=rec.losses + 1, ties=rec.ties)
        elif choice == "B":
            rec = summary[right_methodology]
            summary[right_methodology] = MethodologyRecord(wins=rec.wins + 1, losses=rec.losses, ties=rec.ties)
            rec = summary[left_methodology]
            summary[left_methodology] = MethodologyRecord(wins=rec.wins, losses=rec.losses + 1, ties=rec.ties)
        elif choice == "tie":
            rec = summary[left_methodology]
            summary[left_methodology] = MethodologyRecord(wins=rec.wins, losses=rec.losses, ties=rec.ties + 1)
            rec = summary[right_methodology]
            summary[right_methodology] = MethodologyRecord(wins=rec.wins, losses=rec.losses, ties=rec.ties + 1)

    return RevealResponse(pairs=reveal_pairs, summary=dict(summary))
