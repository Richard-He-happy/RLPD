import json

import pytest

from rlpd.cache import EvaluationCache
from rlpd.policies.random_mutation import RandomMutationPolicy
from rlpd.search_space import PeptideSpace, SequenceError


def test_space_size_and_validation():
    space = PeptideSpace(3, "AC")
    assert space.size == 8
    assert list(space.iter_sequences())[0] == "AAA"
    with pytest.raises(SequenceError):
        space.validate("AAAA")


def test_cache_round_trip(tmp_path):
    path = tmp_path / "cache.json"
    cache = EvaluationCache(path)
    cache.set("AAA", 1.5)
    cache.save()
    assert EvaluationCache(path).get("AAA") == 1.5
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == 1
    assert payload["config_signature"] is None
    assert payload["values"]["AAA"] == 1.5


def test_random_fallback_fills_near_exhausted_space():
    space = PeptideSpace(2, "AB")
    policy = RandomMutationPolicy(space, 1)
    first = policy.propose(1)[0]
    policy.update(first, 1.0)
    remaining = [sequence for sequence in space.iter_sequences() if sequence != first]
    policy.seen.update(remaining[:-1])
    assert len(policy.propose(2)) == 1
