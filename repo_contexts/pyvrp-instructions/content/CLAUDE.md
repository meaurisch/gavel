# PyVRP — repo context

A state-of-the-art vehicle routing problem (VRP) solver. The core algorithm is
implemented in C++20 and exposed to Python through pybind11 bindings. The Python
layer provides the model interface, I/O, and the top-level `solve()` API.
Version: `0.14.0a0`. Build system: **Meson** (via `meson.build` at the repo root).

## Layout

- `pyvrp/cpp/` — all C++ source. Files at this level build into the `_pyvrp`
  extension module (exposed as the top-level `pyvrp` package). The
  `pyvrp/cpp/search/` subdirectory builds into the `_search` extension module
  (exposed as `pyvrp.search`).
- `pyvrp/cpp/bindings.cpp` and `pyvrp/cpp/search/bindings.cpp` — pybind11
  entry points for each extension module.
- `pyvrp/` (Python) — `__init__.py` re-exports from `_pyvrp`; `search/__init__.py`
  re-exports from `_search` and defines the `OPERATORS` list.
- `pyvrp/cpp/search/LocalSearchOperator.h` — base templates `BinaryOperator`
  and `UnaryOperator` (added in pyvrp-B); concrete operators inherit from one of
  these and implement `evaluate()` / `apply()`.
- `tests/` — pytest test suite. Test files for operators live in
  `tests/search/` (e.g. `test_RemoveOptional.py`, `test_ReplaceGroup.py`).

## Conventions

- **C++ standard:** C++20. All headers in `pyvrp/cpp/` are included via the
  `INCLUDES = include_directories('pyvrp/cpp')` Meson variable — use angle
  brackets from that root (e.g. `#include "search/LocalSearchOperator.h"`).
- **New search operator pattern** — for a new operator `Foo`:
  1. Add `pyvrp/cpp/search/Foo.h` and `pyvrp/cpp/search/Foo.cpp`.
  2. Register `Foo.cpp` in the `libsearch` static library in `meson.build`.
  3. Bind it in `pyvrp/cpp/search/bindings.cpp` (follow the pattern of existing
     operators; add a `py::class_<Foo, BinaryOperator>` or `UnaryOperator`).
  4. Export it in `pyvrp/search/__init__.py` (add to the imports and to the
     `OPERATORS` list if appropriate).
- **ProblemData** is the central data object; `CostEvaluator` computes move
  costs. Both are passed by const reference to operator constructors.
- **LocalSearch** registers operators; `UnaryOperator` subclasses are applied
  via a separate unary-operator pass distinct from binary operators.
- **No `PYVRP_` prefixed symbols** and no `pyvrp` namespace — reserved for
  library internals.
- Tests use pytest and are in `tests/`. Run with a plain `pytest` call from the
  repo root (after `pip install -e .`).

## Build / test

The build requires a Linux/WSL environment (Meson + Ninja + a C++20 compiler).
On Windows, run commands inside WSL:

```
# Install (editable) — compiles the C++ extension under WSL
pip install -e . 2>&1

# Run the full test suite
pytest tests/

# Run a specific task's test file
pytest tests/search/test_ReplaceGroup.py -v
```

Do not attempt to build the C++ extensions directly on Windows — use WSL.
