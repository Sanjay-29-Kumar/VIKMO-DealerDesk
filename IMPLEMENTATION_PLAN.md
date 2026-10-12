# VIKMO DealerDesk — 10-Hour Implementation Plan (Django Track + Frontend)

**Track:** Python / Django Software Developer (`--track django`)  
**Target Completion:** Under 10 Hours  
**Deliverables:**
1. Core Backend (Products, Inventory, Dealers, DRAFT Orders) — Part A1
2. Order Engine (Concurrency Locks, All-or-Nothing Stock, Exact GST, Daily Sequences, Idempotency) — Part A2
3. Supplier Sync Engine (Cursor Pagination, 429/5xx Retries, Deduplication, Atomic Rollback) — Part B
4. Interactive Dealer Portal Frontend (Catalogue, Cart, Order Management, Sync & Inventory Tools) — Part E (Bonus)
5. Comprehensive Test Suite & Smoke Test Verification (`smoke_test.py --track django`)
6. Documentation (`DECISIONS.md` with 8 code-cited answers, `README.md`, Video Walkthrough Script)

---

## 1. File & Module Architecture

### 1.1 Given Files Analysis
| Path | Description & Role |
|---|---|
| `API_CONTRACT.md` | **The Source of Truth**: Defines exact URLs (with trailing slashes), HTTP methods, status codes, payload shapes, standard error schema (`error.code`, `error.message`, `error.details`), rounding rules (`ROUND_HALF_UP`), and safety stock formulas. |
| `smoke_test.py` | Automated validation test checking health, products, dealers, inventory, draft orders, order lifecycle, stock reduction/restoration, and supplier sync. |
| `data/catalogue.csv` | 600 catalogue products with initial stock, prices, categories, and untrusted supplier descriptions. |
| `data/dealers.csv` | 25 authorized South India dealers with credit limits, GSTINs, and contact details. |
| `data/DATA_README.md` | Data specifications and warning that supplier descriptions are untrusted text. |
| `data/lead_times.csv`, `sales_history.csv`, `promo_calendar.csv`, `festival_calendar.csv` | Forecasting datasets (primarily AI/ML track). |
| `supplier_mock/mock_supplier.py` | Standalone mock supplier server simulating cursor pagination, rate limits (HTTP 429 + `Retry-After`), transient 5xx errors, and `--outage` modes. |
| `starter/` | Starter Django project layout (`settings.py`, `manage.py`, `requirements.txt`, `.env.example`). Must be copied to repo root. |

---

### 1.2 Target Directory & Module Structure
The grading bot requires `manage.py` and `requirements.txt` to reside at the **repository root**.

```
VIKMO DealerDesk Assignment/
├── API_CONTRACT.md
├── DECISIONS.md                  # Mandatory answers to the 8 Django track questions
├── README.md                     # Setup, architecture, test guide & video link
├── IMPLEMENTATION_PLAN.md        # This roadmap file
├── manage.py                     # Repo root (copied from starter)
├── requirements.txt              # Dependencies (Django, DRF, psycopg, requests, etc.)
├── .env.example                  # Committed template
├── .env                          # Local secrets (never committed)
├── smoke_test.py                 # Smoke test runner
├── data/                         # CSV datasets (unchanged)
├── supplier_mock/                # Local mock supplier server
├── dealerdesk/                   # Django project configuration
│   ├── __init__.py
│   ├── settings.py               # Configured for PostgreSQL, timezone, CORS, DRF
│   ├── urls.py                   # Central routing
│   └── wsgi.py
├── core/                         # Shared utilities & Seed command
│   ├── exceptions.py             # Custom API exceptions & standard error handler
│   ├── pagination.py             # Standard pagination (count, next, previous, results)
│   ├── views.py                  # Health check GET /api/health/
│   ├── urls.py
│   └── management/commands/
│       └── seed_data.py          # Idempotent CSV seeding for catalogue & dealers
├── products/                     # Part A1: Products & Inventory
│   ├── models.py                 # Product, InventoryLog
│   ├── serializers.py
│   ├── views.py                  # ProductViewSet, InventoryView
│   └── urls.py
├── dealers/                      # Part A1: Dealer Management
│   ├── models.py                 # Dealer
│   ├── serializers.py
│   ├── views.py                  # DealerViewSet
│   └── urls.py
├── orders/                       # Part A2: Order Engine & Concurrency
│   ├── models.py                 # Order, OrderItem, DailyOrderSequence, IdempotencyRecord
│   ├── serializers.py            # OrderSerializer, OrderItemSerializer, OrderCreateSerializer
│   ├── services.py               # Atomic order confirmation, stock locking, GST calculation, sequence gen
│   ├── views.py                  # OrderViewSet, OrderActionViews
│   └── urls.py
├── supplier_sync/                # Part B: Supplier Integration
│   ├── client.py                 # HTTP client with cursor pagination, 429 Retry-After & 5xx retries
│   ├── services.py               # Deduplication, validation, atomic sync apply, rollback
│   ├── views.py                  # SupplierSyncView (POST /api/sync/supplier/)
│   └── urls.py
├── tests/                        # Comprehensive automated test suite
│   ├── test_concurrency.py       # Multi-threaded simultaneous order confirm test
│   ├── test_gst_rounding.py      # Paisa-level exact GST ROUND_HALF_UP tests
│   ├── test_idempotency.py       # Duplicate header & body mismatch tests
│   ├── test_supplier_sync.py     # Retry, rollback on 502, and duplicate SKU resolution
│   └── test_status_transitions.py# State machine invalid transition checks
└── frontend/                     # Part E: Dealer Portal (Modern SPA)
    ├── index.html
    ├── src/
    │   ├── api.js                # API client with error handling
    │   ├── styles.css            # Premium dark/light design system
    │   └── app.js                # Catalogue, Cart, Orders & Sync views
    └── package.json
```

---

## 2. Tech Stack

- **Language:** Python 3.11+
- **Framework:** Django 4.2+ / Django REST Framework (DRF)
- **Database:** PostgreSQL (Strict requirement; handles row-level `FOR UPDATE` locking and transactional DDL)
- **Database Adapter:** `psycopg[binary]>=3.1` with `dj-database-url>=2.1`
- **Environment Management:** `python-dotenv`
- **HTTP Client:** `requests>=2.31`
- **Frontend Stack:** Modern Vanilla JS + CSS (or React + Vite), consuming `/api/` endpoints directly with CORS support.

---

## 3. Hour-by-Hour 10-Hour Roadmap

```
+---------------------------------------------------------------------------------+
|                                10-HOUR SCHEDULE                                 |
+---------+-------------------------------------------------------------+---------+
| Hour 1  | Root Setup, Postgres Configuration & Base App Setup         |  60 min |
| Hour 2  | Relational Schema Design & Idempotent Seeding (`seed_data`)  |  60 min |
| Hour 3  | Part A1: Products, Inventory, Dealers & Custom Error Handler|  60 min |
| Hour 4  | Part A2: Order Creation, Exact GST & Idempotent Generation  |  60 min |
| Hour 5  | Part A2: Concurrency Lock, All-or-Nothing Stock & Transitions| 60 min |
| Hour 6  | Part B: Supplier Sync Engine (Cursor, 429/5xx, Rollback)    |  60 min |
| Hour 7  | Smoke Test Run & Concurrency / Unit Test Suite              |  60 min |
| Hour 8  | Part E: Dealer Portal Frontend (Catalogue, Cart, Orders)     |  90 min |
| Hour 9  | DECISIONS.md (8 Questions) & Documentation                  |  45 min |
| Hour 10 | Clean Clone Audit, Verification & Video Walkthrough Prep    |  45 min |
+---------+-------------------------------------------------------------+---------+
```

---

## 4. Detailed Step-by-Step Implementation

### Step 1: Root Layout & Environment Setup (Hour 1)
1. Copy all contents of `starter/` directly into the repository root:
   - `manage.py`, `requirements.txt`, `.env.example`, `.gitignore`, `dealerdesk/`, `core/`.
2. Configure `.env`:
   - Set `DATABASE_URL=postgres://postgres:postgres@localhost:5432/dealerdesk` (or Neon DB URL).
   - Set `SUPPLIER_API_URL=http://127.0.0.1:8099`, `SUPPLIER_API_KEY=dev-supplier-key`.
3. Configure `dealerdesk/settings.py`:
   - Add `corsheaders` (if needed for frontend) or configure static files.
   - Register apps: `'core'`, `'products'`, `'dealers'`, `'orders'`, `'supplier_sync'`.
   - Setup Custom DRF Exception Handler: `REST_FRAMEWORK['EXCEPTION_HANDLER'] = 'core.exceptions.custom_exception_handler'`.
   - Setup Standard Pagination: `REST_FRAMEWORK['DEFAULT_PAGINATION_CLASS'] = 'core.pagination.StandardPagination'`.

---

### Step 2: Database Schema & Idempotent Seeding (Hour 2)
1. **Schema Design**:
   - `Product`:
     - `sku`: `CharField(max_length=64, primary_key=True)`
     - `name`: `CharField(max_length=255)`
     - `category`: `CharField(max_length=100, db_index=True)`
     - `brand`: `CharField(max_length=100, db_index=True)`
     - `vehicle_fitment`: `CharField(max_length=255, db_index=True)`
     - `price`: `DecimalField(max_digits=12, decimal_places=2)`
     - `stock`: `IntegerField(default=0)`
     - `description`: `TextField(blank=True)`
     - `updated_at`: `DateTimeField(auto_now=True)`
   - `InventoryLog`:
     - `product`: `ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_logs')`
     - `quantity_before`: `IntegerField()`
     - `quantity_after`: `IntegerField()`
     - `reason`: `CharField(max_length=255)`
     - `created_at`: `DateTimeField(auto_now_add=True)`
   - `Dealer`:
     - `id`: `BigAutoField(primary_key=True)`
     - `dealer_code`: `CharField(max_length=32, unique=True, db_index=True)`
     - `name`: `CharField(max_length=255)`
     - `city`: `CharField(max_length=100, blank=True)`
     - `phone`: `CharField(max_length=50, blank=True)`
     - `email`: `EmailField(blank=True)`
     - `gstin`: `CharField(max_length=30, blank=True)`
     - `credit_limit`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
   - `DailyOrderSequence`:
     - `date`: `DateField(unique=True)`
     - `last_sequence`: `PositiveIntegerField(default=0)`
   - `IdempotencyRecord`:
     - `key`: `CharField(max_length=128, unique=True)`
     - `request_hash`: `CharField(max_length=64)`
     - `status_code`: `IntegerField()`
     - `response_body`: `JSONField()`
     - `created_at`: `DateTimeField(auto_now_add=True)`
   - `Order`:
     - `order_number`: `CharField(max_length=32, unique=True, primary_key=True)`
     - `dealer`: `ForeignKey(Dealer, on_delete=models.PROTECT, related_name='orders')`
     - `status`: `CharField(max_length=20, default='DRAFT', choices=ORDER_STATUS_CHOICES)`
     - `subtotal`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
     - `tax_total`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
     - `grand_total`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
     - `created_at`: `DateTimeField(auto_now_add=True)`
     - `updated_at`: `DateTimeField(auto_now=True)`
   - `OrderItem`:
     - `id`: `BigAutoField(primary_key=True)`
     - `order`: `ForeignKey(Order, on_delete=models.CASCADE, related_name='items')`
     - `product`: `ForeignKey(Product, on_delete=models.PROTECT)`
     - `sku`: `CharField(max_length=64)`
     - `name`: `CharField(max_length=255)`
     - `quantity`: `PositiveIntegerField()`
     - `unit_price`: `DecimalField(max_digits=12, decimal_places=2)`
     - `line_subtotal`: `DecimalField(max_digits=14, decimal_places=2)`
     - `line_tax`: `DecimalField(max_digits=14, decimal_places=2)`
     - `line_total`: `DecimalField(max_digits=14, decimal_places=2)`

2. **Idempotent `seed_data` Implementation**:
   - Reads `catalogue.csv` and `dealers.csv`.
   - Uses `Product.objects.update_or_create(...)` or `bulk_create(..., update_conflicts=True)`.
   - Ensures running `python manage.py seed_data` twice produces exactly 600 products and 25 dealers with zero duplication.

---

### Step 3: Part A1 — Core REST APIs & Error Formatting (Hour 3)
1. **Standard Error Shape**:
   ```python
   # core/exceptions.py
   def custom_exception_handler(exc, context):
       # Maps validation errors, 404s, 409s, 502s to:
       # {"error": {"code": "...", "message": "...", "details": [...]}}
   ```
2. **Products Endpoints**:
   - `GET /api/products/`: Filters: `search` (case-insensitive across `sku`, `name`, `brand`), `category` (exact), `vehicle` (icontains in `vehicle_fitment`).
   - `POST /api/products/`: Validates positive price with max 2 decimals. Creates with stock 0. Duplicate SKU returns `409 DUPLICATE`.
   - `GET /api/products/{sku}/`: Returns single product or `404 NOT_FOUND`.
   - `PATCH /api/products/{sku}/`: Partial update, immutable `sku`.
3. **Inventory Endpoint**:
   - `PUT /api/inventory/{sku}/`: Sets quantity to exact integer >= 0, creates `InventoryLog`, returns `200 {"sku": "...", "quantity": N}`.
4. **Dealers Endpoints**:
   - `GET /api/dealers/`: Paginated dealer list.
   - `POST /api/dealers/`: Validates `dealer_code` and `name`. Duplicate `dealer_code` returns `409 DUPLICATE`.
   - `GET /api/dealers/{id}/`: Single dealer detail or `404 NOT_FOUND`.

---

### Step 4: Part A2 — Order Creation, Exact GST & Idempotency (Hour 4)
1. **GST Calculation Engine**:
   - Use Python's `decimal.Decimal` with `ROUND_HALF_UP`:
     ```python
     ROUND_HALF_UP = decimal.ROUND_HALF_UP
     TWO_PLACES = Decimal('0.01')
     
     line_subtotal = (unit_price * quantity).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
     line_tax = (line_subtotal * Decimal('0.18')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
     line_total = line_subtotal + line_tax
     ```
   - Tax is computed and rounded per line, then summed for total tax.
   - All money fields serialized as 2-decimal strings: `f"{val:.2f}"`.
2. **Order Number Generation**:
   - Timezone: `Asia/Kolkata`. Format: `ORD-YYYYMMDD-NNNN`.
   - Thread-safe / multi-process safe sequence generation using `DailyOrderSequence.objects.select_for_update()` inside `transaction.atomic()`.
3. **Draft Order Creation (`POST /api/orders/`)**:
   - Validation: at least one item, quantity >= 1, valid existing SKUs, valid dealer, no duplicate SKUs within items list.
   - Line prices snapshot product's current catalogue price.
4. **Idempotency Engine**:
   - Reads `Idempotency-Key` header.
   - Computes SHA-256 hash of JSON payload.
   - If key exists with matching hash: return original cached order response.
   - If key exists with different hash: raise `409 IDEMPOTENCY_CONFLICT`.
   - If new key: save `IdempotencyRecord` atomically with order creation.

---

### Step 5: Part A2 — Concurrency Locks, All-or-Nothing Stock & Transitions (Hour 5)
1. **State Machine (`orders/services.py`)**:
   - Allowed transitions:
     - `DRAFT` -> `CONFIRMED`
     - `DRAFT` -> `CANCELLED`
     - `DRAFT` -> edit items (`PUT /api/orders/{order_number}/`)
     - `CONFIRMED` -> `DISPATCHED`
     - `CONFIRMED` -> `CANCELLED` (restores stock)
     - `DISPATCHED` -> `DELIVERED`
     - Any other transition -> `409 INVALID_TRANSITION`
     - Attempting to edit non-DRAFT order -> `409 ORDER_LOCKED`
2. **Atomic Order Confirmation (`POST /api/orders/{order_number}/confirm/`)**:
   - Wrap in `transaction.atomic()`.
   - Lock product rows in alphabetical SKU order to prevent deadlocks:
     ```python
     products = Product.objects.select_for_update().filter(sku__in=item_skus).order_by('sku')
     ```
   - Check stock for all items:
     - If ANY item is short: Collect all short items into `details` (`{"sku": "...", "requested": X, "available": Y}`) and format descriptive `message`. Raise `409 INSUFFICIENT_STOCK`.
   - If all available: Deduct stock using `F('stock') - item.quantity` and lock order prices.
3. **Safe Cancellation (`POST /api/orders/{order_number}/cancel/`)**:
   - If status was `CONFIRMED`, atomically restore stock using `F('stock') + item.quantity` under row locks.
   - State transition guarantees stock is restored **exactly once**.

---

### Step 6: Part B — Supplier Sync Engine (Hour 6)
1. **HTTP Client (`supplier_sync/client.py`)**:
   - Uses `requests.Session()`.
   - Fetches `GET {SUPPLIER_API_URL}/v1/products?cursor=<cursor>&limit=20`.
   - On `429`: Reads `Retry-After` header, sleeps for specified duration, retries (up to 5 attempts).
   - On `5xx` / Connection error: Exponential backoff (`2 ** attempt * 0.5`), retries (up to 5 attempts).
   - Follows `next_cursor` until `null`.
2. **All-or-Nothing Guarantee**:
   - If any page fails after 5 retries or 401 occurs: Return `502 SUPPLIER_UNAVAILABLE`. Do not touch database!
3. **Feed Processing (`supplier_sync/services.py`)**:
   - **Invalid items**: Discard items missing `sku` or with non-positive / bad decimal prices, record in `rejected: [{"supplier_sku": "...", "reason": "..."}]`.
   - **Deduplication**: Keep the item with the latest `updated_at` timestamp.
   - **Database Apply**: Inside `transaction.atomic()`:
     - Compare fields: `name`, `category`, `brand`, `vehicle_fitment`, `description`, `price`.
     - Non-existing SKU -> Create with `stock = 0` (`created += 1`).
     - Existing SKU with changed fields -> Update (`updated += 1`).
     - Existing SKU with identical fields -> (`unchanged += 1`).
     - **NEVER** modify existing `stock`.

---

### Step 7: Testing & Verification (Hour 7)
1. **Smoke Test Execution**:
   - Run local mock supplier: `python supplier_mock/mock_supplier.py`.
   - Run Django server: `python manage.py runserver 0.0.0.0:8000`.
   - Execute: `python smoke_test.py --base-url http://localhost:8000 --track django`.
   - All tests must pass (Health, Products, Dealers, Inventory, Draft Orders, Lifecycle, Supplier Sync).
2. **Automated Unit & Concurrency Tests**:
   - Write tests simulating concurrent confirmations on the last stock item using `ThreadPoolExecutor` to prove zero overselling.
   - Test GST rounding precision against known edge cases.
   - Test idempotency replay vs conflict.
   - Test supplier sync outage behavior returning 502 without database mutation.

---

### Step 8: Part E — Modern Dealer Portal Frontend (Hour 8)
Build a responsive, modern Web UI connecting to the Django API:
1. **Catalogue View**:
   - Real-time search by SKU, name, or brand.
   - Filter by Category and Vehicle Fitment.
   - Live stock indicator badge (In Stock, Low Stock, Out of Stock).
   - Add-to-cart controls.
2. **Cart & Draft Order**:
   - Cart quantity adjustment.
   - Live price and 18% GST preview.
   - Dealer selector (switch between the 25 dealers).
   - "Create Draft Order" button calling `POST /api/orders/`.
3. **Order Management & Detail Drawer**:
   - List recent orders with status badges (`DRAFT`, `CONFIRMED`, `DISPATCHED`, `DELIVERED`, `CANCELLED`).
   - Line items breakdown with unit price, line tax, and grand total.
   - Action buttons with instant feedback: Confirm (shows clear stock shortage errors), Dispatch, Deliver, Cancel, Edit.
4. **Warehouse Tools & Supplier Sync**:
   - Manual Inventory Adjuster (`PUT /api/inventory/{sku}/`).
   - One-click "Sync Supplier Catalogue" button displaying live stats (`created`, `updated`, `unchanged`, `rejected`).

---

### Step 9: Documentation & DECISIONS.md (Hour 9)
Complete `DECISIONS.md` answering the 8 mandatory Django track questions with exact file and line citations:
1. **Overselling prevention:** `orders/services.py` line references showing `select_for_update()`, sorted SKU locking, and race condition explanation.
2. **GST calculation & rounding:** `orders/services.py` line references for `ROUND_HALF_UP` per-line vs order totals and IEEE 754 float drift risks.
3. **Unique order numbers & idempotency:** `orders/services.py` line references for `DailyOrderSequence` atomic locking and SHA-256 idempotency cache.
4. **Schema & `on_delete` rationale:** Models explanation (`PROTECT` on Dealer/Product to preserve historical financial integrity, `CASCADE` on OrderItem).
5. **Status transitions & single stock restoration:** State machine table and atomic flag verification.
6. **Supplier sync retries, limits & all-or-nothing rollback:** `supplier_sync/client.py` and `services.py` retry loops and atomic abort.
7. **Sync classification (created/updated/unchanged) & idempotency:** Field-by-field equality checks and zero mutations on second pass.
8. **Weakest part & next steps:** Candid self-assessment (e.g., distributed task queue like Celery for async sync, connection pooling with PgBouncer).

---

### Step 10: Final Run Contract Audit & Video Walkthrough Script (Hour 10)
1. Verify clean clone commands:
   ```bash
   pip install -r requirements.txt
   python manage.py migrate --noinput
   python manage.py seed_data
   python manage.py seed_data
   python manage.py runserver 0.0.0.0:8000 --noreload
   ```
2. Verify smoke test passes cleanly:
   ```bash
   python smoke_test.py --base-url http://localhost:8000 --track django
   ```
3. Prepare 5-Minute Video Walkthrough Script:
   - Walk through the order confirmation flow from HTTP request -> DRF view -> transaction boundary -> `select_for_update()` lock -> stock deduction -> response.

---

## 5. Scoring Breakdown for Django Track
- **Backend Core & Order Engine:** 40 Points
- **Supplier Sync:** 15 Points
- **Code Quality & Tests:** 20 Points
- **DECISIONS.md:** 15 Points
- **Video Walkthrough:** 10 Points
- **Part E (Frontend Portal):** Up to 5-10 Bonus Points
- **Target Score:** 100/100 + Bonus Points
