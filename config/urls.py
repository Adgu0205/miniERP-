from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ProcurERP Admin"
admin.site.site_title = "ProcurERP"
admin.site.index_title = "Operations"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.dashboard.urls")),
    path("u/", include("apps.users.urls")),
    path("products/", include("apps.products.urls")),
    path("sales/", include("apps.sales.urls")),
    path("purchase/", include("apps.purchase.urls")),
    path("manufacturing/", include("apps.manufacturing.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("audit/", include("apps.audit.urls")),
]
