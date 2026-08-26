"""Tests for cli module UTF-8 forcing behaviour."""


class _FakeStream:
    def __init__(self, encoding: str):
        self.encoding = encoding
        self._calls: list[dict] = []

    def reconfigure(self, **kwargs):
        self._calls.append(kwargs)


def test_force_utf8_reconfigures_cp1252_stream():
    from cli import _force_utf8

    stream = _FakeStream("cp1252")
    _force_utf8([stream])
    assert stream._calls == [{"encoding": "utf-8"}]


def test_force_utf8_leaves_utf8_stream_untouched():
    from cli import _force_utf8

    stream = _FakeStream("utf-8")
    _force_utf8([stream])
    assert stream._calls == []


def test_force_utf8_ignores_stream_without_reconfigure():
    from cli import _force_utf8

    class _NoReconfigure:
        encoding = "cp1252"

    # Must not raise
    _force_utf8([_NoReconfigure()])


def test_summarize_includes_errored_but_billed_cost():
    from cli import _summarize

    # Regression: an errored trial with real billed cost must count toward
    # total_usd but not toward passed/failed.
    results = {
        "t1": {"passed": None, "usd": 0.12, "tokens": 9000, "wall_seconds": 30.0,
               "error": "agent produced an empty diff (no changes)"},
    }
    passed, failed, errors, total_usd = _summarize(results)
    assert (passed, failed, errors) == (0, 0, 1)
    assert total_usd == 0.12


def test_summarize_excludes_skipped_from_everything():
    from cli import _summarize

    results = {"t1": {"skipped": True}}
    passed, failed, errors, total_usd = _summarize(results)
    assert (passed, failed, errors, total_usd) == (0, 0, 0, 0.0)


def test_summarize_normal_pass_fail_unchanged():
    from cli import _summarize

    results = {
        "t1": {"passed": True, "usd": 0.10, "tokens": 100, "wall_seconds": 5.0, "error": None},
        "t2": {"passed": False, "usd": 0.20, "tokens": 200, "wall_seconds": 6.0, "error": None},
    }
    passed, failed, errors, total_usd = _summarize(results)
    assert (passed, failed, errors) == (1, 1, 0)
    assert abs(total_usd - 0.30) < 1e-9


def test_progress_table_trial_column_is_compact():
    from core.models import Trial
    from cli import _progress_table

    trial = Trial(
        id="task-foo__baseline__none__claude-sonnet-4-6__r1",
        task_id="task-foo",
        methodology_id="baseline",
        repo_context_id="none",
        model="claude-sonnet-4-6",
        runner="claude-code",
        rep=1,
    )
    table = _progress_table([trial], {})
    # First column header
    assert table.columns[0].header == "Trial"
    # Cell text should be compact label, not the full id
    cell_text = table.columns[0]._cells[0]
    assert cell_text == f"{trial.task_id} #{trial.rep}"


def test_run_splits_comma_separated_axis_lists(tmp_path):
    """--task/--methodology/--repo-context accept comma-separated ids, like
    --model always has (regression: a comma list used to be treated as one
    nonexistent id and filtered the whole grid away)."""
    from typer.testing import CliRunner

    from cli import app

    # `custom`, not `karpathy`: vendored packs (methodologies/**/vendor/) are
    # gitignored, so on a clean clone karpathy is unusable until `cli.py setup`
    # vendors it — and the default suite must stay green on a clean clone.
    runner = CliRunner()
    result = runner.invoke(app, [
        "run", "--task", "cosmos-A,cosmos-B",
        "--methodology", "baseline,custom",
        "--repo-context", "none",
        "--model", "m1", "--runner", "nop", "--reps", "1",
        "--db", str(tmp_path / "t.db"), "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "4 trials = 2 tasks x 2 methodologies" in result.output


def test_run_paid_runner_refuses_without_confirmation(tmp_path):
    """CLI parity with the browser launcher's SPEND gate: a paid runner
    (claude-code) must not start spending without an explicit confirmation.
    CliRunner's stdin isn't a tty, so this exercises the non-interactive
    refusal path — must exit before execute_all is ever called."""
    from typer.testing import CliRunner

    import cli

    called = False

    def _fake_execute_all(*args, **kwargs):
        nonlocal called
        called = True
        return []

    cli.execute_all = _fake_execute_all

    runner = CliRunner()
    result = runner.invoke(cli.app, [
        "run", "--task", "cosmos-A",
        "--methodology", "baseline",
        "--repo-context", "none",
        "--model", "m1", "--runner", "claude-code", "--reps", "1",
        "--db", str(tmp_path / "t.db"),
    ])
    assert result.exit_code == 2, result.output
    assert "--yes" in result.output
    assert not called


def test_run_paid_runner_yes_flag_skips_confirmation(tmp_path):
    """--yes lets scripted/CI runs bypass the interactive spend confirmation."""
    from typer.testing import CliRunner

    import cli

    called = False

    def _fake_execute_all(*args, **kwargs):
        nonlocal called
        called = True
        return []

    cli.execute_all = _fake_execute_all

    runner = CliRunner()
    result = runner.invoke(cli.app, [
        "run", "--task", "cosmos-A",
        "--methodology", "baseline",
        "--repo-context", "none",
        "--model", "m1", "--runner", "claude-code", "--reps", "1",
        "--db", str(tmp_path / "t.db"), "--yes",
    ])
    assert result.exit_code == 0, result.output
    assert called


def test_run_free_runner_never_prompts(tmp_path):
    """Free runners (nop/oracle) start unconditionally, --yes or not."""
    from typer.testing import CliRunner

    import cli

    called = False

    def _fake_execute_all(*args, **kwargs):
        nonlocal called
        called = True
        return []

    cli.execute_all = _fake_execute_all

    runner = CliRunner()
    result = runner.invoke(cli.app, [
        "run", "--task", "cosmos-A",
        "--methodology", "baseline",
        "--repo-context", "none",
        "--model", "m1", "--runner", "nop", "--reps", "1",
        "--db", str(tmp_path / "t.db"),
    ])
    assert result.exit_code == 0, result.output
    assert called
