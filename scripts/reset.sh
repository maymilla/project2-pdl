#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Reset PostgreSQL schema.
python postgres/load.py --schema-only

# Reset Memgraph schema and in-memory data.
python memgraph/load.py --schema-only

echo "Database schemas reset successfully."
