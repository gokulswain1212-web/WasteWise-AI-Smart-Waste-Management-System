import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect, text


# --------------------------------------------------
# 1. Project paths and database connection
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import get_engine  # noqa: E402

RAW = ROOT / "ml" / "data" / "raw"


# --------------------------------------------------
# 2. CSV files and destination MySQL tables
# --------------------------------------------------

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


# --------------------------------------------------
# 3. Load CSV files
# --------------------------------------------------

def load_csv_files():
    frames = {}

    for table, path in FILES.items():
        if not path.exists():
            raise FileNotFoundError(
                f"CSV file not found: {path}"
            )

        frames[table] = pd.read_csv(
            path,
            dtype={
                "product_id": str,
                "batch_id": str,
            },
        )

        print(
            f"Loaded {path.name}: "
            f"{len(frames[table]):,} rows"
        )

    return frames


# --------------------------------------------------
# 4. Validate IDs and relationships
# --------------------------------------------------

def validate_data(frames):
    products = frames["products"]
    batches = frames["inventory_batches"]
    perishable = frames["perishable_inventory"]
    discounts = frames["discount_recommendations"]

    # Keep IDs consistent with the database schema.
    for frame in frames.values():
        for column in ("product_id", "batch_id"):
            if column in frame.columns:
                frame[column] = frame[column].astype("string")

    if products["product_id"].isna().any():
        raise ValueError("products.csv contains missing product IDs.")

    if batches["batch_id"].isna().any():
        raise ValueError(
            "inventory_batches.csv contains missing batch IDs."
        )

    if products["product_id"].duplicated().any():
        raise ValueError(
            "products.csv contains duplicate product IDs."
        )

    if batches["batch_id"].duplicated().any():
        raise ValueError(
            "inventory_batches.csv contains duplicate batch IDs."
        )

    product_ids = set(products["product_id"].dropna())

    all_product_ids = (
        set(batches["product_id"].dropna())
        | set(perishable["product_id"].dropna())
        | set(discounts["product_id"].dropna())
    )

    missing_products = all_product_ids - product_ids

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


# --------------------------------------------------
# 5. Prepare date and recommendation columns
# --------------------------------------------------

def prepare_data(frames):
    batches = frames["inventory_batches"]
    perishable = frames["perishable_inventory"]
    discounts = frames["discount_recommendations"]

    # Convert received_at to datetime.
    batches["received_at"] = pd.to_datetime(
        batches["received_at"],
        errors="raise",
    )

    # These fields are SQL DATE columns.
    for column in ("snapshot_date", "expiry_date"):
        batches[column] = pd.to_datetime(
            batches[column],
            errors="raise",
        ).dt.date

    perishable["date"] = pd.to_datetime(
        perishable["date"],
        errors="raise",
    ).dt.date

    # The destination schema requires this field.
    discounts["predicted_gross_margin"] = (
        discounts["estimated_gross_margin_simulated"]
    )

    print("Date and recommendation data preparation passed.")


# --------------------------------------------------
# 6. Import records into MySQL
# --------------------------------------------------

def import_data(frames):
    engine = get_engine()

    with engine.begin() as connection:
        # Inspect all destination tables before inserting.
        inspector = inspect(connection)

        counts = {
            table: connection.execute(
                text(f"SELECT COUNT(*) FROM `{table}`")
            ).scalar_one()
            for table in FILES
        }

        # Avoid accidentally importing duplicate records.
        if any(counts.values()):
            raise RuntimeError(
                "Import cancelled because one or more destination "
                f"tables already contain records: {counts}. "
                "No new records were inserted."
            )

        print("Destination tables are empty. Starting import...")

        for table, frame in frames.items():
            # SQLAlchemy inspector returns column names reliably.
            destination_columns = {
                column["name"]
                for column in inspector.get_columns(table)
            }

            # Insert only columns supported by the destination table.
            matching_columns = [
                column
                for column in frame.columns
                if column in destination_columns
            ]

            if not matching_columns:
                raise ValueError(
                    f"No matching columns found for table '{table}'."
                )

            import_frame = frame.loc[:, matching_columns].copy()

            # Write rows into the existing table.
            import_frame.to_sql(
                name=table,
                con=connection,
                if_exists="append",
                index=False,
                chunksize=500,
                method="multi",
            )

            print(
                f"Imported {len(import_frame):,} rows "
                f"into {table}."
            )

        # Verify counts before the transaction commits.
        final_counts = {
            table: connection.execute(
                text(f"SELECT COUNT(*) FROM `{table}`")
            ).scalar_one()
            for table in FILES
        }

    print("\nCSV import completed successfully!")

    for table, count in final_counts.items():
        print(f"{table}: {count:,} rows")


# --------------------------------------------------
# 7. Main execution
# --------------------------------------------------

def main():
    print("WasteWise AI - CSV to MySQL Import")
    print("=" * 45)

    frames = load_csv_files()

    validate_data(frames)

    prepare_data(frames)

    import_data(frames)


if __name__ == "__main__":
    main()