from django.contrib import admin

from .models import StockLedger


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "movement_type", "quantity",
                    "balance_after", "reference", "created_by")
    list_filter = ("movement_type",)
    search_fields = ("product__name", "product__sku", "reference")
    readonly_fields = [f.name for f in StockLedger._meta.fields]
