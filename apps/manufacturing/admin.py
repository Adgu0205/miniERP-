from django.contrib import admin

from .models import (BoM, BoMLine, BoMOperation, ManufacturingOrder,
                     WorkCenter, WorkOrder)


class BoMLineInline(admin.TabularInline):
    model = BoMLine
    extra = 1


class BoMOperationInline(admin.TabularInline):
    model = BoMOperation
    extra = 1


@admin.register(BoM)
class BoMAdmin(admin.ModelAdmin):
    list_display = ("__str__", "product", "quantity", "is_active")
    inlines = [BoMLineInline, BoMOperationInline]


class WorkOrderInline(admin.TabularInline):
    model = WorkOrder
    extra = 0


@admin.register(ManufacturingOrder)
class MOAdmin(admin.ModelAdmin):
    list_display = ("reference", "product", "quantity", "status", "assignee",
                    "deadline", "is_delayed")
    list_filter = ("status",)
    inlines = [WorkOrderInline]


admin.site.register(WorkCenter)
admin.site.register(BoMLine)
admin.site.register(BoMOperation)
admin.site.register(WorkOrder)
