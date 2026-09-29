# Architecture

The CLI loads YAML into a validated `Config`. The pipeline creates a `PeptideSpace`, selects a public `SearchPolicy`, removes sequences already present in `EvaluationCache`, and sends batches to an `Evaluator`.

For local execution, `ToyEvaluator` produces deterministic synthetic scores. For external molecular evaluation, `AutoDockGPUEvaluator` reads prepared PDBQT files from a configured ligand directory, passes a configured receptor FLD to the evaluator, reuses existing DLG files only when continuing from a compatible checkpoint, and parses generic DLG energy lines. Binding energies are negated into higher-is-better objective scores. The runner keeps one evaluator stream and uses `OverlapScheduler` to prepare the next batch on a CPU worker while the current batch is evaluated.

Scores update the public policy and are written with `Checkpoint`. `SearchState` records evaluated sequences, pending work, step count, and status. `run_metadata.json` stores a path-free run summary and configuration signature. Target-specific files and the core research algorithm are not part of this public architecture.
