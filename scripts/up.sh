#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose up -d postgres memgraph

pg_ready=0
for _ in $(seq 1 60); do
  if docker compose exec -T postgres pg_isready -U gayang -d gayang >/dev/null 2>&1; then
    pg_ready=1
    break
  fi
  sleep 1
done

if [[ "$pg_ready" -ne 1 ]]; then
  echo "PostgreSQL healthcheck failed." >&2
  exit 1
fi

mg_ready=0
for _ in $(seq 1 60); do
  if python - <<'PY'
from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=None)
    with driver.session() as session:
        session.run('RETURN 1')
    print('ok')
except Exception:
    raise SystemExit(1)
finally:
    try:
        driver.close()
    except Exception:
        pass
PY
  then
    mg_ready=1
    break
  fi
  sleep 1
done

if [[ "$mg_ready" -ne 1 ]]; then
  echo "Memgraph Bolt connection failed." >&2
  exit 1
fi

echo "PostgreSQL and Memgraph are ready."
