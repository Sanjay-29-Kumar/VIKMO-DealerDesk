# VIKMO DealerDesk Assignment - django
 
**Track:** `django` (Python / Django Software Developer)  
**Required Parts Implemented:**
- **Part A1 · Backend Core:** Products, Inventory, Dealers, and Draft Orders REST API
- **Part A2 · Order Engine:** Strict state machine, pessimistic row-locking to prevent overselling, exact 18% GST calculation, unique daily order sequences, and duplicate-safe idempotency
- **Part B · Supplier Sync:** Resilient catalog sync engine handling cursor pagination, HTTP 429 `Retry-After` rate-limits, transient 5xx retries, latest `updated_at` deduplication, and atomic all-or-nothing rollbacks

**Optional Parts Implemented:**
- **Part E · Frontend Dealer Portal (Bonus):** Interactive single-page dashboard for browsing catalog parts, calculating real-time line GST, submitting and tracking orders, adjusting warehouse stock, and triggering supplier sync
- **Docker Support (Bonus):** Containerized deployment (`Dockerfile`, `docker-compose.yml`) for running the application and mock supplier in isolated environments (completely optional; standard grader runs directly via Python)

**Video Walkthrough Link:** [https://youtu.be/VyirJ0hWPrc](https://youtu.be/VyirJ0hWPrc)  
**Public Repository Link:** [https://github.com/Sanjay-29-Kumar/VIKMO-DealerDesk](https://github.com/Sanjay-29-Kumar/VIKMO-DealerDesk)

---

## 1. Technology Stack

- **Language:** Python 3.11+ (Tested on Python 3.12)
- **Framework:** Django 5.2.x & Django REST Framework (DRF) 3.15+
- **Database:** PostgreSQL (Neon Cloud / Supabase or Local PostgreSQL 16)
- **Database Driver:** `psycopg[binary]>=3.1` with `dj-database-url>=2.1`
- **HTTP Client:** `requests>=2.31`
- **CORS Support:** `django-cors-headers>=4.3.0`
- **Frontend:** Vanilla HTML5, Modern ES6+ JavaScript, CSS (Custom Design System, Light/Dark theme support)
- **Containerization (Optional):** Docker & Docker Compose

---

## 2. Project Structure

```text
├── .dockerignore              # Excludes .env, .venv, git, and caches from Docker context
├── .env.example               # Template environment configuration (never commit .env)
├── .gitignore                 # Excludes local environments, caches, and secrets
├── API_CONTRACT.md            # Official evaluation specification & error contracts
├── DECISIONS.md               # Technical answers to 8 evaluation questions with code citations
├── Dockerfile                 # Docker image blueprint (Debian slim, Python 3.12, auto-migrate)
├── README.md                  # Setup, architecture, and submission guide
├── docker-compose.yml         # Optional container orchestration for Django & Mock Supplier
├── manage.py                  # Django administrative script
├── requirements.txt           # Python dependency requirements
├── smoke_test.py              # Official assignment test suite (9 validation checks)
├── core/                      # Global utilities, health endpoint, seed command, pagination
│   └── management/commands/   # Custom commands (seed_data)
├── data/                      # Assignment datasets (catalogue.csv, dealers.csv, etc.)
├── dealerdesk/                # Django project settings, WSGI, and URL routing
├── dealers/                   # Dealers app (models, views, serializers, URLs)
├── frontend/                  # Dealer portal frontend (index.html with embedded JS/CSS)
├── orders/                    # Orders engine (models, services, serializers, state flow)
├── products/                  # Product catalog & warehouse inventory adjustments
├── supplier_mock/             # Standalone HTTP mock supplier server
├── supplier_sync/             # Resilient supplier catalog synchronization engine
└── tests/                     # Concurrency, GST, idempotency, and lifecycle tests
```

---

## 3. Setup Instructions (Python & PostgreSQL)

### Step 1: Create and Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` at the repository root:
```bash
# Windows
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```
Open `.env` and set your PostgreSQL connection string:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/dealerdesk
SUPPLIER_API_URL=http://127.0.0.1:8099
SUPPLIER_API_KEY=dev-supplier-key
DJANGO_SECRET_KEY=local-dev-secret-key-2026
DJANGO_DEBUG=1
```

---

## 4. Grader-Compatible Run Commands

The submission adheres strictly to the exact grader startup sequence:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run database migrations
python manage.py migrate --noinput

# 3. Seed data (runs safely twice to verify complete idempotency)
python manage.py seed_data
python manage.py seed_data

# 4. Start the Django application
python manage.py runserver 0.0.0.0:8000 --noreload
```

- **Health Check Endpoint:** [http://localhost:8000/api/health/](http://localhost:8000/api/health/) &rarr; `{"status": "ok"}`
- **DealerDesk Portal UI:** [http://localhost:8000/](http://localhost:8000/) or [http://localhost:8000/portal/](http://localhost:8000/portal/)

---

## 5. Running the Tests

### A. Run the Official Smoke Test Suite
1. In a separate terminal, launch the mock supplier API:
   ```bash
   python supplier_mock/mock_supplier.py
   ```
2. In your primary terminal, execute the official smoke test:
   ```bash
   python smoke_test.py --base-url http://localhost:8000 --track django
   ```
   **Result:** `9/9 checks passed.`

### B. Run the Automated Django Test Suite
Execute the multi-threaded concurrency, GST rounding, idempotency, and status lifecycle test suite:
```bash
python manage.py test tests --keepdb
```
**Result:** `Ran 11 tests in 1.4s ... OK`

---

## 6. Docker Instructions (Optional)

Docker is completely optional. If Docker Desktop is available on your machine:

```bash
# Build the Docker image
docker build -t dealerdesk:latest .

# Run application using Docker Compose (Django + Supplier Mock)
docker compose up -d --build

# View container logs
docker compose logs -f

# Stop containers
docker compose down
```

---

## 7. API Endpoints Reference

All endpoints conform to [`API_CONTRACT.md`](API_CONTRACT.md):

| Method | Endpoint | Description | Error Codes |
|:---|:---|:---|:---|
| `GET` | `/api/health/` | Service health probe | — |
| `GET` | `/api/products/` | Paginated catalog (`page`, `search`, `category`, `vehicle`) | — |
| `POST`| `/api/products/` | Create catalog item with stock 0 | `409 DUPLICATE` |
| `GET` | `/api/products/{sku}/` | Fetch single product by SKU | `404 NOT_FOUND` |
| `PATCH`| `/api/products/{sku}/` | Partial update (SKU is immutable) | `404 NOT_FOUND` |
| `PUT` | `/api/inventory/{sku}/` | Manual stock count correction with audit reason | `400 VALIDATION_ERROR` |
| `GET` | `/api/dealers/` | Paginated list of authorized dealers | — |
| `POST`| `/api/dealers/` | Register new dealer | `409 DUPLICATE` |
| `GET` | `/api/dealers/{id}/` | Dealer detail record | `404 NOT_FOUND` |
| `POST`| `/api/orders/` | Create DRAFT order (`Idempotency-Key` header supported) | `409 IDEMPOTENCY_CONFLICT` |
| `GET` | `/api/orders/` | List orders (filterable by `dealer_id`, `status`) | — |
| `GET` | `/api/orders/{order_number}/` | Order details with exact per-line GST breakdown | `404 NOT_FOUND` |
| `PUT` | `/api/orders/{order_number}/` | Replace items for DRAFT order | `409 ORDER_LOCKED` |
| `POST`| `/api/orders/{order_number}/confirm/` | Confirm order (pessimistic lock, all-or-nothing stock deduction) | `409 INSUFFICIENT_STOCK` |
| `POST`| `/api/orders/{order_number}/dispatch/`| Transition status from CONFIRMED to DISPATCHED | `409 INVALID_TRANSITION` |
| `POST`| `/api/orders/{order_number}/deliver/` | Transition status from DISPATCHED to DELIVERED | `409 INVALID_TRANSITION` |
| `POST`| `/api/orders/{order_number}/cancel/`  | Cancel order (restores stock exactly once if CONFIRMED) | `409 INVALID_TRANSITION` |
| `POST`| `/api/sync/supplier/` | Fetch supplier catalog with cursor pagination & atomic DB update | `502 SUPPLIER_UNAVAILABLE` |

---

## 8. Assumptions & Known Limitations

1. **PostgreSQL Required:** Concurrency guarantees (`SELECT ... FOR UPDATE`) require PostgreSQL. SQLite is explicitly blocked in settings because it does not support row-level pessimistic write locking.
2. **Untrusted Supplier Feed:** Supplier names, vehicle fitments, and descriptions are sanitized at ingestion time.
3. **Synchronous Supplier Sync:** For the 600-item catalog, sync executes well within the 120-second contract limit. In high-scale production (50,000+ items), this would be migrated to Celery background workers.
4. **Questions & Architecture Decisions:** Detailed architectural justifications with line-number code citations are documented in [`DECISIONS.md`](DECISIONS.md).
