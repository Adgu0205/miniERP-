from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "product_type", "strategy", "procurement_type",
                    "on_hand", "reserved", "free_to_use", "sale_price")
    list_filter = ("product_type", "strategy", "procurement_type")
    search_fields = ("name", "sku")
    readonly_fields = ("on_hand", "reserved")
