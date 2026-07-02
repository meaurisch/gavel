"""Seed a self-contained DEMO results database.

`python cli.py demo` builds a small, deterministic, clearly-synthetic dataset
so the grading UI and the report command can be tried in minutes, with zero
API spend and no repos cloned:

- one task (`demo-lru-cache`), four methodologies in distinct coding styles,
  three reps each — realistic Python diffs, three-tier gate scorecards, and
  costs;
- a second model (`demo-model-m`) on the baseline methodology, so the model
  axis is gradeable too;
- one pre-graded session on the methodology axis, so `cli.py report
  --db results-demo.db` tells the full ranking/frontier story immediately.

Every id is prefixed `demo-` so this data can never be mistaken for a real
measurement.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.db import (
    connect,
    insert_cost_record,
    insert_gate_result,
    insert_grading_session,
    insert_judgment,
    insert_run_result,
    insert_trial,
)
from core.models import CostRecord, GateResult, GradingSession, Judgment, RunResult, Trial

TASK = "demo-lru-cache"
CTX = "none"
RUNNER = "demo-runner"
MODEL_S = "demo-model-s"
MODEL_M = "demo-model-m"

# value -> (style blurb used in the diff, mean cost, [gate pass per rep])
METHODOLOGIES = {
    "demo-baseline": (0.05, [True, False, True]),
    "demo-checklist": (0.09, [True, True, True]),
    "demo-tdd": (0.16, [True, True, True]),
    "demo-agentpack": (0.62, [True, True, False]),
}


def _diff(methodology: str, rep: int) -> str:
    """A plausible unified diff; body varies by methodology so blind A/B has
    something to compare, and lightly by rep so reps aren't byte-identical."""
    impls = {
        "demo-baseline": (
            "+class LRUCache:\n"
            "+    def __init__(self, capacity):\n"
            "+        self.capacity = capacity\n"
            "+        self.data = {}\n"
            "+        self.order = []\n"
            "+\n"
            "+    def get(self, key):\n"
            "+        if key not in self.data:\n"
            "+            return None\n"
            "+        self.order.remove(key)\n"
            "+        self.order.append(key)\n"
            "+        return self.data[key]\n"
            "+\n"
            "+    def put(self, key, value):\n"
            "+        if key in self.data:\n"
            "+            self.order.remove(key)\n"
            "+        elif len(self.data) >= self.capacity:\n"
            "+            oldest = self.order.pop(0)\n"
            "+            del self.data[oldest]\n"
            "+        self.data[key] = value\n"
            "+        self.order.append(key)\n"
        ),
        "demo-checklist": (
            "+from collections import OrderedDict\n"
            "+\n"
            "+\n"
            "+class LRUCache:\n"
            "+    \"\"\"LRU cache backed by OrderedDict.\"\"\"\n"
            "+\n"
            "+    def __init__(self, capacity: int) -> None:\n"
            "+        if capacity <= 0:\n"
            "+            raise ValueError(\"capacity must be positive\")\n"
            "+        self._capacity = capacity\n"
            "+        self._items: OrderedDict = OrderedDict()\n"
            "+\n"
            "+    def get(self, key):\n"
            "+        if key not in self._items:\n"
            "+            return None\n"
            "+        self._items.move_to_end(key)\n"
            "+        return self._items[key]\n"
            "+\n"
            "+    def put(self, key, value) -> None:\n"
            "+        if key in self._items:\n"
            "+            self._items.move_to_end(key)\n"
            "+        self._items[key] = value\n"
            "+        if len(self._items) > self._capacity:\n"
            "+            self._items.popitem(last=False)\n"
        ),
        "demo-tdd": (
            "+from collections import OrderedDict\n"
            "+\n"
            "+\n"
            "+class LRUCache:\n"
            "+    \"\"\"LRU cache with O(1) get/put and eviction callbacks.\"\"\"\n"
            "+\n"
            "+    def __init__(self, capacity: int, on_evict=None) -> None:\n"
            "+        if capacity <= 0:\n"
            "+            raise ValueError(f\"capacity must be positive, got {capacity}\")\n"
            "+        self._capacity = capacity\n"
            "+        self._items: OrderedDict = OrderedDict()\n"
            "+        self._on_evict = on_evict\n"
            "+\n"
            "+    def get(self, key, default=None):\n"
            "+        try:\n"
            "+            self._items.move_to_end(key)\n"
            "+        except KeyError:\n"
            "+            return default\n"
            "+        return self._items[key]\n"
            "+\n"
            "+    def put(self, key, value) -> None:\n"
            "+        if key in self._items:\n"
            "+            self._items.move_to_end(key)\n"
            "+        self._items[key] = value\n"
            "+        if len(self._items) > self._capacity:\n"
            "+            evicted_key, evicted_value = self._items.popitem(last=False)\n"
            "+            if self._on_evict is not None:\n"
            "+                self._on_evict(evicted_key, evicted_value)\n"
        ),
        "demo-agentpack": (
            "+from dataclasses import dataclass\n"
            "+from typing import Any, Optional\n"
            "+\n"
            "+\n"
            "+@dataclass\n"
            "+class _Node:\n"
            "+    key: Any\n"
            "+    value: Any\n"
            "+    prev: \"Optional[_Node]\" = None\n"
            "+    next: \"Optional[_Node]\" = None\n"
            "+\n"
            "+\n"
            "+class LRUCache:\n"
            "+    \"\"\"Doubly-linked-list LRU cache (hand-rolled for O(1) ops).\"\"\"\n"
            "+\n"
            "+    def __init__(self, capacity: int) -> None:\n"
            "+        self._capacity = capacity\n"
            "+        self._map: dict = {}\n"
            "+        self._head: Optional[_Node] = None\n"
            "+        self._tail: Optional[_Node] = None\n"
            "+\n"
            "+    def _unlink(self, node: _Node) -> None:\n"
            "+        if node.prev: node.prev.next = node.next\n"
            "+        if node.next: node.next.prev = node.prev\n"
            "+        if self._head is node: self._head = node.next\n"
            "+        if self._tail is node: self._tail = node.prev\n"
            "+\n"
            "+    def _push_back(self, node: _Node) -> None:\n"
            "+        node.prev, node.next = self._tail, None\n"
            "+        if self._tail: self._tail.next = node\n"
            "+        self._tail = node\n"
            "+        if self._head is None: self._head = node\n"
            "+\n"
            "+    def get(self, key):\n"
            "+        node = self._map.get(key)\n"
            "+        if node is None:\n"
            "+            return None\n"
            "+        self._unlink(node); self._push_back(node)\n"
            "+        return node.value\n"
            "+\n"
            "+    def put(self, key, value) -> None:\n"
            "+        node = self._map.get(key)\n"
            "+        if node is not None:\n"
            "+            node.value = value\n"
            "+            self._unlink(node); self._push_back(node)\n"
            "+            return\n"
            "+        node = _Node(key, value)\n"
            "+        self._map[key] = node\n"
            "+        self._push_back(node)\n"
            "+        if len(self._map) > self._capacity:\n"
            "+            oldest = self._head\n"
            "+            self._unlink(oldest)\n"
            "+            del self._map[oldest.key]\n"
        ),
    }
    body = impls[methodology]
    n = body.count("\n")
    return (
        f"diff --git a/lru_cache.py b/lru_cache.py\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/lru_cache.py\n"
        f"@@ -0,0 +1,{n + 1} @@\n"
        f"+# rev {rep + 1}\n"
        + body
    )


def _trial_id(methodology: str, model: str, rep: int) -> str:
    return f"{TASK}__{methodology}__{CTX}__{model}__r{rep}"


def seed_demo(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)

    def add_trial(methodology: str, model: str, rep: int, passed: bool, usd: float):
        tid = _trial_id(methodology, model, rep)
        insert_trial(conn, Trial(
            id=tid, task_id=TASK, methodology_id=methodology,
            repo_context_id=CTX, model=model, runner=RUNNER, rep=rep,
        ))
        insert_run_result(conn, RunResult(
            trial_id=tid, diff=_diff(methodology, rep), exit_status=0,
            wall_seconds=30.0 + 20.0 * rep + len(methodology),
        ))
        insert_gate_result(conn, GateResult(
            trial_id=tid, passed=passed,
            compile_passed=True,
            visible_passed=True if passed else rep % 2 == 0,
            hidden_passed=passed,
            hidden_output="demo",
        ))
        insert_cost_record(conn, CostRecord(
            trial_id=tid, native_unit="usd", native_amount=usd, usd_equiv=usd,
            input_tokens=int(usd * 40_000), output_tokens=int(usd * 9_000),
            cache_read_tokens=int(usd * 100_000),
        ))
        return tid

    passers: dict[str, list[str]] = {}
    for methodology, (mean_usd, gate_pattern) in METHODOLOGIES.items():
        for rep, passed in enumerate(gate_pattern):
            usd = round(mean_usd * (1.0 + 0.12 * (rep - 1)), 4)
            tid = add_trial(methodology, MODEL_S, rep, passed, usd)
            if passed:
                passers.setdefault(methodology, []).append(tid)

    # Second model on the baseline methodology -> the model axis is gradeable.
    for rep in range(3):
        add_trial("demo-baseline", MODEL_M, rep, True, round(0.21 * (1.0 + 0.1 * rep), 4))

    # Pre-graded methodology-axis session: demo-tdd > demo-checklist >
    # demo-agentpack > demo-baseline, with one upset and one tie for realism.
    order = ["demo-tdd", "demo-checklist", "demo-agentpack", "demo-baseline"]
    pairs: list[tuple[str, str]] = []
    choices: list[str] = []
    for i, stronger in enumerate(order):
        for weaker in order[i + 1:]:
            for k in range(min(len(passers[stronger]), len(passers[weaker]))):
                pairs.append((passers[stronger][k], passers[weaker][k]))
                choices.append("A")
    if len(choices) >= 6:
        choices[3] = "B"     # one upset
        choices[5] = "tie"   # one tie

    session_id = "demo-pregraded-session"
    insert_grading_session(conn, GradingSession(
        id=session_id, axis="methodology",
        cell={"task_id": TASK, "repo_context_id": CTX, "model": MODEL_S, "runner": RUNNER},
        pairs=pairs, created_at="2026-07-02T00:00:00+00:00",
    ))
    for i, ((left, right), choice) in enumerate(zip(pairs, choices)):
        insert_judgment(conn, Judgment(
            id=f"demo-judgment-{i}", session_id=session_id, task_id=TASK, model=MODEL_S,
            left_trial_id=left, right_trial_id=right, choice=choice,
            rubric_correctness=None, rubric_minimality=None,
            rubric_readability=None, rubric_overengineering=None,
            created_at="2026-07-02T00:00:00+00:00",
        ))

    return conn
