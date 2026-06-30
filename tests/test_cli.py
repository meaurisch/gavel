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
