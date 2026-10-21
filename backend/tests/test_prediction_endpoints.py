from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import quoted_name

from app.api.v1 import analytics
from app.main import app, get_api_identity


DEMAND_FEATURES = [
    "day_of_week", "month", "year", "day_of_year", "week_sin", "week_cos",
    "is_event", "snap", "sell_price", "discount_pct", "promotion",
    "sales_lag_1", "sales_lag_7", "sales_lag_28",
    "sales_rolling_mean_7", "sales_rolling_mean_28",
    "item_id", "dept_id", "cat_id", "store_id",
]


class DemandModel:
    def __init__(self, result: list[float] | None = None) -> None:
        self.result = result
        self.inputs: list[pd.DataFrame] = []

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        self.inputs.append(frame.copy())
        if self.result is None:
            return np.full(len(frame), 3.5)
        return np.asarray(self.result)


class ExpiryModel:
    classes_ = np.array([0, 1])

    def __init__(self, result: list[list[float]]) -> None:
        self.result = np.asarray(result, dtype=float)
        self.inputs: list[pd.DataFrame] = []

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        self.inputs.append(frame.copy())
        return self.result


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_api_identity] = lambda: "test-user"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_api_identity, None)


@pytest.fixture
def demand_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2026-01-01", periods=35, freq="D")
    calendar = pd.DataFrame(
        {
            "d": [f"d_{index}" for index in range(1, len(dates) + 1)],
            "date": dates,
            "wm_yr_wk": ["week-1"] * len(dates),
            "event_name_1": [None] * len(dates),
            "event_name_2": [None] * len(dates),
            "snap_CA": [0] * len(dates),
            "snap_TX": [0] * len(dates),
            "snap_WI": [0] * len(dates),
        }
    )
    history = pd.DataFrame(
        {
            "id": ["FOODS_1_001_CA_1"] * 28,
            "item_id": ["FOODS_1_001"] * 28,
            "dept_id": ["FOODS_1"] * 28,
            "cat_id": ["FOODS"] * 28,
            "store_id": ["CA_1"] * 28,
            "state_id": ["CA"] * 28,
            "d": calendar["d"].iloc[:28].tolist(),
            "sales": list(range(1, 29)),
        }
    )
    prices = pd.DataFrame(
        [{"store_id": "CA_1", "item_id": "FOODS_1_001", "wm_yr_wk": "week-1", "sell_price": 10.0}]
    )
    return history, calendar, prices


def test_demand_forecast_price_filter_preserves_only_selected_pairs() -> None:
    prices = pd.DataFrame(
        [
            {"store_id": "CA_1", "item_id": "item-a", "wm_yr_wk": "week-1", "sell_price": 10.0},
            {"store_id": "CA_1", "item_id": "item-b", "wm_yr_wk": "week-1", "sell_price": 12.0},
            {"store_id": "TX_1", "item_id": "unselected", "wm_yr_wk": "week-1", "sell_price": 1.0},
            {"store_id": "TX_1", "item_id": "unselected", "wm_yr_wk": "week-1", "sell_price": 1.0},
        ]
    )
    selected_pairs = pd.DataFrame(
        [{"store_id": "CA_1", "item_id": "item-a"}]
    )

    result = analytics.filter_demand_prices(prices, selected_pairs)

    assert result[["store_id", "item_id", "wm_yr_wk", "sell_price"]].to_dict(
        orient="records"
    ) == [
        {"store_id": "CA_1", "item_id": "item-a", "wm_yr_wk": "week-1", "sell_price": 10.0}
    ]


def test_demand_forecast_returns_490_predictions_for_70_series(
    demand_inputs: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    history, calendar, prices = demand_inputs
    histories = []
    selected_prices = []
    for index in range(70):
        item_id = f"FOODS_1_{index:03d}"
        series_history = history.copy()
        series_history["id"] = f"{item_id}_CA_1"
        series_history["item_id"] = item_id
        histories.append(series_history)
        selected_prices.append(
            {
                "store_id": "CA_1",
                "item_id": item_id,
                "wm_yr_wk": "week-1",
                "sell_price": 10.0,
            }
        )
    all_prices = pd.concat(
        [
            pd.DataFrame(selected_prices),
            pd.DataFrame(
                [
                    {
                        "store_id": "TX_1",
                        "item_id": "unselected",
                        "wm_yr_wk": "week-1",
                        "sell_price": 1.0,
                    }
                    for _ in range(1_000)
                ]
            ),
        ],
        ignore_index=True,
    )
    model = DemandModel()

    result = analytics.build_demand_forecast(
        pd.concat(histories, ignore_index=True),
        calendar,
        all_prices,
        model,
        DEMAND_FEATURES,
        horizon_days=7,
    )

    assert result["series_count"] == 70
    assert len(result["predictions"]) == 490
    assert len(model.inputs) == 7
    assert all(len(frame) == 70 for frame in model.inputs)


def test_demand_forecast_maps_day_ids_to_dates_and_uses_model_features(
    demand_inputs: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    model = DemandModel()

    result = analytics.build_demand_forecast(
        *demand_inputs, model, DEMAND_FEATURES, horizon_days=2
    )

    assert result["historical_data_through"] == "2026-01-28"
    assert result["forecast_start"] == "2026-01-29"
    assert result["forecast_end"] == "2026-01-30"
    assert result["series_count"] == 1
    assert len(result["predictions"]) == 2
    assert result["predictions"][0]["predicted_units"] == 3.5
    assert list(model.inputs[0].columns) == DEMAND_FEATURES
    assert model.inputs[0].iloc[0]["sales_lag_1"] == 28
    assert model.inputs[0].iloc[0]["sales_lag_7"] == 22
    assert model.inputs[0].iloc[0]["sales_lag_28"] == 1
    assert model.inputs[0].iloc[0]["sales_rolling_mean_7"] == 25
    assert model.inputs[0].iloc[0]["sales_rolling_mean_28"] == 14.5


def test_demand_forecast_rejects_missing_features_and_malformed_history(
    demand_inputs: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    with pytest.raises(HTTPException) as missing_features:
        analytics.build_demand_forecast(
            *demand_inputs, DemandModel(), DEMAND_FEATURES[:-1], horizon_days=1
        )
    assert missing_features.value.status_code == 503
    assert "missing trained features" in missing_features.value.detail

    malformed = demand_inputs[0].copy()
    malformed["sales"] = malformed["sales"].astype(object)
    malformed.loc[0, "sales"] = "not-a-number"
    with pytest.raises(HTTPException) as malformed_history:
        analytics.build_demand_forecast(
            malformed, demand_inputs[1], demand_inputs[2],
            DemandModel(), DEMAND_FEATURES, horizon_days=1,
        )
    assert malformed_history.value.status_code == 422


def test_demand_forecast_rejects_empty_history_and_missing_future_calendar(
    demand_inputs: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    with pytest.raises(HTTPException) as empty_history:
        analytics.build_demand_forecast(
            demand_inputs[0].iloc[:0], demand_inputs[1], demand_inputs[2],
            DemandModel(), DEMAND_FEATURES, horizon_days=1,
        )
    assert empty_history.value.status_code == 422

    with pytest.raises(HTTPException) as no_future:
        analytics.build_demand_forecast(
            *demand_inputs, DemandModel(), DEMAND_FEATURES, horizon_days=8
        )
    assert no_future.value.status_code == 503


def test_demand_forecast_rejects_malformed_model_output(
    demand_inputs: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    with pytest.raises(HTTPException) as malformed_output:
        analytics.build_demand_forecast(
            *demand_inputs,
            DemandModel([np.nan]),
            DEMAND_FEATURES,
            horizon_days=1,
        )
    assert malformed_output.value.status_code == 500
    assert "malformed or non-finite predictions" in malformed_output.value.detail


def test_demand_endpoint_returns_forecast_and_validates_horizon(
    client: TestClient,
    demand_inputs: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    analytics.load_model.cache_clear()
    with (
        patch.object(analytics, "get_features", return_value=DEMAND_FEATURES),
        patch.object(analytics, "load_demand_forecast_inputs", return_value=demand_inputs),
        patch.object(analytics, "load_model", return_value=DemandModel()),
    ):
        response = client.get("/api/v1/predictions/demand-forecast?horizon_days=2")
        invalid_response = client.get(
            "/api/v1/predictions/demand-forecast?horizon_days=29"
        )

    assert response.status_code == 200
    assert response.json()["horizon_days"] == 2
    assert response.json()["data_source"] == "M5 evaluation benchmark CSV"
    assert len(response.json()["predictions"]) == 2
    assert invalid_response.status_code == 422


def expiry_inventory() -> pd.DataFrame:
    snapshot = pd.Timestamp("2026-10-10")
    days = [-1, 0, 2]
    return pd.DataFrame(
        [
            {
                "batch_id": f"B-{index}",
                "product_id": f"P-{index}",
                "product_name": f"Product {index}",
                "category": "Produce",
                "received_at": "2026-10-01",
                "snapshot_date": snapshot,
                "expiry_date": snapshot + pd.Timedelta(days=day),
                "initial_quantity": 10,
                "quantity_remaining": 5,
                "days_to_expiry": day,
                "avg_daily_sales_7d": 2.0,
                "expected_demand_before_expiry": 4.0,
                "unit_price": 3.0,
                "unit_cost": 1.5,
                "discount_pct": 5.0,
            }
            for index, day in enumerate(days)
        ]
    )


def test_expiry_endpoint_accepts_percent_discount_inputs_and_returns_contract(
    client: TestClient,
) -> None:
    model = ExpiryModel([[0.1, 0.9], [0.4, 0.6], [0.8, 0.2]])
    with (
        patch.object(analytics, "inventory_view", return_value=expiry_inventory()),
        patch.object(analytics, "get_features", return_value=[
            "initial_quantity", "quantity_remaining", "days_to_expiry",
            "avg_daily_sales_7d", "expected_demand_before_expiry", "unit_price",
            "unit_cost", "discount_pct", "days_since_received", "snapshot_month",
            "snapshot_day_of_week", "product_id", "category",
        ]),
        patch.object(
            analytics,
            "load_model",
            return_value=model,
        ),
    ):
        response = client.get("/api/v1/predictions/expiry-risk?min_probability=0.5")

    assert response.status_code == 200
    result = response.json()
    assert result["batches_at_or_above_threshold"] == 2
    assert result["predictions"][0]["snapshot_expiry_status"].startswith("EXPIRED")
    assert "do not sell or discount" in result["predictions"][0]["snapshot_expiry_status"]
    assert result["predictions"][0]["expiry_date"].startswith("2026-10-09T00:00:00")
    assert result["predictions"][0]["quantity_at_risk"] == 5
    assert result["predictions"][0]["risk_category"] == "HIGH"
    assert result["predictions"][1]["snapshot_expiry_status"].startswith(
        "Expires on recorded snapshot date"
    )
    assert result["predictions"][1]["risk_category"] == "MEDIUM"
    assert model.inputs[0].iloc[0]["discount_pct"] == 5.0


def test_expiry_prediction_normalizes_sqlalchemy_column_names(
    client: TestClient,
) -> None:
    inventory = expiry_inventory()
    inventory.columns = [quoted_name(column, False) for column in inventory.columns]
    model = ExpiryModel([[0.1, 0.9], [0.4, 0.6], [0.8, 0.2]])
    features = [
        "initial_quantity", "quantity_remaining", "days_to_expiry",
        "avg_daily_sales_7d", "expected_demand_before_expiry", "unit_price",
        "unit_cost", "discount_pct", "days_since_received", "snapshot_month",
        "snapshot_day_of_week", "product_id", "category",
    ]
    model.feature_names_in_ = np.array(features)
    with (
        patch.object(analytics, "inventory_view", return_value=inventory),
        patch.object(analytics, "get_features", return_value=features),
        patch.object(analytics, "load_model", return_value=model),
    ):
        response = client.get("/api/v1/predictions/expiry-risk")

    assert response.status_code == 200
    assert len(model.inputs) == 1
    assert all(type(column) is str for column in model.inputs[0].columns)
    assert list(model.inputs[0].columns) == features


def test_expiry_rejects_model_feature_order_mismatch(
    client: TestClient,
) -> None:
    model = ExpiryModel([[0.1, 0.9], [0.4, 0.6], [0.8, 0.2]])
    model.feature_names_in_ = np.array(["category", "product_id"])
    with (
        patch.object(analytics, "inventory_view", return_value=expiry_inventory()),
        patch.object(analytics, "get_features", return_value=[
            "initial_quantity", "quantity_remaining", "days_to_expiry",
            "avg_daily_sales_7d", "expected_demand_before_expiry", "unit_price",
            "unit_cost", "discount_pct", "days_since_received", "snapshot_month",
            "snapshot_day_of_week", "product_id", "category",
        ]),
        patch.object(analytics, "load_model", return_value=model),
    ):
        response = client.get("/api/v1/predictions/expiry-risk")

    assert response.status_code == 503
    assert "features do not match" in response.json()["detail"]
    assert model.inputs == []


@pytest.mark.parametrize(
    ("threshold", "expected_batches"),
    [(0, 3), (1, 1)],
)
def test_expiry_threshold_boundary_values(
    client: TestClient,
    threshold: int,
    expected_batches: int,
) -> None:
    with (
        patch.object(analytics, "inventory_view", return_value=expiry_inventory()),
        patch.object(analytics, "get_features", return_value=[
            "initial_quantity", "quantity_remaining", "days_to_expiry",
            "avg_daily_sales_7d", "expected_demand_before_expiry", "unit_price",
            "unit_cost", "discount_pct", "days_since_received", "snapshot_month",
            "snapshot_day_of_week", "product_id", "category",
        ]),
        patch.object(
            analytics,
            "load_model",
            return_value=ExpiryModel([[0.1, 0.9], [0.4, 0.6], [0.0, 1.0]]),
        ),
    ):
        response = client.get(
            f"/api/v1/predictions/expiry-risk?min_probability={threshold}"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["min_probability"] == threshold
    assert payload["batches_at_or_above_threshold"] == expected_batches
    assert len(payload["predictions"]) == expected_batches
    assert {"batch_id", "predicted_expiry_risk", "risk_category"} <= set(
        payload["predictions"][0]
    )


def test_expiry_endpoint_rejects_malformed_inputs_and_model_probabilities(
    client: TestClient,
) -> None:
    inventory = expiry_inventory()
    inventory["quantity_remaining"] = inventory["quantity_remaining"].astype(object)
    inventory.loc[0, "quantity_remaining"] = "invalid"
    with patch.object(analytics, "inventory_view", return_value=inventory):
        malformed = client.get("/api/v1/predictions/expiry-risk")
    assert malformed.status_code == 500

    with (
        patch.object(analytics, "inventory_view", return_value=expiry_inventory()),
        patch.object(analytics, "get_features", return_value=["missing_feature"]),
    ):
        missing_feature = client.get("/api/v1/predictions/expiry-risk")
    assert missing_feature.status_code == 500
    assert "missing required columns" in missing_feature.json()["detail"]

    with (
        patch.object(analytics, "inventory_view", return_value=expiry_inventory()),
        patch.object(analytics, "get_features", return_value=[
            "initial_quantity", "quantity_remaining", "days_to_expiry",
            "avg_daily_sales_7d", "expected_demand_before_expiry", "unit_price",
            "unit_cost", "discount_pct", "days_since_received", "snapshot_month",
            "snapshot_day_of_week", "product_id", "category",
        ]),
        patch.object(
            analytics,
            "load_model",
            return_value=ExpiryModel([[0.2, 0.9], [0.4, 0.6], [0.8, 0.2]]),
        ),
    ):
        bad_probabilities = client.get("/api/v1/predictions/expiry-risk")
    assert bad_probabilities.status_code == 500
    assert "invalid probability" in bad_probabilities.json()["detail"]


def test_expiry_endpoint_handles_empty_data_and_invalid_threshold(
    client: TestClient,
) -> None:
    empty = expiry_inventory().iloc[:0]
    with patch.object(analytics, "inventory_view", return_value=empty):
        response = client.get("/api/v1/predictions/expiry-risk")
        invalid_threshold = client.get(
            "/api/v1/predictions/expiry-risk?min_probability=1.1"
        )

    assert response.status_code == 200
    assert response.json()["predictions"] == []
    assert response.json()["batches_at_or_above_threshold"] == 0
    assert invalid_threshold.status_code == 422


def test_expiry_invalid_and_omitted_query_parameters_have_expected_status(
    client: TestClient,
) -> None:
    with (
        patch.object(analytics, "inventory_view", return_value=expiry_inventory()),
        patch.object(analytics, "get_features", return_value=[
            "initial_quantity", "quantity_remaining", "days_to_expiry",
            "avg_daily_sales_7d", "expected_demand_before_expiry", "unit_price",
            "unit_cost", "discount_pct", "days_since_received", "snapshot_month",
            "snapshot_day_of_week", "product_id", "category",
        ]),
        patch.object(
            analytics,
            "load_model",
            return_value=ExpiryModel([[0.1, 0.9], [0.4, 0.6], [0.8, 0.2]]),
        ),
    ):
        default_response = client.get("/api/v1/predictions/expiry-risk")
        malformed_response = client.get(
            "/api/v1/predictions/expiry-risk?min_probability=not-a-number"
        )
        empty_response = client.get(
            "/api/v1/predictions/expiry-risk?min_probability="
        )

    assert default_response.status_code == 200
    assert default_response.json()["min_probability"] == 0.5
    assert malformed_response.status_code == 422
    assert empty_response.status_code == 422


def test_expiry_invalid_dates_and_unavailable_model_are_safe_errors(
    client: TestClient,
    tmp_path,
) -> None:
    invalid_dates = expiry_inventory()
    invalid_dates["snapshot_date"] = invalid_dates["snapshot_date"].astype(object)
    invalid_dates.loc[0, "snapshot_date"] = "not-a-date"
    with patch.object(analytics, "inventory_view", return_value=invalid_dates):
        invalid_date_response = client.get("/api/v1/predictions/expiry-risk")
    assert invalid_date_response.status_code == 500
    assert "path" not in invalid_date_response.text.lower()

    analytics.load_model.cache_clear()
    with (
        patch.object(analytics, "ARTIFACTS", tmp_path),
        patch.object(analytics, "inventory_view", return_value=expiry_inventory()),
        patch.object(analytics, "get_features", return_value=[
            "initial_quantity", "quantity_remaining", "days_to_expiry",
            "avg_daily_sales_7d", "expected_demand_before_expiry", "unit_price",
            "unit_cost", "discount_pct", "days_since_received", "snapshot_month",
            "snapshot_day_of_week", "product_id", "category",
        ]),
    ):
        missing_model_response = client.get("/api/v1/predictions/expiry-risk")
    analytics.load_model.cache_clear()

    assert missing_model_response.status_code == 503
    assert "expiry_risk.joblib is missing" in missing_model_response.json()["detail"]
    assert str(tmp_path) not in missing_model_response.text


def test_expiry_database_failure_is_controlled_and_does_not_leak_details(
    client: TestClient,
) -> None:
    with (
        patch.object(analytics, "database_configured", return_value=True),
        patch.object(
            analytics,
            "get_engine",
            side_effect=RuntimeError("database internal diagnostic"),
        ),
    ):
        response = client.get("/api/v1/predictions/expiry-risk")

    assert response.status_code == 503
    assert "database internal diagnostic" not in response.text
    assert "password" not in response.text.lower()
