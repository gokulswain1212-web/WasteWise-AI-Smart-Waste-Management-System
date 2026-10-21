from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError


BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import database_configured, get_engine  # noqa: E402


RAW_DATA = ROOT / "ml" / "data" / "raw"
ARTIFACTS = ROOT / "artifacts"
SCHEMA_PATH = ROOT / "database" / "schema.sql"
CSV_TABLES = {
    RAW_DATA / "products.csv": "products",
    RAW_DATA / "inventory_batches.csv": "inventory_batches",
    RAW_DATA / "perishable_inventory - perishable_inventory.csv": "perishable_inventory",
    ARTIFACTS / "discount_recommendations.csv": "discount_recommendations",
}
EXCLUDED_CSV_DATASETS = {
    RAW_DATA / "discount_scenarios_simulated (1).csv": (
        "not imported: database/schema.sql has no reviewed discount_scenarios "
        "table definition"
    )
}
SCHEMA_TABLE_PATTERN = r"CREATE TABLE IF NOT EXISTS `(\w+)`"


def load_datasets() -> dict[str, pd.DataFrame]:
    datasets: dict[str, pd.DataFrame] = {}
    for path, table_name in CSV_TABLES.items():
        if not path.exists():
            if table_name == "discount_recommendations":
                print(f"Skipping {table_name}: train the models to create {path.name}.")
                continue
            raise FileNotFoundError(f"Required dataset is missing: {path}")
        datasets[table_name] = pd.read_csv(path)
    return datasets


def parse_schema_statements(schema_sql: str) -> list[str]:
    statements = []
    for raw_statement in schema_sql.split(";"):
        statement = "\n".join(
            line
            for line in raw_statement.splitlines()
            if not line.lstrip().startswith("--")
        ).strip()
        if statement:
            statements.append(statement)
    return statements


def validate_csv_schema(
    datasets: dict[str, pd.DataFrame], schema_sql: str
) -> None:
    schema_tables = set(re.findall(SCHEMA_TABLE_PATTERN, schema_sql))
    missing_tables = sorted(set(datasets) - schema_tables)
    if missing_tables:
        raise ValueError(
            "CSV import targets are not defined in database/schema.sql: "
            + ", ".join(missing_tables)
        )

    for table_name, frame in datasets.items():
        match = re.search(
            rf"CREATE TABLE IF NOT EXISTS `{table_name}`\s*\((.*?)\)\s*ENGINE=",
            schema_sql,
            flags=re.DOTALL,
        )
        if match is None:
            raise ValueError(f"Could not find a complete schema for '{table_name}'.")
        schema_columns = set(
            re.findall(
                r"^\s{4}`(\w+)`\s+(?:INT|VARCHAR|DATE|DECIMAL|TINYINT|DATETIME|YEAR)\b",
                match.group(1),
                flags=re.MULTILINE,
            )
        )
        missing_columns = sorted(set(frame.columns) - schema_columns)
        if missing_columns:
            raise ValueError(
                f"CSV columns for '{table_name}' are missing from its SQL table: "
                + ", ".join(missing_columns)
            )


def import_datasets(
    engine: Any,
    datasets: dict[str, pd.DataFrame],
    schema_sql: str,
) -> None:
    validate_csv_schema(datasets, schema_sql)
    schema_tables = set(re.findall(SCHEMA_TABLE_PATTERN, schema_sql))
    existing_tables = set(inspect(engine).get_table_names())
    conflicts = sorted(existing_tables.intersection(schema_tables))
    if conflicts:
        raise RuntimeError(
            "Import cancelled because project tables already exist; no tables or "
            "rows were changed: "
            + ", ".join(conflicts)
        )

    statements = parse_schema_statements(schema_sql)
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
        for table_name, frame in datasets.items():
            frame.to_sql(
                table_name,
                connection,
                if_exists="append",
                index=False,
                chunksize=1000,
                method="multi",
            )
            print(f"Imported {len(frame):,} rows into {table_name}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create the reviewed WasteWise schema and import CSV data into an "
            "empty configured MySQL database. Existing project tables are never "
            "dropped, truncated, replaced, or appended to."
        )
    )
    parser.parse_args()

    if not database_configured():
        raise SystemExit(
            "DATABASE_URL is not set. Configure backend/.env before importing."
        )

    try:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        for path, reason in EXCLUDED_CSV_DATASETS.items():
            if path.exists():
                print(f"Skipping {path.name}: {reason}.")
        datasets = load_datasets()
        validate_csv_schema(datasets, schema_sql)
        engine = get_engine()
        import_datasets(engine, datasets, schema_sql)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    except (SQLAlchemyError, OSError, ValueError) as error:
        raise SystemExit(f"MySQL import failed: {error}") from error

    print("Import complete.")


if __name__ == "__main__":
    main()
