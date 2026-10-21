import { useState, type FormEvent } from "react";
import axios from "axios";
import {
  AlertTriangle,
  ArrowRight,
  BadgePercent,
  ChartNoAxesCombined,
  Eye,
  EyeOff,
  Leaf,
  LockKeyhole,
  Mail,
  Recycle,
} from "lucide-react";
import "./login.css";
import { login } from "../services/auth";

type LoginProps = {
  initialError?: string | null;
  onAuthenticated: () => void;
};

const features = [
  {
    icon: ChartNoAxesCombined,
    title: "Demand Forecasting",
    description: "Predict future demand with AI-powered accuracy.",
    color: "forecast",
  },
  {
    icon: AlertTriangle,
    title: "Expiry Risk Prediction",
    description: "Identify products at risk before it's too late.",
    color: "expiry",
  },
  {
    icon: BadgePercent,
    title: "Smart Recommendations",
    description: "Get practical discount suggestions for your inventory.",
    color: "recommendations",
  },
  {
    icon: Recycle,
    title: "Waste Reduction",
    description: "Less waste, lower costs, and a healthier planet.",
    color: "reduction",
  },
];

export default function Login({
  initialError,
  onAuthenticated,
}: LoginProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState(initialError ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthError("");
    setIsSubmitting(true);
    const formData = new FormData(event.currentTarget);

    try {
      await login(
        String(formData.get("email") ?? ""),
        String(formData.get("password") ?? "")
      );
      onAuthenticated();
    } catch (error: unknown) {
      if (axios.isAxiosError<{ detail?: string }>(error)) {
        setAuthError(
          error.response?.data?.detail ??
            "Could not sign in. Check the backend connection and try again."
        );
      } else {
        setAuthError("An unexpected error occurred. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-intro" aria-labelledby="login-brand">
        <div className="login-intro-inner">
          <header className="login-brand">
            <span className="login-brand-mark" aria-hidden="true">
              <Leaf size={34} />
            </span>
            <div>
              <h1 id="login-brand">
                WasteWise <span>AI</span>
              </h1>
              <p>Smarter Decisions. Less Food Waste. A Greener Tomorrow.</p>
            </div>
          </header>

          <div className="login-hero">
            <div className="login-copy">
              <p className="login-eyebrow">
                <Leaf size={15} /> SUSTAINABLE FOOD MANAGEMENT
              </p>
              <h2>
                AI-powered
                <br />
                food waste
                <br />
                management
              </h2>
              <p className="login-description">
                Make better inventory decisions with predictive insights that
                reduce food waste and support your business.
              </p>

              <ul className="login-features">
                {features.map(({ icon: Icon, title, description, color }) => (
                  <li key={title}>
                    <span className={`login-feature-icon ${color}`}>
                      <Icon size={19} />
                    </span>
                    <span>
                      <strong>{title}</strong>
                      <small>{description}</small>
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="login-illustration" aria-hidden="true">
              <div className="forecast-card">
                <div className="forecast-heading">
                  <strong>Demand forecast</strong>
                  <span>Waste reduced <b>−32%</b></span>
                </div>
                <div className="forecast-chart">
                  <span className="chart-gridline" />
                  <span className="chart-gridline" />
                  <span className="chart-gridline" />
                  <svg viewBox="0 0 340 120" preserveAspectRatio="none">
                    <path d="M0 104 L48 83 L92 90 L138 56 L184 63 L230 36 L273 43 L340 5" />
                    <path
                      className="forecast-fill"
                      d="M0 104 L48 83 L92 90 L138 56 L184 63 L230 36 L273 43 L340 5 L340 120 L0 120 Z"
                    />
                  </svg>
                </div>
                <div className="forecast-statuses">
                  <span><i className="status-warning" /> Expiry risk <b>Low</b></span>
                  <span><i className="status-discount" /> Smart discount <b>20%</b></span>
                </div>
              </div>
              <div className="produce-card">
                <div className="produce-leaves">♧</div>
                <div className="produce-items" aria-hidden="true">
                  <span>🥬</span><span>🍅</span><span>🥕</span><span>🫑</span>
                </div>
                <div className="produce-crate">
                  <Recycle size={45} />
                </div>
              </div>
              <p className="illustration-caption">Better food. Better future.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-panel-decoration login-decoration-top" />
        <div className="login-panel-decoration login-decoration-bottom" />
        <div className="login-form-wrap">
          <span className="login-panel-leaf" aria-hidden="true">
            <Leaf size={32} />
          </span>
          <h2 id="login-title">Welcome Back</h2>
          <p className="login-subtitle">
            Sign in to continue to WasteWise AI and manage your food inventory
            smarter.
          </p>

          <form className="login-form" onSubmit={handleSubmit}>
            <label className="login-input-wrap">
              <Mail size={21} aria-hidden="true" />
              <span className="visually-hidden">Email address</span>
              <input
                type="email"
                name="email"
                placeholder="Email address"
                autoComplete="username"
                required
              />
            </label>
            <label className="login-input-wrap">
              <LockKeyhole size={21} aria-hidden="true" />
              <span className="visually-hidden">Password</span>
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                placeholder="Password"
                autoComplete="current-password"
                required
              />
              <button
                className="password-toggle"
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <Eye size={19} /> : <EyeOff size={19} />}
              </button>
            </label>
            {authError && (
              <p className="login-error" role="alert">
                {authError}
              </p>
            )}
            <button className="login-submit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Sign In"}
              {!isSubmitting && <ArrowRight size={22} />}
            </button>
          </form>

          <p className="login-footer">
            <span />
            Small changes make a big difference
            <span />
          </p>
        </div>
      </section>
    </main>
  );
}