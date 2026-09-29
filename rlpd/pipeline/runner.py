import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..cache import EvaluationCache
from ..config import Config
from ..evaluators.autodock_gpu import AutoDockGPUEvaluator
from ..evaluators.toy import ToyEvaluator
from ..policies.random_mutation import RandomMutationPolicy
from ..policies.vanilla_ucb import VanillaUCBPolicy
from ..utils import atomic_write_json
from .checkpoint import Checkpoint
from .scheduler import OverlapScheduler
from .state import SearchState


@dataclass
class PreparedBatch:
    batch: list[str]
    policy_state: dict


def evaluate_batch(
    batch: list[str], cache: EvaluationCache, evaluator: object
) -> dict[str, float]:
    scores = {sequence: cache.get(sequence) for sequence in batch}
    missing = [sequence for sequence in batch if scores[sequence] is None]
    if missing:
        scores.update(evaluator.evaluate(missing))
    return {sequence: float(scores[sequence]) for sequence in batch}


def _make_policy(config: Config):
    if config.policy == "ucb":
        return VanillaUCBPolicy(config.search_space, config.seed, config.exploration)
    return RandomMutationPolicy(config.search_space, config.seed)


def run(config: Config, resume: bool = True) -> dict:
    work = Path(config.work_root)
    work.mkdir(parents=True, exist_ok=True)
    checkpoint = Checkpoint(work / "checkpoint.json")
    expected_signature = config.signature()
    cache_path = work / "cache.json"
    if not resume and cache_path.exists():
        cache_path.unlink()
    cache = EvaluationCache(cache_path, expected_signature)
    has_checkpoint = resume and checkpoint.exists
    state = checkpoint.read() if has_checkpoint else SearchState(config_signature=expected_signature)
    if has_checkpoint and state.config_signature != expected_signature:
        raise ValueError("checkpoint configuration is incompatible with the current configuration")
    if not resume:
        cache.clear()
        state = SearchState(config_signature=expected_signature)
    else:
        cache.update(state.evaluated)
        cache.save()

    policy = _make_policy(config)
    if state.policy:
        policy.load_state(state.policy)
    else:
        for sequence, score in state.evaluated.items():
            policy.update(sequence, score)

    def persist() -> None:
        state.policy = policy.state_dict()
        checkpoint.write(state)

    active_batch_size = 0
    prefetched_for_resume = [
        sequence for sequence in state.prefetched if sequence not in state.pending
    ] if state.pending else []
    if not state.pending and state.prefetched:
        state.pending = list(state.prefetched)
        state.prefetched = []

    def prepare(index: int) -> PreparedBatch:
        nonlocal active_batch_size, prefetched_for_resume
        if index == 0 and state.pending:
            batch = list(state.pending)
            active_batch_size = len(batch)
            return PreparedBatch(batch, policy.state_dict())
        if index > 0 and prefetched_for_resume:
            batch = prefetched_for_resume
            prefetched_for_resume = []
            return PreparedBatch(batch, policy.state_dict())
        if index == 0:
            remaining = config.budget - len(state.evaluated)
            source_policy = policy
        else:
            remaining = config.budget - len(state.evaluated) - active_batch_size
            source_policy = copy.deepcopy(policy)
        batch = source_policy.propose(min(config.batch_size, remaining)) if remaining > 0 else []
        active_batch_size = len(batch)
        return PreparedBatch(batch, source_policy.state_dict())

    def accept(current: object, scores: object, next_batch: object | None) -> None:
        nonlocal active_batch_size
        if not isinstance(current, PreparedBatch):
            raise TypeError("scheduler returned an invalid prepared batch")
        if isinstance(next_batch, PreparedBatch):
            policy.load_state(next_batch.policy_state)
        for sequence, score in dict(scores).items():
            cache.set(sequence, score)
            state.evaluated[sequence] = float(score)
            policy.update(sequence, float(score))
        state.pending = []
        state.prefetched = list(next_batch.batch) if isinstance(next_batch, PreparedBatch) else []
        active_batch_size = len(state.prefetched)
        state.steps += 1
        persist()
        cache.save()

    def evaluate_toy(prepared: PreparedBatch) -> dict[str, float]:
        state.pending = list(prepared.batch)
        state.prefetched = []
        persist()
        return evaluate_batch(prepared.batch, cache, ToyEvaluator(config.seed))

    remaining = config.budget - len(state.evaluated)
    if config.evaluator.kind == "toy":
        while remaining > 0:
            prepared = prepare(0)
            if not prepared.batch:
                break
            scores = evaluate_toy(prepared)
            accept(prepared, scores, None)
            remaining = config.budget - len(state.evaluated)
    else:
        evaluator = AutoDockGPUEvaluator(
            config.evaluator.command,
            config.evaluator.receptor_fld,
            config.evaluator.ligand_dir,
            work,
            config.evaluator.timeout,
            reuse_existing=has_checkpoint,
        )

        def evaluate_autodock(prepared: PreparedBatch) -> dict[str, float]:
            state.pending = list(prepared.batch)
            state.prefetched = []
            persist()
            return evaluate_batch(prepared.batch, cache, evaluator)

        OverlapScheduler(prepare, evaluate_autodock, accept).run(max(remaining, 0))

    state.status = "completed"
    state.pending = []
    state.prefetched = []
    persist()
    cache.save()
    best = max(state.evaluated.items(), key=lambda item: item[1]) if state.evaluated else (None, None)
    result = {
        "evaluated": len(state.evaluated),
        "steps": state.steps,
        "best_sequence": best[0],
        "best_score": best[1],
        "checkpoint": str(checkpoint.path),
        "cache": str(cache.path),
    }
    atomic_write_json(
        work / "run_metadata.json",
        {
            "version": "0.1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": state.status,
            "length": config.length,
            "alphabet": config.alphabet,
            "seed": config.seed,
            "budget": config.budget,
            "batch_size": config.batch_size,
            "policy": config.policy,
            "exploration": config.exploration,
            "evaluator": config.evaluator.kind,
            "config_signature": expected_signature,
            "evaluated": result["evaluated"],
            "steps": result["steps"],
            "best_sequence": result["best_sequence"],
            "best_score": result["best_score"],
        },
    )
    return result
