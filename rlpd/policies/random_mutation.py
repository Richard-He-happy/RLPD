import random

from ..search_space import PeptideSpace
from .base import SearchPolicy


def _json_safe(value):
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _as_tuple(value):
    if isinstance(value, list):
        return tuple(_as_tuple(item) for item in value)
    return value


class RandomMutationPolicy(SearchPolicy):
    def __init__(self, space: PeptideSpace, seed: int = 7):
        self.space = space
        self.rng = random.Random(seed)
        self.parents: list[str] = []
        self.seen: set[str] = set()
        self.scores: dict[str, float] = {}
        self.source_by_candidate: dict[str, str] = {}

    def _reserve(self, sequence: str, source: str | None) -> str:
        self.seen.add(sequence)
        if source is not None:
            self.source_by_candidate[sequence] = source
        return sequence

    def _fallback(self, count: int, result: list[str]) -> list[str]:
        if len(result) >= count:
            return result
        for sequence in self.space.iter_sequences():
            if sequence not in self.seen:
                result.append(self._reserve(sequence, None))
                if len(result) == count:
                    break
        return result

    def _initial_candidate(self) -> list[str]:
        for _ in range(30):
            candidate = self.space.random_sequence(self.rng)
            if candidate not in self.seen:
                return [self._reserve(candidate, None)]
        return self._fallback(1, [])

    def _choose_parent(self) -> str:
        return self.rng.choice(self.parents)

    def propose(self, count: int) -> list[str]:
        if count < 1:
            return []
        if not self.parents:
            return self._initial_candidate()
        result: list[str] = []
        attempts = 0
        while len(result) < count and attempts < max(30, count * 30):
            attempts += 1
            parent = self._choose_parent()
            position = self.rng.randrange(self.space.length)
            symbol = self.rng.choice(self.space.alphabet)
            if symbol == parent[position]:
                continue
            candidate = self.space.mutate(parent, position, symbol)
            if candidate not in self.seen:
                result.append(self._reserve(candidate, parent))
        return self._fallback(count, result)

    def update(self, sequence: str, score: float) -> None:
        self.space.validate(sequence)
        if sequence not in self.parents:
            self.parents.append(sequence)
        self.scores[sequence] = float(score)
        self.source_by_candidate.pop(sequence, None)

    def state_dict(self) -> dict:
        return {
            "parents": list(self.parents),
            "seen": sorted(self.seen),
            "scores": dict(self.scores),
            "source_by_candidate": dict(self.source_by_candidate),
            "rng_state": _json_safe(self.rng.getstate()),
        }

    def load_state(self, values: dict) -> None:
        self.parents = list(values.get("parents", []))
        self.seen = set(values.get("seen", self.parents))
        self.scores = {str(key): float(value) for key, value in values.get("scores", {}).items()}
        self.source_by_candidate = {
            str(key): str(value)
            for key, value in values.get("source_by_candidate", {}).items()
        }
        if "rng_state" in values:
            self.rng.setstate(_as_tuple(values["rng_state"]))
