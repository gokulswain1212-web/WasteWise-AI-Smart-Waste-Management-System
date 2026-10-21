from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[2]
RAW_DATA = ROOT / "ml" / "data" / "raw"
ARTIFACT_DIR = ROOT / "artifacts"
RANDOM_STATE = 42


def make_pipeline(
    estimator: Any,
    numeric_features: list[str],
    categorical_features: list[str],
) -> Pipeline:
    numeric = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median"))]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric, numeric_features),
            ("categorical", categorical, categorical_features),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[("preprocessor", preprocessor), ("model", estimator)]
    )


def regression_metrics(
    actual: pd.Series | np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float]:
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    denominator = float(np.abs(actual_values).sum())
    return {
        "mae": float(mean_absolute_error(actual_values, predicted_values)),
        "rmse": float(np.sqrt(mean_squared_error(actual_values, predicted_values))),
        "wape": (
            float(np.abs(actual_values - predicted_values).sum() / denominator)
            if denominator
            else 0.0
        ),
    }


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_pipeline(name: str, pipeline: Pipeline, metadata: dict[str, Any]) -> None:
    joblib.dump(pipeline, ARTIFACT_DIR / f"{name}.joblib")
    save_json(ARTIFACT_DIR / f"{name}_metadata.json", metadata)


def require_columns(frame: pd.DataFrame, columns: list[str], filename: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{filename} is missing required columns: {missing}")


def train_demand_forecast() -> dict[str, Any]:
    sales_path = RAW_DATA / "sales_train_evaluation.csv"
    calendar_path = RAW_DATA / "calendar.csv"
    prices_path = RAW_DATA / "sell_prices.csv"
    metadata_columns = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    metadata = pd.read_csv(sales_path, usecols=metadata_columns)
    metadata["sample_key"] = metadata["id"].map(
        lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    )
    selected = (
        metadata.sort_values(["store_id", "dept_id", "sample_key"])
        .groupby(["store_id", "dept_id"], sort=False, as_index=False)
        .head(1)
        .drop(columns="sample_key")
        .reset_index(drop=True)
    )
    selected_ids = set(selected["id"])
    day_columns = [
        column
        for column in pd.read_csv(sales_path, nrows=0).columns
        if column.startswith("d_")
    ]
    if not day_columns:
        raise ValueError(f"No daily sales columns found in {sales_path}")

    identifier_columns = metadata_columns
    selected_parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        sales_path,
        usecols=identifier_columns + day_columns,
        chunksize=128,
    ):
        rows = chunk[chunk["id"].isin(selected_ids)]
        if not rows.empty:
            selected_parts.append(
                rows.melt(
                    id_vars=identifier_columns,
                    value_vars=day_columns,
                    var_name="d",
                    value_name="sales",
                )
            )
    if not selected_parts:
        raise ValueError("Could not load any selected sales series.")
    sales = pd.concat(selected_parts, ignore_index=True)
    sales["sales"] = pd.to_numeric(sales["sales"], errors="coerce")

    calendar = pd.read_csv(calendar_path)
    require_columns(
        calendar,
        ["d", "date", "wm_yr_wk", "event_name_1", "event_name_2"],
        calendar_path.name,
    )
    calendar["date"] = pd.to_datetime(calendar["date"], errors="raise")
    calendar["is_event"] = (
        calendar["event_name_1"].notna() | calendar["event_name_2"].notna()
    ).astype("int8")
    snap_columns = {
        "CA": "snap_CA",
        "TX": "snap_TX",
        "WI": "snap_WI",
    }
    calendar_columns = [
        "d",
        "date",
        "wm_yr_wk",
        "weekday",
        "month",
        "year",
        "is_event",
    ]
    calendar = calendar[calendar_columns + list(snap_columns.values())]
    sales = sales.merge(calendar, on="d", how="left", validate="many_to_one")
    sales["snap"] = 0
    for state, column in snap_columns.items():
        state_rows = sales["state_id"].eq(state)
        sales.loc[state_rows, "snap"] = sales.loc[state_rows, column].fillna(0)
    sales = sales.drop(columns=list(snap_columns.values()))

    selected_pairs = selected[["store_id", "item_id"]].drop_duplicates()
    price_parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        prices_path,
        usecols=["store_id", "item_id", "wm_yr_wk", "sell_price"],
        chunksize=200_000,
    ):
        matches = chunk.merge(
            selected_pairs, on=["store_id", "item_id"], how="inner"
        )
        if not matches.empty:
            price_parts.append(matches)
    if not price_parts:
        raise ValueError("No sell prices found for the selected sales series.")
    prices = pd.concat(price_parts, ignore_index=True)
    sales = sales.merge(
        prices,
        on=["store_id", "item_id", "wm_yr_wk"],
        how="left",
        validate="many_to_one",
    )
    sales = sales.sort_values(["id", "date"]).reset_index(drop=True)

    grouped = sales.groupby("id", sort=False)
    previous_week_price = grouped["sell_price"].shift(7)
    sales["discount_pct"] = (
        (1 - sales["sell_price"] / previous_week_price)
        .where(previous_week_price.gt(0), 0)
        .clip(lower=0, upper=1)
        .fillna(0)
    )
    sales["promotion"] = sales["discount_pct"].gt(0).astype("int8")
    sales["day_of_week"] = sales["date"].dt.dayofweek
    sales["day_of_year"] = sales["date"].dt.dayofyear
    sales["week_sin"] = np.sin(2 * np.pi * sales["day_of_year"] / 365.25)
    sales["week_cos"] = np.cos(2 * np.pi * sales["day_of_year"] / 365.25)
    for lag in (1, 7, 28):
        sales[f"sales_lag_{lag}"] = grouped["sales"].shift(lag)
    for window in (7, 28):
        sales[f"sales_rolling_mean_{window}"] = grouped["sales"].transform(
            lambda values: values.shift(1).rolling(window, min_periods=window).mean()
        )

    numeric_features = [
        "day_of_week",
        "month",
        "year",
        "day_of_year",
        "week_sin",
        "week_cos",
        "is_event",
        "snap",
        "sell_price",
        "discount_pct",
        "promotion",
        "sales_lag_1",
        "sales_lag_7",
        "sales_lag_28",
        "sales_rolling_mean_7",
        "sales_rolling_mean_28",
    ]
    categorical_features = ["item_id", "dept_id", "cat_id", "store_id"]
    usable = sales.dropna(subset=["sales"] + [
        "sales_lag_1",
        "sales_lag_7",
        "sales_lag_28",
        "sales_rolling_mean_7",
        "sales_rolling_mean_28",
    ]).copy()
    last_date = usable["date"].max()
    cutoff = last_date - pd.Timedelta(days=27)
    train_mask = usable["date"] < cutoff
    test_mask = usable["date"] >= cutoff
    if not train_mask.any() or not test_mask.any():
        raise ValueError("Demand data does not support a 28-day chronological holdout.")

    estimator = ExtraTreesRegressor(
        n_estimators=160,
        min_samples_leaf=2,
        max_features=0.9,
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    pipeline = make_pipeline(estimator, numeric_features, categorical_features)
    pipeline.fit(usable.loc[train_mask, numeric_features + categorical_features],
                 usable.loc[train_mask, "sales"])
    predictions = pipeline.predict(
        usable.loc[test_mask, numeric_features + categorical_features]
    )
    test = usable.loc[test_mask]
    metrics = regression_metrics(test["sales"], predictions)
    metrics["lag_7_baseline_wape"] = regression_metrics(
        test["sales"], test["sales_lag_7"].to_numpy()
    )["wape"]
    metrics.update(
        {
            "train_rows": int(train_mask.sum()),
            "test_rows": int(test_mask.sum()),
            "series_count": int(usable["id"].nunique()),
            "holdout_start": cutoff.date().isoformat(),
            "holdout_end": last_date.date().isoformat(),
            "split": "chronological last 28 calendar days",
        }
    )
    pipeline.fit(usable[numeric_features + categorical_features], usable["sales"])
    save_pipeline(
        "demand_forecast",
        pipeline,
        {
            "features": numeric_features + categorical_features,
            "target": "sales",
            "metrics": metrics,
            "promotion_definition": "current weekly sell price below its value seven days earlier",
        },
    )
    return metrics


def train_expiry_risk() -> dict[str, Any]:
    path = RAW_DATA / "inventory_batches.csv"
    frame = pd.read_csv(path)
    required = [
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
    ]
    require_columns(frame, required, path.name)
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="raise")
    frame["received_at"] = pd.to_datetime(frame["received_at"], errors="raise")
    frame["days_since_received"] = (
        frame["snapshot_date"] - frame["received_at"]
    ).dt.days
    frame["snapshot_month"] = frame["snapshot_date"].dt.month
    frame["snapshot_day_of_week"] = frame["snapshot_date"].dt.dayofweek
    numeric_features = [
        "initial_quantity",
        "quantity_remaining",
        "days_to_expiry",
        "avg_daily_sales_7d",
        "expected_demand_before_expiry",
        "unit_price",
        "unit_cost",
        "discount_pct",
        "days_since_received",
        "snapshot_month",
        "snapshot_day_of_week",
    ]
    categorical_features = ["product_id", "category"]
    features = numeric_features + categorical_features
    forbidden_features = {
        "expiry_risk_label",
        "waste_units_actual_simulated",
        "batch_id",
        "expiry_date",
        "received_at",
        "snapshot_date",
    }
    if forbidden_features.intersection(features):
        raise ValueError("Expiry-risk target or identifier leaked into model inputs.")
    frame["expiry_risk_label"] = pd.to_numeric(
        frame["expiry_risk_label"], errors="raise"
    ).astype(int)
    dates = np.sort(frame["snapshot_date"].unique())
    cutoff = dates[max(1, int(len(dates) * 0.8))]
    train_mask = frame["snapshot_date"] < cutoff
    test_mask = frame["snapshot_date"] >= cutoff
    if not train_mask.any() or not test_mask.any():
        raise ValueError("Inventory batches do not support a chronological holdout.")

    pipeline = make_pipeline(
        ExtraTreesClassifier(
            n_estimators=240,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=-1,
            random_state=RANDOM_STATE,
        ),
        numeric_features,
        categorical_features,
    )
    x_train = frame.loc[train_mask, features]
    y_train = frame.loc[train_mask, "expiry_risk_label"]
    x_test = frame.loc[test_mask, features]
    y_test = frame.loc[test_mask, "expiry_risk_label"]
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    probabilities = pipeline.predict_proba(x_test)[:, 1]
    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "roc_auc": (
            float(roc_auc_score(y_test, probabilities))
            if y_test.nunique() == 2
            else None
        ),
        "train_rows": int(train_mask.sum()),
        "test_rows": int(test_mask.sum()),
        "holdout_start": pd.Timestamp(cutoff).date().isoformat(),
        "split": "chronological by snapshot_date",
    }
    pipeline.fit(frame[features], frame["expiry_risk_label"])
    save_pipeline(
        "expiry_risk",
        pipeline,
        {"features": features, "target": "expiry_risk_label", "metrics": metrics},
    )
    return metrics


def train_food_waste() -> dict[str, Any]:
    path = RAW_DATA / "perishable_inventory - perishable_inventory.csv"
    frame = pd.read_csv(path)
    required = [
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
    ]
    require_columns(frame, required, path.name)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values(["product_id", "date"]).reset_index(drop=True)
    grouped = frame.groupby("product_id", sort=False)
    frame["target_waste_units"] = grouped["waste_units"].shift(-1)
    frame["target_date"] = grouped["date"].shift(-1)
    frame["ending_stock_estimate"] = (
        frame["opening_stock"] + frame["units_received"] - frame["units_sold"]
    )
    frame["target_day_of_week"] = frame["target_date"].dt.dayofweek
    frame["target_month"] = frame["target_date"].dt.month
    frame = frame.dropna(subset=["target_waste_units", "target_date"]).copy()

    numeric_features = [
        "opening_stock",
        "units_received",
        "units_sold",
        "ending_stock_estimate",
        "unit_price",
        "discount_pct",
        "days_to_expiry",
        "temperature_c",
        "stockout_flag",
        "target_day_of_week",
        "target_month",
    ]
    categorical_features = ["product_id", "category"]
    features = numeric_features + categorical_features
    if "waste_units" in features or "target_waste_units" in features:
        raise ValueError("Food-waste outcome leaked into model inputs.")

    dates = np.sort(frame["target_date"].unique())
    cutoff = dates[max(1, int(len(dates) * 0.8))]
    train_mask = frame["target_date"] < cutoff
    test_mask = frame["target_date"] >= cutoff
    if not train_mask.any() or not test_mask.any():
        raise ValueError("Perishable inventory does not support a chronological holdout.")
    estimator = ExtraTreesRegressor(
        n_estimators=240,
        min_samples_leaf=2,
        max_features=0.9,
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    pipeline = make_pipeline(estimator, numeric_features, categorical_features)
    pipeline.fit(
        frame.loc[train_mask, features],
        frame.loc[train_mask, "target_waste_units"],
    )
    predictions = pipeline.predict(frame.loc[test_mask, features])
    test_target = frame.loc[test_mask, "target_waste_units"]
    metrics = regression_metrics(test_target, predictions)
    metrics.update(
        {
            "train_rows": int(train_mask.sum()),
            "test_rows": int(test_mask.sum()),
            "holdout_start": pd.Timestamp(cutoff).date().isoformat(),
            "prediction_horizon_days": 1,
            "split": "chronological by future target date",
        }
    )
    pipeline.fit(frame[features], frame["target_waste_units"])
    save_pipeline(
        "food_waste",
        pipeline,
        {
            "features": features,
            "target": "waste_units on the next date for the same product",
            "metrics": metrics,
            "input_alignment": "inventory features from the day before the predicted waste date",
        },
    )
    return metrics


def train_discount_recommendation() -> dict[str, Any]:
    path = RAW_DATA / "discount_scenarios_simulated (1).csv"
    frame = pd.read_csv(path)
    required = [
        "batch_id",
        "product_id",
        "days_to_expiry",
        "quantity_remaining",
        "discount_pct",
        "estimated_gross_margin_simulated",
    ]
    require_columns(frame, required, path.name)
    numeric_features = ["days_to_expiry", "quantity_remaining", "discount_pct"]
    categorical_features = ["product_id"]
    features = numeric_features + categorical_features
    target = "estimated_gross_margin_simulated"
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE)
    train_indices, test_indices = next(
        splitter.split(frame[features], frame[target], groups=frame["batch_id"])
    )
    pipeline = make_pipeline(
        ExtraTreesRegressor(
            n_estimators=240,
            min_samples_leaf=2,
            max_features=0.9,
            n_jobs=-1,
            random_state=RANDOM_STATE,
        ),
        numeric_features,
        categorical_features,
    )
    pipeline.fit(frame.iloc[train_indices][features], frame.iloc[train_indices][target])
    predictions = pipeline.predict(frame.iloc[test_indices][features])
    metrics = regression_metrics(frame.iloc[test_indices][target], predictions)
    metrics.update(
        {
            "train_rows": int(len(train_indices)),
            "test_rows": int(len(test_indices)),
            "train_batches": int(frame.iloc[train_indices]["batch_id"].nunique()),
            "test_batches": int(frame.iloc[test_indices]["batch_id"].nunique()),
            "split": "grouped by batch_id to keep scenarios for a batch together",
            "data_status": "simulated prototype; not evidence of real customer price response",
        }
    )
    pipeline.fit(frame[features], frame[target])

    recommendations = frame[["batch_id", "product_id", "days_to_expiry", "quantity_remaining"]].copy()
    recommendations["predicted_gross_margin_simulated"] = pipeline.predict(
        frame[features]
    )
    best_rows = recommendations.groupby("batch_id")[
        "predicted_gross_margin_simulated"
    ].idxmax()
    recommendations = recommendations.loc[best_rows].copy()
    recommendations = recommendations.rename(
        columns={"predicted_gross_margin_simulated": "predicted_gross_margin"}
    )
    recommendations.to_csv(
        ARTIFACT_DIR / "discount_recommendations.csv", index=False
    )
    save_pipeline(
        "discount_recommendation",
        pipeline,
        {
            "features": features,
            "target": target,
            "metrics": metrics,
            "data_status": "simulated prototype; not evidence of real customer price response",
        },
    )
    return metrics


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    trainers = {
        "demand_forecast": train_demand_forecast,
        "expiry_risk": train_expiry_risk,
        "food_waste": train_food_waste,
        "discount_recommendation": train_discount_recommendation,
    }
    results: dict[str, Any] = {}
    for name, train in trainers.items():
        print(f"Training {name}...", flush=True)
        results[name] = train()
        print(json.dumps({name: results[name]}, indent=2), flush=True)
    save_json(ARTIFACT_DIR / "training_metrics.json", results)
    print(f"All models and metrics saved to {ARTIFACT_DIR}", flush=True)


if __name__ == "__main__":
    main()
