from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log
from apps.audit.models import Action
from apps.users.permissions import module_required

from .forms import ProductForm
from .models import Product


@module_required("products")
def product_list(request):
    qs = Product.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if request.GET.get("export") == "csv":
        from config.utils import csv_response
        return csv_response("products.csv",
            ["Name", "SKU", "Type", "Strategy", "Source", "On Hand",
             "Reserved", "Free", "Cost", "Sale"],
            [(p.name, p.sku, p.get_product_type_display(), p.get_strategy_display(),
              p.get_procurement_type_display(), p.on_hand, p.reserved,
              p.free_to_use, p.cost_price, p.sale_price) for p in qs])
    return render(request, "products/list.html", {"products": qs, "q": q})


@module_required("products")
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    old_price = product.sale_price if product else None
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        if product is None:
            log("products", Action.CREATE, obj, user=request.user,
                description=f"Product created (cost {obj.cost_price}, sale {obj.sale_price})")
        else:
            if old_price != obj.sale_price:
                log("products", Action.PRICE, obj, user=request.user,
                    field="sale_price", old=old_price, new=obj.sale_price)
            log("products", Action.UPDATE, obj, user=request.user)
        messages.success(request, f"Saved {obj.name}.")
        return redirect("products:list")
    return render(request, "products/form.html", {"form": form, "product": product})
