from decimal import Decimal
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Product, InventoryLog
from .serializers import (
    ProductSerializer,
    ProductCreateSerializer,
    ProductUpdateSerializer,
)
from core.exceptions import (
    DealerDeskAPIException,
    DuplicateException,
    NotFoundException,
)
from core.pagination import StandardPagination


class ProductListCreateView(APIView):
    """
    GET /api/products/ - Paginated product list with search, category, and vehicle fitment filters.
    POST /api/products/ - Creates a product with initial stock 0.
    """
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Product.objects.all().order_by("sku")

        # Filters
        search_query = request.query_params.get("search")
        if search_query:
            search_query = search_query.strip()
            queryset = queryset.filter(
                Q(sku__icontains=search_query)
                | Q(name__icontains=search_query)
                | Q(brand__icontains=search_query)
            )

        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category.strip())

        vehicle = request.query_params.get("vehicle")
        if vehicle:
            queryset = queryset.filter(vehicle_fitment__icontains=vehicle.strip())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProductSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        sku = request.data.get("sku")
        if not sku or not str(sku).strip():
            raise DealerDeskAPIException("SKU is required.", code="VALIDATION_ERROR", status_code=400)
        
        sku = str(sku).strip()
        if Product.objects.filter(sku=sku).exists():
            raise DuplicateException(f"Product with SKU '{sku}' already exists.")

        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductDetailView(APIView):
    """
    GET /api/products/{sku}/ - Product detail
    PATCH /api/products/{sku}/ - Partial update
    """
    def get_object(self, sku):
        try:
            return Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            raise NotFoundException(f"Product with SKU '{sku}' not found.")

    def get(self, request, sku):
        product = self.get_object(sku)
        return Response(ProductSerializer(product).data)

    def patch(self, request, sku):
        product = self.get_object(sku)
        if "sku" in request.data and request.data["sku"] != sku:
            raise DealerDeskAPIException("SKU cannot be changed.", code="VALIDATION_ERROR", status_code=400)

        serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_product = serializer.save()
        return Response(ProductSerializer(updated_product).data)


class InventoryView(APIView):
    """
    PUT /api/inventory/{sku}/ - Sets available stock to exact integer >= 0.
    """
    def put(self, request, sku):
        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            raise NotFoundException(f"Product with SKU '{sku}' not found.")

        raw_qty = request.data.get("quantity")
        if raw_qty is None:
            raise DealerDeskAPIException("Quantity is required.", code="VALIDATION_ERROR", status_code=400)

        try:
            quantity = int(raw_qty)
        except (ValueError, TypeError):
            raise DealerDeskAPIException("Quantity must be an integer.", code="VALIDATION_ERROR", status_code=400)

        if quantity < 0:
            raise DealerDeskAPIException("Quantity must be an integer >= 0.", code="VALIDATION_ERROR", status_code=400)

        reason = request.data.get("reason", "")

        # Audit log
        InventoryLog.objects.create(
            product=product,
            quantity_before=product.stock,
            quantity_after=quantity,
            reason=reason,
        )

        product.stock = quantity
        product.save(update_fields=["stock", "updated_at"])

        return Response({"sku": product.sku, "quantity": product.stock}, status=status.HTTP_200_OK)
