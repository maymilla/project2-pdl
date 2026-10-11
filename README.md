# Gayang Data Project

Implementasi lingkungan PostgreSQL + Memgraph sesuai kebutuhan proyek Gayang (e-commerce sederhana). Dataset dihasilkan secara deterministik, memuat ke kedua DBMS, dan menjalankan query berpasangan Q1–Q6. Hasil query disimpan ke CSV dan laporan waktu. 

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
- `postgres/queries/`, `memgraph/queries/`: query berpasangan Q1–Q6
- `benchmark/run_queries.py`: menjalankan query dan menyimpan hasil CSV serta laporan waktu

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

## Menjalankan query

Setelah kedua database di-seed, jalankan semua query dan simpan hasil ke
`benchmark/results/outputs/`. CSV hasil query disertai file `query_run.txt`
yang berisi tabel hasil dan durasi tiap query. Gunakan `--output-dir` berbeda
untuk setiap percobaan agar hasil tidak tertimpa:

```bash
python benchmark/run_queries.py
```

Runner menerima `--engine postgres|memgraph|both` dan `--query` yang diikuti
nama file query tanpa ekstensi. Contoh:

```bash
python benchmark/run_queries.py --engine postgres --query q1_favorit q3_jaccard
```

Nilai parameter di header bisa diubah saat dijalankan, misalnya:

```bash
python benchmark/run_queries.py --query q3_jaccard --param id=54928
```

Q6 dijalankan sebelum Q4 dan Q5 karena memerlukan produk berstatus tersedia.
Q4 dan Q5 mengubah data, sedangkan Q6 memakai ID pesanan tetap; load ulang
kedua database sebelum setiap percobaan. Urutan eksekusi Q1, Q2, Q3, Q6, Q4,
lalu Q5. Saat kedua DBMS dipilih, runner menjalankan setiap query berpasangan
(PostgreSQL kemudian Memgraph) sebelum beralih ke query berikutnya.
Gunakan `--memgraph-first` pada sebagian percobaan untuk menyeimbangkan urutan
DBMS, misalnya bergantian di antara empat percobaan.

Q3 mengukur Jaccard kesamaan himpunan penjual dari pesanan berstatus selesai
dan menggunakan `id_pengguna` sebagai pengurutan sekunder ketika skor seri.

Pemeriksaan rencana eksekusi disimpan terpisah dan tidak masuk ke waktu
percobaan:

```bash
python benchmark/run_queries.py --plans-only --output-dir benchmark/results/outputs/plans
```

PostgreSQL memakai `EXPLAIN ANALYZE` dengan statistik buffer dan me-rollback
hasil query tulis. Memgraph menjalankan `PROFILE` sebagai query auto-commit
tunggal; query tulis di sana dapat mengubah data. Load ulang kedua DBMS setelah
mengambil plan dan sebelum timed run. Schema PostgreSQL menambahkan indeks
`pesanan(status_pesanan)` untuk kondisi filter pada Q4.
