import re
from pathlib import Path


class DLGParseError(ValueError):
    pass


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def parse_lowest_energy(text: str) -> float:
    energies = [
        float(value)
        for value in re.findall(
            rf"Estimated Free Energy of Binding\s*=\s*({_NUMBER})",
            text,
            re.IGNORECASE,
        )
    ]
    histogram = re.search(r"CLUSTERING HISTOGRAM(.*)", text, re.IGNORECASE | re.DOTALL)
    if histogram:
        for line in histogram.group(1).splitlines():
            match = re.match(rf"\s*1(?:\s+|:)\s*({_NUMBER})", line)
            if match:
                energies.append(float(match.group(1)))
    if not energies:
        energies.extend(float(value) for value in re.findall(rf"DOCKED:\s*({_NUMBER})", text, re.IGNORECASE))
    if not energies:
        raise DLGParseError("no docking score found")
    return min(energies)


def parse_score(text: str) -> float:
    return parse_lowest_energy(text)


def parse_dlg(path: str | Path) -> float:
    return parse_lowest_energy(Path(path).read_text(encoding="utf-8", errors="replace"))
