from decimal import Decimal
from django.test import TestCase

from products.models import Product
from dealers.models import Dealer
from orders.models import Order
from orders.services import OrderService
from core.exceptions import IdempotencyConflictException


class IdempotencyTestCase(TestCase):
    """
    Validates Idempotency-Key guarantees according to contract section 7.5.
    """

    def setUp(self):
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-IDEM-01",
            name="Idempotency Test Dealer",
            credit_limit=Decimal("50000.00"),
        )
        self.product = Product.objects.create(
            sku="IDEM-1001",
            name="Idempotent Oil Filter",
            category="Engine",
            brand="Bosch",
            vehicle_fitment="Universal",
            price=Decimal("450.00"),
            stock=50,
        )

    def test_same_key_same_body_returns_original(self):
        """Reusing same key with same payload returns original order without creating duplicate."""
        key = "unique-test-key-12345"
        payload = [{"sku": self.product.sku, "quantity": 2}]

        order1, created1 = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=payload,
            idempotency_key=key,
        )
        self.assertTrue(created1)

        # Second call with exact same key and payload
        order2, created2 = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=payload,
            idempotency_key=key,
        )
        self.assertFalse(created2)
        self.assertEqual(order1.order_number, order2.order_number)
        self.assertEqual(Order.objects.filter(order_number=order1.order_number).count(), 1)

    def test_same_key_different_body_raises_conflict(self):
        """Reusing same key with different payload must raise 409 IDEMPOTENCY_CONFLICT."""
        key = "conflict-test-key-67890"

        OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 1}],
            idempotency_key=key,
        )

        # Attempt with different quantity
        with self.assertRaises(IdempotencyConflictException):
            OrderService.create_draft_order(
                dealer_id=self.dealer.id,
                items_data=[{"sku": self.product.sku, "quantity": 5}],
                idempotency_key=key,
            )
