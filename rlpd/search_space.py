from dataclasses import dataclass
from itertools import product
from typing import Iterable, Iterator


class SequenceError(ValueError):
    pass


@dataclass(frozen=True)
class PeptideSpace:
    length: int
    alphabet: str

    def __post_init__(self) -> None:
        if self.length < 1:
            raise SequenceError("length must be positive")
        if not self.alphabet or len(set(self.alphabet)) != len(self.alphabet):
            raise SequenceError("alphabet must contain unique symbols")

    @property
    def size(self) -> int:
        return len(self.alphabet) ** self.length

    def validate(self, sequence: str) -> str:
        if len(sequence) != self.length:
            raise SequenceError(f"sequence length must be {self.length}")
        if any(symbol not in self.alphabet for symbol in sequence):
            raise SequenceError("sequence contains a symbol outside the alphabet")
        return sequence

    def iter_sequences(self) -> Iterator[str]:
        yield from ("".join(items) for items in product(self.alphabet, repeat=self.length))

    def mutate(self, sequence: str, position: int, symbol: str) -> str:
        self.validate(sequence)
        if position < 0 or position >= self.length:
            raise SequenceError("position is outside the sequence")
        if symbol not in self.alphabet:
            raise SequenceError("symbol is outside the alphabet")
        if sequence[position] == symbol:
            raise SequenceError("mutation must change the symbol")
        return sequence[:position] + symbol + sequence[position + 1:]

    def random_sequence(self, rng) -> str:
        return "".join(rng.choice(self.alphabet) for _ in range(self.length))

    def validate_many(self, sequences: Iterable[str]) -> list[str]:
        return [self.validate(sequence) for sequence in sequences]
