from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

REQUIRED_TABLE_COLUMNS = {
    "products": {"product_id", "product_name", "category"},
    "inventory_batches": {
        "batch_id",
        "product_id",
        "category",
        "received_at",
        "snapshot_date",
        "initial_quantity",
        "quantity_remaining",
        "days_to_expiry",
        "avg_daily_sales_7d",
        "expected_demand_before_expiry",
        "unit_price",
        "unit_cost",
        "discount_pct",
        "expiry_risk_label",
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
        "stockout_flag",
        "waste_units",
    },
    "discount_recommendations": {
        "batch_id",
        "product_id",
        "days_to_expiry",
        "quantity_remaining",
        "predicted_gross_margin",
    },
}


def database_configured() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in backend/.env."
        )
    if not url.startswith("mysql+pymysql://"):
        raise ValueError("DATABASE_URL must use the mysql+pymysql:// driver.")
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 5},
    )


def database_status() -> dict[str, Any]:
    if not database_configured():
        return {
            "configured": False,
            "connected": False,
            "schema_ready": False,
            "message": "Set DATABASE_URL in backend/.env to enable MySQL.",
            "tables": [],
            "missing_tables": sorted(REQUIRED_TABLE_COLUMNS),
            "missing_columns": {},
        }
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        missing_tables = sorted(set(REQUIRED_TABLE_COLUMNS) - set(table_names))
        missing_columns = {
            table_name: sorted(
                REQUIRED_TABLE_COLUMNS[table_name]
                - {column["name"] for column in inspector.get_columns(table_name)}
            )
            for table_name in REQUIRED_TABLE_COLUMNS
            if table_name in table_names
        }
        missing_columns = {
            table_name: columns
            for table_name, columns in missing_columns.items()
            if columns
        }
        schema_ready = not missing_tables and not missing_columns
        return {
            "configured": True,
            "connected": True,
            "schema_ready": schema_ready,
            "message": (
                "MySQL connection and WasteWise schema are ready."
                if schema_ready
                else "MySQL is connected, but required WasteWise tables or columns are missing."
            ),
            "tables": table_names,
            "missing_tables": missing_tables,
            "missing_columns": missing_columns,
        }
    except (SQLAlchemyError, OSError, ValueError, RuntimeError) as error:
        return {
            "configured": True,
            "connected": False,
            "schema_ready": False,
            "message": f"MySQL connection failed ({type(error).__name__}).",
            "tables": [],
            "missing_tables": sorted(REQUIRED_TABLE_COLUMNS),
            "missing_columns": {},
        }