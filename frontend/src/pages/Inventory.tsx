import { useEffect, useState } from "react";
import { getInventory, type InventoryResponse } from "../services/inventory";

export default function Inventory() {
  const [result, setResult] = useState<InventoryResponse | null>(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      getInventory(search.trim() || undefined, 100, offset)
        .then((data) => {
          if (!cancelled) setResult(data);
        })
        .catch(() => {
          if (!cancelled) {
            setError("Could not load inventory snapshots. Check the API connection and sign-in session.");
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 200);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [search, offset]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>Inventory snapshots</h3>
          <p>Read-only batch records ordered by recorded days to expiry.</p>
        </div>
        <span className="small-pill">
          {result ? (result.data_source === "mysql" ? "MySQL" : "Sample CSV") : "Checking source"}
        </span>
      </div>
      <label className="table-search">
        <input
          aria-label="Search inventory batches"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setOffset(0);
          }}
          placeholder="Search batch, product, or category"
        />
      </label>
      {loading && <p className="notice" role="status">Loading inventory...</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      {result && !error && (
        <>
          <p className="muted">Showing {result.inventory_batches.length} of {result.total} matching batches.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>BATCH</th>
                  <th>PRODUCT</th>
                  <th>SNAPSHOT</th>
                  <th>QUANTITY</th>
                  <th>DAYS TO EXPIRY</th>
                  <th>STATUS AT SNAPSHOT</th>
                </tr>
              </thead>
              <tbody>
                {result.inventory_batches.map((batch) => (
                  <tr key={batch.batch_id}>
                    <td>{batch.batch_id}</td>
                    <td>{batch.product_name ?? batch.product_id}</td>
                    <td>{batch.snapshot_date ?? "Not supplied"}</td>
                    <td>{batch.quantity_remaining?.toLocaleString() ?? "Not supplied"}</td>
                    <td>{batch.days_to_expiry ?? "Not supplied"}</td>
                    <td>{batch.snapshot_expiry_status}</td>
                  </tr>
                ))}
                {!result.inventory_batches.length && (
                  <tr><td colSpan={6} className="empty-state">No matching inventory batches were returned.</td></tr>
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
              Page {Math.floor(result.offset / result.limit) + 1} of {Math.max(1, Math.ceil(result.total / result.limit))}
            </span>
            <button
              className="text-button"
              disabled={result.offset + result.inventory_batches.length >= result.total}
              onClick={() => setOffset(result.offset + result.limit)}
            >
              Next
            </button>
          </div>
          <p className="notice">{result.inventory_data_notice}</p>
          <p className="muted">Inventory edits and stock transactions are not available in this prototype.</p>
        </>
      )}
    </section>
  );
}