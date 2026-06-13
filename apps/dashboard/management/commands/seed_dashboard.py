"""Generate ~30 days of historical orders so the dashboard charts look alive.
Idempotent-ish: clears prior demo history rows (origin='hist') before reseeding."""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.manufacturing.models import ManufacturingOrder, MOStatus
from apps.products.models import ProcurementType, Product
from apps.purchase.models import POStatus, PurchaseOrder, PurchaseOrderLine
from apps.sales.models import (Customer, SalesOrder, SalesOrderLine, SOStatus)

D = lambda v: Decimal(str(v))


class Command(BaseCommand):
    help = "Seed historical sales/purchase/manufacturing activity for dashboards."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--orders", type=int, default=70)

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(42)
        days = opts["days"]
        n = opts["orders"]
        now = timezone.now()
        admin = User.objects.filter(username="admin").first()

        customers = list(Customer.objects.all())
        finished = list(Product.objects.filter(sku__startswith="FG-"))
        components = list(Product.objects.filter(sku__startswith="RM-"))
        if not (customers and finished):
            self.stdout.write(self.style.ERROR("Run seed_demo first."))
            return

        # Clean previous history
        SalesOrder.objects.filter(reference__startswith="HSO").delete()
        PurchaseOrder.objects.filter(reference__startswith="HPO").delete()
        ManufacturingOrder.objects.filter(reference__startswith="HMO").delete()

        so_statuses = ([SOStatus.DELIVERED] * 6 + [SOStatus.PARTIAL] * 2 +
                       [SOStatus.CONFIRMED] * 2 + [SOStatus.DRAFT, SOStatus.CANCELLED])

        # --- Sales history ---
        created = 0
        for i in range(n):
            day = random.randint(0, days - 1)
            # weight recent days a bit heavier
            when = now - timedelta(days=day, hours=random.randint(0, 23))
            cust = random.choice(customers)
            status = random.choice(so_statuses)
            so = SalesOrder.objects.create(customer=cust, status=status)
            so.reference = f"HSO{so.pk:05d}"
            nlines = random.randint(1, 3)
            for _ in range(nlines):
                p = random.choice(finished)
                qty = random.randint(1, 12)
                line = SalesOrderLine.objects.create(
                    order=so, product=p, quantity=D(qty), unit_price=p.sale_price)
                if status == SOStatus.DELIVERED:
                    line.delivered_qty = D(qty)
                elif status == SOStatus.PARTIAL:
                    line.delivered_qty = D(max(1, qty // 2))
                line.save()
            SalesOrder.objects.filter(pk=so.pk).update(
                reference=so.reference, order_date=when.date(), created_at=when,
                deadline=(when + timedelta(days=random.randint(2, 10))).date())
            created += 1

        # --- Purchase history ---
        for i in range(max(8, n // 4)):
            when = now - timedelta(days=random.randint(0, days - 1))
            comp = random.choice(components)
            status = random.choice([POStatus.RECEIVED] * 4 + [POStatus.PARTIAL,
                                    POStatus.CONFIRMED, POStatus.DRAFT])
            po = PurchaseOrder.objects.create(vendor=comp.vendor, status=status,
                                              origin="history")
            po.reference = f"HPO{po.pk:05d}"
            qty = random.randint(20, 200)
            line = PurchaseOrderLine.objects.create(
                order=po, product=comp, quantity=D(qty), unit_price=comp.cost_price)
            if status == POStatus.RECEIVED:
                line.received_qty = D(qty)
            elif status == POStatus.PARTIAL:
                line.received_qty = D(qty // 2)
            line.save()
            PurchaseOrder.objects.filter(pk=po.pk).update(
                reference=po.reference, order_date=when.date(), created_at=when)

        # --- Manufacturing history ---
        mfg_products = [p for p in finished
                        if p.procurement_type == ProcurementType.MANUFACTURE]
        for i in range(max(6, n // 5)):
            when = now - timedelta(days=random.randint(0, days - 1))
            p = random.choice(mfg_products or finished)
            status = random.choice([MOStatus.DONE] * 3 + [MOStatus.IN_PROGRESS,
                                   MOStatus.CONFIRMED, MOStatus.DRAFT])
            mo = ManufacturingOrder.objects.create(
                product=p, bom=p.bom, quantity=D(random.randint(2, 15)),
                status=status, origin="history",
                deadline=(when + timedelta(days=random.randint(3, 12))).date())
            mo.reference = f"HMO{mo.pk:05d}"
            ManufacturingOrder.objects.filter(pk=mo.pk).update(
                reference=mo.reference, created_at=when)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {created} sales orders + purchase/mfg history over {days} days."))
