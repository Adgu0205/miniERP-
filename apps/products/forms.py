from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name", "sku", "product_type", "sale_price", "cost_price",
            "strategy", "procure_on_demand", "procurement_type", "vendor", "bom",
            "reorder_point", "manufacture_lead_days",
        ]
        widgets = {
            f: forms.Select(attrs={"class": "inp"})
            for f in ("product_type", "strategy", "procurement_type", "vendor", "bom")
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "inp"
            if isinstance(field.widget, forms.CheckboxInput):
                css = "h-4 w-4"
            field.widget.attrs.setdefault("class", css)
        # BoM choices belong to THIS product only (empty for a brand-new product)
        from apps.manufacturing.models import BoM
        if self.instance and self.instance.pk:
            self.fields["bom"].queryset = BoM.objects.filter(product=self.instance)
        else:
            self.fields["bom"].queryset = BoM.objects.none()
        self.fields["bom"].empty_label = "— select after saving —"
