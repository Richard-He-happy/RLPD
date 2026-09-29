from abc import ABC, abstractmethod


class SearchPolicy(ABC):
    @abstractmethod
    def propose(self, count: int) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def update(self, sequence: str, score: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def state_dict(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def load_state(self, values: dict) -> None:
        raise NotImplementedError
