"""
Held-out tests for the ReplaceGroup operator (pyvrp-A).

This task is intentionally UNDER-SPECIFIED: the ticket fixes the *contract*
(swap the visited member of a mutually-exclusive group for a cheaper member of
the same group, when that reduces cost) but leaves the search strategy open.
These tests therefore assert only that contract, and recompute expected cost
deltas from the instance data rather than hard-coding magic numbers, so any
reasonable implementation passes.
"""

from numpy.testing import assert_, assert_equal

from pyvrp import CostEvaluator
from pyvrp import Solution as PyVRPSolution
from pyvrp.search import ReplaceGroup
from pyvrp.search._search import Node, Solution


def test_replacegroup_importable_from_search_module():
    """
    ReplaceGroup is exported from pyvrp.search and follows the operator
    protocol (evaluate/apply/init/supports).
    """
    from pyvrp.search import ReplaceGroup as RG

    assert_(hasattr(RG, "evaluate"))
    assert_(hasattr(RG, "apply"))
    assert_(hasattr(RG, "init"))
    assert_(hasattr(RG, "supports"))


def test_supports(
    gtsp,
    ok_small,
    ok_small_prizes,
    ok_small_mutually_exclusive_groups,
):
    """
    ReplaceGroup applies exactly to instances that have client groups, and to
    no others.
    """
    assert_(ReplaceGroup.supports(gtsp))
    assert_(ReplaceGroup.supports(ok_small_mutually_exclusive_groups))
    assert_(not ReplaceGroup.supports(ok_small))
    assert_(not ReplaceGroup.supports(ok_small_prizes))


def test_improving_replacement_matches_data_delta(
    ok_small_mutually_exclusive_groups,
):
    """
    With member 1 of the group routed, evaluating a cheaper same-group member
    must report an improving move whose delta equals the true distance delta of
    the swap (depot -> U -> 4 in place of depot -> 1 -> 4). The expected value
    is recomputed from the distance matrix, not hard-coded, so any correct
    cost evaluation passes regardless of search strategy.
    """
    data = ok_small_mutually_exclusive_groups
    cost_eval = CostEvaluator([0], 0, 0)  # pure distance
    dist = data.distance_matrix(0)

    sol = Solution(data)
    sol.load(PyVRPSolution(data, [[1, 4]]))
    assert_equal(str(sol.routes[0]), "1 4")

    op = ReplaceGroup(data)
    op.init(sol)

    # The group is {1, 2, 3}; member 1 is routed. Swapping in either 2 or 3
    # replaces arcs (0,1) and (1,4) with (0,U) and (U,4). Keep the candidate
    # nodes alive for the duration of the evaluation.
    for candidate in (2, 3):
        node = Node(loc=candidate)
        expected = (
            dist[0][candidate]
            + dist[candidate][4]
            - dist[0][1]
            - dist[1][4]
        )
        delta, improving = op.evaluate(node, cost_eval)
        assert_equal(delta, expected)
        assert_equal(improving, expected < 0)


def test_apply_replaces_member_and_lowers_cost(
    ok_small_mutually_exclusive_groups,
):
    """
    Applying an improving replacement actually swaps the routed member for the
    candidate and strictly lowers the solution's penalised cost.
    """
    data = ok_small_mutually_exclusive_groups
    cost_eval = CostEvaluator([0], 0, 0)
    dist = data.distance_matrix(0)

    sol = Solution(data)
    sol.load(PyVRPSolution(data, [[1, 4]]))

    op = ReplaceGroup(data)
    op.init(sol)

    # Pick whichever candidate the data says is improving. The node must stay
    # alive: apply() inserts it into the route by reference.
    candidate = 2
    node = Node(loc=candidate)
    delta, improving = op.evaluate(node, cost_eval)
    assert_(improving)
    assert_(delta < 0)

    before = cost_eval.penalised_cost(PyVRPSolution(data, [[1, 4]]))
    op.apply(node)
    assert_equal(str(sol.routes[0]), f"{candidate} 4")
    after = cost_eval.penalised_cost(PyVRPSolution(data, [[candidate, 4]]))
    assert_(after < before)


def test_no_improving_move_when_no_group_member_routed(
    ok_small_mutually_exclusive_groups,
):
    """
    If no member of the candidate's group is currently in the solution there is
    nothing to replace, so the move is a no-op (delta 0, not improving).
    """
    data = ok_small_mutually_exclusive_groups
    cost_eval = CostEvaluator([0], 0, 0)

    # Only client 4 (not in any group) is routed.
    sol = Solution(data)
    sol.load(PyVRPSolution(data, [[4]]))

    op = ReplaceGroup(data)
    op.init(sol)

    delta, improving = op.evaluate(Node(loc=2), cost_eval)
    assert_equal(delta, 0)
    assert_equal(improving, False)


def test_replace_updates_route_state(ok_small_mutually_exclusive_groups):
    """
    After a replacement the route state is updated: re-initialising and
    re-evaluating the same candidate (now the routed member) is no longer an
    improving move.
    """
    data = ok_small_mutually_exclusive_groups
    cost_eval = CostEvaluator([0], 0, 0)

    sol = Solution(data)
    sol.load(PyVRPSolution(data, [[1, 4]]))

    op = ReplaceGroup(data)
    op.init(sol)

    node2 = Node(loc=2)
    _, improving = op.evaluate(node2, cost_eval)
    assert_(improving)

    op.apply(node2)
    assert_equal(str(sol.routes[0]), "2 4")

    # Member 2 is now routed; trying to swap it back in is not improving.
    op.init(sol)
    _, improving2 = op.evaluate(node2, cost_eval)
    assert_equal(improving2, False)
