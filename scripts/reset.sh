#!/usr/bin/env bash
# Rebuild everything from scratch: regenerate the synthetic corpus, reseed the
# database through the real pipeline, and recompute the evaluation metrics.
set -euo pipefail
cd "$(dirname "$0")/../backend"

echo "→ generating the synthetic corpus"
python3 -m app.seed.generate

echo "→ seeding (runs the full pipeline over every document)"
python3 -m app.seed.seed --reset

echo "→ computing evaluation metrics"
python3 -m app.eval.run_eval "$@"

echo "✓ done. Start the app with: npm run dev"
