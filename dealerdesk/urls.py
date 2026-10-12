from django.contrib import admin
from django.urls import include, path
from core.views import portal

urlpatterns = [
    path("", portal, name="portal-home"),
    path("portal/", portal, name="portal"),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/", include("products.urls")),
    path("api/", include("dealers.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("supplier_sync.urls")),
]
