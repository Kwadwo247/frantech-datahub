# SellBundle Ghana 🇬🇭 — Instant Data Bundles & Digital Voucher Platform

SellBundle is a full-stack e-commerce and automated telecommunications reselling platform engineered specifically for the Ghanaian market. It enables automated, instant fulfillment of mobile data bundles (MTN, Telecel, AirtelTigo), WAEC Result Checker PINs (BECE & WASSCE), and MTN AFA scheme registrations, powered by Mobile Money via Paystack.

---

## 🌟 Key Features

### 1. Customer Storefront (`/`)
- **Instant Data Bundles**: Direct discounts on high-speed internet data for **MTN Ghana**, **Telecel Ghana**, **AirtelTigo Big Time Data**, and **AirtelTigo iShare**.
- **Smart Prefix Detection**: Auto-detects phone network (e.g. `024`/`054`/`055`/`059` for MTN, `020`/`050` for Telecel, `027`/`057`/`026`/`056` for AT).
- **WAEC Result Checkers**: Purchase BECE and WASSCE result checker serial numbers and secret PINs with instant digital reveal upon payment.
- **MTN AFA Registration**: Digital KYC submission (Ghana Card PIN, resident town, profession) for discounted telco bundles.
- **Live Order Tracker**: Real-time status polling, one-click PIN copy, WhatsApp receipt sharing, and printable thermal receipts.

### 2. Payment & Sandbox Engine (`apps/payments`)
- **Paystack Mobile Money & Card Integration**: HMAC-SHA512 webhook verification (`X-Paystack-Signature`), multi-channel processing (MTN MoMo, Telecel Cash, AT Money, Debit Cards).
- **Built-in MoMo Sandbox Simulator (`/sandbox/paystack/<reference>/`)**: Test full payment confirmation and delivery lifecycles offline without deducting real funds or needing live credentials.

### 3. Automated Fulfillment & Delivery Engine (`apps/orders`)
- **Aggregator / Vendor Integration (`MyDataGigs`)**: Direct push of data packages straight to customer phone numbers via API, complete with automated wallet balance checks and mock fallbacks during development.
- **Atomic WAEC Voucher Dispensing**: Database `select_for_update` transactional locks preventing double-dispensing or race conditions under high concurrent volume.
- **Ghana SMS Gateway Notifications (`apps/orders/services/sms.py`)**: Multi-provider failover support for **Arkesel**, **mNotify**, and **Hubtel**, with local sandbox simulation and audit logs (`SMSLog`).
- **Resilient Worker Architecture**: Celery background queue with automatic synchronous fallback when Redis is offline.

### 4. Admin Financial Dashboard (`/dashboard/`)
- **Executive Analytics**: Real-time Gross Profit calculations across all lines of business, daily revenue velocity, and sales breakdowns by network.
- **Interactive Visualizations**: Powered by Chart.js (daily revenue trendline, product mix donut, network distribution bar chart).
- **Voucher Stock Level Monitor**: Visual progress bars and low-inventory warnings.
- **1-Click AFA Batch Approvals**: Instant batch and single review actions for pending farmers/AFA registrations.

---

## 📁 Project Architecture

```
SellBundle/
├── apps/
│   ├── accounts/     # User authentication and admin profiles
│   ├── bundles/      # BundleCatalog, vendor syncing, and MyDataGigs API client
│   ├── dashboard/    # Staff analytics views, Chart.js APIs, and AFA actions
│   ├── orders/       # Order state machine, WAEC vouchers, AFA KYC, and SMS engine
│   └── payments/     # Paystack integration, Webhook processor, and MoMo sandbox
├── scripts/
│   ├── test_flow.py                # End-to-end full lifecycle integration test
│   └── test_postgres_connection.py # Database connectivity diagnostic utility
├── sellbundle/
│   ├── settings.py   # Django settings (decouple-managed)
│   ├── urls.py       # Global URL routing
│   ├── wsgi.py / asgi.py
│   └── celery.py     # Celery configuration
├── static/
│   ├── css/storefront.css  # Dark modern responsive UI theme
│   └── js/app.js           # Single-page application logic and live tracking
├── templates/
│   ├── index.html                  # Customer storefront SPA
│   ├── sandbox_checkout.html       # Simulated Paystack MoMo modal
│   └── admin/dashboard/index.html  # Executive financial analytics dashboard
├── manage.py
├── requirements.txt
└── .env
```

---

## 🚀 Quickstart & Installation

### 1. Environment Setup
```bash
# Clone the repository and enter directory
cd SellBundle

# Activate the virtual environment
.\.venv\Scripts\activate   # Windows PowerShell
# or: source .venv/bin/activate (Linux/macOS)

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Copy `.env.example` to `.env` if not already present:
```ini
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,testserver

# Database (SQLite default for instant development; set to True for PostgreSQL)
USE_POSTGRESQL=False
DB_NAME=sellbundle_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Gateways (Leave defaults for local sandbox mode)
PAYSTACK_SECRET_KEY=sk_test_placeholder
PAYSTACK_PUBLIC_KEY=pk_test_placeholder
PAYSTACK_WEBHOOK_SECRET=placeholder_secret

VENDOR_BASE_URL=https://mydatagigs.com/wp-json/custom/v1
VENDOR_API_KEY=your_mydatagigs_api_key_here

SMS_ENABLED=True
SMS_PROVIDER=sandbox
SMS_SENDER_ID=SellBundle
```

### 3. Database Migration & Initial Data Seeding
```bash
# Run migrations
python manage.py migrate

# Seed data bundles (MTN, Telecel, AT Big Time, AT iShare) and WAEC products
python manage.py populate_initial_data

# Seed sample WAEC Result Checker inventory (BECE & WASSCE PINs/Serials)
python manage.py seed_waec_vouchers --count 20

# Create admin superuser (if needed)
python manage.py createsuperuser
```

### 4. Start the Application
```bash
python manage.py runserver 127.0.0.1:8000
```
- **Customer Storefront**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Financial Dashboard**: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/) (Requires staff login)
- **Django Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **API Root**: [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)

---

## 🧪 Testing & Verification

SellBundle includes a comprehensive automated test suite covering all apps, permission boundaries, calculation logic, and webhook signatures.

### Run Django Test Suite
```bash
python manage.py test
```
*Current test suite: **52 passing tests**.*

### Run End-to-End Lifecycle Verification
```bash
python scripts/test_flow.py
```
This script exercises:
1. Health and API root validation.
2. Network catalog exploration.
3. Data bundle creation & simulated vendor fulfillment.
4. WAEC result checker order, pre-payment security check (vouchers hidden), payment confirmation, and atomic voucher dispensing.
5. MTN AFA registration creation and status lifecycle.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health/` | Service health check |
| `GET` | `/api/bundles/` | List active data bundles (filters: `network`, `min_size`, `max_size`) |
| `GET` | `/api/bundles/networks/` | List supported telcos with brand metadata and active counts |
| `POST` | `/api/orders/` | Create a new order (`data_bundle`, `result_checker`, `afa_registration`) |
| `GET` | `/api/orders/<ref>/` | Retrieve order status, delivery progress, and revealed PINs |
| `GET` | `/api/orders/result-checkers/`| List WAEC products and real-time inventory count |
| `POST` | `/api/payments/initialize/` | Initiate Paystack payment transaction |
| `GET` | `/api/payments/verify/<ref>/` | Verify transaction state against Paystack gateway |
| `POST` | `/api/payments/webhook/` | Secure Paystack webhook receiver (HMAC-SHA512) |

---

## 🔒 Security Best Practices
- **HMAC SHA-512**: Webhooks strictly validate the `X-Paystack-Signature` against `PAYSTACK_WEBHOOK_SECRET`.
- **Double-Spend Guard**: Orders in `paid` or `completed` states reject re-initialization or duplicate charges.
- **Race Condition Prevention**: Voucher dispensing uses `select_for_update` in database atomic transactions.
- **CSRF Defense**: All dashboard actions enforce CSRF cookies and tokens across AJAX requests.
- **Rate Throttling**: REST APIs employ DRF Anonymous and User rate throttles to mitigate brute-force attacks.

---

## 📜 License
Proprietary & Confidential — SellBundle Ghana © 2026. All rights reserved.

