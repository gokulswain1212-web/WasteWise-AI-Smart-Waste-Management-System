
import api from "./api";

export interface ModelMetadata {
  ready: boolean;
  metadata: Record<string, string | number | boolean | null>;
}

export interface DriftFeatureResult {
  feature: string;
  status: "normal" | "drift_detected" | "unavailable";
  reason?: string;
  reference_rows?: number;
  current_rows?: number;
  reference_mean?: number;
  current_mean?: number;
  ks_statistic?: number;
  p_value?: number;
}

export interface DriftReport {
  status: "normal" | "drift_detected" | "unavailable";
  comparison_type?: string;
  date_column?: string;
  reference_period?: {
    start: string;
    end: string;
  };
  current_period?: {
    start: string;
    end: string;
  };
  reference_rows?: number;
  current_rows?: number;
  method?: string;
  p_value_threshold?: number;
  features_tested?: number;
  features_with_drift?: number;
  results?: DriftFeatureResult[];
  reason?: string;
  note?: string;
}




export interface MonitoringResponse {
  models: Record<string, ModelMetadata>;
  datasets: {
    dataset: string;
    rows: number;
    date_range: {
      start: string;
      end: string;
    } | null;
  }[];
  drift: {
    expiry_risk: DriftReport;
    food_waste: DriftReport;
  };
}


export async function getMonitoring(): Promise<MonitoringResponse> {
  const response = await api.get<MonitoringResponse>(
    "/api/v1/monitoring"
  );

  return response.data;
}
