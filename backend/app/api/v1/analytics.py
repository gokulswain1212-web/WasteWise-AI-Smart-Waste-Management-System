from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import database_configured, database_status, get_engine
from app.services.drift_detection import detect_data_drift


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[4]

RAW_DATA = ROOT / "ml" / "data" / "raw"
ARTIFACTS = ROOT / "artifacts"

PRODUCTS_PATH = RAW_DATA / "products.csv"
INVENTORY_PATH = RAW_DATA / "inventory_batches.csv"
WASTE_PATH = RAW_DATA / "perishable_inventory - perishable_inventory.csv"

DISCOUNT_RECOMMENDATIONS_PATH = (
    ARTIFACTS / "discount_recommendations.csv"
)

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
    DISCOUNT_RECOMMENDATIONS_PATH.name: "discount_recommendations",
}

router = APIRouter(prefix="/api/v1", tags=["analytics"])


# ============================================================
# 2. DATABASE STATUS
# ============================================================

@router.get("/database/status")
def database_connection_status() -> dict:
    """Return the current database connection and schema status."""
    return database_status()


# ============================================================
# 3. DATA ACCESS
# ============================================================

def read_csv(
    path: Path,
    required: bool = True,
) -> pd.DataFrame:
    """
    Read a configured dataset from MySQL when available.
    Otherwise, use the local CSV file.
    """

    table_name = DATASET_TABLES.get(path.name)

    if table_name and database_configured():
        try:
            return pd.read_sql_table(
                table_name,
                get_engine(),
            )
        except (
            SQLAlchemyError,
            OSError,
            ValueError,
            RuntimeError,
        ) as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Could not read MySQL table '{table_name}'. "
                    "Check the MySQL connection, table permissions, "
                    "and required schema."
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

    except (
        OSError,
        pd.errors.ParserError,
        UnicodeDecodeError,
    ) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read dataset {path.name}: {error}",
        ) from error


def records(
    frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-compatible records."""

    return json.loads(
        frame.to_json(
            orient="records",
            date_format="iso",
        )
    )


def require_columns(
    frame: pd.DataFrame,
    columns: set[str],
    dataset_name: str,
) -> None:
    """Validate that a dataset contains required columns."""

    missing = sorted(columns - set(frame.columns))

    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                f"{dataset_name} is missing required columns: "
                f"{missing}"
            ),
        )


def inventory_view() -> pd.DataFrame:
    """Return inventory enriched with product names when available."""

    inventory = read_csv(INVENTORY_PATH)
    products = read_csv(
        PRODUCTS_PATH,
        required=False,
    )

    if (
        not products.empty
        and {"product_id", "product_name"}.issubset(products.columns)
    ):
        inventory = inventory.merge(
            products[
                ["product_id", "product_name"]
            ].drop_duplicates("product_id"),
            on="product_id",
            how="left",
        )

    return inventory


# ============================================================
# 4. MODEL HELPERS
# ============================================================

def get_features(name: str) -> list[str]:
    """Load and validate the expected features for a model."""

    path = ARTIFACTS / f"{name}_metadata.json"

    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Metadata for {name} is missing. "
                "Train the models first."
            ),
        )

    try:
        metadata = json.loads(
            path.read_text(encoding="utf-8")
        )
        features = metadata["features"]

    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not read {name} model metadata: {error}"
            ),
        ) from error

    if not isinstance(features, list) or not all(
        isinstance(feature, str)
        for feature in features
    ):
        raise HTTPException(
            status_code=500,
            detail=f"Feature list in {name} metadata is invalid.",
        )

    return features


@lru_cache(maxsize=4)
def load_model(name: str):
    """Load a trained model artifact."""

    if name not in MODEL_NAMES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model: {name}",
        )

    path = ARTIFACTS / f"{name}.joblib"

    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Model artifact {path.name} is missing. "
                "Train the models first."
            ),
        )

    try:
        return joblib.load(path)

    except (
        OSError,
        ValueError,
        EOFError,
        ImportError,
    ) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load {name} model: {error}",
        ) from error


# ============================================================
# 5. DASHBOARD SUMMARY
# ============================================================

@router.get("/dashboard")
def dashboard_summary() -> dict[str, Any]:
    """
    Return dashboard metrics and inventory expiry classifications.

    Important:
    Expiry classifications use the stored inventory snapshot values.
    They do not establish the status of verified live stock.
    """

    inventory = inventory_view()
    waste = read_csv(WASTE_PATH)
    products = read_csv(
        PRODUCTS_PATH,
        required=False,
    )

    require_columns(
        inventory,
        {
            "product_id",
            "expiry_risk_label",
            "days_to_expiry",
            "quantity_remaining",
        },
        "inventory_batches",
    )

    require_columns(
        waste,
        {"date", "waste_units"},
        "perishable_inventory",
    )

    # --------------------------------------------------------
    # Historical waste and sales summary
    # --------------------------------------------------------

    waste["date"] = pd.to_datetime(
        waste["date"],
        errors="coerce",
    )

    waste["waste_units"] = pd.to_numeric(
        waste["waste_units"],
        errors="coerce",
    )

    latest = waste["date"].max()

    if pd.notna(latest):
        recent = waste[
            waste["date"] >= latest - pd.Timedelta(days=6)
        ].copy()

        recent = recent.dropna(
            subset=["date"]
        )

    else:
        recent = waste.iloc[0:0].copy()

    recent["waste_units"] = pd.to_numeric(
        recent["waste_units"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Expiry classifications at the recorded snapshot
    # --------------------------------------------------------

    inventory = inventory.copy()

    inventory["days_to_expiry"] = pd.to_numeric(
        inventory["days_to_expiry"],
        errors="coerce",
    )

    inventory["quantity_remaining"] = pd.to_numeric(
        inventory["quantity_remaining"],
        errors="coerce",
    )

    risk_label = pd.to_numeric(
        inventory["expiry_risk_label"],
        errors="coerce",
    ).eq(1)

    days = inventory["days_to_expiry"]
    quantity = inventory["quantity_remaining"]

    has_stock = quantity.gt(0)

    # These are statuses relative to each row's snapshot.
    expired_mask = days.lt(0) & has_stock
    due_today_mask = days.eq(0) & has_stock

    expiring_soon_mask = (
        days.between(1, 3)
        & has_stock
    )

    inventory["expiry_status"] = (
        "MONITOR AT RECORDED SNAPSHOT"
    )

    inventory.loc[
        expiring_soon_mask,
        "expiry_status",
    ] = "EXPIRING WITHIN 1-3 DAYS OF SNAPSHOT"

    inventory.loc[
        due_today_mask,
        "expiry_status",
    ] = (
        "EXPIRES ON SNAPSHOT DATE - DO NOT DISCOUNT"
    )

    inventory.loc[
        expired_mask,
        "expiry_status",
    ] = (
        "EXPIRED AT RECORDED SNAPSHOT - "
        "DO NOT SELL OR DISCOUNT"
    )

    # Include model-labelled risk and urgent expiry records.
    risky = inventory[
        risk_label
        | expired_mask
        | due_today_mask
        | expiring_soon_mask
    ].copy()

    # Most urgent snapshot-relative statuses appear first.
    risky = risky.sort_values(
        ["days_to_expiry", "quantity_remaining"],
        ascending=[True, False],
        na_position="last",
    )

    expired_stock_batches = int(
        expired_mask.sum()
    )

    stock_expiring_today_batches = int(
        due_today_mask.sum()
    )

    # Keep explicit aliases to make the reference period clear.
    expired_at_recorded_snapshot_batches = (
        expired_stock_batches
    )

    expiring_on_recorded_snapshot_date_batches = (
        stock_expiring_today_batches
    )

    # --------------------------------------------------------
    # Model artifact availability
    # --------------------------------------------------------

    available_models = {
        name: (
            ARTIFACTS / f"{name}.joblib"
        ).exists()
        for name in MODEL_NAMES
    }

    # --------------------------------------------------------
    # Product count
    # --------------------------------------------------------

    product_count = (
        int(products["product_id"].nunique())
        if (
            not products.empty
            and "product_id" in products.columns
        )
        else int(inventory["product_id"].nunique())
    )

    # --------------------------------------------------------
    # Expiry-risk queue
    # --------------------------------------------------------

    display_cols = [
        column
        for column in (
            "batch_id",
            "product_name",
            "product_id",
            "category",
            "snapshot_date",
            "expiry_date",
            "days_to_expiry",
            "quantity_remaining",
            "expected_demand_before_expiry",
            "expiry_status",
        )
        if column in risky.columns
    ]

    # --------------------------------------------------------
    # Waste by category
    # --------------------------------------------------------

    waste_by_category: list[dict[str, Any]] = []

    if "category" in recent.columns:
        category_waste = recent.assign(
            category=recent["category"].fillna(
                "Uncategorized"
            )
        )

        waste_by_category = records(
            category_waste.groupby(
                "category",
                as_index=False,
            )["waste_units"]
            .sum()
            .sort_values(
                "waste_units",
                ascending=False,
            )
        )

    # --------------------------------------------------------
    # Daily sales
    # --------------------------------------------------------

    daily_sales: list[dict[str, Any]] = []

    if "units_sold" in recent.columns:
        sales = recent.assign(
            units_sold=pd.to_numeric(
                recent["units_sold"],
                errors="coerce",
            )
        )

        daily_sales = records(
            sales.groupby(
                sales["date"].dt.strftime("%Y-%m-%d")
            )["units_sold"]
            .sum(min_count=1)
            .rename_axis("date")
            .reset_index()
            .sort_values("date")
        )

    # --------------------------------------------------------
    # Dashboard response
    # --------------------------------------------------------

    return {
        "data_source": (
            "mysql"
            if database_configured()
            else "local_csv"
        ),

        "products_tracked": product_count,

        "inventory_batches": int(
            len(inventory)
        ),

        "expiry_risk_batches": int(
            len(risky)
        ),

        # Backward-compatible field names.
        # These counts refer to the recorded snapshots.
        "expired_stock_batches": (
            expired_stock_batches
        ),

        "stock_expiring_today_batches": (
            stock_expiring_today_batches
        ),

        # Explicit field names for clarity.
        "expired_at_recorded_snapshot_batches": (
            expired_at_recorded_snapshot_batches
        ),

        "expiring_on_recorded_snapshot_date_batches": (
            expiring_on_recorded_snapshot_date_batches
        ),

        "inventory_data_notice": (
            "Inventory batches combine records from multiple snapshot "
            "dates, potentially including historical and future-dated "
            "snapshots. Expiry statuses are calculated from recorded "
            "snapshot values and are not verified live stock levels. "
            "Verify current physical stock and expiry dates before "
            "making operational decisions."
        ),

        "recorded_waste_last_7_days": float(
            recent["waste_units"].sum()
        ),

        "waste_data_through": (
            latest.date().isoformat()
            if pd.notna(latest)
            else None
        ),

        "waste_by_category_last_7_days": (
            waste_by_category
        ),

        "daily_sales_last_7_days": (
            daily_sales
        ),

        "models": available_models,

        "expiry_risk_queue": records(
            risky[display_cols].head(20)
        ),
    }


# ============================================================
# 6. HISTORICAL DRIFT REPORT
# ============================================================

def historical_drift_report(
    frame: pd.DataFrame,
    date_column: str,
    features: list[str],
) -> dict[str, Any]:
    """
    Compare earlier and later historical records.
    This is historical drift analysis, not live monitoring.
    """

    required = [
        date_column,
        *features,
    ]

    missing = [
        column
        for column in required
        if column not in frame.columns
    ]

    if missing:
        return {
            "status": "unavailable",
            "reason": (
                f"Missing required columns: "
                f"{', '.join(missing)}"
            ),
            "comparison_type": "historical",
        }

    data = frame.copy()

    data[date_column] = pd.to_datetime(
        data[date_column],
        errors="coerce",
    )

    data = data.dropna(
        subset=[date_column]
    ).sort_values(date_column)

    unique_dates = (
        data[date_column]
        .drop_duplicates()
        .sort_values()
    )

    if len(unique_dates) < 2:
        return {
            "status": "unavailable",
            "reason": (
                "At least two distinct dates are required."
            ),
            "comparison_type": "historical",
        }

    split_index = max(
        1,
        len(unique_dates) // 2,
    )

    cutoff = unique_dates.iloc[split_index]

    reference = data[
        data[date_column] < cutoff
    ]

    current = data[
        data[date_column] >= cutoff
    ]

    if len(reference) < 2 or len(current) < 2:
        return {
            "status": "unavailable",
            "reason": (
                "Not enough records in both historical periods."
            ),
            "comparison_type": "historical",
        }

    report = detect_data_drift(
        reference,
        current,
        features,
    )

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
            "start": (
                reference[date_column]
                .min()
                .date()
                .isoformat()
            ),
            "end": (
                reference[date_column]
                .max()
                .date()
                .isoformat()
            ),
        },

        "current_period": {
            "start": (
                current[date_column]
                .min()
                .date()
                .isoformat()
            ),
            "end": (
                current[date_column]
                .max()
                .date()
                .isoformat()
            ),
        },

        "reference_rows": int(
            len(reference)
        ),

        "current_rows": int(
            len(current)
        ),

        **report,
    }


# ============================================================
# 7. MONITORING SUMMARY
# ============================================================

@router.get("/monitoring")
def monitoring_summary() -> dict[str, Any]:
    metrics_path = ARTIFACTS / "training_metrics.json"

    metrics: dict[str, Any] = {}

    if metrics_path.exists():
        try:
            metrics = json.loads(
                metrics_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Could not read training_metrics.json: {error}"
                ),
            ) from error

    # --------------------------------------------------------
    # Dataset coverage
    # --------------------------------------------------------

    coverage: list[dict[str, Any]] = []

    for name, path, date_column in (
        (
            "Inventory batches",
            INVENTORY_PATH,
            "snapshot_date",
        ),
        (
            "Perishable inventory",
            WASTE_PATH,
            "date",
        ),
        (
            "Product catalog",
            PRODUCTS_PATH,
            None,
        ),
    ):
        frame = read_csv(
            path,
            required=False,
        )

        date_range = None

        if (
            date_column
            and date_column in frame.columns
            and not frame.empty
        ):
            dates = pd.to_datetime(
                frame[date_column],
                errors="coerce",
            ).dropna()

            if not dates.empty:
                date_range = {
                    "start": (
                        dates.min().date().isoformat()
                    ),
                    "end": (
                        dates.max().date().isoformat()
                    ),
                }

        coverage.append(
            {
                "dataset": name,
                "rows": int(len(frame)),
                "date_range": date_range,
            }
        )

    # --------------------------------------------------------
    # Historical data drift checks
    # --------------------------------------------------------

    inventory = read_csv(
        INVENTORY_PATH,
        required=False,
    )

    waste = read_csv(
        WASTE_PATH,
        required=False,
    )

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
                "ready": (
                    ARTIFACTS / f"{name}.joblib"
                ).exists(),
                "metadata": metrics.get(
                    name,
                    {},
                ),
            }
            for name in MODEL_NAMES
        },

        "datasets": coverage,

        "drift": drift_reports,
    }


# ============================================================
# 8. FOOD-WASTE PREDICTIONS
# ============================================================

@router.get("/predictions/food-waste")
def predict_food_waste() -> dict[str, Any]:
    frame = read_csv(WASTE_PATH)

    require_columns(
        frame,
        {
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
        },
        "perishable_inventory",
    )

    frame["date"] = pd.to_datetime(
        frame["date"],
        errors="raise",
    )

    frame = frame.sort_values(
        ["product_id", "date"]
    )

    latest = (
        frame.groupby(
            "product_id",
            as_index=False,
            sort=False,
        )
        .tail(1)
        .copy()
    )

    latest["ending_stock_estimate"] = (
        latest["opening_stock"]
        + latest["units_received"]
        - latest["units_sold"]
    )

    forecast_dates = (
        latest["date"] + pd.Timedelta(days=1)
    )

    latest["target_day_of_week"] = (
        forecast_dates.dt.dayofweek
    )

    latest["target_month"] = (
        forecast_dates.dt.month
    )

    features = get_features("food_waste")

    if {
        "waste_units",
        "target_waste_units",
    }.intersection(features):
        raise HTTPException(
            status_code=500,
            detail=(
                "Food-waste model metadata contains target leakage."
            ),
        )

    require_columns(
        latest,
        set(features),
        "perishable_inventory prediction inputs",
    )

    model = load_model("food_waste")

    try:
        predictions = model.predict(
            latest[features]
        ).clip(min=0)

    except (
        ValueError,
        TypeError,
    ) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Food-waste prediction failed: {error}",
        ) from error

    latest["forecast_date"] = forecast_dates

    latest["predicted_waste_units"] = predictions

    products = read_csv(
        PRODUCTS_PATH,
        required=False,
    )

    if (
        not products.empty
        and {
            "product_id",
            "product_name",
        }.issubset(products.columns)
    ):
        latest = latest.merge(
            products[
                ["product_id", "product_name"]
            ].drop_duplicates("product_id"),
            on="product_id",
            how="left",
        )

    if "product_name" not in latest.columns:
        latest["product_name"] = (
            latest["product_id"].astype(str)
        )

    else:
        latest["product_name"] = (
            latest["product_name"].fillna(
                latest["product_id"].astype(str)
            )
        )

    latest = latest.sort_values(
        "predicted_waste_units",
        ascending=False,
    )

    return {
        "forecast_date": (
            forecast_dates.max().date().isoformat()
        ),

        "total_predicted_waste_units": float(
            latest["predicted_waste_units"].sum()
        ),

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


# ============================================================
# 9. EXPIRY-RISK PREDICTIONS
# ============================================================

@router.get("/predictions/expiry-risk")
def predict_expiry_risk(
    min_probability: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
    ),
) -> dict[str, Any]:

    inventory = inventory_view()

    require_columns(
        inventory,
        {
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
        },
        "inventory_batches",
    )

    inventory["received_at"] = pd.to_datetime(
        inventory["received_at"],
        errors="raise",
    )

    inventory["snapshot_date"] = pd.to_datetime(
        inventory["snapshot_date"],
        errors="raise",
    )

    inventory["days_since_received"] = (
        inventory["snapshot_date"]
        - inventory["received_at"]
    ).dt.days

    inventory["snapshot_month"] = (
        inventory["snapshot_date"].dt.month
    )

    inventory["snapshot_day_of_week"] = (
        inventory["snapshot_date"].dt.dayofweek
    )

    features = get_features("expiry_risk")

    if {
        "expiry_risk_label",
        "waste_units_actual_simulated",
    }.intersection(features):
        raise HTTPException(
            status_code=500,
            detail=(
                "Expiry-risk model metadata contains target leakage."
            ),
        )

    require_columns(
        inventory,
        set(features),
        "inventory_batches prediction inputs",
    )

    model = load_model("expiry_risk")

    try:
        class_index = list(
            model.classes_
        ).index(1)

        inventory["predicted_expiry_risk"] = (
            model.predict_proba(
                inventory[features]
            )[:, class_index]
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
    ) as error:
        raise HTTPException(
            status_code=500,
            detail=f"Expiry-risk prediction failed: {error}",
        ) from error

    risky = inventory[
        inventory["predicted_expiry_risk"]
        >= min_probability
    ].copy()

    risky = risky.sort_values(
        "predicted_expiry_risk",
        ascending=False,
    )

    display_cols = [
        column
        for column in (
            "batch_id",
            "product_name",
            "product_id",
            "category",
            "snapshot_date",
            "expiry_date",
            "days_to_expiry",
            "quantity_remaining",
            "predicted_expiry_risk",
        )
        if column in risky.columns
    ]

    return {
        "min_probability": min_probability,

        "batches_at_or_above_threshold": int(
            len(risky)
        ),

        "predictions": records(
            risky[display_cols]
        ),
    }


# ============================================================
# 10. DISCOUNT RECOMMENDATIONS
# ============================================================

@router.get("/recommendations/discounts")
def discount_recommendations(
    limit: int = Query(
        default=25,
        ge=1,
        le=500,
    ),
) -> dict[str, Any]:
    """
    Return eligible simulated discount scenarios.

    Safety filters:
    - Exclude expired stock based on the recorded scenario.
    - Exclude stock expiring on the recorded scenario date.
    - Exclude zero or negative remaining quantity.
    - Exclude invalid discount percentages.

    The recorded scenario is not proof of current physical stock.
    The sales API must independently prevent expired-stock sales.
    """

    frame = read_csv(
        DISCOUNT_RECOMMENDATIONS_PATH,
        required=False,
    )

    if frame.empty:
        raise HTTPException(
            status_code=503,
            detail=(
                "Discount scenario data is missing or empty. "
                "Check the configured scenario CSV."
            ),
        )

    required_columns = {
        "batch_id",
        "product_id",
        "days_to_expiry",
        "quantity_remaining",
        "discount_pct",
    }

    missing_columns = (
        required_columns - set(frame.columns)
    )

    if missing_columns:
        raise HTTPException(
            status_code=500,
            detail=(
                "Discount scenario data is missing required columns: "
                f"{sorted(missing_columns)}"
            ),
        )

    # Convert safety-related values to numeric.
    for column in (
        "days_to_expiry",
        "quantity_remaining",
        "discount_pct",
    ):
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    # Stocked scenarios that are already expired relative
    # to their recorded scenario data.
    expired_mask = (
        frame["days_to_expiry"].lt(0)
        & frame["quantity_remaining"].gt(0)
    )

    # Stocked scenarios expiring on the recorded scenario date.
    due_today_mask = (
        frame["days_to_expiry"].eq(0)
        & frame["quantity_remaining"].gt(0)
    )

    excluded_expired = int(
        expired_mask.sum()
    )

    excluded_due_today = int(
        due_today_mask.sum()
    )

    # Only scenarios with positive recorded days remaining,
    # positive stock, and valid discount percentages are eligible.
    eligible_mask = (
        frame["days_to_expiry"].notna()
        & frame["days_to_expiry"].gt(0)
        & frame["quantity_remaining"].notna()
        & frame["quantity_remaining"].gt(0)
        & frame["discount_pct"].notna()
        & frame["discount_pct"].between(0, 100)
    )

    eligible = frame.loc[
        eligible_mask
    ].copy()

    # Prioritize scenarios closest to expiry.
    eligible = eligible.sort_values(
        ["days_to_expiry", "discount_pct"],
        ascending=[True, True],
    )

    return {
        "data_status": (
            "Simulated prototype; not evidence of real customer "
            "price response. Expired stock and stock expiring "
            "on the recorded scenario date are excluded. "
            "Verify current stock and expiry before acting."
        ),

        "scenario_rows_loaded": int(
            len(frame)
        ),

        "eligible_scenarios": int(
            len(eligible)
        ),

        "excluded_expired_scenarios": (
            excluded_expired
        ),

        "excluded_expiring_today_scenarios": (
            excluded_due_today
        ),

        "recommendations": records(
            eligible.head(limit)
        ),
    }