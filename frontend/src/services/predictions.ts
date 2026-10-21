
import api from "./api";

export interface ExpiryPrediction {
  batch_id: number;
  product_name: string;
  product_id: number;
  category: string;
  snapshot_date: string;
  days_to_expiry: number;
  quantity_remaining: number;
  predicted_expiry_risk: number;
}

export interface ExpiryRiskResponse {
  min_probability: number;
  batches_at_or_above_threshold: number;
  predictions: ExpiryPrediction[];
}

export interface DiscountRecommendation {
  batch_id: number;
  product_id: number;
  days_to_expiry: number;
  quantity_remaining: number;
  predicted_gross_margin: number;
}

export interface DiscountResponse {
  data_status: string;
  recommendations: DiscountRecommendation[];
}

export async function getExpiryRisk(): Promise<ExpiryRiskResponse> {
  const response = await api.get<ExpiryRiskResponse>(
    "/api/v1/predictions/expiry-risk"
  );
  return response.data;
}

export async function getDiscountRecommendations(): Promise<DiscountResponse> {
  const response = await api.get<DiscountResponse>(
    "/api/v1/recommendations/discounts"
  );
  return response.data;
}
