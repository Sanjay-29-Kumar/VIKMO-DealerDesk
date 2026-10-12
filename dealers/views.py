from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Dealer
from .serializers import DealerSerializer, DealerCreateSerializer
from core.exceptions import NotFoundException, DuplicateException
from core.pagination import StandardPagination


class DealerListCreateView(APIView):
    """
    GET /api/dealers/ - Paginated list of dealers
    POST /api/dealers/ - Create dealer
    """
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Dealer.objects.all().order_by("id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = DealerSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = DealerSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DealerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = serializer.save()
        return Response(DealerSerializer(dealer).data, status=status.HTTP_201_CREATED)


class DealerDetailView(APIView):
    """
    GET /api/dealers/{id}/ - Dealer detail
    """
    def get(self, request, pk):
        try:
            dealer = Dealer.objects.get(pk=pk)
        except Dealer.DoesNotExist:
            raise NotFoundException(f"Dealer with ID {pk} not found.")

        return Response(DealerSerializer(dealer).data)
