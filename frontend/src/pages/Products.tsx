import { useEffect, useState } from "react";
import { getProducts, type Product, type ProductsResponse } from "../services/products";

function displayValue(value: number | null | undefined): string {
  return value == null ? "Not supplied" : value.toLocaleString();
}

export default function Products() {
  const [result, setResult] = useState<ProductsResponse | null>(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      getProducts(search.trim() || undefined, 100, offset)
        .then((data) => {
          if (!cancelled) setResult(data);
        })
        .catch(() => {
          if (!cancelled) {
            setError("Could not load the product catalog. Check the API connection and sign-in session.");
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 200);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [search, offset]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>Product catalog</h3>
          <p>Read-only products from the configured database or local CSV source.</p>
        </div>
        <span className="small-pill">
          {result ? (result.data_source === "mysql" ? "MySQL" : "Sample CSV") : "Checking source"}
        </span>
      </div>
      <label className="table-search">
        <input
          aria-label="Search products"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setOffset(0);
          }}
          placeholder="Search name, ID, or category"
        />
      </label>
      {loading && <p className="notice" role="status">Loading products...</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      {result && !error && (
        <>
          <p className="muted">Showing {result.products.length} of {result.total} matching products.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>PRODUCT ID</th>
                  <th>PRODUCT</th>
                  <th>CATEGORY</th>
                  <th>SHELF LIFE (DAYS)</th>
                  <th>SELLING PRICE</th>
                </tr>
              </thead>
              <tbody>
                {result.products.map((product: Product) => (
                  <tr key={product.product_id}>
                    <td>{product.product_id}</td>
                    <td>{product.product_name}</td>
                    <td>{product.category}</td>
                    <td>{displayValue(product.shelf_life_days)}</td>
                    <td>{displayValue(product.selling_price)}</td>
                  </tr>
                ))}
                {!result.products.length && (
                  <tr><td colSpan={5} className="empty-state">No matching products were returned.</td></tr>
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
              Page {Math.floor(result.offset / result.limit) + 1} of {Math.max(1, Math.ceil(result.total / result.limit))}
            </span>
            <button
              className="text-button"
              disabled={result.offset + result.products.length >= result.total}
              onClick={() => setOffset(result.offset + result.limit)}
            >
              Next
            </button>
          </div>
          <p className="muted">Catalog viewing only; product create, edit, and delete operations are not available.</p>
        </>
      )}
    </section>
  );
}