
from typing import Any

import pandas as pd
from scipy.stats import ks_2samp


def detect_data_drift(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
    columns: list[str],
    p_value_threshold: float = 0.05,
) -> dict[str, Any]:
    """
    Compare numerical feature distributions using the KS two-sample test.

    A low p-value indicates evidence that the two distributions differ.
    It does not, by itself, prove that model performance has declined.
    """
    results = []

    for column in columns:
        if column not in reference_data.columns:
            results.append({
                "feature": column,
                "status": "unavailable",
                "reason": "Missing from reference data",
            })
            continue

        if column not in current_data.columns:
            results.append({
                "feature": column,
                "status": "unavailable",
                "reason": "Missing from current data",
            })
            continue

        reference = pd.to_numeric(
            reference_data[column], errors="coerce"
        ).dropna()

        current = pd.to_numeric(
            current_data[column], errors="coerce"
        ).dropna()

        if len(reference) < 2 or len(current) < 2:
            results.append({
                "feature": column,
                "status": "unavailable",
                "reason": "At least two valid values per dataset are required",
            })
            continue

        test = ks_2samp(reference, current)

        drift_detected = test.pvalue < p_value_threshold

        results.append({
            "feature": column,
            "status": "drift_detected" if drift_detected else "normal",
            "reference_rows": int(len(reference)),
            "current_rows": int(len(current)),
            "reference_mean": float(reference.mean()),
            "current_mean": float(current.mean()),
            "ks_statistic": float(test.statistic),
            "p_value": float(test.pvalue),
        })

    tested = [
        result for result in results
        if result["status"] in ("normal", "drift_detected")
    ]

    return {
        "method": "Kolmogorov-Smirnov two-sample test",
        "p_value_threshold": p_value_threshold,
        "features_tested": len(tested),
        "features_with_drift": sum(
            result["status"] == "drift_detected"
            for result in tested
        ),
        "results": results,
        "note": (
            "Statistical drift is a signal to investigate, not proof "
            "that model accuracy has declined. Multiple-feature testing "
            "may require correction for false positives."
        ),
    }
