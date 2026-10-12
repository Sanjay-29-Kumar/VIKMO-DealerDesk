from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .services import SupplierSyncService


class SupplierSyncView(APIView):
    """
    POST /api/sync/supplier/ - Triggers full supplier catalogue sync.
    Runs within 120 seconds, handles retries, rate-limits, and errors.
    """
    def post(self, request):
        result = SupplierSyncService.run_sync()
        return Response(result, status=status.HTTP_200_OK)
