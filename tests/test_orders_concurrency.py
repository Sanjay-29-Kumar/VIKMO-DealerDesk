import concurrent.futures
from decimal import Decimal
from django.test import TransactionTestCase
from django.db import connection

from products.models import Product
from dealers.models import Dealer
from orders.models import Order, OrderStatus
from orders.services import OrderService
from core.exceptions import InsufficientStockException


class OrderConcurrencyTestCase(TransactionTestCase):
    """
    Validates pessimistic row-locking and all-or-nothing stock guarantees
    under parallel simultaneous confirmation requests.
    """

    def setUp(self):
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-CONC-01",
            name="Concurrency Dealer",
            credit_limit=Decimal("100000.00"),
        )
        self.product = Product.objects.create(
            sku="CONC-1001",
            name="High Demand Brake Rotor",
            category="Brakes",
            brand="Brembo",
            vehicle_fitment="Yamaha R3",
            price=Decimal("2500.00"),
            stock=10,  # Exactly 10 units in stock
        )

    def test_concurrent_confirmations_prevent_overselling(self):
        """
        Two dealers create orders for 10 units each (competing for the same 10 units).
        When both try to confirm at the exact same moment:
        - Exactly ONE must succeed (confirming 10 units).
        - Exactly ONE must fail with InsufficientStockException.
        - Final stock must be exactly 0, NEVER negative.
        """
        order1, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 10}],
        )
        order2, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 10}],
        )

        results = []
        errors = []

        def attempt_confirm(order_number):
            # Close connection so each thread opens its own DB connection
            connection.close()
            try:
                confirmed = OrderService.confirm_order(order_number)
                return ("SUCCESS", confirmed.order_number)
            except InsufficientStockException as e:
                return ("INSUFFICIENT_STOCK", str(e))
            except Exception as e:
                return ("ERROR", str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(attempt_confirm, order1.order_number)
            future2 = executor.submit(attempt_confirm, order2.order_number)
            res1 = future1.result()
            res2 = future2.result()

        outcomes = [res1[0], res2[0]]

        # Assert exactly one succeeded and one was rejected for insufficient stock
        self.assertIn("SUCCESS", outcomes)
        self.assertIn("INSUFFICIENT_STOCK", outcomes)

        # Refresh product from DB and assert stock is exactly 0
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
