# ShipRate Calculator

A server-rendered Django app that checks real courier serviceability and estimated shipping charges through the Shiprocket API. It does not create orders or book shipments, and it never substitutes sample rates for API results.

## Features

- Responsive shipment form for Indian pincodes, parcel weight, prepaid/COD mode, order value, and optional dimensions.
- Server-side and browser-side validation.
- Server-side Shiprocket authentication, cached bearer token, and one automatic refresh after an expired-token response.
- Courier results sorted by estimate, with returned delivery estimates and COD availability when present.
- Safe user-facing error handling for missing configuration, credentials, timeouts, API errors, and empty results.
- Automated tests mock external HTTP calls and need no Shiprocket credentials.

## Stack

Python, Django, MySQL, Django templates, Bootstrap 5, vanilla JavaScript, `requests`, `python-dotenv`, and `mysqlclient`.

## Requirements

- Python 3.12 or newer (Django 6.0)
- MySQL 8.0.11 or newer
- A Shiprocket API user with API access

The installed Django version is constrained to `>=6.0,<6.1`, since Django 6.1 requires MySQL 8.4 or newer. Upgrade MySQL to 8.4 before moving to Django 6.1.

## Local setup

From the project root in PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create the MySQL schema once if it does not already exist, using an account with permission to create databases:

```sql
CREATE DATABASE shiprate_calculator CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Keep using the existing root `.env` file. The app reads the database values already there and requires `SECRET_KEY`. Add the Shiprocket values if they are missing:

```dotenv
SHIPROCKET_EMAIL=your-api-user-email
SHIPROCKET_PASSWORD=your-api-user-password
SHIPROCKET_BASE_URL=https://apiv2.shiprocket.in/v1/external
```

`.env.example` documents all expected variables with dummy/blank values. Copy it only when setting up a separate development checkout; do not replace an existing `.env`. The real `.env` is excluded by `.gitignore`.

Create a Shiprocket API user in the Shiprocket panel under **Settings → API → Add New API User**. Use that API user’s credentials, not a password in source code. The application calls the official auth endpoint and serviceability endpoint over HTTPS.

Apply Django migrations and run the development server:

```powershell
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Configure a running MySQL service and make sure the selected host/port, schema, username, and password in `.env` are correct before migrating.

## API behavior

For a rate lookup, the server authenticates at `/auth/login` and calls `/courier/serviceability/` with `pickup_postcode`, `delivery_postcode`, actual `weight`, and `cod` (1 for COD, 0 for prepaid). Shiprocket documents auth tokens as valid for 10 days; this app caches them for 9 days and refreshes once if serviceability returns HTTP 401. Dimensions and order value are collected for the shipment form but are not sent because they are not required by the documented serviceability request used here. No volumetric-weight substitution is performed.

The displayed rates and delivery times come only from fields returned by Shiprocket. Rates are estimates and may differ at booking due to shipment details, surcharges, or account configuration. Missing response fields are omitted or shown as unavailable.

## Tests

```powershell
python manage.py test calculator
```

Tests mock all Shiprocket network calls. Django still needs a configured database when running its full test runner; with MySQL configured, it creates and removes a temporary test database.

## Security and deployment

- Never commit `.env`, Shiprocket credentials, bearer tokens, or production `SECRET_KEY` values.
- Keep `DEBUG=False` in production and set a production-only secret key and explicit `ALLOWED_HOSTS`.
- Use a production WSGI/ASGI server, HTTPS, and a managed cache backend if multiple workers need to share cached tokens.
- Restrict database credentials and network access to the application host.
- API errors are translated to safe messages; logs avoid credentials, authorization headers, tokens, and request payloads.
- No CORS policy is opened, CSRF protection stays enabled, and TLS certificate verification remains enabled.
