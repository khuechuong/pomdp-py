import random
from pomdp_problems.tiger.tiger_problem import TigerState, TigerProblem, test_planner
import pomdp_py
from pomdp_py.utils.debugging import TreeDebugger

def test_tree_debugger_tiger():

    init_true_state = random.choice([TigerState("tiger-left"),
                                     TigerState("tiger-right")])
    init_belief = pomdp_py.Histogram({TigerState("tiger-left"): 0.5,
                                      TigerState("tiger-right"): 0.5})
    tiger_problem = TigerProblem(0.15,  # observation noise
                                 init_true_state, init_belief)

    tiger_problem.agent.set_belief(init_belief, prior=True)
    pouct = pomdp_py.POUCT(max_depth=6, discount_factor=0.95,
                           num_sims=4096, exploration_const=200,
                           rollout_policy=tiger_problem.agent.policy_model)

    pouct.plan(tiger_problem.agent)
    dd = TreeDebugger(tiger_problem.agent.tree)

    # The number of VNodes equals to the sum of VNodes per layer
    assert dd.nv == sum([len(dd.l(i)) for i in range(dd.nl)])

    # The total number of nodes equal to the number of VNodes plus QNodes
    assert dd.nn == dd.nv + dd.nq

    print("Passed tests.")
    test_planner(tiger_problem, pouct, nsteps=3, debug_tree=True)


if __name__ == "__main__":
    test_tree_debugger_tiger()