
import { useEffect, useState, type ReactNode } from "react";
import { getMonitoring, type MonitoringResponse } from "./services/monitoring";
import {
  LayoutDashboard,
  Package,
  ShoppingCart,
  ChartNoAxesCombined,
  AlertTriangle,
  Lightbulb,
  Activity,
  FileBarChart,
  BookOpen,
  Search,
  Bell,
  Leaf,
  Menu,
  X,
  TrendingUp,
  ArrowUpRight,
  ShieldCheck,
  BrainCircuit,
  Boxes,
  CalendarDays,
  ChevronRight,
  LogOut,
} from "lucide-react";
import {
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  BarChart,
  Bar,
} from "recharts";
import ExpiryRisk from "./pages/ExpiryRisk";
import Login from "./pages/Login";
import Recommendations from "./pages/Recommendations";
import {
  getDashboardSummary,
  type DashboardSummary,
  type RiskBatch,
} from "./services/dashboard";
import { getSession, logout } from "./services/auth";
import "./styles.css";

export default function App() {
  const [authStatus, setAuthStatus] = useState<
    "checking" | "authenticated" | "unauthenticated"
  >("checking");
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getSession()
      .then((session) => {
        if (!cancelled) {
          setAuthStatus(session.email ? "authenticated" : "unauthenticated");
        }
      })
      .catch(() => {
        if (cancelled) return;

        setAuthError("Could not check your sign-in session. Please try signing in.");
        setAuthStatus("unauthenticated");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSignOut() {
    await logout();
    setAuthError(null);
    setAuthStatus("unauthenticated");
  }

  if (authStatus === "checking") {
    return (
      <main className="auth-checking" role="status">
        Checking your WasteWise AI session...
      </main>
    );
  }

  if (authStatus === "unauthenticated") {
    return (
      <Login
        initialError={authError}
        onAuthenticated={() => {
          setAuthError(null);
          setAuthStatus("authenticated");
        }}
      />
    );
  }

  return <Dashboard onSignOut={handleSignOut} />;
}

const pages = [
  { name: "Dashboard", icon: LayoutDashboard },
  { name: "Inventory Monitoring", icon: Package },
  { name: "Sales History", icon: ShoppingCart },
  { name: "Demand Forecast", icon: ChartNoAxesCombined },
  { name: "Expiry Risk", icon: AlertTriangle },
  { name: "Smart Recommendations", icon: Lightbulb },
  { name: "Model Monitoring", icon: Activity },
  { name: "Waste Reports", icon: FileBarChart },
  { name: "Project Conclusion", icon: BookOpen },
];

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  trend,
  color,
}: {
  icon: typeof Package;
  label: string;
  value: string;
  detail: string;
  trend: string;
  color: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span className={`metric-icon ${color}`}>
          <Icon size={21} />
        </span>
        <span className="metric-trend">
          <TrendingUp size={14} /> {trend}
        </span>
      </div>
      <p className="muted metric-label">{label}</p>
      <h2>{value}</h2>
      <p className="metric-detail">{detail}</p>
    </article>
  );
}

function Panel({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Dashboard({ onSignOut }: { onSignOut: () => Promise<void> }) {
  const [activePage, setActivePage] = useState("Dashboard");
  const [search, setSearch] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [monitoring, setMonitoring] = useState<MonitoringResponse | null>(null);
  const [monitoringError, setMonitoringError] = useState<string | null>(null);
  const [monitoringLoading, setMonitoringLoading] = useState(false);
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    getDashboardSummary()
      .then((data) => {
        if (!cancelled) setDashboard(data);
      })
      .catch(() => {
        if (!cancelled) {
          setDashboardError(
            "Could not load dashboard data. Check the database connection and required table schema."
          );
        }
      })
      .finally(() => {
        if (!cancelled) setDashboardLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (activePage !== "Model Monitoring") return;

    let cancelled = false;

    async function loadMonitoring() {
      setMonitoringLoading(true);
      setMonitoringError(null);

      try {
        const data = await getMonitoring();

        if (!cancelled) {
          setMonitoring(data);
        }
      } catch {
        if (!cancelled) {
          setMonitoringError(
            "Could not load monitoring data. Check the backend connection."
          );
        }
      } finally {
        if (!cancelled) {
          setMonitoringLoading(false);
        }
      }
    }

    void loadMonitoring();

    return () => {
      cancelled = true;
    };
  }, [activePage]);

  const filtered = (dashboard?.expiry_risk_queue ?? []).filter((batch) =>
    `${batch.product_name ?? batch.product_id} ${batch.category ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );
  const dashboardSourceLabel =
    dashboard?.data_source === "mysql" ? "MySQL" : "Sample CSV";

  function changePage(name: string) {
    setActivePage(name);
    setMenuOpen(false);
  }

  async function handleSignOut() {
    setSignOutError(null);
    try {
      await onSignOut();
    } catch {
      setSignOutError("Could not sign out because the server could not be reached. Please try again.");
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-icon">
            <Leaf size={25} />
          </div>
          <div>
            <h2>
              WasteWise <span>AI</span>
            </h2>
            <p>FOOD WASTE INTELLIGENCE</p>
          </div>
          <button
            className="icon-button mobile-close"
            onClick={() => setMenuOpen(false)}
            aria-label="Close menu"
          >
            <X />
          </button>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="navigation">
          {pages.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={`nav-item ${activePage === name ? "active" : ""}`}
              onClick={() => changePage(name)}
            >
              <Icon size={18} />
              <span>{name}</span>
              {name === "Expiry Risk" && dashboard?.expiry_risk_batches ? (
                <span className="nav-count">{dashboard.expiry_risk_batches}</span>
              ) : null}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="eco-card">
            <Leaf size={21} />
            <h3>Every product matters.</h3>
            <p>
              Use data to make smarter stock decisions and reduce avoidable
              food waste.
            </p>
            <div className="eco-progress">
              <span />
            </div>
            <small>Waste reduction workspace</small>
          </div>

          <div className="profile">
            <div className="avatar">WM</div>
            <div className="profile-text">
              <strong>Store Manager</strong>
              <span>Administrator</span>
            </div>
            <span className="online-dot" />
          </div>
        </div>
      </aside>

      {menuOpen && (
        <button
          className="mobile-overlay"
          onClick={() => setMenuOpen(false)}
          aria-label="Close menu"
        />
      )}

      <main className="main-content">
        {signOutError && (
          <div className="notice signout-error" role="alert">
            {signOutError}
          </div>
        )}
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
            >
              <Menu />
            </button>
            <span>WasteWise AI</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{activePage}</strong>
          </div>

          <div className="topbar-actions">
            <span className="demo-status">
              <span />
              {dashboard?.data_source === "mysql"
                ? "MYSQL DATA"
                : dashboard?.data_source === "local_csv"
                  ? "SAMPLE CSV"
                  : "CONNECTING"}
            </span>
            <button
              className="icon-button notification-button"
              aria-label="Notifications"
            >
              <Bell size={19} />
            </button>
            <div className="top-avatar">WM</div>
            <button
              className="text-button"
              onClick={() => void handleSignOut()}
              aria-label="Sign out"
            >
              <LogOut size={16} /> Sign out
            </button>
          </div>
        </header>

        <section className="page-content">
          <div className="welcome-row">
            <div>
              <div className="eyebrow">
                <span /> SMART INVENTORY · LESS FOOD WASTE
              </div>
              <h1>{activePage}</h1>
              <p className="welcome-description">
                {pageDescription(activePage)}
              </p>
            </div>
            <div className="date-chip">
              <CalendarDays size={16} /> Retail intelligence
            </div>
          </div>

          {activePage === "Dashboard" && (
            <>
              {dashboardLoading && (
                <div className="notice" role="status">
                  Loading database-backed inventory and waste summaries...
                </div>
              )}
              {dashboardError && (
                <div className="notice" role="alert">
                  <ShieldCheck size={18} />
                  <span>{dashboardError}</span>
                </div>
              )}
              {dashboard && (
                <div className="notice">
                  <ShieldCheck size={18} />
                  <span>
                    <strong>
                      {dashboard.data_source === "mysql"
                        ? "MySQL data"
                        : "Local sample CSV data"}
                    </strong>
                    {" · "}Waste data through{" "}
                    {dashboard.waste_data_through ?? "not available"}. Risk
                    counts reflect dataset labels, not model-generated alerts.
                  </span>
                </div>
              )}

              <div className="metrics-grid">
                <MetricCard
                  icon={Boxes}
                  label="Tracked Products"
                  value={dashboard?.products_tracked.toLocaleString() ?? "—"}
                  detail="Products in the configured catalog"
                  trend={dashboardLoading ? "Loading" : dashboardSourceLabel}
                  color="green"
                />
                <MetricCard
                  icon={Package}
                  label="Inventory Batches"
                  value={dashboard?.inventory_batches.toLocaleString() ?? "—"}
                  detail="Batches in the inventory snapshot"
                  trend={dashboardSourceLabel}
                  color="blue"
                />
                <MetricCard
                  icon={AlertTriangle}
                  label="Risk-labeled Batches"
                  value={dashboard?.expiry_risk_batches.toLocaleString() ?? "—"}
                  detail="Batches labeled as expiry risk in the inventory data"
                  trend="Risk labels"
                  color="orange"
                />
                <MetricCard
                  icon={Leaf}
                  label="Recorded Waste (7 days)"
                  value={dashboard?.recorded_waste_last_7_days.toLocaleString(undefined, { maximumFractionDigits: 1 }) ?? "—"}
                  detail="Units from the waste dataset; not a cost estimate"
                  trend="Recorded"
                  color="purple"
                />
              </div>

              <div className="charts-grid">
                <Panel
                  title="Recorded daily sales"
                  subtitle="Units sold recorded with the waste dataset"
                  action={<span className="small-pill">7-day view</span>}
                >
                  {dashboard?.daily_sales_last_7_days.length ? (
                    <div className="chart-area">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={dashboard.daily_sales_last_7_days}>
                        <CartesianGrid
                          stroke="#263841"
                          strokeDasharray="4 5"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="date"
                          tick={{ fill: "#8da39e", fontSize: 12 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: "#8da39e", fontSize: 12 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#12221f",
                            border: "1px solid #2b4840",
                            borderRadius: 10,
                            color: "#fff",
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="units_sold"
                          name="Units sold"
                          stroke="#60d6a2"
                          strokeWidth={2.5}
                          connectNulls
                        />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="empty-state">No daily sales records are available.</p>
                  )}
                </Panel>

                <Panel
                  title="Waste by Category"
                  subtitle="Recorded waste units over the latest 7-day window"
                >
                  {dashboard?.waste_by_category_last_7_days.length ? (
                    <div className="chart-area">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={dashboard.waste_by_category_last_7_days}
                          margin={{ top: 10, right: 8, left: -18, bottom: 0 }}
                        >
                        <CartesianGrid
                          stroke="#263841"
                          strokeDasharray="4 5"
                          vertical={false}
                        />
                        <XAxis
                          dataKey="category"
                          tick={{ fill: "#8da39e", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          tick={{ fill: "#8da39e", fontSize: 12 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#12221f",
                            border: "1px solid #2b4840",
                            borderRadius: 10,
                            color: "#fff",
                          }}
                        />
                        <Bar
                          dataKey="waste_units"
                          name="Waste units"
                          fill="#60d6a2"
                          radius={[5, 5, 0, 0]}
                        />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="empty-state">No categorized waste records are available.</p>
                  )}
                </Panel>
              </div>

              <Panel
                title="Inventory & Expiry Watch"
                subtitle="Highest-priority batches from the inventory risk labels"
                action={
                  <button
                    className="text-button"
                    onClick={() => changePage("Inventory Monitoring")}
                  >
                    View inventory <ArrowUpRight size={15} />
                  </button>
                }
              >
                <InventoryTable
                  items={filtered}
                  search={search}
                  setSearch={setSearch}
                />
              </Panel>

              <div className="bottom-grid">
                <Panel
                  title="Priority actions"
                  subtitle="Safety reminders for store operators"
                >
                  <Recommendation
                    icon={<AlertTriangle />}
                    title="Review fresh produce"
                    detail="Compare stock with expected demand and remaining shelf life."
                    tag="HIGH PRIORITY"
                    color="orange"
                  />
                  <Recommendation
                    icon={<Package />}
                    title="Check low-stock products"
                    detail="Products with demand above stock may need replenishment."
                    tag="STOCK REVIEW"
                    color="blue"
                  />
                  <Recommendation
                    icon={<Leaf />}
                    title="Plan safe markdowns"
                    detail="Consider eligible products before expiry; never sell expired or unsafe food."
                    tag="FOOD SAFETY"
                    color="green"
                  />
                </Panel>

                <Panel
                  title="How WasteWise helps"
                  subtitle="The business objective"
                >
                  <div className="objective-item">
                    <span className="objective-icon">
                      <TrendingUp />
                    </span>
                    <div>
                      <strong>Forecast demand</strong>
                      <p>
                        Use historical sales to estimate future product needs.
                      </p>
                    </div>
                  </div>
                  <div className="objective-item">
                    <span className="objective-icon">
                      <Boxes />
                    </span>
                    <div>
                      <strong>Balance inventory</strong>
                      <p>
                        Compare stock on hand against predicted demand.
                      </p>
                    </div>
                  </div>
                  <div className="objective-item">
                    <span className="objective-icon">
                      <Leaf />
                    </span>
                    <div>
                      <strong>Prevent avoidable waste</strong>
                      <p>
                        Highlight expiry risk and support timely action.
                      </p>
                    </div>
                  </div>
                </Panel>
              </div>
            </>
          )}

          {activePage === "Inventory Monitoring" && (
            <Panel
              title="Expiry-risk inventory batches"
              subtitle="Risk-labeled records returned by the configured inventory data source"
            >
              {dashboardError && <div className="notice" role="alert">{dashboardError}</div>}
              {dashboardLoading && <p role="status">Loading inventory records...</p>}
              <InventoryTable
                items={filtered}
                search={search}
                setSearch={setSearch}
              />
            </Panel>
          )}

          {activePage === "Sales History" && (
            <Panel
              title="Historical sales"
              subtitle="Recorded daily units sold in the latest available 7-day data window"
            >
              {dashboardError && <div className="notice" role="alert">{dashboardError}</div>}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>DATE</th>
                      <th>UNITS SOLD</th>
                      <th>DATA STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(dashboard?.daily_sales_last_7_days ?? []).map((day) => (
                      <tr key={day.date}>
                        <td>{day.date}</td>
                        <td>{day.units_sold?.toLocaleString() ?? "—"}</td>
                        <td>
                          <span className="status status-normal">
                            {dashboard?.data_source === "mysql" ? "Database" : "Sample CSV"}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {!dashboardLoading && !dashboard?.daily_sales_last_7_days.length && (
                      <tr><td colSpan={3} className="empty-state">No sales records are available.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {activePage === "Demand Forecast" && (
            <>
              <Panel
                title="Demand forecast availability"
                subtitle="The backend does not yet produce store-specific forward demand estimates"
              >
                <div className="notice">
                  <BrainCircuit size={19} />
                  <span>
                    A trained demand model exists, but it was evaluated on a
                    separate sample dataset and the API has no live
                    store-specific forecast endpoint. No forecast is shown
                    rather than presenting sample predictions as operational
                    advice. Connect this store&apos;s dated sales, calendar,
                    price, and promotion data to enable this view.
                  </span>
                </div>
              </Panel>
            </>
          )}

          {activePage === "Expiry Risk" && <ExpiryRisk />}

          {activePage === "Smart Recommendations" && <Recommendations />}

          {activePage === "Model Monitoring" && (
            <>
              {monitoringLoading && (
                <div className="notice">
                  Loading model monitoring data...
                </div>
              )}

              {monitoringError && (
                <div className="notice">{monitoringError}</div>
              )}

              {monitoring && (
                <>
                  <div className="metrics-grid">
                    <MetricCard
                      icon={Activity}
                      label="Model readiness"
                      value={`${Object.values(monitoring.models).filter((model) => model.ready).length}/${Object.keys(monitoring.models).length}`}
                      detail="Models reporting ready"
                      trend="Live API"
                      color="blue"
                    />

                    <MetricCard
                      icon={ChartNoAxesCombined}
                      label="Forecast MAE"
                      value={
                        monitoring.models.demand_forecast?.metadata.mae != null
                          ? Number(
                              monitoring.models.demand_forecast.metadata.mae
                            ).toFixed(3)
                          : "N/A"
                      }
                      detail="Demand forecast evaluation"
                      trend="MAE"
                      color="purple"
                    />

                    <MetricCard
                      icon={ShieldCheck}
                      label="Expiry risk ROC-AUC"
                      value={
                        monitoring.models.expiry_risk?.metadata.roc_auc != null
                          ? Number(
                              monitoring.models.expiry_risk.metadata.roc_auc
                            ).toFixed(3)
                          : "N/A"
                      }
                      detail="Expiry-risk holdout evaluation"
                      trend="ROC-AUC"
                      color="green"
                    />

                    <MetricCard
                      icon={Boxes}
                      label="Datasets"
                      value={String(monitoring.datasets.length)}
                      detail="Datasets reported by backend"
                      trend="Live API"
                      color="orange"
                    />
                  </div>

                  <Panel
                    title="Model evaluation details"
                    subtitle="Metrics reported by the backend training artifacts"
                  >
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>MODEL</th>
                            <th>STATUS</th>
                            <th>KEY METRICS</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(monitoring.models).map(
                            ([name, model]) => (
                              <tr key={name}>
                                <td>
                                  <strong>{name.replaceAll("_", " ")}</strong>
                                </td>
                                <td>
                                  <span
                                    className={`status ${model.ready ? "status-normal" : "status-high"}`}
                                  >
                                    {model.ready ? "Ready" : "Not ready"}
                                  </span>
                                </td>
                                <td>
                                  {Object.entries(model.metadata)
                                    .filter(
                                      ([key, value]) =>
                                        [
                                          "mae",
                                          "rmse",
                                          "wape",
                                          "accuracy",
                                          "f1",
                                          "roc_auc",
                                          "precision",
                                          "recall",
                                        ].includes(key) &&
                                        typeof value === "number"
                                    )
                                    .map(
                                      ([key, value]) =>
                                        `${key}: ${Number(value).toFixed(3)}`
                                    )
                                    .join(" · ") || "No evaluation metrics"}
                                </td>
                              </tr>
                            )
                          )}
                        </tbody>
                      </table>
                    </div>
                  </Panel>

                  <Panel
                    title="Dataset status"
                    subtitle="Dataset coverage reported by the backend"
                  >
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>DATASET</th>
                            <th>ROWS</th>
                            <th>START DATE</th>
                            <th>END DATE</th>
                          </tr>
                        </thead>
                        <tbody>
                          {monitoring.datasets.map((dataset) => (
                            <tr key={dataset.dataset}>
                              <td>{dataset.dataset}</td>
                              <td>{dataset.rows.toLocaleString()}</td>
                              <td>{dataset.date_range?.start ?? "N/A"}</td>
                              <td>{dataset.date_range?.end ?? "N/A"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Panel>

                  <Panel
                    title="Historical data drift"
                    subtitle="Statistical comparison between earlier and later dataset periods"
                  >
                    <div className="metrics-grid">
                      {Object.entries(monitoring.drift ?? {}).map(
                        ([name, report]) => (
                          <MetricCard
                            key={name}
                            icon={Activity}
                            label={name.replaceAll("_", " ")}
                            value={
                              report.status === "unavailable"
                                ? "Unavailable"
                                : report.status === "drift_detected"
                                  ? "Drift detected"
                                  : "Normal"
                            }
                            detail={`${report.features_with_drift ?? 0} of ${report.features_tested ?? 0} features show drift`}
                            trend="Historical"
                            color={
                              report.status === "drift_detected"
                                ? "orange"
                                : report.status === "unavailable"
                                  ? "blue"
                                  : "green"
                            }
                          />
                        )
                      )}
                    </div>

                    {Object.entries(monitoring.drift ?? {}).map(
                      ([name, report]) => (
                        <div key={name} style={{ marginTop: 24 }}>
                          <h4>{name.replaceAll("_", " ")} details</h4>

                          <p className="muted">
                            Reference period:{" "}
                            {report.reference_period?.start ?? "N/A"}
                            {" — "}
                            {report.reference_period?.end ?? "N/A"}
                          </p>

                          <p className="muted">
                            Current period:{" "}
                            {report.current_period?.start ?? "N/A"}
                            {" — "}
                            {report.current_period?.end ?? "N/A"}
                          </p>

                          {report.reason && (
                            <p className="muted">{report.reason}</p>
                          )}

                          <div className="table-wrap">
                            <table>
                              <thead>
                                <tr>
                                  <th>FEATURE</th>
                                  <th>STATUS</th>
                                  <th>REFERENCE MEAN</th>
                                  <th>CURRENT MEAN</th>
                                  <th>P-VALUE</th>
                                </tr>
                              </thead>

                              <tbody>
                                {(report.results ?? []).map((result) => (
                                  <tr key={result.feature}>
                                    <td>
                                      {result.feature.replaceAll("_", " ")}
                                    </td>
                                    <td>
                                      <span
                                        className={`status ${
                                          result.status === "drift_detected"
                                            ? "status-high"
                                            : result.status === "normal"
                                              ? "status-normal"
                                              : "status-medium"
                                        }`}
                                      >
                                        {result.status.replaceAll("_", " ")}
                                      </span>
                                    </td>
                                    <td>
                                      {result.reference_mean == null
                                        ? "N/A"
                                        : result.reference_mean.toFixed(3)}
                                    </td>
                                    <td>
                                      {result.current_mean == null
                                        ? "N/A"
                                        : result.current_mean.toFixed(3)}
                                    </td>
                                    <td>
                                      {result.p_value == null
                                        ? "N/A"
                                        : result.p_value.toExponential(3)}
                                    </td>
                                  </tr>
                                ))}

                                {!report.results?.length && (
                                  <tr>
                                    <td colSpan={5} className="empty-state">
                                      No feature-level drift results available.
                                    </td>
                                  </tr>
                                )}
                              </tbody>
                            </table>
                          </div>

                          <p className="muted">
                            Method: {report.method ?? "N/A"}
                            {" · "}
                            P-value threshold:{" "}
                            {report.p_value_threshold ?? "N/A"}
                          </p>

                          {report.note && (
                            <p className="muted">{report.note}</p>
                          )}
                        </div>
                      )
                    )}
                  </Panel>

                  <div className="notice">
                    <ShieldCheck size={18} />
                    <span>
                      These are historical statistical comparisons, not proof
                      of model degradation or live production drift.
                      Investigate detected changes before deciding whether
                      model retraining is needed.
                    </span>
                  </div>
                </>
              )}
            </>
          )}

          {activePage === "Waste Reports" && (
            <>
              <Panel
                title="Waste overview"
                subtitle="Recorded waste units by category over the latest 7-day data window"
              >
                {dashboardError && <div className="notice" role="alert">{dashboardError}</div>}
                {dashboard?.waste_by_category_last_7_days.length ? (
                  <div className="chart-area large-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dashboard.waste_by_category_last_7_days}>
                        <CartesianGrid stroke="#263841" strokeDasharray="4 5" />
                        <XAxis dataKey="category" tick={{ fill: "#8da39e" }} />
                        <YAxis tick={{ fill: "#8da39e" }} />
                        <Tooltip />
                        <Bar
                          dataKey="waste_units"
                          name="Recorded waste units"
                          fill="#60d6a2"
                          radius={[5, 5, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  !dashboardLoading && (
                    <p className="empty-state">No categorized waste records are available.</p>
                  )
                )}
              </Panel>

              <div className="notice">
                <FileBarChart size={18} />
                <span>
                  {dashboard?.data_source === "mysql"
                    ? "Waste quantities come from the connected database. Verify that records represent measured disposals before using them for operational or financial reporting."
                    : "This view uses supplied CSV sample data. It does not estimate financial impact; use measured waste and verified costs for operational reporting."}
                </span>
              </div>
            </>
          )}

          {activePage === "Project Conclusion" && (
            <div className="conclusion-grid">
              <Panel
                title="Project objective"
                subtitle="Why WasteWise AI exists"
              >
                <p className="body-copy">
                  WasteWise AI is designed to help grocery stores reduce
                  avoidable food waste by combining historical sales, inventory
                  levels, demand forecasting and expiry-risk monitoring.
                </p>
              </Panel>

              <Panel
                title="Expected business value"
                subtitle="Outcomes to measure after evaluation"
              >
                <ul className="conclusion-list">
                  <li>Fewer products expiring unsold</li>
                  <li>Better alignment between stock and demand</li>
                  <li>More informed replenishment decisions</li>
                  <li>Clearer visibility into waste quantities and cost</li>
                </ul>
              </Panel>

              <Panel
                title="Evaluation and limitations"
                subtitle="Report actual results, not assumptions"
              >
                <p className="body-copy">
                  This interface does not claim a verified forecasting score
                  or measured waste reduction. Evaluate the trained model on
                  held-out data and compare waste, stockouts and costs against
                  a baseline.
                </p>
              </Panel>

              <Panel
                title="Future scope"
                subtitle="Possible next improvements"
              >
                <ul className="conclusion-list">
                  <li>Connect live inventory and sales data</li>
                  <li>Evaluate multiple forecasting models</li>
                  <li>Add alerts and model drift monitoring</li>
                  <li>Measure impact in a real store pilot</li>
                </ul>
              </Panel>
            </div>
          )}

          <footer className="footer">
            <span>© 2026 WasteWise AI</span>
            <span>
              <Leaf size={15} /> Smarter inventory. Less food waste.
            </span>
          </footer>
        </section>
      </main>
    </div>
  );
}

function pageDescription(page: string) {
  const descriptions: Record<string, string> = {
    Dashboard:
      "A clear view of grocery stock, expected demand and food-waste risks.",
    "Inventory Monitoring":
      "Review current quantities alongside demand and shelf life.",
    "Sales History":
      "Explore the historical sales patterns used for demand planning.",
    "Demand Forecast":
      "Compare historical sales with future demand estimates.",
    "Expiry Risk":
      "Identify products that may expire before they can be sold.",
    "Smart Recommendations":
      "Turn inventory signals into practical, food-safe actions.",
    "Model Monitoring":
      "Track model quality and data health when real metrics are connected.",
    "Waste Reports":
      "Understand waste quantities and the costs associated with discarded stock.",
    "Project Conclusion":
      "Project objectives, evaluation approach, limitations and future scope.",
  };

  return descriptions[page] ?? "";
}

function InventoryTable({
  items,
  search,
  setSearch,
}: {
  items: RiskBatch[];
  search: string;
  setSearch: (value: string) => void;
}) {
  return (
    <>
      <div className="table-search">
        <Search size={16} />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search products or categories..."
        />
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>BATCH</th>
              <th>PRODUCT</th>
              <th>QUANTITY REMAINING</th>
              <th>DAYS TO EXPIRY</th>
              <th>EXPECTED DEMAND</th>
              <th>RISK LABEL</th>
            </tr>
          </thead>

          <tbody>
            {items.map((batch) => (
              <tr key={batch.batch_id}>
                <td>
                  {batch.batch_id}
                </td>
                <td>
                  <strong>{batch.product_name ?? `Product ${batch.product_id}`}</strong>
                  <span className="item-category">{batch.category ?? "Uncategorized"}</span>
                </td>
                <td>{batch.quantity_remaining.toLocaleString()}</td>
                <td>{batch.days_to_expiry ?? "N/A"}</td>
                <td>{batch.expected_demand_before_expiry?.toLocaleString() ?? "N/A"}</td>
                <td>
                  <span className="status status-warning">At risk</span>
                </td>
              </tr>
            ))}

            {!items.length && (
              <tr>
                <td colSpan={6} className="empty-state">
                  {search
                    ? "No risk-labeled batches match your search."
                    : "No risk-labeled inventory batches are available."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Recommendation({
  icon,
  title,
  detail,
  tag,
  color,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
  tag: string;
  color: string;
}) {
  return (
    <div className="recommendation">
      <span className={`recommendation-icon ${color}`}>{icon}</span>
      <div className="recommendation-body">
        <strong>{title}</strong>
        <p>{detail}</p>
        <span className={`recommendation-tag ${color}`}>{tag}</span>
      </div>
      <ChevronRight className="recommendation-arrow" size={17} />
    </div>
  );
}
