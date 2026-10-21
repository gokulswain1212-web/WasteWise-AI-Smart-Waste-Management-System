import { useEffect, useState } from "react";
import axios from "axios";
import {
  getExpiryRisk,
  type ExpiryPrediction,
  type ExpiryRiskResponse,
} from "../services/predictions";

export default function ExpiryRisk() {
  const [result, setResult] = useState<ExpiryRiskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getExpiryRisk()
      .then(setResult)
      .catch((requestError: unknown) => setError(getRequestErrorMessage(requestError)))
      .finally(() => setLoading(false));
  }, []);

  const predictions: ExpiryPrediction[] = result?.predictions ?? [];

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>Expiry-risk predictions</h3>
          <p>
            Saved-model probabilities for recorded inventory snapshots; not
            verified live stock.
          </p>
        </div>
        <span className="status status-high">
          {loading
            ? "Loading"
            : `${result?.batches_at_or_above_threshold.toLocaleString() ?? 0} at threshold`}
        </span>
      </div>
      {loading && (
        <p className="notice" role="status">
          Scoring inventory snapshots with the saved expiry-risk model...
        </p>
      )}
      {error && <p className="notice" role="alert">{error}</p>}
      {!loading && !error && result && (
        <>
          <p className="notice">{result.data_notice}</p>
          <p className="muted">
            Showing probability ≥ {(result.min_probability * 100).toFixed(0)}%.
            Risk categories: {result.risk_category_thresholds.low} (low),{" "}
            {result.risk_category_thresholds.medium} (medium),{" "}
            {result.risk_category_thresholds.high} (high).
          </p>
          {predictions.length === 0 ? (
            <p className="empty-state">
              No batches meet the selected probability threshold.
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>Product</th>
                    <th>Snapshot date</th>
                    <th>Expiry date</th>
                    <th>Status at snapshot</th>
                    <th>Days to expiry</th>
                    <th>Quantity at risk</th>
                    <th>Risk category</th>
                    <th>Predicted probability</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((item) => (
                    <tr key={item.batch_id}>
                      <td>{item.batch_id}</td>
                      <td>{item.product_name ?? item.product_id}</td>
                      <td>{item.snapshot_date ?? "Not supplied"}</td>
                      <td>{item.expiry_date ?? "Not supplied"}</td>
                      <td>{item.snapshot_expiry_status}</td>
                      <td>{item.days_to_expiry}</td>
                      <td>{item.quantity_at_risk.toLocaleString()}</td>
                      <td>{item.risk_category}</td>
                      <td>
                        {(item.predicted_expiry_risk * 100).toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function getRequestErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return "An unexpected error prevented expiry predictions from loading.";
  }
  if (!error.response) {
    return "The API could not be reached. Check that the backend is running and the frontend proxy is configured.";
  }
  switch (error.response.status) {
    case 401:
      return "Your sign-in session is missing or expired. Sign in again to view expiry predictions.";
    case 422:
      return "The expiry-risk request parameters are invalid. Use a probability threshold from 0 to 1.";
    case 503:
      return "Expiry predictions are temporarily unavailable because inventory data or the saved model could not be loaded.";
    case 500:
      return "The backend could not score the available inventory. Check the server logs for the diagnostic.";
    default:
      return `Expiry predictions could not be loaded (HTTP ${error.response.status}).`;
  }
}
