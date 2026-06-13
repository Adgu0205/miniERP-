from django.contrib import admin

from .models import ProcurementLog


@admin.register(ProcurementLog)
class ProcurementLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "trigger", "shortage", "action",
                    "result_ref")
    list_filter = ("action",)
