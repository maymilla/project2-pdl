#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PROFILE="${1:-dev}"
SEED="${2:-20260101}"

./scripts/up.sh
./scripts/reset.sh
python data/generate.py --profile "$PROFILE" --seed "$SEED"
python postgres/load.py --csv-dir "data/out/$PROFILE"
python memgraph/load.py --csv-dir "data/out/$PROFILE"
python validation/validate.py --profile "$PROFILE"

echo "Seed completed for profile $PROFILE with seed $SEED"
