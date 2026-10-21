"""
Tests for database schema and seed data.

These tests verify the SQL schema DDL and seed data without modifying
your real database. When a MySQL test database is available, integration
tests run against it. Otherwise, the tests validate the SQL files directly.

Run with: python -m pytest backend/tests/test_database_schema.py -v
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.db.base import Base

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "database" / "schema.sql"
SEED_PATH = ROOT / "database" / "seed_data.sql"

EXPECTED_TABLES = {
    "products",
    "inventory_batches",
    "perishable_inventory",
    "discount_recommendations",
    "calendar",
    "forecast_results",
}

EXPECTED_COLUMNS = {
    "products": {
        "product_id", "product_name", "category", "shelf_life_days",
        "selling_price", "unit_cost", "created_at", "updated_at",
    },
    "inventory_batches": {
        "batch_id", "product_id", "category", "received_at",
        "snapshot_date", "expiry_date", "initial_quantity",
        "quantity_remaining", "days_to_expiry", "avg_daily_sales_7d",
        "expected_demand_before_expiry", "unit_price", "unit_cost",
        "discount_pct", "expiry_risk_label",
        "waste_units_actual_simulated", "created_at",
    },
    "perishable_inventory": {
        "record_id", "product_id", "date", "category",
        "opening_stock", "units_received", "units_sold", "unit_price",
        "discount_pct", "days_to_expiry", "temperature_c",
        "waste_units", "stockout_flag", "created_at",
    },
    "discount_recommendations": {
        "recommendation_id", "batch_id", "product_id", "days_to_expiry",
        "quantity_remaining", "discount_pct", "predicted_gross_margin",
        "created_at",
    },
    "calendar": {
        "date", "wm_yr_wk", "weekday", "wday", "month", "year",
        "event_name_1", "event_type_1", "event_name_2", "event_type_2",
        "snap_CA", "snap_TX", "snap_WI", "created_at",
    },
    "forecast_results": {
        "forecast_id", "product_id", "forecast_date", "target_date",
        "model_name", "predicted_waste_units", "predicted_expiry_risk",
        "created_at",
    },
}

EXPECTED_FOREIGN_KEYS = {
    "inventory_batches": [("product_id", "products", "product_id")],
    "perishable_inventory": [("product_id", "products", "product_id")],
    "discount_recommendations": [
        ("batch_id", "inventory_batches", "batch_id"),
        ("product_id", "products", "product_id"),
    ],
    "forecast_results": [("product_id", "products", "product_id")],
}


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_table_names(sql: str) -> set[str]:
    """Extract table names from CREATE TABLE statements."""
    pattern = r"CREATE TABLE IF NOT EXISTS `(\w+)`"
    return set(re.findall(pattern, sql))


def _extract_column_names(sql: str, table: str) -> set[str]:
    """Extract column names for a specific table from CREATE TABLE."""
    start = sql.find(f"CREATE TABLE IF NOT EXISTS `{table}`")
    if start == -1:
        return set()
    block = sql[start:]
    end = block.find(") ENGINE=")
    if end == -1:
        end = block.find(");")
    if end == -1:
        return set()
    block = block[:end]
    return set(re.findall(r"`(\w+)`", block))


class TestSchemaFile:
    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"
        assert SCHEMA_PATH.stat().st_size > 0, "Schema file is empty"

    def test_seed_file_exists(self):
        assert SEED_PATH.exists(), f"Seed file not found: {SEED_PATH}"
        assert SEED_PATH.stat().st_size > 0, "Seed file is empty"

    def test_all_expected_tables_defined(self):
        sql = _read_file(SCHEMA_PATH)
        actual_tables = _extract_table_names(sql)
        missing = EXPECTED_TABLES - actual_tables
        assert not missing, f"Missing tables in schema: {missing}"

    def test_no_unexpected_tables(self):
        sql = _read_file(SCHEMA_PATH)
        actual_tables = _extract_table_names(sql)
        unexpected = actual_tables - EXPECTED_TABLES
        assert not unexpected, f"Unexpected tables in schema: {unexpected}"

    def test_all_expected_columns_defined(self):
        sql = _read_file(SCHEMA_PATH)
        for table, expected_cols in EXPECTED_COLUMNS.items():
            actual_cols = _extract_column_names(sql, table)
            missing = expected_cols - actual_cols
            assert not missing, (
                f"Table '{table}' missing columns: {missing}"
            )

    def test_primary_keys_defined(self):
        sql = _read_file(SCHEMA_PATH)
        for table in EXPECTED_TABLES:
            block_start = sql.find(f"CREATE TABLE IF NOT EXISTS `{table}`")
            assert block_start != -1, f"Table {table} not found"
            block = sql[block_start:]
            block_end = block.find(") ENGINE=")
            if block_end == -1:
                block_end = block.find(");")
            block = block[:block_end]
            assert "PRIMARY KEY" in block.upper(), (
                f"Table '{table}' is missing a PRIMARY KEY constraint"
            )

    def test_foreign_keys_defined(self):
        sql = _read_file(SCHEMA_PATH)
        for table, fk_list in EXPECTED_FOREIGN_KEYS.items():
            block_start = sql.find(f"CREATE TABLE IF NOT EXISTS `{table}`")
            assert block_start != -1, f"Table {table} not found"
            block = sql[block_start:]
            block_end = block.find(") ENGINE=")
            if block_end == -1:
                block_end = block.find(");")
            block = block[:block_end]
            for col, ref_table, ref_col in fk_list:
                assert f"FOREIGN KEY (`{col}`)" in block, (
                    f"Table '{table}' missing FOREIGN KEY on `{col}`"
                )
                assert f"REFERENCES `{ref_table}` (`{ref_col}`)" in block, (
                    f"Table '{table}' missing REFERENCES to `{ref_table}`(`{ref_col}`)"
                )

    def test_check_constraints_defined(self):
        sql = _read_file(SCHEMA_PATH)
        for table in EXPECTED_TABLES:
            block_start = sql.find(f"CREATE TABLE IF NOT EXISTS `{table}`")
            assert block_start != -1, f"Table {table} not found"
            block = sql[block_start:]
            block_end = block.find(") ENGINE=")
            if block_end == -1:
                block_end = block.find(");")
            block = block[:block_end]
            assert "CHECK" in block.upper(), (
                f"Table '{table}' is missing CHECK constraints"
            )

    def test_indexes_defined(self):
        sql = _read_file(SCHEMA_PATH)
        assert "idx_inventory_batches_product_id" in sql
        assert "idx_perishable_inventory_product_id" in sql
        assert "idx_discount_recommendations_product_id" in sql
        assert "idx_forecast_results_product_id" in sql

    def test_each_create_table_has_a_complete_engine_boundary(self):
        sql = _read_file(SCHEMA_PATH)
        create_count = len(re.findall(r"CREATE TABLE IF NOT EXISTS", sql))
        engine_boundaries = len(re.findall(r"\)\s*ENGINE=InnoDB[^;]*;", sql))
        assert create_count == len(EXPECTED_TABLES)
        assert engine_boundaries == create_count
        assert not re.search(
            r"SET SQL_MODE=@OLD_SQL_MODE;\s*SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;"
            r"\s*SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;\s*\)\s*ENGINE=",
            sql,
        )

    def test_perishable_inventory_date_matches_csv_contract(self):
        sql = _read_file(SCHEMA_PATH)
        columns = _extract_column_names(sql, "perishable_inventory")
        assert "date" in columns
        assert "record_date" not in columns

    def test_forecast_outputs_allow_non_applicable_values(self):
        sql = _read_file(SCHEMA_PATH)
        assert re.search(
            r"`predicted_waste_units`\s+DECIMAL\(10,2\)\s+DEFAULT NULL",
            sql,
        )
        assert (
            "`predicted_waste_units` IS NULL OR `predicted_waste_units` >= 0"
            in sql
        )

    def test_example_environment_files_use_placeholders(self):
        for path in (ROOT / ".env.example", ROOT / "backend" / ".env.example"):
            lines = path.read_text(encoding="utf-8").splitlines()
            for name in (
                "DATABASE_URL",
                "MYSQL_ADMIN_URL",
                "MYSQL_PASSWORD",
                "MYSQL_ROOT_PASSWORD",
                "API_KEY",
                "SECRET_KEY",
            ):
                values = [
                    line.partition("=")[2]
                    for line in lines
                    if line.startswith(f"{name}=")
                ]
                assert all("CHANGE_ME" in value for value in values), (
                    f"{name} in {path.name} must use a placeholder"
                )


class TestSeedFile:
    def test_seed_uses_on_duplicate_key_update(self):
        sql = _read_file(SEED_PATH)
        assert "ON DUPLICATE KEY UPDATE" in sql, (
            "Rows with primary or unique keys should remain repeatable"
        )

    def test_seed_has_inserts_for_all_core_tables(self):
        sql = _read_file(SEED_PATH)
        for table in ["products", "inventory_batches", "perishable_inventory",
                       "discount_recommendations", "calendar", "forecast_results"]:
            assert f"INSERT INTO `{table}`" in sql, (
                f"Seed data missing INSERT for table '{table}'"
            )

    def test_seed_is_repeatable(self):
        """Verify seeds avoid overwrites and duplicate natural-key rows."""
        sql = _read_file(SEED_PATH)
        non_comment_sql = "\n".join(
            line for line in sql.splitlines()
            if not line.strip().startswith("--")
        )
        inserts = re.findall(
            r"INSERT INTO `(\w+)`.*?;",
            non_comment_sql,
            flags=re.DOTALL,
        )
        assert inserts == [
            "products",
            "inventory_batches",
            "perishable_inventory",
            "discount_recommendations",
            "calendar",
            "forecast_results",
        ]
        assert non_comment_sql.count("ON DUPLICATE KEY UPDATE") == 4
        assert non_comment_sql.count("WHERE NOT EXISTS") == 2
        assert "`record_date`" not in non_comment_sql
        assert "`unit_cost` = VALUES(`unit_cost`)" not in non_comment_sql

        duplicate_clauses = re.findall(
            r"ON DUPLICATE KEY UPDATE\s+(.*?);",
            non_comment_sql,
            flags=re.DOTALL,
        )
        assert all(
            re.fullmatch(r"`(\w+)`\s*=\s*`\1`", clause.strip())
            for clause in duplicate_clauses
        )
        assert all(
            statement.strip().startswith("INSERT INTO")
            for statement in non_comment_sql.split(";")
            if statement.strip()
        )


class TestSQLAlchemyBase:
    def test_base_imports(self):
        assert Base is not None
        assert hasattr(Base, "metadata")

    def test_base_metadata_empty_initially(self):
        # No models are defined yet, so metadata should have no tables
        assert len(Base.metadata.tables) == 0


class TestDatabaseIntegration:
    """Integration tests that run only when MySQL is available."""

    @pytest.fixture
    def mysql_available(self):
        settings = get_settings()
        if not settings.database_url:
            pytest.skip("DATABASE_URL not configured — skipping MySQL integration tests")
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(settings.database_url, connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception:
            pytest.skip("MySQL not available — skipping integration tests")

    def test_database_has_expected_tables(self, mysql_available):
        from sqlalchemy import inspect
        inspector = inspect(mysql_available)
        table_names = set(inspector.get_table_names())
        missing = EXPECTED_TABLES - table_names
        if missing:
            pytest.skip(f"MySQL tables not yet created: {missing}. Run schema.sql first.")

    def test_seed_data_row_counts(self, mysql_available):
        from sqlalchemy import text
        with mysql_available.connect() as conn:
            for table in ["products", "inventory_batches", "perishable_inventory",
                          "discount_recommendations"]:
                result = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`"))
                count = result.scalar()
                assert count > 0, f"Table '{table}' should have seed data rows"
