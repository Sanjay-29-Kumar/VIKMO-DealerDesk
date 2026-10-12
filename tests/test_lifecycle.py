from decimal import Decimal
from django.test import TestCase

from products.models import Product
from dealers.models import Dealer
from orders.models import OrderStatus
from orders.services import OrderService
from core.exceptions import InvalidTransitionException, OrderLockedException


class OrderLifecycleTestCase(TestCase):
    """
    Validates status transitions and stock restoration rules from contract section 7.2 & 7.3.
    """

    def setUp(self):
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-LIFE-01",
            name="Lifecycle Dealer",
            credit_limit=Decimal("50000.00"),
        )
        self.product = Product.objects.create(
            sku="LIFE-1001",
            name="Chain Link Master",
            category="Drivetrain",
            brand="D.I.D",
            vehicle_fitment="Universal",
            price=Decimal("150.00"),
            stock=20,
        )

    def test_full_successful_flow(self):
        """Flow: DRAFT -> CONFIRMED -> DISPATCHED -> DELIVERED."""
        order, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 5}],
        )
        self.assertEqual(order.status, OrderStatus.DRAFT)
        self.assertEqual(self.product.stock, 20)  # Draft does not touch stock

        # Confirm: deducts stock to 15
        confirmed = OrderService.confirm_order(order.order_number)
        self.assertEqual(confirmed.status, OrderStatus.CONFIRMED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)

        # Dispatch
        dispatched = OrderService.dispatch_order(order.order_number)
        self.assertEqual(dispatched.status, OrderStatus.DISPATCHED)

        # Deliver
        delivered = OrderService.deliver_order(order.order_number)
        self.assertEqual(delivered.status, OrderStatus.DELIVERED)

    def test_cancel_confirmed_order_restores_stock_exactly_once(self):
        """Cancelling a CONFIRMED order restores stock exactly once."""
        order, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 4}],
        )
        OrderService.confirm_order(order.order_number)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 16)

        # Cancel
        cancelled = OrderService.cancel_order(order.order_number)
        self.assertEqual(cancelled.status, OrderStatus.CANCELLED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)  # Restored to 20

        # Attempting to cancel again must raise InvalidTransitionException
        with self.assertRaises(InvalidTransitionException):
            OrderService.cancel_order(order.order_number)

    def test_dispatched_and_delivered_cannot_be_cancelled(self):
        """DISPATCHED and DELIVERED orders cannot be cancelled."""
        order, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 1}],
        )
        OrderService.confirm_order(order.order_number)
        OrderService.dispatch_order(order.order_number)

        with self.assertRaises(InvalidTransitionException):
            OrderService.cancel_order(order.order_number)

    def test_editing_locked_order_rejected(self):
        """PUT /api/orders/{order_number}/ rejected if order is not in DRAFT status."""
        order, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 1}],
        )
        OrderService.confirm_order(order.order_number)

        with self.assertRaises(OrderLockedException):
            OrderService.update_draft_order_items(
                order.order_number,
                [{"sku": self.product.sku, "quantity": 3}],
            )
