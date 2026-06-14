from django import forms
from django.forms import inlineformset_factory

from apps.products.models import ProcurementType, Product

from .models import BoM, BoMLine, BoMOperation, ManufacturingOrder, WorkCenter


class MOForm(forms.ModelForm):
    class Meta:
        model = ManufacturingOrder
        fields = ["product", "bom", "quantity", "assignee", "deadline"]
        widgets = {"deadline": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        mfg = Product.objects.filter(procurement_type=ProcurementType.MANUFACTURE)
        self.fields["product"].queryset = mfg if mfg.exists() else Product.objects.all()
        # Only active BoMs; scoped to the order's product when editing.
        boms = BoM.objects.filter(is_active=True)
        if self.instance and self.instance.product_id:
            boms = boms.filter(product_id=self.instance.product_id)
        self.fields["bom"].queryset = boms
        self.fields["bom"].empty_label = "Auto (resolve from product)"
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")


class BoMForm(forms.ModelForm):
    class Meta:
        model = BoM
        fields = ["product", "name", "quantity", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "inp")


BoMLineFormSet = inlineformset_factory(
    BoM, BoMLine, fields=["component", "quantity"], extra=3, can_delete=True,
    widgets={"component": forms.Select(attrs={"class": "inp"}),
             "quantity": forms.NumberInput(attrs={"class": "inp"})},
)

BoMOperationFormSet = inlineformset_factory(
    BoM, BoMOperation, fields=["sequence", "name", "work_center", "duration_mins"],
    extra=2, can_delete=True,
    widgets={
        "sequence": forms.NumberInput(attrs={"class": "inp"}),
        "name": forms.TextInput(attrs={"class": "inp"}),
        "work_center": forms.Select(attrs={"class": "inp"}),
        "duration_mins": forms.NumberInput(attrs={"class": "inp"}),
    },
)
