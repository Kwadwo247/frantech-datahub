import os
import sys
import json
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sellbundle.settings')
import django
django.setup()

import requests
from django.test import Client as DjangoClient
from apps.bundles.models import BundleCatalog, NetworkChoices
from apps.orders.models import Order, OrderStatus, OrderType, ResultCheckerType, ResultCheckerVoucher, AfaStatus
from apps.orders.tasks import dispatch_delivery

BASE_URL = "http://127.0.0.1:8000"


class UnifiedClient:
    """
    HTTP client that automatically checks if a live dev server is running.
    If yes, makes real HTTP requests via `requests`.
    If no, transparently falls back to Django's in-memory `Client` so testing
    can run without needing a separate server process.
    """
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.is_live = False
        self.django_client = None

        try:
            r = requests.get(f"{self.base_url}/api/health/", timeout=1)
            if r.status_code == 200:
                self.is_live = True
        except Exception:
            self.is_live = False

        if not self.is_live:
            self.django_client = DjangoClient()

    def get(self, path: str):
        if self.is_live:
            return requests.get(f"{self.base_url}{path}", timeout=5)
        response = self.django_client.get(path)
        return self._wrap_response(response)

    def post(self, path: str, json_data: dict):
        if self.is_live:
            return requests.post(f"{self.base_url}{path}", json=json_data, timeout=5)
        response = self.django_client.post(
            path,
            data=json.dumps(json_data),
            content_type="application/json"
        )
        return self._wrap_response(response)

    def _wrap_response(self, django_resp):
        class Wrapped:
            def __init__(self, r):
                self.status_code = r.status_code
                self.text = r.content.decode('utf-8')
                self._r = r

            def json(self):
                return json.loads(self.text)
        return Wrapped(django_resp)


def test_full_lifecycle():
    client = UnifiedClient(BASE_URL)
    mode = "Live Server (http://127.0.0.1:8000)" if client.is_live else "In-Memory Django Test Client (Offline)"
    print(f"\n=== Testing SellBundle Full Lifecycle End-to-End [{mode}] ===\n")

    # --------------------------------------------------------------------------
    # 1. API Root & Health Check
    # --------------------------------------------------------------------------
    r = client.get("/api/")
    assert r.status_code == 200, f"API root failed: {r.status_code}"
    print("[OK] 1. API Root reached successfully")

    r = client.get("/api/health/")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    print("[OK] 2. Service health check reported healthy")

    # --------------------------------------------------------------------------
    # 2. Bundles & Networks Listing
    # --------------------------------------------------------------------------
    r = client.get("/api/bundles/networks/")
    assert r.status_code == 200
    networks = r.json()["networks"]
    net_codes = [n["code"] for n in networks]
    print(f"[OK] 3. Supported networks queried: {', '.join(net_codes)}")
    assert "mtn" in net_codes and "telecel" in net_codes and "at_bigdata" in net_codes and "at_ishare" in net_codes

    r = client.get("/api/bundles/?network=mtn")
    assert r.status_code == 200
    mtn_bundles = r.json()["bundles"]
    print(f"[OK] 4. MTN catalog queried: {len(mtn_bundles)} active packages found")
    assert len(mtn_bundles) > 0
    selected_bundle = mtn_bundles[0]

    # --------------------------------------------------------------------------
    # 3. Data Bundle Order & Fulfillment
    # --------------------------------------------------------------------------
    bundle_payload = {
        "order_type": "data_bundle",
        "customer_phone": "0241234567",
        "customer_email": "buyer@example.com",
        "network": "mtn",
        "bundle_id": selected_bundle["id"],
        "auto_initialize_payment": False
    }
    r = client.post("/api/orders/", bundle_payload)
    assert r.status_code == 201, f"Failed to create bundle order: {r.text}"
    b_order = r.json()["order"]
    b_ref = b_order["reference"]
    print(f"[OK] 5. Data Bundle order created: Reference={b_ref}, Package={selected_bundle['name']}")

    # Simulate payment & vendor delivery
    order_obj = Order.objects.get(reference=b_ref)
    order_obj.status = OrderStatus.PAID
    order_obj.save()
    dispatch_delivery(order_obj.id)

    order_obj.refresh_from_db()
    print(f"[OK] 6. Data Bundle delivered: Status={order_obj.status}, Vendor Order ID={order_obj.vendor_order_id}")
    assert order_obj.status == OrderStatus.COMPLETED

    # --------------------------------------------------------------------------
    # 4. WAEC Result Checker Order & Voucher Dispensing
    # --------------------------------------------------------------------------
    # Ensure BECE has at least 2 vouchers in stock
    bece_type, _ = ResultCheckerType.objects.get_or_create(
        code="BECE",
        defaults={"name": "BECE Result Checker", "selling_price": Decimal("16.00"), "vendor_price": Decimal("13.50")}
    )
    needed = 2 - bece_type.available_stock
    for i in range(max(0, needed)):
        ResultCheckerVoucher.objects.create(
            checker_type=bece_type,
            serial_number=f"TEST-BECE-{os.urandom(4).hex().upper()}",
            pin="123456789012",
            is_sold=False
        )

    r = client.get("/api/orders/result-checkers/")
    assert r.status_code == 200
    checkers = r.json()["result_checkers"]
    bece = next(c for c in checkers if c["code"] == "BECE")
    print(f"[OK] 7. WAEC BECE in stock: {bece['available_stock']} units, price: GHS {bece['selling_price']}")

    checker_payload = {
        "order_type": "result_checker",
        "customer_phone": "0247654321",
        "customer_email": "student@example.com",
        "result_checker_data": {
            "checker_type_code": "BECE",
            "quantity": 2
        },
        "auto_initialize_payment": False
    }
    r = client.post("/api/orders/", checker_payload)
    assert r.status_code == 201, f"Failed to create result checker order: {r.text}"
    c_order = r.json()["order"]
    c_ref = c_order["reference"]
    print(f"[OK] 8. Result Checker order created: Reference={c_ref}, Total=GHS {c_order['amount']}")

    # Verify protected before payment (0 vouchers shown)
    r = client.get(f"/api/orders/{c_ref}/")
    assert r.status_code == 200
    assert len(r.json()["vouchers"]) == 0
    print("[OK] 9. Security verified: Vouchers strictly hidden before payment")

    # Confirm payment & dispatch vouchers
    c_order_obj = Order.objects.get(reference=c_ref)
    c_order_obj.status = OrderStatus.PAID
    c_order_obj.save()
    dispatch_delivery(c_order_obj.id)

    # Verify dispensed
    r = client.get(f"/api/orders/{c_ref}/")
    assert r.status_code == 200
    dispensed = r.json()
    assert dispensed["status"] == "completed"
    assert len(dispensed["vouchers"]) == 2
    for v in dispensed["vouchers"]:
        print(f"   -> Dispensed PIN: {v['pin']} | Serial: {v['serial_number']}")
    print("[OK] 10. Atomic voucher dispensing verified: 2 valid PINs received")

    # --------------------------------------------------------------------------
    # 5. MTN AFA Registration Order
    # --------------------------------------------------------------------------
    afa_payload = {
        "order_type": "afa_registration",
        "customer_phone": "0249876543",
        "customer_email": "farmer@example.com",
        "afa_data": {
            "full_name": "Kwadwo Asare",
            "phone_number": "0249876543",
            "ghana_card_number": "GHA-987654321-0",
            "town": "Sunyani",
            "occupation": "Cocoa Farmer"
        },
        "auto_initialize_payment": False
    }
    r = client.post("/api/orders/", afa_payload)
    assert r.status_code == 201, f"Failed to create AFA order: {r.text}"
    afa_ref = r.json()["order"]["reference"]
    print(f"[OK] 11. MTN AFA Registration order created: Reference={afa_ref}")

    # Confirm payment and dispatch
    afa_order_obj = Order.objects.get(reference=afa_ref)
    afa_order_obj.status = OrderStatus.PAID
    afa_order_obj.save()
    dispatch_delivery(afa_order_obj.id)

    afa_reg = afa_order_obj.afa_registration
    afa_reg.refresh_from_db()
    assert afa_reg.status == AfaStatus.SUBMITTED
    print(f"[OK] 12. AFA registration transitioned to SUBMITTED for telco activation")

    print("\n=============================================================")
    print("  ALL FULL LIFECYCLE END-TO-END TESTS PASSED SUCCESSFULLY!   ")
    print("=============================================================\n")


if __name__ == "__main__":
    test_full_lifecycle()
