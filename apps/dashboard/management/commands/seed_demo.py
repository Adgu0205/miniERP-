from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.inventory import services as stock
from apps.inventory.models import MovementType
from apps.manufacturing.models import (BoM, BoMLine, BoMOperation, WorkCenter)
from apps.products.models import (ProcurementStrategy, ProcurementType,
                                  ProductType, Product)
from apps.purchase.models import Vendor
from apps.sales.models import Customer
from apps.users.models import Profile, Role

D = lambda v: Decimal(str(v))


class Command(BaseCommand):
    help = "Seed Shiv Furniture demo data (users, products, BoM, stock)."

    @transaction.atomic
    def handle(self, *args, **opts):
        self.stdout.write("Seeding demo data...")

        # --- Users / roles ---
        admin, created = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True})
        if created:
            admin.set_password("admin123"); admin.save()
        Profile.objects.update_or_create(user=admin, defaults={"role": Role.ADMIN})

        role_users = {
            "owner": Role.OWNER, "sales": Role.SALES, "purchase": Role.PURCHASE,
            "manufacturing": Role.MANUFACTURING, "inventory": Role.INVENTORY,
        }
        for uname, role in role_users.items():
            u, c = User.objects.get_or_create(username=uname, defaults={"is_staff": True})
            if c:
                u.set_password("demo1234"); u.save()
            Profile.objects.update_or_create(
                user=u, defaults={"role": role, "position": role.label})

        # --- Vendors ---
        timber = Vendor.objects.get_or_create(
            name="Timber Traders", defaults={"phone": "+91 90000 11111",
            "email": "sales@timber.example", "lead_time_days": 4})[0]
        hardware = Vendor.objects.get_or_create(
            name="National Hardware", defaults={"phone": "+91 90000 22222",
            "lead_time_days": 2})[0]

        # --- Work centers ---
        wc_assembly = WorkCenter.objects.get_or_create(
            name="Assembly Line", defaults={"cost_per_hour": 300})[0]
        wc_paint = WorkCenter.objects.get_or_create(
            name="Paint Floor", defaults={"cost_per_hour": 250})[0]
        wc_pack = WorkCenter.objects.get_or_create(
            name="Packaging Unit", defaults={"cost_per_hour": 150})[0]

        # --- Components (raw materials, bought) ---
        def make_product(name, sku, sale, cost, ptype=ProductType.STOCKABLE,
                         strategy=ProcurementStrategy.MTS,
                         proc=ProcurementType.BUY, vendor=None, onhand=0):
            p, _ = Product.objects.get_or_create(sku=sku, defaults={
                "name": name, "sale_price": D(sale), "cost_price": D(cost),
                "product_type": ptype, "strategy": strategy,
                "procurement_type": proc, "vendor": vendor,
                "procure_on_demand": True})
            if onhand and p.on_hand == 0:
                stock.record_move(p, D(onhand), MovementType.ADJUST,
                                  reference="opening stock", user=admin)
            return p

        legs = make_product("Wooden Legs", "RM-LEG", 0, 80, vendor=timber, onhand=200)
        top = make_product("Wooden Top", "RM-TOP", 0, 600, vendor=timber, onhand=30)
        screws = make_product("Screws", "RM-SCR", 0, 2, vendor=hardware, onhand=1000)
        seat = make_product("Chair Seat", "RM-SEAT", 0, 220, vendor=timber, onhand=120)
        paint = make_product("Paint Can", "RM-PNT", 0, 150, vendor=hardware, onhand=60)

        # --- Finished goods ---
        table = make_product(
            "Wooden Table", "FG-TBL", 4500, 1800,
            strategy=ProcurementStrategy.MTO, proc=ProcurementType.MANUFACTURE,
            onhand=2)
        chair = make_product(
            "Office Chair", "FG-CHR", 2200, 900,
            strategy=ProcurementStrategy.MTS, proc=ProcurementType.MANUFACTURE,
            onhand=100)
        dining = make_product(
            "Dining Table", "FG-DIN", 9000, 3600,
            strategy=ProcurementStrategy.MTO, proc=ProcurementType.MANUFACTURE,
            onhand=5)

        # --- BoMs ---
        def make_bom(product, comps, ops):
            bom, created = BoM.objects.get_or_create(
                product=product, defaults={"name": f"BoM {product.name}", "quantity": 1})
            if created:
                for comp, qty in comps:
                    BoMLine.objects.create(bom=bom, component=comp, quantity=D(qty))
                for i, (name, wc, mins) in enumerate(ops, 1):
                    BoMOperation.objects.create(bom=bom, name=name, work_center=wc,
                                                duration_mins=mins, sequence=i * 10)
            product.bom = bom
            product.save(update_fields=["bom"])
            return bom

        make_bom(table, [(legs, 4), (top, 1), (screws, 12)],
                 [("Assembly", wc_assembly, 60), ("Painting", wc_paint, 30),
                  ("Packing", wc_pack, 20)])
        make_bom(chair, [(legs, 4), (seat, 1), (screws, 8)],
                 [("Assembly", wc_assembly, 40), ("Packing", wc_pack, 15)])
        make_bom(dining, [(legs, 6), (top, 2), (screws, 20), (paint, 1)],
                 [("Assembly", wc_assembly, 90), ("Painting", wc_paint, 45),
                  ("Packing", wc_pack, 25)])

        # --- Customers ---
        for n, ph in [("Sharma Interiors", "+91 98100 00001"),
                      ("Gupta Furnishings", "+91 98100 00002"),
                      ("Mehta Homes", "+91 98100 00003")]:
            Customer.objects.get_or_create(name=n, defaults={"phone": ph})

        self.stdout.write(self.style.SUCCESS(
            "Done. Login admin/admin123. Try: create an SO for 10 Wooden Tables "
            "and confirm it to watch procurement auto-create a Manufacturing Order."))
