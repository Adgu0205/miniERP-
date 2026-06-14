from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory

from apps.products.models import ProcurementType, Product

from .models import PurchaseOrder, PurchaseOrderLine, Vendor


class POForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["vendor"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")


class POLineForm(forms.ModelForm):
    """Purchase lines buy *purchasable* products (procurement type = Purchase)."""
    class Meta:
        model = PurchaseOrderLine
        fields = ["product", "quantity", "unit_price"]
        widgets = {"quantity": forms.NumberInput(attrs={"class": "inp"}),
                   "unit_price": forms.NumberInput(attrs={"class": "inp"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        buyable = Q(procurement_type=ProcurementType.BUY)
        if self.instance and self.instance.product_id:
            buyable |= Q(pk=self.instance.product_id)
        self.fields["product"].queryset = Product.objects.filter(buyable)
        self.fields["product"].widget.attrs["class"] = "inp"


POLineFormSet = inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine, form=POLineForm, extra=3, can_delete=True,
)


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "email", "phone", "address", "lead_time_days"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")
