# Design

## Policy and evaluator separation

`SearchPolicy` owns candidate proposal and score updates. `Evaluator` owns score production. This boundary allows local deterministic tests and external evaluation to use the same runner.

## Cache and checkpoint

`EvaluationCache` stores a signature-bound sequence-to-score JSON mapping and writes it atomically. `Checkpoint` stores `SearchState`, including evaluated sequences, pending work, step count, and status. The runner checks the cache before evaluation and writes a checkpoint after each accepted batch.

## CPU/GPU overlap

`OverlapScheduler` has one CPU preparation worker and one evaluator execution path. It submits preparation for the next batch before calling the evaluator for the current batch, waits for the prepared batch, then accepts the current result. The evaluator callback is never invoked concurrently, so one GPU stream cannot be occupied by two docking jobs at once.

The runner uses this scheduler for the AutoDock-GPU path. A pending batch is checkpointed before evaluation. Existing DLG files are parsed only when continuing from a compatible checkpoint. A new run, including a run with no compatible checkpoint, removes only the sequence-specific stale DLG before launching evaluation.

The evaluator contract uses higher-is-better objective scores. AutoDock-GPU binding energies are negated before they reach the search policy.
