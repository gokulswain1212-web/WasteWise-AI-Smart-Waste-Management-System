from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import analytics
from app.main import app, get_api_identity


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_api_identity] = lambda: "test-user"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_api_identity, None)


def test_products_endpoint_filters_and_paginates(client: TestClient) -> None:
    products = pd.DataFrame(
        [
            {"product_id": "P1", "product_name": "Apple", "category": "Fruit"},
            {"product_id": "P2", "product_name": "Pear", "category": "Fruit"},
        ]
    )
    with (
        patch.object(analytics, "read_csv", return_value=products),
        patch.object(analytics, "database_configured", return_value=False),
    ):
        response = client.get("/api/v1/products?search=pea&limit=1")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["products"] == [
        {"product_id": "P2", "product_name": "Pear", "category": "Fruit"}
    ]
    assert response.json()["data_source"] == "local_csv"


def test_inventory_endpoint_marks_expired_and_same_day_batches_unsafe(
    client: TestClient,
) -> None:
    inventory = pd.DataFrame(
        [
            {
                "batch_id": "B-EXPIRED",
                "product_id": "P1",
                "category": "Fruit",
                "days_to_expiry": -1,
                "quantity_remaining": 4,
            },
            {
                "batch_id": "B-TODAY",
                "product_id": "P2",
                "category": "Dairy",
                "days_to_expiry": 0,
                "quantity_remaining": 3,
            },
            {
                "batch_id": "B-SAFE",
                "product_id": "P3",
                "category": "Bakery",
                "days_to_expiry": 2,
                "quantity_remaining": 5,
            },
        ]
    )
    with (
        patch.object(analytics, "inventory_view", return_value=inventory),
        patch.object(analytics, "database_configured", return_value=False),
    ):
        response = client.get("/api/v1/inventory?limit=3")

    assert response.status_code == 200
    items = response.json()["inventory_batches"]
    assert [item["batch_id"] for item in items] == [
        "B-EXPIRED",
        "B-TODAY",
        "B-SAFE",
    ]
    assert "do not sell or discount" in items[0]["snapshot_expiry_status"]
    assert "do not discount" in items[1]["snapshot_expiry_status"]
    assert response.json()["total"] == 3


def test_sales_history_and_waste_report_return_recorded_aggregates(
    client: TestClient,
) -> None:
    records = pd.DataFrame(
        [
            {
                "date": "2026-10-20",
                "category": "Produce",
                "units_sold": 7,
                "waste_units": 2,
            },
            {
                "date": "2026-10-20",
                "category": "Produce",
                "units_sold": 5,
                "waste_units": 1,
            },
            {
                "date": "2026-10-21",
                "category": "Dairy",
                "units_sold": 4,
                "waste_units": 3,
            },
        ]
    )
    with (
        patch.object(analytics, "read_csv", return_value=records),
        patch.object(analytics, "database_configured", return_value=False),
    ):
        sales_response = client.get("/api/v1/sales-history")
        waste_response = client.get("/api/v1/waste-report")

    assert sales_response.status_code == 200
    assert sales_response.json()["total_units_sold"] == 16
    assert sales_response.json()["sales_by_day"] == [
        {"date": "2026-10-20", "units_sold": 12},
        {"date": "2026-10-21", "units_sold": 4},
    ]
    assert waste_response.status_code == 200
    assert waste_response.json()["recorded_waste_units"] == 6
    assert waste_response.json()["category_breakdown"] == [
        {"category": "Dairy", "waste_units": 3},
        {"category": "Produce", "waste_units": 3},
    ]
    assert waste_response.json()["daily_count"] == 2


def test_read_endpoints_reject_invalid_pagination(client: TestClient) -> None:
    assert client.get("/api/v1/products?limit=0").status_code == 422
    assert client.get("/api/v1/inventory?offset=-1").status_code == 422


def test_missing_model_artifact_returns_clear_service_unavailable_error(
    tmp_path,
) -> None:
    analytics.load_model.cache_clear()
    with patch.object(analytics, "ARTIFACTS", tmp_path):
        with pytest.raises(HTTPException) as error:
            analytics.load_model("expiry_risk")
    analytics.load_model.cache_clear()

    assert error.value.status_code == 503
    assert "expiry_risk.joblib is missing" in error.value.detail
    assert "Train the models first" in error.value.detail
