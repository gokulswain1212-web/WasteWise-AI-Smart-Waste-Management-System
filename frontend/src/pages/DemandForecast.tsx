import { useEffect, useMemo, useState } from "react";
import {
  getDemandForecast,
  type DemandForecastResponse,
} from "../services/forecast";

export default function DemandForecast() {
  const [forecast, setForecast] = useState<DemandForecastResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDemandForecast()
      .then((result) => {
        setForecast(result);
        setSelectedDate(result.forecast_start);
      })
      .catch(() => {
        setError(
          "Could not load the saved-model forecast. Check the API connection, model artifact, and sign-in session.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const forecastDates = useMemo(
    () => [...new Set(forecast?.predictions.map((item) => item.forecast_date) ?? [])],
    [forecast],
  );
  const dailyPredictions = useMemo(
    () =>
      forecast?.predictions.filter((item) => item.forecast_date === selectedDate) ?? [],
    [forecast, selectedDate],
  );

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>Daily demand forecast</h3>
          <p>Iterative predictions from the saved demand model.</p>
        </div>
        <span className="status status-normal">
          {loading ? "Loading" : forecast ? "Model forecast" : "Unavailable"}
        </span>
      </div>
      {loading && (
        <p className="notice" role="status">
          Loading historical benchmark inputs and generating daily predictions...
        </p>
      )}
      {error && <p className="notice" role="alert">{error}</p>}
      {!loading && !error && forecast && forecast.predictions.length === 0 && (
        <p className="empty-state">The model returned no demand predictions.</p>
      )}
      {!loading && !error && forecast && forecast.predictions.length > 0 && (
        <>
          <p className="notice">
            {forecast.data_source}. Forecasts cover a deterministic sample of{" "}
            {forecast.series_count.toLocaleString()} item/store series, not the
            configured MySQL store. {forecast.series_scope}
          </p>
          <div className="metrics-grid forecast-metrics">
            <div className="metric-card">
              <p className="metric-label">Historical data through</p>
              <h2>{forecast.historical_data_through}</h2>
            </div>
            <div className="metric-card">
              <p className="metric-label">Forecast period</p>
              <h2>{forecast.forecast_start} – {forecast.forecast_end}</h2>
            </div>
            <div className="metric-card">
              <p className="metric-label">Frequency / horizon</p>
              <h2>{forecast.forecast_frequency} / {forecast.horizon_days} days</h2>
            </div>
          </div>
          <label className="metric-label" htmlFor="forecast-date">
            Forecast date
          </label>
          <select
            className="forecast-date-select"
            id="forecast-date"
            value={selectedDate}
            onChange={(event) => setSelectedDate(event.target.value)}
          >
            {forecastDates.map((date) => (
              <option key={date} value={date}>{date}</option>
            ))}
          </select>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Store</th>
                  <th>Item</th>
                  <th>Department</th>
                  <th>Category</th>
                  <th>Predicted demand (units)</th>
                </tr>
              </thead>
              <tbody>
                {dailyPredictions.map((item) => (
                  <tr key={`${item.forecast_date}-${item.series_id}`}>
                    <td>{item.store_id}</td>
                    <td>{item.item_id}</td>
                    <td>{item.department_id}</td>
                    <td>{item.category_id}</td>
                    <td>{item.predicted_units.toLocaleString(undefined, {
                      maximumFractionDigits: 2,
                    })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
