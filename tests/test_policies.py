import json

from rlpd.policies.random_mutation import RandomMutationPolicy
from rlpd.policies.vanilla_ucb import VanillaUCBPolicy
from rlpd.search_space import PeptideSpace


def test_random_policy_is_deterministic_and_unique():
    space = PeptideSpace(4, "AC")
    first = RandomMutationPolicy(space, 3)
    second = RandomMutationPolicy(space, 3)
    initial_first = first.propose(1)
    initial_second = second.propose(1)
    assert initial_first == initial_second
    first.update(initial_first[0], 0.5)
    second.update(initial_second[0], 0.5)
    assert first.propose(4) == second.propose(4)


def test_ucb_policy_updates():
    policy = VanillaUCBPolicy(PeptideSpace(3, "AC"), 2)
    seed = policy.propose(1)[0]
    policy.update(seed, 0.8)
    candidate = policy.propose(1)[0]
    assert policy.source_by_candidate[candidate] == seed
    policy.update(candidate, 0.2)
    assert policy.visits[seed] == 2
    assert policy.values[seed] == 1.0
    assert policy.visits[candidate] == 1


def test_ucb_state_restore_reproduces_continuation():
    space = PeptideSpace(3, "AC")
    first = VanillaUCBPolicy(space, 9)
    seed = first.propose(1)[0]
    first.update(seed, 0.8)
    candidate = first.propose(1)[0]
    snapshot = first.state_dict()
    json.dumps(snapshot)
    first.update(candidate, 0.2)
    expected = first.propose(2)
    restored = VanillaUCBPolicy(space, 9)
    restored.load_state(snapshot)
    restored.update(candidate, 0.2)
    assert restored.propose(2) == expected
