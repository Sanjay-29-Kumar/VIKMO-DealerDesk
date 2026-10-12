# VIKMO DealerDesk — Automotive Parts Distribution & Ordering OS

**Track:** `django` (Python / Django Software Developer)  
**Optional Parts Attempted:** Part E — Frontend Dealer Portal (Bonus)  
**Video Walkthrough Link:** [https://youtu.be/placeholder-demo-link](https://youtu.be/placeholder-demo-link) *(Replace with your unlisted YouTube, Loom, or Google Drive link)*

---

## 1. Overview & Architecture

VIKMO DealerDesk is a high-reliability commerce backend and dealer portal built for an automotive spare parts distributor supplying 25 independent dealers across South India from a 600-product catalogue.

### Key Architectural Guarantees:
- **Pessimistic Concurrency Control:** Prevents overselling of stock using PostgreSQL row-level locks (`select_for_update()`) ordered by SKU (eliminating deadlocks) under high concurrent load.
- **Paisa-Level Financial Precision:** Exact 18% GST calculation per line item using Python's `decimal.Decimal` with strict `ROUND_HALF_UP` rounding.
- **Atomic Daily Sequence Numbering:** Unique `ORD-YYYYMMDD-NNNN` order numbers generated in `Asia/Kolkata` timezone with transactional sequence locking.
- **Duplicate-Safe Idempotency:** SHA-256 payload hashing and atomic key reservations for `Idempotency-Key` headers.
- **Resilient Supplier Sync:** Fault-tolerant integration with the supplier catalogue API supporting cursor pagination, HTTP 429 `Retry-After` backoff, transient 5xx retries, latest `updated_at` deduplication, and atomic rollback on failures.
- **Interactive Dealer Portal (Part E Bonus):** A modern, responsive single-page web dashboard with live search, real-time stock pills, cart GST preview, order lifecycle management, warehouse inventory adjustment, and supplier sync monitoring.

---

## 2. Tech Stack

- **Language:** Python 3.11+
- **Backend Framework:** Django 5.x / 4.2+ & Django REST Framework (DRF)
- **Database:** PostgreSQL (Cloud Neon / Supabase or Local)
- **Database Driver:** `psycopg[binary]>=3.1` with `dj-database-url`
- **HTTP Client:** `requests>=2.31`
- **Frontend Stack:** Vanilla Modern JavaScript (ES6+), HTML5, Custom Glassmorphism CSS Design System
- **Testing:** `smoke_test.py`, Django Test Runner (`tests/`)

---

## 3. Getting Started

### Prerequisites
- Python 3.11 or newer
- PostgreSQL database connection URL (e.g. Neon, Supabase, or local PostgreSQL)

### 1. Clone & Set Up Virtual Environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the repository root (based on `.env.example`):
```env
DATABASE_URL=postgresql://user:password@host:5432/dealerdesk?sslmode=require
SUPPLIER_API_URL=http://127.0.0.1:8099
SUPPLIER_API_KEY=dev-supplier-key
DJANGO_SECRET_KEY=your-dev-secret-key
DJANGO_DEBUG=1
```

### 4. Run Migrations & Seed Data
```bash
python manage.py migrate --noinput
python manage.py seed_data
```
*(The `seed_data` command is completely idempotent and safe to execute multiple times without duplicate records).*

### 5. Start Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```

- **Health Check:** `http://localhost:8000/api/health/` &rarr; `{"status": "ok"}`
- **Interactive Dealer Portal:** `http://localhost:8000/` or `http://localhost:8000/portal/`

### 6. Or Run with Docker Compose (All-in-One)
To run the Django app, local PostgreSQL 16 database, and supplier mock service together in isolated Docker containers:
```bash
docker compose up --build
```
This automatically runs migrations, seeds 600 catalogue parts and 25 dealers, starts the mock supplier on port 8099, and serves the DealerDesk portal on `http://localhost:8000`.

---

## 4. Running the Tests

### 1. Run the Smoke Test Suite
In one terminal, start the local mock supplier:
```bash
python supplier_mock/mock_supplier.py
```

In a second terminal, execute the official smoke test:
```bash
python smoke_test.py --base-url http://localhost:8000 --track django
```
**Expected Output:** `9/9 checks passed.`

### 2. Run Comprehensive Unit & Concurrency Tests
Run the automated test suite covering multi-threaded concurrency, GST rounding, idempotency, and status transitions:
```bash
python manage.py test tests --keepdb
```
**Expected Output:** `Ran 11 tests ... OK`

---

## 5. Endpoints Reference (Conforms to API_CONTRACT.md)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health/` | Service health status check |
| `GET` | `/api/products/` | Paginated product catalogue with `search`, `category`, and `vehicle` filters |
| `POST` | `/api/products/` | Create new product with stock 0 (rejects duplicate SKU with `409 DUPLICATE`) |
| `GET` | `/api/products/{sku}/` | Single product detail |
| `PATCH`| `/api/products/{sku}/` | Partial update (SKU immutable) |
| `PUT` | `/api/inventory/{sku}/`| Warehouse stock count correction with audit reason |
| `GET` | `/api/dealers/` | Paginated list of 25 authorized dealers |
| `POST` | `/api/dealers/` | Create dealer (rejects duplicate code with `409 DUPLICATE`) |
| `GET` | `/api/dealers/{id}/` | Dealer details |
| `POST` | `/api/orders/` | Create DRAFT order (supports `Idempotency-Key` header) |
| `GET` | `/api/orders/` | Paginated orders list with `dealer_id` and `status` filters |
| `GET` | `/api/orders/{order_number}/` | Order details with line-by-line GST breakdown |
| `PUT` | `/api/orders/{order_number}/` | Replace items for DRAFT orders (rejects with `409 ORDER_LOCKED` otherwise) |
| `POST` | `/api/orders/{order_number}/confirm/` | DRAFT &rarr; CONFIRMED (pessimistic row-level lock, all-or-nothing stock deduction, price lock) |
| `POST` | `/api/orders/{order_number}/dispatch/`| CONFIRMED &rarr; DISPATCHED |
| `POST` | `/api/orders/{order_number}/deliver/` | DISPATCHED &rarr; DELIVERED |
| `POST` | `/api/orders/{order_number}/cancel/`  | Cancels DRAFT or CONFIRMED order (restores stock exactly once) |
| `POST` | `/api/sync/supplier/` | Automated supplier catalogue sync with cursor pagination & retries |

---

## 6. Assumptions & Engineering Decisions

1. **PostgreSQL as Source of Truth:** Pessimistic row locking (`SELECT ... FOR UPDATE`) is used rather than optimistic locking because high-contention spikes on the last available stock units require strict serialization to guarantee zero overselling.
2. **Untrusted Supplier Data:** Descriptions, fitment strings, and categories received from supplier feeds are treated as untrusted data and sanitized during JSON ingestion.
3. **Idempotency Lifetime:** Idempotency keys are persisted in the database, allowing duplicate detection across distributed processes.
4. **DECISIONS.md:** Refer to [`DECISIONS.md`](DECISIONS.md) for detailed, code-cited explanations answering all eight evaluation questions.
