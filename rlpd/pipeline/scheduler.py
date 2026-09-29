from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable


class OverlapScheduler:
    def __init__(
        self,
        prepare: Callable[[int], object],
        evaluate: Callable[[object], object],
        accept: Callable[[object, object, object | None], None] | None = None,
    ):
        self.prepare = prepare
        self.evaluate = evaluate
        self.accept = accept

    def run(self, batch_count: int | list[list[str]]) -> list[object]:
        count = batch_count if isinstance(batch_count, int) else len(batch_count)
        if count < 1:
            return []
        results: list[object] = []
        with ThreadPoolExecutor(max_workers=1) as executor:
            current = self.prepare(0)
            for index in range(count):
                if current is None or (hasattr(current, "batch") and not current.batch):
                    break
                next_future: Future | None = executor.submit(self.prepare, index + 1) if index + 1 < count else None
                result = self.evaluate(current)
                next_batch = next_future.result() if next_future is not None else None
                if self.accept is not None:
                    self.accept(current, result, next_batch)
                results.append(result)
                current = next_batch
        return results
