import subprocess
from pathlib import Path

from rlpd.evaluators.autodock_gpu import AutoDockGPUEvaluator
from rlpd.evaluators.dlg_parser import parse_lowest_energy, parse_score
from rlpd.evaluators.toy import ToyEvaluator


def test_toy_is_deterministic():
    assert ToyEvaluator(1).evaluate(["AAAA"]) == ToyEvaluator(1).evaluate(["AAAA"])


def test_dlg_score():
    assert parse_score("Estimated Free Energy of Binding = -4.25") == -4.25


def test_dlg_parser_uses_lowest_energy_and_rank_one_histogram():
    text = """
Estimated Free Energy of Binding = -3.5
Estimated Free Energy of Binding = -8.0
CLUSTERING HISTOGRAM
    1    -7.25    3
    2    -6.10    1
"""
    assert parse_lowest_energy(text) == -8.0
    assert parse_lowest_energy("CLUSTERING HISTOGRAM\n  1 -9.25 2") == -9.25


def test_autodock_reuses_existing_dlg(tmp_path, monkeypatch):
    output_dir = tmp_path / "work" / "autodock"
    output_dir.mkdir(parents=True)
    (output_dir / "AAAA.dlg").write_text("Estimated Free Energy of Binding = -3.5", encoding="utf-8")

    def fail(*args, **kwargs):
        raise AssertionError("external evaluator should not run")

    monkeypatch.setattr(subprocess, "run", fail)
    evaluator = AutoDockGPUEvaluator(["unused"], "target.fld", tmp_path / "ligands", tmp_path / "work")
    assert evaluator.evaluate(["AAAA"]) == {"AAAA": 3.5}


def test_autodock_command_and_objective_direction(tmp_path, monkeypatch):
    ligand_dir = tmp_path / "ligands"
    ligand_dir.mkdir()
    output_dir = tmp_path / "work" / "autodock"
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        output_dir.mkdir(parents=True, exist_ok=True)
        name = Path(command[-1]).stem
        energy = "-8.0" if name == "B" else "-3.5"
        (output_dir / f"{name}.dlg").write_text(f"Estimated Free Energy of Binding = {energy}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    evaluator = AutoDockGPUEvaluator(["autodock_gpu", "--demo"], "Target_A.maps.fld", ligand_dir, tmp_path / "work")
    scores = evaluator.evaluate(["A", "B"])
    assert scores["B"] > scores["A"]
    assert "--ffile" in calls[0]
    assert calls[0][calls[0].index("--ffile") + 1] == "Target_A.maps.fld"
    assert "--lfile" in calls[0]
    assert calls[0][calls[0].index("--lfile") + 1].endswith("A.pdbqt")


def test_autodock_no_resume_replaces_stale_dlg(tmp_path, monkeypatch):
    output_dir = tmp_path / "work" / "autodock"
    output_dir.mkdir(parents=True)
    dlg_path = output_dir / "AAAA.dlg"
    dlg_path.write_text("Estimated Free Energy of Binding = -1.0", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        dlg_path.write_text("Estimated Free Energy of Binding = -8.0", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    evaluator = AutoDockGPUEvaluator(
        ["autodock_gpu"], "target.fld", tmp_path / "ligands", tmp_path / "work",
        reuse_existing=False,
    )
    assert evaluator.evaluate(["AAAA"]) == {"AAAA": 8.0}
    assert calls
