from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils.dateparse import parse_datetime
from products.models import Product
from .client import SupplierClient


def is_valid_price(raw_price) -> tuple[bool, Decimal]:
    try:
        val = Decimal(str(raw_price).strip())
        if val <= Decimal("0.00"):
            return False, Decimal("0.00")
        if val.as_tuple().exponent < -2:
            return False, Decimal("0.00")
        return True, val
    except (InvalidOperation, TypeError, ValueError):
        return False, Decimal("0.00")


class SupplierSyncService:

    @classmethod
    def run_sync(cls, base_url: str = None, api_key: str = None) -> dict:
        client = SupplierClient(base_url=base_url, api_key=api_key)
        
        # Step 1: Fetch all products into memory with full retry logic.
        # If any request fails, client raises SupplierUnavailableException (HTTP 502)
        raw_items, pages_fetched, requests_made = client.fetch_all_products()

        rejected = []
        valid_items_by_sku = {}

        # Step 2: Validate items & discard invalids
        for it in raw_items:
            supplier_sku = it.get("supplier_sku", "")
            sku = it.get("sku")
            if not sku or not str(sku).strip():
                rejected.append({
                    "supplier_sku": supplier_sku,
                    "reason": "missing sku",
                })
                continue
            
            sku = str(sku).strip()
            raw_price = it.get("price")
            valid_p, parsed_price = is_valid_price(raw_price)
            if not valid_p:
                rejected.append({
                    "supplier_sku": supplier_sku,
                    "reason": "invalid price",
                })
                continue

            # Step 3: Deduplicate SKUs using latest updated_at
            item_updated_at = parse_datetime(it.get("updated_at", "")) if it.get("updated_at") else None
            
            if sku in valid_items_by_sku:
                existing_item, existing_ts, _ = valid_items_by_sku[sku]
                if item_updated_at and existing_ts:
                    if item_updated_at > existing_ts:
                        valid_items_by_sku[sku] = (it, item_updated_at, parsed_price)
                elif item_updated_at and not existing_ts:
                    valid_items_by_sku[sku] = (it, item_updated_at, parsed_price)
            else:
                valid_items_by_sku[sku] = (it, item_updated_at, parsed_price)

        # Step 4: Apply to database inside an atomic transaction
        created_count = 0
        updated_count = 0
        unchanged_count = 0

        with transaction.atomic():
            existing_products = {
                p.sku: p for p in Product.objects.filter(sku__in=list(valid_items_by_sku.keys()))
            }

            to_create = []
            for sku, (it, _, parsed_price) in valid_items_by_sku.items():
                name = str(it.get("name", "")).strip()
                category = str(it.get("category", "")).strip()
                brand = str(it.get("brand", "")).strip()
                vehicle_fitment = str(it.get("vehicle_fitment", "")).strip()
                description = str(it.get("description", "")).strip()

                if sku not in existing_products:
                    # New product: create with stock 0
                    to_create.append(
                        Product(
                            sku=sku,
                            name=name,
                            category=category,
                            brand=brand,
                            vehicle_fitment=vehicle_fitment,
                            description=description,
                            price=parsed_price,
                            stock=0,  # Contract: always initial stock 0
                        )
                    )
                    created_count += 1
                else:
                    existing = existing_products[sku]
                    # Check if any field differs
                    differs = (
                        existing.name != name
                        or existing.category != category
                        or existing.brand != brand
                        or existing.vehicle_fitment != vehicle_fitment
                        or existing.description != description
                        or existing.price != parsed_price
                    )

                    if differs:
                        existing.name = name
                        existing.category = category
                        existing.brand = brand
                        existing.vehicle_fitment = vehicle_fitment
                        existing.description = description
                        existing.price = parsed_price
                        # NEVER change existing.stock!
                        existing.save(update_fields=[
                            "name",
                            "category",
                            "brand",
                            "vehicle_fitment",
                            "description",
                            "price",
                            "updated_at",
                        ])
                        updated_count += 1
                    else:
                        unchanged_count += 1

            if to_create:
                Product.objects.bulk_create(to_create)

        return {
            "created": created_count,
            "updated": updated_count,
            "unchanged": unchanged_count,
            "rejected": rejected,
            "pages_fetched": pages_fetched,
            "requests_made": requests_made,
        }
