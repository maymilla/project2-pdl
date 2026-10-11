# Gayang Data Project

Implementasi lingkungan PostgreSQL + Memgraph sesuai kebutuhan proyek.

## Versi yang dipakai

- PostgreSQL: `postgres:16`
- Memgraph: `memgraph/memgraph:2.18.0`
- Memgraph Lab: `memgraph/lab`
- Python: 3.11+

## Fast start

1. Buat environment lokal:
   ```bash
   python -m venv .venv
   . .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Jalankan database:
   ```bash
   ./scripts/up.sh
   ```
3. Seed dataset dev:
   ```bash
   ./scripts/seed.sh dev 20260101
   ```
   Untuk dataset medium:
   ```bash
   ./scripts/seed.sh medium 20260101
   ```
4. Atau generate manual:
   ```bash
   python data/generate.py --profile dev --seed 20260101
   ```

## Struktur utama

- `data/generate.py`: deterministic generator CSV
- `data/invariants.py`: validasi invariant wajib
- `postgres/schema.sql`: DDL PostgreSQL
- `postgres/load.py`: COPY ke PostgreSQL
- `memgraph/schema.cypher`: index Memgraph
- `memgraph/load.py`: load node + relationship ke Memgraph
- `validation/validate.py`: validasi hasil final
- `scripts/up.sh`, `reset.sh`, `seed.sh`: alur operasional

## Perintah lengkap

```bash
# 1. bangun container
./scripts/up.sh

# 2. reset schema
./scripts/reset.sh

# 3. generate dataset
python data/generate.py --profile dev --seed 20260101

# 4. load PostgreSQL
python postgres/load.py --csv-dir data/out/dev

# 5. load Memgraph
python memgraph/load.py --csv-dir data/out/dev

# 6. validasi
python validation/validate.py --profile dev
```

## Catatan verifikasi dan temuan

1. Tag Memgraph dipakai: `memgraph/memgraph:2.18.0`.
   - Volume data dipasang di `/var/lib/memgraph` pada container.
   - `docker compose` menjalankan container utama dengan Bolt port 7687 dan port 7444. Memgraph Lab tersedia pada port 3000 jika profile `lab` diaktifkan.
2. Constraint unik Memgraph: untuk versi dan sintaks yang dipakai, constraint unik belum ditambahkan ke `schema.cypher` karena kompatibilitas versi dapat bervariasi. Daftar index dibuat tetap; jika versi Memgraph yang digunakan mendukung `CREATE CONSTRAINT`, dapat ditambahkan tanpa mengubah model data.
3. Tipe `date` Memgraph: `date(r.tanggal_daftar)` dan `date(r.tanggal_pesanan)` dipakai saat load. Fungsi ini sesuai pola tanggal ISO `YYYY-MM-DD` dan kompatibel untuk perbandingan serta extract tanggal.
4. `shortestPath` / pola relationship panjang variabel: belum diuji pada implementasi ini; perlu diverifikasi jika query terkait digunakan.
5. Estimasi RAM Memgraph untuk profile medium/large: belum diverifikasi secara eksplisit di runtime. Disarankan mengecek dokumentasi storage Memgraph untuk profil target sebelum menjalankan `medium` atau `large` di mesin yang terbatas.
6. `COPY` PostgreSQL via `psycopg` versi 3: didukung. Loader menggunakan `cursor.copy(..., FORMAT csv, HEADER true)` dan mengirim data secara streaming.

## Catatan implementasi

- Semua data generator deterministik menggunakan satu instance `random.Random(seed)`.
- Generator akan gagal bila invariant `I1` sampai `I15` tidak terpenuhi.
- `.env` dipakai untuk konfigurasi koneksi; file `.env` tidak disertakan di repo.
- Reset Memgraph dilakukan melalui reinitialisasi schema in-memory dan penghapusan data akibat reset connect; ini sesuai pendekatan yang dijelaskan dalam spec.
