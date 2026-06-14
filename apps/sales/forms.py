from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory

from apps.products.models import Product

from .models import Customer, SalesOrder, SalesOrderLine


class SOForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ["customer", "deadline"]
        widgets = {"deadline": forms.DateInput(attrs={"type": "date", "class": "inp"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].widget.attrs.setdefault("class", "inp")


class SOLineForm(forms.ModelForm):
    """Sales lines sell *sellable* products (finished goods with a sale price)."""
    class Meta:
        model = SalesOrderLine
        fields = ["product", "quantity", "unit_price"]
        widgets = {"quantity": forms.NumberInput(attrs={"class": "inp"}),
                   "unit_price": forms.NumberInput(attrs={"class": "inp"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sellable = Q(sale_price__gt=0)
        if self.instance and self.instance.product_id:
            sellable |= Q(pk=self.instance.product_id)  # keep existing selection
        self.fields["product"].queryset = Product.objects.filter(sellable)
        self.fields["product"].widget.attrs["class"] = "inp"


SOLineFormSet = inlineformset_factory(
    SalesOrder, SalesOrderLine, form=SOLineForm, extra=3, can_delete=True,
)


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "address"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")
