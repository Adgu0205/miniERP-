from django.contrib import admin

from .models import Customer, SalesOrder, SalesOrderLine


class SOLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1


@admin.register(SalesOrder)
class SOAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "status", "total", "order_date",
                    "is_delayed")
    list_filter = ("status",)
    inlines = [SOLineInline]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone")
    search_fields = ("name",)
