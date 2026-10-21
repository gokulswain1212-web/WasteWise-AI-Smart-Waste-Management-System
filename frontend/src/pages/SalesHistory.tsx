import { useEffect, useState } from "react";
import { getSalesHistory, type SalesHistoryResponse } from "../services/reports";

export default function SalesHistory() {
  const [result, setResult] = useState<SalesHistoryResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSalesHistory(100, offset)
      .then(setResult)
      .catch(() => setError("Could not load sales history. Check the API connection and sign-in session."))
      .finally(() => setLoading(false));
  }, [offset]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>Recorded sales history</h3>
          <p>Daily units sold aggregated from the perishable-inventory records.</p>
        </div>
        <span className="small-pill">
          {result ? (result.data_source === "mysql" ? "MySQL" : "Sample CSV") : "Checking source"}
        </span>
      </div>
      {loading && <p className="notice" role="status">Loading sales history...</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      {result && !error && (
        <>
          <p className="muted">
            {result.date_from ?? "No dated records"} through {result.date_through ?? "no dated records"} · {result.total_days} days · {result.total_units_sold?.toLocaleString() ?? "Units not recorded"}
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>DATE</th><th>UNITS SOLD</th></tr></thead>
              <tbody>
                {result.sales_by_day.map((day) => (
                  <tr key={day.date}>
                    <td>{day.date}</td>
                    <td>{day.units_sold?.toLocaleString() ?? "Not recorded"}</td>
                  </tr>
                ))}
                {!result.sales_by_day.length && (
                  <tr><td colSpan={2} className="empty-state">No sales records are available.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="pagination-controls">
            <button
              className="text-button"
              disabled={result.offset === 0}
              onClick={() => setOffset(Math.max(0, result.offset - result.limit))}
            >
              Previous
            </button>
            <span className="muted">
              Page {Math.floor(result.offset / result.limit) + 1} of {Math.max(1, Math.ceil(result.total_days / result.limit))}
            </span>
            <button
              className="text-button"
              disabled={result.offset + result.sales_by_day.length >= result.total_days}
              onClick={() => setOffset(result.offset + result.limit)}
            >
              Next
            </button>
          </div>
          <p className="muted">This is an aggregated history, not a transaction ledger. Sales entry is not available.</p>
        </>
      )}
    </section>
  );
}