#!/usr/bin/env bash
# Recompute the published validation numbers (docs/research/reproduce.md).
#   scripts/reproduce.sh            check: every number from the committed tables and raw answers
#   scripts/reproduce.sh --full     also rebuild them from the inputs: the FAERS tables from the local
#                                   counts (.data, see docs/research/faers-calibration.md) and the
#                                   cascade answers from the public API; then compare
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -I pipelines/tools/faers_calibration.py --verify data/validation/faers/results
python3 -I pipelines/tools/cascade_validation.py --verify data/validation/cascades/results
[ "${1:-}" = "--full" ] || exit 0

out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
(cd apps/api && uv run --frozen python ../../pipelines/tools/faers_calibration.py \
  --data-dir ../../.data --ref ../../data/validation/faers --out "$out/faers" >/dev/null)
cmp "$out/faers/metrics.json" data/validation/faers/results/metrics.json \
  && echo "faers calibration: rebuilt from the counts, identical"
python3 -I pipelines/tools/cascade_validation.py --ref data/validation/cascades \
  --out "$out/cascades" >/dev/null
python3 -I pipelines/tools/cascade_validation.py --compare \
  data/validation/cascades/results/metrics.json "$out/cascades/metrics.json"
