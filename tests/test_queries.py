import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.run_queries import (
    QUERY_ORDER,
    format_result_table,
    load_queries,
    parse_parameter_overrides,
)


def test_query_pairs_have_matching_metadata():
    queries = load_queries()

    assert len(queries) == 6
    assert {query.name for query in queries} == {
        "q1_favorit",
        "q2_pembeli_berulang",
        "q3_jaccard",
        "q4_tandai_terjual",
        "q5_hapus_favorit",
        "q6_insert_pesanan",
    }
    assert all(query.query_type in {"read", "write"} for query in queries)


def test_query_order_runs_reads_before_writes():
    assert QUERY_ORDER == (
        "q1_favorit",
        "q2_pembeli_berulang",
        "q3_jaccard",
        "q6_insert_pesanan",
        "q4_tandai_terjual",
        "q5_hapus_favorit",
    )


def test_q3_uses_a_stable_user_id_tiebreaker():
    query = next(query for query in load_queries() if query.name == "q3_jaccard")

    assert "ORDER BY jaccard DESC, sh.id_pengguna" in query.postgres
    assert "ORDER BY jaccard DESC, id_pengguna" in query.memgraph


def test_q6_sql_is_a_single_statement():
    query = next(query for query in load_queries() if query.name == "q6_insert_pesanan")

    assert query.query_type == "write"
    assert query.postgres.count(";") == 1
    assert set(query.params) == {
        "id_pesanan",
        "id_pembeli",
        "id_penjual",
        "id_produk_arr",
    }
    assert query.params["id_produk_arr"]


def test_parameter_overrides_parse_json_values():
    assert parse_parameter_overrides(["id=54928", "id_produk_arr=[11,12]"]) == {
        "id": 54928,
        "id_produk_arr": [11, 12],
    }


def test_result_table_includes_query_output_and_empty_state():
    assert format_result_table(["id", "name"], [{"id": 1, "name": "Ayu"}]) == [
        "id | name",
        "---+-----",
        "1  | Ayu ",
    ]
    assert format_result_table(["id"], []) == ["id", "--", "(no rows)"]
