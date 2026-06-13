from django import forms

from apps.products.models import ProcurementType, Product

from .models import BoM, ManufacturingOrder


class MOForm(forms.ModelForm):
    class Meta:
        model = ManufacturingOrder
        fields = ["product", "bom", "quantity", "assignee", "deadline"]
        widgets = {"deadline": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            procurement_type=ProcurementType.MANUFACTURE
        ) or Product.objects.all()
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
