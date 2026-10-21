import api from "./api";

export interface Product {
  product_id: string;
  product_name: string;
  category: string;
  shelf_life_days?: number | null;
  selling_price?: number | null;
  unit_cost?: number | null;
}

export interface ProductsResponse {
  data_source: "mysql" | "local_csv";
  total: number;
  limit: number;
  offset: number;
  products: Product[];
}

export async function getProducts(
  search?: string,
  limit = 100,
  offset = 0,
): Promise<ProductsResponse> {
  const response = await api.get<ProductsResponse>("/api/v1/products", {
    params: { limit, offset, ...(search ? { search } : {}) },
  });
  return response.data;
}