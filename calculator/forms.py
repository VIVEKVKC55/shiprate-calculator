from django import forms


class ShipmentForm(forms.Form):
    PAYMENT_CHOICES = (("prepaid", "Prepaid"), ("cod", "Cash on delivery (COD)"))

    pickup_postcode = forms.CharField(label="Pickup pincode", max_length=6, min_length=6)
    delivery_postcode = forms.CharField(label="Delivery pincode", max_length=6, min_length=6)
    weight = forms.DecimalField(label="Shipment weight (kg)", min_value=0.001, max_digits=8, decimal_places=3)
    payment_mode = forms.ChoiceField(label="Payment mode", choices=PAYMENT_CHOICES, widget=forms.RadioSelect)
    order_value = forms.DecimalField(label="Order value (₹)", min_value=0, max_digits=10, decimal_places=2)
    length = forms.DecimalField(label="Length (cm)", required=False, min_value=0.01, max_digits=8, decimal_places=2)
    width = forms.DecimalField(label="Width (cm)", required=False, min_value=0.01, max_digits=8, decimal_places=2)
    height = forms.DecimalField(label="Height (cm)", required=False, min_value=0.01, max_digits=8, decimal_places=2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "payment_mode":
                field.widget.attrs["class"] = "form-control"
                field.widget.attrs["placeholder"] = "Enter value"
        for name in ("pickup_postcode", "delivery_postcode"):
            self.fields[name].widget.attrs.update({"placeholder": "e.g. 110001", "autocomplete": "postal-code"})
        self.fields["weight"].widget.attrs.update({"placeholder": "e.g. 1.25", "step": "0.001"})
        self.fields["order_value"].widget.attrs.update({"placeholder": "e.g. 1499", "step": "0.01"})
        for name in ("length", "width", "height"):
            self.fields[name].widget.attrs.update({"placeholder": "cm", "step": "0.01"})

    def clean_pickup_postcode(self):
        return self._validate_postcode("pickup_postcode")

    def clean_delivery_postcode(self):
        return self._validate_postcode("delivery_postcode")

    def _validate_postcode(self, field):
        value = self.cleaned_data[field]
        if not value.isascii() or not value.isdigit() or len(value) != 6 or value[0] == "0":
            raise forms.ValidationError("Enter a valid six-digit Indian pincode.")
        return value

    def clean(self):
        cleaned = super().clean()
        keys = ("length", "width", "height")
        dimensions = [cleaned.get(key) for key in keys]
        if any(value is not None for value in dimensions) and not all(value is not None for value in dimensions):
            for key, value in zip(keys, dimensions):
                if value is None:
                    self.add_error(key, "Enter all three dimensions, or leave all dimensions blank.")
        return cleaned
