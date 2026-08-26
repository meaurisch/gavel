"""Browser LLM-judge launcher: plan, confirm, run, and watch judge sessions.

Modeled on ui.runs (the trial run launcher): a background thread judges the
pairs of one llm-mode grading session, appending progress events that the SSE
endpoint in ui.server streams to the browser. One judge run at a time.

Spend safety: the mock provider is free and starts unconditionally; every
other provider costs something real (subscription quota or metered tokens),
so starting one requires the typed confirmation phrase CONFIRM_PHRASE —
the same philosophy as the trial launcher's SPEND gate.

Blinding: the judge sees exactly what a blind human sees. Diffs go through
grading.pairwise.anonymize_diff with the session's blinding map, and
grading.judge.run_pair re-checks the assembled prompt against the raw axis
ids (BlindingError) before anything reaches a provider. Progress events carry
A/B/tie letters only — never axis values.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.db import (
    connect,
    get_gate_result,
    get_grading_session,
    get_run_result,
    get_task_spec,
    get_trial,
    insert_grading_session,
    insert_judge_call,
    list_judgments,
    list_passing_trials,
    upsert_judgment,
)
from core.models import GradingSession, JudgeCallRecord, Judgment, Trial
from grading.judge import BlindingError, JudgeError, run_pair
from grading.judge_providers import JudgeProviderError, get_provider, list_providers
from grading.pairwise import AXIS_FIELDS, anonymize_diff, generate_pairs, redact_axis_ids

logger = logging.getLogger(__name__)

CONFIRM_PHRASE = "JUDGE"

# Plan-estimate fallbacks for providers that don't declare their own
# EST_OUTPUT_TOKENS_PER_CALL / EST_PROMPT_OVERHEAD_TOKENS (see
# grading.judge_providers for the measured per-provider values).
_EST_OUTPUT_TOKENS_PER_CALL = 400
_EST_PROMPT_OVERHEAD_TOKENS = 0

_PARAM_TO_KWARG = {
    "methodology": "methodology_id",
    "repo_context": "repo_context_id",
    "model": "model",
    "runner": "runner",
}


class JudgeRequestError(Exception):
    """Invalid or refused judge request; .status carries the HTTP status."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class JudgeRunHandle:
    id: str
    session_id: str
    db_name: str
    db_path: str
    provider: str
    model: str
    passes: int
    n_pairs: int
    status: str = "running"          # running | done | error | cancelled
    error: str | None = None
    events: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    cancel_requested: bool = False

    def snapshot(self) -> dict:
        pair_events = [e for e in self.events if e.get("type") == "pair"]
        n_consistent = sum(1 for e in pair_events if e.get("position_consistent"))
        return {
            "id": self.id,
            "session_id": self.session_id,
            "db": self.db_name,
            "provider": self.provider,
            "model": self.model,
            "passes": self.passes,
            "status": self.status,
            "error": self.error,
            "n_pairs": self.n_pairs,
            "n_done": len(pair_events),
            "n_consistent": n_consistent,
            "events": list(self.events),
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


_runs: dict[str, JudgeRunHandle] = {}
_lock = threading.Lock()


def get_judge_run(run_id: str) -> JudgeRunHandle | None:
    return _runs.get(run_id)


def judge_run_for_session(session_id: str) -> JudgeRunHandle | None:
    """The most recent run handle for a session (page reloads land here)."""
    candidates = [h for h in _runs.values() if h.session_id == session_id]
    if not candidates:
        return None
    return max(candidates, key=lambda h: h.created_at)


def list_judge_runs() -> list[dict]:
    out = []
    for h in sorted(_runs.values(), key=lambda h: h.created_at, reverse=True):
        snap = h.snapshot()
        snap.pop("events")
        out.append(snap)
    return out


def provider_info() -> list[dict]:
    """Every registered provider with availability + models — the config UI."""
    out = []
    for p in list_providers():
        ok, reason = p.availability()
        out.append({
            "id": p.id,
            "label": p.label,
            "billing": p.billing,
            "available": ok,
            "reason": reason,
            "models": p.models(),
            "default_model": p.default_model(),
            "confirm_phrase": None if p.billing == "free" else CONFIRM_PHRASE,
        })
    return out


# ---------------------------------------------------------------------------
# planning
# ---------------------------------------------------------------------------

def _pinned_kwargs(params: dict, comparison_col: str) -> dict:
    pinned: dict[str, str] = {}
    for param_name, kwarg_name in _PARAM_TO_KWARG.items():
        val = params.get(param_name, "")
        if kwarg_name != comparison_col and val:
            pinned[kwarg_name] = val
    return pinned


def _validate_passes(raw) -> int:
    try:
        passes = int(raw)
    except (TypeError, ValueError):
        raise JudgeRequestError("passes must be 1 or 2")
    if passes not in (1, 2):
        raise JudgeRequestError("passes must be 1 or 2")
    return passes


def plan_judge(conn: sqlite3.Connection, params: dict) -> dict:
    """Dry-run: how many pairs/calls a judge session would make, with a token
    and (where priceable) dollar estimate. Never executes anything."""
    axis = params.get("axis", "")
    if axis not in AXIS_FIELDS:
        raise JudgeRequestError(f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")
    passes = _validate_passes(params.get("passes", 2))
    provider_id = params.get("provider", "claude-cli")
    try:
        provider = get_provider(provider_id)
    except KeyError as exc:
        raise JudgeRequestError(str(exc))
    model = params.get("judge_model") or provider.default_model()

    comparison_col = AXIS_FIELDS[axis]
    pinned = _pinned_kwargs(params, comparison_col)
    trials = list_passing_trials(conn, task_id=params.get("task", ""), **pinned)

    # Count only trials that HAVE a diff to judge — session creation drops
    # run_result-less trials, so the plan must too or n_pairs overpromises.
    counts: dict[str, int] = defaultdict(int)
    diff_chars = 0
    n_diffs = 0
    for t in trials:
        rr = get_run_result(conn, t.id)
        if rr is None:
            continue
        counts[getattr(t, comparison_col)] += 1
        diff_chars += len(rr.diff)
        n_diffs += 1
    total = sum(counts.values())
    candidates = (total * total - sum(c * c for c in counts.values())) // 2
    m = len(counts)
    n_pairs = min((m * (m - 1) // 2) * 3, candidates)
    if n_pairs < 1:
        raise JudgeRequestError(
            "Not enough passing values for this axis in the selected cell")

    task = get_task_spec(conn, params.get("task", ""))
    instruction_chars = len(task.instruction) if task else 500
    avg_diff = (diff_chars / n_diffs) if n_diffs else 2000
    # one call = provider wrapper overhead + static preamble + instruction
    # + both diffs; output size is provider-specific (thinking counts as
    # output on the claude CLI) — both measured against the real run.
    per_call_chars = 1800 + instruction_chars + 2 * avg_diff
    overhead_tokens = getattr(provider, "EST_PROMPT_OVERHEAD_TOKENS",
                              _EST_PROMPT_OVERHEAD_TOKENS)
    output_tokens_per_call = getattr(provider, "EST_OUTPUT_TOKENS_PER_CALL",
                                     _EST_OUTPUT_TOKENS_PER_CALL)
    n_calls = n_pairs * passes
    est_input = int(n_calls * (per_call_chars / 4 + overhead_tokens))
    est_output = n_calls * output_tokens_per_call

    est_usd = None
    if provider.billing == "free":
        est_usd = 0.0
    elif provider_id == "claude-cli":
        try:
            from cost.pricing import compute_api_rate_usd
            est_usd = compute_api_rate_usd(model, est_input, est_output, 0) or None
        except Exception:  # pragma: no cover - pricing table optional
            est_usd = None

    available, reason = provider.availability()
    return {
        "axis": axis,
        "provider": provider_id,
        "judge_model": model,
        "passes": passes,
        "billing": provider.billing,
        "available": available,
        "reason": reason,
        "n_pairs": n_pairs,
        "n_calls": n_calls,
        "est_input_tokens": est_input,
        "est_output_tokens": est_output,
        "est_usd": round(est_usd, 4) if est_usd else est_usd,
        "confirm_phrase": None if provider.billing == "free" else CONFIRM_PHRASE,
    }


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

def _create_llm_session(conn: sqlite3.Connection, params: dict,
                        provider_id: str, model: str, passes: int) -> GradingSession:
    axis = params.get("axis", "")
    if axis not in AXIS_FIELDS:
        raise JudgeRequestError(f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")
    comparison_col = AXIS_FIELDS[axis]
    pinned = _pinned_kwargs(params, comparison_col)
    task_id = params.get("task", "")

    trials = list_passing_trials(conn, task_id=task_id, **pinned)
    run_results = {}
    for t in trials:
        rr = get_run_result(conn, t.id)
        if rr is not None:
            run_results[t.id] = rr
    trials = [t for t in trials if t.id in run_results]

    if len({getattr(t, comparison_col) for t in trials}) < 2:
        raise JudgeRequestError(
            "Not enough passing values for this axis in the selected cell")

    trial_pairs = generate_pairs(trials, run_results, axis)
    session = GradingSession(
        id=uuid.uuid4().hex,
        axis=axis,
        cell={"task_id": task_id, **pinned},
        pairs=[(left.id, right.id) for left, right in trial_pairs],
        created_at=datetime.now(timezone.utc).isoformat(),
        mode="llm",
        judge_provider=provider_id,
        judge_model=model,
        judge_passes=passes,
    )
    insert_grading_session(conn, session)
    return session


def start_judge(db_name: str, db_path: Path, params: dict,
                confirm_phrase: str | None) -> JudgeRunHandle:
    conn = connect(Path(db_path))
    try:
        session_id = params.get("session_id")
        if session_id:
            # Resume an existing llm session: unjudged pairs get judged.
            stored = get_grading_session(conn, session_id)
            if stored is None:
                raise JudgeRequestError("Session not found", status=404)
            if stored.mode != "llm":
                raise JudgeRequestError(
                    "Session was graded by a human — the LLM judge must not touch it",
                    status=409,
                )
            if stored.revealed_at is not None:
                raise JudgeRequestError(
                    "Session was revealed and is closed — start a new session "
                    "to judge this cell again",
                    status=409,
                )
            provider_id = stored.judge_provider or params.get("provider", "mock")
            model = stored.judge_model or params.get("judge_model", "")
            passes = stored.judge_passes or _validate_passes(params.get("passes", 2))
            session = stored
        else:
            provider_id = params.get("provider", "claude-cli")
            passes = _validate_passes(params.get("passes", 2))
            try:
                provider_for_defaults = get_provider(provider_id)
            except KeyError as exc:
                raise JudgeRequestError(str(exc))
            model = params.get("judge_model") or provider_for_defaults.default_model()
            session = None  # created after the spend gate below

        try:
            provider = get_provider(provider_id)
        except KeyError as exc:
            raise JudgeRequestError(str(exc))
        if provider.billing != "free" and confirm_phrase != CONFIRM_PHRASE:
            raise JudgeRequestError(
                f"the {provider_id!r} judge spends your {provider.billing} budget — "
                f"repeat the confirmation phrase {CONFIRM_PHRASE!r} to start it",
                status=409,
            )
        available, reason = provider.availability()
        if not available:
            raise JudgeRequestError(f"judge provider {provider_id!r} unavailable: {reason}",
                                    status=409)

        with _lock:
            if any(h.status == "running" for h in _runs.values()):
                raise JudgeRequestError(
                    "another judge run is already in progress — wait for it to finish",
                    status=409,
                )
            if session is None:
                session = _create_llm_session(conn, params, provider_id, model, passes)
            handle = JudgeRunHandle(
                id=uuid.uuid4().hex[:12],
                session_id=session.id,
                db_name=db_name,
                db_path=str(db_path),
                provider=provider_id,
                model=model,
                passes=passes,
                n_pairs=len(session.pairs),
            )
            _runs[handle.id] = handle
    finally:
        conn.close()

    thread = threading.Thread(target=_worker, args=(handle,), daemon=True,
                              name=f"judge-{handle.id}")
    thread.start()
    return handle


def request_cancel(run_id: str) -> bool:
    handle = _runs.get(run_id)
    if handle is None or handle.status != "running":
        return False
    handle.cancel_requested = True
    return True


# ---------------------------------------------------------------------------
# worker
# ---------------------------------------------------------------------------

def _blinding_for_session(conn: sqlite3.Connection, session: GradingSession,
                          pair_trials: dict[str, Trial]) -> dict[str, list[str]]:
    """Same blinding map the human session endpoints build: every passing
    trial in the cell, unioned with the pair trials themselves."""
    from ui.server import _axis_ids_for_blinding  # late import: server imports us

    kwargs = {k: v for k, v in session.cell.items() if k != "task_id"}
    by_id = {t.id: t for t in list_passing_trials(
        conn, task_id=session.cell.get("task_id", ""), **kwargs)}
    for tid, t in pair_trials.items():
        by_id.setdefault(tid, t)
    return _axis_ids_for_blinding(list(by_id.values()))


def _payload(conn: sqlite3.Connection, trial_id: str,
             axis_ids: dict[str, list[str]]) -> dict:
    rr = get_run_result(conn, trial_id)
    if rr is None:
        raise JudgeError(f"trial {trial_id} has no run_result")
    gr = get_gate_result(conn, trial_id)
    gate = None
    if gr is not None:
        # Functional tiers only — the observational tier never reaches a judge
        # (same reasoning as ui.server.GateScorecard).
        gate = {
            "compile_passed": gr.compile_passed,
            "visible_passed": gr.visible_passed,
            "hidden_passed": gr.hidden_passed,
        }
    return {"diff": anonymize_diff(rr.diff, axis_ids), "gate": gate}


def _persist_calls(conn: sqlite3.Connection, session_id: str, pair_index: int,
                   handle: JudgeRunHandle, calls, now: str | None = None) -> None:
    """Write one pair's provider calls to the judge_call audit — successful,
    retried, AND permanently-failed pairs alike (every call was billed)."""
    if now is None:
        now = datetime.now(timezone.utc).isoformat()
    for call in calls:
        insert_judge_call(conn, JudgeCallRecord(
            id=uuid.uuid4().hex,
            session_id=session_id,
            pair_index=pair_index,
            ordering=call.ordering,
            provider=handle.provider,
            model=handle.model,
            status=call.status,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            usd_equiv=call.usd_equiv,
            wall_seconds=call.wall_seconds,
            error=call.error,
            created_at=now,
        ))


def _worker(handle: JudgeRunHandle) -> None:
    conn = connect(Path(handle.db_path))
    try:
        session = get_grading_session(conn, handle.session_id)
        if session is None:
            raise JudgeError("session vanished before judging started")

        task = get_task_spec(conn, session.cell.get("task_id", ""))
        instruction = task.instruction if task else session.cell.get("task_id", "")

        pair_trials: dict[str, Trial] = {}
        for left_id, right_id in session.pairs:
            for tid in (left_id, right_id):
                if tid not in pair_trials:
                    t = get_trial(conn, tid)
                    if t is None:
                        raise JudgeError(f"session references missing trial {tid}")
                    pair_trials[tid] = t

        axis_ids = _blinding_for_session(conn, session, pair_trials)
        forbidden = sorted({sid for ids in axis_ids.values() for sid in ids})
        # The instruction is part of the judge's view, so it gets the same
        # redaction the diffs do — task text that names an axis id (any case)
        # must neither reach the provider nor fail the run as a false alarm.
        instruction = redact_axis_ids(instruction, axis_ids)

        judged = {
            (j.left_trial_id, j.right_trial_id)
            for j in list_judgments(conn, handle.session_id)
        }
        provider = get_provider(handle.provider)
        grader = f"llm:{handle.provider}:{handle.model}"

        for i, (left_id, right_id) in enumerate(session.pairs):
            if handle.cancel_requested:
                handle.status = "cancelled"
                break
            if (left_id, right_id) in judged:
                continue
            # Reveal closes a session permanently; a reveal racing this run
            # must stop it — post-reveal judgments would not be blind.
            current = get_grading_session(conn, handle.session_id)
            if current is not None and current.revealed_at is not None:
                raise JudgeError("session was revealed mid-run — judging stopped")

            left = _payload(conn, left_id, axis_ids)
            right = _payload(conn, right_id, axis_ids)
            try:
                result = run_pair(
                    provider, handle.model, instruction, left, right,
                    passes=handle.passes, forbidden_tokens=forbidden,
                )
            except JudgeError as exc:
                # The pair failed permanently, but its attempts were billed —
                # the audit table records them even though no verdict exists.
                _persist_calls(conn, session.id, i, handle, exc.calls)
                raise

            # Re-check AFTER the provider call too: a reveal can land while
            # the call is in flight (minutes on real providers), and a
            # judgment must never be written into a revealed session. The
            # call itself was billed — keep it in the audit, drop the verdict.
            current = get_grading_session(conn, handle.session_id)
            if current is not None and current.revealed_at is not None:
                _persist_calls(conn, session.id, i, handle, result.calls)
                raise JudgeError(
                    "session was revealed mid-run — judging stopped and the "
                    "in-flight verdict was discarded"
                )

            now = datetime.now(timezone.utc).isoformat()
            rubric = result.verdicts[0].rubric if result.verdicts else {}
            upsert_judgment(conn, Judgment(
                id=uuid.uuid4().hex,
                session_id=session.id,
                task_id=session.cell.get("task_id", ""),
                model=session.cell.get("model", ""),
                left_trial_id=left_id,
                right_trial_id=right_id,
                choice=result.choice,
                rubric_correctness=rubric.get("correctness"),
                rubric_minimality=rubric.get("minimality"),
                rubric_readability=rubric.get("readability"),
                rubric_overengineering=rubric.get("overengineering"),
                created_at=now,
                grader=grader,
                rationale=result.rationale,
                confidence=result.confidence,
                position_consistent=result.position_consistent,
                truncated=result.truncated,
            ))
            _persist_calls(conn, session.id, i, handle, result.calls, now=now)
            handle.events.append({
                "type": "pair",
                "index": i,
                "choice": result.choice,
                "position_consistent": result.position_consistent,
                "truncated": result.truncated,
                "ts": time.time(),
            })
        else:
            if handle.status == "running":
                handle.status = "done"
    except (JudgeError, BlindingError, JudgeProviderError) as e:
        handle.status = "error"
        handle.error = str(e)
        logger.error("Judge run %s failed: %s", handle.id, e)
    except Exception as e:  # pragma: no cover - defensive
        handle.status = "error"
        handle.error = str(e)
        logger.error("Judge run %s crashed: %s", handle.id, e, exc_info=True)
    finally:
        handle.finished_at = time.time()
        conn.close()
        handle.events.append({
            "type": "status", "status": handle.status,
            "error": handle.error, "ts": time.time(),
        })
