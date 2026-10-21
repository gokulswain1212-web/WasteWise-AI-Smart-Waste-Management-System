from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
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


def validate_dataset_values(datasets: dict[str, pd.DataFrame]) -> None:
    """Validate CSV values against the reviewed schema before any database writes."""
    required_columns = {
        "products": {
            "product_id",
            "product_name",
            "category",
            "shelf_life_days",
            "selling_price",
            "unit_cost",
        },
        "inventory_batches": {
            "batch_id",
            "product_id",
            "category",
            "received_at",
            "snapshot_date",
            "expiry_date",
            "initial_quantity",
            "quantity_remaining",
            "days_to_expiry",
            "avg_daily_sales_7d",
            "expected_demand_before_expiry",
            "unit_price",
            "unit_cost",
            "discount_pct",
            "expiry_risk_label",
            "waste_units_actual_simulated",
        },
        "perishable_inventory": {
            "product_id",
            "date",
            "category",
            "opening_stock",
            "units_received",
            "units_sold",
            "unit_price",
            "discount_pct",
            "days_to_expiry",
            "temperature_c",
            "waste_units",
            "stockout_flag",
        },
        "discount_recommendations": {
            "batch_id",
            "product_id",
            "days_to_expiry",
            "quantity_remaining",
            "predicted_gross_margin",
        },
    }
    integer_columns = {
        "products": {"product_id", "shelf_life_days"},
        "inventory_batches": {
            "batch_id",
            "product_id",
            "initial_quantity",
            "quantity_remaining",
            "days_to_expiry",
            "expiry_risk_label",
            "waste_units_actual_simulated",
        },
        "perishable_inventory": {
            "product_id",
            "opening_stock",
            "units_received",
            "units_sold",
            "days_to_expiry",
            "waste_units",
            "stockout_flag",
        },
        "discount_recommendations": {
            "batch_id",
            "product_id",
            "days_to_expiry",
            "quantity_remaining",
        },
    }
    numeric_columns = {
        "products": {"selling_price", "unit_cost"},
        "inventory_batches": {
            "avg_daily_sales_7d",
            "expected_demand_before_expiry",
            "unit_price",
            "unit_cost",
            "discount_pct",
        },
        "perishable_inventory": {
            "unit_price",
            "discount_pct",
            "temperature_c",
        },
        "discount_recommendations": {
            "discount_pct",
            "predicted_gross_margin",
        },
    }
    optional_numeric_columns = {
        "discount_recommendations": {"discount_pct"},
    }
    date_columns = {
        "inventory_batches": {"received_at", "snapshot_date", "expiry_date"},
        "perishable_inventory": {"date"},
    }
    nonblank_columns = {
        "products": {"product_name", "category"},
        "inventory_batches": {"category"},
        "perishable_inventory": {"category"},
    }

    if not set(datasets).issubset(required_columns):
        raise ValueError("CSV import contains an unsupported dataset.")
    if (
        {"inventory_batches", "perishable_inventory"} & set(datasets)
        and "products" not in datasets
    ):
        raise ValueError("The products dataset is required for inventory imports.")
    if "discount_recommendations" in datasets and not {
        "products",
        "inventory_batches",
    }.issubset(datasets):
        raise ValueError(
            "Products and inventory_batches are required for recommendation imports."
        )

    for table_name, frame in datasets.items():
        if frame.empty:
            raise ValueError(f"CSV dataset '{table_name}' is empty.")

        missing_columns = sorted(required_columns[table_name] - set(frame.columns))
        if missing_columns:
            raise ValueError(
                f"CSV dataset '{table_name}' is missing required columns: "
                + ", ".join(missing_columns)
            )

        nullable_columns = (
            {"temperature_c"} if table_name == "perishable_inventory" else set()
        )
        missing_values = sorted(
            column
            for column in frame.columns
            if column not in nullable_columns and frame[column].isna().any()
        )
        if missing_values:
            raise ValueError(
                f"CSV dataset '{table_name}' has null values in required columns: "
                + ", ".join(missing_values)
            )

        blank_values = sorted(
            column
            for column in nonblank_columns.get(table_name, set())
            if frame[column].astype(str).str.strip().eq("").any()
        )
        if blank_values:
            raise ValueError(
                f"CSV dataset '{table_name}' has blank required values in: "
                + ", ".join(blank_values)
            )

        for column in date_columns.get(table_name, set()):
            try:
                pd.to_datetime(frame[column], errors="raise")
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"CSV column '{table_name}.{column}' contains invalid dates."
                ) from error

        for column in integer_columns[table_name] | numeric_columns[table_name]:
            if column not in frame.columns:
                if column in optional_numeric_columns.get(table_name, set()):
                    continue
                raise ValueError(
                    f"CSV dataset '{table_name}' is missing numeric column '{column}'."
                )
            try:
                values = pd.to_numeric(frame[column], errors="raise")
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"CSV column '{table_name}.{column}' must contain numeric values."
                ) from error
            if not np.isfinite(values.dropna().to_numpy(dtype=float)).all():
                raise ValueError(
                    f"CSV column '{table_name}.{column}' contains non-finite values."
                )
            if column in integer_columns[table_name] and not np.equal(
                np.mod(values.dropna().to_numpy(dtype=float), 1), 0
            ).all():
                raise ValueError(
                    f"CSV column '{table_name}.{column}' must contain whole numbers."
                )

        if table_name == "products":
            if frame["product_id"].duplicated().any():
                raise ValueError("CSV dataset 'products' has duplicate product IDs.")
            shelf_life = pd.to_numeric(frame["shelf_life_days"], errors="raise")
            if not shelf_life.gt(0).all():
                raise ValueError("Product shelf_life_days must be positive.")
            prices = frame[["selling_price", "unit_cost"]].apply(
                pd.to_numeric, errors="raise"
            )
            if not prices.ge(0).all().all():
                raise ValueError("Product prices and costs must be non-negative.")

        elif table_name == "inventory_batches":
            if frame["batch_id"].duplicated().any():
                raise ValueError("CSV dataset 'inventory_batches' has duplicate batch IDs.")
            initial = pd.to_numeric(frame["initial_quantity"], errors="raise")
            remaining = pd.to_numeric(frame["quantity_remaining"], errors="raise")
            discount = pd.to_numeric(frame["discount_pct"], errors="raise")
            if not initial.gt(0).all() or not remaining.between(0, initial).all():
                raise ValueError("Inventory quantities are outside the allowed range.")
            if not discount.between(0, 100).all():
                raise ValueError("Inventory discount_pct must be between 0 and 100.")
            if not pd.to_numeric(
                frame["waste_units_actual_simulated"], errors="raise"
            ).ge(0).all():
                raise ValueError("Inventory waste units must be non-negative.")
            if not pd.to_numeric(
                frame["expiry_risk_label"], errors="raise"
            ).isin([0, 1]).all():
                raise ValueError("Inventory expiry_risk_label must be 0 or 1.")

        elif table_name == "perishable_inventory":
            stocks = frame[
                ["opening_stock", "units_received", "units_sold", "waste_units"]
            ].apply(pd.to_numeric, errors="raise")
            discount = pd.to_numeric(frame["discount_pct"], errors="raise")
            stockout = pd.to_numeric(frame["stockout_flag"], errors="raise")
            if not stocks.ge(0).all().all():
                raise ValueError("Perishable inventory quantities must be non-negative.")
            if not discount.between(0, 100).all():
                raise ValueError(
                    "Perishable inventory discount_pct must be between 0 and 100."
                )
            if not stockout.isin([0, 1]).all():
                raise ValueError("Perishable inventory stockout_flag must be 0 or 1.")

        elif table_name == "discount_recommendations":
            if frame["batch_id"].duplicated().any():
                raise ValueError(
                    "CSV dataset 'discount_recommendations' has duplicate batch IDs."
                )
            quantity = pd.to_numeric(frame["quantity_remaining"], errors="raise")
            if not quantity.ge(0).all():
                raise ValueError(
                    "Recommendation quantity_remaining must be non-negative."
                )
            if "discount_pct" in frame.columns and not pd.to_numeric(
                frame["discount_pct"], errors="raise"
            ).between(0, 100).all():
                raise ValueError(
                    "Recommendation discount_pct must be between 0 and 100."
                )

    if "products" in datasets:
        product_ids = set(datasets["products"]["product_id"])
        for table_name in ("inventory_batches", "perishable_inventory"):
            if table_name in datasets and not set(
                datasets[table_name]["product_id"]
            ).issubset(product_ids):
                raise ValueError(
                    f"CSV dataset '{table_name}' references an unknown product ID."
                )

    if "inventory_batches" in datasets:
        batch_ids = set(datasets["inventory_batches"]["batch_id"])
        for table_name in ("discount_recommendations",):
            if table_name in datasets and not set(
                datasets[table_name]["batch_id"]
            ).issubset(batch_ids):
                raise ValueError(
                    f"CSV dataset '{table_name}' references an unknown batch ID."
                )
        if "discount_recommendations" in datasets and not set(
            datasets["discount_recommendations"]["product_id"]
        ).issubset(product_ids):
            raise ValueError(
                "CSV dataset 'discount_recommendations' references an unknown product ID."
            )


def import_datasets(
    engine: Any,
    datasets: dict[str, pd.DataFrame],
    schema_sql: str,
) -> None:
    validate_csv_schema(datasets, schema_sql)
    validate_dataset_values(datasets)
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
        validate_dataset_values(datasets)
        engine = get_engine()
        import_datasets(engine, datasets, schema_sql)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    except (SQLAlchemyError, OSError, ValueError) as error:
        raise SystemExit(f"MySQL import failed: {error}") from error

    print("Import complete.")


if __name__ == "__main__":
    main()
