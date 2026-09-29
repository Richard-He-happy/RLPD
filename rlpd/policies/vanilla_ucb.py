import math

from ..search_space import PeptideSpace
from .random_mutation import RandomMutationPolicy


class VanillaUCBPolicy(RandomMutationPolicy):
    def __init__(self, space: PeptideSpace, seed: int = 7, exploration: float = 1.41421356237):
        super().__init__(space, seed)
        self.exploration = exploration
        self.visits: dict[str, int] = {}
        self.values: dict[str, float] = {}
        self.total_visits = 0

    def _choose_parent(self) -> str:
        total = max(self.total_visits, 1)
        def ucb(sequence: str) -> float:
            mean = self.values[sequence] / self.visits[sequence]
            bonus = self.exploration * math.sqrt(math.log(total) / self.visits[sequence])
            return mean + bonus

        return max(self.parents, key=ucb)

    def update(self, sequence: str, score: float) -> None:
        source = self.source_by_candidate.pop(sequence, None)
        super().update(sequence, score)
        self.visits[sequence] = self.visits.get(sequence, 0) + 1
        self.values[sequence] = self.values.get(sequence, 0.0) + float(score)
        if source is not None and source in self.visits:
            self.visits[source] += 1
            self.values[source] += float(score)
        self.total_visits = sum(self.visits.values())

    def state_dict(self) -> dict:
        state = super().state_dict()
        state.update(
            {
                "visits": dict(self.visits),
                "values": dict(self.values),
                "total_visits": self.total_visits,
                "exploration": self.exploration,
            }
        )
        return state

    def load_state(self, values: dict) -> None:
        super().load_state(values)
        self.visits = {str(key): int(value) for key, value in values.get("visits", {}).items()}
        self.values = {str(key): float(value) for key, value in values.get("values", {}).items()}
        self.total_visits = int(values.get("total_visits", sum(self.visits.values())))
        self.exploration = float(values.get("exploration", self.exploration))
