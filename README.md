# AI-Inventory-System


## ✨ Highlights

* **Forecasting:** Probabilistic demand forecasts (daily/weekly) per SKU/location with confidence intervals.
* **Vision:** Optional camera/phone-based **image capture** for shelf counts via object detection + OCR (UPC/QR).
* **Replenishment:** Smart reorder points & purchase order suggestions based on lead time and service levels.
* **Anomalies:** Automatic stockout/overstock detection, shrinkage alerts, and outlier sales cleanup.
* **Ops Copilot:** Natural‑language Q&A over inventory, creating POs, and explaining forecasts.
* **APIs & UI:** REST + WebSocket APIs, Admin dashboard, and webhook integrations.
* **Batteries included:** AuthN/Z, migrations, seeding, background jobs, metrics, tracing, and tests.



---

## 🏗 Architecture

```
[Clients]
  ├─ Web Admin (React/Next.js)
  ├─ Mobile (Expo/React Native)
  └─ Integrations (Webhooks)

[API Gateway]
  └─ FastAPI (Python) / NestJS (Node)  ← REST + WS
      ├─ Auth Service (JWT/OAuth2)
      ├─ Inventory Service
      ├─ Orders/PO Service
      ├─ Forecast Service (ML)
      └─ Vision Service (CV)

[Async]
  ├─ Task Queue (Celery/RQ/BullMQ)
  └─ Message Bus (Redis/Kafka)

[Data]
  ├─ PostgreSQL (OLTP)
  └─ Object Store (S3/MinIO)


```

* **Scales down** to a single `docker-compose` for local dev.
* **Scales up** to Kubernetes with horizontal autoscaling.

---

## 🧰 Tech Stack

* **Backend:** Python 3.11, FastAPI, SQLModel/SQLAlchemy, Pydantic
* **Workers:** Celery + Redis (scheduling, ETL, training, notifications)
* **Forecasting:** Prophet / ARIMA / LightGBM (hierarchical reconciliation via MinT)
* **Vision:** Tesseract/EasyOCR for OCR
* **DB/Storage:** PostgreSQL.
* **Auth:** OAuth2+OIDC (Auth0/Keycloak) or local JWT
* **Frontend:** Next.js 14 (App Router), Tailwind, TanStack Query, shadcn/ui
* **Infra:** Docker, docker‑compose, Make, GitHub Actions, Helm/ArgoCD


---

## 📁 Repository Layout

```
AI-Inventory-System/
├─ apps/
│  ├─ api/                # FastAPI app (routers, schemas, services)
│  ├─ worker/             # Celery worker tasks (ETL, training, alerts)
│  └─ web/                # Next.js admin dashboard
├─ packages/
│  ├─ ml/                 # Forecasting & feature pipelines
│  └─ vision/             # Detection models & inference server
├─ infra/
│  ├─ docker/             # Dockerfiles
│  ├─ compose/            # docker-compose.yml
│  └─ k8s/                # Helm charts & manifests
├─ migrations/            # Alembic migrations
├─ seeds/                 # Example data
├─ .env.example
├─ Makefile
├─ pyproject.toml
└─ README.md
```

---

## 🚀 Quickstart

### 1) Prerequisites

* Docker 24+
* Docker Compose v2
* Make (optional but recommended)

### 2) Clone & Configure

```bash
git clone https://github.com/<your-org>/AI-Inventory-System.git
cd AI-Inventory-System
cp .env.example .env
# edit .env as needed
```

### 3) One‑liner (Docker Compose)

```bash
make up
# or
docker compose -f infra/compose/docker-compose.yml up -d --build
```

> API: [http://localhost:8000](http://localhost:8000)  •  Docs: [http://localhost:8000/docs](http://localhost:8000/docs)  •  Web: [http://localhost:3000](http://localhost:3000)

### 4) Seed Data (optional)

```bash
make seed
# or
python scripts/seed.py
```

### 5) Run Tests

```bash
make test
# or
pytest -q
```

---

## ⚙️ Configuration

Environment variables (copy from `.env.example`):

```ini
# core
APP_ENV=dev
SECRET_KEY=change-me

# database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=inventory
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# redis / queue
REDIS_URL=redis://redis:6379/0

# object storage
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=ai-inventory

# auth
OAUTH_ISSUER=
OAUTH_CLIENT_ID=
OAUTH_CLIENT_SECRET=
JWT_EXPIRES_IN=3600

# forecasting
FORECAST_FREQ=D
FORECAST_HORIZON=28
SERVICE_LEVEL=0.95

```

> For production, set unique secrets, enable HTTPS, and use managed Postgres/S3.

---

## 📊 Data & Modeling

### Entities

* **Product (SKU)**, **Location**, **InventoryLevel**, **Transaction** (receipts, sales, adjustments), **PurchaseOrder**, **Supplier**.

### Forecasting Pipeline

1. Ingest sales & calendar/price features
2. Clean outliers, impute missing days, reconcile hierarchies (SKU→Category→Location)
3. Fit base models (Prophet/ARIMA/LightGBM)
4. Blend & calibrate quantiles (P10/P50/P90)
5. Emit forecasts → `forecasts` table & parquet snapshots

**Safety stock** `SS = z * σ_LT` and **ROP** `ROP = μ_LT + SS` where lead‑time parameters come from supplier SLAs.

### Vision Pipeline (optional)

* Upload image via UI or API → detect SKUs → tally counts → suggest adjustments if variance > threshold.

---

## 📚 API Reference

Base URL: `http://localhost:8000`

### Auth

* `POST /auth/login` – Email/Password → JWT
* `GET /auth/me` – Current user

### Inventory

* `GET /inventory` – List items (filters: `sku`, `location_id`, `in_stock`)
* `GET /inventory/{id}` – Get item
* `POST /inventory` – Create/adjust levels
* `POST /inventory/reconcile` – Bulk recount upload (CSV/images)

### Orders

* `GET /orders` – List POs
* `POST /orders` – Create purchase order (auto‑suggest from forecasts)
* `PATCH /orders/{id}` – Update status

### Forecasts

* `GET /forecasts?sku=&location_id=&horizon=` – Quantile forecasts
* `POST /forecasts/retrain` – Trigger model retrain (async)

### Webhooks

* `POST /webhooks/sales` – Ingest sales
* `POST /webhooks/erp` – Sync products/locations

> Explore interactive docs at **`/docs`** (Swagger) and **`/redoc`**.

---

## 🧵 Background Jobs

* **Nightly retraining:** refresh models if accuracy drops
* **PO suggestions:** generate vendor‑grouped reorders
* **Anomaly alerts:** shrinkage/stockout alerts to Slack/Email
* **ETL:** import CSVs from S3, normalize, and load

Schedule examples (Celery beat):

```yaml
beat_schedule:
  retrain_daily: { task: ml.retrain_all, schedule: "0 2 * * *" }
  suggest_pos:   { task: ops.generate_pos, schedule: "0 6 * * 1-6" }
```




---

## ☁️ Deployment

### Docker Compose (prod‑like)

```bash
docker compose -f infra/compose/docker-compose.yml --env-file .env up -d
```

### Kubernetes (Helm)

```bash
helm upgrade --install ai-inventory infra/k8s/chart \
  --set image.tag=$(git rev-parse --short HEAD) \
  --values infra/k8s/values.prod.yaml
```

### Database Migrations

```bash
alembic upgrade head
```



---

## 🤝 Contributing

1. Fork the repo & create a feature branch
2. Run tests & linters: `make ci`
3. Open a PR with a clear description and screenshots

Please read `CODE_OF_CONDUCT.md` and `CONTRIBUTING.md`.

---



## 🙌 Acknowledgements

* Inspired by best practices from retail ops & MLOps communities

