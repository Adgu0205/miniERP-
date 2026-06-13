from django import forms
from django.forms import inlineformset_factory

from .models import Customer, SalesOrder, SalesOrderLine


class SOForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ["customer", "deadline"]
        widgets = {"deadline": forms.DateInput(attrs={"type": "date", "class": "inp"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].widget.attrs.setdefault("class", "inp")


SOLineFormSet = inlineformset_factory(
    SalesOrder, SalesOrderLine,
    fields=["product", "quantity", "unit_price"],
    extra=3, can_delete=True,
    widgets={f: forms.NumberInput(attrs={"class": "inp"}) for f in ("quantity", "unit_price")},
)


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "address"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")
