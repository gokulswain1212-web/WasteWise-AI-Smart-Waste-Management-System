
import { useEffect, useState } from "react";
import {
  getDiscountRecommendations,
  type DiscountRecommendation,
} from "../services/predictions";

export default function Recommendations() {
  const [items, setItems] = useState<DiscountRecommendation[]>([]);
  const [dataStatus, setDataStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDiscountRecommendations()
      .then((data) => {
        setItems(data.recommendations ?? []);
        setDataStatus(data.data_status ?? "");
      })
      .catch(() =>
        setError("Could not load recommendations. Check backend authentication and connection.")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading recommendations...</p>;
  if (error) return <p role="alert">{error}</p>;

  const eligible = items.filter(
    (item) => item.days_to_expiry > 0 && item.quantity_remaining > 0
  );

  const needsReview = items.filter(
    (item) => item.days_to_expiry <= 0 && item.quantity_remaining > 0
  );

  return (
    <section>
      <h1>Smart Recommendations</h1>
      <p>{dataStatus}</p>
      <p>
        These are simulated prototype recommendations, not proven customer-price
        predictions. Verify stock, expiry, and store policy before acting.
      </p>

      <h2>Eligible for review</h2>
      {eligible.length === 0 ? (
        <p>No eligible batches found.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Batch</th>
                <th>Product ID</th>
                <th>Days to expiry</th>
                <th>Quantity remaining</th>
                <th>Predicted gross margin</th>
              </tr>
            </thead>
            <tbody>
              {eligible.map((item) => (
                <tr key={item.batch_id}>
                  <td>{item.batch_id}</td>
                  <td>{item.product_id}</td>
                  <td>{item.days_to_expiry}</td>
                  <td>{item.quantity_remaining}</td>
                  <td>{item.predicted_gross_margin.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Expired or expiry-date review required</h2>
      <p>
        Do not discount or sell these batches. Verify product safety and follow
        your store's removal policy.
      </p>
      {needsReview.length === 0 ? (
        <p>No batches require this review in the returned recommendations.</p>
      ) : (
        <ul>
          {needsReview.map((item) => (
            <li key={item.batch_id}>
              Batch {item.batch_id}: Product {item.product_id},{" "}
              {item.days_to_expiry < 0
                ? `${Math.abs(item.days_to_expiry)} day(s) past expiry`
                : "expires today"}; quantity {item.quantity_remaining}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
