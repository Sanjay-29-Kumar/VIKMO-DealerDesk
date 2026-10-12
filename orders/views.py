from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer
from .services import OrderService
from core.exceptions import NotFoundException, DealerDeskAPIException
from core.pagination import StandardPagination


class OrderListCreateView(APIView):
    """
    GET /api/orders/ - Paginated list of orders, filtered by dealer_id and status.
    POST /api/orders/ - Creates a DRAFT order with idempotency support.
    """
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Order.objects.all().order_by("-created_at")

        dealer_id = request.query_params.get("dealer_id")
        if dealer_id:
            try:
                queryset = queryset.filter(dealer_id=int(dealer_id))
            except ValueError:
                pass

        order_status = request.query_params.get("status")
        if order_status:
            queryset = queryset.filter(status=order_status.strip().upper())

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = OrderSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        dealer_id = request.data.get("dealer_id")
        if dealer_id is None:
            raise DealerDeskAPIException("dealer_id is required.", code="VALIDATION_ERROR", status_code=400)

        items = request.data.get("items")
        if items is None or not isinstance(items, list) or len(items) == 0:
            raise DealerDeskAPIException("items must be a non-empty list.", code="VALIDATION_ERROR", status_code=400)

        idempotency_key = request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY")

        order, created = OrderService.create_draft_order(
            dealer_id=dealer_id,
            items_data=items,
            idempotency_key=idempotency_key,
        )

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(OrderSerializer(order).data, status=response_status)


class OrderDetailUpdateView(APIView):
    """
    GET /api/orders/{order_number}/ - Retrieve order detail.
    PUT /api/orders/{order_number}/ - Replace order items while in DRAFT status.
    """
    def get(self, request, order_number):
        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            raise NotFoundException(f"Order '{order_number}' not found.")

        return Response(OrderSerializer(order).data)

    def put(self, request, order_number):
        items = request.data.get("items")
        if items is None or not isinstance(items, list) or len(items) == 0:
            raise DealerDeskAPIException("items must be a non-empty list.", code="VALIDATION_ERROR", status_code=400)

        order = OrderService.update_draft_order_items(order_number, items)
        return Response(OrderSerializer(order).data)


class OrderConfirmView(APIView):
    """POST /api/orders/{order_number}/confirm/ - Confirms draft order, checks stock, locks price."""
    def post(self, request, order_number):
        order = OrderService.confirm_order(order_number)
        return Response(OrderSerializer(order).data)


class OrderDispatchView(APIView):
    """POST /api/orders/{order_number}/dispatch/ - Marks order as dispatched."""
    def post(self, request, order_number):
        order = OrderService.dispatch_order(order_number)
        return Response(OrderSerializer(order).data)


class OrderDeliverView(APIView):
    """POST /api/orders/{order_number}/deliver/ - Marks order as delivered."""
    def post(self, request, order_number):
        order = OrderService.deliver_order(order_number)
        return Response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    """POST /api/orders/{order_number}/cancel/ - Cancels order and restores stock if was confirmed."""
    def post(self, request, order_number):
        order = OrderService.cancel_order(order_number)
        return Response(OrderSerializer(order).data)
