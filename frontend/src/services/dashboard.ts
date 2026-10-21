import api from "./api";

export interface RiskBatch {
  batch_id: number | string;
  product_name: string | null;
  product_id: number | string;
  category: string | null;
  days_to_expiry: number | null;
  quantity_remaining: number;
  expected_demand_before_expiry: number | null;
}

export interface DashboardSummary {
  data_source: "mysql" | "local_csv";
  products_tracked: number;
  inventory_batches: number;
  expiry_risk_batches: number;
  recorded_waste_last_7_days: number;
  waste_data_through: string | null;
  waste_by_category_last_7_days: {
    category: string;
    waste_units: number;
  }[];
  daily_sales_last_7_days: {
    date: string;
    units_sold: number | null;
  }[];
  models: Record<string, boolean>;
  expiry_risk_queue: RiskBatch[];
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const response = await api.get<DashboardSummary>("/api/v1/dashboard");
  return response.data;
}
