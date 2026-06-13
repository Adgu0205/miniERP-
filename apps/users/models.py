from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    OWNER = "owner", "Business Owner"
    SALES = "sales", "Sales User"
    PURCHASE = "purchase", "Purchase User"
    MANUFACTURING = "manufacturing", "Manufacturing User"
    INVENTORY = "inventory", "Inventory Manager"


# Modules each role may access. Admin & Owner see everything.
ROLE_MODULES = {
    Role.ADMIN: {"dashboard", "products", "sales", "purchase",
                 "manufacturing", "inventory", "procurement", "audit", "users"},
    Role.OWNER: {"dashboard", "products", "sales", "purchase",
                 "manufacturing", "inventory", "procurement", "audit"},
    Role.SALES: {"dashboard", "products", "sales"},
    Role.PURCHASE: {"dashboard", "products", "purchase"},
    Role.MANUFACTURING: {"dashboard", "products", "manufacturing", "inventory"},
    Role.INVENTORY: {"dashboard", "products", "inventory", "procurement"},
}


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALES)
    phone = models.CharField(max_length=20, blank=True)
    position = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def modules(self):
        return ROLE_MODULES.get(self.role, set())

    def can_access(self, module):
        return module in self.modules
