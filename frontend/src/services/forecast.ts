import api from "./api";

export interface DemandForecastPrediction {
  forecast_date: string;
  series_id: string;
  item_id: string;
  department_id: string;
  category_id: string;
  store_id: string;
  predicted_units: number;
}

export interface DemandForecastResponse {
  data_source: string;
  forecast_frequency: "daily";
  historical_data_through: string;
  forecast_start: string;
  forecast_end: string;
  horizon_days: number;
  series_count: number;
  series_scope: string;
  predictions: DemandForecastPrediction[];
}

const pendingForecasts = new Map<number, Promise<DemandForecastResponse>>();

export async function getDemandForecast(
  horizonDays = 7,
): Promise<DemandForecastResponse> {
  const pending = pendingForecasts.get(horizonDays);
  if (pending) return pending;

  const request = api
    .get<DemandForecastResponse>(
      "/api/v1/predictions/demand-forecast",
      { params: { horizon_days: horizonDays }, timeout: 120_000 },
    )
    .then((response) => response.data)
    .finally(() => pendingForecasts.delete(horizonDays));
  pendingForecasts.set(horizonDays, request);
  return request;
}
