
import { useEffect, useState } from "react";
import {
  getExpiryRisk,
  type ExpiryPrediction,
} from "../services/predictions";

export default function ExpiryRisk() {
  const [predictions, setPredictions] = useState<ExpiryPrediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getExpiryRisk()
      .then((data) => setPredictions(data.predictions ?? []))
      .catch(() => setError("Could not load expiry predictions. Check backend authentication and connection."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading expiry-risk predictions...</p>;
  if (error) return <p role="alert">{error}</p>;

  return (
    <section>
      <h1>Expiry Risk Monitor</h1>
      <p>Model predictions from saved inventory snapshots. Verify current stock and expiry dates before acting.</p>

      {predictions.length === 0 ? (
        <p>No expiry predictions are available.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Batch</th>
                <th>Product</th>
                <th>Snapshot date</th>
                <th>Days to expiry</th>
                <th>Quantity</th>
                <th>Predicted risk</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map((item) => (
                <tr key={item.batch_id}>
                  <td>{item.batch_id}</td>
                  <td>{item.product_name}</td>
                  <td>{item.snapshot_date}</td>
                  <td>{item.days_to_expiry}</td>
                  <td>{item.quantity_remaining}</td>
                  <td>{(item.predicted_expiry_risk * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
