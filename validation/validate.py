import argparse
import csv
import os
from pathlib import Path

import psycopg
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]


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


def get_pg_connection():
    env = load_env(ROOT / ".env")
    for key in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD"):
        if key in os.environ:
            env[key] = os.environ[key]
    return psycopg.connect(
        host=env.get("PG_HOST", "localhost"),
        port=env.get("PG_PORT", "5432"),
        dbname=env.get("PG_DB", "gayang"),
        user=env.get("PG_USER", "gayang"),
        password=env.get("PG_PASSWORD", "gayang"),
    )


def get_mg_driver():
    env = load_env(ROOT / ".env")
    uri = env.get("MG_URI", "bolt://localhost:7687")
    user = env.get("MG_USER", "")
    password = env.get("MG_PASSWORD", "")
    return GraphDatabase.driver(uri, auth=(user, password) if user or password else None)


def count_csv_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def count_pg_tables(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM pengguna")
        pengguna = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM produk")
        produk = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM pesanan")
        pesanan = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM detail_pesanan")
        detail = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM produk_favorit")
        favorit = cur.fetchone()[0]
    return {
        "pengguna": pengguna,
        "produk": produk,
        "pesanan": pesanan,
        "detail_pesanan": detail,
        "produk_favorit": favorit,
    }


def count_mg_nodes(driver):
    with driver.session() as session:
        pengguna = session.run("MATCH (n:Pengguna) RETURN count(n) AS c").single()[0]
        produk = session.run("MATCH (n:Produk) RETURN count(n) AS c").single()[0]
        pesanan = session.run("MATCH (n:Pesanan) RETURN count(n) AS c").single()[0]
        detail = session.run("MATCH ()-[r:BERISI]->() RETURN count(r) AS c").single()[0]
        favorit = session.run("MATCH ()-[r:MENYUKAI]->() RETURN count(r) AS c").single()[0]
    return {
        "pengguna": pengguna,
        "produk": produk,
        "pesanan": pesanan,
        "detail_pesanan": detail,
        "produk_favorit": favorit,
    }


def verify(profile: str):
    csv_dir = ROOT / "data" / "out" / profile
    csv_counts = {
        "pengguna": count_csv_rows(csv_dir / "pengguna.csv"),
        "produk": count_csv_rows(csv_dir / "produk.csv"),
        "pesanan": count_csv_rows(csv_dir / "pesanan.csv"),
        "detail_pesanan": count_csv_rows(csv_dir / "detail_pesanan.csv"),
        "produk_favorit": count_csv_rows(csv_dir / "produk_favorit.csv"),
    }

    pg_conn = get_pg_connection()
    mg_driver = get_mg_driver()
    try:
        pg_counts = count_pg_tables(pg_conn)
        mg_counts = count_mg_nodes(mg_driver)
    finally:
        pg_conn.close()
        mg_driver.close()

    checks = [
        ("pengguna", pg_counts["pengguna"], mg_counts["pengguna"], csv_counts["pengguna"]),
        ("produk", pg_counts["produk"], mg_counts["produk"], csv_counts["produk"]),
        ("pesanan", pg_counts["pesanan"], mg_counts["pesanan"], csv_counts["pesanan"]),
        ("detail_pesanan", pg_counts["detail_pesanan"], mg_counts["detail_pesanan"], csv_counts["detail_pesanan"]),
        ("produk_favorit", pg_counts["produk_favorit"], mg_counts["produk_favorit"], csv_counts["produk_favorit"]),
    ]

    failures = []
    for name, pg_value, mg_value, expected in checks:
        if pg_value != expected or mg_value != expected or pg_value != mg_value:
            failures.append((name, pg_value, mg_value, expected))

    if failures:
        for name, pg_value, mg_value, expected in failures:
            print(f"FAIL {name}: PG={pg_value}, MG={mg_value}, expected={expected}")
        raise SystemExit(1)

    print("PASS: all row-count checks match the CSV source.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare PostgreSQL and Memgraph data against the generated CSV.")
    parser.add_argument("--profile", default="dev")
    args = parser.parse_args()
    verify(args.profile)
