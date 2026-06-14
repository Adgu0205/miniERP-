from audit.models import AuditLog, Notification
from products.models import Product

ROLE_ACCESS_MAP = {
    'admin': ["dashboard", "products_list", "sales_pipeline", "purchase_list", "manufacturing_cockpit", "bom_list", "audit_logs"],
    'sales_user': ["dashboard", "products_list", "sales_pipeline"],
    'purchase_user': ["dashboard", "products_list", "purchase_list"],
    'manufacturing_user': ["dashboard", "manufacturing_cockpit", "bom_list"],
    'inventory_manager': ["dashboard", "products_list"],
    'business_owner': ["dashboard", "products_list", "sales_pipeline", "purchase_list", "manufacturing_cockpit", "bom_list"]
}

ROLE_INFO_MAP = {
    'admin': {'name': 'Admin User', 'role': 'admin', 'letters': 'AD'},
    'sales_user': {'name': 'Sales Representative', 'role': 'sales_user', 'letters': 'SR'},
    'purchase_user': {'name': 'Procurement Manager', 'role': 'purchase_user', 'letters': 'PM'},
    'manufacturing_user': {'name': 'Shop Floor Operator', 'role': 'manufacturing_user', 'letters': 'SO'},
    'inventory_manager': {'name': 'Stockroom Controller', 'role': 'inventory_manager', 'letters': 'SC'},
    'business_owner': {'name': 'Shiv (CEO)', 'role': 'business_owner', 'letters': 'SV'}
}

def init_role_session(request):
    if 'current_role' not in request.session:
        request.session['current_role'] = 'admin'
    if 'current_user' not in request.session:
        request.session['current_user'] = ROLE_INFO_MAP['admin']

def get_current_role(request):
    init_role_session(request)
    return request.session['current_role']

def get_current_user(request):
    init_role_session(request)
    return request.session['current_user']

def has_page_access(role, page_name):
    allowed = ROLE_ACCESS_MAP.get(role, [])
    return page_name in allowed

def get_role_permissions(role):
    return {
        'can_edit_products': role in ['admin', 'inventory_manager'],
        'can_edit_sales': role in ['admin', 'sales_user'],
        'can_edit_purchases': role in ['admin', 'purchase_user'],
        'can_edit_manufacturing': role in ['admin', 'manufacturing_user'],
        'can_edit_bom': role in ['admin', 'manufacturing_user'],
        'can_adjust_inventory': role in ['admin', 'inventory_manager'],
        'can_view_audit_logs': role == 'admin',
        'is_read_only': role == 'business_owner'
    }

def record_audit(request, module, action, details, record_id='', record_type='', field_changed='-', old_value='-', new_value='-', action_type='Create'):
    user_name = get_current_user(request)['name']
    AuditLog.objects.create(
        module=module,
        action=action,
        details=details,
        user=user_name,
        record_id=record_id,
        record_type=record_type,
        field_changed=field_changed,
        old_value=old_value,
        new_value=new_value,
        action_type=action_type
    )

def create_notification(notif_type, message):
    Notification.objects.create(
        type=notif_type,
        message=message
    )

def recalculate_stock_quantity(product_id):
    try:
        p = Product.objects.get(id=product_id)
        # Check reorder threshold alert
        if p.free_to_use < p.reorder_threshold and p.status != "Low Stock":
            p.status = "Low Stock"
            create_notification("low_stock", f"Low stock alert: {p.name} ({p.sku}) is at {p.on_hand} units.")
        elif p.free_to_use >= p.reorder_threshold:
            p.status = "Active"
        p.save()
    except Product.DoesNotExist:
        pass
