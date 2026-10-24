from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from .forms import ShipmentForm
from .services import (
    TOKEN_CACHE_KEY,
    ShiprocketAuthenticationError,
    ShiprocketUnavailableError,
    check_serviceability,
)


def valid_payload(**changes):
    data = {
        "pickup_postcode": "110001", "delivery_postcode": "400001", "weight": "1.25",
        "payment_mode": "prepaid", "order_value": "1250.00", "length": "", "width": "", "height": "",
    }
    data.update(changes)
    return data


class ShipmentFormTests(SimpleTestCase):
    def test_valid_form(self):
        self.assertTrue(ShipmentForm(valid_payload()).is_valid())

    def test_rejects_invalid_pincodes(self):
        for field in ("pickup_postcode", "delivery_postcode"):
            form = ShipmentForm(valid_payload(**{field: "1234x6"}))
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_rejects_non_positive_weight(self):
        self.assertFalse(ShipmentForm(valid_payload(weight="0")).is_valid())

    def test_rejects_negative_order_value(self):
        self.assertFalse(ShipmentForm(valid_payload(order_value="-1")).is_valid())

    def test_dimensions_must_be_all_present_or_all_blank(self):
        form = ShipmentForm(valid_payload(length="10"))
        self.assertFalse(form.is_valid())
        self.assertIn("width", form.errors)


class ShiprocketServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(SHIPROCKET_EMAIL="seller@example.com", SHIPROCKET_PASSWORD="secret", SHIPROCKET_BASE_URL="https://api.example/v1")
    @patch("calculator.services.requests.get")
    @patch("calculator.services.requests.post")
    def test_success_returns_actual_couriers_and_supported_params(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {"token": "token-1"})
        get.return_value = Mock(ok=True, status_code=200, json=lambda: {"data": {"available_courier_companies": [
            {"courier_name": "Courier B", "rate": 90, "etd": "4 days"},
            {"courier_name": "Courier A", "rate": 40, "cod": 1},
        ]}})
        result = check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1.25"), cod=False)
        self.assertEqual([row["courier_name"] for row in result], ["Courier A", "Courier B"])
        self.assertEqual(get.call_args.kwargs["params"], {
            "pickup_postcode": "110001", "delivery_postcode": "400001", "weight": "1.25", "cod": 0,
        })

    @override_settings(SHIPROCKET_EMAIL="seller@example.com", SHIPROCKET_PASSWORD="secret", SHIPROCKET_BASE_URL="https://api.example/v1")
    @patch("calculator.services.requests.post")
    def test_failed_authentication_is_safe(self, post):
        post.return_value = Mock(ok=False, status_code=401)
        with self.assertRaises(ShiprocketAuthenticationError):
            check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1"), cod=False)

    @override_settings(SHIPROCKET_EMAIL="seller@example.com", SHIPROCKET_PASSWORD="secret", SHIPROCKET_BASE_URL="https://api.example/v1")
    @patch("calculator.services.requests.post", side_effect=requests.Timeout)
    def test_auth_timeout(self, post):
        with self.assertRaises(ShiprocketUnavailableError):
            check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1"), cod=False)

    @override_settings(SHIPROCKET_EMAIL="seller@example.com", SHIPROCKET_PASSWORD="secret", SHIPROCKET_BASE_URL="https://api.example/v1")
    @patch("calculator.services.requests.get")
    @patch("calculator.services.requests.post")
    def test_expired_token_is_refreshed(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {"token": "fresh-token"})
        get.side_effect = [Mock(ok=False, status_code=401), Mock(ok=True, status_code=200, json=lambda: {"data": {"available_courier_companies": []}})]
        self.assertEqual(check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1"), cod=True), [])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(cache.get(TOKEN_CACHE_KEY), "fresh-token")
        self.assertTrue(cache.get(TOKEN_CACHE_KEY))

    @override_settings(SHIPROCKET_EMAIL="seller@example.com", SHIPROCKET_PASSWORD="secret", SHIPROCKET_BASE_URL="https://api.example/v1")
    @patch("calculator.services.requests.get", side_effect=requests.Timeout)
    @patch("calculator.services.requests.post")
    def test_serviceability_timeout(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {"token": "token-1"})
        with self.assertRaises(ShiprocketUnavailableError):
            check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1"), cod=False)

    @override_settings(SHIPROCKET_EMAIL="seller@example.com", SHIPROCKET_PASSWORD="secret", SHIPROCKET_BASE_URL="https://api.example/v1")
    @patch("calculator.services.requests.get")
    @patch("calculator.services.requests.post")
    def test_http_error_is_handled_without_leaking_response(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {"token": "token-1"})
        get.return_value = Mock(ok=False, status_code=500)
        with self.assertRaises(ShiprocketUnavailableError) as caught:
            check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1"), cod=False)
        self.assertNotIn("token-1", str(caught.exception))

    @override_settings(SHIPROCKET_EMAIL="seller@example.com", SHIPROCKET_PASSWORD="secret", SHIPROCKET_BASE_URL="https://api.example/v1")
    @patch("calculator.services.requests.post")
    def test_unexpected_auth_response_is_handled(self, post):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {"message": "no token field"})
        from .services import ShiprocketResponseError

        with self.assertRaises(ShiprocketResponseError):
            check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1"), cod=False)

    @override_settings(SHIPROCKET_EMAIL="", SHIPROCKET_PASSWORD="", SHIPROCKET_BASE_URL="https://api.example/v1")
    def test_missing_credentials_are_reported_before_network_call(self):
        from .services import ShiprocketConfigurationError

        with self.assertRaises(ShiprocketConfigurationError):
            check_serviceability(pickup_postcode="110001", delivery_postcode="400001", weight=Decimal("1"), cod=False)


class CalculatorViewTests(SimpleTestCase):
    @patch("calculator.views.check_serviceability", return_value=[{"courier_name": "Real API courier", "rate": 45}])
    def test_valid_post_displays_mocked_api_result(self, lookup):
        response = self.client.post("/", valid_payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Real API courier")
        lookup.assert_called_once()

    @patch("calculator.views.check_serviceability", return_value=[])
    def test_no_serviceable_courier_message(self, lookup):
        response = self.client.post("/", valid_payload())
        self.assertContains(response, "No serviceable couriers")

    def test_about_page_loads(self):
        self.assertEqual(self.client.get("/about/").status_code, 200)

    @patch("calculator.views.check_serviceability", return_value=[{"courier_name": "Live result", "rate": 52}])
    def test_ajax_post_returns_json_without_page_template(self, lookup):
        response = self.client.post("/", valid_payload(), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "couriers": [{"courier_name": "Live result", "rate": 52}]})
        lookup.assert_called_once()

    def test_ajax_validation_error_returns_field_messages(self):
        response = self.client.post(
            "/", valid_payload(delivery_postcode="bad"), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("delivery_postcode", response.json()["errors"])

    @patch("calculator.views.check_serviceability", side_effect=ShiprocketUnavailableError("Try again later."))
    def test_ajax_api_error_returns_safe_json_message(self, lookup):
        response = self.client.post("/", valid_payload(), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"ok": False, "error": "Try again later."})

    @patch("calculator.views.lookup_pincode_location", return_value={"city": "New Delhi", "state": "Delhi"})
    def test_pincode_lookup_returns_city_and_state(self, lookup):
        response = self.client.get("/api/pincode/110001/")
        self.assertEqual(response.json(), {"ok": True, "city": "New Delhi", "state": "Delhi"})
        lookup.assert_called_once_with("110001")

    @patch("calculator.views.lookup_pincode_location")
    def test_pincode_lookup_rejects_invalid_input(self, lookup):
        response = self.client.get("/api/pincode/1234x6/")
        self.assertEqual(response.status_code, 400)
        lookup.assert_not_called()

    @patch("calculator.services.requests.get")
    def test_pincode_lookup_parses_versioned_directory_response(self, get):
        get.return_value = Mock(
            status_code=200,
            json=lambda: {
                "success": True,
                "data": {"post_offices": [{"district": "New Delhi", "state": "Delhi", "delivery_status": "Delivery"}]},
            },
        )
        from .services import lookup_pincode_location

        self.assertEqual(lookup_pincode_location("110001"), {"city": "New Delhi", "state": "Delhi"})
        self.assertIn("api.pincodeapi.in/api/v1/pincode/110001", get.call_args.args[0])
