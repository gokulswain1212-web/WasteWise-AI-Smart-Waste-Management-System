import { useEffect, useState } from "react";
import { getWasteReport, type WasteReportResponse } from "../services/reports";

export default function WasteReports() {
  const [result, setResult] = useState<WasteReportResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getWasteReport(100, offset)
      .then(setResult)
      .catch(() => setError("Could not load waste records. Check the API connection and sign-in session."))
      .finally(() => setLoading(false));
  }, [offset]);

  return (
    <>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>Recorded waste report</h3>
            <p>Measured waste quantities available in the configured source.</p>
          </div>
          <span className="small-pill">
            {result ? (result.data_source === "mysql" ? "MySQL" : "Sample CSV") : "Checking source"}
          </span>
        </div>
        {loading && <p className="notice" role="status">Loading waste records...</p>}
        {error && <p className="notice" role="alert">{error}</p>}
        {result && !error && (
          <>
            <p className="muted">
              Recorded units: {result.recorded_waste_units?.toLocaleString() ?? "Not recorded"} · {result.record_count.toLocaleString()} rows · {result.date_from ?? "No dated records"} through {result.date_through ?? "no dated records"}
            </p>
            <p className="notice">{result.notice}</p>
            <h4>Waste by category</h4>
            <div className="table-wrap">
              <table>
                <thead><tr><th>CATEGORY</th><th>RECORDED WASTE UNITS</th></tr></thead>
                <tbody>
                  {result.category_breakdown.map((item) => (
                    <tr key={item.category}>
                      <td>{item.category}</td>
                      <td>{item.waste_units?.toLocaleString() ?? "Not recorded"}</td>
                    </tr>
                  ))}
                  {!result.category_breakdown.length && (
                    <tr><td colSpan={2} className="empty-state">No categorized waste records are available.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <h4>Daily recorded waste</h4>
            <div className="table-wrap">
              <table>
                <thead><tr><th>DATE</th><th>RECORDED WASTE UNITS</th></tr></thead>
                <tbody>
                  {result.daily_waste.map((item) => (
                    <tr key={item.date}>
                      <td>{item.date}</td>
                      <td>{item.waste_units?.toLocaleString() ?? "Not recorded"}</td>
                    </tr>
                  ))}
                  {!result.daily_waste.length && (
                    <tr><td colSpan={2} className="empty-state">No daily waste records are available.</td></tr>
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
                Page {Math.floor(result.offset / result.limit) + 1} of {Math.max(1, Math.ceil(result.daily_count / result.limit))}
              </span>
              <button
                className="text-button"
                disabled={result.offset + result.daily_waste.length >= result.daily_count}
                onClick={() => setOffset(result.offset + result.limit)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}