from django.http import JsonResponse
from django.shortcuts import render


def health(request):
    """GET /api/health/ — the grader polls this until your app is ready."""
    return JsonResponse({"status": "ok"})


def portal(request):
    """GET / or /portal/ — serves the DealerDesk portal interface."""
    return render(request, "index.html")
