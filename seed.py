import os
import django
from datetime import datetime, timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mini_erp.settings')
django.setup()

from products.models import Product
from manufacturing.models import BoM, BoMComponent, BoMOperation, ManufacturingOrder, WorkOrder
from sales.models import SalesOrder, SalesOrderItem
from purchases.models import PurchaseOrder, PurchaseOrderItem
from inventory.models import StockLedgerEntry
from audit.models import AuditLog, Notification

def seed():
    print("Deleting existing database data...")
    Product.objects.all().delete()
    BoM.objects.all().delete()
    BoMComponent.objects.all().delete()
    BoMOperation.objects.all().delete()
    ManufacturingOrder.objects.all().delete()
    WorkOrder.objects.all().delete()
    SalesOrder.objects.all().delete()
    SalesOrderItem.objects.all().delete()
    PurchaseOrder.objects.all().delete()
    PurchaseOrderItem.objects.all().delete()
    StockLedgerEntry.objects.all().delete()
    AuditLog.objects.all().delete()
    Notification.objects.all().delete()

    print("Creating Products...")
    prod_wt = Product.objects.create(
        name="Wooden Table", sku="W-TBL-01", category="Furniture",
        cost_price=80.00, sales_price=150.00, on_hand=8, reserved=0,
        procure_strategy="MTO", procure_type="Manufacturing", vendor="Timber Supplier Co",
        reorder_threshold=2
    )
    prod_dt = Product.objects.create(
        name="Dining Table", sku="D-TBL-02", category="Furniture",
        cost_price=180.00, sales_price=350.00, on_hand=3, reserved=0,
        procure_strategy="MTO", procure_type="Manufacturing", vendor="Timber Supplier Co",
        reorder_threshold=1
    )
    prod_oc = Product.objects.create(
        name="Office Chair", sku="O-CHR-03", category="Furniture",
        cost_price=50.00, sales_price=120.00, on_hand=15, reserved=0,
        procure_strategy="MTS", procure_type="Purchase", vendor="Office World",
        reorder_threshold=5
    )
    prod_leg = Product.objects.create(
        name="Wooden Legs", sku="COMP-LEG", category="Components",
        cost_price=10.00, sales_price=0.00, on_hand=40, reserved=0,
        procure_strategy="MTS", procure_type="Purchase", vendor="Timber Supplier Co",
        reorder_threshold=15
    )
    prod_top = Product.objects.create(
        name="Wooden Top", sku="COMP-TOP", category="Components",
        cost_price=25.00, sales_price=0.00, on_hand=12, reserved=0,
        procure_strategy="MTS", procure_type="Purchase", vendor="Timber Supplier Co",
        reorder_threshold=5
    )
    prod_scr = Product.objects.create(
        name="Screws", sku="COMP-SCR", category="Components",
        cost_price=0.10, sales_price=0.00, on_hand=280, reserved=0,
        procure_strategy="MTS", procure_type="Purchase", vendor="Hardware Goods LLC",
        reorder_threshold=100
    )
    prod_pnt = Product.objects.create(
        name="Paint Can", sku="COMP-PNT", category="Components",
        cost_price=8.00, sales_price=0.00, on_hand=15, reserved=0,
        procure_strategy="MTS", procure_type="Purchase", vendor="Sherwin Paints",
        reorder_threshold=4
    )

    print("Creating BoMs...")
    bom_wt = BoM.objects.create(name="Bill of Materials - Wooden Table", product=prod_wt)
    BoMComponent.objects.create(bom=bom_wt, product=prod_leg, quantity=4)
    BoMComponent.objects.create(bom=bom_wt, product=prod_top, quantity=1)
    BoMComponent.objects.create(bom=bom_wt, product=prod_scr, quantity=12)

    BoMOperation.objects.create(bom=bom_wt, name="Assembly", work_center="Assembly Line", duration=60)
    BoMOperation.objects.create(bom=bom_wt, name="Painting", work_center="Painting Station", duration=30)
    BoMOperation.objects.create(bom=bom_wt, name="Packing", work_center="Packaging Unit", duration=20)

    bom_dt = BoM.objects.create(name="Bill of Materials - Dining Table", product=prod_dt)
    BoMComponent.objects.create(bom=bom_dt, product=prod_leg, quantity=4)
    BoMComponent.objects.create(bom=bom_dt, product=prod_top, quantity=1)
    BoMComponent.objects.create(bom=bom_dt, product=prod_scr, quantity=16)

    BoMOperation.objects.create(bom=bom_dt, name="Assembly", work_center="Assembly Line", duration=80)
    BoMOperation.objects.create(bom=bom_dt, name="Painting", work_center="Painting Station", duration=40)
    BoMOperation.objects.create(bom=bom_dt, name="Packing", work_center="Packaging Unit", duration=30)

    print("Creating Sales Orders...")
    so1 = SalesOrder.objects.create(customer_name="John Doe Furniture Store", total_amount=450.00, status="draft")
    SalesOrderItem.objects.create(sales_order=so1, product=prod_wt, quantity=3, unit_price=150.00, delivered_quantity=0)

    so2 = SalesOrder.objects.create(customer_name="Acme Corp Office Replenishment", total_amount=1200.00, status="confirmed")
    SalesOrderItem.objects.create(sales_order=so2, product=prod_oc, quantity=10, unit_price=120.00, delivered_quantity=0)
    # Reserve stock for SO2
    prod_oc.reserved += 10
    prod_oc.save()

    so3 = SalesOrder.objects.create(customer_name="Luxury Home Designs", total_amount=350.00, status="fully_delivered")
    SalesOrderItem.objects.create(sales_order=so3, product=prod_dt, quantity=1, unit_price=350.00, delivered_quantity=1)

    print("Creating Purchase Orders...")
    po1 = PurchaseOrder.objects.create(vendor_name="Timber Supplier Co", total_amount=500.00, status="draft")
    PurchaseOrderItem.objects.create(purchase_order=po1, product=prod_top, quantity=20, unit_price=25.00, received_quantity=0)

    po2 = PurchaseOrder.objects.create(vendor_name="Hardware Goods LLC", total_amount=20.00, status="fully_received")
    PurchaseOrderItem.objects.create(purchase_order=po2, product=prod_scr, quantity=200, unit_price=0.10, received_quantity=200)

    print("Creating Manufacturing Orders...")
    mo1 = ManufacturingOrder.objects.create(
        product=prod_wt, quantity=4, bom=bom_wt, status="completed", assignee="John Operative"
    )
    WorkOrder.objects.create(manufacturing_order=mo1, name="Assembly", work_center="Assembly Line", duration=60, elapsed_seconds=3600, status="completed")
    WorkOrder.objects.create(manufacturing_order=mo1, name="Painting", work_center="Painting Station", duration=30, elapsed_seconds=1800, status="completed")
    WorkOrder.objects.create(manufacturing_order=mo1, name="Packing", work_center="Packaging Unit", duration=20, elapsed_seconds=1200, status="completed")

    mo2 = ManufacturingOrder.objects.create(
        product=prod_dt, quantity=2, bom=bom_dt, status="confirmed", assignee="Mark Builder"
    )
    WorkOrder.objects.create(manufacturing_order=mo2, name="Assembly", work_center="Assembly Line", duration=80, elapsed_seconds=0, status="pending")
    WorkOrder.objects.create(manufacturing_order=mo2, name="Painting", work_center="Painting Station", duration=40, elapsed_seconds=0, status="pending")
    WorkOrder.objects.create(manufacturing_order=mo2, name="Packing", work_center="Packaging Unit", duration=30, elapsed_seconds=0, status="pending")
    # Reserve components for MO2
    prod_leg.reserved += 8
    prod_top.reserved += 2
    prod_scr.reserved += 32
    prod_leg.save()
    prod_top.save()
    prod_scr.save()

    print("Creating Stock Ledger Entries...")
    StockLedgerEntry.objects.create(product=prod_wt, movement_type="Manufacturing Production", quantity_change=4, source_document=f"MO-{mo1.id:03d}", user="John Operative")
    StockLedgerEntry.objects.create(product=prod_leg, movement_type="Manufacturing Consumption", quantity_change=-16, source_document=f"MO-{mo1.id:03d}", user="John Operative")
    StockLedgerEntry.objects.create(product=prod_top, movement_type="Manufacturing Consumption", quantity_change=-4, source_document=f"MO-{mo1.id:03d}", user="John Operative")
    StockLedgerEntry.objects.create(product=prod_scr, movement_type="Manufacturing Consumption", quantity_change=-48, source_document=f"MO-{mo1.id:03d}", user="John Operative")
    StockLedgerEntry.objects.create(product=prod_dt, movement_type="Sales Delivery", quantity_change=-1, source_document=f"SO-{so3.id:03d}", user="Sarah Sales")
    StockLedgerEntry.objects.create(product=prod_scr, movement_type="Purchase Receipt", quantity_change=200, source_document=f"PO-{po2.id:03d}", user="Paul Purchase")

    print("Creating Audit Logs...")
    AuditLog.objects.create(module="Manufacturing", action="Order Creation", details=f"Manufacturing Order MO-{mo1.id:03d} created for 4x Wooden Table", user="John Operative")
    AuditLog.objects.create(module="Manufacturing", action="Status Change", details=f"MO-{mo1.id:03d} status changed from in_progress to completed", user="John Operative")
    AuditLog.objects.create(module="Sales", action="Order Delivery", details=f"Sales Order SO-{so3.id:03d} fully delivered to Luxury Home Designs", user="Sarah Sales")
    AuditLog.objects.create(module="Purchase", action="Receipt Validation", details=f"Purchase Order PO-{po2.id:03d} received 200 Screws", user="Paul Purchase")

    print("Creating Notifications...")
    Notification.objects.create(type="purchase_received", message=f"Purchase Order PO-{po2.id:03d} has been fully received. 200x Screws added to stock.")
    Notification.objects.create(type="low_stock", message="Low stock alert: Wooden Top (COMP-TOP) is at 12 units (threshold is 5, but on reservations check, free stock is low).")

    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed()
