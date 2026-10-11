import argparse
import csv
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "memgraph" / "schema.cypher"


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


def get_driver():
    env = load_env(ROOT / ".env")
    uri = env.get("MG_URI", "bolt://localhost:7687")
    user = env.get("MG_USER", "")
    password = env.get("MG_PASSWORD", "")
    auth = (user, password) if user or password else None
    return GraphDatabase.driver(uri, auth=auth)


def run_cypher_file(driver, path: Path):
    content = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("//")
    )
    statements = [segment.strip() for segment in content.split(";") if segment.strip()]
    with driver.session() as session:
        for statement in statements:
            session.run(statement)


def _iter_rows(csv_path: Path):
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def _batch(iterable, batch_size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def load_nodes(driver, label: str, csv_path: Path):
    with driver.session() as session:
        for batch in _batch(_iter_rows(csv_path), 5000):
            rows = []
            for row in batch:
                rows.append(dict(row))

            if label == "Pengguna":
                session.run(
                    """
                    UNWIND $rows AS r
                    MERGE (n:Pengguna {id_pengguna: toInteger(r.id_pengguna)})
                    SET n.nama = r.nama,
                        n.email = r.email,
                        n.tanggal_daftar = date(r.tanggal_daftar)
                    """,
                    rows=rows,
                )
            elif label == "Produk":
                session.run(
                    """
                    UNWIND $rows AS r
                    MERGE (n:Produk {id_produk: toInteger(r.id_produk)})
                    SET n.id_penjual = toInteger(r.id_penjual),
                        n.nama_produk = r.nama_produk,
                        n.harga_jual = toInteger(r.harga_jual),
                        n.status_produk = r.status_produk,
                        n.tanggal_dibuat = date(r.tanggal_dibuat)
                    """,
                    rows=rows,
                )
            elif label == "Pesanan":
                session.run(
                    """
                    UNWIND $rows AS r
                    MERGE (n:Pesanan {id_pesanan: toInteger(r.id_pesanan)})
                    SET n.id_pembeli = toInteger(r.id_pembeli),
                        n.id_penjual = toInteger(r.id_penjual),
                        n.tanggal_pesanan = date(r.tanggal_pesanan),
                        n.status_pesanan = r.status_pesanan
                    """,
                    rows=rows,
                )


def load_relationships(driver, csv_path: Path, query: str):
    with driver.session() as session:
        for batch in _batch(_iter_rows(csv_path), 5000):
            session.run(query, rows=list(batch))


def main():
    parser = argparse.ArgumentParser(description="Load benchmark CSV data into Memgraph.")
    parser.add_argument("--csv-dir", type=Path, default=ROOT / "data" / "out" / "dev")
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()

    driver = get_driver()
    try:
        if args.schema_only:
            run_cypher_file(driver, SCHEMA_PATH)
            print(f"Applied Memgraph schema at {SCHEMA_PATH}")
            return

        run_cypher_file(driver, SCHEMA_PATH)
        load_nodes(driver, "Pengguna", args.csv_dir / "pengguna.csv")
        load_nodes(driver, "Produk", args.csv_dir / "produk.csv")
        load_nodes(driver, "Pesanan", args.csv_dir / "pesanan.csv")

        load_relationships(
            driver,
            args.csv_dir / "produk.csv",
            """
            UNWIND $rows AS r
            MATCH (u:Pengguna {id_pengguna: toInteger(r.id_penjual)})
            MATCH (p:Produk {id_produk: toInteger(r.id_produk)})
            MERGE (u)-[:MENJUAL]->(p)
            """,
        )
        load_relationships(
            driver,
            args.csv_dir / "pesanan.csv",
            """
            UNWIND $rows AS r
            MATCH (u:Pengguna {id_pengguna: toInteger(r.id_pembeli)})
            MATCH (o:Pesanan {id_pesanan: toInteger(r.id_pesanan)})
            MERGE (u)-[:MEMBUAT]->(o)
            """,
        )
        load_relationships(
            driver,
            args.csv_dir / "detail_pesanan.csv",
            """
            UNWIND $rows AS r
            MATCH (o:Pesanan {id_pesanan: toInteger(r.id_pesanan)})
            MATCH (p:Produk {id_produk: toInteger(r.id_produk)})
            MERGE (o)-[:BERISI {no_urut: toInteger(r.no_urut), jumlah: toInteger(r.jumlah), harga: toInteger(r.harga)}]->(p)
            """,
        )
        load_relationships(
            driver,
            args.csv_dir / "produk_favorit.csv",
            """
            UNWIND $rows AS r
            MATCH (u:Pengguna {id_pengguna: toInteger(r.id_pengguna)})
            MATCH (p:Produk {id_produk: toInteger(r.id_produk)})
            MERGE (u)-[:MENYUKAI]->(p)
            """,
        )

        print(f"Loaded Memgraph benchmark data from {args.csv_dir}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
