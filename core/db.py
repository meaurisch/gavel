import json
import sqlite3
from pathlib import Path

from pydantic import TypeAdapter

from core.models import (
    CostRecord,
    GateResult,
    Judgment,
    MethodologySpec,
    RepoContextSpec,
    RunResult,
    TaskSpec,
    Trial,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_spec (
    id TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    instruction TEXT NOT NULL,
    run_cmd TEXT NOT NULL,
    held_out_tests_path TEXT NOT NULL,
    reference_diff_path TEXT NOT NULL
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
    wall_seconds REAL NOT NULL
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
    test_output TEXT NOT NULL
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
    created_at TEXT NOT NULL
);
"""


def connect(db_path: Path = Path("results.db")) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


# -- inserts --

def insert_task_spec(conn: sqlite3.Connection, t: TaskSpec) -> None:
    conn.execute(
        "INSERT INTO task_spec VALUES (?, ?, ?, ?, ?, ?, ?)",
        (t.id, t.repo_url, t.base_commit, t.instruction, t.run_cmd,
         t.held_out_tests_path, t.reference_diff_path),
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


def insert_trial(conn: sqlite3.Connection, t: Trial) -> None:
    conn.execute(
        "INSERT INTO trial VALUES (?, ?, ?, ?, ?, ?, ?)",
        (t.id, t.task_id, t.methodology_id, t.repo_context_id, t.model, t.runner, t.rep),
    )
    conn.commit()


def insert_run_result(conn: sqlite3.Connection, r: RunResult) -> None:
    conn.execute(
        "INSERT INTO run_result VALUES (?, ?, ?, ?)",
        (r.trial_id, r.diff, r.exit_status, r.wall_seconds),
    )
    conn.commit()


def insert_cost_record(conn: sqlite3.Connection, c: CostRecord) -> None:
    conn.execute(
        "INSERT INTO cost_record VALUES (?, ?, ?, ?, ?, ?, ?)",
        (c.trial_id, c.native_unit, c.native_amount, c.usd_equiv,
         c.input_tokens, c.output_tokens, c.cache_read_tokens),
    )
    conn.commit()


def insert_gate_result(conn: sqlite3.Connection, g: GateResult) -> None:
    conn.execute(
        "INSERT INTO gate_result VALUES (?, ?, ?)",
        (g.trial_id, int(g.passed), g.test_output),
    )
    conn.commit()


# -- reads --

def get_task_spec(conn: sqlite3.Connection, id: str) -> TaskSpec | None:
    row = conn.execute("SELECT * FROM task_spec WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return TypeAdapter(TaskSpec).validate_python(dict(row))


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
    return TypeAdapter(GateResult).validate_python(d)


def trial_exists(conn: sqlite3.Connection, id: str) -> bool:
    row = conn.execute("SELECT 1 FROM trial WHERE id = ?", (id,)).fetchone()
    return row is not None


def list_trials(conn: sqlite3.Connection) -> list[Trial]:
    rows = conn.execute("SELECT * FROM trial").fetchall()
    ta = TypeAdapter(Trial)
    return [ta.validate_python(dict(r)) for r in rows]


# -- judgment --

def insert_judgment(conn: sqlite3.Connection, j: Judgment) -> None:
    conn.execute(
        "INSERT INTO judgment VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (j.id, j.session_id, j.task_id, j.model, j.left_trial_id,
         j.right_trial_id, j.choice, j.rubric_correctness,
         j.rubric_minimality, j.rubric_readability,
         j.rubric_overengineering, j.created_at),
    )
    conn.commit()


def list_judgments(conn: sqlite3.Connection, session_id: str) -> list[Judgment]:
    rows = conn.execute(
        "SELECT * FROM judgment WHERE session_id = ?", (session_id,)
    ).fetchall()
    ta = TypeAdapter(Judgment)
    return [ta.validate_python(dict(r)) for r in rows]


# -- grading queries --

def list_passing_trials(conn: sqlite3.Connection, task_id: str, model: str) -> list[Trial]:
    rows = conn.execute(
        """SELECT t.* FROM trial t
           JOIN gate_result g ON t.id = g.trial_id
           WHERE t.task_id = ? AND t.model = ? AND g.passed = 1""",
        (task_id, model),
    ).fetchall()
    ta = TypeAdapter(Trial)
    return [ta.validate_python(dict(r)) for r in rows]


def list_grading_tasks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT t.task_id, t.model, t.repo_context_id,
                  COUNT(DISTINCT t.methodology_id) as n_methodologies
           FROM trial t
           JOIN gate_result g ON t.id = g.trial_id
           WHERE g.passed = 1
           GROUP BY t.task_id, t.model, t.repo_context_id
           HAVING COUNT(DISTINCT t.methodology_id) >= 2"""
    ).fetchall()
    return [dict(r) for r in rows]
