from pathlib import Path

from .state import SearchState, load_state, save_state


class Checkpoint:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def write(self, state: SearchState) -> None:
        save_state(state, self.path)

    def read(self) -> SearchState:
        return load_state(self.path)

    @property
    def exists(self) -> bool:
        return self.path.exists()
