from django.urls import path
from .views import ProductListCreateView, ProductDetailView, InventoryView

urlpatterns = [
    path("products/", ProductListCreateView.as_view(), name="product-list-create"),
    path("products/<str:sku>/", ProductDetailView.as_view(), name="product-detail"),
    path("inventory/<str:sku>/", InventoryView.as_view(), name="inventory-update"),
]
