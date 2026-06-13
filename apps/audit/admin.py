from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "module", "action", "model", "object_ref", "user")
    list_filter = ("module", "action")
    search_fields = ("object_ref", "description")
    readonly_fields = [f.name for f in AuditLog._meta.fields]
