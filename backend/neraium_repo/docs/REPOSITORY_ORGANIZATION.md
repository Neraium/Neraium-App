# Repository Organization Guide

This document is the canonical map of the repo and the conventions for where new files should live.

## Top-level layout

- `neraium_core/`: Core product package (engine, decision layer, structural analytics).
- `apps/`: Deployable app surfaces (API + static UI).
- `tools/`: Operational scripts for demos, evaluation, diagnostics, and release checks.
- `examples/`: Scenario-specific entrypoints and datasets for guided demonstrations.
- `validation/`: Validation harnesses (history, replay, drift, outcomes, feedback).
- `evaluation/`: Benchmarking and model/representation evaluation logic.
- `docs/`: Product, architecture, deployment, runbooks, and workflow documentation.
- `artifacts/`: Stored proof artifacts and long-form generated outputs that are intentionally versioned.
- `fixtures/`: Static test and replay fixtures.
- `logs/`: Human-readable run transcripts and local run logs.

## Root file policy

Root should only contain:

1. Packaging/build metadata (`pyproject.toml`, `setup.py`, `build_backend.py`).
2. Deployment manifests (`Dockerfile`, `docker-compose.yml`, `apprunner.yaml`).
3. High-signal entrypoints (`app.py`, `run_demo.py`, selected compatibility launchers).
4. Small number of global config files (`pytest.ini`, `.gitignore`, env examples).

Everything else should go in a domain directory (`tools/`, `examples/`, `docs/`, `artifacts/`).

## Where new code should go

- New reusable library logic: `neraium_core/`.
- New one-off runnable script: `tools/`.
- New scenario/demo workflow: `examples/<scenario>/`.
- New release/operations documentation: `docs/`.
- New deterministic fixture used by tests: `fixtures/`.

## Naming conventions

- Tooling scripts: `tools/run_<task>.py`, `tools/evaluate_<task>.py`, `tools/plot_<task>.py`.
- Docs: `docs/<UPPER_SNAKE_CASE>.md` for runbooks/policies, `docs/<TitleLike>.md` only when already established.
- Generated report files: place under `reports/` (gitignored) unless they are intentional proof artifacts for version control.

## Cleanup checklist for future PRs

When adding files, perform this quick check:

- Did I add a script at root that belongs in `tools/`?
- Did I commit generated outputs that should be ignored?
- Did I add docs for a new workflow under `docs/`?
- Did I preserve backwards-compatible entrypoints if moving scripts?

Keeping this structure consistent reduces cognitive overhead and makes release workflows easier to audit.
