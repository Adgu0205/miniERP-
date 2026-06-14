from django.shortcuts import render, redirect
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta, date
import json

from core.utils import get_current_role, get_current_user, ROLE_INFO_MAP, record_audit, has_page_access, create_notification, recalculate_stock_quantity
from products.models import Product
from sales.models import SalesOrder
from purchases.models import PurchaseOrder, PurchaseOrderItem
from manufacturing.models import ManufacturingOrder, WorkOrder, BoM
from audit.models import AuditLog, Notification


@csrf_exempt
def dashboard(request):
    role = get_current_role(request)
    if not has_page_access(role, "dashboard"):
        return render(request, "no_access.html", {'page_name': 'Dashboard'})

    # Handle AJAX run_mts quick action
    if request.method == 'POST' and request.GET.get('action') == 'run_mts':
        triggers = run_mts_reordering_rules_python(request)
        return JsonResponse({'status': 'success', 'triggers': triggers})

    user_info = get_current_user(request)

    # ── Core querysets ─────────────────────────────────────────────────────
    products = Product.objects.all()
    sales_orders = SalesOrder.objects.exclude(status='cancelled')
    purchase_orders = PurchaseOrder.objects.all()
    mfg_orders = ManufacturingOrder.objects.all()

    # ── KPI: Gross Revenue ─────────────────────────────────────────────────
    total_sales_val = sales_orders.aggregate(total=Sum('total_amount'))['total'] or 0.00
    confirmed_so_count = sales_orders.exclude(status='draft').count()

    # ── KPI: Pending Deliveries ────────────────────────────────────────────
    pending_deliveries = sales_orders.filter(status__in=['confirmed', 'partially_delivered']).count()
    confirmed_so_count_pend = sales_orders.filter(status='confirmed').count()
    partially_delivered_count = sales_orders.filter(status='partially_delivered').count()

    # ── KPI: Active Productions ────────────────────────────────────────────
    active_mfg_orders = mfg_orders.filter(status__in=['confirmed', 'in_progress', 'quality_check']).count()
    total_mos = mfg_orders.count()
    completed_mos = mfg_orders.filter(status='completed').count()

    # ── KPI: Inventory Valuation ───────────────────────────────────────────
    total_products_count = products.count()
    total_inventory_value = sum(p.on_hand * p.cost_price for p in products)

    # ── KPI: Shortages ─────────────────────────────────────────────────────
    shortage_items = sum(1 for p in products if p.free_to_use < p.reorder_threshold)
    safe_stock_count = products.count() - shortage_items

    # ── KPI: Active Procurement ────────────────────────────────────────────
    total_pos_count = purchase_orders.count()
    active_purchase_orders = purchase_orders.filter(status__in=['confirmed', 'partially_received']).count()
    confirmed_pos_count = purchase_orders.filter(status='confirmed').count()
    partially_received_pos = purchase_orders.filter(status='partially_received').count()

    # ── P2: Delayed Orders (real calculation) ──────────────────────────────
    today = date.today()
    delayed_orders = SalesOrder.objects.filter(
        expected_delivery_date__lt=today,
        status__in=['draft', 'confirmed', 'partially_delivered']
    ).count()

    # ── P2: Order Fulfillment Rate (replaces fake "Uptime") ───────────────
    total_non_cancelled = SalesOrder.objects.exclude(status='cancelled').count()
    fully_delivered = SalesOrder.objects.filter(status='fully_delivered').count()
    fulfillment_rate = round((fully_delivered / total_non_cancelled * 100), 1) if total_non_cancelled > 0 else 0.0

    # ── P2: Manufacturing Efficiency ───────────────────────────────────────
    mfg_efficiency = round((completed_mos / total_mos * 100), 1) if total_mos > 0 else 0.0

    # ── P2: Monthly Revenue Trend (last 12 months, real data) ─────────────
    now = timezone.now()
    monthly_revenue = []
    monthly_labels = []
    for i in range(11, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        month_end_month = month_start.month % 12 + 1
        month_end_year = month_start.year + (1 if month_start.month == 12 else 0)
        month_end = month_start.replace(year=month_end_year, month=month_end_month, day=1)
        revenue = SalesOrder.objects.filter(
            date__gte=month_start,
            date__lt=month_end
        ).exclude(status='cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
        monthly_revenue.append(float(revenue))
        monthly_labels.append(month_start.strftime('%b %Y'))

    # ── Audit log trail ────────────────────────────────────────────────────
    recent_activities = AuditLog.objects.all().order_by('-timestamp')[:5]

    # ── Notification logs ──────────────────────────────────────────────────
    notifications_list = Notification.objects.all().order_by('-timestamp')[:10]
    unread_notifications = Notification.objects.filter(read=False).count()

    # ── Smart Recommendations (math-based, no AI branding) ───────────────
    insights = []

    # --- Recommendation 1: Stock coverage ratio per product ---
    # For each product below threshold, compute deficit ratio = (threshold - free_to_use) / threshold
    # Sort by severity (highest deficit ratio first), show top 3
    shortage_products = [
        p for p in products if p.reorder_threshold > 0 and p.free_to_use < p.reorder_threshold
    ]
    if shortage_products:
        # Sort by deficit severity descending
        shortage_products_sorted = sorted(
            shortage_products,
            key=lambda p: (p.reorder_threshold - p.free_to_use) / p.reorder_threshold,
            reverse=True
        )
        top_short = shortage_products_sorted[:3]
        parts = []
        for p in top_short:
            deficit = p.reorder_threshold - p.free_to_use
            ratio = round((deficit / p.reorder_threshold) * 100, 1)
            parts.append(f"<strong>{p.name}</strong> ({ratio}% below threshold, deficit: {deficit} units)")
        insights.append(
            f"Stock replenishment required for {len(shortage_products)} product(s). "
            f"Highest priority: {'; '.join(parts)}."
        )
    else:
        insights.append(
            "All inventory lines are at or above their reorder thresholds. "
            "No immediate replenishment action required."
        )

    # --- Recommendation 2: MTO queue depth ---
    # Count MTO-linked MOs that are still open; flag if queue exceeds 3 orders
    pending_mtos = mfg_orders.filter(source_document__startswith='SO-').exclude(
        status__in=['completed', 'cancelled']
    ).count()
    if pending_mtos > 0:
        # Estimate average throughput: completed MOs / total non-cancelled MOs
        total_closeable = mfg_orders.exclude(status='cancelled').count()
        completion_ratio = round((mfg_orders.filter(status='completed').count() / total_closeable * 100), 1) if total_closeable > 0 else 0.0
        if pending_mtos > 3:
            insights.append(
                f"MTO queue depth is <strong>{pending_mtos} open manufacturing orders</strong>. "
                f"With a current completion ratio of {completion_ratio}%, production capacity may be constrained. "
                f"Consider scheduling additional shifts or batching work orders."
            )
        else:
            insights.append(
                f"{pending_mtos} MTO-linked manufacturing order(s) are active. "
                f"Current production completion ratio: {completion_ratio}%. Queue is within normal bounds."
            )

    # --- Recommendation 3: Delivery punctuality ---
    # Overdue rate = delayed_orders / pending_deliveries
    if delayed_orders > 0 and pending_deliveries > 0:
        overdue_rate = round((delayed_orders / pending_deliveries) * 100, 1)
        insights.append(
            f"<strong>{delayed_orders} of {pending_deliveries} pending delivery order(s)</strong> have passed their "
            f"expected delivery date ({overdue_rate}% overdue rate). "
            f"Expedite dispatch for overdue orders to reduce delay exposure."
        )
    elif fulfillment_rate >= 90:
        insights.append(
            f"Order fulfilment rate is <strong>{fulfillment_rate}%</strong>. "
            f"Delivery operations are meeting commitments within acceptable margins."
        )
    elif fulfillment_rate > 0:
        insights.append(
            f"Order fulfilment rate is <strong>{fulfillment_rate}%</strong>. "
            f"A rate below 90% indicates incomplete delivery chains. Review partially delivered orders."
        )

    # --- Recommendation 4: Manufacturing throughput ---
    # Only show if there is meaningful completion data
    if mfg_efficiency > 0:
        total_mos_all = mfg_orders.count()
        in_progress_mos = mfg_orders.filter(status__in=['confirmed', 'in_progress', 'quality_check']).count()
        insights.append(
            f"Manufacturing completion rate: <strong>{mfg_efficiency}%</strong> across {total_mos_all} total production orders "
            f"({in_progress_mos} currently in progress). "
            + ("Throughput is on track." if mfg_efficiency >= 75 else "Throughput is below the 75% benchmark — review work order bottlenecks.")
        )

    # ── Data for Chart.js ─────────────────────────────────────────────────
    chart_products = products.filter(sales_price__gt=0)[:5]
    chart_labels = [p.sku for p in chart_products]
    chart_free = [p.free_to_use for p in chart_products]
    chart_reserved = [p.reserved for p in chart_products]

    context = {
        'role': role,
        'user_info': user_info,
        'total_sales_val': float(total_sales_val),
        'confirmed_so_count': confirmed_so_count,
        'pending_deliveries': pending_deliveries,
        'confirmed_so_count_pend': confirmed_so_count_pend,
        'partially_delivered_count': partially_delivered_count,
        'active_mfg_orders': active_mfg_orders,
        'total_mos': total_mos,
        'completed_mos': completed_mos,
        'total_inventory_value': float(total_inventory_value),
        'total_products_count': total_products_count,
        'shortage_items': shortage_items,
        'safe_stock_count': safe_stock_count,
        'active_purchase_orders': active_purchase_orders,
        'total_pos_count': total_pos_count,
        'confirmed_pos_count': confirmed_pos_count,
        'partially_received_pos': partially_received_pos,
        'delayed_orders': delayed_orders,
        'fulfillment_rate': fulfillment_rate,
        'fully_delivered': fully_delivered,
        'total_non_cancelled': total_non_cancelled,
        'mfg_efficiency': mfg_efficiency,
        'recent_activities': recent_activities,
        'notifications_list': notifications_list,
        'unread_notifications': unread_notifications,
        'insights': insights,
        'chart_labels': chart_labels,
        'chart_free': chart_free,
        'chart_reserved': chart_reserved,
        # P2: Real monthly trend
        'monthly_revenue': json.dumps(monthly_revenue),
        'monthly_labels': json.dumps(monthly_labels),
    }

    return render(request, "dashboard.html", context)


@csrf_exempt
def switch_role(request):
    role = request.POST.get('role', 'admin') or request.GET.get('role', 'admin')
    if role in ROLE_INFO_MAP:
        request.session['current_role'] = role
        request.session['current_user'] = ROLE_INFO_MAP[role]
        record_audit(request, "System", "User Login", f"Switched active role to {ROLE_INFO_MAP[role]['name']} ({role})")

    # Redirect to referring page or dashboard
    next_page = request.META.get('HTTP_REFERER', '/')
    return redirect(next_page)


def run_mts_reordering_rules_python(request):
    products = Product.objects.all()
    trigger_count = 0
    for p in products:
        if p.procure_strategy == 'MTS' and p.reorder_threshold > 0:
            if p.free_to_use < p.reorder_threshold:
                # check if active PO or MO exists for this product to prevent duplicate triggers
                has_active_mo = ManufacturingOrder.objects.filter(product=p, status__in=['draft', 'confirmed', 'in_progress']).exists()
                has_active_po = PurchaseOrder.objects.filter(items__product=p, status__in=['draft', 'confirmed', 'partially_received']).exists()
                if has_active_mo or has_active_po:
                    continue

                # Replenish quantity
                replenish_qty = max(p.reorder_threshold * 2, (p.reorder_threshold - p.free_to_use) + p.reorder_threshold)

                if p.procurement_type == 'Manufacturing' and hasattr(p, 'bom'):
                    mo = ManufacturingOrder.objects.create(
                        product=p, quantity=replenish_qty, bom=p.bom,
                        assignee="MTS Reordering Engine", status='confirmed',
                        source_document="Reordering Rule (MTS)"
                    )
                    # Create work orders
                    for op in p.bom.operations.all():
                        WorkOrder.objects.create(
                            manufacturing_order=mo,
                            operation=op.operation_name,
                            work_center=op.work_center,
                            duration_minutes=op.duration_minutes,
                            status='pending'
                        )
                    # Reserve components
                    for comp in p.bom.components.all():
                        comp_prod = comp.product
                        comp_prod.reserved += comp.quantity * replenish_qty
                        comp_prod.save()
                        recalculate_stock_quantity(comp_prod.id)

                    trigger_count += 1
                    create_notification("low_stock", f"MTS Reordering: Created MO-{mo.id:03d} for {replenish_qty}x {p.name}")
                elif p.procurement_type == 'Purchase':
                    po = PurchaseOrder.objects.create(
                        vendor_name=p.vendor or "Default Supplier",
                        total_amount=p.cost_price * replenish_qty, status='confirmed',
                        source_document="Reordering Rule (MTS)"
                    )
                    PurchaseOrderItem.objects.create(
                        purchase_order=po, product=p, quantity=replenish_qty,
                        unit_cost=p.cost_price, received_quantity=0
                    )
                    trigger_count += 1
                    create_notification("low_stock", f"MTS Reordering: Created PO-{po.id:03d} for {replenish_qty}x {p.name}")
    return trigger_count
