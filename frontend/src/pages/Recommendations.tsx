
import { useEffect, useState } from "react";
import {
  getDiscountRecommendations,
  type DiscountRecommendation,
  type DiscountResponse,
} from "../services/predictions";

export default function Recommendations() {
  const [items, setItems] = useState<DiscountRecommendation[]>([]);
  const [result, setResult] = useState<DiscountResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDiscountRecommendations()
      .then((data) => {
        setResult(data);
        setItems(data.recommendations ?? []);
      })
      .catch(() =>
        setError("Could not load recommendations. Check the API connection and sign-in session.")
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>Smart discount scenarios</h3>
          <p>Read-only simulated model output; not validated customer-price response.</p>
        </div>
      </div>
      {loading && <p className="notice" role="status">Loading discount scenarios...</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      {result && !error && (
        <>
          <p className="notice">{result.data_status}</p>
          <p className="muted">
            {result.scenario_rows_loaded.toLocaleString()} source scenarios ·{" "}
            {result.eligible_scenarios.toLocaleString()} eligible ·{" "}
            {result.excluded_expired_scenarios.toLocaleString()} expired excluded ·{" "}
            {result.excluded_expiring_today_scenarios.toLocaleString()} expiring-today excluded
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>BATCH</th>
                  <th>PRODUCT ID</th>
                  <th>DAYS TO EXPIRY</th>
                  <th>QUANTITY REMAINING</th>
                  <th>DISCOUNT RATE</th>
                  <th>PREDICTED GROSS MARGIN (MODEL UNITS)</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.batch_id}>
                    <td>{item.batch_id}</td>
                    <td>{item.product_id}</td>
                    <td>{item.days_to_expiry}</td>
                    <td>{item.quantity_remaining.toLocaleString()}</td>
                    <td>{item.discount_pct.toFixed(1)}%</td>
                    <td>{item.predicted_gross_margin.toFixed(2)}</td>
                  </tr>
                ))}
                {!items.length && (
                  <tr><td colSpan={6} className="empty-state">No eligible discount scenarios were returned.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="notice">
            Expired products must never be sold or discounted. Scenarios expiring on their recorded scenario date are excluded. Verify current physical stock, expiry labels, and store policy before acting.
          </p>
        </>
      )}
    </section>
  );
}
