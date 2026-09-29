import hashlib

from .base import Evaluator


class ToyEvaluator(Evaluator):
    def __init__(self, seed: int = 0):
        self.seed = str(seed)
        self.calls = 0

    def evaluate(self, sequences: list[str]) -> dict[str, float]:
        result = {}
        for sequence in sequences:
            digest = hashlib.sha256((self.seed + sequence).encode()).digest()
            result[sequence] = round(int.from_bytes(digest[:8], "big") / 2**64, 8)
            self.calls += 1
        return result
