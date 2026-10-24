import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
TOKEN_CACHE_KEY = "shiprocket_api_token_v1"
TOKEN_TTL_SECONDS = 9 * 24 * 60 * 60
REQUEST_TIMEOUT = (5, 20)


class ShiprocketError(Exception):
    """Safe-to-display Shiprocket integration error."""


class ShiprocketConfigurationError(ShiprocketError):
    pass


class ShiprocketAuthenticationError(ShiprocketError):
    pass


class ShiprocketUnavailableError(ShiprocketError):
    pass


class ShiprocketResponseError(ShiprocketError):
    pass


def _url(path):
    return f"{settings.SHIPROCKET_BASE_URL}/{path.lstrip('/')}"


def _json_response(response):
    try:
        result = response.json()
    except ValueError as exc:
        raise ShiprocketResponseError("Shiprocket returned an unreadable response. Please try again.") from exc
    if not isinstance(result, dict):
        raise ShiprocketResponseError("Shiprocket returned an unexpected response. Please try again.")
    return result


def _get_token(force_refresh=False):
    if not settings.SHIPROCKET_EMAIL or not settings.SHIPROCKET_PASSWORD:
        raise ShiprocketConfigurationError("Add your Shiprocket API email and password to the .env file.")
    token = None if force_refresh else cache.get(TOKEN_CACHE_KEY)
    if token:
        return token
    try:
        response = requests.post(
            _url("auth/login"),
            json={"email": settings.SHIPROCKET_EMAIL, "password": settings.SHIPROCKET_PASSWORD},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("Shiprocket authentication request failed (%s).", type(exc).__name__)
        raise ShiprocketUnavailableError("Could not connect to Shiprocket. Please try again shortly.") from exc
    if response.status_code in (401, 403):
        raise ShiprocketAuthenticationError("Shiprocket rejected the API credentials. Check your .env settings.")
    if not response.ok:
        logger.warning("Shiprocket authentication returned HTTP %s.", response.status_code)
        raise ShiprocketUnavailableError("Shiprocket could not authenticate this request. Please try again later.")
    data = _json_response(response)
    token = data.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ShiprocketResponseError("Shiprocket did not return an authentication token.")
    cache.set(TOKEN_CACHE_KEY, token, TOKEN_TTL_SECONDS)
    return token


def _request_serviceability(params, token):
    try:
        return requests.get(
            _url("courier/serviceability/"),
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("Shiprocket serviceability request failed (%s).", type(exc).__name__)
        raise ShiprocketUnavailableError("Could not connect to Shiprocket. Please try again shortly.") from exc


def _courier_list(data):
    result = data.get("data", data)
    if not isinstance(result, dict):
        raise ShiprocketResponseError("Shiprocket returned an unexpected serviceability response.")
    couriers = result.get("available_courier_companies", [])
    if couriers is None:
        return []
    if not isinstance(couriers, list) or any(not isinstance(item, dict) for item in couriers):
        raise ShiprocketResponseError("Shiprocket returned an unexpected courier list.")
    normalized = []
    for courier in couriers:
        item = {}
        for key in (
            "courier_name", "rate", "etd", "cod", "estimated_delivery_days", "pickup_performance", "rating",
        ):
            if key in courier and courier[key] is not None and courier[key] != "":
                item[key] = courier[key]
        if item:
            normalized.append(item)
    try:
        normalized.sort(key=lambda item: float(item.get("rate", float("inf"))))
    except (TypeError, ValueError):
        pass
    return normalized


def check_serviceability(*, pickup_postcode, delivery_postcode, weight, cod):
    params = {
        "pickup_postcode": pickup_postcode,
        "delivery_postcode": delivery_postcode,
        "weight": str(weight),
        "cod": 1 if cod else 0,
    }
    token = _get_token()
    response = _request_serviceability(params, token)
    if response.status_code == 401:
        cache.delete(TOKEN_CACHE_KEY)
        token = _get_token(force_refresh=True)
        response = _request_serviceability(params, token)
    if response.status_code in (401, 403):
        cache.delete(TOKEN_CACHE_KEY)
        raise ShiprocketAuthenticationError("Shiprocket authentication failed. Check your API credentials and try again.")
    if response.status_code == 429:
        raise ShiprocketUnavailableError("Shiprocket is receiving too many requests. Please wait and try again.")
    if not response.ok:
        logger.warning("Shiprocket serviceability returned HTTP %s.", response.status_code)
        raise ShiprocketUnavailableError("Shiprocket could not calculate rates right now. Please try again later.")
    data = _json_response(response)
    if data.get("status") is False or data.get("status_code") not in (None, 200, 202):
        raise ShiprocketUnavailableError("Shiprocket could not calculate rates for these shipment details.")
    return _courier_list(data)


def lookup_pincode_location(pincode):
    """Look up district and state using public postal PIN directory APIs."""
    cache_key = f"india_post_pincode_location_{pincode}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    providers = (
        (f"https://api.pincodeapi.in/api/v1/pincode/{pincode}", "versioned"),
        (f"https://api.postalpincode.in/pincode/{pincode}", "legacy"),
    )
    for url, provider in providers:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.info("Pincode lookup provider failed (%s).", type(exc).__name__)
            continue

        office = None
        if provider == "versioned" and isinstance(payload, dict) and payload.get("success"):
            data = payload.get("data")
            offices = data.get("post_offices", []) if isinstance(data, dict) else []
            if isinstance(offices, list):
                office = next((item for item in offices if isinstance(item, dict) and item.get("delivery_status") == "Delivery"), None)
                if office is None:
                    office = next((item for item in offices if isinstance(item, dict)), None)
            location = {
                "city": str((office or {}).get("district") or "").strip(),
                "state": str((office or {}).get("state") or "").strip(),
            }
        elif provider == "legacy" and isinstance(payload, list) and payload and isinstance(payload[0], dict):
            entry = payload[0]
            offices = entry.get("PostOffice")
            if entry.get("Status") == "Success" and isinstance(offices, list):
                office = next((item for item in offices if isinstance(item, dict) and item.get("DeliveryStatus") == "Delivery"), None)
                if office is None:
                    office = next((item for item in offices if isinstance(item, dict)), None)
            location = {
                "city": str((office or {}).get("District") or "").strip(),
                "state": str((office or {}).get("State") or "").strip(),
            }
        else:
            location = {"city": "", "state": ""}

        if location["city"] or location["state"]:
            cache.set(cache_key, location, 24 * 60 * 60)
            return location
    return None
