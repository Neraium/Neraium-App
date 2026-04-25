#!/usr/bin/env bash
set -euo pipefail

CORPUS_IDS=${CORPUS_IDS:-"corpus_v1"}
HISTORY_ROOT=${HISTORY_ROOT:-"reports/validation/history"}

for corpus in ${CORPUS_IDS}; do
  python tools/run_release_candidate.py \
    --corpus-id "${corpus}" \
    --history-root "${HISTORY_ROOT}" \
    --output "reports/validation/history/${corpus}/latest_real_world_validation_report.json" \
    --core-output "reports/validation/history/${corpus}/latest_core_validation_report.json" \
    --release-gate-output "reports/validation/history/${corpus}/latest_release_gate_report.json"
done

python -m validation.history.trends --history-root "${HISTORY_ROOT}" --output "${HISTORY_ROOT}/trend_summary.json"
