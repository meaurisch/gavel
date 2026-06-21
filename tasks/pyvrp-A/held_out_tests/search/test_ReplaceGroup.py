from numpy.testing import assert_, assert_equal

from pyvrp import CostEvaluator
from pyvrp import Solution as PyVRPSolution
from pyvrp.search import ReplaceGroup
from pyvrp.search._search import Node, Solution


def test_replace(ok_small_mutually_exclusive_groups):
    """
    Tests that ReplaceGroup replace clients within the same group.
    """
    data = ok_small_mutually_exclusive_groups
    cost_eval = CostEvaluator([0], 0, 0)

    sol = Solution(data)
    sol.load(PyVRPSolution(data, [[1, 4]]))
    assert_equal(str(sol.routes[0]), "1 4")

    op = ReplaceGroup(data)
    op.init(sol)

    # Replacing client 1 with 2 is slightly improving:
    # delta = dist(0, 2) + dist(2, 4) - dist(0, 1) - dist(1, 4)
    #       = 1944 + 1090 - 1544 - 1593
    #       = -103.
    node = Node(loc=2)
    assert_equal(op.evaluate(node, cost_eval), (-103, True))

    op.apply(node)
    assert_equal(str(sol.routes[0]), "2 4")


def test_replacegroup_importable_from_search_module():
    """
    Tests that ReplaceGroup can be imported from pyvrp.search and has the
    expected interface methods.
    """
    from pyvrp.search import ReplaceGroup as RG

    assert_(hasattr(RG, "evaluate"))
    assert_(hasattr(RG, "apply"))
    assert_(hasattr(RG, "init"))
    assert_(hasattr(RG, "supports"))


def test_no_improving_move_no_group_member_in_solution(
    ok_small_mutually_exclusive_groups,
):
    """
    Tests that ReplaceGroup does not find an improving move when no group
    member is currently in the solution.
    """
    data = ok_small_mutually_exclusive_groups
    cost_eval = CostEvaluator([0], 0, 0)

    # Place only client 4 (not in a group). No group member is in the
    # solution, so there is nothing to replace.
    sol = Solution(data)
    sol.load(PyVRPSolution(data, [[4]]))

    op = ReplaceGroup(data)
    op.init(sol)

    # Evaluating client 2 (a group member): nobody from the group is in
    # the solution, so deltaCost stays 0 and there is no improving move.
    node2 = Node(loc=2)
    delta, improving = op.evaluate(node2, cost_eval)
    assert_equal(delta, 0)
    assert_equal(improving, False)


def test_replace_updates_route_state(ok_small_mutually_exclusive_groups):
    """
    Tests that after applying a replace, the route state is updated and
    re-evaluating the same move does not find it improving again.
    """
    data = ok_small_mutually_exclusive_groups
    cost_eval = CostEvaluator([0], 0, 0)

    sol = Solution(data)
    sol.load(PyVRPSolution(data, [[1, 4]]))

    op = ReplaceGroup(data)
    op.init(sol)

    # First, replacing client 1 with 2 should be improving.
    node2 = Node(loc=2)
    delta, improving = op.evaluate(node2, cost_eval)
    assert_(improving)

    op.apply(node2)
    assert_equal(str(sol.routes[0]), "2 4")

    # Re-init and re-evaluate: trying the same replacement (node2 is now
    # in the solution) should not be improving.
    op.init(sol)
    delta2, improving2 = op.evaluate(node2, cost_eval)
    assert_equal(improving2, False)


def test_supports(
    gtsp,
    ok_small,
    ok_small_prizes,
    ok_small_mutually_exclusive_groups,
):
    """
    Tests that ReplaceGroup only supports instances with groups.
    """
    assert_(ReplaceGroup.supports(gtsp))
    assert_(ReplaceGroup.supports(ok_small_mutually_exclusive_groups))
    assert_(not ReplaceGroup.supports(ok_small))
    assert_(not ReplaceGroup.supports(ok_small_prizes))
