# VIKMO DealerDesk — Engineering Decisions (Django Track)

This document answers the eight mandatory evaluation questions for the Python / Django track, citing exact files and line numbers.

---

### 1. Where exactly is overselling prevented? Cite the code and explain what would happen without it when two confirmations arrive together.

**Code Citations:**  
- `orders/services.py:261` (`confirm_order` wrapped in `@transaction.atomic`)  
- `orders/services.py:282-283` (Pessimistic row locking on products sorted by SKU)  
- `orders/services.py:285-303` (All-or-nothing stock sufficiency verification)  
- `orders/services.py:305-308` (Atomic stock deduction)

**Explanation:**  
When an order confirmation request arrives, `confirm_order` executes inside an atomic database transaction. Products involved are fetched using:
```python
skus = sorted([it.sku for it in items])
locked_products = {p.sku: p for p in Product.objects.select_for_update().filter(sku__in=skus).order_by("sku")}
```
In PostgreSQL, `select_for_update()` issues a row-level write lock (`SELECT ... FOR UPDATE`). 

**What would happen without it:**  
If two dealers attempt to confirm orders for the last 10 units of an item simultaneously, standard ORM reads without row locking would cause a classic race condition: both concurrent transactions would read `stock == 10`, evaluate `10 >= 10` as true, and decrement stock. Stock would drop to `-10` (or 0 with double promises), overselling goods and disappointing one dealer.  
With row-level locking, the second transaction is blocked until the first transaction commits its deduction. When the second transaction acquires the row lock, it reads the updated `stock == 0`, fails the stock check, and receives a `409 INSUFFICIENT_STOCK` error with full shortfall details. Sorting by `sku` is strictly required to prevent database deadlocks when concurrent transactions order the same items in different sequences.

---

### 2. How do you calculate and round GST? What would go wrong with floats or Decimal's default rounding?

**Code Citation:**  
- `orders/services.py:25-35` (`calculate_line_item`)

**Implementation:**  
Financial calculations use Python's `decimal.Decimal` with explicit `ROUND_HALF_UP` rounding to 2 decimal places:
```python
subtotal = (unit_price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
tax = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
total = subtotal + tax
```
Order-level totals are the exact sums of the per-line amounts:
`subtotal = Σ line_subtotal`, `tax_total = Σ line_tax`, `grand_total = subtotal + tax_total`.

**What would go wrong with floats:**  
Binary floating-point numbers (IEEE 754) cannot represent base-10 fractions exactly. For example, `1459.50 * 0.18` yields `262.71000000000004`. Over orders with multiple items, accumulated float imprecision drifts order totals by several paise, failing accounting reconciliations, GSTIN audits, and exact string contract requirements.

**What would go wrong with Decimal's default rounding:**  
Python's `Decimal` context defaults to `ROUND_HALF_EVEN` (Banker's rounding), which rounds half-way values to the nearest *even* digit (e.g., `0.025` rounds to `0.02`, while `0.015` rounds to `0.02`). Indian tax laws and the contract mandate `ROUND_HALF_UP`, where `.005` strictly rounds upwards to `.01` regardless of parity. Furthermore, rounding tax on the aggregate order total instead of per-line produces paise mismatches between line item totals and grand totals.

---

### 3. How do you guarantee unique order numbers and idempotent order creation when duplicate requests arrive at the same moment?

**Code Citations:**  
- `orders/services.py:38-55` (`generate_order_number`)  
- `orders/services.py:57-61` (`hash_payload`)  
- `orders/services.py:73-86, 169-176` (Idempotency enforcement in `create_draft_order`)

**Unique Order Numbers:**  
Dates are evaluated in the `Asia/Kolkata` timezone (`zoneinfo.ZoneInfo("Asia/Kolkata")`). Daily sequences are maintained via the `DailyOrderSequence` table. Inside `transaction.atomic()`, we call `DailyOrderSequence.objects.select_for_update().get_or_create(date=today)`. Simultaneous requests are serialized at the database lock, incrementing `last_sequence` monotonically without gaps or collisions to format `ORD-YYYYMMDD-NNNN`.

**Idempotent Order Creation:**  
When an `Idempotency-Key` header is supplied, the JSON payload is canonicalized and hashed using SHA-256 (`hashlib.sha256`). We query `IdempotencyRecord` with `select_for_update()`. If the key exists:
- If the stored hash matches the current hash: the previously created order is returned (`HTTP 200/201`) without creating duplicate records.
- If the hash differs: an `IdempotencyConflictException` is raised (`HTTP 409 IDEMPOTENCY_CONFLICT`).  
If the key does not exist, the order is created and the key and hash are recorded atomically within the same transaction.

---

### 4. Explain your schema: each model, its relationships and the `on_delete` choice for every foreign key, with reasons.

**Code Citations:**  
- `products/models.py:5-30` (`Product`, `InventoryLog`)  
- `dealers/models.py:5-20` (`Dealer`)  
- `orders/models.py:12-48` (`Order`, `OrderItem`, `DailyOrderSequence`, `IdempotencyRecord`)

**Schema & Relationships:**
1. **`Product`**: Primary key `sku` (string), category, brand, vehicle fitment, price (`DecimalField`), available stock (`IntegerField`), and supplier description.
2. **`InventoryLog`**: Audit trail for manual warehouse stock adjustments.  
   - `product` &rarr; `ForeignKey(Product, on_delete=models.CASCADE)`: If a product is purged, its auxiliary audit log can be removed.
3. **`Dealer`**: Stores authorized distributor accounts, GSTIN, and credit limits.
4. **`Order`**: Primary key `order_number`, status enum, and calculated money amounts (`subtotal`, `tax_total`, `grand_total`).  
   - `dealer` &rarr; `ForeignKey(Dealer, on_delete=models.PROTECT)`: **`PROTECT` is essential**. A dealer record with historical transactions must never be deleted, preserving financial records, tax liability, and contract history.
5. **`OrderItem`**: Line items for orders.  
   - `order` &rarr; `ForeignKey(Order, on_delete=models.CASCADE)`: Order items have no independent identity outside their parent order; deleting an order cascades to its items.  
   - `product` &rarr; `ForeignKey(Product, on_delete=models.PROTECT)`: **`PROTECT` is essential**. Prevents deleting products referenced in order lines. Order items also snapshot `sku`, `name`, and `unit_price` at order creation time to protect against future price changes.
6. **`DailyOrderSequence`**: `(date, last_sequence)` ensuring gapless unique daily sequence numbering.
7. **`IdempotencyRecord`**: `(key, request_hash, status_code, order_number)` ensuring replay safety.

---

### 5. Where are status transitions enforced, and how do you guarantee a cancellation restores stock exactly once?

**Code Citations:**  
- `orders/services.py:274-276` (Confirm status guard)  
- `orders/services.py:323-325` (Dispatch status guard)  
- `orders/services.py:339-341` (Deliver status guard)  
- `orders/services.py:358-375` (Cancel status guard & atomic stock restoration)

**Status Enforcement:**  
Status transitions are strictly validated in `OrderService` within atomic transactions:
- `DRAFT` &rarr; `CONFIRMED` or `CANCELLED` (or edited via PUT)
- `CONFIRMED` &rarr; `DISPATCHED` or `CANCELLED`
- `DISPATCHED` &rarr; `DELIVERED`
- Any illegal transition raises `InvalidTransitionException` &rarr; `409 INVALID_TRANSITION`.
- Modifying items on non-DRAFT orders raises `OrderLockedException` &rarr; `409 ORDER_LOCKED`.

**Single Restoration Guarantee:**  
In `cancel_order`, the order row is locked with `select_for_update()`. Stock is restored **only if** `order.status == OrderStatus.CONFIRMED`. The items are locked, product stocks incremented by line quantities, and `order.status` is updated to `CANCELLED`. If a second cancellation request arrives, the status is now `CANCELLED`, which fails the transition check and raises `409 INVALID_TRANSITION` without executing stock restoration a second time.

---

### 6. How does your supplier sync handle rate limits, failures and duplicates? How do you guarantee it changes nothing when the feed cannot be fully fetched?

**Code Citations:**  
- `supplier_sync/client.py:23-88` (`SupplierClient.fetch_all_products`)  
- `supplier_sync/services.py:20-53` (`SupplierSyncService.run_sync`)

**Handling:**  
- **Rate Limits (429):** On HTTP 429, `SupplierClient` parses the `Retry-After` header (defaulting to 1 second if omitted), pauses execution (`time.sleep`), and retries the exact page.
- **Failures (5xx & Network):** Transient errors (500, 502, 503, 504) or connection drops use exponential backoff (`0.5 * 2^(attempt - 1)`). Each page is permitted at most 5 attempts.
- **Duplicates Across Pages:** All items are fetched into memory. `valid_items_by_sku` deduplicates identical SKUs by comparing parsed `updated_at` timestamps, retaining only the entry with the latest timestamp.
- **All-or-Nothing Guarantee:** `SupplierClient` buffers the entire catalogue across all pages into memory **before touching the database**. If any page fails after 5 retries or returns a 401, a `SupplierUnavailableException` is raised immediately. No database transaction is ever opened, guaranteeing that partial feeds alter zero records and returning `502 SUPPLIER_UNAVAILABLE`.

---

### 7. How does the sync decide between created, updated and unchanged, and why does a second run change nothing?

**Code Citation:**  
- `supplier_sync/services.py:73-138` (Catalogue reconciliation)

**Decision Logic:**  
1. **Validation:** Items missing `sku` or with non-positive/non-decimal prices are appended to `rejected` and excluded from DB processing.
2. **Comparison:** In `transaction.atomic()`, existing database products matching valid feed SKUs are indexed into a dictionary.
   - **`created`:** If the SKU does not exist in our catalogue, it is inserted with **`stock = 0`** (never touching our warehouse stock).
   - **`updated`:** If the SKU exists, we check field equality: `existing.name != name or existing.category != category or existing.brand != brand or existing.vehicle_fitment != vehicle_fitment or existing.description != description or existing.price != parsed_price`. If any field differs, those specific fields are updated while preserving `stock`.
   - **`unchanged`:** If the SKU exists and all catalogue attributes match, the record is skipped.

**Why a second run changes nothing:**  
On a subsequent run against an unchanged feed, all valid SKUs already exist in the database with identical attributes. Therefore, `created == 0`, `updated == 0`, and all items evaluate to `unchanged`, guaranteeing zero database mutations and complete idempotency.

---

### 8. What is the weakest part of your submission, and what would you do with two more days?

**Weakest Part:**  
The weakest architectural component is the **synchronous execution of `POST /api/sync/supplier/`**. Although the endpoint completes within the required 120-second threshold for the given mock catalog (~600 items), pulling an enterprise catalog with 50,000+ items across rate-limited endpoints would exceed HTTP gateway timeouts (e.g. Nginx 60s proxy timeouts).

**What I would do with two more days:**  
1. **Asynchronous Background Processing:** Decouple supplier sync using Celery and Redis. The endpoint would immediately return `202 ACCEPTED` with a task UUID, and a worker process would stream sync progress via WebSockets/Server-Sent Events (SSE) to the frontend dashboard.
2. **High-Concurrency Connection Pooling:** Implement PgBouncer in front of PostgreSQL to manage database connection spikes under high thread concurrency without saturating database connection limits.
3. **Distributed Stock Reservation (Redis Redlock):** Implement a distributed Redis lock pattern with sub-millisecond TTLs for high-volume inventory reservations, falling back to PostgreSQL row locks only during final confirmation.
