import csv
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Product
from dealers.models import Dealer


class Command(BaseCommand):
    help = "Load catalogue.csv and dealers.csv into PostgreSQL. Idempotent and high-performance."

    def handle(self, *args, **options):
        data_dir = settings.DATA_DIR
        catalogue_path = data_dir / "catalogue.csv"
        dealers_path = data_dir / "dealers.csv"

        # 1. Seed Dealers
        if dealers_path.exists():
            dealer_objs = []
            with open(dealers_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row["dealer_code"].strip()
                    if not code:
                        continue
                    dealer_objs.append(
                        Dealer(
                            dealer_code=code,
                            name=row.get("name", "").strip(),
                            city=row.get("city", "").strip(),
                            phone=row.get("phone", "").strip(),
                            email=row.get("email", "").strip(),
                            gstin=row.get("gstin", "").strip(),
                            credit_limit=Decimal(row.get("credit_limit", "0.00").strip() or "0.00"),
                        )
                    )
            with transaction.atomic():
                Dealer.objects.bulk_create(
                    dealer_objs,
                    update_conflicts=True,
                    unique_fields=["dealer_code"],
                    update_fields=["name", "city", "phone", "email", "gstin", "credit_limit"],
                )
            self.stdout.write(self.style.SUCCESS(
                f"Dealers seeded. Total in DB: {Dealer.objects.count()}"
            ))

        # 2. Seed Catalogue Products
        if catalogue_path.exists():
            product_objs = []
            with open(catalogue_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sku = row["sku"].strip()
                    if not sku:
                        continue
                    product_objs.append(
                        Product(
                            sku=sku,
                            name=row.get("name", "").strip(),
                            category=row.get("category", "").strip(),
                            brand=row.get("brand", "").strip(),
                            vehicle_fitment=row.get("vehicle_fitment", "").strip(),
                            price=Decimal(row.get("price", "0.00").strip() or "0.00"),
                            stock=int(row.get("stock", "0").strip() or 0),
                            description=row.get("description", "").strip(),
                        )
                    )
            with transaction.atomic():
                Product.objects.bulk_create(
                    product_objs,
                    update_conflicts=True,
                    unique_fields=["sku"],
                    update_fields=["name", "category", "brand", "vehicle_fitment", "price", "stock", "description"],
                )
            self.stdout.write(self.style.SUCCESS(
                f"Catalogue seeded. Total in DB: {Product.objects.count()}"
            ))
