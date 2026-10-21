# 🌿 WasteWise AI — Smart Waste Management System

### Smart Inventory Insights • Expiry-Risk Monitoring • AI/ML Decision Support

WasteWise AI is a full-stack web application prototype designed to help grocery businesses explore inventory data, monitor expiry risks, understand recorded food waste, and investigate data-driven inventory decisions.

By combining **Machine Learning, Python, FastAPI, React, and MySQL**, this project demonstrates how AI/ML can be integrated into a practical inventory-management workflow.

> 🚀 **Project goal:** Explore how data-driven insights can help businesses identify inventory risks and make more informed decisions about food waste.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 📊 **Interactive Dashboard** | Explore inventory summaries and available business insights. |
| 📦 **Product & Inventory Management** | Browse product records and inventory snapshots. |
| ⏳ **Expiry-Risk Monitoring** | Review model-generated risk estimates for recorded inventory. |
| 📈 **Demand Forecasting** | Explore daily demand predictions using compatible benchmark data. |
| 🧾 **Sales History** | Review recorded daily sales summaries. |
| ♻️ **Waste Reports** | Analyze waste information from available inventory data. |
| 🏷️ **Smart Discount Scenarios** | Explore prototype discount recommendations using simulated scenarios. |
| 🔍 **Model Monitoring** | Access available model-monitoring information. |
| 🔐 **Secure API Access** | Protect business endpoints with browser-session authentication or an API key. |

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend logic and ML workflows |
| Pandas | Data processing and analysis |
| scikit-learn | Machine Learning pipelines and predictions |
| FastAPI | REST API development |
| React | Frontend user interface |
| TypeScript | Frontend type safety |
| Vite | Frontend development and production builds |
| MySQL | Relational database support |
| SQLAlchemy | Database integration |
| Docker Compose | Containerized deployment |

---

## 🏗️ System Architecture

```text
                ┌────────────────────────┐
                │      React + Vite      │
                │     User Interface     │
                └───────────┬────────────┘
                            │
                            ▼
                ┌────────────────────────┐
                │       FastAPI          │
                │   REST API & Security  │
                └───────────┬────────────┘
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
        ┌────────────────┐    ┌────────────────┐
        │  MySQL / CSV   │    │ ML Model       │
        │  Data Sources  │    │ Artifacts      │
        └────────────────┘    └────────────────┘
```

The frontend communicates with the FastAPI backend. Depending on the configuration, the backend can read supported data from MySQL or local CSV files and load saved Machine Learning artifacts for prediction endpoints.

---

## 🚀 Getting Started

### 1. Prerequisites

Install the following tools:

- Python
- Node.js and npm
- Git
- MySQL or Docker with Docker Compose (optional, depending on your setup)

### 2. Clone the repository

```bash
git clone https://github.com/gokulswain1212-web/WasteWise-AI-Smart-Waste-Management-System.git
cd WasteWise-AI-Smart-Waste-Management-System
```

To access the latest changes on the development branch:

```bash
git checkout audit/submission-readiness
```

### 3. Install Python dependencies

Run these commands from the project root:

```bash
python -m pip install -r requirements.txt
python -m pip install -r backend/requirements.txt
python -m pip install -r ml/requirements.txt
```

### 4. Configure environment variables

For a local setup, create your private environment files:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
```

Edit the files and configure the required values for your environment.

- Set the database connection details correctly.
- Use strong, unique application secrets.
- Configure authentication using `AUTH_EMAIL` and `AUTH_PASSWORD_HASH`.
- Never commit real passwords, API keys, or private `.env` files.

### 5. Start the backend

From the project root:

```bash
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Check the API:

- Health endpoint: `http://127.0.0.1:8000/health`
- Interactive API documentation: `http://127.0.0.1:8000/docs`

Keep the backend terminal running.

### 6. Start the frontend

Open a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the local URL printed in your terminal, usually:

`http://127.0.0.1:5173`

The frontend development proxy normally sends API requests to the backend on port `8000`.

### 7. Optional: Start MySQL with Docker

After configuring the project-root `.env` and `backend/.env`, run:

```bash
docker compose --profile mysql up -d mysql
```

Configure the database connection to match your MySQL username, password, and database name.

**Important:** Review the importer and database configuration before importing data. Do not use development import scripts against an important database without a backup.

---

## 🤖 Machine Learning

The project includes model workflows for:

- **Demand forecasting** — daily predictions based on compatible sales, calendar, price, and related benchmark features.
- **Expiry-risk estimation** — model-generated risk estimates using recorded inventory snapshots.
- **Food-waste prediction** — predictions using available historical data and engineered features.
- **Discount scenario analysis** — prototype recommendations based on simulated discount scenarios.

### Train the models

If you have obtained the required datasets and intend to regenerate the model artifacts, run:

```bash
python ml/src/train_all_models.py
```

Training requires the compatible M5 sales, calendar, and sell-price datasets, along with the project's inventory, perishable-inventory, and simulated discount-scenario CSV files in `ml/data/raw/`.

The repository does not automatically download these datasets. Obtain them from an authorized source and keep raw datasets out of Git.

> **Model compatibility:** The project expects scikit-learn 1.9.1 for its saved model artifacts. A fresh clone also needs compatible model artifacts from an approved source before model-backed prediction endpoints can run.

---

## 🔌 Main API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API health status |
| GET | `/api/v1/database/status` | Database readiness information |
| GET | `/api/v1/dashboard` | Dashboard summaries |
| GET | `/api/v1/products` | Product catalog |
| GET | `/api/v1/inventory` | Inventory snapshots |
| GET | `/api/v1/sales-history` | Recorded sales summaries |
| GET | `/api/v1/waste-report` | Waste summaries |
| GET | `/api/v1/monitoring` | Model-monitoring information |
| GET | `/api/v1/predictions/food-waste` | Food-waste predictions |
| GET | `/api/v1/predictions/demand-forecast?horizon_days=7` | Demand forecast |
| GET | `/api/v1/predictions/expiry-risk?min_probability=0.5` | Expiry-risk estimates |
| GET | `/api/v1/recommendations/discounts` | Discount recommendations |

Protected business endpoints require authentication. See the interactive API documentation at `http://127.0.0.1:8000/docs` when the backend is running.

---

## 🧪 Run Tests

### Backend tests

From the `backend/` directory:

```bash
python -m pytest tests -v
```

### Frontend production build

From the `frontend/` directory:

```bash
npm run build
```

These commands help verify backend behavior and frontend compilation. Database-dependent tests may require the appropriate local configuration.

---

## ⚠️ Important Project Limitations

WasteWise AI is a **prototype for learning, experimentation, and decision support**. Some capabilities are not yet connected to live store operations.

- **Demand forecasting:** The saved forecast model uses a deterministic 70-series M5 benchmark sample. It does not currently forecast demand for the configured MySQL store.
- **Expiry-risk estimates:** Predictions are based on recorded inventory snapshots, not verified live inventory.
- **Discount recommendations:** These use simulated scenarios and do not prove real customer price response or guarantee financial savings.
- **Food safety:** Expired stock and stock expiring on the snapshot date must not be sold or discounted. Always verify actual stock, expiry dates, and food-safety requirements.
- **Read-only functionality:** Product editing, stock transactions, and sales entry are not implemented. Sales History summarizes recorded inventory data rather than a complete transaction ledger.
- **Database safety:** The application does not automatically migrate or overwrite existing databases. Review import scripts and back up important data before use.
- **Data and model availability:** Raw datasets and large model artifacts are excluded from Git. Compatible files must be provided locally for the corresponding model-backed features.

Machine Learning outputs should support human review, not replace inventory verification or food-safety procedures.

---

## 🔐 Security Best Practices

- Keep real `.env` files out of GitHub.
- Never expose database passwords, API keys, or secret keys.
- Use strong, unique credentials.
- Set `DEBUG=false` in production.
- Use a least-privilege database account.
- Configure HTTPS before exposing the application publicly.

---

## 🎯 What This Project Demonstrates

WasteWise AI brings several practical development areas together:

- Full-stack application development
- REST API design with FastAPI
- Data processing and feature engineering
- Machine Learning inference
- Relational database integration
- Authentication and configuration management
- Automated testing and deployment preparation
- Responsible communication of model limitations

## 🌱 Future Improvements

Potential next steps include:

- Connecting forecasting to store-specific sales data.
- Adding product editing and stock transaction workflows.
- Improving model evaluation with additional relevant data.
- Adding scheduled alerts for inventory nearing expiry.
- Expanding deployment and automated testing.
- Improving model monitoring and operational reporting.

---

## 👨‍💻 Project

**WasteWise AI — Smart Waste Management System**

Built as a practical AI/ML and full-stack development project to explore data-driven inventory insights and food-waste decision support.

⭐ If you find this project interesting, feel free to explore the code and share feedback or suggestions.

**GitHub:** [gokulswain1212-web](https://github.com/gokulswain1212-web)
