from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from app.api.v1.analytics import dashboard_summary


def test_dashboard_summary_aggregates_configured_data_window() -> None:
    inventory = pd.DataFrame(
        [
            {
                "batch_id": 11,
                "product_id": 1,
                "product_name": "Apples",
                "category": "Produce",
                "expiry_risk_label": 1,
                "days_to_expiry": 2,
                "quantity_remaining": 5,
                "expected_demand_before_expiry": 3,
            },
            {
                "batch_id": 12,
                "product_id": 2,
                "product_name": "Milk",
                "category": "Dairy",
                "expiry_risk_label": 0,
                "days_to_expiry": 8,
                "quantity_remaining": 10,
                "expected_demand_before_expiry": 6,
            },
        ]
    )
    waste = pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "category": "Produce",
                "waste_units": 100,
                "units_sold": 20,
            },
            {
                "date": "2025-01-05",
                "category": "Produce",
                "waste_units": 2,
                "units_sold": 10,
            },
            {
                "date": "2025-01-10",
                "category": "Dairy",
                "waste_units": 3,
                "units_sold": 15,
            },
        ]
    )
    products = pd.DataFrame(
        {"product_id": [1, 2], "product_name": ["Apples", "Milk"]}
    )

    def read_dataset(path, required=True):
        return waste if path.name.startswith("perishable_inventory") else products

    with (
        patch("app.api.v1.analytics.inventory_view", return_value=inventory),
        patch("app.api.v1.analytics.read_csv", side_effect=read_dataset),
        patch("app.api.v1.analytics.database_configured", return_value=False),
    ):
        result = dashboard_summary()

    assert result["data_source"] == "local_csv"
    assert result["products_tracked"] == 2
    assert result["inventory_batches"] == 2
    assert result["expiry_risk_batches"] == 1
    assert result["recorded_waste_last_7_days"] == 5
    assert result["waste_data_through"] == "2025-01-10"
    assert result["daily_sales_last_7_days"] == [
        {"date": "2025-01-05", "units_sold": 10},
        {"date": "2025-01-10", "units_sold": 15},
    ]
    assert result["waste_by_category_last_7_days"] == [
        {"category": "Dairy", "waste_units": 3},
        {"category": "Produce", "waste_units": 2},
    ]
    assert [batch["batch_id"] for batch in result["expiry_risk_queue"]] == [11]
