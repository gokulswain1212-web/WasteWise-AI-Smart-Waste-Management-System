from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = ROOT / "ml" / "data" / "raw"
ARTIFACT_DIR = ROOT / "artifacts"
SALES_PATH = RAW_DATA / "sales_train_evaluation.csv"
INVENTORY_PATH = RAW_DATA / "inventory_batches.csv"
WASTE_PATH = RAW_DATA / "perishable_inventory - perishable_inventory.csv"
DISCOUNT_PATH = RAW_DATA / "discount_scenarios_simulated (1).csv"
PRODUCTS_PATH = RAW_DATA / "products.csv"
API_BASE_URL = os.getenv("WASTEWISE_API_URL", "http://127.0.0.1:8000").rstrip("/")
PRODUCT_COLUMNS = ["product_id", "product_name", "category"]
GUIDE = [
    ("Demand Forecast", "📈", "Plan replenishment using sales history and calendar signals."),
    ("Expiry Risk", "⏳", "Prioritize batches with limited time remaining before expiry."),
    ("Food Waste", "🥬", "Estimate next-day waste using the previous day's stock and sales."),
    ("Discount Plan", "🏷️", "Compare candidate discounts using simulated scenario outcomes."),
]
ANALYTICAL_MODELS = [
    "demand_forecast",
    "expiry_risk",
    "food_waste",
    "discount_recommendation",
]

st.set_page_config(
    page_title="WasteWise AI",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        color-scheme: dark;
        --ww-bg: #07111b;
        --ww-panel: #101e2b;
        --ww-panel-raised: #142536;
        --ww-line: #233749;
        --ww-text: #edf5f7;
        --ww-muted: #91a5b6;
        --ww-green: #51d28c;
        --ww-green-dark: #123d31;
    }
    .stApp {
        background:
            radial-gradient(ellipse at 78% 0%, rgba(18, 79, 57, .20), transparent 36%),
            var(--ww-bg);
        color: var(--ww-text);
    }
    .block-container {
        max-width: 1540px;
        padding: 1.15rem 1.5rem 2.2rem;
    }
    [data-testid="stSidebar"] {
        background: #091520;
        border-right: 1px solid #1c2c3b;
        width: 242px !important;
        min-width: 242px !important;
        max-width: 242px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.4rem;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        border-radius: 10px;
        padding: .5rem .65rem;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: #122a29;
    }
    h1, h2, h3, p, label {
        color: var(--ww-text);
    }
    h1 {
        letter-spacing: -.035em;
    }
    [data-testid="stMarkdownContainer"] p {
        color: var(--ww-muted);
    }
    [data-testid="stTextInput"] input {
        background: #122232;
        border: 1px solid #263b4e;
        border-radius: 10px;
        color: var(--ww-text);
    }
    [data-testid="stFileUploader"] section {
        background: #0d1c28;
        border: 1px dashed #376b69;
        border-radius: 12px;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: var(--ww-green);
    }
    [data-testid="stButton"] button {
        background: linear-gradient(120deg, #167650, #249263);
        color: white;
        border: 1px solid #329b70;
        border-radius: 9px;
        font-weight: 650;
        min-height: 2.65rem;
    }
    [data-testid="stButton"] button:hover {
        background: #25875e;
        border-color: #54d595;
        color: white;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #142433, #101d29);
        border: 1px solid var(--ww-line);
        border-radius: 13px;
        padding: .9rem 1rem;
        min-height: 112px;
    }
    [data-testid="stMetricLabel"] {
        color: #a9bac8;
    }
    [data-testid="stMetricValue"] {
        color: var(--ww-text);
    }
    .ww-stat-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: .65rem;
        margin: 0 0 1rem;
    }
    .ww-stat-card {
        min-width: 0;
        min-height: 100px;
        padding: .8rem .85rem;
        border: 1px solid var(--ww-line);
        border-radius: 13px;
        background: linear-gradient(145deg, #142433, #101d29);
    }
    .ww-stat-label {
        display: flex;
        align-items: center;
        gap: .4rem;
        color: #a9bac8;
        font-size: .72rem;
        line-height: 1.25;
    }
    .ww-stat-value {
        display: block;
        margin-top: .55rem;
        color: var(--ww-text);
        font-size: 1.35rem;
        font-weight: 700;
        line-height: 1;
    }
    .ww-stat-caption {
        display: block;
        margin-top: .42rem;
        color: var(--ww-muted);
        font-size: .65rem;
        line-height: 1.25;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--ww-line);
        border-radius: 14px;
        background: linear-gradient(155deg, #122231, #0e1a26);
    }
    .ww-brand {
        display: flex;
        align-items: center;
        gap: .75rem;
        padding: .3rem .25rem 1.2rem;
    }
    .ww-brand-mark {
        display: grid;
        place-items: center;
        width: 43px;
        height: 43px;
        border: 1px solid #287650;
        border-radius: 14px;
        background: linear-gradient(145deg, #1c6d48, #12382e);
        font-size: 1.45rem;
    }
    .ww-brand-name {
        color: #f4f7f8;
        font-size: 1.05rem;
        font-weight: 750;
        line-height: 1.15;
    }
    .ww-brand-name span, .ww-green {
        color: var(--ww-green);
    }
    .ww-brand-caption {
        color: var(--ww-muted);
        font-size: .72rem;
        margin-top: .18rem;
    }
    .ww-sidebar-note {
        margin-top: 2.3rem;
        padding: 1rem .85rem;
        border: 1px solid #1c3a32;
        border-radius: 12px;
        background: linear-gradient(140deg, #10251f, #0d1b24);
        color: #b9d0c3;
        font-size: .8rem;
        line-height: 1.5;
    }
    .ww-topline {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        min-height: 2.1rem;
        color: #b6c5cf;
        font-size: .84rem;
    }
    .ww-user-dot {
        display: inline-grid;
        place-items: center;
        width: 32px;
        height: 32px;
        margin-right: .55rem;
        border-radius: 50%;
        background: #253747;
        color: #d9e8ef;
        font-weight: 700;
    }
    .ww-hero {
        display: flex;
        justify-content: space-between;
        align-items: center;
        overflow: hidden;
        min-height: 170px;
        margin: .6rem 0 1rem;
        padding: 1.4rem 1.7rem;
        border: 1px solid #1b4939;
        border-radius: 16px;
        background:
            radial-gradient(ellipse at 83% 55%, rgba(54, 142, 80, .42), transparent 27%),
            linear-gradient(105deg, #102a25 0%, #0e211f 53%, #112c22 100%);
    }
    .ww-hero-copy {
        position: relative;
        z-index: 1;
        max-width: 720px;
    }
    .ww-eyebrow {
        color: #91d7ae;
        font-size: .73rem;
        font-weight: 750;
        letter-spacing: .13em;
        text-transform: uppercase;
    }
    .ww-hero h1 {
        margin: .35rem 0 .3rem;
        color: #f2f7f5;
        font-size: clamp(1.7rem, 3vw, 2.5rem);
    }
    .ww-hero p {
        margin: 0;
        color: #c2d3ce;
        font-size: .94rem;
    }
    .ww-hero-tags {
        display: flex;
        flex-wrap: wrap;
        gap: .5rem;
        margin-top: 1rem;
    }
    .ww-hero-tags span {
        padding: .35rem .6rem;
        border: 1px solid #31584a;
        border-radius: 999px;
        background: rgba(6, 22, 19, .35);
        color: #d5e9de;
        font-size: .74rem;
    }
    .ww-hero-art {
        padding: 0 2rem;
        font-size: 5.2rem;
        filter: drop-shadow(0 10px 18px rgba(91, 202, 116, .18));
    }
    .ww-data-note {
        margin: .65rem 0;
        padding: .7rem .85rem;
        border: 1px solid #34485a;
        border-radius: 10px;
        background: #122231;
        color: #bbcad4;
        font-size: .78rem;
        line-height: 1.45;
    }
    .ww-risk {
        color: #ffb46b;
        font-weight: 700;
    }
    .ww-panel {
        height: 100%;
        padding: 1.05rem 1.1rem;
        border: 1px solid var(--ww-line);
        border-radius: 14px;
        background: linear-gradient(155deg, #122231, #0e1a26);
    }
    .ww-panel-heading {
        display: flex;
        align-items: center;
        gap: .65rem;
        margin-bottom: .2rem;
    }
    .ww-panel-icon {
        display: inline-grid;
        flex: 0 0 38px;
        place-items: center;
        width: 38px;
        height: 38px;
        border-radius: 12px;
        background: linear-gradient(145deg, #176b4b, #12382f);
        font-size: 1.15rem;
    }
    .ww-panel-heading h3 {
        margin: 0;
        font-size: 1.02rem;
    }
    .ww-panel-subtitle {
        margin: .25rem 0 .85rem 3rem;
        color: var(--ww-muted);
        font-size: .76rem;
    }
    .ww-guide-row {
        display: flex;
        align-items: center;
        gap: .7rem;
        margin-top: .5rem;
        padding: .65rem .7rem;
        border: 1px solid #263a4b;
        border-radius: 11px;
        background: #122130;
    }
    .ww-guide-icon {
        display: grid;
        flex: 0 0 36px;
        place-items: center;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #173b34;
        font-size: 1rem;
    }
    .ww-guide-copy strong {
        display: block;
        color: #eaf2f5;
        font-size: .81rem;
    }
    .ww-guide-copy span {
        display: block;
        margin-top: .13rem;
        color: #9db0bf;
        font-size: .72rem;
        line-height: 1.35;
    }
    .ww-tip {
        margin-top: .85rem;
        padding: .8rem .9rem;
        border: 1px solid #23523c;
        border-radius: 11px;
        background: linear-gradient(110deg, #103428, #112720);
        color: #c9e4d0;
        font-size: .78rem;
        line-height: 1.45;
    }
    .ww-tip strong {
        color: #8ee1a5;
    }
    .ww-empty {
        padding: 1rem;
        border: 1px dashed #304557;
        border-radius: 11px;
        color: #9db0bf;
        font-size: .82rem;
        text-align: center;
    }
    .ww-footer {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin-top: 1.1rem;
        color: #788b9b;
        font-size: .7rem;
    }
    @media (max-width: 900px) {
        .ww-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 760px) {
        .block-container { padding: .8rem .8rem 1.5rem; }
        .ww-hero { padding: 1.1rem; }
        .ww-hero-art { padding: 0 .2rem; font-size: 3rem; }
        .ww-footer { flex-direction: column; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_retail_data() -> dict[str, pd.DataFrame]:
    files = {
        "products": PRODUCTS_PATH,
        "inventory": INVENTORY_PATH,
        "waste": WASTE_PATH,
        "discount_scenarios": DISCOUNT_PATH,
    }
    return {
        name: pd.read_csv(path) if path.exists() else pd.DataFrame()
        for name, path in files.items()
    }


def load_training_metrics() -> dict[str, dict]:
    metrics_path = ARTIFACT_DIR / "training_metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        st.error(f"Could not read training metrics: {error}")
        return {}
    if not isinstance(metrics, dict):
        st.error("Training metrics file must contain a JSON object.")
        return {}
    return metrics


def api_get(path: str, params: dict | None = None) -> dict:
    headers = {}
    api_key = os.getenv("WASTEWISE_API_KEY")
    if api_key:
        headers["X-API-KEY"] = api_key
    response = requests.get(
        f"{API_BASE_URL}{path}",
        params=params,
        headers=headers,
        timeout=60,
    )
    if response.status_code == 401:
        raise ValueError(
            "Authentication failed: the backend rejected the API key. "
            "Set `WASTEWISE_API_KEY` to match the backend's `API_KEY`."
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Backend returned an invalid response from {path}.")
    return payload


@st.cache_data(ttl=10)
def get_backend_health() -> tuple[bool, str, str]:
    try:
        result = api_get("/health")
    except requests.RequestException as error:
        return False, str(error), "unknown"
    except ValueError as error:
        return False, str(error), "unknown"
    if result.get("status") != "ok":
        return False, "Backend health check did not report status=ok.", "unknown"
    database = result.get("database", {})
    database_state = (
        "connected" if database.get("connected")
        else "not configured" if not database.get("configured")
        else "disconnected"
    )
    return True, str(result.get("service", "WasteWise API")), database_state


def get_model_status() -> tuple[int, int]:
    ready = sum(
        (ARTIFACT_DIR / f"{name}.joblib").exists()
        for name in ANALYTICAL_MODELS
    )
    return ready, len(ANALYTICAL_MODELS)


def render_brand() -> None:
    st.markdown(
        """
        <div class="ww-brand">
            <div class="ww-brand-mark">🛒</div>
            <div>
                <div class="ww-brand-name">WasteWise <span>AI</span></div>
                <div class="ww-brand-caption">Grocery Food Waste Intelligence</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_inventory_view(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    inventory = data["inventory"].copy()
    if inventory.empty:
        return inventory
    products = data["products"]
    if not products.empty and {"product_id", "product_name"}.issubset(products.columns):
        inventory = inventory.merge(
            products[["product_id", "product_name"]].drop_duplicates("product_id"),
            on="product_id",
            how="left",
        )
    if "snapshot_date" in inventory:
        inventory["snapshot_date"] = pd.to_datetime(
            inventory["snapshot_date"], errors="coerce"
        )
    for column in ("days_to_expiry", "quantity_remaining", "expiry_risk_label"):
        if column in inventory:
            inventory[column] = pd.to_numeric(inventory[column], errors="coerce")
    return inventory


def get_recent_waste(data: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, float, str]:
    waste = data["waste"].copy()
    if waste.empty or not {"date", "waste_units"}.issubset(waste.columns):
        return pd.DataFrame(), 0.0, "No food-waste records available."
    waste["date"] = pd.to_datetime(waste["date"], errors="coerce")
    waste["waste_units"] = pd.to_numeric(waste["waste_units"], errors="coerce")
    latest = waste["date"].max()
    if pd.isna(latest):
        return waste, 0.0, "Waste dataset has no valid dates."
    recent = waste[waste["date"] >= latest - pd.Timedelta(days=6)].copy()
    return recent, float(recent["waste_units"].sum()), latest.date().isoformat()


def render_pipeline_summary(metrics: dict[str, dict], name: str) -> None:
    model_path = ARTIFACT_DIR / f"{name}.joblib"
    if model_path.exists():
        st.success("Model artifact is available.")
    else:
        st.warning("Model not trained yet. Run `python ml/src/train_all_models.py`.")
    if name in metrics:
        st.json(metrics[name])


def render_expiry_table(inventory: pd.DataFrame, search: str = "") -> None:
    if inventory.empty:
        st.info("Add inventory batch data to `ml/data/raw/inventory_batches.csv`.")
        return
    if "expiry_risk_label" not in inventory:
        st.warning("The inventory data does not include expiry-risk labels.")
        return
    risky = inventory[inventory["expiry_risk_label"].eq(1)].copy()
    if search:
        text = search.casefold()
        product_column = risky.get("product_name", pd.Series("", index=risky.index))
        category_column = risky.get("category", pd.Series("", index=risky.index))
        matches = product_column.astype(str).str.casefold().str.contains(text)
        matches |= category_column.astype(str).str.casefold().str.contains(text)
        risky = risky[matches]
    sort_columns = [
        column for column in ("days_to_expiry", "quantity_remaining")
        if column in risky.columns
    ]
    if sort_columns:
        risky = risky.sort_values(sort_columns, ascending=True)
    display_columns = [
        column for column in (
            "product_name", "product_id", "category", "days_to_expiry",
            "quantity_remaining", "expected_demand_before_expiry", "discount_pct",
        ) if column in risky.columns
    ]
    if risky.empty:
        st.info("No matching expiry-risk batches found.")
    else:
        st.dataframe(risky[display_columns].head(12), width="stretch", hide_index=True)


def render_waste_chart(data: dict[str, pd.DataFrame]) -> None:
    recent, total, latest = get_recent_waste(data)
    if recent.empty:
        st.info("Food-waste history is unavailable.")
        return
    st.caption(f"Recorded waste for the latest 7 days in the dataset (through {latest}).")
    if "category" in recent.columns:
        chart = recent.groupby("category")["waste_units"].sum().sort_values(ascending=False)
    else:
        chart = recent.groupby("date")["waste_units"].sum()
    st.bar_chart(chart)
    st.metric("Recorded waste, latest 7 days", f"{total:,.0f} units")


def render_monitoring(data: dict[str, pd.DataFrame], metrics: dict[str, dict]) -> None:
    st.title("Monitoring")
    st.caption(
        "Dataset coverage, trained model availability, and holdout performance. "
        "Dataset dates are historical file dates, not live store telemetry."
    )
    try:
        backend_status = api_get("/api/v1/monitoring")
    except (requests.RequestException, ValueError) as error:
        st.error(f"Backend monitoring endpoint is unavailable: {error}")
        backend_status = None
    if backend_status is not None:
        st.success("Monitoring data loaded from the WasteWise backend API.")
        api_models = backend_status.get("models", {})
        if isinstance(api_models, dict):
            st.subheader("Backend model status")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Model": name.replace("_", " ").title(),
                            "Status": "Ready" if model.get("ready") else "Not trained",
                            "Holdout metrics": json.dumps(
                                model.get("metadata", {}), ensure_ascii=True
                            ),
                        }
                        for name, model in api_models.items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        api_datasets = backend_status.get("datasets", [])
        if isinstance(api_datasets, list) and api_datasets:
            st.subheader("Backend data coverage")
            st.dataframe(pd.DataFrame(api_datasets), width="stretch", hide_index=True)

    models = pd.DataFrame(
        [
            {
                "Model": name.replace("_", " ").title(),
                "Status": "Ready" if (ARTIFACT_DIR / f"{name}.joblib").exists() else "Not trained",
                "Artifact size (MB)": round(
                    (ARTIFACT_DIR / f"{name}.joblib").stat().st_size / (1024 * 1024), 1
                )
                if (ARTIFACT_DIR / f"{name}.joblib").exists()
                else None,
            }
            for name in ANALYTICAL_MODELS
        ]
    )
    st.subheader("Model status")
    st.dataframe(models, width="stretch", hide_index=True)

    st.subheader("Data coverage")
    coverage = []
    for name, frame, date_column in [
        ("Inventory batches", data["inventory"], "snapshot_date"),
        ("Perishable inventory", data["waste"], "date"),
        ("Product catalog", data["products"], None),
        ("Discount scenarios", data["discount_scenarios"], None),
    ]:
        date_range = "—"
        if date_column and date_column in frame.columns and not frame.empty:
            parsed = pd.to_datetime(frame[date_column], errors="coerce").dropna()
            if not parsed.empty:
                date_range = f"{parsed.min().date()} to {parsed.max().date()}"
        coverage.append(
            {
                "Dataset": name,
                "Rows": len(frame),
                "Date coverage": date_range,
            }
        )
    st.dataframe(pd.DataFrame(coverage), width="stretch", hide_index=True)

    st.subheader("Holdout performance")
    if not metrics:
        st.info("No saved training metrics found. Train models to monitor performance.")
    else:
        rows = []
        for name, values in metrics.items():
            rows.append(
                {
                    "Model": name.replace("_", " ").title(),
                    "MAE": values.get("mae"),
                    "WAPE": (
                        f"{values['wape']:.1%}" if "wape" in values else None
                    ),
                    "Accuracy": (
                        f"{values['accuracy']:.1%}" if "accuracy" in values else None
                    ),
                    "ROC-AUC": values.get("roc_auc"),
                    "Holdout": values.get("holdout_start", "Grouped holdout"),
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    waste = data["waste"]
    if not waste.empty and {"date", "waste_units"}.issubset(waste.columns):
        st.subheader("Recorded food waste trend")
        history = waste.copy()
        history["date"] = pd.to_datetime(history["date"], errors="coerce")
        history["waste_units"] = pd.to_numeric(history["waste_units"], errors="coerce")
        history = history.dropna(subset=["date", "waste_units"])
        daily = history.groupby("date")["waste_units"].sum().tail(45)
        st.line_chart(daily)


def render_predictions(data: dict[str, pd.DataFrame]) -> None:
    st.title("Predictions")
    st.caption(
        "Run the saved models against the latest available inventory records "
        "and inspect their forecast graphs."
    )
    prediction_type = st.selectbox(
        "Prediction type",
        ["Next-day food waste", "Inventory expiry risk"],
        key="prediction_type",
    )
    model_name = "food_waste" if prediction_type == "Next-day food waste" else "expiry_risk"
    if not st.button("Generate predictions", type="primary", key="generate_predictions"):
        st.info("Choose a prediction type, then generate predictions to update the charts.")
        return

    try:
        if prediction_type == "Next-day food waste":
            result = api_get("/api/v1/predictions/food-waste")
            forecasts = pd.DataFrame(result["predictions"])
            forecast_date = pd.Timestamp(result["forecast_date"])
        else:
            result = api_get(
                "/api/v1/predictions/expiry-risk",
                params={"min_probability": 0},
            )
            forecasts = pd.DataFrame(result["predictions"])
            if "snapshot_date" in forecasts:
                forecasts["snapshot_date"] = pd.to_datetime(
                    forecasts["snapshot_date"], errors="coerce"
                )
    except (requests.RequestException, ValueError, KeyError) as error:
        st.error(
            f"Could not generate predictions from the backend API: {error}. "
            "Start the backend with `python -m uvicorn app.main:app --app-dir backend --reload`."
        )
        return

    if prediction_type == "Next-day food waste":
        st.metric(
            f"Predicted waste for {forecast_date.date()}",
            f"{float(result['total_predicted_waste_units']):,.1f} units",
        )
        waste = data["waste"].copy()
        waste["date"] = pd.to_datetime(waste["date"], errors="coerce")
        waste["waste_units"] = pd.to_numeric(waste["waste_units"], errors="coerce")
        actual = (
            waste.dropna(subset=["date", "waste_units"])
            .groupby("date")["waste_units"]
            .sum()
            .tail(21)
        )
        if not actual.empty:
            st.subheader("Recorded waste and next-day forecast")
            st.line_chart(actual.rename("Recorded waste, all products"))
            anchor_date = actual.index.max()
            anchor_value = float(actual.loc[anchor_date])
            graph = pd.Series(
                [anchor_value, float(result["total_predicted_waste_units"])],
                index=[anchor_date, forecast_date],
                name="Forecast (last actual to next day)",
            )
            st.line_chart(graph)
        st.subheader("Predicted waste by product")
        product_graph = forecasts.set_index("product_name")[
            "predicted_waste_units"
        ].sort_values(ascending=False)
        st.bar_chart(product_graph)
        display_columns = [
            column for column in (
                "product_name", "category", "forecast_date", "predicted_waste_units",
            ) if column in forecasts.columns
        ]
        st.dataframe(
            forecasts[display_columns].round({"predicted_waste_units": 2}),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Forecast inputs come from each product's latest recorded date. "
            "Actual future waste is not yet available."
        )
    else:
        high_risk = forecasts.head(20).copy()
        st.metric(
            "Batches with predicted expiry risk ≥ 50%",
            int(forecasts["predicted_expiry_risk"].ge(0.5).sum()),
        )
        st.subheader("Predicted expiry risk by batch")
        chart_column = "product_name" if "product_name" in high_risk else "product_id"
        high_risk["batch_label"] = (
            high_risk["batch_id"].astype(str)
            + " · "
            + high_risk[chart_column].astype(str)
        )
        st.bar_chart(
            high_risk.set_index("batch_label")["predicted_expiry_risk"].sort_values()
        )
        display_columns = [
            column for column in (
                "batch_id", "product_name", "product_id", "category",
                "days_to_expiry", "quantity_remaining", "predicted_expiry_risk",
            ) if column in high_risk.columns
        ]
        high_risk["predicted_expiry_risk"] = (
            high_risk["predicted_expiry_risk"] * 100
        ).round(1)
        st.dataframe(high_risk[display_columns], width="stretch", hide_index=True)
        st.caption(
            "Risk probabilities are model predictions from inventory features; "
            "the stored expiry-risk label is not used as an input."
        )


def render_model_page(
    title: str,
    model_name: str,
    description: str,
    metrics: dict[str, dict],
) -> None:
    st.title(title)
    st.caption(description)
    render_pipeline_summary(metrics, model_name)


def render_dashboard(search: str, data: dict[str, pd.DataFrame], metrics: dict[str, dict]) -> None:
    inventory = get_inventory_view(data)
    recent_waste, waste_total, latest_date = get_recent_waste(data)
    models_ready, model_total = get_model_status()
    product_count = (
        data["products"]["product_id"].nunique()
        if "product_id" in data["products"]
        else inventory.get("product_id", pd.Series(dtype=str)).nunique()
    )
    risky_count = (
        int(inventory["expiry_risk_label"].eq(1).sum())
        if "expiry_risk_label" in inventory
        else 0
    )
    backend_summary = None
    try:
        backend_summary = api_get("/api/v1/dashboard")
    except (requests.RequestException, ValueError) as error:
        st.warning(f"Backend dashboard data is unavailable; showing local CSV data: {error}")
    if backend_summary:
        product_count = int(backend_summary.get("products_tracked", product_count))
        risky_count = int(backend_summary.get("expiry_risk_batches", risky_count))
        waste_total = float(
            backend_summary.get("recorded_waste_last_7_days", waste_total)
        )
        latest_date = str(
            backend_summary.get("waste_data_through", latest_date)
        )

    st.markdown(
        f"""
        <section class="ww-hero">
            <div class="ww-hero-copy">
                <div class="ww-eyebrow">Fresh inventory. Smarter store decisions.</div>
                <h1>Welcome to <span class="ww-green">WasteWise AI</span></h1>
                <p>Forecast grocery demand, catch expiry risks early, and reduce food waste across your supermarket.</p>
                <div class="ww-hero-tags">
                    <span>📈 Demand forecasting</span>
                    <span>⏳ Expiry risk alerts</span>
                    <span>🥬 Food waste prediction</span>
                </div>
            </div>
            <div class="ww-hero-art" aria-hidden="true">🛒</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    stat_cards = [
        ("🛍️", "Products tracked", f"{product_count:,}", "Grocery catalog"),
        ("📦", "Inventory batches", f"{len(inventory):,}", "Current dataset"),
        ("⏳", "Expiry-risk batches", f"{risky_count:,}", "Labeled high risk"),
        ("🥬", "Recorded food waste", f"{waste_total:,.0f}", f"Latest 7 days · {latest_date}"),
        ("🤖", "Models trained", f"{models_ready}/{model_total}", "Forecasting + waste"),
    ]
    cards_html = "".join(
        f'<div class="ww-stat-card"><div class="ww-stat-label">'
        f"<span>{icon}</span><span>{label}</span></div>"
        f'<strong class="ww-stat-value">{value}</strong>'
        f'<span class="ww-stat-caption">{caption}</span></div>'
        for icon, label, value, caption in stat_cards
    )
    st.markdown(f'<div class="ww-stat-grid">{cards_html}</div>', unsafe_allow_html=True)

    left, right = st.columns([1.38, 1], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown(
                """
                <div class="ww-panel-heading">
                    <div class="ww-panel-icon">⚠️</div>
                    <h3>Expiry risk action queue</h3>
                </div>
                <div class="ww-panel-subtitle">Prioritize stock with the least time remaining.</div>
                """,
                unsafe_allow_html=True,
            )
            if backend_summary and "expiry_risk_queue" in backend_summary:
                queue = pd.DataFrame(backend_summary["expiry_risk_queue"])
                if search and not queue.empty:
                    searchable = queue.astype(str).apply(
                        lambda column: column.str.casefold().str.contains(
                            search.casefold(), regex=False
                        )
                    ).any(axis=1)
                    queue = queue[searchable]
                if queue.empty:
                    st.info("No matching expiry-risk batches found.")
                else:
                    st.dataframe(queue, width="stretch", hide_index=True)
            else:
                render_expiry_table(inventory, search)
    with right:
        with st.container(border=True):
            st.markdown(
                """
                <div class="ww-panel-heading">
                    <div class="ww-panel-icon">🥬</div>
                    <h3>Food waste snapshot</h3>
                </div>
                <div class="ww-panel-subtitle">Recent recorded waste by product category.</div>
                """,
                unsafe_allow_html=True,
            )
            render_waste_chart(data)
    if "discount_recommendation" in metrics:
        st.markdown(
            '<div class="ww-data-note"><strong>Discount recommendations:</strong> '
            'the scenario dataset is simulated, so recommendations are a prototype '
            'and not evidence of real customer price response.</div>',
            unsafe_allow_html=True,
        )


def render_statistics(metrics: dict[str, dict]) -> None:
    st.title("Model performance")
    st.caption("Chronological holdout metrics for forecasting and waste models.")
    if not metrics:
        st.info("No evaluation metrics yet. Train the models to populate this page.")
        return
    for name, values in metrics.items():
        with st.expander(name.replace("_", " ").title(), expanded=True):
            st.json(values)


def render_about() -> None:
    st.title("About WasteWise AI")
    st.write(
        "WasteWise AI is a grocery and supermarket food-waste decision-support "
        "prototype. It is designed to forecast item demand from historical sales, "
        "flag inventory batches at expiry risk, estimate next-day waste from "
        "prior-day inventory signals, and explore discount scenarios."
    )
    st.info(
        "Demand, expiry and waste estimates depend on the supplied datasets. "
        "The discount scenarios are simulated and should not be treated as "
        "measured customer price response."
    )


def main() -> None:
    data = load_retail_data()
    metrics = load_training_metrics()
    with st.sidebar:
        render_brand()
        page = st.radio(
            "Navigation",
            [
                "Dashboard",
                "Monitoring",
                "Predictions",
                "Demand Forecast",
                "Expiry Risk",
                "Food Waste",
                "Discount Recommendations",
                "Model Performance",
                "About",
            ],
            format_func=lambda item: {
                "Dashboard": "⌂  Dashboard",
                "Monitoring": "◷  Monitoring",
                "Predictions": "↗  Predictions",
                "Demand Forecast": "▥  Demand Forecast",
                "Expiry Risk": "⌛  Expiry Risk",
                "Food Waste": "🥬  Food Waste",
                "Discount Recommendations": "🏷️  Discount Plan",
                "Model Performance": "▤  Model Performance",
                "About": "ⓘ  About",
            }[item],
            label_visibility="collapsed",
        )
        st.markdown(
            """
            <div class="ww-sidebar-note">
                🥬 <strong>Save good food.</strong><br>
                Turn store data into smarter ordering and timely stock actions.
            </div>
            """,
            unsafe_allow_html=True,
        )

    search_col, user_col = st.columns([3.4, 1])
    with search_col:
        search = st.text_input(
            "Search products",
            placeholder="⌕  Search product or category...",
            label_visibility="collapsed",
        )
    with user_col:
        st.markdown(
            '<div class="ww-topline"><span class="ww-user-dot">S</span>Store Analytics</div>',
            unsafe_allow_html=True,
        )

    backend_online, backend_message, database_state = get_backend_health()
    if backend_online:
        st.caption(
            f"Backend API: connected · {backend_message} · MySQL: {database_state}"
        )
        if database_state != "connected":
            st.warning(
                "MySQL is not connected yet; the backend is currently using local CSV "
                "data where available. Configure `backend/.env` and import the datasets."
            )
    elif page in {"Dashboard", "Predictions", "Monitoring"}:
        st.warning(
            "Backend API is offline. Start it in a separate terminal with "
            "`python -m uvicorn app.main:app --app-dir backend --reload`."
        )

    if page == "Dashboard":
        render_dashboard(search, data, metrics)
    elif page == "Monitoring":
        render_monitoring(data, metrics)
    elif page == "Predictions":
        render_predictions(data)
    elif page == "Demand Forecast":
        render_model_page(
            "Demand forecast",
            "demand_forecast",
            "Historical sales, calendar signals, lagged demand, prices, and promotions support replenishment planning.",
            metrics,
        )
    elif page == "Expiry Risk":
        render_model_page(
            "Expiry risk",
            "expiry_risk",
            "Identify batches that may not sell through before their expiry date.",
            metrics,
        )
        render_expiry_table(get_inventory_view(data), search)
    elif page == "Food Waste":
        render_model_page(
            "Food waste prediction",
            "food_waste",
            "Estimate the next day's waste from the previous day's stock, receipts, sales, price, and expiry signals.",
            metrics,
        )
        render_waste_chart(data)
    elif page == "Discount Recommendations":
        render_model_page(
            "Discount recommendations",
            "discount_recommendation",
            "Compare simulated discount scenarios for remaining grocery stock.",
            metrics,
        )
        recommendations_path = ARTIFACT_DIR / "discount_recommendations.csv"
        if recommendations_path.exists():
            st.dataframe(
                pd.read_csv(recommendations_path).head(25),
                width="stretch",
                hide_index=True,
            )
        st.warning(
            "Prototype only: the supplied scenario outcomes are simulated and do "
            "not establish real customer price response."
        )
    elif page == "Model Performance":
        render_statistics(metrics)
    else:
        render_about()

    st.markdown(
        """
        <div class="ww-footer">
            <span>WasteWise AI · Grocery food waste management</span>
            <span>Decision-support prototype · Verify recommendations with store data</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
