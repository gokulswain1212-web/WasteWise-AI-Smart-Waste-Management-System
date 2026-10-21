from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from app.api.v1.analytics import (
    DISCOUNT_RECOMMENDATIONS_PATH,
    DISCOUNT_SCENARIOS_PATH,
    discount_recommendations,
)


def test_discount_recommendations_rebuild_missing_rates_from_saved_model() -> None:
    recommendation_artifact = pd.DataFrame(
        {
            "batch_id": [1],
            "product_id": [10],
            "days_to_expiry": [3],
            "quantity_remaining": [12],
            "predicted_gross_margin": [100.0],
        }
    )
    scenarios = pd.DataFrame(
        [
            {
                "batch_id": 1,
                "product_id": 10,
                "days_to_expiry": 3,
                "quantity_remaining": 12,
                "discount_pct": 20,
            },
            {
                "batch_id": 1,
                "product_id": 10,
                "days_to_expiry": 3,
                "quantity_remaining": 12,
                "discount_pct": 10,
            },
            {
                "batch_id": 2,
                "product_id": 20,
                "days_to_expiry": -1,
                "quantity_remaining": 5,
                "discount_pct": 5,
            },
            {
                "batch_id": 3,
                "product_id": 30,
                "days_to_expiry": 0,
                "quantity_remaining": 5,
                "discount_pct": 25,
            },
        ]
    )
    model = MagicMock()
    model.predict.return_value = [110.0, 100.0, 250.0, 200.0]

    def read_csv(path, required=True):
        if path == DISCOUNT_RECOMMENDATIONS_PATH:
            return recommendation_artifact
        assert path == DISCOUNT_SCENARIOS_PATH
        return scenarios

    with (
        patch("app.api.v1.analytics.read_csv", side_effect=read_csv),
        patch(
            "app.api.v1.analytics.get_features",
            return_value=[
                "days_to_expiry",
                "quantity_remaining",
                "discount_pct",
                "product_id",
            ],
        ),
        patch("app.api.v1.analytics.load_model", return_value=model),
    ):
        result = discount_recommendations(limit=25)

    assert result["scenario_rows_loaded"] == 4
    assert result["excluded_expired_scenarios"] == 1
    assert result["excluded_expiring_today_scenarios"] == 1
    assert result["eligible_scenarios"] == 1
    assert result["recommendations"] == [
        {
            "batch_id": 1,
            "product_id": 10,
            "days_to_expiry": 3,
            "quantity_remaining": 12,
            "discount_pct": 20,
            "predicted_gross_margin": 110.0,
        }
    ]
    model.predict.assert_called_once()
