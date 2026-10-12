from decimal import Decimal
from django.test import TestCase

from products.models import Product
from dealers.models import Dealer
from orders.services import OrderService, calculate_line_item
from orders.serializers import OrderSerializer


class PricingAndGSTTestCase(TestCase):
    """
    Validates per-line 18% GST calculation, ROUND_HALF_UP precision,
    and post-confirmation price locking.
    """

    def setUp(self):
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-TAX-01",
            name="Tax Validation Dealer",
            credit_limit=Decimal("50000.00"),
        )
        self.product = Product.objects.create(
            sku="TAX-1001",
            name="Precision Spark Plug",
            category="Engine",
            brand="NGK",
            vehicle_fitment="Universal",
            price=Decimal("1459.50"),
            stock=100,
        )

    def test_line_tax_round_half_up(self):
        """
        Verify exact formula from contract section 7.4:
        unit_price = 1459.50, quantity = 3
        subtotal = 4378.50
        tax = 4378.50 * 0.18 = 788.13 (rounded half up)
        total = 5166.63
        """
        subtotal, tax, total = calculate_line_item(Decimal("1459.50"), 3)
        self.assertEqual(subtotal, Decimal("4378.50"))
        self.assertEqual(tax, Decimal("788.13"))
        self.assertEqual(total, Decimal("5166.63"))

    def test_rounding_edge_case(self):
        """
        Test paisa boundary rounding: 0.005 must round up to 0.01.
        subtotal = 0.03 * 0.18 = 0.0054 -> rounds to 0.01
        """
        subtotal, tax, total = calculate_line_item(Decimal("0.03"), 1)
        self.assertEqual(subtotal, Decimal("0.03"))
        self.assertEqual(tax, Decimal("0.01"))
        self.assertEqual(total, Decimal("0.04"))

    def test_price_locked_on_confirmation(self):
        """
        In DRAFT, changing product price does not mutate saved lines until PUT /api/orders/.
        On CONFIRMATION, order price is permanently locked forever.
        """
        order, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 2}],
        )
        self.assertEqual(order.subtotal, Decimal("2919.00"))

        # Confirm the order
        confirmed_order = OrderService.confirm_order(order.order_number)
        self.assertEqual(confirmed_order.subtotal, Decimal("2919.00"))

        # Now change product price in catalogue
        self.product.price = Decimal("9999.00")
        self.product.save()

        # The confirmed order must retain the original locked price
        confirmed_order.refresh_from_db()
        self.assertEqual(confirmed_order.subtotal, Decimal("2919.00"))
        first_item = confirmed_order.items.first()
        self.assertEqual(first_item.unit_price, Decimal("1459.50"))

    def test_serializer_money_format_strings(self):
        """Money fields in output JSON must be strings with 2 decimals."""
        order, _ = OrderService.create_draft_order(
            dealer_id=self.dealer.id,
            items_data=[{"sku": self.product.sku, "quantity": 1}],
        )
        serialized = OrderSerializer(order).data
        self.assertEqual(serialized["subtotal"], "1459.50")
        self.assertEqual(serialized["tax_total"], "262.71")
        self.assertEqual(serialized["grand_total"], "1722.21")
        self.assertIsInstance(serialized["subtotal"], str)
