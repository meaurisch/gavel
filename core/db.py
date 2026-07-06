import json
import sqlite3
from pathlib import Path

from pydantic import TypeAdapter

from core.models import (
    CostRecord,
    GateResult,
    GradingSession,
    JudgeCallRecord,
    Judgment,
    MethodologySpec,
    RepoContextSpec,
    RunResult,
    TaskSpec,
    Trial,
)
from grading.pairwise import AXIS_FIELDS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_spec (
    id TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    instruction TEXT NOT NULL,
    run_cmd TEXT NOT NULL,
    held_out_tests_path TEXT NOT NULL,
    reference_diff_path TEXT NOT NULL,
    build_cmd TEXT,
    visible_test_cmd TEXT,
    difficulty TEXT
);

CREATE TABLE IF NOT EXISTS methodology_spec (
    id TEXT PRIMARY KEY,
    files TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repo_context_spec (
    id TEXT PRIMARY KEY,
    files TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trial (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    methodology_id TEXT NOT NULL,
    repo_context_id TEXT NOT NULL,
    model TEXT NOT NULL,
    runner TEXT NOT NULL,
    rep INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS run_result (
    trial_id TEXT PRIMARY KEY,
    diff TEXT NOT NULL,
    exit_status INTEGER NOT NULL,
    wall_seconds REAL NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS cost_record (
    trial_id TEXT PRIMARY KEY,
    native_unit TEXT NOT NULL,
    native_amount REAL NOT NULL,
    usd_equiv REAL NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS gate_result (
    trial_id TEXT PRIMARY KEY,
    passed INTEGER NOT NULL,
    compile_passed INTEGER,
    compile_output TEXT,
    visible_passed INTEGER,
    visible_output TEXT,
    hidden_passed INTEGER,
    hidden_output TEXT
);

CREATE TABLE IF NOT EXISTS grading_session (
    id TEXT PRIMARY KEY,
    axis TEXT NOT NULL,
    cell TEXT NOT NULL,
    pairs TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revealed_at TEXT,
    mode TEXT NOT NULL DEFAULT 'human',
    judge_provider TEXT,
    judge_model TEXT,
    judge_passes INTEGER
);

CREATE TABLE IF NOT EXISTS judgment (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    model TEXT NOT NULL,
    left_trial_id TEXT NOT NULL,
    right_trial_id TEXT NOT NULL,
    choice TEXT NOT NULL,
    rubric_correctness TEXT,
    rubric_minimality TEXT,
    rubric_readability TEXT,
    rubric_overengineering TEXT,
    created_at TEXT NOT NULL,
    grader TEXT NOT NULL DEFAULT 'human',
    rationale TEXT,
    confidence REAL,
    position_consistent INTEGER
);

CREATE TABLE IF NOT EXISTS judge_call (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    pair_index INTEGER NOT NULL,
    ordering TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    usd_equiv REAL,
    wall_seconds REAL NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);
"""


def connect(db_path: Path = Path("results.db")) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    # Backfill columns onto DBs created by an earlier schema.
    _ensure_column(conn, "task_spec", "build_cmd", "TEXT")
    _ensure_column(conn, "task_spec", "visible_test_cmd", "TEXT")
    _ensure_column(conn, "task_spec", "difficulty", "TEXT")
    _ensure_column(conn, "run_result", "error", "TEXT")
    _ensure_column(conn, "grading_session", "revealed_at", "TEXT")
    # LLM-judge mode (2026-07-06): pre-existing rows read as human-mode.
    _ensure_column(conn, "grading_session", "mode", "TEXT NOT NULL DEFAULT 'human'")
    _ensure_column(conn, "grading_session", "judge_provider", "TEXT")
    _ensure_column(conn, "grading_session", "judge_model", "TEXT")
    _ensure_column(conn, "grading_session", "judge_passes", "INTEGER")
    _ensure_column(conn, "judgment", "grader", "TEXT NOT NULL DEFAULT 'human'")
    _ensure_column(conn, "judgment", "rationale", "TEXT")
    _ensure_column(conn, "judgment", "confidence", "REAL")
    _ensure_column(conn, "judgment", "position_consistent", "INTEGER")
    conn.commit()


# -- inserts --

def insert_task_spec(conn: sqlite3.Connection, t: TaskSpec) -> None:
    conn.execute(
        "INSERT INTO task_spec VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (t.id, t.repo_url, t.base_commit, t.instruction, t.run_cmd,
         t.held_out_tests_path, t.reference_diff_path,
         t.build_cmd, t.visible_test_cmd, t.difficulty),
    )
    conn.commit()


def insert_methodology_spec(conn: sqlite3.Connection, s: MethodologySpec) -> None:
    conn.execute(
        "INSERT INTO methodology_spec VALUES (?, ?)",
        (s.id, json.dumps(s.files)),
    )
    conn.commit()


def insert_repo_context_spec(conn: sqlite3.Connection, s: RepoContextSpec) -> None:
    conn.execute(
        "INSERT INTO repo_context_spec VALUES (?, ?)",
        (s.id, json.dumps(s.files)),
    )
    conn.commit()


def _execute_trial_insert(conn: sqlite3.Connection, t: Trial) -> None:
    conn.execute(
        "INSERT INTO trial VALUES (?, ?, ?, ?, ?, ?, ?)",
        (t.id, t.task_id, t.methodology_id, t.repo_context_id, t.model, t.runner, t.rep),
    )


def insert_trial(conn: sqlite3.Connection, t: Trial) -> None:
    _execute_trial_insert(conn, t)
    conn.commit()


def _execute_run_result_insert(conn: sqlite3.Connection, r: RunResult) -> None:
    conn.execute(
        "INSERT INTO run_result VALUES (?, ?, ?, ?, ?)",
        (r.trial_id, r.diff, r.exit_status, r.wall_seconds, r.error),
    )


def insert_run_result(conn: sqlite3.Connection, r: RunResult) -> None:
    _execute_run_result_insert(conn, r)
    conn.commit()


def _execute_cost_record_insert(conn: sqlite3.Connection, c: CostRecord) -> None:
    conn.execute(
        "INSERT INTO cost_record VALUES (?, ?, ?, ?, ?, ?, ?)",
        (c.trial_id, c.native_unit, c.native_amount, c.usd_equiv,
         c.input_tokens, c.output_tokens, c.cache_read_tokens),
    )


def insert_cost_record(conn: sqlite3.Connection, c: CostRecord) -> None:
    _execute_cost_record_insert(conn, c)
    conn.commit()


def _bool_to_int(v: bool | None) -> int | None:
    return int(v) if v is not None else None


def _execute_gate_result_insert(conn: sqlite3.Connection, g: GateResult) -> None:
    conn.execute(
        "INSERT INTO gate_result VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (g.trial_id, int(g.passed),
         _bool_to_int(g.compile_passed), g.compile_output,
         _bool_to_int(g.visible_passed), g.visible_output,
         _bool_to_int(g.hidden_passed), g.hidden_output),
    )


def insert_gate_result(conn: sqlite3.Connection, g: GateResult) -> None:
    _execute_gate_result_insert(conn, g)
    conn.commit()


def persist_trial_result(
    conn: sqlite3.Connection,
    trial: Trial,
    run_result: RunResult,
    cost_record: CostRecord | None,
    gate_result: GateResult,
) -> None:
    """All-or-nothing persistence of one completed trial.

    A partial write (trial row committed, later insert failed) would leave an
    orphan trial that resume-dedup skips forever, with no result/gate/cost.
    """
    try:
        _execute_trial_insert(conn, trial)
        _execute_run_result_insert(conn, run_result)
        if cost_record is not None:
            _execute_cost_record_insert(conn, cost_record)
        _execute_gate_result_insert(conn, gate_result)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# -- reads --

def get_task_spec(conn: sqlite3.Connection, id: str) -> TaskSpec | None:
    row = conn.execute("SELECT * FROM task_spec WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d.setdefault("build_cmd", None)
    d.setdefault("visible_test_cmd", None)
    d.setdefault("difficulty", None)
    return TypeAdapter(TaskSpec).validate_python(d)


def get_methodology_spec(conn: sqlite3.Connection, id: str) -> MethodologySpec | None:
    row = conn.execute("SELECT * FROM methodology_spec WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["files"] = json.loads(d["files"])
    return TypeAdapter(MethodologySpec).validate_python(d)


def get_repo_context_spec(conn: sqlite3.Connection, id: str) -> RepoContextSpec | None:
    row = conn.execute("SELECT * FROM repo_context_spec WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["files"] = json.loads(d["files"])
    return TypeAdapter(RepoContextSpec).validate_python(d)


def get_trial(conn: sqlite3.Connection, id: str) -> Trial | None:
    row = conn.execute("SELECT * FROM trial WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return TypeAdapter(Trial).validate_python(dict(row))


def get_run_result(conn: sqlite3.Connection, trial_id: str) -> RunResult | None:
    row = conn.execute("SELECT * FROM run_result WHERE trial_id = ?", (trial_id,)).fetchone()
    if row is None:
        return None
    return TypeAdapter(RunResult).validate_python(dict(row))


def get_cost_record(conn: sqlite3.Connection, trial_id: str) -> CostRecord | None:
    row = conn.execute("SELECT * FROM cost_record WHERE trial_id = ?", (trial_id,)).fetchone()
    if row is None:
        return None
    return TypeAdapter(CostRecord).validate_python(dict(row))


def get_gate_result(conn: sqlite3.Connection, trial_id: str) -> GateResult | None:
    row = conn.execute("SELECT * FROM gate_result WHERE trial_id = ?", (trial_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["passed"] = bool(d["passed"])
    for col in ("compile_passed", "visible_passed", "hidden_passed"):
        if d.get(col) is not None:
            d[col] = bool(d[col])
    return TypeAdapter(GateResult).validate_python(d)


def list_gate_results(conn: sqlite3.Connection) -> dict[str, GateResult]:
    """All gate results keyed by trial_id (bulk read for reports)."""
    out: dict[str, GateResult] = {}
    for row in conn.execute("SELECT * FROM gate_result").fetchall():
        d = dict(row)
        d["passed"] = bool(d["passed"])
        for col in ("compile_passed", "visible_passed", "hidden_passed"):
            if d.get(col) is not None:
                d[col] = bool(d[col])
        out[d["trial_id"]] = TypeAdapter(GateResult).validate_python(d)
    return out


def list_cost_records(conn: sqlite3.Connection) -> dict[str, CostRecord]:
    """All cost records keyed by trial_id (bulk read for reports)."""
    ta = TypeAdapter(CostRecord)
    return {
        row["trial_id"]: ta.validate_python(dict(row))
        for row in conn.execute("SELECT * FROM cost_record").fetchall()
    }


def trial_exists(conn: sqlite3.Connection, id: str) -> bool:
    row = conn.execute("SELECT 1 FROM trial WHERE id = ?", (id,)).fetchone()
    return row is not None


def list_trials(conn: sqlite3.Connection) -> list[Trial]:
    rows = conn.execute("SELECT * FROM trial").fetchall()
    ta = TypeAdapter(Trial)
    return [ta.validate_python(dict(r)) for r in rows]


# -- judgment --

_JUDGMENT_COLS = (
    "id, session_id, task_id, model, left_trial_id, right_trial_id, choice, "
    "rubric_correctness, rubric_minimality, rubric_readability, "
    "rubric_overengineering, created_at, grader, rationale, confidence, "
    "position_consistent"
)


def _judgment_params(j: Judgment) -> tuple:
    return (j.id, j.session_id, j.task_id, j.model, j.left_trial_id,
            j.right_trial_id, j.choice, j.rubric_correctness,
            j.rubric_minimality, j.rubric_readability,
            j.rubric_overengineering, j.created_at, j.grader, j.rationale,
            j.confidence, _bool_to_int(j.position_consistent))


def insert_judgment(conn: sqlite3.Connection, j: Judgment) -> None:
    conn.execute(
        f"INSERT INTO judgment ({_JUDGMENT_COLS}) VALUES ({', '.join('?' * 16)})",
        _judgment_params(j),
    )
    conn.commit()


def upsert_judgment(conn: sqlite3.Connection, j: Judgment) -> None:
    """Latest-wins persistence for one (session, pair): re-judging a pair (the
    UI's go-back flow, or a client retry after a lost response) must REPLACE
    the earlier row, not add a second one — Bradley-Terry in the report counts
    every row, so duplicates would double-weight the pair."""
    try:
        conn.execute(
            "DELETE FROM judgment WHERE session_id = ? AND left_trial_id = ? AND right_trial_id = ?",
            (j.session_id, j.left_trial_id, j.right_trial_id),
        )
        conn.execute(
            f"INSERT INTO judgment ({_JUDGMENT_COLS}) VALUES ({', '.join('?' * 16)})",
            _judgment_params(j),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _judgment_from_row(row) -> Judgment:
    d = dict(row)
    d["grader"] = d.get("grader") or "human"
    if d.get("position_consistent") is not None:
        d["position_consistent"] = bool(d["position_consistent"])
    return TypeAdapter(Judgment).validate_python(d)


def list_judgments(conn: sqlite3.Connection, session_id: str) -> list[Judgment]:
    rows = conn.execute(
        "SELECT * FROM judgment WHERE session_id = ?", (session_id,)
    ).fetchall()
    return [_judgment_from_row(r) for r in rows]


# -- judge calls (LLM-judge usage/cost audit) --

_JUDGE_CALL_COLS = (
    "id, session_id, pair_index, ordering, provider, model, status, "
    "input_tokens, output_tokens, usd_equiv, wall_seconds, error, created_at"
)


def insert_judge_call(conn: sqlite3.Connection, c: JudgeCallRecord) -> None:
    conn.execute(
        f"INSERT INTO judge_call ({_JUDGE_CALL_COLS}) VALUES ({', '.join('?' * 13)})",
        (c.id, c.session_id, c.pair_index, c.ordering, c.provider, c.model,
         c.status, c.input_tokens, c.output_tokens, c.usd_equiv,
         c.wall_seconds, c.error, c.created_at),
    )
    conn.commit()


def list_judge_calls(conn: sqlite3.Connection, session_id: str) -> list[JudgeCallRecord]:
    rows = conn.execute(
        "SELECT * FROM judge_call WHERE session_id = ? ORDER BY created_at, pair_index",
        (session_id,),
    ).fetchall()
    ta = TypeAdapter(JudgeCallRecord)
    return [ta.validate_python(dict(r)) for r in rows]


def judge_call_rollup(conn: sqlite3.Connection, session_id: str) -> dict:
    """Session-level judge spend: call count, tokens, $ (where priced), errors."""
    row = conn.execute(
        """SELECT COUNT(*) AS n_calls,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(usd_equiv), 0.0) AS usd_equiv,
                  COALESCE(SUM(wall_seconds), 0.0) AS wall_seconds,
                  COALESCE(SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END), 0) AS n_errors
           FROM judge_call WHERE session_id = ?""",
        (session_id,),
    ).fetchone()
    return dict(row)


# -- grading sessions --

def insert_grading_session(conn: sqlite3.Connection, s: GradingSession) -> None:
    conn.execute(
        """INSERT INTO grading_session
           (id, axis, cell, pairs, created_at, revealed_at,
            mode, judge_provider, judge_model, judge_passes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (s.id, s.axis, json.dumps(s.cell), json.dumps(s.pairs), s.created_at,
         s.revealed_at, s.mode, s.judge_provider, s.judge_model, s.judge_passes),
    )
    conn.commit()


def mark_session_revealed(conn: sqlite3.Connection, session_id: str, revealed_at: str) -> None:
    """Idempotently close a session at its FIRST reveal — the original
    timestamp must survive later reveal-page loads."""
    conn.execute(
        "UPDATE grading_session SET revealed_at = ? WHERE id = ? AND revealed_at IS NULL",
        (revealed_at, session_id),
    )
    conn.commit()


def _session_from_row(row) -> GradingSession:
    d = dict(row)
    d["cell"] = json.loads(d["cell"])
    d["pairs"] = [tuple(p) for p in json.loads(d["pairs"])]
    d["mode"] = d.get("mode") or "human"
    return TypeAdapter(GradingSession).validate_python(d)


def get_grading_session(conn: sqlite3.Connection, id: str) -> GradingSession | None:
    row = conn.execute("SELECT * FROM grading_session WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _session_from_row(row)


def list_grading_sessions(conn: sqlite3.Connection) -> list[GradingSession]:
    rows = conn.execute("SELECT * FROM grading_session ORDER BY created_at").fetchall()
    return [_session_from_row(r) for r in rows]


# -- grading queries --

def list_passing_trials(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    methodology_id: str | None = None,
    repo_context_id: str | None = None,
    model: str | None = None,
    runner: str | None = None,
) -> list[Trial]:
    clauses = ["t.task_id = ?"]
    params: list[str] = [task_id]
    for col, val in [
        ("methodology_id", methodology_id),
        ("repo_context_id", repo_context_id),
        ("model", model),
        ("runner", runner),
    ]:
        if val is not None:
            clauses.append(f"t.{col} = ?")
            params.append(val)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""SELECT t.* FROM trial t
            JOIN gate_result g ON t.id = g.trial_id
            WHERE {where} AND g.passed = 1""",
        params,
    ).fetchall()
    ta = TypeAdapter(Trial)
    return [ta.validate_python(dict(r)) for r in rows]


def list_cell_trials(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    methodology_id: str | None = None,
    repo_context_id: str | None = None,
    model: str | None = None,
    runner: str | None = None,
) -> list[Trial]:
    """All trials in a cell — passing and failing — for pass-rate / analyzer / stats."""
    clauses = ["t.task_id = ?"]
    params: list[str] = [task_id]
    for col, val in [
        ("methodology_id", methodology_id),
        ("repo_context_id", repo_context_id),
        ("model", model),
        ("runner", runner),
    ]:
        if val is not None:
            clauses.append(f"t.{col} = ?")
            params.append(val)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT t.* FROM trial t WHERE {where}",
        params,
    ).fetchall()
    ta = TypeAdapter(Trial)
    return [ta.validate_python(dict(r)) for r in rows]


def grading_readiness(conn: sqlite3.Connection) -> dict:
    """Diagnostic: how much passing data exists to grade, per axis."""
    total_hidden_gate_passers = conn.execute(
        "SELECT COUNT(*) FROM gate_result WHERE passed = 1"
    ).fetchone()[0]

    axes: dict[str, dict] = {}
    for axis, comparison_col in AXIS_FIELDS.items():
        distinct_passing_values = conn.execute(
            f"""SELECT COUNT(DISTINCT t.{comparison_col}) FROM trial t
                JOIN gate_result g ON t.id = g.trial_id
                WHERE g.passed = 1"""
        ).fetchone()[0]
        axes[axis] = {
            "distinct_passing_values": distinct_passing_values,
            "gradeable_cells": len(list_grading_cells(conn, axis)),
        }

    return {
        "total_hidden_gate_passers": total_hidden_gate_passers,
        "axes": axes,
    }


def list_grading_cells(conn: sqlite3.Connection, axis: str) -> list[dict]:
    if axis not in AXIS_FIELDS:
        raise ValueError(f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")
    comparison_col = AXIS_FIELDS[axis]
    all_axis_cols = ["methodology_id", "repo_context_id", "model", "runner"]
    fixed_cols = ["task_id"] + [c for c in all_axis_cols if c != comparison_col]
    fixed_select = ", ".join(f"t.{c}" for c in fixed_cols)
    fixed_group = ", ".join(f"t.{c}" for c in fixed_cols)
    rows = conn.execute(
        f"""SELECT {fixed_select},
                   COUNT(DISTINCT t.{comparison_col}) AS n_values
            FROM trial t
            JOIN gate_result g ON t.id = g.trial_id
            WHERE g.passed = 1
            GROUP BY {fixed_group}
            HAVING COUNT(DISTINCT t.{comparison_col}) >= 2"""
    ).fetchall()
    return [dict(r) for r in rows]
