from __future__ import annotations

import hashlib
import json
import logging
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import database_configured, database_status, get_engine
from app.services.drift_detection import detect_data_drift

ROOT = Path(__file__).resolve().parents[4]
RAW_DATA = ROOT / "ml" / "data" / "raw"
ARTIFACTS = ROOT / "artifacts"
PRODUCTS_PATH = RAW_DATA / "products.csv"
INVENTORY_PATH = RAW_DATA / "inventory_batches.csv"
WASTE_PATH = RAW_DATA / "perishable_inventory - perishable_inventory.csv"
DISCOUNT_RECOMMENDATIONS_PATH = ARTIFACTS / "discount_recommendations.csv"
DISCOUNT_SCENARIOS_PATH = RAW_DATA / "discount_scenarios_simulated (1).csv"
DEMAND_SALES_PATH = RAW_DATA / "sales_train_evaluation.csv"
DEMAND_CALENDAR_PATH = RAW_DATA / "calendar.csv"
DEMAND_PRICES_PATH = RAW_DATA / "sell_prices.csv"
MODEL_NAMES = (
    "demand_forecast",
    "expiry_risk",
    "food_waste",
    "discount_recommendation",
)
DATASET_TABLES = {
    PRODUCTS_PATH.name: "products",
    INVENTORY_PATH.name: "inventory_batches",
    WASTE_PATH.name: "perishable_inventory",
    (ARTIFACTS / "discount_recommendations.csv").name: "discount_recommendations",
}

router = APIRouter(prefix="/api/v1", tags=["analytics"])
logger = logging.getLogger(__name__)


class ExpiryRiskThresholds(BaseModel):
    low: str
    medium: str
    high: str


class ExpiryRiskPrediction(BaseModel):
    batch_id: str | int
    product_name: str | None = None
    product_id: str | int
    category: str
    snapshot_date: str
    expiry_date: str | None = None
    days_to_expiry: int
    quantity_remaining: float
    quantity_at_risk: float
    predicted_expiry_risk: float
    risk_category: Literal["LOW", "MEDIUM", "HIGH"]
    snapshot_expiry_status: str


class ExpiryRiskResponse(BaseModel):
    min_probability: float
    risk_category_thresholds: ExpiryRiskThresholds
    data_notice: str
    batches_at_or_above_threshold: int
    predictions: list[ExpiryRiskPrediction]


@router.get("/database/status")
def database_connection_status() -> dict:
    return database_status()


def read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    table_name = DATASET_TABLES.get(path.name)
    if table_name and database_configured():
        try:
            return pd.read_sql_table(table_name, get_engine())
        except (SQLAlchemyError, OSError, ValueError, RuntimeError) as error:
            logger.exception("Failed reading configured dataset table %s", table_name)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Could not read MySQL table '{table_name}'. Check the MySQL "
                    "connection, table permissions, and required schema."
                ),
            ) from error
    if not path.exists():
        if required:
            raise HTTPException(
                status_code=503,
                detail=f"Required dataset is missing: {path.name}",
            )
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read dataset {path.name}: {error}",
        ) from error


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def get_features(name: str) -> list[str]:
    path = ARTIFACTS / f"{name}_metadata.json"
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Metadata for {name} is missing. Train the models first.",
        )
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        features = metadata["features"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        logger.exception("Failed reading model metadata for %s", name)
        raise HTTPException(
            status_code=500,
            detail=f"Could not read {name} model metadata.",
        ) from error
    if not isinstance(features, list) or not all(
        isinstance(feature, str) for feature in features
    ):
        logger.error("Invalid feature list in model metadata for %s", name)
        raise HTTPException(
            status_code=500,
            detail=f"Feature list in {name} metadata is invalid.",
        )
    return features


def filter_demand_prices(
    prices: pd.DataFrame,
    selected_pairs: pd.DataFrame,
) -> pd.DataFrame:
    """Keep only price rows for item/store pairs used by the forecast."""
    return prices.merge(
        selected_pairs[["store_id", "item_id"]].drop_duplicates(),
        on=["store_id", "item_id"],
        how="inner",
        validate="many_to_one",
    )


@lru_cache(maxsize=4)
def load_model(name: str):
    if name not in MODEL_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown model: {name}")
    path = ARTIFACTS / f"{name}.joblib"
    if not path.exists():
        logger.error("Required model artifact is missing: %s", path.name)
        raise HTTPException(
            status_code=503,
            detail=f"Model artifact {path.name} is missing. Train the models first.",
        )
    try:
        return joblib.load(path)
    except (
        OSError,
        ValueError,
        EOFError,
        ImportError,
        AttributeError,
        pickle.UnpicklingError,
    ) as error:
        logger.exception("Could not load model artifact %s", path.name)
        raise HTTPException(
            status_code=503,
            detail=f"The {name} model artifact could not be loaded.",
        ) from error


@lru_cache(maxsize=1)
def load_demand_forecast_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the same deterministic daily item/store sample used for training."""
    paths = (DEMAND_SALES_PATH, DEMAND_CALENDAR_PATH, DEMAND_PRICES_PATH)
    missing_paths = [path.name for path in paths if not path.is_file()]
    if missing_paths:
        raise HTTPException(
            status_code=503,
            detail=(
                "Demand forecast input files are missing: "
                f"{', '.join(missing_paths)}."
            ),
        )

    identifiers = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    try:
        available_columns = pd.read_csv(DEMAND_SALES_PATH, nrows=0).columns.tolist()
        missing_identifiers = sorted(set(identifiers) - set(available_columns))
        day_columns = [
            column for column in available_columns if column.startswith("d_")
        ]
        if missing_identifiers or not day_columns:
            missing = missing_identifiers or ["daily sales columns (d_*)"]
            raise HTTPException(
                status_code=503,
                detail=(
                    "Demand sales data is incompatible; missing required "
                    f"columns: {', '.join(missing)}."
                ),
            )

        metadata = pd.read_csv(DEMAND_SALES_PATH, usecols=identifiers)
        metadata["sample_key"] = metadata["id"].map(
            lambda value: hashlib.sha256(str(value).encode("utf-8")).hexdigest()
        )
        selected = (
            metadata.sort_values(["store_id", "dept_id", "sample_key"])
            .groupby(["store_id", "dept_id"], sort=False, as_index=False)
            .head(1)
            .drop(columns="sample_key")
            .reset_index(drop=True)
        )
        selected_ids = set(selected["id"])
        selected_parts: list[pd.DataFrame] = []
        for chunk in pd.read_csv(
            DEMAND_SALES_PATH,
            usecols=identifiers + day_columns,
            chunksize=128,
        ):
            rows = chunk[chunk["id"].isin(selected_ids)]
            if not rows.empty:
                selected_parts.append(
                    rows.melt(
                        id_vars=identifiers,
                        value_vars=day_columns,
                        var_name="d",
                        value_name="sales",
                    )
                )
        if not selected_parts:
            raise HTTPException(
                status_code=503,
                detail="Demand sales data contains no model-selected series.",
            )
        history = pd.concat(selected_parts, ignore_index=True)
        history["sales"] = pd.to_numeric(history["sales"], errors="coerce")

        calendar = pd.read_csv(DEMAND_CALENDAR_PATH)
        prices = pd.read_csv(
            DEMAND_PRICES_PATH,
            usecols=["store_id", "item_id", "wm_yr_wk", "sell_price"],
        )
        prices = filter_demand_prices(
            prices,
            selected[["store_id", "item_id"]],
        )
    except HTTPException:
        raise
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not parse the saved demand forecast inputs. "
                "Check the sales, calendar, and sell-price CSV formats."
            ),
        ) from error

    return history, calendar, prices


def build_demand_forecast(
    history: pd.DataFrame,
    calendar: pd.DataFrame,
    prices: pd.DataFrame,
    model: Any,
    features: list[str],
    horizon_days: int,
) -> dict[str, Any]:
    """Build iterative daily predictions from the model's actual input contract."""
    if horizon_days < 1 or horizon_days > 28:
        raise HTTPException(
            status_code=422,
            detail="horizon_days must be between 1 and 28.",
        )
    history_columns = {
        "id",
        "item_id",
        "dept_id",
        "cat_id",
        "store_id",
        "state_id",
        "d",
        "sales",
    }
    missing_history = sorted(history_columns - set(history.columns))
    calendar_columns = {
        "d",
        "date",
        "wm_yr_wk",
        "event_name_1",
        "event_name_2",
        "snap_CA",
        "snap_TX",
        "snap_WI",
    }
    missing_calendar = sorted(calendar_columns - set(calendar.columns))
    price_columns = {"store_id", "item_id", "wm_yr_wk", "sell_price"}
    missing_prices = sorted(price_columns - set(prices.columns))
    if missing_history or missing_calendar or missing_prices:
        missing_groups = []
        if missing_history:
            missing_groups.append(f"sales: {', '.join(missing_history)}")
        if missing_calendar:
            missing_groups.append(f"calendar: {', '.join(missing_calendar)}")
        if missing_prices:
            missing_groups.append(f"prices: {', '.join(missing_prices)}")
        raise HTTPException(
            status_code=503,
            detail=(
                "Demand forecast inputs are incomplete: "
                + "; ".join(missing_groups)
                + "."
            ),
        )

    trained_features = {
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
        "item_id",
        "dept_id",
        "cat_id",
        "store_id",
    }
    unsupported_features = sorted(set(features) - trained_features)
    missing_features = sorted(trained_features - set(features))
    if len(features) != len(set(features)) or unsupported_features or missing_features:
        details = []
        if len(features) != len(set(features)):
            details.append("feature list contains duplicate columns")
        if missing_features:
            details.append(f"missing trained features: {', '.join(missing_features)}")
        if unsupported_features:
            details.append(f"unsupported features: {', '.join(unsupported_features)}")
        raise HTTPException(
            status_code=503,
            detail="Demand model feature contract is incompatible (" + "; ".join(details) + ").",
        )

    history = history.copy()
    calendar = calendar.copy()
    calendar["date"] = pd.to_datetime(calendar["date"], errors="coerce")
    if calendar.empty or calendar["date"].isna().any():
        raise HTTPException(
            status_code=503,
            detail="Demand calendar is empty or contains invalid dates.",
        )
    if calendar["date"].duplicated().any() or calendar["d"].duplicated().any():
        raise HTTPException(
            status_code=503,
            detail="Demand calendar contains duplicate dates or day identifiers.",
        )
    history = history.merge(
        calendar[["d", "date"]],
        on="d",
        how="left",
        validate="many_to_one",
    )
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["sales"] = pd.to_numeric(history["sales"], errors="coerce")
    if (
        history.empty
        or history["date"].isna().any()
        or history["sales"].isna().any()
        or not np.isfinite(history["sales"].to_numpy(dtype=float)).all()
        or history["sales"].lt(0).any()
    ):
        raise HTTPException(
            status_code=422,
            detail="Demand history contains empty, malformed, or negative daily sales.",
        )
    required_identifiers = [
        "id", "item_id", "dept_id", "cat_id", "store_id", "state_id",
    ]
    if history[required_identifiers].isna().any().any():
        raise HTTPException(
            status_code=422,
            detail="Demand history contains missing series identifiers.",
        )
    prices = filter_demand_prices(
        prices,
        history[["store_id", "item_id"]],
    )
    if prices.duplicated(["store_id", "item_id", "wm_yr_wk"]).any():
        raise HTTPException(
            status_code=503,
            detail="Sell-price data contains duplicate store/item/week records.",
        )

    history = history.sort_values(["id", "date"])
    date_counts = history.groupby("id")["date"].nunique()
    last_dates = history.groupby("id")["date"].max()
    if date_counts.empty or last_dates.nunique() != 1:
        raise HTTPException(
            status_code=503,
            detail="Selected demand series do not share a common final history date.",
        )
    last_date = pd.Timestamp(last_dates.iloc[0])
    unique_history_dates = pd.DatetimeIndex(history["date"].drop_duplicates().sort_values())
    if (
        len(unique_history_dates) < 28
        or (unique_history_dates.to_series().diff().dropna() != pd.Timedelta(days=1)).any()
    ):
        raise HTTPException(
            status_code=503,
            detail="Demand history must contain at least 28 consecutive daily observations.",
        )
    if (history.groupby("id")["date"].nunique() != len(unique_history_dates)).any():
        raise HTTPException(
            status_code=503,
            detail="Demand history contains missing daily observations for a selected series.",
        )

    future_calendar = calendar.loc[calendar["date"] > last_date].sort_values("date")
    if len(future_calendar) < horizon_days:
        raise HTTPException(
            status_code=503,
            detail=(
                "The calendar does not contain enough dates beyond the sales "
                f"history for a {horizon_days}-day forecast."
            ),
        )
    future_calendar = future_calendar.head(horizon_days).copy()
    if (
        future_calendar["date"].diff().dropna() != pd.Timedelta(days=1)
    ).any() or future_calendar["date"].iloc[0] != last_date + pd.Timedelta(days=1):
        raise HTTPException(
            status_code=503,
            detail="Future calendar dates are not consecutive daily observations.",
        )

    calendar_by_date = calendar.set_index("date", drop=False)
    if not history["state_id"].astype(str).isin(["CA", "TX", "WI"]).all():
        raise HTTPException(
            status_code=503,
            detail="Demand model history contains an unsupported SNAP state.",
        )
    prices = prices.copy()
    prices["sell_price"] = pd.to_numeric(prices["sell_price"], errors="coerce")
    price_lookup = {
        (str(row.store_id), str(row.item_id), str(row.wm_yr_wk)): float(row.sell_price)
        for row in prices.itertuples(index=False)
        if pd.notna(row.sell_price) and np.isfinite(float(row.sell_price))
    }
    grouped_history = {
        str(series_id): group.sort_values("date")
        for series_id, group in history.groupby("id", sort=False)
    }
    series_rows: list[dict[str, Any]] = []
    sales_by_series: dict[str, list[float]] = {}
    for series_id, group in grouped_history.items():
        row = group.iloc[-1]
        sales_by_series[series_id] = group["sales"].astype(float).tolist()
        series_rows.append(
            {
                "id": series_id,
                "item_id": row["item_id"],
                "dept_id": row["dept_id"],
                "cat_id": row["cat_id"],
                "store_id": row["store_id"],
                "state_id": row["state_id"],
            }
        )

    output: list[dict[str, Any]] = []
    for future in future_calendar.itertuples(index=False):
        forecast_date = pd.Timestamp(future.date)
        previous_date = forecast_date - pd.Timedelta(days=7)
        if previous_date not in calendar_by_date.index:
            raise HTTPException(
                status_code=503,
                detail="Calendar input is missing the prior-week day needed for promotion features.",
            )
        previous_calendar = calendar_by_date.loc[previous_date]
        prediction_rows: list[dict[str, Any]] = []
        prediction_series: list[dict[str, Any]] = []
        day_of_year = forecast_date.dayofyear
        for series in series_rows:
            state_column = f"snap_{series['state_id']}"
            current_price = price_lookup.get(
                (
                    str(series["store_id"]),
                    str(series["item_id"]),
                    str(future.wm_yr_wk),
                )
            )
            previous_price = price_lookup.get(
                (
                    str(series["store_id"]),
                    str(series["item_id"]),
                    str(previous_calendar["wm_yr_wk"]),
                )
            )
            if current_price is None or current_price <= 0:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Sell-price data is missing for at least one selected "
                        f"series on {forecast_date.date().isoformat()}."
                    ),
                )
            if state_column not in calendar.columns:
                raise HTTPException(
                    status_code=503,
                    detail=f"Calendar is missing required SNAP feature {state_column}.",
                )
            snap_value = pd.to_numeric(
                pd.Series([getattr(future, state_column)]),
                errors="coerce",
            ).iloc[0]
            if pd.isna(snap_value):
                raise HTTPException(
                    status_code=503,
                    detail=f"Calendar contains no SNAP value for {state_column}.",
                )
            sales_values = sales_by_series[str(series["id"])]
            discount_pct = (
                min(max(1.0 - current_price / previous_price, 0.0), 1.0)
                if previous_price is not None and previous_price > 0
                else 0.0
            )
            feature_row: dict[str, Any] = {
                "day_of_week": forecast_date.dayofweek,
                "month": forecast_date.month,
                "year": forecast_date.year,
                "day_of_year": day_of_year,
                "week_sin": np.sin(2 * np.pi * day_of_year / 365.25),
                "week_cos": np.cos(2 * np.pi * day_of_year / 365.25),
                "is_event": int(
                    pd.notna(future.event_name_1)
                    or pd.notna(future.event_name_2)
                ),
                "snap": int(snap_value),
                "sell_price": current_price,
                "discount_pct": discount_pct,
                "promotion": int(discount_pct > 0),
                "sales_lag_1": sales_values[-1],
                "sales_lag_7": sales_values[-7],
                "sales_lag_28": sales_values[-28],
                "sales_rolling_mean_7": float(np.mean(sales_values[-7:])),
                "sales_rolling_mean_28": float(np.mean(sales_values[-28:])),
                "item_id": series["item_id"],
                "dept_id": series["dept_id"],
                "cat_id": series["cat_id"],
                "store_id": series["store_id"],
            }
            prediction_rows.append(feature_row)
            prediction_series.append(series)

        try:
            predicted = np.asarray(
                model.predict(pd.DataFrame(prediction_rows, columns=features)),
                dtype=float,
            )
        except (ValueError, TypeError, AttributeError) as error:
            raise HTTPException(
                status_code=500,
                detail="Demand model prediction failed for the validated daily inputs.",
            ) from error
        if (
            predicted.ndim != 1
            or len(predicted) != len(prediction_series)
            or not np.isfinite(predicted).all()
        ):
            raise HTTPException(
                status_code=500,
                detail="Demand model returned malformed or non-finite predictions.",
            )

        for series, prediction in zip(prediction_series, predicted):
            predicted_units = max(float(prediction), 0.0)
            sales_by_series[str(series["id"])].append(predicted_units)
            output.append(
                {
                    "forecast_date": forecast_date.date().isoformat(),
                    "series_id": str(series["id"]),
                    "item_id": str(series["item_id"]),
                    "department_id": str(series["dept_id"]),
                    "category_id": str(series["cat_id"]),
                    "store_id": str(series["store_id"]),
                    "predicted_units": predicted_units,
                }
            )

    return {
        "data_source": "M5 evaluation benchmark CSV",
        "forecast_frequency": "daily",
        "historical_data_through": last_date.date().isoformat(),
        "forecast_start": future_calendar["date"].iloc[0].date().isoformat(),
        "forecast_end": future_calendar["date"].iloc[-1].date().isoformat(),
        "horizon_days": int(len(future_calendar)),
        "series_count": len(series_rows),
        "series_scope": (
            "Model-selected benchmark sample: one deterministic item series "
            "per store and department; not a forecast for the configured MySQL store."
        ),
        "predictions": output,
    }


def require_columns(
    frame: pd.DataFrame,
    columns: set[str],
    dataset_name: str,
) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"{dataset_name} is missing required columns: {missing}",
        )


def inventory_view() -> pd.DataFrame:
    inventory = read_csv(INVENTORY_PATH)
    products = read_csv(PRODUCTS_PATH, required=False)
    if not products.empty and {"product_id", "product_name"}.issubset(products.columns):
        inventory = inventory.merge(
            products[["product_id", "product_name"]].drop_duplicates("product_id"),
            on="product_id",
            how="left",
        )
    return inventory


@router.get("/products")
def list_products(
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    products = read_csv(PRODUCTS_PATH)
    require_columns(
        products,
        {"product_id", "product_name", "category"},
        "products",
    )
    if search:
        term = search.strip().casefold()
        searchable = products[["product_id", "product_name", "category"]]
        matches = searchable.fillna("").astype(str).apply(
            lambda column: column.str.casefold().str.contains(term, regex=False)
        )
        products = products.loc[matches.any(axis=1)]
    selected_columns = [
        column for column in (
            "product_id", "product_name", "category",
            "shelf_life_days", "selling_price", "unit_cost",
        ) if column in products.columns
    ]
    total = len(products)
    return {
        "data_source": "mysql" if database_configured() else "local_csv",
        "total": total,
        "limit": limit,
        "offset": offset,
        "products": records(products[selected_columns].iloc[offset : offset + limit]),
    }


@router.get("/inventory")
def list_inventory(
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    inventory = inventory_view()
    require_columns(
        inventory,
        {"batch_id", "product_id", "days_to_expiry", "quantity_remaining"},
        "inventory_batches",
    )
    if search:
        term = search.strip().casefold()
        searchable_columns = [
            column for column in ("batch_id", "product_id", "product_name", "category")
            if column in inventory.columns
        ]
        matches = inventory[searchable_columns].fillna("").astype(str).apply(
            lambda column: column.str.casefold().str.contains(term, regex=False)
        )
        inventory = inventory.loc[matches.any(axis=1)]
    days_to_expiry = pd.to_numeric(inventory["days_to_expiry"], errors="coerce")
    inventory["snapshot_expiry_status"] = "Expiry status unavailable"
    inventory.loc[
        days_to_expiry.lt(0), "snapshot_expiry_status"
    ] = "EXPIRED at recorded snapshot - do not sell or discount"
    inventory.loc[
        days_to_expiry.eq(0), "snapshot_expiry_status"
    ] = "Expires on recorded snapshot date - do not discount"
    inventory.loc[
        days_to_expiry.between(1, 3),
        "snapshot_expiry_status",
    ] = "Expiring within 1-3 days of recorded snapshot"
    inventory.loc[
        days_to_expiry.gt(3), "snapshot_expiry_status"
    ] = "Not expired at recorded snapshot"
    total = len(inventory)
    return {
        "data_source": "mysql" if database_configured() else "local_csv",
        "total": total,
        "limit": limit,
        "offset": offset,
        "inventory_batches": records(inventory.iloc[offset : offset + limit]),
        "inventory_data_notice": (
            "Inventory values are recorded snapshots, not verified live stock. "
            "Expired stock must not be sold or discounted."
        ),
    }


@router.get("/sales-history")
def sales_history(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    frame = read_csv(WASTE_PATH)
    require_columns(frame, {"date", "units_sold"}, "perishable_inventory")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["units_sold"] = pd.to_numeric(frame["units_sold"], errors="coerce")
    valid = frame.dropna(subset=["date"])
    daily = (
        valid.groupby(valid["date"].dt.strftime("%Y-%m-%d"))["units_sold"]
        .sum(min_count=1)
        .rename_axis("date")
        .reset_index()
        .sort_values("date")
    )
    return {
        "data_source": "mysql" if database_configured() else "local_csv",
        "total_days": int(len(daily)),
        "total_units_sold": (
            float(valid["units_sold"].sum(min_count=1))
            if valid["units_sold"].notna().any()
            else None
        ),
        "date_from": daily["date"].iloc[0] if not daily.empty else None,
        "date_through": daily["date"].iloc[-1] if not daily.empty else None,
        "limit": limit,
        "offset": offset,
        "sales_by_day": records(daily.iloc[offset : offset + limit]),
    }


@router.get("/waste-report")
def waste_report(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    frame = read_csv(WASTE_PATH)
    require_columns(
        frame,
        {"date", "category", "waste_units"},
        "perishable_inventory",
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["waste_units"] = pd.to_numeric(frame["waste_units"], errors="coerce")
    valid = frame.dropna(subset=["date"]).copy()
    valid["category"] = valid["category"].fillna("Uncategorized")
    category_breakdown = (
        valid.groupby("category", as_index=False)["waste_units"]
        .sum(min_count=1)
        .sort_values("category")
    )
    daily_waste = (
        valid.groupby(valid["date"].dt.strftime("%Y-%m-%d"))["waste_units"]
        .sum(min_count=1)
        .rename_axis("date")
        .reset_index()
        .sort_values("date")
    )
    return {
        "data_source": "mysql" if database_configured() else "local_csv",
        "recorded_waste_units": (
            float(valid["waste_units"].sum(min_count=1))
            if valid["waste_units"].notna().any()
            else None
        ),
        "record_count": int(len(valid)),
        "daily_count": int(len(daily_waste)),
        "date_from": daily_waste["date"].iloc[0] if not daily_waste.empty else None,
        "date_through": daily_waste["date"].iloc[-1] if not daily_waste.empty else None,
        "category_breakdown": records(category_breakdown),
        "daily_waste": records(daily_waste.iloc[offset : offset + limit]),
        "limit": limit,
        "offset": offset,
        "notice": "Aggregates are based on recorded perishable-inventory data.",
    }


@router.get("/dashboard")
def dashboard_summary() -> dict[str, Any]:
    inventory = inventory_view()
    waste = read_csv(WASTE_PATH)
    products = read_csv(PRODUCTS_PATH, required=False)
    require_columns(inventory, {"expiry_risk_label", "days_to_expiry"}, "inventory_batches")
    require_columns(waste, {"date", "waste_units"}, "perishable_inventory")
    waste["date"] = pd.to_datetime(waste["date"], errors="coerce")
    waste["waste_units"] = pd.to_numeric(waste["waste_units"], errors="coerce")
    latest = waste["date"].max()
    recent = waste[waste["date"] >= latest - pd.Timedelta(days=6)]
    recent = recent.dropna(subset=["date"]).copy()
    recent["waste_units"] = pd.to_numeric(recent["waste_units"], errors="coerce")
    risky = inventory[pd.to_numeric(inventory["expiry_risk_label"], errors="coerce").eq(1)]
    sort_cols = [c for c in ("days_to_expiry", "quantity_remaining") if c in risky]
    if sort_cols:
        risky = risky.sort_values(sort_cols)
    available_models = {
        name: (ARTIFACTS / f"{name}.joblib").exists() for name in MODEL_NAMES
    }
    product_count = (
        int(products["product_id"].nunique())
        if not products.empty and "product_id" in products
        else int(inventory["product_id"].nunique())
    )
    display_cols = [
        c for c in (
            "batch_id", "product_name", "product_id", "category",
            "days_to_expiry", "quantity_remaining", "expected_demand_before_expiry",
        ) if c in risky
    ]
    waste_by_category: list[dict[str, Any]] = []
    if "category" in recent:
        category_waste = recent.assign(
            category=recent["category"].fillna("Uncategorized")
        )
        waste_by_category = records(
            category_waste.groupby("category", as_index=False)["waste_units"]
            .sum()
            .sort_values("waste_units", ascending=False)
            .rename(columns={"waste_units": "waste_units"})
        )

    daily_sales: list[dict[str, Any]] = []
    if "units_sold" in recent:
        sales = recent.assign(
            units_sold=pd.to_numeric(recent["units_sold"], errors="coerce")
        )
        daily_sales = records(
            sales.groupby(sales["date"].dt.strftime("%Y-%m-%d"))["units_sold"]
            .sum(min_count=1)
            .rename_axis("date")
            .reset_index()
            .sort_values("date")
        )

    return {
        "data_source": "mysql" if database_configured() else "local_csv",
        "products_tracked": product_count,
        "inventory_batches": int(len(inventory)),
        "expiry_risk_batches": int(len(risky)),
        "recorded_waste_last_7_days": float(recent["waste_units"].sum()),
        "waste_data_through": latest.date().isoformat() if pd.notna(latest) else None,
        "waste_by_category_last_7_days": waste_by_category,
        "daily_sales_last_7_days": daily_sales,
        "models": available_models,
        "expiry_risk_queue": records(risky[display_cols].head(20)),
    }

def historical_drift_report(
    frame: pd.DataFrame,
    date_column: str,
    features: list[str],
) -> dict[str, Any]:
    """Compare earlier and later historical records; this is not live monitoring."""
    required = [date_column, *features]
    missing = [column for column in required if column not in frame.columns]

    if missing:
        return {
            "status": "unavailable",
            "reason": f"Missing required columns: {', '.join(missing)}",
            "comparison_type": "historical",
        }

    data = frame.copy()
    data[date_column] = pd.to_datetime(data[date_column], errors="coerce")
    data = data.dropna(subset=[date_column]).sort_values(date_column)

    unique_dates = data[date_column].drop_duplicates().sort_values()

    if len(unique_dates) < 2:
        return {
            "status": "unavailable",
            "reason": "At least two distinct dates are required.",
            "comparison_type": "historical",
        }

    split_index = max(1, len(unique_dates) // 2)
    cutoff = unique_dates.iloc[split_index]

    reference = data[data[date_column] < cutoff]
    current = data[data[date_column] >= cutoff]

    if len(reference) < 2 or len(current) < 2:
        return {
            "status": "unavailable",
            "reason": "Not enough records in both historical periods.",
            "comparison_type": "historical",
        }

    report = detect_data_drift(reference, current, features)

    return {
        "status": (
            "drift_detected"
            if report["features_with_drift"] > 0
            else "normal"
            if report["features_tested"] > 0
            else "unavailable"
        ),
        "comparison_type": "historical",
        "date_column": date_column,
        "reference_period": {
            "start": reference[date_column].min().date().isoformat(),
            "end": reference[date_column].max().date().isoformat(),
        },
        "current_period": {
            "start": current[date_column].min().date().isoformat(),
            "end": current[date_column].max().date().isoformat(),
        },
        "reference_rows": int(len(reference)),
        "current_rows": int(len(current)),
        **report,
    }




@router.get("/monitoring")
def monitoring_summary() -> dict[str, Any]:
    metrics_path = ARTIFACTS / "training_metrics.json"
    metrics: dict[str, Any] = {}
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=500,
                detail=f"Could not read training_metrics.json: {error}",
            ) from error

    coverage: list[dict[str, Any]] = []
    for name, path, date_column in (
        ("Inventory batches", INVENTORY_PATH, "snapshot_date"),
        ("Perishable inventory", WASTE_PATH, "date"),
        ("Product catalog", PRODUCTS_PATH, None),
    ):
        frame = read_csv(path, required=False)
        date_range = None
        if date_column and date_column in frame and not frame.empty:
            dates = pd.to_datetime(frame[date_column], errors="coerce").dropna()
            if not dates.empty:
                date_range = {
                    "start": dates.min().date().isoformat(),
                    "end": dates.max().date().isoformat(),
                }
        coverage.append(
            {"dataset": name, "rows": int(len(frame)), "date_range": date_range}
        )


    inventory = read_csv(INVENTORY_PATH, required=False)
    waste = read_csv(WASTE_PATH, required=False)

    drift_reports = {
        "expiry_risk": historical_drift_report(
            inventory,
            "snapshot_date",
            [
                "initial_quantity",
                "quantity_remaining",
                "days_to_expiry",
                "avg_daily_sales_7d",
                "expected_demand_before_expiry",
                "unit_price",
                "unit_cost",
                "discount_pct",
            ],
        ),
        "food_waste": historical_drift_report(
            waste,
            "date",
            [
                "opening_stock",
                "units_received",
                "units_sold",
                "unit_price",
                "discount_pct",
                "days_to_expiry",
                "temperature_c",
                "stockout_flag",
            ],
        ),
    }

    return {
        "models": {
            name: {
                "ready": (ARTIFACTS / f"{name}.joblib").exists(),
                "metadata": metrics.get(name, {}),
            }
            for name in MODEL_NAMES
        },
        "datasets": coverage,
        "drift": drift_reports,
    }


@router.get("/predictions/food-waste")
def predict_food_waste() -> dict[str, Any]:
    frame = read_csv(WASTE_PATH)
    require_columns(
        frame,
        {
            "product_id", "date", "category", "opening_stock", "units_received",
            "units_sold", "unit_price", "discount_pct", "days_to_expiry",
            "temperature_c", "stockout_flag",
        },
        "perishable_inventory",
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values(["product_id", "date"])
    latest = frame.groupby("product_id", as_index=False, sort=False).tail(1).copy()
    latest["ending_stock_estimate"] = (
        latest["opening_stock"] + latest["units_received"] - latest["units_sold"]
    )
    forecast_dates = latest["date"] + pd.Timedelta(days=1)
    latest["target_day_of_week"] = forecast_dates.dt.dayofweek
    latest["target_month"] = forecast_dates.dt.month
    features = get_features("food_waste")
    if {"waste_units", "target_waste_units"}.intersection(features):
        raise HTTPException(
            status_code=500,
            detail="Food-waste model metadata contains target leakage.",
        )
    require_columns(latest, set(features), "perishable_inventory prediction inputs")
    model = load_model("food_waste")
    try:
        predictions = model.predict(latest[features]).clip(min=0)
    except (ValueError, TypeError) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Food-waste prediction failed: {error}",
        ) from error
    latest["forecast_date"] = forecast_dates
    latest["predicted_waste_units"] = predictions
    products = read_csv(PRODUCTS_PATH, required=False)
    if not products.empty and {"product_id", "product_name"}.issubset(products.columns):
        latest = latest.merge(
            products[["product_id", "product_name"]].drop_duplicates("product_id"),
            on="product_id",
            how="left",
        )
    if "product_name" not in latest:
        latest["product_name"] = latest["product_id"].astype(str)
    else:
        latest["product_name"] = latest["product_name"].fillna(
            latest["product_id"].astype(str)
        )
    latest = latest.sort_values("predicted_waste_units", ascending=False)
    return {
        "forecast_date": forecast_dates.max().date().isoformat(),
        "total_predicted_waste_units": float(latest["predicted_waste_units"].sum()),
        "predictions": records(
            latest[
                [
                    "product_id",
                    "product_name",
                    "category",
                    "date",
                    "forecast_date",
                    "predicted_waste_units",
                ]
            ]
        ),
    }


@router.get("/predictions/demand-forecast")
def predict_demand_forecast(
    horizon_days: int = Query(default=7, ge=1, le=28),
) -> dict[str, Any]:
    """Predict daily demand for the trained M5 benchmark series."""
    features = get_features("demand_forecast")
    if {"sales", "target_sales"}.intersection(features):
        raise HTTPException(
            status_code=500,
            detail="Demand model metadata contains target leakage.",
        )
    history, calendar, prices = load_demand_forecast_inputs()
    return build_demand_forecast(
        history,
        calendar,
        prices,
        load_model("demand_forecast"),
        features,
        horizon_days,
    )


@router.get(
    "/predictions/expiry-risk",
    response_model=ExpiryRiskResponse,
    responses={
        422: {"description": "min_probability must be between 0 and 1."},
        503: {"description": "Inventory data or model is unavailable."},
    },
)
def predict_expiry_risk(
    min_probability: float = Query(default=0.5, ge=0.0, le=1.0),
) -> dict[str, Any]:
    inventory = inventory_view()
    require_columns(
        inventory,
        {
            "batch_id", "product_id", "category", "received_at", "snapshot_date",
            "initial_quantity", "quantity_remaining", "days_to_expiry",
            "avg_daily_sales_7d", "expected_demand_before_expiry",
            "unit_price", "unit_cost", "discount_pct",
        },
        "inventory_batches",
    )
    if inventory.empty:
        return {
            "min_probability": min_probability,
            "risk_category_thresholds": {
                "low": "probability < 0.40",
                "medium": "0.40 <= probability < 0.70",
                "high": "probability >= 0.70",
            },
            "data_notice": (
                "Probabilities are model outputs for recorded inventory snapshots, "
                "not live stock confirmation. Expiry status is relative to each "
                "snapshot date. Expired batches must not be sold or discounted."
            ),
            "batches_at_or_above_threshold": 0,
            "predictions": [],
        }
    try:
        inventory["received_at"] = pd.to_datetime(
            inventory["received_at"], errors="coerce", format="mixed"
        )
        inventory["snapshot_date"] = pd.to_datetime(
            inventory["snapshot_date"], errors="coerce", format="mixed"
        )
    except (ValueError, TypeError) as error:
        raise HTTPException(
            status_code=500,
            detail="Inventory received_at or snapshot_date contains an invalid date.",
        ) from error
    if inventory[["received_at", "snapshot_date"]].isna().any().any():
        raise HTTPException(
            status_code=500,
            detail="Inventory is missing received_at or snapshot_date values.",
        )

    numeric_features = [
        "initial_quantity",
        "quantity_remaining",
        "days_to_expiry",
        "avg_daily_sales_7d",
        "expected_demand_before_expiry",
        "unit_price",
        "unit_cost",
        "discount_pct",
    ]
    for column in numeric_features:
        inventory[column] = pd.to_numeric(inventory[column], errors="coerce")
    numeric_values = inventory[numeric_features].to_numpy(dtype=float)
    if not np.isfinite(numeric_values).all():
        logger.error("Inventory contains missing or non-finite expiry-risk inputs")
        raise HTTPException(
            status_code=500,
            detail="Inventory contains missing or invalid numeric expiry-risk inputs.",
        )
    if (
        inventory["quantity_remaining"].lt(0).any()
        or inventory["initial_quantity"].lt(0).any()
        or inventory["avg_daily_sales_7d"].lt(0).any()
        or inventory["expected_demand_before_expiry"].lt(0).any()
        or inventory["unit_price"].lt(0).any()
        or inventory["unit_cost"].lt(0).any()
        or inventory["discount_pct"].lt(0).any()
        or inventory["discount_pct"].gt(100).any()
    ):
        logger.error("Inventory contains out-of-range expiry-risk inputs")
        raise HTTPException(
            status_code=500,
            detail="Inventory contains out-of-range numeric expiry-risk inputs.",
        )
    if inventory[["batch_id", "product_id", "category"]].isna().any().any():
        logger.error("Inventory contains missing batch/product/category identifiers")
        raise HTTPException(
            status_code=500,
            detail="Inventory is missing a batch, product, or category identifier.",
        )
    if "expiry_date" in inventory.columns:
        expiry_dates = pd.to_datetime(
            inventory["expiry_date"], errors="coerce", format="mixed"
        )
        invalid_expiry = inventory["expiry_date"].notna() & expiry_dates.isna()
        if invalid_expiry.any():
            logger.error("Inventory contains invalid expiry_date values")
            raise HTTPException(
                status_code=500,
                detail="Inventory contains an invalid expiry_date.",
            )
        expected_days = (expiry_dates - inventory["snapshot_date"]).dt.days
        has_expiry = expiry_dates.notna()
        inconsistent = has_expiry & expected_days.ne(inventory["days_to_expiry"])
        if inconsistent.any():
            logger.error("Inventory days_to_expiry conflicts with stored dates")
            raise HTTPException(
                status_code=500,
                detail=(
                    "Inventory days_to_expiry does not match expiry_date "
                    "and snapshot_date."
                ),
            )
        inventory["expiry_date"] = expiry_dates

    inventory["days_since_received"] = (
        inventory["snapshot_date"] - inventory["received_at"]
    ).dt.days
    if inventory["days_since_received"].lt(0).any():
        logger.error("Inventory received_at is after snapshot_date")
        raise HTTPException(
            status_code=500,
            detail="Inventory received_at is after snapshot_date.",
        )
    inventory["snapshot_month"] = inventory["snapshot_date"].dt.month
    inventory["snapshot_day_of_week"] = inventory["snapshot_date"].dt.dayofweek
    features = get_features("expiry_risk")
    if {"expiry_risk_label", "waste_units_actual_simulated"}.intersection(features):
        raise HTTPException(
            status_code=500,
            detail="Expiry-risk model metadata contains target leakage.",
        )
    require_columns(inventory, set(features), "inventory_batches prediction inputs")
    model = load_model("expiry_risk")
    model_features = getattr(model, "feature_names_in_", None)
    if model_features is not None and list(model_features) != features:
        logger.error(
            "Expiry model feature order differs from metadata: model=%s metadata=%s",
            list(model_features),
            features,
        )
        raise HTTPException(
            status_code=503,
            detail="Expiry-risk model features do not match the saved metadata.",
        )
    model_input = inventory[features].copy()
    model_input.columns = [str(column) for column in model_input.columns]
    try:
        class_index = list(model.classes_).index(1)
        probabilities = np.asarray(
            model.predict_proba(model_input), dtype=float
        )
    except (ValueError, TypeError, AttributeError, IndexError) as error:
        logger.exception("Expiry-risk model prediction failed")
        raise HTTPException(
            status_code=500,
            detail="Expiry-risk prediction failed for the validated inventory inputs.",
        ) from error
    if (
        probabilities.ndim != 2
        or probabilities.shape[0] != len(inventory)
        or probabilities.shape[1] <= class_index
        or not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or (probabilities > 1).any()
        or not np.isclose(probabilities.sum(axis=1), 1.0).all()
    ):
        logger.error("Expiry-risk model returned malformed probability values")
        raise HTTPException(
            status_code=500,
            detail="Expiry-risk model returned invalid probability values.",
        )
    inventory["predicted_expiry_risk"] = probabilities[:, class_index]
    inventory["risk_category"] = pd.cut(
        inventory["predicted_expiry_risk"],
        bins=[-np.inf, 0.4, 0.7, np.inf],
        labels=["LOW", "MEDIUM", "HIGH"],
        right=False,
    ).astype(str)
    inventory["snapshot_expiry_status"] = "Not expired at recorded snapshot"
    inventory.loc[
        inventory["days_to_expiry"].lt(0), "snapshot_expiry_status"
    ] = "EXPIRED at recorded snapshot - do not sell or discount"
    inventory.loc[
        inventory["days_to_expiry"].eq(0), "snapshot_expiry_status"
    ] = "Expires on recorded snapshot date - do not discount"
    inventory.loc[
        inventory["days_to_expiry"].between(1, 3),
        "snapshot_expiry_status",
    ] = "Expiring within 1-3 days of recorded snapshot"
    inventory["quantity_at_risk"] = inventory["quantity_remaining"].clip(lower=0)
    risky = inventory[inventory["predicted_expiry_risk"] >= min_probability].copy()
    risky = risky.sort_values("predicted_expiry_risk", ascending=False)
    display_cols = [
        c for c in (
            "batch_id", "product_name", "product_id", "category", "snapshot_date",
            "expiry_date", "days_to_expiry", "quantity_remaining",
            "quantity_at_risk", "predicted_expiry_risk", "risk_category",
            "snapshot_expiry_status",
        ) if c in risky
    ]
    return {
        "min_probability": min_probability,
        "risk_category_thresholds": {
            "low": "probability < 0.40",
            "medium": "0.40 <= probability < 0.70",
            "high": "probability >= 0.70",
        },
        "data_notice": (
            "Probabilities are model outputs for recorded inventory snapshots, "
            "not live stock confirmation. Expiry status is relative to each "
            "snapshot date. Expired batches must not be sold or discounted."
        ),
        "batches_at_or_above_threshold": int(len(risky)),
        "predictions": records(risky[display_cols]),
    }



@router.get("/recommendations/discounts")
def discount_recommendations(
    limit: int = Query(default=25, ge=1, le=500),
) -> dict[str, Any]:
    """Return eligible simulated discount scenarios.

    Safety filters:
    - Exclude expired stock (days_to_expiry < 0).
    - Exclude stock expiring today (days_to_expiry == 0).
    - Exclude zero/negative stock and invalid discounts.

    This filters the recommendation response; a sales endpoint must also
    independently enforce the expired-stock sale block.
    """
    scenarios = read_csv(DISCOUNT_SCENARIOS_PATH, required=False)
    if not scenarios.empty:
        features = get_features("discount_recommendation")
        require_columns(scenarios, set(features), "discount scenario prediction inputs")
        model = load_model("discount_recommendation")
        try:
            predicted_margin = np.asarray(
                model.predict(scenarios[features]), dtype=float
            )
        except (ValueError, TypeError, AttributeError) as error:
            raise HTTPException(
                status_code=500,
                detail="Discount model prediction failed for the validated scenarios.",
            ) from error
        if (
            predicted_margin.ndim != 1
            or len(predicted_margin) != len(scenarios)
            or not np.isfinite(predicted_margin).all()
        ):
            raise HTTPException(
                status_code=500,
                detail="Discount model returned malformed or non-finite predictions.",
            )
        frame = scenarios.copy()
        frame["predicted_gross_margin"] = predicted_margin
    else:
        frame = read_csv(DISCOUNT_RECOMMENDATIONS_PATH, required=False)
        if frame.empty:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Discount scenario and saved recommendation data are missing "
                    "or empty. Check the configured CSV files."
                ),
            )

    required_columns = {
        "batch_id",
        "product_id",
        "days_to_expiry",
        "quantity_remaining",
        "discount_pct",
    }
    missing_columns = required_columns - set(frame.columns)

    if missing_columns:
        raise HTTPException(
            status_code=500,
            detail=(
                "Discount scenario data is missing required columns: "
                f"{sorted(missing_columns)}"
            ),
        )

    # Coerce safety-critical fields to numeric values; invalid values are
    # treated as ineligible by the filters below.
    for column in ("days_to_expiry", "quantity_remaining", "discount_pct"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    # Count stocked scenarios excluded because they are expired or expire today.
    expired_mask = (
        frame["days_to_expiry"].lt(0)
        & frame["quantity_remaining"].gt(0)
    )
    due_today_mask = (
        frame["days_to_expiry"].eq(0)
        & frame["quantity_remaining"].gt(0)
    )
    excluded_expired = int(expired_mask.sum())
    excluded_due_today = int(due_today_mask.sum())

    # Only stock with more than one day remaining is eligible for discount
    # scenarios. Stock expiring today or earlier is excluded.
    eligible_mask = (
        frame["days_to_expiry"].notna()
        & frame["days_to_expiry"].gt(0)
        & frame["quantity_remaining"].notna()
        & frame["quantity_remaining"].gt(0)
        & frame["discount_pct"].notna()
        & frame["discount_pct"].between(0, 100)
    )
    eligible = frame.loc[eligible_mask].copy()
    if "predicted_gross_margin" in eligible:
        eligible["predicted_gross_margin"] = pd.to_numeric(
            eligible["predicted_gross_margin"], errors="coerce"
        )
        eligible = eligible.loc[
            np.isfinite(eligible["predicted_gross_margin"].to_numpy(dtype=float))
        ].copy()
        if not eligible.empty:
            best_rows = eligible.groupby("batch_id")[
                "predicted_gross_margin"
            ].idxmax()
            eligible = eligible.loc[best_rows].copy()

    # Show eligible stock nearest to expiry first, then lower discounts first.
    eligible = eligible.sort_values(
        ["days_to_expiry", "discount_pct"],
        ascending=[True, True],
    )

    return {
        "data_status": (
            "Simulated prototype; not evidence of real customer price response. "
            "Expired stock and stock expiring today are excluded."
        ),
        "scenario_rows_loaded": int(len(frame)),
        "eligible_scenarios": int(len(eligible)),
        "excluded_expired_scenarios": excluded_expired,
        "excluded_expiring_today_scenarios": excluded_due_today,
        "recommendations": records(eligible.head(limit)),
    }
