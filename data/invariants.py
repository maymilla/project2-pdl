import csv
from collections import defaultdict
from datetime import date
from pathlib import Path


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _to_int(value):
    return int(value)


def validate_data_dir(output_dir: str | Path) -> bool:
    base = Path(output_dir)
    expected_files = {
        "pengguna.csv",
        "produk.csv",
        "pesanan.csv",
        "detail_pesanan.csv",
        "produk_favorit.csv",
    }
    missing = sorted(str(base / name) for name in sorted(expected_files) if not (base / name).exists())
    if missing:
        raise ValueError(f"Missing required CSV(s): {missing}")

    pengguna = _read_csv(base / "pengguna.csv")
    produk = _read_csv(base / "produk.csv")
    pesanan = _read_csv(base / "pesanan.csv")
    detail_pesanan = _read_csv(base / "detail_pesanan.csv")
    produk_favorit = _read_csv(base / "produk_favorit.csv")

    errors: list[str] = []

    pengguna_ids = {int(r["id_pengguna"]) for r in pengguna}
    produk_ids = {int(r["id_produk"]) for r in produk}
    pesanan_ids = {int(r["id_pesanan"]) for r in pesanan}

    # I1
    for row in produk:
        if int(row["id_penjual"]) not in pengguna_ids:
            errors.append(f"I1: id_penjual {row['id_penjual']} tidak ada di pengguna")

    # I2
    for row in pesanan:
        if int(row["id_pembeli"]) not in pengguna_ids:
            errors.append(f"I2: id_pembeli {row['id_pembeli']} tidak ada di pengguna")
        if int(row["id_penjual"]) not in pengguna_ids:
            errors.append(f"I2: id_penjual {row['id_penjual']} tidak ada di pengguna")

    # I3
    for row in pesanan:
        if int(row["id_pembeli"]) == int(row["id_penjual"]):
            errors.append(f"I3: pembeli dan penjual sama pada pesanan {row['id_pesanan']}")

    # I4 & I5
    for row in detail_pesanan:
        if int(row["id_pesanan"]) not in pesanan_ids:
            errors.append(f"I4: id_pesanan {row['id_pesanan']} tidak ada di pesanan")
        if int(row["id_produk"]) not in produk_ids:
            errors.append(f"I5: id_produk {row['id_produk']} tidak ada di produk")

    produk_by_id = {int(r["id_produk"]): r for r in produk}
    pesanan_by_id = {int(r["id_pesanan"]): r for r in pesanan}
    pengguna_by_id = {int(r["id_pengguna"]): r for r in pengguna}
    details_by_pesanan = defaultdict(list)
    for row in detail_pesanan:
        details_by_pesanan[int(row["id_pesanan"])].append(row)

    # I6
    for row in detail_pesanan:
        produk_row = produk_by_id[int(row["id_produk"])]
        pesanan_row = pesanan_by_id[int(row["id_pesanan"])]
        if int(produk_row["id_penjual"]) != int(pesanan_row["id_penjual"]):
            errors.append(
                f"I6: produk {row['id_produk']} dijual oleh penjual {produk_row['id_penjual']} "
                f"tetapi pesanan {row['id_pesanan']} milik penjual {pesanan_row['id_penjual']}"
            )

    # I7, I8, I9, I10, I11
    seen_by_pesanan = defaultdict(set)
    seen_by_produk = set()
    for row in detail_pesanan:
        pid = int(row["id_pesanan"])
        prod_id = int(row["id_produk"])
        if prod_id in seen_by_pesanan[pid]:
            errors.append(f"I7/I8: produk {prod_id} muncul lebih dari sekali dalam pesanan {pid}")
        seen_by_pesanan[pid].add(prod_id)
        if prod_id in seen_by_produk:
            errors.append(f"I7: produk {prod_id} muncul di lebih dari satu pesanan")
        seen_by_produk.add(prod_id)

        if int(row["jumlah"]) != 1:
            errors.append(f"I9: jumlah untuk detail {pid}/{row['id_produk']} bukan 1")
        if int(row["harga"]) != int(produk_by_id[prod_id]["harga_jual"]):
            errors.append(f"I10: harga detail {pid}/{prod_id} tidak sama dengan harga_jual")

    # I8 uniqueness of (id_pesanan, no_urut)
    seen_urut = set()
    for row in detail_pesanan:
        key = (int(row["id_pesanan"]), int(row["no_urut"]))
        if key in seen_urut:
            errors.append(f"I8: duplikat (id_pesanan, no_urut) = {key}")
        seen_urut.add(key)

    # I11 no cancelled order details
    cancelled_ids = {int(r["id_pesanan"]) for r in pesanan if r["status_pesanan"] == "dibatalkan"}
    for row in detail_pesanan:
        if int(row["id_pesanan"]) in cancelled_ids:
            errors.append(f"I11: pesanan dibatalkan {row['id_pesanan']} memiliki detail_pesanan")

    # I12 uniqueness of favorite pairs
    favorite_pairs = set()
    for row in produk_favorit:
        pair = (int(row["id_pengguna"]), int(row["id_produk"]))
        if pair in favorite_pairs:
            errors.append(f"I12: duplikat pair favorit {pair}")
        favorite_pairs.add(pair)

    # I13 email uniqueness
    emails = set()
    for row in pengguna:
        if row["email"] in emails:
            errors.append(f"I13: alamat email duplikat: {row['email']}")
        emails.add(row["email"])

    # I14 date range and ordering
    def parse_date(value: str):
        return date.fromisoformat(value)

    earliest_user = date(2024, 1, 1)
    latest_user = date(2026, 6, 30)
    for row in pengguna:
        d = parse_date(row["tanggal_daftar"])
        if not (earliest_user <= d <= latest_user):
            errors.append(f"I14: tanggal_daftar pengguna {row['id_pengguna']} di luar rentang")

    for row in produk:
        d = parse_date(row["tanggal_dibuat"])
        seller_date = pengguna_by_id[int(row["id_penjual"])]["tanggal_daftar"]
        if d <= parse_date(seller_date):
            errors.append(f"I14: tanggal_dibuat produk {row['id_produk']} tidak setelah tanggal_daftar penjual")
        if d >= date(2026, 10, 11):
            errors.append(f"I14: tanggal_dibuat produk {row['id_produk']} tidak sebelum 2026-10-11")

    for row in pesanan:
        d = parse_date(row["tanggal_pesanan"])
        if d >= date(2026, 10, 11):
            errors.append(f"I14: tanggal_pesanan {row['id_pesanan']} tidak sebelum 2026-10-11")
        first_product_date = None
        for detail in details_by_pesanan[int(row["id_pesanan"])]:
            product_row = produk_by_id[int(detail["id_produk"])]
            product_date = parse_date(product_row["tanggal_dibuat"])
            first_product_date = product_date if first_product_date is None else max(first_product_date, product_date)
        if first_product_date is not None and d <= first_product_date:
            errors.append(f"I14: tanggal_pesanan {row['id_pesanan']} tidak setelah produk pertama dalam pesanan")

    # I15 status produk harus tersedia
    for row in produk:
        if row["status_produk"] != "tersedia":
            errors.append(f"I15: status produk {row['id_produk']} bukan tersedia")

    if errors:
        raise ValueError("\n".join(errors))
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate generated CSV data against the mandatory invariants.")
    parser.add_argument("--output-dir", default="data/out/dev", type=Path)
    args = parser.parse_args()
    validate_data_dir(args.output_dir)
    print(f"All invariants passed for {args.output_dir}")
