"""Browser run-launcher: plan, estimate, start, and watch trial runs.

Reuses core.executor.execute_all (the one and only execution path) in a
background thread; on_progress events accumulate on a RunHandle that the SSE
endpoint in ui.server streams to the browser.

Spend safety: only free runners (oracle/nop) start unconditionally. claude-code
spends real API budget, so starting it requires the exact confirmation phrase
CONFIRM_PHRASE — the browser must make the user type it. manual/copilot-cli
are never browser-launchable (stdin-interactive / stub).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from core.db import connect
from core.executor import execute_all
from core.matrix import expand
from core.methodology_loader import list_methodologies
from core.models import Trial
from core.repo_context_loader import list_repo_contexts
from core.task_loader import list_tasks

logger = logging.getLogger(__name__)

FREE_RUNNERS = {"oracle", "nop"}
PAID_RUNNERS = {"claude-code"}
CONFIRM_PHRASE = "SPEND"

# manual blocks on input(); copilot-cli is a stub.
UNLAUNCHABLE = {
    "manual": "the manual runner waits on terminal stdin — launch it with `python cli.py run --runner manual`",
    "copilot-cli": "copilot-cli is a stub runner (Copilot support deferred)",
}


class RunRequestError(Exception):
    """Invalid or refused run request; .status carries the HTTP status."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class _RunCancelled(Exception):
    pass


@dataclass
class RunHandle:
    id: str
    params: dict
    db_name: str
    db_path: str
    trials: list[dict]
    status: str = "running"          # running | done | error | cancelled
    error: str | None = None
    events: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    cancel_requested: bool = False

    def snapshot(self) -> dict:
        done = sum(1 for e in self.events if e.get("type") == "progress")
        return {
            "id": self.id,
            "params": self.params,
            "db": self.db_name,
            "status": self.status,
            "error": self.error,
            "trials": self.trials,
            "n_trials": len(self.trials),
            "n_done": done,
            "events": list(self.events),
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


_runs: dict[str, RunHandle] = {}
_lock = threading.Lock()


def get_run(run_id: str) -> RunHandle | None:
    return _runs.get(run_id)


def list_runs() -> list[dict]:
    out = []
    for h in sorted(_runs.values(), key=lambda h: h.created_at, reverse=True):
        snap = h.snapshot()
        snap.pop("events")  # list view stays light
        snap.pop("trials")
        out.append(snap)
    return out


def active_run() -> RunHandle | None:
    with _lock:
        return next((h for h in _runs.values() if h.status == "running"), None)


def _ids(value: str, list_all) -> list[str]:
    if value == "all":
        return list_all()
    return [v.strip() for v in value.split(",") if v.strip()]


def expand_params(params: dict) -> list[Trial]:
    tasks = _ids(params.get("task", "all"), list_tasks)
    methodologies = _ids(params.get("methodology", "all"), list_methodologies)
    repo_contexts = _ids(params.get("repo_context", "all"), list_repo_contexts)
    models = [m.strip() for m in params.get("model", "").split(",") if m.strip()]
    runner = params.get("runner", "")
    reps = int(params.get("reps", 1))

    if not runner:
        raise RunRequestError("runner is required")
    if not models:
        raise RunRequestError("model is required (comma-separated model ids)")
    if not tasks:
        raise RunRequestError("no tasks found")
    if reps < 1 or reps > 20:
        raise RunRequestError("reps must be between 1 and 20")

    return expand(
        tasks, methodologies, repo_contexts, models, runner, reps,
        full_matrix=bool(params.get("full_matrix", False)),
    )


def estimate_cost(conn: sqlite3.Connection, trials: list[Trial]) -> dict:
    """Cost estimate from historical trials in this DB: prefer the mean of the
    same (task, model), fall back to the model's overall mean, else pricing
    rates only (no token prediction is honest without history)."""
    hist_task_model: dict[tuple[str, str], tuple[float, int]] = {}
    hist_model: dict[str, tuple[float, int]] = {}
    for row in conn.execute(
        """SELECT t.task_id, t.model, AVG(c.usd_equiv) AS mean_usd, COUNT(*) AS n
           FROM cost_record c JOIN trial t ON t.id = c.trial_id
           GROUP BY t.task_id, t.model"""
    ).fetchall():
        hist_task_model[(row["task_id"], row["model"])] = (row["mean_usd"], row["n"])
    for row in conn.execute(
        """SELECT t.model, AVG(c.usd_equiv) AS mean_usd, COUNT(*) AS n
           FROM cost_record c JOIN trial t ON t.id = c.trial_id
           GROUP BY t.model"""
    ).fetchall():
        hist_model[row["model"]] = (row["mean_usd"], row["n"])

    total = 0.0
    n_estimated = 0
    lines: list[dict] = []
    for t in trials:
        est, basis = None, None
        if (t.task_id, t.model) in hist_task_model:
            est, n = hist_task_model[(t.task_id, t.model)]
            basis = f"mean of {n} historical {t.task_id}×{t.model} trial(s)"
        elif t.model in hist_model:
            est, n = hist_model[t.model]
            basis = f"mean of {n} historical {t.model} trial(s), any task"
        if est is not None:
            total += est
            n_estimated += 1
        lines.append({"trial_id": t.id, "est_usd": est, "basis": basis})

    pricing_rates = None
    models = sorted({t.model for t in trials})
    try:
        from cost.pricing import load_pricing
        table, aliases = load_pricing()
        pricing_rates = {}
        for m in models:
            p = table.get(m) or table.get(aliases.get(m, ""))
            if p:
                pricing_rates[m] = {
                    "input_per_mtok": p.input_per_mtok,
                    "output_per_mtok": p.output_per_mtok,
                    "cache_read_per_mtok": p.cache_read_per_mtok,
                }
    except Exception:
        pass

    return {
        "n_trials": len(trials),
        "n_with_estimate": n_estimated,
        "estimated_total_usd": round(total, 4) if n_estimated else None,
        "estimate_covers_all_trials": n_estimated == len(trials),
        "per_trial": lines,
        "pricing_rates": pricing_rates,
    }


def plan_run(conn: sqlite3.Connection, params: dict) -> dict:
    """Dry-run: the expanded trial grid plus a cost estimate. Never executes."""
    trials = expand_params(params)
    runner = params["runner"]
    return {
        "trials": [t.__dict__ for t in trials],
        "n_trials": len(trials),
        "runner": runner,
        "paid": runner in PAID_RUNNERS,
        "launchable": runner not in UNLAUNCHABLE,
        "launch_blocked_reason": UNLAUNCHABLE.get(runner),
        "confirm_phrase": CONFIRM_PHRASE if runner in PAID_RUNNERS else None,
        "estimate": estimate_cost(conn, trials) if runner in PAID_RUNNERS else None,
    }


def start_run(db_name: str, db_path: Path, params: dict, confirm_phrase: str | None) -> RunHandle:
    runner = params.get("runner", "")
    if runner in UNLAUNCHABLE:
        raise RunRequestError(f"runner {runner!r} cannot be launched from the browser: {UNLAUNCHABLE[runner]}")
    if runner not in FREE_RUNNERS | PAID_RUNNERS:
        raise RunRequestError(f"unknown runner {runner!r}")
    if runner in PAID_RUNNERS and confirm_phrase != CONFIRM_PHRASE:
        raise RunRequestError(
            f"runner {runner!r} spends real API budget — repeat the confirmation "
            f"phrase {CONFIRM_PHRASE!r} to start it",
            status=409,
        )

    trials = expand_params(params)
    if not trials:
        raise RunRequestError("no trials to run (methodology/harness filtering removed all combinations)")

    with _lock:
        if any(h.status == "running" for h in _runs.values()):
            raise RunRequestError("another run is already in progress — wait for it to finish", status=409)
        handle = RunHandle(
            id=uuid.uuid4().hex[:12],
            params={k: v for k, v in params.items()},
            db_name=db_name,
            db_path=str(db_path),
            trials=[t.__dict__ for t in trials],
        )
        _runs[handle.id] = handle

    thread = threading.Thread(target=_worker, args=(handle, trials), daemon=True, name=f"run-{handle.id}")
    thread.start()
    return handle


def request_cancel(run_id: str) -> bool:
    handle = _runs.get(run_id)
    if handle is None or handle.status != "running":
        return False
    handle.cancel_requested = True
    return True


def _worker(handle: RunHandle, trials: list[Trial]) -> None:
    conn = connect(Path(handle.db_path))
    try:
        def on_progress(i: int, trial: Trial, summary: dict) -> None:
            clean = {k: v for k, v in summary.items() if k != "worktree"}
            handle.events.append({
                "type": "progress",
                "index": i,
                "trial_id": trial.id,
                "summary": clean,
                "ts": time.time(),
            })
            if handle.cancel_requested:
                raise _RunCancelled()

        execute_all(trials, conn, delay=float(handle.params.get("delay", 0.0)), on_progress=on_progress)
        handle.status = "done"
    except _RunCancelled:
        handle.status = "cancelled"
        logger.info("Run %s cancelled after current trial", handle.id)
    except Exception as e:
        handle.status = "error"
        handle.error = str(e)
        logger.error("Run %s failed: %s", handle.id, e, exc_info=True)
    finally:
        handle.finished_at = time.time()
        conn.close()
        handle.events.append({"type": "status", "status": handle.status, "error": handle.error, "ts": time.time()})
