import hashlib
import json
import numbers
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .search_space import PeptideSpace


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluatorConfig:
    kind: str = "toy"
    command: list[str] = field(default_factory=list)
    receptor_fld: str = ""
    ligand_dir: str = ""
    timeout: float = 300.0


@dataclass(frozen=True)
class Config:
    length: int = 4
    alphabet: str = "ACDE"
    seed: int = 7
    budget: int = 24
    batch_size: int = 4
    policy: str = "random"
    exploration: float = 1.41421356237
    work_root: str = "./work"
    evaluator: EvaluatorConfig = field(default_factory=EvaluatorConfig)

    @property
    def search_space(self) -> PeptideSpace:
        return PeptideSpace(self.length, self.alphabet)

    def validate(self) -> "Config":
        space = self.search_space
        if self.budget < 1 or self.batch_size < 1:
            raise ConfigError("budget and batch_size must be positive")
        if self.budget > space.size:
            raise ConfigError("budget cannot exceed the search-space size")
        if self.policy not in {"random", "ucb"}:
            raise ConfigError("policy must be random or ucb")
        if not isinstance(self.exploration, numbers.Real) or self.exploration < 0:
            raise ConfigError("exploration must be non-negative")
        if not isinstance(self.evaluator.command, list) or not all(
            isinstance(item, str) and item for item in self.evaluator.command
        ):
            raise ConfigError("evaluator.command must be a non-empty list of strings")
        if not isinstance(self.evaluator.timeout, numbers.Real) or self.evaluator.timeout <= 0:
            raise ConfigError("evaluator.timeout must be positive")
        if self.evaluator.kind not in {"toy", "autodock_gpu"}:
            raise ConfigError("evaluator.kind must be toy or autodock_gpu")
        if self.evaluator.kind == "autodock_gpu":
            if not self.evaluator.command:
                raise ConfigError("autodock_gpu requires evaluator.command")
            if not self.evaluator.receptor_fld:
                raise ConfigError("autodock_gpu requires evaluator.receptor_fld")
            if not self.evaluator.ligand_dir:
                raise ConfigError("autodock_gpu requires evaluator.ligand_dir")
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def signature(self) -> str:
        values = {
            "length": self.length,
            "alphabet": self.alphabet,
            "seed": self.seed,
            "batch_size": self.batch_size,
            "policy": self.policy,
            "exploration": self.exploration,
            "evaluator": {
                "kind": self.evaluator.kind,
                "command": list(self.evaluator.command),
                "receptor_fld": self.evaluator.receptor_fld,
                "ligand_dir": self.evaluator.ligand_dir,
            },
        }
        payload = json.dumps(values, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_config(path: str | Path) -> Config:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"configuration file not found: {config_path}")
    with config_path.open(encoding="utf-8") as handle:
        values = yaml.safe_load(handle) or {}
    if not isinstance(values, dict):
        raise ConfigError("configuration must be a YAML mapping")
    evaluator_values = values.pop("evaluator", {}) or {}
    if not isinstance(evaluator_values, dict):
        raise ConfigError("evaluator must be a YAML mapping")
    try:
        evaluator = EvaluatorConfig(**evaluator_values)
        config = Config(evaluator=evaluator, **values)
    except TypeError as exc:
        raise ConfigError(str(exc)) from exc
    return config.validate()
