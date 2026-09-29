from abc import ABC, abstractmethod


class Evaluator(ABC):
    @abstractmethod
    def evaluate(self, sequences: list[str]) -> dict[str, float]:
        raise NotImplementedError
