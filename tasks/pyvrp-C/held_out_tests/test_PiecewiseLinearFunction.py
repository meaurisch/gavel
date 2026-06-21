import pickle

from numpy.testing import assert_, assert_equal, assert_raises

from pyvrp import PiecewiseLinearFunction


def test_call():
    """
    Tests calling the piecewise linear function on various segments.
    """
    fn = PiecewiseLinearFunction([5, 10, 20], [(1, 2), (11, 3), (26, 4)])

    # 1st segment, defined for values < 5.
    assert_equal(fn(-100), 1 + 2 * -100)
    assert_equal(fn(0), 1 + 2 * 0)
    assert_equal(fn(4), 1 + 2 * 4)

    # 2nd segment, defined for values in [5, 10).
    assert_equal(fn(5), 11 + 3 * 5)
    assert_equal(fn(9), 11 + 3 * 9)

    # 3rd segment, defined for values >= 10.
    assert_equal(fn(10), 26 + 4 * 10)
    assert_equal(fn(13), 26 + 4 * 13)
    assert_equal(fn(100), 26 + 4 * 100)


def test_zero():
    """
    Tests the piecewise linear function with zero slope and/or intercept.
    """
    fn = PiecewiseLinearFunction([0], [(0, 7)])  # zero intercept
    assert_equal(fn(-1), -7)
    assert_equal(fn(0), 0)
    assert_equal(fn(1), 7)

    fn = PiecewiseLinearFunction([0], [(7, 0)])  # zero slope (constant)
    assert_equal(fn(-5), 7)
    assert_equal(fn(0), 7)
    assert_equal(fn(5), 7)

    fn = PiecewiseLinearFunction([0], [(0, 0)])  # all zero
    assert_equal(fn(-100), 0)
    assert_equal(fn(0), 0)
    assert_equal(fn(100), 0)


def test_piecewise_linear_function_raises_inconsisten_argument_sizes():
    """
    Tests that the piecewise linear function cannot be constructed with
    inconsistently sized arguments.
    """
    with assert_raises(ValueError):  # need at least one segment
        PiecewiseLinearFunction([], [])

    with assert_raises(ValueError):  # argument sizes must match
        PiecewiseLinearFunction([0], [])

    with assert_raises(ValueError):  # argument sizes must match
        PiecewiseLinearFunction([], [(0, 0)])

    with assert_raises(ValueError):  # also when both arguments are not empty
        PiecewiseLinearFunction([0, 1, 2], [(0, 0), (0, 0)])


def test_breakpoints_and_segments_properties():
    """
    Tests getting the breakpoints and segments.
    """
    fn = PiecewiseLinearFunction([0, 5], [(1, 2), (11, 3)])
    assert_equal(fn.breakpoints, [0, 5])
    assert_equal(fn.segments, [(1, 2), (11, 3)])


def test_eq():
    """
    Tests equality comparisons between various functions.
    """
    fn1 = PiecewiseLinearFunction([5], [(1, 2)])
    fn2 = PiecewiseLinearFunction([5], [(1, 2)])
    fn3 = PiecewiseLinearFunction([5], [(1, 3)])
    fn4 = PiecewiseLinearFunction([6], [(1, 2)])

    assert_(fn1 == fn2)
    assert_(fn1 != fn3)
    assert_(fn1 != fn4)
    assert_(fn1 != "string")


def test_single_segment():
    """
    Tests a piecewise linear function with a single segment (one breakpoint).
    """
    fn = PiecewiseLinearFunction([0], [(5, 3)])

    # The single segment is f(x) = 5 + 3 * x for all x.
    assert_equal(fn(-10), 5 + 3 * -10)
    assert_equal(fn(-1), 5 + 3 * -1)
    assert_equal(fn(0), 5 + 3 * 0)
    assert_equal(fn(1), 5 + 3 * 1)
    assert_equal(fn(100), 5 + 3 * 100)


def test_many_breakpoints():
    """
    Tests a piecewise linear function with 100 breakpoints, evaluating at
    each breakpoint and between breakpoints for correctness at scale.
    """
    breakpoints = list(range(100))
    segments = [(i, i + 1) for i in range(100)]
    fn = PiecewiseLinearFunction(breakpoints, segments)

    # At breakpoint i (for i < 99) the active segment is i+1, because the
    # breakpoint marks the transition to the next segment.
    for i in range(99):
        bp = breakpoints[i]
        seg_idx = i + 1
        intercept, slope = segments[seg_idx]
        assert_equal(fn(bp), intercept + slope * bp)

    # At the last breakpoint (99), uses segment 99.
    assert_equal(fn(99), segments[99][0] + segments[99][1] * 99)

    # Evaluate before the first breakpoint (uses segment 0).
    assert_equal(fn(-5), segments[0][0] + segments[0][1] * -5)

    # Evaluate after the last breakpoint (uses segment 99).
    assert_equal(fn(200), segments[99][0] + segments[99][1] * 200)


def test_pickle_roundtrip():
    """
    Tests that a PiecewiseLinearFunction survives a pickle roundtrip.
    """
    fn = PiecewiseLinearFunction([5, 10], [(1, 2), (11, 3)])
    data = pickle.dumps(fn)
    fn2 = pickle.loads(data)
    assert_(fn == fn2)
    assert_equal(fn2(7), 11 + 3 * 7)


def test_negative_breakpoints():
    """
    Tests a piecewise linear function with negative breakpoints, evaluating
    at negative values.
    """
    fn = PiecewiseLinearFunction(
        [-10, -5, 0, 5],
        [(1, 1), (2, 2), (3, 3), (4, 4)],
    )

    # Before first breakpoint (-10): segment 0 => 1 + 1 * x
    assert_equal(fn(-20), 1 + 1 * -20)
    assert_equal(fn(-11), 1 + 1 * -11)

    # At first breakpoint: segment 1 => 2 + 2 * x
    assert_equal(fn(-10), 2 + 2 * -10)
    assert_equal(fn(-7), 2 + 2 * -7)

    # At second breakpoint: segment 2 => 3 + 3 * x
    assert_equal(fn(-5), 3 + 3 * -5)
    assert_equal(fn(-3), 3 + 3 * -3)

    # At third breakpoint (0): segment 3 => 4 + 4 * x
    assert_equal(fn(0), 4 + 4 * 0)
    assert_equal(fn(3), 4 + 4 * 3)

    # At fourth breakpoint (5) and beyond: still segment 3 (last)
    assert_equal(fn(5), 4 + 4 * 5)
    assert_equal(fn(100), 4 + 4 * 100)


def test_raises_unsorted_breakpoints():
    """
    Tests that the piecewise linear function cannot be constructed with
    unsorted breakpoints, or breakpoints that are not strictly increasing.
    """
    with assert_raises(ValueError):  # unsorted
        PiecewiseLinearFunction([2, 1, 3], [(1, 1), (2, 2), (3, 3)])

    with assert_raises(ValueError):  # not strictly increasing
        PiecewiseLinearFunction([1, 1], [(1, 1), (2, 2)])
