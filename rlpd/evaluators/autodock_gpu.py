import subprocess
from pathlib import Path

from .base import Evaluator
from .dlg_parser import parse_dlg


class AutoDockGPUEvaluator(Evaluator):
    def __init__(
        self,
        command: list[str],
        receptor_fld: str,
        ligand_dir: str | Path,
        work_dir: str | Path,
        timeout: float = 300.0,
        reuse_existing: bool = True,
    ):
        if not command:
            raise ValueError("AutoDock-GPU command cannot be empty")
        self.command = list(command)
        self.receptor_fld = str(receptor_fld)
        self.ligand_dir = Path(ligand_dir)
        self.work_dir = Path(work_dir)
        self.output_dir = self.work_dir / "autodock"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.reuse_existing = reuse_existing

    def command_for(self, sequence: str) -> list[str]:
        ligand_path = self.ligand_dir / f"{sequence}.pdbqt"
        return self.command + ["--ffile", self.receptor_fld, "--lfile", str(ligand_path)]

    def evaluate(self, sequences: list[str]) -> dict[str, float]:
        result = {}
        for sequence in sequences:
            dlg_path = self.output_dir / f"{sequence}.dlg"
            if dlg_path.exists() and not self.reuse_existing:
                dlg_path.unlink()
            if not dlg_path.exists():
                completed = subprocess.run(
                    self.command_for(sequence),
                    cwd=self.output_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
                if completed.returncode:
                    raise RuntimeError(completed.stderr.strip() or "AutoDock-GPU failed")
            result[sequence] = -parse_dlg(dlg_path)
        return result
