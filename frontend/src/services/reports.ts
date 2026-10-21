import api from "./api";

export interface SalesHistoryResponse {
  data_source: "mysql" | "local_csv";
  total_days: number;
  total_units_sold: number | null;
  date_from: string | null;
  date_through: string | null;
  limit: number;
  offset: number;
  sales_by_day: { date: string; units_sold: number | null }[];
}

export interface WasteReportResponse {
  data_source: "mysql" | "local_csv";
  recorded_waste_units: number | null;
  record_count: number;
  daily_count: number;
  date_from: string | null;
  date_through: string | null;
  category_breakdown: { category: string; waste_units: number | null }[];
  daily_waste: { date: string; waste_units: number | null }[];
  limit: number;
  offset: number;
  notice: string;
}

export async function getSalesHistory(
  limit = 100,
  offset = 0,
): Promise<SalesHistoryResponse> {
  const response = await api.get<SalesHistoryResponse>(
    "/api/v1/sales-history",
    { params: { limit, offset } },
  );
  return response.data;
}

export async function getWasteReport(
  limit = 100,
  offset = 0,
): Promise<WasteReportResponse> {
  const response = await api.get<WasteReportResponse>(
    "/api/v1/waste-report",
    { params: { limit, offset } },
  );
  return response.data;
}
