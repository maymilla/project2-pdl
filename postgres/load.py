import argparse
import csv
import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "postgres" / "schema.sql"


def load_env(path: Path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_connection_kwargs():
    env = load_env(ROOT / ".env")
    return {
        "host": env.get("PG_HOST", os.getenv("PG_HOST", "localhost")),
        "port": env.get("PG_PORT", os.getenv("PG_PORT", "5432")),
        "dbname": env.get("PG_DB", os.getenv("PG_DB", "gayang")),
        "user": env.get("PG_USER", os.getenv("PG_USER", "gayang")),
        "password": env.get("PG_PASSWORD", os.getenv("PG_PASSWORD", "gayang")),
    }


def run_schema(connection):
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    with connection.cursor() as cur:
        cur.execute(ddl)


def copy_csv(connection, table_name: str, csv_path: Path):
    with csv_path.open("rb") as fh:
        with connection.cursor() as cur:
            with cur.copy(f"COPY {table_name} FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
                while chunk := fh.read(1024 * 1024):
                    copy.write(chunk)


def load_all(connection, csv_dir: Path):
    tables = [
        ("pengguna", csv_dir / "pengguna.csv"),
        ("produk", csv_dir / "produk.csv"),
        ("pesanan", csv_dir / "pesanan.csv"),
        ("detail_pesanan", csv_dir / "detail_pesanan.csv"),
        ("produk_favorit", csv_dir / "produk_favorit.csv"),
    ]
    with connection.transaction():
        run_schema(connection)
        for table_name, csv_path in tables:
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing CSV file for {table_name}: {csv_path}")
            copy_csv(connection, table_name, csv_path)
        with connection.cursor() as cur:
            cur.execute("ANALYZE")


def main():
    parser = argparse.ArgumentParser(description="Load the generated benchmark CSV data into PostgreSQL.")
    parser.add_argument("--csv-dir", type=Path, default=ROOT / "data" / "out" / "dev")
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()

    conn = psycopg.connect(**get_connection_kwargs())
    try:
        if args.schema_only:
            run_schema(conn)
            conn.commit()
            print(f"Applied PostgreSQL schema at {SCHEMA_PATH}")
            return
        load_all(conn, args.csv_dir)
        print(f"Loaded PostgreSQL benchmark data from {args.csv_dir}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
