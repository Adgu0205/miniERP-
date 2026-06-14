from django.contrib import admin
from django.urls import path
import core.views
import products.views
import sales.views
import purchases.views
import manufacturing.views
import inventory.views
import audit.views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Core Dashboard
    path('', core.views.dashboard, name='dashboard'),
    path('index.html', core.views.dashboard, name='dashboard_index'),
    path('role/switch/', core.views.switch_role, name='switch_role'),
    
    # Products
    path('products/', products.views.products_list, name='products_list'),
    path('products/create/', products.views.create_product, name='create_product'),
    path('products/edit/<int:product_id>/', products.views.edit_product, name='edit_product'),
    
    # Sales
    path('sales/', sales.views.sales_pipeline, name='sales_pipeline'),
    path('sales/create/', sales.views.create_sales_order, name='create_sales_order'),
    path('sales/<int:so_id>/confirm/', sales.views.confirm_sales_order, name='confirm_sales_order'),
    path('sales/<int:so_id>/deliver/', sales.views.deliver_sales_order, name='deliver_sales_order'),
    path('sales/<int:so_id>/cancel/', sales.views.cancel_sales_order, name='cancel_sales_order'),
    path('sales/<int:so_id>/edit/', sales.views.edit_sales_order, name='edit_sales_order'),
    
    # Purchases
    path('purchases/', purchases.views.purchase_list, name='purchase_list'),
    path('purchases/create/', purchases.views.create_purchase_order, name='create_purchase_order'),
    path('purchases/<int:po_id>/confirm/', purchases.views.confirm_purchase_order, name='confirm_purchase_order'),
    path('purchases/<int:po_id>/receive/', purchases.views.receive_purchase_order, name='receive_purchase_order'),
    path('purchases/<int:po_id>/cancel/', purchases.views.cancel_purchase_order, name='cancel_purchase_order'),
    path('purchases/<int:po_id>/edit/', purchases.views.edit_purchase_order, name='edit_purchase_order'),
    
    # Manufacturing
    path('manufacturing/', manufacturing.views.manufacturing_cockpit, name='manufacturing_cockpit'),
    path('manufacturing/create/', manufacturing.views.create_mo, name='create_mo'),
    path('manufacturing/<int:mo_id>/confirm/', manufacturing.views.confirm_mo, name='confirm_mo'),
    path('manufacturing/<int:mo_id>/complete/', manufacturing.views.complete_mo, name='complete_mo'),
    path('manufacturing/<int:mo_id>/cancel/', manufacturing.views.cancel_mo, name='cancel_mo'),
    path('manufacturing/<int:mo_id>/edit/', manufacturing.views.edit_mo, name='edit_mo'),
    path('manufacturing/<int:mo_id>/start/', manufacturing.views.start_mo, name='start_mo'),
    
    # Work Orders
    path('manufacturing/workorder/<int:wo_id>/start/', manufacturing.views.start_work_order, name='start_work_order'),
    path('manufacturing/workorder/<int:wo_id>/complete/', manufacturing.views.complete_work_order, name='complete_work_order'),
    
    # BoMs
    path('bom/', manufacturing.views.bom_list, name='bom_list'),
    path('bom/create/', manufacturing.views.create_bom, name='create_bom'),
    
    # Inventory
    path('inventory/', inventory.views.inventory_valuation, name='inventory_valuation'),
    path('inventory/adjust/', inventory.views.post_stock_adjustment, name='post_stock_adjustment'),
    path('inventory/movements/', inventory.views.inventory_movements, name='inventory_movements'),
    path('inventory/movements/export/', inventory.views.export_movements_csv, name='export_movements_csv'),
    path('ledger/', inventory.views.stock_ledger, name='stock_ledger'),
    path('ledger/export/', inventory.views.export_ledger_csv, name='export_ledger_csv'),
    
    # Audit & Notifications
    path('audit/', audit.views.audit_logs, name='audit_logs'),
    path('audit/export/', audit.views.export_audit_csv, name='export_audit_csv'),
    path('notifications/read/', audit.views.mark_notifications_read, name='mark_notifications_read'),
]
