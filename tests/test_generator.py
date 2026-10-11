import csv
import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_generator_is_deterministic_and_valid(tmp_path):
    output_a = tmp_path / "run_a"
    output_b = tmp_path / "run_b"

    for output in (output_a, output_b):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "data" / "generate.py"),
                "--profile",
                "dev",
                "--seed",
                "20260101",
                "--output-dir",
                str(output),
            ],
            check=True,
            cwd=str(ROOT),
        )

    for filename in [
        "pengguna.csv",
        "produk.csv",
        "pesanan.csv",
        "detail_pesanan.csv",
        "produk_favorit.csv",
    ]:
        assert _sha256(output_a / filename) == _sha256(output_b / filename)

    profile = yaml.safe_load((ROOT / "config" / "profiles.yaml").read_text(encoding="utf-8"))["dev"]
    for dataset, expected_rows in (
        ("pengguna.csv", profile["pengguna"]),
        ("produk.csv", profile["produk"]),
        ("pesanan.csv", profile["pesanan"]),
        ("produk_favorit.csv", profile["produk_favorit"]),
    ):
        with (output_a / dataset).open("r", encoding="utf-8", newline="") as fh:
            assert sum(1 for _ in csv.DictReader(fh)) == expected_rows
