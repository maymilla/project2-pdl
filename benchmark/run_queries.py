import argparse
import csv
from datetime import datetime
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from neo4j import GraphDatabase
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
POSTGRES_QUERY_DIR = ROOT / "postgres" / "queries"
MEMGRAPH_QUERY_DIR = ROOT / "memgraph" / "queries"
OUTPUT_DIR = ROOT / "benchmark" / "results" / "outputs"
REPORT_PATH = OUTPUT_DIR / "query_run.txt"
QUERY_ORDER = (
    "q1_favorit",
    "q2_pembeli_berulang",
    "q3_jaccard",
    "q6_insert_pesanan",
    "q4_tandai_terjual",
    "q5_hapus_favorit",
)
METADATA_PATTERN = re.compile(r"^(?:--|//)\s*(type|params):\s*(.*?)\s*$")


@dataclass(frozen=True)
class Query:
    name: str
    query_type: str
    params: dict[str, Any]
    postgres: str
    memgraph: str


def load_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def setting(name: str, default: str, file_values: dict[str, str]) -> str:
    return os.environ.get(name, file_values.get(name, default))


def read_query(path: Path) -> tuple[str, dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    metadata: dict[str, str] = {}
    body_start = 0
    for index, line in enumerate(lines):
        match = METADATA_PATTERN.match(line.strip())
        if match:
            metadata[match.group(1)] = match.group(2)
            body_start = index + 1
            continue
        if not line.strip() or line.lstrip().startswith(("--", "//")):
            body_start = index + 1
            continue
        break

    missing = {"type", "params"} - metadata.keys()
    if missing:
        raise ValueError(f"{path} is missing query metadata: {', '.join(sorted(missing))}")
    query_type = metadata["type"]
    if query_type not in {"read", "write"}:
        raise ValueError(f"{path} has unsupported query type: {query_type!r}")
    try:
        params = json.loads(metadata["params"])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} has invalid JSON in its params header: {exc}") from exc
    if not isinstance(params, dict):
        raise ValueError(f"{path} params header must be a JSON object")
    query = "\n".join(lines[body_start:]).strip()
    if not query:
        raise ValueError(f"{path} contains no query")
    return query, {"type": query_type, "params": params}


def load_queries() -> list[Query]:
    sql_files = {path.stem: path for path in POSTGRES_QUERY_DIR.glob("*.sql")}
    cypher_files = {path.stem: path for path in MEMGRAPH_QUERY_DIR.glob("*.cypher")}
    if sql_files.keys() != cypher_files.keys():
        missing_cypher = sorted(sql_files.keys() - cypher_files.keys())
        missing_sql = sorted(cypher_files.keys() - sql_files.keys())
        raise ValueError(
            f"Unpaired query files; missing Cypher: {missing_cypher}; missing SQL: {missing_sql}"
        )

    queries = []
    for name in sorted(sql_files):
        sql, sql_metadata = read_query(sql_files[name])
        cypher, cypher_metadata = read_query(cypher_files[name])
        if sql_metadata != cypher_metadata:
            raise ValueError(f"Query metadata differs between SQL and Cypher for {name}")
        queries.append(
            Query(
                name=name,
                query_type=sql_metadata["type"],
                params=sql_metadata["params"],
                postgres=sql,
                memgraph=cypher,
            )
        )
    return queries


def connect_postgres(file_values: dict[str, str]) -> psycopg.Connection:
    return psycopg.connect(
        host=setting("PG_HOST", "localhost", file_values),
        port=setting("PG_PORT", "5432", file_values),
        dbname=setting("PG_DB", "gayang", file_values),
        user=setting("PG_USER", "gayang", file_values),
        password=setting("PG_PASSWORD", "gayang", file_values),
    )


def connect_memgraph(file_values: dict[str, str]):
    uri = setting("MG_URI", "bolt://localhost:7687", file_values)
    user = setting("MG_USER", "", file_values)
    password = setting("MG_PASSWORD", "", file_values)
    auth = (user, password) if user or password else None
    return GraphDatabase.driver(uri, auth=auth)


def execute_postgres(connection: psycopg.Connection, query: Query) -> tuple[list[str], list[dict[str, Any]], float]:
    started = time.perf_counter()
    with connection.transaction():
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query.postgres, query.params)
            if query.name == "q6_insert_pesanan":
                expected_rows = len(query.params["id_produk_arr"])
                if cursor.rowcount != expected_rows:
                    raise RuntimeError(
                        f"PostgreSQL Q6 inserted {cursor.rowcount} detail rows; expected {expected_rows}. "
                        "The transaction was rolled back."
                    )
                columns = ["id_pesanan", "detail_rows"]
                rows = [{
                    "id_pesanan": query.params["id_pesanan"],
                    "detail_rows": cursor.rowcount,
                }]
            elif cursor.description is None:
                columns = ["affected_rows"]
                rows = [{"affected_rows": cursor.rowcount}]
            else:
                columns = [column.name for column in cursor.description]
                rows = cursor.fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return columns, rows, elapsed_ms


def execute_memgraph(driver, query: Query) -> tuple[list[str], list[dict[str, Any]], float]:
    started = time.perf_counter()
    with driver.session() as session:
        if query.query_type == "read":
            def read_transaction(tx):
                result = tx.run(query.memgraph, **query.params)
                columns = list(result.keys())
                return columns, result.data()

            columns, rows = session.execute_read(read_transaction)
        else:
            def write_transaction(tx):
                result = tx.run(query.memgraph, **query.params)
                columns = list(result.keys())
                rows = result.data()
                if query.name == "q6_insert_pesanan":
                    expected_rows = len(query.params["id_produk_arr"])
                    if not rows or rows[0]["detail_rows"] != expected_rows:
                        actual_rows = rows[0]["detail_rows"] if rows else 0
                        raise RuntimeError(
                            f"Memgraph Q6 inserted {actual_rows} detail rows; expected {expected_rows}. "
                            "The transaction was rolled back."
                        )
                return columns, rows

            columns, rows = session.execute_write(write_transaction)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return columns, rows, elapsed_ms


def write_results(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def format_result_table(columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    if not columns:
        return ["(no columns)"]
    values = [[str(row.get(column, "")) for column in columns] for row in rows]
    widths = [
        max([len(column), *(len(row[index]) for row in values)])
        for index, column in enumerate(columns)
    ]
    header = " | ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
    separator = "-+-".join("-" * width for width in widths)
    lines = [header, separator]
    lines.extend(
        " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in values
    )
    if not rows:
        lines.append("(no rows)")
    return lines


def record_query_result(
    report: list[str],
    engine: str,
    name: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    elapsed_ms: float,
    csv_path: Path,
) -> None:
    lines = [
        f"{engine} {name}: {len(rows)} row(s), {elapsed_ms:.2f} ms",
        f"CSV: {csv_path}",
        *format_result_table(columns, rows),
        "",
    ]
    report.extend(lines)
    print("\n".join(lines))


def parse_parameter_overrides(values: list[str]) -> dict[str, Any]:
    overrides = {}
    for value in values:
        name, separator, raw_value = value.partition("=")
        if not separator or not name:
            raise ValueError(f"Invalid parameter override {value!r}; expected name=JSON_VALUE")
        try:
            overrides[name] = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON value for parameter {name!r}: {exc}") from exc
    return overrides


def run(
    engine: str,
    selected_names: set[str],
    param_overrides: dict[str, Any] | None = None,
    output_dir: Path = OUTPUT_DIR,
    memgraph_first: bool = False,
) -> None:
    queries_by_name = {query.name: query for query in load_queries()}
    unknown = selected_names - queries_by_name.keys()
    if unknown:
        raise ValueError(f"Unknown query name(s): {', '.join(sorted(unknown))}")
    overrides = param_overrides or {}
    applicable_params = set().union(*(queries_by_name[name].params for name in selected_names))
    unknown_params = overrides.keys() - applicable_params
    if unknown_params:
        raise ValueError(f"Unknown parameter name(s): {', '.join(sorted(unknown_params))}")
    for name in selected_names:
        query = queries_by_name[name]
        query_overrides = {key: value for key, value in overrides.items() if key in query.params}
        queries_by_name[name] = Query(
            name=query.name,
            query_type=query.query_type,
            params={**query.params, **query_overrides},
            postgres=query.postgres,
            memgraph=query.memgraph,
        )
    names = [name for name in QUERY_ORDER if name in selected_names]
    names.extend(sorted(selected_names - set(names)))
    file_values = load_env(ROOT / ".env")
    report = [
        "Query run results",
        f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Engines: {engine}",
        f"Queries: {', '.join(names)}",
        "Execution order: paired by query "
        f"({'Memgraph then PostgreSQL' if memgraph_first else 'PostgreSQL then Memgraph'})",
        "",
    ]

    connection = connect_postgres(file_values) if engine in {"both", "postgres"} else None
    driver = connect_memgraph(file_values) if engine in {"both", "memgraph"} else None
    try:
        for name in names:
            query = queries_by_name[name]
            engines = ("memgraph", "postgres") if memgraph_first else ("postgres", "memgraph")
            for current_engine in engines:
                if current_engine == "postgres" and connection is not None:
                    columns, rows, elapsed_ms = execute_postgres(connection, query)
                elif current_engine == "memgraph" and driver is not None:
                    columns, rows, elapsed_ms = execute_memgraph(driver, query)
                else:
                    continue
                output = output_dir / f"{name}_{current_engine}.csv"
                write_results(output, columns, rows)
                record_query_result(
                    report,
                    "PostgreSQL" if current_engine == "postgres" else "Memgraph",
                    name,
                    columns,
                    rows,
                    elapsed_ms,
                    output,
                )
    finally:
        if connection is not None:
            connection.close()
        if driver is not None:
            driver.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / REPORT_PATH.name
    report_path.write_text("\n".join(report).rstrip() + "\n", encoding="utf-8")
    print(f"Text report: {report_path}")


def explain_postgres(connection: psycopg.Connection, query: Query) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)\n" + query.postgres,
            query.params,
        )
        return "\n".join(row[0] for row in cursor.fetchall())


def profile_memgraph(driver, query: Query) -> str:
    with driver.session() as session:
        result = session.run("PROFILE\n" + query.memgraph, **query.params)
        summary = result.consume()
        profile = summary.profile
        if profile is None:
            raise RuntimeError(f"Memgraph returned no PROFILE details for {query.name}")
        if isinstance(profile, str):
            return profile
        return json.dumps(profile, indent=2, default=str)


def run_plans(
    engine: str,
    selected_names: set[str],
    param_overrides: dict[str, Any] | None = None,
    output_dir: Path = OUTPUT_DIR,
) -> None:
    queries_by_name = {query.name: query for query in load_queries()}
    unknown = selected_names - queries_by_name.keys()
    if unknown:
        raise ValueError(f"Unknown query name(s): {', '.join(sorted(unknown))}")
    overrides = param_overrides or {}
    applicable_params = set().union(*(queries_by_name[name].params for name in selected_names))
    unknown_params = overrides.keys() - applicable_params
    if unknown_params:
        raise ValueError(f"Unknown parameter name(s): {', '.join(sorted(unknown_params))}")
    for name in selected_names:
        query = queries_by_name[name]
        query_overrides = {key: value for key, value in overrides.items() if key in query.params}
        queries_by_name[name] = Query(
            name=query.name,
            query_type=query.query_type,
            params={**query.params, **query_overrides},
            postgres=query.postgres,
            memgraph=query.memgraph,
        )

    names = [name for name in QUERY_ORDER if name in selected_names]
    report = [
        "Query execution plans",
        f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Engines: {engine}",
        f"Queries: {', '.join(names)}",
        "PostgreSQL plans run in order inside one transaction and are rolled back "
        "afterward; Memgraph PROFILE uses single auto-commit queries, so write "
        "profiles may mutate data.",
        "",
    ]
    file_values = load_env(ROOT / ".env")
    connection = connect_postgres(file_values) if engine in {"both", "postgres"} else None
    driver = connect_memgraph(file_values) if engine in {"both", "memgraph"} else None
    try:
        for name in names:
            query = queries_by_name[name]
            if connection is not None:
                plan = explain_postgres(connection, query)
                report.extend([f"PostgreSQL EXPLAIN ANALYZE {name}", plan, ""])
            if driver is not None:
                profile = profile_memgraph(driver, query)
                report.extend([f"Memgraph PROFILE {name}", profile, ""])
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()
        if driver is not None:
            driver.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "query_plans.txt"
    report_path.write_text("\n".join(report).rstrip() + "\n", encoding="utf-8")
    print(f"Plan report: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired PostgreSQL and Memgraph queries.")
    parser.add_argument(
        "--engine",
        choices=("both", "postgres", "memgraph"),
        default="both",
        help="Database engine to run (default: both).",
    )
    parser.add_argument(
        "--query",
        nargs="+",
        help="Run only these query file stems, for example q1_favorit q3_jaccard.",
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=JSON_VALUE",
        help="Override a query parameter, for example --param id=54928.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for this run's CSV and text report.",
    )
    parser.add_argument(
        "--plans-only",
        action="store_true",
        help="Write PostgreSQL EXPLAIN ANALYZE and Memgraph PROFILE plans without timed runs.",
    )
    parser.add_argument(
        "--memgraph-first",
        action="store_true",
        help="Run Memgraph before PostgreSQL for each paired query.",
    )
    args = parser.parse_args()
    all_names = {query.name for query in load_queries()}
    selected_names = set(args.query) if args.query else all_names
    overrides = parse_parameter_overrides(args.param)
    if args.plans_only:
        run_plans(args.engine, selected_names, overrides, args.output_dir)
    else:
        run(args.engine, selected_names, overrides, args.output_dir, args.memgraph_first)


if __name__ == "__main__":
    main()
