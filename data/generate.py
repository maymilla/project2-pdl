import argparse
import csv
import math
import random
from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.invariants import validate_data_dir


def _load_profiles(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _random_date(rng: random.Random, start: date, end: date) -> date:
    if start > end:
        raise ValueError(f"Invalid date range: start={start.isoformat()} end={end.isoformat()}")
    delta_days = (end - start).days
    return start + timedelta(days=rng.randint(0, delta_days))


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() for ch in value if ch.isalnum() or ch.isspace())
    return cleaned.replace(" ", ".")


def _weighted_choice(rng: random.Random, choices, weights):
    total = sum(weights)
    threshold = rng.random() * total
    cumulative = 0.0
    for choice, weight in zip(choices, weights):
        cumulative += weight
        if threshold <= cumulative:
            return choice
    return choices[-1]


@lru_cache(maxsize=8)
def _zipf_cumulative_weights(n: int, exponent: float) -> tuple[float, ...]:
    cumulative = []
    total = 0.0
    for rank in range(1, n + 1):
        total += 1.0 / (rank**exponent)
        cumulative.append(total)
    return tuple(cumulative)


def _zipf_sample(rng: random.Random, n: int, exponent: float = 1.1) -> int:
    cumulative = _zipf_cumulative_weights(n, exponent)
    target = rng.random() * cumulative[-1]
    return bisect_left(cumulative, target) + 1


def _generate_user_rows(count: int, rng: random.Random):
    first_names = [
        "Ayu", "Budi", "Citra", "Dewi", "Eko", "Fajar", "Gita", "Hendra", "Indra", "Joko",
        "Kartika", "Lukman", "Mega", "Nanda", "Omar", "Putri", "Raka", "Sari", "Tono", "Umi",
    ]
    last_names = [
        "Saputra", "Wijaya", "Pratama", "Purnama", "Siregar", "Hidayat", "Nugraha", "Ramadhan",
        "Santoso", "Hartono", "Kurniawan", "Suryadi", "Lestari", "Rizki", "Dewi", "Halim",
    ]
    rows = []
    for user_id in range(1, count + 1):
        first_name = first_names[rng.randrange(len(first_names))]
        last_name = last_names[rng.randrange(len(last_names))]
        name = f"{first_name} {last_name}"
        email = f"{_slugify(name)}.{user_id}@example.com"
        registered_on = _random_date(rng, date(2024, 1, 1), date(2026, 6, 30))
        rows.append({
            "id_pengguna": user_id,
            "nama": name,
            "email": email,
            "tanggal_daftar": registered_on.isoformat(),
        })
    return rows


def _assign_product_counts(total_products: int, seller_count: int, rng: random.Random):
    counts = {}
    remaining = total_products
    seller_ids = list(range(1, seller_count + 1))
    for index, seller_id in enumerate(seller_ids):
        if index == len(seller_ids) - 1:
            counts[seller_id] = remaining
            break
        p = 0.62
        count = max(1, int(math.floor(math.log(rng.random()) / math.log(1 - p))) + 1)
        count = min(count, remaining)
        counts[seller_id] = count
        remaining -= count
    return counts


def _generate_product_rows(user_rows, total_products: int, rng: random.Random):
    user_by_id = {int(row["id_pengguna"]): row for row in user_rows}
    seller_count = max(1, int(round(len(user_rows) * 0.8)))
    seller_ids = list(range(1, seller_count + 1))
    seller_product_counts = _assign_product_counts(total_products, seller_count, rng)

    product_names = [
        "Kaos", "Celana", "Jaket", "Blazer", "Sweater", "Topi", "Sepatu", "Sandal", "Tas", "Kemeja",
        "Dress", "Rok", "Hoodie", "Tunik", "Syal", "Kacamata", "Dompet", "Baju", "Jeans", "Kopi",
    ]
    item_suffixes = [
        "Muda", "Santai", "Urban", "Premium", "Casual", "Trend", "Formal", "Minimal", "Vintage", "Kulit",
    ]

    rows = []
    product_id = 1
    for seller_id in seller_ids:
        seller_date = date.fromisoformat(user_by_id[seller_id]["tanggal_daftar"])
        for _ in range(seller_product_counts.get(seller_id, 0)):
            name = f"{product_names[rng.randrange(len(product_names))]} {item_suffixes[rng.randrange(len(item_suffixes))]}"
            price = int(max(20000, min(2000000, round(math.exp(rng.gauss(math.log(150000), 1.0))))))
            created_date = _random_date(rng, seller_date + timedelta(days=1), date(2026, 10, 9))
            rows.append({
                "id_produk": product_id,
                "id_penjual": seller_id,
                "nama_produk": name,
                "harga_jual": price,
                "status_produk": "tersedia",
                "tanggal_dibuat": created_date.isoformat(),
            })
            product_id += 1
    return rows, seller_ids


def _generate_order_rows(product_rows, user_count: int, order_count: int, rng: random.Random):
    statuses = ["selesai", "dibayar", "menunggu_pembayaran", "dibatalkan"]
    weights = [70, 10, 10, 10]
    available_by_seller = defaultdict(list)
    for row in product_rows:
        available_by_seller[int(row["id_penjual"])].append(int(row["id_produk"]))

    product_by_id = {int(row["id_produk"]): row for row in product_rows}
    orders = []
    detail_rows = []
    history_by_seller = defaultdict(set)
    eligible_sellers = [seller_id for seller_id, product_ids in available_by_seller.items() if product_ids]
    seller_indexes = {seller_id: index for index, seller_id in enumerate(eligible_sellers)}

    for order_id in range(1, order_count + 1):
        status = _weighted_choice(rng, statuses, weights)
        if not eligible_sellers:
            raise ValueError("Tidak ada produk yang tersedia untuk membuat pesanan baru.")
        seller_id = rng.choice(eligible_sellers)

        if rng.random() < 0.2 and history_by_seller.get(seller_id):
            buyer_id = rng.choice(tuple(history_by_seller[seller_id]))
        else:
            buyer_id = rng.randint(1, user_count)
            while buyer_id == seller_id:
                buyer_id = rng.randint(1, user_count)

        desired_count = _weighted_choice(rng, [1, 2, 3], [60, 30, 10])
        product_ids = rng.sample(available_by_seller[seller_id], min(desired_count, len(available_by_seller[seller_id])))
        product_ids = sorted(product_ids)

        min_order_date = max((date.fromisoformat(product_by_id[pid]["tanggal_dibuat"]) for pid in product_ids), default=date(2024, 1, 1)) + timedelta(days=1)
        if status == "dibatalkan":
            order_date = _random_date(rng, min_order_date, date(2026, 10, 10))
        else:
            for pid in product_ids:
                available_by_seller[seller_id].remove(pid)
            if not available_by_seller[seller_id]:
                seller_index = seller_indexes.pop(seller_id)
                last_seller = eligible_sellers.pop()
                if seller_index < len(eligible_sellers):
                    eligible_sellers[seller_index] = last_seller
                    seller_indexes[last_seller] = seller_index
            order_date = _random_date(rng, min_order_date, date(2026, 10, 10))
            for no_urut, pid in enumerate(product_ids, start=1):
                detail_rows.append({
                    "id_pesanan": order_id,
                    "no_urut": no_urut,
                    "id_produk": pid,
                    "jumlah": 1,
                    "harga": product_by_id[pid]["harga_jual"],
                })

        orders.append({
            "id_pesanan": order_id,
            "id_pembeli": buyer_id,
            "id_penjual": seller_id,
            "tanggal_pesanan": order_date.isoformat(),
            "status_pesanan": status,
        })
        history_by_seller[seller_id].add(buyer_id)

    return orders, detail_rows


def _generate_favorites(user_count: int, product_rows, favorite_count: int, sold_product_ids, rng: random.Random):
    rows = []
    seen = set()
    sold_products = sorted(sold_product_ids)
    while len(rows) < favorite_count:
        user_id = rng.randint(1, user_count)
        if rng.random() < 0.3 and sold_products:
            product_id = rng.choice(sold_products)
        else:
            product_id = _zipf_sample(rng, len(product_rows))
        pair = (user_id, product_id)
        if pair in seen:
            continue
        seen.add(pair)
        rows.append({"id_pengguna": user_id, "id_produk": product_id})
    rows.sort(key=lambda row: (int(row["id_pengguna"]), int(row["id_produk"])))
    return rows


def generate_dataset(profile_name: str, seed: int, output_dir: str | Path):
    root_dir = Path(__file__).resolve().parents[1]
    profiles = _load_profiles(root_dir / "config" / "profiles.yaml")
    profile = profiles[profile_name]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    user_rows = _generate_user_rows(profile["pengguna"], rng)
    product_rows, _ = _generate_product_rows(user_rows, profile["produk"], rng)
    order_rows, detail_rows = _generate_order_rows(product_rows, profile["pengguna"], profile["pesanan"], rng)
    sold_product_ids = {int(row["id_produk"]) for row in detail_rows}
    favorite_rows = _generate_favorites(profile["pengguna"], product_rows, profile["produk_favorit"], sold_product_ids, rng)

    datasets = {
        "pengguna.csv": (
            ["id_pengguna", "nama", "email", "tanggal_daftar"],
            [[row["id_pengguna"], row["nama"], row["email"], row["tanggal_daftar"]] for row in user_rows],
        ),
        "produk.csv": (
            ["id_produk", "id_penjual", "nama_produk", "harga_jual", "status_produk", "tanggal_dibuat"],
            [
                [
                    row["id_produk"], row["id_penjual"], row["nama_produk"], row["harga_jual"], row["status_produk"], row["tanggal_dibuat"]
                ]
                for row in product_rows
            ],
        ),
        "pesanan.csv": (
            ["id_pesanan", "id_pembeli", "id_penjual", "tanggal_pesanan", "status_pesanan"],
            [
                [row["id_pesanan"], row["id_pembeli"], row["id_penjual"], row["tanggal_pesanan"], row["status_pesanan"]]
                for row in order_rows
            ],
        ),
        "detail_pesanan.csv": (
            ["id_pesanan", "no_urut", "id_produk", "jumlah", "harga"],
            [
                [row["id_pesanan"], row["no_urut"], row["id_produk"], row["jumlah"], row["harga"]]
                for row in detail_rows
            ],
        ),
        "produk_favorit.csv": (
            ["id_pengguna", "id_produk"],
            [[row["id_pengguna"], row["id_produk"]] for row in favorite_rows],
        ),
    }

    for filename, (header, rows) in datasets.items():
        with (output_path / filename).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)

    validate_data_dir(output_path)
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate deterministic benchmark CSVs.")
    parser.add_argument("--profile", default="dev", choices=["dev", "medium", "large"])
    parser.add_argument("--seed", type=int, default=20260101)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    output_dir = args.output_dir or Path("data") / "out" / args.profile
    generate_dataset(args.profile, args.seed, output_dir)
    print(f"Generated {args.profile} dataset with seed {args.seed} at {output_dir}")
