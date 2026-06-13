from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderLine, Vendor


class POLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class POAdmin(admin.ModelAdmin):
    list_display = ("reference", "vendor", "status", "total", "order_date")
    list_filter = ("status",)
    inlines = [POLineInline]


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "lead_time_days")
    search_fields = ("name",)
