
import api from "./api";

export interface ExpiryPrediction {
  batch_id: number | string;
  product_name?: string | null;
  product_id: number | string;
  category: string;
  snapshot_date: string;
  expiry_date: string | null;
  days_to_expiry: number;
  quantity_remaining: number;
  quantity_at_risk: number;
  predicted_expiry_risk: number;
  risk_category: "LOW" | "MEDIUM" | "HIGH";
  snapshot_expiry_status: string;
}

export interface ExpiryRiskResponse {
  min_probability: number;
  risk_category_thresholds: {
    low: string;
    medium: string;
    high: string;
  };
  data_notice: string;
  batches_at_or_above_threshold: number;
  predictions: ExpiryPrediction[];
}

export interface DiscountRecommendation {
  batch_id: number;
  product_id: number;
  days_to_expiry: number;
  quantity_remaining: number;
  discount_pct: number;
  predicted_gross_margin: number;
}

export interface DiscountResponse {
  data_status: string;
  scenario_rows_loaded: number;
  eligible_scenarios: number;
  excluded_expired_scenarios: number;
  excluded_expiring_today_scenarios: number;
  recommendations: DiscountRecommendation[];
}

const pendingExpiryRequests = new Map<number, Promise<ExpiryRiskResponse>>();

export async function getExpiryRisk(
  minProbability = 0.5,
): Promise<ExpiryRiskResponse> {
  const pending = pendingExpiryRequests.get(minProbability);
  if (pending) return pending;

  const request = api
    .get<ExpiryRiskResponse>(
      "/api/v1/predictions/expiry-risk",
      { params: { min_probability: minProbability } },
    )
    .then((response) => response.data)
    .finally(() => pendingExpiryRequests.delete(minProbability));
  pendingExpiryRequests.set(minProbability, request);
  return request;
}

export async function getDiscountRecommendations(): Promise<DiscountResponse> {
  const response = await api.get<DiscountResponse>(
    "/api/v1/recommendations/discounts"
  );
  return response.data;
}
