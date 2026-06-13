from django import forms
from django.forms import inlineformset_factory

from .models import PurchaseOrder, PurchaseOrderLine, Vendor


class POForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["vendor"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")


POLineFormSet = inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine,
    fields=["product", "quantity", "unit_price"],
    extra=3, can_delete=True,
    widgets={f: forms.NumberInput(attrs={"class": "inp"}) for f in ("quantity", "unit_price")},
)


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "email", "phone", "address", "lead_time_days"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")
