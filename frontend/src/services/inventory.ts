import api from "./api";

export interface InventoryBatch {
  batch_id: string;
  product_id: string;
  product_name?: string | null;
  category?: string | null;
  snapshot_date?: string | null;
  expiry_date?: string | null;
  days_to_expiry: number | null;
  quantity_remaining: number | null;
  initial_quantity?: number | null;
  avg_daily_sales_7d?: number | null;
  expected_demand_before_expiry?: number | null;
  expiry_risk_label?: string | number | null;
  snapshot_expiry_status: string;
}

export interface InventoryResponse {
  data_source: "mysql" | "local_csv";
  total: number;
  limit: number;
  offset: number;
  inventory_batches: InventoryBatch[];
  inventory_data_notice: string;
}

export async function getInventory(
  search?: string,
  limit = 100,
  offset = 0,
): Promise<InventoryResponse> {
  const response = await api.get<InventoryResponse>("/api/v1/inventory", {
    params: { limit, offset, ...(search ? { search } : {}) },
  });
  return response.data;
}