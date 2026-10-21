# WasteWise AI — Smart Waste Management System

# WasteWise AI — Grocery Food Waste Management

WasteWise AI is a React application for inventory expiry-risk monitoring,
recorded sales and waste reporting, model monitoring, and prototype discount
scenario analysis. A FastAPI service provides authentication, health,
dashboard, and prediction endpoints.

## Install

From the project root:

    python -m pip install -r requirements.txt
    python -m pip install -r ml/requirements.txt
    python -m pip install -r backend/requirements.txt

## Train the tabular models

    python ml/src/train_all_models.py

The trained model artifacts, metadata, holdout metrics, and discount
recommendation examples are saved in `artifacts/`. Demand forecasting uses a
chronological holdout with calendar, lag, price, and promotion features. The
expiry-risk target and food-waste target are excluded from their respective
model inputs. Food-waste prediction features are taken from the prior day.

Discount scenarios are simulated; their model is a prototype, not evidence of
real customer price response. Regression quality is reported using MAE, RMSE,
and WAPE rather than classification accuracy.

## Run the backend API

### Start MySQL with Docker Compose

Create local environment files (keep your real passwords out of Git):

    Copy-Item .env.example .env
    Copy-Item backend/.env.example backend/.env

Set `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` to different strong passwords in
the project `.env`. In `backend/.env`, set `DATABASE_URL` to use the same
`MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`, with `127.0.0.1` as host.
URL-encode special characters in the username or password.

Start the database from the project root:

    docker compose --profile mysql up -d mysql

### Import the supplied datasets into MySQL

From the project root:

    python -m pip install -r backend/requirements.txt
    python backend/import_data.py

The importer creates tables from `database/schema.sql` only when none of the
project schema tables exist, then appends the supplied CSV rows. It stops
without writing if any project schema table already exists; it has no
replace/drop/truncate mode. The simulated discount-scenarios CSV is not
imported because no reviewed table definition for it exists in the SQL schema.

### Start the API

Start from the project root in a separate terminal:

    python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

Check `http://127.0.0.1:8000/health` or open the interactive API docs at
`http://127.0.0.1:8000/docs`.
The health response shows whether MySQL is configured and reachable. The
`/api/v1/database/status` endpoint also lists imported tables. If MySQL is not
configured, the API continues to use the supplied local CSV files.

## Run the React frontend locally

Start the FastAPI backend as described above, then, from a second terminal:

    cd frontend
    npm ci
    npm run dev

Open the Vite URL printed in the terminal (normally `http://127.0.0.1:5173`).
The Vite development proxy sends API requests to `http://127.0.0.1:8000`.
Set `WASTEWISE_API_URL` before `npm run dev` if the API runs elsewhere.

The login account is configured only by `AUTH_EMAIL` and
`AUTH_PASSWORD_HASH` in the private `backend/.env`; there is no default
password. Use a unique, strong password and change any password that has been
shared in chat or otherwise exposed. Generate a PBKDF2 password hash without
putting a plaintext password in source code. Set `DEBUG=false`, a strong
random `API_KEY` and `SECRET_KEY`, and a private `DATABASE_URL` for production.
Do not commit either `.env` file.

## Production deployment with Docker Compose

Docker and the Compose plugin must be installed on the deployment server. Copy
`backend/.env.example` to `backend/.env` and configure all production values
privately. `DEBUG=false`, `DATABASE_URL`, `API_KEY`, `SECRET_KEY`, `AUTH_EMAIL`,
and `AUTH_PASSWORD_HASH` are required by the production API. Keep the API
internal to Compose; only the frontend is published on the configured
`WASTEWISE_HTTP_PORT` (default `8080`).

The API connects to the MySQL database specified by `DATABASE_URL`. Use your
existing MySQL host and a dedicated, least-privilege application user. The
database must contain the following compatible tables and columns:

- `products`: `product_id`, `product_name`, `category`
- `inventory_batches`: `batch_id`, `product_id`, `category`, `received_at`,
  `snapshot_date`, `initial_quantity`, `quantity_remaining`, `days_to_expiry`,
  `avg_daily_sales_7d`, `expected_demand_before_expiry`, `unit_price`,
  `unit_cost`, `discount_pct`, `expiry_risk_label`
- `perishable_inventory`: `product_id`, `date`, `category`, `opening_stock`,
  `units_received`, `units_sold`, `unit_price`, `discount_pct`, `days_to_expiry`,
  `temperature_c`, `stockout_flag`, `waste_units`
- `discount_recommendations`: `batch_id`, `product_id`, `days_to_expiry`,
  `quantity_remaining`, `predicted_gross_margin`

Check the schema/readiness without exposing credentials at
`/api/v1/database/status` (requires sign-in). An incompatible database should
be corrected by its administrator; the application does not migrate or
overwrite an existing database automatically. The CSV import script is for
the supplied datasets and must not be used to replace a production database
without an explicit backup and approval.

Build and launch from the project root:

    docker compose up --build -d

For the optional bundled MySQL service, create a root `.env` from
`.env.example`, set distinct strong `MYSQL_PASSWORD` and
`MYSQL_ROOT_PASSWORD` values, then use:

    docker compose --profile mysql up --build -d

For that profile, set `DATABASE_URL` in `backend/.env` to use `mysql` as the
host and ensure its database/user/password match the root `.env`. Do not enable
the bundled database when using your existing external database.

The frontend container serves HTTP only. Put it behind a trusted reverse proxy
or load balancer configured for HTTPS before exposing it publicly; production
session cookies are Secure and require HTTPS. Configure the proxy to forward
HTTPS requests to the frontend container. Back up the database and keep
secrets in private deployment configuration, not in Git.

## Data and model limitations

The dashboard identifies whether values come from MySQL or the supplied local
CSV sample. A live store-specific demand forecast is not available: the
existing demand model was evaluated on a separate sample dataset and is not
wired to a live forecast endpoint. Discount recommendations are simulated
prototype scenarios, not validated customer-price predictions. Verify
inventory, expiry, and food safety before acting on model outputs. The
application does not claim live customer response or financial savings.

Available API endpoints include:

- `GET /health`
- `GET /api/v1/dashboard`
- `GET /api/v1/monitoring`
- `GET /api/v1/predictions/food-waste`
- `GET /api/v1/predictions/expiry-risk?min_probability=0.5`
- `GET /api/v1/recommendations/discounts`
