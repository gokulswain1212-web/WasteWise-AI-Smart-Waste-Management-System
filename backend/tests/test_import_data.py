from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import import_data


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = import_data.SCHEMA_PATH.read_text(encoding="utf-8")


def test_csv_headers_are_compatible_with_reviewed_sql_schema() -> None:
    headers = {}
    for path, table_name in import_data.CSV_TABLES.items():
        assert path.exists(), f"Missing CSV source: {path.name}"
        headers[table_name] = pd.read_csv(path, nrows=0)

    import_data.validate_csv_schema(headers, SCHEMA_SQL)


def test_csv_rows_satisfy_reviewed_keys_and_check_constraints() -> None:
    datasets = import_data.load_datasets()
    products = datasets["products"]
    inventory = datasets["inventory_batches"]
    perishable = datasets["perishable_inventory"]
    recommendations = datasets["discount_recommendations"]
    product_ids = set(products["product_id"])
    batch_ids = set(inventory["batch_id"])

    assert products["product_id"].is_unique
    assert products["shelf_life_days"].gt(0).all()
    assert products[["selling_price", "unit_cost"]].ge(0).all().all()

    assert inventory["batch_id"].is_unique
    assert set(inventory["product_id"]).issubset(product_ids)
    assert inventory["initial_quantity"].gt(0).all()
    assert inventory["quantity_remaining"].ge(0).all()
    assert inventory["quantity_remaining"].le(inventory["initial_quantity"]).all()
    assert inventory["discount_pct"].between(0, 100).all()

    assert set(perishable["product_id"]).issubset(product_ids)
    assert perishable[
        ["opening_stock", "units_received", "units_sold", "waste_units"]
    ].ge(0).all().all()
    assert perishable["discount_pct"].between(0, 100).all()
    assert perishable["stockout_flag"].isin([0, 1]).all()

    assert recommendations["batch_id"].is_unique
    assert set(recommendations["batch_id"]).issubset(batch_ids)
    assert set(recommendations["product_id"]).issubset(product_ids)
    assert recommendations["quantity_remaining"].ge(0).all()


def test_import_validation_reports_undefined_table_and_column_errors() -> None:
    with pytest.raises(ValueError, match="not defined in database/schema.sql"):
        import_data.validate_csv_schema(
            {"unknown_table": pd.DataFrame(columns=["id"])}, SCHEMA_SQL
        )

    with pytest.raises(ValueError, match="not_a_real_column"):
        import_data.validate_csv_schema(
            {"products": pd.DataFrame(columns=["product_id", "not_a_real_column"])},
            SCHEMA_SQL,
        )


def test_discount_scenarios_are_explicitly_excluded_without_a_schema() -> None:
    scenario_path = ROOT / "ml" / "data" / "raw" / "discount_scenarios_simulated (1).csv"

    assert scenario_path in import_data.EXCLUDED_CSV_DATASETS
    assert "discount_scenarios" not in import_data.CSV_TABLES.values()
    assert "discount_scenarios" not in import_data.re.findall(
        import_data.SCHEMA_TABLE_PATTERN, SCHEMA_SQL
    )


def test_schema_parser_returns_complete_create_statements() -> None:
    statements = import_data.parse_schema_statements(SCHEMA_SQL)
    create_statements = [
        statement for statement in statements if statement.startswith("CREATE TABLE")
    ]

    assert len(create_statements) == 6
    assert all(statement.endswith("ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci") for statement in create_statements)


def test_existing_project_tables_prevent_all_import_writes() -> None:
    engine = MagicMock()
    datasets = {"products": pd.DataFrame({"product_id": [1]})}
    inspector = MagicMock()
    inspector.get_table_names.return_value = ["products"]

    with (
        patch.object(import_data, "inspect", return_value=inspector),
        patch.object(pd.DataFrame, "to_sql") as to_sql,
    ):
        with pytest.raises(RuntimeError, match="no tables or rows were changed"):
            import_data.import_datasets(engine, datasets, SCHEMA_SQL)

    engine.begin.assert_not_called()
    to_sql.assert_not_called()


def test_new_database_import_appends_after_schema_creation() -> None:
    engine = MagicMock()
    connection = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    inspector = MagicMock()
    inspector.get_table_names.return_value = []
    datasets = {"products": pd.DataFrame({"product_id": [1]})}

    with (
        patch.object(import_data, "inspect", return_value=inspector),
        patch.object(pd.DataFrame, "to_sql") as to_sql,
        patch("builtins.print"),
    ):
        import_data.import_datasets(engine, datasets, SCHEMA_SQL)

    executed = [
        call.args[0] for call in connection.exec_driver_sql.call_args_list
    ]
    assert len(executed) == len(import_data.parse_schema_statements(SCHEMA_SQL))
    assert not any(
        statement.lstrip().upper().startswith(("DROP ", "TRUNCATE "))
        for statement in executed
    )
    to_sql.assert_called_once()
    assert to_sql.call_args.kwargs["if_exists"] == "append"


def test_destructive_replace_option_is_not_supported() -> None:
    with (
        patch.object(sys, "argv", ["import_data.py", "--replace-existing"]),
        patch.object(import_data, "get_engine") as get_engine,
    ):
        with pytest.raises(SystemExit) as error:
            import_data.main()

    assert error.value.code == 2
    get_engine.assert_not_called()
