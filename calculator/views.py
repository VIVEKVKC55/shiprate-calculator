from django.shortcuts import render

from .forms import ShipmentForm
from .services import ShiprocketError, check_serviceability


def home(request):
    if request.method == "POST":
        form = ShipmentForm(request.POST)
        if form.is_valid():
            shipment = form.cleaned_data
            try:
                couriers = check_serviceability(
                    pickup_postcode=shipment["pickup_postcode"],
                    delivery_postcode=shipment["delivery_postcode"],
                    weight=shipment["weight"],
                    cod=shipment["payment_mode"] == "cod",
                )
            except ShiprocketError as exc:
                return render(request, "calculator/results.html", {"form_data": shipment, "error": str(exc)})
            return render(request, "calculator/results.html", {"form_data": shipment, "couriers": couriers})
    else:
        form = ShipmentForm()
    return render(request, "calculator/home.html", {"form": form})


def about(request):
    return render(request, "calculator/about.html")
