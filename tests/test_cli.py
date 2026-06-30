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
