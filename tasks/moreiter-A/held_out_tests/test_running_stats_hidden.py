"""Held-out tests for the running-aggregates feature (moreiter-A).

Strengthened beyond the reference implementation's own tests: brute-force
window oracles across many window sizes, exactness on Fraction/Decimal,
laziness on pure iterators, eager window-size validation, and the Stats
contract (field values, ordering, frozenness).
"""

from decimal import Decimal
from fractions import Fraction
from statistics import mean as stat_mean, median as stat_median

import dataclasses
import itertools
import pytest

from more_itertools import (
    Stats,
    running_max,
    running_mean,
    running_min,
    running_statistics,
)


SEQ = [4, 3, 7, 0, 8, 1, 6, 2, 9, 5]
TIES = [5, 5, 1, 5, 1, 1, 3, 3, 5, 1]


def brute_window(seq, i, maxlen):
    if maxlen is None:
        return seq[: i + 1]
    return seq[max(0, i + 1 - maxlen) : i + 1]


# ---------------------------------------------------------------- min / max

@pytest.mark.parametrize("seq", [SEQ, TIES, [2], [-1, -1, -1], [3, 1]])
@pytest.mark.parametrize("maxlen", [None, 1, 2, 3, 5, 100])
def test_running_min_matches_bruteforce(seq, maxlen):
    expected = [min(brute_window(seq, i, maxlen)) for i in range(len(seq))]
    assert list(running_min(seq, maxlen=maxlen)) == expected


@pytest.mark.parametrize("seq", [SEQ, TIES, [2], [-1, -1, -1], [3, 1]])
@pytest.mark.parametrize("maxlen", [None, 1, 2, 3, 5, 100])
def test_running_max_matches_bruteforce(seq, maxlen):
    expected = [max(brute_window(seq, i, maxlen)) for i in range(len(seq))]
    assert list(running_max(seq, maxlen=maxlen)) == expected


def test_running_min_max_empty():
    assert list(running_min([])) == []
    assert list(running_max([], maxlen=3)) == []


def test_running_min_max_exact_types_preserved():
    values = [Fraction(1, 3), Fraction(1, 2), Fraction(1, 4)]
    out = list(running_min(values, maxlen=2))
    assert out == [Fraction(1, 3), Fraction(1, 3), Fraction(1, 4)]
    assert all(isinstance(v, Fraction) for v in out)

    dec = [Decimal("2.5"), Decimal("1.5"), Decimal("3.5")]
    assert list(running_max(dec)) == [Decimal("2.5"), Decimal("2.5"), Decimal("3.5")]


def test_running_min_max_consume_iterators_lazily():
    # Works on a single-pass iterator, and doesn't require it to be sized.
    it = iter(SEQ)
    out = running_min(it, maxlen=3)
    assert next(out) == 4
    assert next(out) == 3


@pytest.mark.parametrize("fn", [running_min, running_max, running_mean])
@pytest.mark.parametrize("bad", [0, -1, -100])
def test_window_size_validated_eagerly(fn, bad):
    # The error must surface at call time, not on first iteration.
    with pytest.raises(ValueError):
        fn(iter(SEQ), maxlen=bad)


# ---------------------------------------------------------------- mean

@pytest.mark.parametrize("maxlen", [None, 1, 3, 4, 100])
def test_running_mean_matches_bruteforce(maxlen):
    expected = [
        stat_mean(brute_window(SEQ, i, maxlen)) for i in range(len(SEQ))
    ]
    got = list(running_mean(SEQ, maxlen=maxlen))
    assert got == pytest.approx(expected)


def test_running_mean_unbounded_still_works_like_before():
    # The pre-existing no-window behaviour must be unchanged.
    assert list(running_mean([100, 200, 600])) == [100.0, 150.0, 300.0]


# ---------------------------------------------------------------- statistics

def test_stats_is_a_frozen_dataclass_with_named_fields():
    (first,) = itertools.islice(running_statistics([7]), 1)
    assert isinstance(first, Stats)
    assert (first.size, first.minimum, first.median, first.maximum) == (1, 7, 7, 7)
    assert first.mean == pytest.approx(7.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.size = 2


@pytest.mark.parametrize("maxlen", [None, 1, 3, 100])
def test_running_statistics_matches_bruteforce(maxlen):
    got = list(running_statistics(SEQ, maxlen=maxlen))
    assert len(got) == len(SEQ)
    for i, s in enumerate(got):
        window = brute_window(SEQ, i, maxlen)
        assert s.size == len(window)
        assert s.minimum == min(window)
        assert s.maximum == max(window)
        assert s.median == stat_median(window)
        assert s.mean == pytest.approx(stat_mean(window))


def test_running_statistics_empty_and_iterator_input():
    assert list(running_statistics(iter([]))) == []
    got = list(running_statistics(iter([3, 1]), maxlen=2))
    assert [s.size for s in got] == [1, 2]
    assert got[1].minimum == 1 and got[1].maximum == 3


def test_running_statistics_rejects_bad_window_eagerly():
    with pytest.raises(ValueError):
        running_statistics(iter(SEQ), maxlen=0)


# ---------------------------------------------------------------- exports

def test_public_api_exports():
    import more_itertools

    for name in ("running_min", "running_max", "running_statistics", "Stats"):
        assert hasattr(more_itertools, name), f"{name} not exported from the package"
