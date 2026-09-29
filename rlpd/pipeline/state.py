import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..utils import atomic_write_json


@dataclass
class SearchState:
    schema_version: int = 1
    config_signature: str = ""
    evaluated: dict[str, float] = field(default_factory=dict)
    pending: list[str] = field(default_factory=list)
    prefetched: list[str] = field(default_factory=list)
    steps: int = 0
    status: str = "running"
    policy: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict) -> "SearchState":
        version = int(values.get("schema_version", 0))
        if version != 1:
            raise ValueError(f"unsupported checkpoint schema version: {version}")
        return cls(
            schema_version=version,
            config_signature=str(values.get("config_signature", "")),
            evaluated={
                str(key): float(value)
                for key, value in values.get("evaluated", {}).items()
            },
            pending=list(values.get("pending", [])),
            prefetched=list(values.get("prefetched", [])),
            steps=int(values.get("steps", 0)),
            status=str(values.get("status", "running")),
            policy=dict(values.get("policy", {})),
        )


def save_state(state: SearchState, path: str | Path) -> None:
    atomic_write_json(path, state.to_dict())


def load_state(path: str | Path) -> SearchState:
    with Path(path).open(encoding="utf-8") as handle:
        return SearchState.from_dict(json.load(handle))
