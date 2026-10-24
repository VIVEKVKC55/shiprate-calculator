from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .forms import ShipmentForm
from .services import ShiprocketError, check_serviceability, lookup_pincode_location


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
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"ok": False, "error": str(exc)}, status=502)
                return render(request, "calculator/results.html", {"form_data": shipment, "error": str(exc)})
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": True, "couriers": couriers})
            return render(request, "calculator/results.html", {"form_data": shipment, "couriers": couriers})
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    else:
        form = ShipmentForm()
    return render(request, "calculator/home.html", {"form": form})


def about(request):
    return render(request, "calculator/about.html")


@require_GET
def pincode_location(request, pincode):
    if len(pincode) != 6 or not pincode.isascii() or not pincode.isdigit() or pincode.startswith("0"):
        return JsonResponse({"ok": False}, status=400)
    location = lookup_pincode_location(pincode)
    if location is None:
        return JsonResponse({"ok": False, "message": "Location not found"}, status=404)
    return JsonResponse({"ok": True, **location})
