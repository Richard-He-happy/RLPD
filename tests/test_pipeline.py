import json
import subprocess
import threading

import pytest

from rlpd.cli import main
from rlpd.cache import EvaluationCache
from rlpd.config import Config, ConfigError, EvaluatorConfig, load_config
from rlpd.pipeline.checkpoint import Checkpoint
from rlpd.pipeline.runner import run
from rlpd.pipeline.scheduler import OverlapScheduler
from rlpd.pipeline.state import SearchState
from rlpd.policies.random_mutation import RandomMutationPolicy


def write_config(tmp_path, budget=4, evaluator="toy", policy="random"):
    if evaluator == "toy":
        evaluator_text = "  kind: toy\n"
    else:
        ligand_dir = str(tmp_path / "ligands").replace("\\", "/")
        evaluator_text = (
            "  kind: autodock_gpu\n"
            "  command: [autodock_gpu]\n"
            "  receptor_fld: Target_A.maps.fld\n"
            f"  ligand_dir: {ligand_dir}\n"
        )
    path = tmp_path / "config.yaml"
    work_root = str(tmp_path / "work").replace("\\", "/")
    config_text = (
        "length: 3\n"
        "alphabet: AC\n"
        f"budget: {budget}\n"
        "batch_size: 2\n"
        f"policy: {policy}\n"
        f"work_root: '{work_root}'\n"
        "evaluator:\n"
        f"{evaluator_text}"
    )
    path.write_text(config_text, encoding="utf-8")
    return path


def test_checkpoint_round_trip(tmp_path):
    checkpoint = Checkpoint(tmp_path / "checkpoint.json")
    expected = SearchState(evaluated={"AAA": 0.5}, pending=["AAC"], steps=2)
    checkpoint.write(expected)
    assert checkpoint.read() == expected
    assert json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))["schema_version"] == 1


def test_checkpoint_rejects_unknown_schema(tmp_path):
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema version"):
        Checkpoint(path).read()


def test_budget_and_resume_without_duplicate_evaluation(tmp_path):
    config = load_config(write_config(tmp_path))
    first = run(config, resume=False)
    cache_before = json.loads((tmp_path / "work" / "cache.json").read_text(encoding="utf-8"))
    second = run(config, resume=True)
    cache_after = json.loads((tmp_path / "work" / "cache.json").read_text(encoding="utf-8"))
    assert first["evaluated"] == 4
    assert second["evaluated"] == 4
    assert cache_after == cache_before


def test_cache_reconciles_from_checkpoint(tmp_path):
    config = load_config(write_config(tmp_path, budget=1))
    work = tmp_path / "work"
    work.mkdir()
    policy = RandomMutationPolicy(config.search_space, config.seed)
    policy.update("AAA", 0.5)
    Checkpoint(work / "checkpoint.json").write(
        SearchState(
            config_signature=config.signature(),
            evaluated={"AAA": 0.5},
            policy=policy.state_dict(),
        )
    )
    result = run(config, resume=True)
    assert result["evaluated"] == 1
    payload = json.loads((work / "cache.json").read_text(encoding="utf-8"))
    assert payload["values"]["AAA"] == 0.5


def test_resume_rejects_incompatible_config(tmp_path):
    path = write_config(tmp_path, budget=1)
    config = load_config(path)
    work = tmp_path / "work"
    work.mkdir()
    Checkpoint(work / "checkpoint.json").write(SearchState(config_signature=config.signature()))
    path.write_text(path.read_text(encoding="utf-8").replace("alphabet: AC", "alphabet: AD"), encoding="utf-8")
    with pytest.raises(ValueError, match="incompatible"):
        run(load_config(path), resume=True)


def test_prefetched_batch_survives_resume(tmp_path, monkeypatch):
    path = write_config(tmp_path, budget=2, evaluator="autodock")
    config = load_config(path)
    policy = RandomMutationPolicy(config.search_space, config.seed)
    pending = policy.propose(1)[0]
    policy.update(pending, 0.0)
    prefetched = policy.propose(1)[0]
    work = tmp_path / "work"
    work.mkdir()
    Checkpoint(work / "checkpoint.json").write(
        SearchState(
            config_signature=config.signature(),
            pending=[pending],
            prefetched=[prefetched],
            policy=policy.state_dict(),
        )
    )
    received = []

    class FakeEvaluator:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, sequences):
            received.extend(sequences)
            return {sequence: float(index) for index, sequence in enumerate(sequences)}

    monkeypatch.setattr("rlpd.pipeline.runner.AutoDockGPUEvaluator", FakeEvaluator)
    result = run(config, resume=True)
    assert result["evaluated"] == 2
    assert received == [pending, prefetched]


def test_fake_autodock_reaches_exact_budget(tmp_path, monkeypatch):
    path = write_config(tmp_path, budget=8, evaluator="autodock", policy="ucb")
    config = load_config(path)
    received = []

    class FakeEvaluator:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, sequences):
            received.extend(sequences)
            return {sequence: float(index) for index, sequence in enumerate(sequences)}

    monkeypatch.setattr("rlpd.pipeline.runner.AutoDockGPUEvaluator", FakeEvaluator)
    result = run(config, resume=False)
    assert result["evaluated"] == 8
    assert len(received) == 8
    assert len(set(received)) == 8



def test_resume_without_checkpoint_does_not_reuse_stale_dlg(tmp_path, monkeypatch):
    path = write_config(tmp_path, budget=1, evaluator="autodock")
    config = load_config(path)
    work = tmp_path / "work"
    output_dir = work / "autodock"
    output_dir.mkdir(parents=True)
    candidate = RandomMutationPolicy(config.search_space, config.seed).propose(1)[0]
    dlg_path = output_dir / f"{candidate}.dlg"
    dlg_path.write_text("Estimated Free Energy of Binding = -1.0", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        dlg_path.write_text("Estimated Free Energy of Binding = -8.0", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("rlpd.evaluators.autodock_gpu.subprocess.run", fake_run)
    result = run(config, resume=True)
    assert calls
    assert result["evaluated"] == 1
    assert result["best_sequence"] == candidate
    assert result["best_score"] == 8.0


def test_cache_schema_has_no_duplicate_root_values(tmp_path):
    path = tmp_path / "cache.json"
    cache = EvaluationCache(path, "signature")
    cache.set("AAA", 1.5)
    cache.save()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {"schema_version", "config_signature", "values"}
    assert payload["config_signature"] == "signature"
    assert payload["values"] == {"AAA": 1.5}

def test_cli_demo(tmp_path, capsys):
    path = write_config(tmp_path, 2)
    assert main(["demo", "--config", str(path), "--no-resume"]) == 0
    assert json.loads(capsys.readouterr().out)["evaluated"] == 2


def test_scheduler_overlaps_preparation_with_single_evaluator_stream():
    evaluation_running = threading.Event()
    next_prepared = threading.Event()
    active_evaluations = 0
    maximum_active = 0
    lock = threading.Lock()

    def prepare(index):
        if index == 1:
            assert evaluation_running.wait(1)
            next_prepared.set()
        return [index]

    def evaluate(batch):
        nonlocal active_evaluations, maximum_active
        with lock:
            active_evaluations += 1
            maximum_active = max(maximum_active, active_evaluations)
        evaluation_running.set()
        if batch == [0]:
            assert next_prepared.wait(1)
        evaluation_running.clear()
        with lock:
            active_evaluations -= 1
        return batch[0]

    assert OverlapScheduler(prepare, evaluate).run(3) == [0, 1, 2]
    assert maximum_active == 1


def test_cache_hit_without_checkpoint_skips_expensive_evaluator(tmp_path, monkeypatch):
    path = write_config(tmp_path, budget=1, evaluator="autodock")
    config = load_config(path)
    work = tmp_path / "work"
    work.mkdir()
    candidate = RandomMutationPolicy(config.search_space, config.seed).propose(1)[0]
    cache = EvaluationCache(work / "cache.json", config.signature())
    cache.set(candidate, 7.5)
    cache.save()

    class FailingEvaluator:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, sequences):
            raise AssertionError(f"cache miss for {sequences}")

    monkeypatch.setattr("rlpd.pipeline.runner.AutoDockGPUEvaluator", FailingEvaluator)
    result = run(config, resume=True)
    assert result["evaluated"] == 1
    assert result["best_score"] == 7.5


def test_interrupted_overlap_resume_matches_uninterrupted_sequence(tmp_path, monkeypatch):
    path = write_config(tmp_path, budget=6, evaluator="autodock")
    config = load_config(path)
    failed_calls = []

    class InterruptingEvaluator:
        calls = 0

        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, sequences):
            failed_calls.extend(sequences)
            type(self).calls += 1
            if type(self).calls == 2:
                raise RuntimeError("simulated interruption")
            return {sequence: float(index) for index, sequence in enumerate(sequences)}

    monkeypatch.setattr("rlpd.pipeline.runner.AutoDockGPUEvaluator", InterruptingEvaluator)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        run(config, resume=False)
    checkpoint = json.loads((tmp_path / "work" / "checkpoint.json").read_text())
    assert set(checkpoint["pending"]).isdisjoint(checkpoint["prefetched"])
    evaluated_before = set(checkpoint["evaluated"])

    resumed_calls = []

    class RecordingEvaluator:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, sequences):
            resumed_calls.extend(sequences)
            return {sequence: float(index) for index, sequence in enumerate(sequences)}

    monkeypatch.setattr("rlpd.pipeline.runner.AutoDockGPUEvaluator", RecordingEvaluator)
    resumed = run(config, resume=True)
    assert evaluated_before.isdisjoint(resumed_calls)

    uninterrupted_path = tmp_path / "uninterrupted.yaml"
    uninterrupted_path.write_text(
        path.read_text(encoding="utf-8").replace(
            str(tmp_path / "work").replace("\\", "/"),
            str(tmp_path / "uninterrupted").replace("\\", "/"),
        ),
        encoding="utf-8",
    )
    uninterrupted_calls = []

    class UninterruptedEvaluator(RecordingEvaluator):
        def evaluate(self, sequences):
            uninterrupted_calls.extend(sequences)
            return {sequence: float(index) for index, sequence in enumerate(sequences)}

    monkeypatch.setattr("rlpd.pipeline.runner.AutoDockGPUEvaluator", UninterruptedEvaluator)
    uninterrupted = run(load_config(uninterrupted_path), resume=False)
    assert resumed["evaluated"] == uninterrupted["evaluated"]
    assert resumed["best_sequence"] == uninterrupted["best_sequence"]
    assert resumed_calls == uninterrupted_calls[len(checkpoint["evaluated"]):]


def test_config_signature_collision_regressions(tmp_path):
    evaluator = EvaluatorConfig(
        kind="autodock_gpu",
        command=["/one/bin/autodock"],
        receptor_fld="/target_A/foo.maps.fld",
        ligand_dir="/ligands_A",
    )
    base = Config(
        length=2, alphabet="AC", seed=3, budget=2, batch_size=1,
        policy="random", exploration=1.0, work_root=str(tmp_path),
        evaluator=evaluator,
    ).validate()
    assert base.signature() != Config(
        length=2, alphabet="AC", seed=3, budget=2, batch_size=2,
        policy="random", exploration=1.0, work_root=str(tmp_path),
        evaluator=evaluator,
    ).validate().signature()
    for changed in (
        EvaluatorConfig(kind="autodock_gpu", command=["/one/bin/autodock"],
                        receptor_fld="/target_B/foo.maps.fld", ligand_dir="/ligands_A"),
        EvaluatorConfig(kind="autodock_gpu", command=["/two/bin/autodock"],
                        receptor_fld=evaluator.receptor_fld, ligand_dir="/ligands_A"),
        EvaluatorConfig(kind="autodock_gpu", command=["/one/bin/autodock"],
                        receptor_fld=evaluator.receptor_fld, ligand_dir="/ligands_B"),
    ):
        assert base.signature() != Config(
            length=2, alphabet="AC", seed=3, budget=2, batch_size=1,
            policy="random", exploration=1.0, work_root=str(tmp_path),
            evaluator=changed,
        ).validate().signature()


def test_metadata_is_path_free(tmp_path):
    path = write_config(tmp_path, budget=1)
    config = load_config(path)
    result = run(config, resume=False)
    metadata_path = tmp_path / "work" / "run_metadata.json"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    assert str(tmp_path / "work") not in metadata_text
    assert "config" not in json.loads(metadata_text)
    assert "result" not in json.loads(metadata_text)
