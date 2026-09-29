import json
from pathlib import Path
from typing import Optional

from .utils import atomic_write_json


class EvaluationCache:
    schema_version = 1

    def __init__(self, path: str | Path, config_signature: str | None = None):
        self.path = Path(path)
        self.config_signature = config_signature
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._values: dict[str, float] = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict) or loaded.get("schema_version") != self.schema_version:
                raise ValueError("cache configuration is incompatible")
            stored_signature = loaded.get("config_signature")
            if config_signature is not None and stored_signature != config_signature:
                raise ValueError("cache configuration is incompatible")
            values = loaded.get("values")
            if not isinstance(values, dict):
                raise ValueError("cache configuration is incompatible")
            self.config_signature = stored_signature
            self._values = {str(key): float(value) for key, value in values.items()}

    def get(self, sequence: str) -> Optional[float]:
        return self._values.get(sequence)

    def __contains__(self, sequence: str) -> bool:
        return sequence in self._values

    def set(self, sequence: str, score: float) -> None:
        self._values[sequence] = float(score)

    def update(self, values: dict[str, float]) -> None:
        self._values.update({str(key): float(value) for key, value in values.items()})

    def clear(self) -> None:
        self._values.clear()

    def save(self) -> None:
        atomic_write_json(
            self.path,
            {
                "schema_version": self.schema_version,
                "config_signature": self.config_signature,
                "values": self._values,
            },
        )

    def __len__(self) -> int:
        return len(self._values)

    def items(self):
        return self._values.items()
