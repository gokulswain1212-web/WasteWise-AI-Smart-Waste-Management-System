
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect, text


# ==================================================
# 1. PROJECT PATHS AND DATABASE CONNECTION
# ==================================================

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
RAW = ROOT / "ml" / "data" / "raw"

# Allow Python to import modules from the backend folder.
backend_path = str(BACKEND_DIR)

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.db.session import get_engine  # noqa: E402


# ==================================================
# 2. CSV FILES AND DESTINATION TABLES
# ==================================================

FILES = {
    "products": RAW / "products.csv",
    "inventory_batches": RAW / "inventory_batches.csv",
    "perishable_inventory": (
        RAW / "perishable_inventory - perishable_inventory.csv"
    ),
    "discount_recommendations": (
        RAW / "discount_scenarios_simulated (1).csv"
    ),
}


# ==================================================
# 3. LOAD CSV FILES
# ==================================================

def load_csv_files():
    frames = {}

    for table, path in FILES.items():
        if not path.is_file():
            raise FileNotFoundError(
                f"CSV file not found:\n{path}"
            )

        frame = pd.read_csv(
            path,
            dtype={
                "product_id": str,
                "batch_id": str,
            },
        )

        if frame.empty:
            raise ValueError(
                f"The CSV file contains no records: {path.name}"
            )

        frames[table] = frame

        print(
            f"Loaded {path.name}: "
            f"{len(frame):,} rows"
        )

    return frames


# ==================================================
# 4. VALIDATE IDS AND RELATIONSHIPS
# ==================================================

def validate_data(frames):
    products = frames["products"]
    batches = frames["inventory_batches"]
    perishable = frames["perishable_inventory"]
    discounts = frames["discount_recommendations"]

    # Normalize IDs consistently across the CSV files.
    for frame in frames.values():
        for column in ("product_id", "batch_id"):
            if column in frame.columns:
                frame[column] = frame[column].astype("string").str.strip()

    # Check required identifiers.
    if products["product_id"].isna().any():
        raise ValueError("Products CSV contains missing product IDs.")

    if products["product_id"].eq("").any():
        raise ValueError("Products CSV contains blank product IDs.")

    if batches["batch_id"].isna().any():
        raise ValueError("Inventory batches contain missing batch IDs.")

    if batches["batch_id"].eq("").any():
        raise ValueError("Inventory batches contain blank batch IDs.")

    # Parent table IDs must be unique.
    if products["product_id"].duplicated().any():
        raise ValueError("Duplicate product IDs found in products.csv.")

    if batches["batch_id"].duplicated().any():
        raise ValueError(
            "Duplicate batch IDs found in inventory_batches.csv."
        )

    # Validate product references.
    product_ids = set(products["product_id"].dropna())

    referenced_product_ids = set()

    for frame in (batches, perishable, discounts):
        referenced_product_ids.update(
            frame["product_id"].dropna()
        )

    missing_products = referenced_product_ids - product_ids

    # Every discount scenario must reference an existing batch.
    batch_ids = set(batches["batch_id"].dropna())

    missing_batches = (
        set(discounts["batch_id"].dropna()) - batch_ids
    )

    if missing_products or missing_batches:
        raise ValueError(
            "CSV relationship validation failed.\n"
            f"Missing product IDs: {list(missing_products)[:10]}\n"
            f"Missing batch IDs: {list(missing_batches)[:10]}"
        )

    print("Product and batch ID validation passed.")


# ==================================================
# 5. PREPARE DATES AND RECOMMENDATION VALUES
# ==================================================

def prepare_data(frames):
    batches = frames["inventory_batches"]
    perishable = frames["perishable_inventory"]
    discounts = frames["discount_recommendations"]

    # Convert received_at to datetime.
    batches["received_at"] = pd.to_datetime(
        batches["received_at"],
        errors="raise",
    )

    # Convert date-only columns to Python date values.
    for column in ("snapshot_date", "expiry_date"):
        batches[column] = pd.to_datetime(
            batches[column],
            errors="raise",
        ).dt.date

    perishable["date"] = pd.to_datetime(
        perishable["date"],
        errors="raise",
    ).dt.date

    # The MySQL table requires predicted_gross_margin.
    discounts["predicted_gross_margin"] = pd.to_numeric(
        discounts["estimated_gross_margin_simulated"],
        errors="raise",
    )

    print("Date and recommendation preparation passed.")


# ==================================================
# 6. IMPORT RECORDS INTO MYSQL
# ==================================================

def import_data(frames):
    engine = get_engine()

    with engine.begin() as connection:
        inspector = inspect(connection)

        # Confirm that every destination table exists.
        existing_tables = set(inspector.get_table_names())

        missing_tables = set(FILES) - existing_tables

        if missing_tables:
            raise RuntimeError(
                f"Missing MySQL tables: {sorted(missing_tables)}. "
                "Initialize the database schema first."
            )

        # Abort if a previous import already populated any target table.
        counts = {
            table: connection.execute(
                text(f"SELECT COUNT(*) FROM `{table}`")
            ).scalar_one()
            for table in FILES
        }

        if any(counts.values()):
            raise RuntimeError(
                "Import cancelled to prevent duplicate data.\n"
                f"Current row counts: {counts}\n"
                "No new records were inserted."
            )

        # Verify destination columns before inserting records.
        destination_columns = {}

        for table in FILES:
            destination_columns[table] = {
                column["name"]
                for column in inspector.get_columns(table)
            }

        print("Destination tables are empty.")
        print("Starting CSV import...")

        # Import in parent-to-child order.
        for table, frame in frames.items():
            available_columns = destination_columns[table]

            matching_columns = [
                column
                for column in frame.columns
                if column in available_columns
            ]

            if not matching_columns:
                raise ValueError(
                    f"No matching columns for table '{table}'."
                )

            import_frame = frame.loc[
                :, matching_columns
            ].copy()

            # Pandas uses the existing transaction and table.
            # It will not drop or replace the destination table.
            import_frame.to_sql(
                name=table,
                con=connection,
                if_exists="append",
                index=False,
                chunksize=500,
            )

            print(
                f"Inserted {len(import_frame):,} rows "
                f"into {table}."
            )

        # Verify the row counts before committing.
        final_counts = {
            table: connection.execute(
                text(f"SELECT COUNT(*) FROM `{table}`")
            ).scalar_one()
            for table in FILES
        }

    # The transaction has committed successfully at this point.
    print("\nCSV import completed successfully!")

    for table, count in final_counts.items():
        print(f"{table}: {count:,} rows")


# ==================================================
# 7. MAIN EXECUTION
# ==================================================

def main():
    print("WasteWise AI - CSV to MySQL Import")
    print("=" * 45)

    frames = load_csv_files()
    validate_data(frames)
    prepare_data(frames)
    import_data(frames)


if __name__ == "__main__":
    main()
