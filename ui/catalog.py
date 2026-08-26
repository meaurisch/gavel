"""Catalog: everything the picker, dashboard, and run launcher show about the
five axes — descriptions, task instructions, pricing, per-id trial counts.

Nothing here is blind: the catalog is only served OUTSIDE an active grading
pair (picker / dashboard / launcher screens). Blinding starts when a session
serves diffs — see ui.server.
"""

from __future__ import annotations

import logging
import sqlite3

from core.methodology_loader import METHODOLOGIES_DIR, list_methodologies, load_manifest
from core.repo_context_loader import REPO_CONTEXTS_DIR, list_repo_contexts
from core.task_loader import list_tasks, load_task

logger = logging.getLogger(__name__)

# Static runner registry: which runners exist, what they cost, and whether the
# browser run-launcher may start them. `manual` blocks on terminal stdin and
# `copilot-cli` is an unimplemented stub — both stay visible (so the axis is
# explained) but not launchable.
RUNNERS = [
    {
        "id": "claude-code",
        "paid": True,
        "browser_launchable": True,
        "description": "Headless Claude Code CLI — runs the real agent. Spends real API budget on every trial.",
    },
    {
        "id": "oracle",
        "paid": False,
        "browser_launchable": True,
        "description": "Applies the task's reference diff — free pipeline self-test that should pass the gate.",
    },
    {
        "id": "nop",
        "paid": False,
        "browser_launchable": True,
        "description": "Does nothing — free pipeline self-test that should fail the gate.",
    },
    {
        "id": "manual",
        "paid": False,
        "browser_launchable": False,
        "description": "Human-in-IDE: the tool prepares the worktree and waits at the terminal. "
                       "Launch with: python cli.py run --runner manual (needs interactive stdin).",
    },
    {
        "id": "copilot-cli",
        "paid": True,
        "browser_launchable": False,
        "description": "Stub — Copilot support is deferred (no plan on hand). Not runnable.",
    },
]


def _axis_counts(conn: sqlite3.Connection, column: str) -> dict[str, dict[str, int]]:
    """Per-id trial and hidden-gate-passer counts from one DB."""
    rows = conn.execute(
        f"""SELECT t.{column} AS id,
                   COUNT(*) AS n_trials,
                   SUM(CASE WHEN g.passed = 1 THEN 1 ELSE 0 END) AS n_passers
            FROM trial t LEFT JOIN gate_result g ON g.trial_id = t.id
            GROUP BY t.{column}"""
    ).fetchall()
    return {r["id"]: {"n_trials": r["n_trials"], "n_passers": r["n_passers"] or 0} for r in rows}


def _task_entries(conn: sqlite3.Connection) -> list[dict]:
    counts = _axis_counts(conn, "task_id")
    entries = []
    for task_id in sorted(set(list_tasks()) | set(counts)):
        entry: dict = {
            "id": task_id,
            "available_locally": False,
            "instruction": None,
            "difficulty": None,
            "repo": None,
            "build_cmd": None,
            "run_cmd": None,
            "visible_test_cmd": None,
            "observe_cmd": None,
            **counts.get(task_id, {"n_trials": 0, "n_passers": 0}),
        }
        try:
            task = load_task(task_id)
            entry.update(
                available_locally=True,
                instruction=task.instruction,
                difficulty=task.difficulty,
                repo=task.repo or task.repo_url.rstrip("/").split("/")[-1].lower(),
                build_cmd=task.build_cmd,
                run_cmd=task.run_cmd,
                visible_test_cmd=task.visible_test_cmd,
                observe_cmd=task.observe_cmd,
            )
        except Exception:
            pass  # DB-only id (e.g. demo data) — counts still shown
        entries.append(entry)
    return entries


def _spec_entries(conn: sqlite3.Connection, column: str, list_ids, specs_dir) -> list[dict]:
    counts = _axis_counts(conn, column)
    entries = []
    for spec_id in sorted(set(list_ids()) | set(counts)):
        entry: dict = {
            "id": spec_id,
            "available_locally": False,
            "description": None,
            "noop": False,
            "source": None,
            "harnesses": {},
            "task_affinity": [],
            **counts.get(spec_id, {"n_trials": 0, "n_passers": 0}),
        }
        try:
            manifest = load_manifest(spec_id, specs_dir)
            entry.update(
                available_locally=True,
                description=manifest.description,
                noop=manifest.noop,
                source={"repo": manifest.source.repo, "commit": manifest.source.commit} if manifest.source else None,
                harnesses={h: [m.dest for m in mappings] for h, mappings in manifest.harnesses.items()},
                task_affinity=manifest.task_affinity,
            )
        except Exception:
            pass
        entries.append(entry)
    return entries


def _model_entries(conn: sqlite3.Connection) -> tuple[list[dict], dict[str, str]]:
    counts = _axis_counts(conn, "model")
    pricing: dict = {}
    aliases: dict[str, str] = {}
    try:
        from cost.pricing import load_pricing
        pricing, aliases = load_pricing()
    except Exception as e:
        logger.warning("pricing table unavailable for catalog: %s", e)

    entries = []
    for model_id in sorted(set(counts) | set(pricing)):
        p = pricing.get(model_id) or pricing.get(aliases.get(model_id, ""))
        entries.append({
            "id": model_id,
            "pricing": {
                "vendor": p.vendor,
                "input_per_mtok": p.input_per_mtok,
                "output_per_mtok": p.output_per_mtok,
                "cache_read_per_mtok": p.cache_read_per_mtok,
            } if p else None,
            **counts.get(model_id, {"n_trials": 0, "n_passers": 0}),
        })
    return entries, aliases


def build_catalog(conn: sqlite3.Connection) -> dict:
    models, aliases = _model_entries(conn)
    runner_counts = _axis_counts(conn, "runner")
    runners = [
        {**r, **runner_counts.get(r["id"], {"n_trials": 0, "n_passers": 0})}
        for r in RUNNERS
    ] + [
        # DB-only runner ids (e.g. demo-runner) still need to appear.
        {"id": rid, "paid": False, "browser_launchable": False,
         "description": "Unknown runner id (present in this DB only).", **c}
        for rid, c in sorted(runner_counts.items())
        if rid not in {r["id"] for r in RUNNERS}
    ]
    return {
        "tasks": _task_entries(conn),
        "methodologies": _spec_entries(conn, "methodology_id", list_methodologies, METHODOLOGIES_DIR),
        "repo_contexts": _spec_entries(conn, "repo_context_id", list_repo_contexts, REPO_CONTEXTS_DIR),
        "models": models,
        "model_aliases": aliases,
        "runners": runners,
    }
