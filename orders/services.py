import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
import zoneinfo

from .models import Order, OrderItem, OrderStatus, DailyOrderSequence, IdempotencyRecord
from products.models import Product
from dealers.models import Dealer
from core.exceptions import (
    DealerDeskAPIException,
    InsufficientStockException,
    InvalidTransitionException,
    OrderLockedException,
    IdempotencyConflictException,
    NotFoundException,
)

TWO_PLACES = Decimal("0.01")
TAX_RATE = Decimal("0.18")
KOLKATA_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")


def calculate_line_item(unit_price: Decimal, quantity: int):
    """
    Calculates line pricing strictly following API_CONTRACT.md section 7.4:
    line_subtotal = unit_price * quantity
    line_tax = line_subtotal * 0.18 (ROUND_HALF_UP per line)
    line_total = line_subtotal + line_tax
    """
    subtotal = (unit_price * quantity).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    tax = (subtotal * TAX_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    total = subtotal + tax
    return subtotal, tax, total


def generate_order_number() -> str:
    """
    Generates ORD-YYYYMMDD-NNNN using Asia/Kolkata current date.
    Uses DailyOrderSequence with select_for_update() to guarantee uniqueness under concurrency.
    """
    now_kolkata = timezone.now().astimezone(KOLKATA_TZ)
    today = now_kolkata.date()

    seq_obj, _ = DailyOrderSequence.objects.select_for_update().get_or_create(
        date=today,
        defaults={"last_sequence": 0},
    )
    seq_obj.last_sequence += 1
    seq_obj.save(update_fields=["last_sequence"])

    date_str = today.strftime("%Y%m%d")
    return f"ORD-{date_str}-{seq_obj.last_sequence:04d}"


def hash_payload(data: dict) -> str:
    """Computes a deterministic SHA-256 hash for idempotency checking."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class OrderService:

    @classmethod
    @transaction.atomic
    def create_draft_order(cls, dealer_id, items_data, idempotency_key=None) -> tuple[Order, bool]:
        """
        Creates a DRAFT order. If idempotency_key is given:
        - returns original order if duplicate request with same body.
        - raises 409 IDEMPOTENCY_CONFLICT if body differs.
        """
        request_hash = None
        if idempotency_key:
            payload = {"dealer_id": dealer_id, "items": items_data}
            request_hash = hash_payload(payload)

            # Check existing idempotency record with row lock
            existing = IdempotencyRecord.objects.select_for_update().filter(key=idempotency_key).first()
            if existing:
                if existing.request_hash == request_hash:
                    # Return cached order
                    order = Order.objects.get(order_number=existing.order_number)
                    return order, False
                else:
                    raise IdempotencyConflictException("Idempotency key reused with different request payload.")

        # Validate dealer
        try:
            dealer = Dealer.objects.get(pk=dealer_id)
        except Dealer.DoesNotExist:
            raise DealerDeskAPIException(f"Dealer with ID {dealer_id} does not exist.", code="VALIDATION_ERROR", status_code=400)

        # Validate items
        if not items_data or not isinstance(items_data, list):
            raise DealerDeskAPIException("Order must contain at least one item.", code="VALIDATION_ERROR", status_code=400)

        skus_seen = set()
        clean_items = []
        for it in items_data:
            sku = str(it.get("sku", "")).strip()
            qty = it.get("quantity")

            if not sku:
                raise DealerDeskAPIException("Each item must have a SKU.", code="VALIDATION_ERROR", status_code=400)
            if sku in skus_seen:
                raise DealerDeskAPIException(f"Duplicate SKU '{sku}' in order items.", code="VALIDATION_ERROR", status_code=400)
            skus_seen.add(sku)

            try:
                qty = int(qty)
            except (ValueError, TypeError):
                raise DealerDeskAPIException(f"Quantity for SKU '{sku}' must be an integer.", code="VALIDATION_ERROR", status_code=400)

            if qty < 1:
                raise DealerDeskAPIException(f"Quantity for SKU '{sku}' must be at least 1.", code="VALIDATION_ERROR", status_code=400)

            clean_items.append((sku, qty))

        # Fetch products
        products_map = {p.sku: p for p in Product.objects.filter(sku__in=[s for s, _ in clean_items])}
        for sku, _ in clean_items:
            if sku not in products_map:
                raise DealerDeskAPIException(f"Product with SKU '{sku}' does not exist.", code="VALIDATION_ERROR", status_code=400)

        # Generate order number
        order_number = generate_order_number()

        # Create Order
        order = Order.objects.create(
            order_number=order_number,
            dealer=dealer,
            status=OrderStatus.DRAFT,
        )

        subtotal_sum = Decimal("0.00")
        tax_sum = Decimal("0.00")
        order_items = []

        for sku, qty in clean_items:
            product = products_map[sku]
            unit_price = product.price
            line_subtotal, line_tax, line_total = calculate_line_item(unit_price, qty)

            subtotal_sum += line_subtotal
            tax_sum += line_tax

            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    sku=product.sku,
                    name=product.name,
                    quantity=qty,
                    unit_price=unit_price,
                    line_subtotal=line_subtotal,
                    line_tax=line_tax,
                    line_total=line_total,
                )
            )

        OrderItem.objects.bulk_create(order_items)

        order.subtotal = subtotal_sum
        order.tax_total = tax_sum
        order.grand_total = subtotal_sum + tax_sum
        order.save(update_fields=["subtotal", "tax_total", "grand_total"])

        if idempotency_key:
            IdempotencyRecord.objects.create(
                key=idempotency_key,
                request_hash=request_hash,
                status_code=201,
                response_body={},
                order_number=order.order_number,
            )

        return order, True

    @classmethod
    @transaction.atomic
    def update_draft_order_items(cls, order_number: str, items_data: list) -> Order:
        """PUT /api/orders/{order_number}/ - Replaces all items while in DRAFT."""
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundException(f"Order '{order_number}' not found.")

        if order.status != OrderStatus.DRAFT:
            raise OrderLockedException(f"Order cannot be edited in '{order.status}' status. Only DRAFT orders can be modified.")

        if not items_data or not isinstance(items_data, list):
            raise DealerDeskAPIException("Order must contain at least one item.", code="VALIDATION_ERROR", status_code=400)

        skus_seen = set()
        clean_items = []
        for it in items_data:
            sku = str(it.get("sku", "")).strip()
            qty = it.get("quantity")

            if not sku:
                raise DealerDeskAPIException("Each item must have a SKU.", code="VALIDATION_ERROR", status_code=400)
            if sku in skus_seen:
                raise DealerDeskAPIException(f"Duplicate SKU '{sku}' in order items.", code="VALIDATION_ERROR", status_code=400)
            skus_seen.add(sku)

            try:
                qty = int(qty)
            except (ValueError, TypeError):
                raise DealerDeskAPIException(f"Quantity for SKU '{sku}' must be an integer.", code="VALIDATION_ERROR", status_code=400)

            if qty < 1:
                raise DealerDeskAPIException(f"Quantity for SKU '{sku}' must be at least 1.", code="VALIDATION_ERROR", status_code=400)

            clean_items.append((sku, qty))

        products_map = {p.sku: p for p in Product.objects.filter(sku__in=[s for s, _ in clean_items])}
        for sku, _ in clean_items:
            if sku not in products_map:
                raise DealerDeskAPIException(f"Product with SKU '{sku}' does not exist.", code="VALIDATION_ERROR", status_code=400)

        # Clear existing items
        order.items.all().delete()

        subtotal_sum = Decimal("0.00")
        tax_sum = Decimal("0.00")
        order_items = []

        for sku, qty in clean_items:
            product = products_map[sku]
            unit_price = product.price  # Follows current catalogue price in DRAFT
            line_subtotal, line_tax, line_total = calculate_line_item(unit_price, qty)

            subtotal_sum += line_subtotal
            tax_sum += line_tax

            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    sku=product.sku,
                    name=product.name,
                    quantity=qty,
                    unit_price=unit_price,
                    line_subtotal=line_subtotal,
                    line_tax=line_tax,
                    line_total=line_total,
                )
            )

        OrderItem.objects.bulk_create(order_items)

        order.subtotal = subtotal_sum
        order.tax_total = tax_sum
        order.grand_total = subtotal_sum + tax_sum
        order.save(update_fields=["subtotal", "tax_total", "grand_total", "updated_at"])

        return order

    @classmethod
    @transaction.atomic
    def confirm_order(cls, order_number: str) -> Order:
        """
        DRAFT -> CONFIRMED.
        All-or-nothing stock validation.
        Prevents overselling using row-level select_for_update() with sorted SKU locking (prevents deadlocks).
        Locks price forever.
        """
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundException(f"Order '{order_number}' not found.")

        if order.status != OrderStatus.DRAFT:
            raise InvalidTransitionException(f"Cannot confirm order in '{order.status}' status. Only DRAFT orders can be confirmed.")

        items = list(order.items.all())
        if not items:
            raise DealerDeskAPIException("Order contains no items.", code="VALIDATION_ERROR", status_code=400)

        # Sort SKUs to prevent database deadlocks under high concurrency
        skus = sorted([it.sku for it in items])
        locked_products = {p.sku: p for p in Product.objects.select_for_update().filter(sku__in=skus).order_by("sku")}

        # All-or-nothing stock check
        insufficient_details = []
        messages = []

        for it in items:
            p = locked_products.get(it.sku)
            if not p or p.stock < it.quantity:
                available = p.stock if p else 0
                insufficient_details.append({
                    "sku": it.sku,
                    "requested": it.quantity,
                    "available": available,
                })
                prod_name = p.name if p else it.name
                messages.append(f"Insufficient stock for {prod_name}. Available: {available}, Requested: {it.quantity}")

        if insufficient_details:
            raise InsufficientStockException(message=". ".join(messages), details=insufficient_details)

        # Deduct stock and lock prices
        for it in items:
            p = locked_products[it.sku]
            p.stock -= it.quantity
            p.save(update_fields=["stock", "updated_at"])

        order.status = OrderStatus.CONFIRMED
        order.save(update_fields=["status", "updated_at"])
        return order

    @classmethod
    @transaction.atomic
    def dispatch_order(cls, order_number: str) -> Order:
        """CONFIRMED -> DISPATCHED."""
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundException(f"Order '{order_number}' not found.")

        if order.status != OrderStatus.CONFIRMED:
            raise InvalidTransitionException(f"Cannot dispatch order in '{order.status}' status. Only CONFIRMED orders can be dispatched.")

        order.status = OrderStatus.DISPATCHED
        order.save(update_fields=["status", "updated_at"])
        return order

    @classmethod
    @transaction.atomic
    def deliver_order(cls, order_number: str) -> Order:
        """DISPATCHED -> DELIVERED."""
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundException(f"Order '{order_number}' not found.")

        if order.status != OrderStatus.DISPATCHED:
            raise InvalidTransitionException(f"Cannot deliver order in '{order.status}' status. Only DISPATCHED orders can be delivered.")

        order.status = OrderStatus.DELIVERED
        order.save(update_fields=["status", "updated_at"])
        return order

    @classmethod
    @transaction.atomic
    def cancel_order(cls, order_number: str) -> Order:
        """
        DRAFT -> CANCELLED, or CONFIRMED -> CANCELLED (restores stock exactly once).
        DISPATCHED, DELIVERED, CANCELLED cannot be cancelled.
        """
        try:
            order = Order.objects.select_for_update().get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundException(f"Order '{order_number}' not found.")

        if order.status not in (OrderStatus.DRAFT, OrderStatus.CONFIRMED):
            raise InvalidTransitionException(f"Cannot cancel order in '{order.status}' status.")

        # If CONFIRMED, restore stock exactly once
        if order.status == OrderStatus.CONFIRMED:
            items = list(order.items.all())
            skus = sorted([it.sku for it in items])
            locked_products = {p.sku: p for p in Product.objects.select_for_update().filter(sku__in=skus).order_by("sku")}

            for it in items:
                p = locked_products.get(it.sku)
                if p:
                    p.stock += it.quantity
                    p.save(update_fields=["stock", "updated_at"])

        order.status = OrderStatus.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        return order
