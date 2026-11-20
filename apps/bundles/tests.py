from decimal import Decimal
from unittest.mock import patch, MagicMock
import requests
from django.test import TestCase
from apps.bundles.models import BundleCatalog, NetworkChoices, VendorRequestLog
from apps.bundles.services.vendor_api import (
    MyDataGigsClient,
    VendorAPIException,
    VendorAuthenticationError,
)
from apps.orders.models import Order


class BundleCatalogModelTest(TestCase):
    def setUp(self):
        self.bundle = BundleCatalog.objects.create(
            network=NetworkChoices.MTN,
            name="MTN 10GB Data",
            data_size=10.0,
            package_id=638849,
            vendor_package_param="10",
            vendor_price=Decimal("39.50"),
            selling_price=Decimal("46.00"),
            is_active=True,
        )

    def test_profit_margin(self):
        """Verify profit margin calculation."""
        self.assertEqual(self.bundle.profit_margin, Decimal("6.50"))

    def test_vendor_log_creation(self):
        """Verify VendorRequestLog records API audit details."""
        log = VendorRequestLog.objects.create(
            endpoint="/place-order",
            http_method="POST",
            request_payload={"network": "mtn", "beneficiary": "0241234567"},
            response_payload={"status": "success", "order_id": 1669242},
            status_code=200,
            is_success=True,
            duration_ms=450
        )
        self.assertTrue(log.is_success)
        self.assertEqual(log.status_code, 200)


class VendorAPIServiceTest(TestCase):
    def setUp(self):
        self.client = MyDataGigsClient(
            base_url="https://mydatagigs.com/wp-json/custom/v1",
            api_key="test_api_key_123"
        )

    @patch('requests.Session.request')
    def test_get_wallet_balance_success(self, mock_request):
        """Verify get_wallet_balance parses balance and creates VendorRequestLog."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "balance": 851.44}
        mock_request.return_value = mock_response

        balance = self.client.get_wallet_balance()

        self.assertEqual(balance, Decimal("851.44"))
        log = VendorRequestLog.objects.latest('id')
        self.assertEqual(log.endpoint, "/wallet-balance")
        self.assertTrue(log.is_success)
        self.assertEqual(log.status_code, 200)

    @patch('requests.Session.request')
    def test_fetch_packages_success(self, mock_request):
        """Verify fetch_packages retrieves package list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "network": "MTN",
            "packages": [
                {"package_id": 638849, "label": "10", "price": 39.5, "data_size": 10},
                {"package_id": 1307872, "label": "1", "price": 4.34, "data_size": 1}
            ]
        }
        mock_request.return_value = mock_response

        packages = self.client.fetch_packages("mtn")

        self.assertEqual(len(packages), 2)
        self.assertEqual(packages[0]["package_id"], 638849)

    @patch('requests.Session.request')
    def test_place_order_success(self, mock_request):
        """Verify place_order formats Ghana numbers, calls API, and links to order."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "order_id": 1669242,
            "amount": 8.3,
            "network": "MTN",
            "beneficiary": "0241234567"
        }
        mock_request.return_value = mock_response

        order = Order.objects.create(
            customer_phone="+233241234567",
            amount=Decimal("10.00"),
            network="mtn"
        )

        result = self.client.place_order(
            network="mtn",
            beneficiary="+233241234567",
            package_param="2",
            order=order
        )

        self.assertEqual(result["order_id"], 1669242)
        log = VendorRequestLog.objects.filter(order=order).latest('id')
        self.assertEqual(log.request_payload["beneficiary"], "0241234567")
        self.assertTrue(log.is_success)

    @patch('requests.Session.request')
    def test_check_order_status_success(self, mock_request):
        """Verify check_order_status queries order status endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "order_id": 1685487,
            "order_status": "Delivered",
            "amount": 4.15
        }
        mock_request.return_value = mock_response

        status_data = self.client.check_order_status(1685487)

        self.assertEqual(status_data["order_status"], "Delivered")
        self.assertEqual(status_data["order_id"], 1685487)

    @patch('requests.Session.request')
    def test_authentication_failure_raises_exception(self, mock_request):
        """Verify 401 Unauthorized raises VendorAuthenticationError and logs failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API Key"
        mock_response.json.side_effect = ValueError("No JSON")
        mock_request.return_value = mock_response

        with self.assertRaises(VendorAuthenticationError):
            self.client.get_wallet_balance()

        log = VendorRequestLog.objects.latest('id')
        self.assertFalse(log.is_success)
        self.assertEqual(log.status_code, 401)

    @patch('requests.Session.request')
    def test_network_timeout_logs_and_raises(self, mock_request):
        """Verify network timeouts are safely captured in VendorRequestLog."""
        mock_request.side_effect = requests.exceptions.Timeout("Connection timed out")

        with self.assertRaises(VendorAPIException):
            self.client.get_wallet_balance()

        log = VendorRequestLog.objects.latest('id')
        self.assertFalse(log.is_success)
        self.assertIn("Connection timed out", log.error_message)


class BundleAPITest(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.mtn_bundle = BundleCatalog.objects.create(
            network=NetworkChoices.MTN,
            name="MTN 1GB Data",
            data_size=1.0,
            package_id=1307872,
            vendor_package_param="1",
            vendor_price=Decimal("4.34"),
            selling_price=Decimal("5.50"),
            display_order=1,
            is_active=True,
        )
        self.telecel_bundle = BundleCatalog.objects.create(
            network=NetworkChoices.TELECEL,
            name="Telecel 2GB Data",
            data_size=2.0,
            package_id=638817,
            vendor_package_param="2",
            vendor_price=Decimal("8.80"),
            selling_price=Decimal("10.50"),
            display_order=1,
            is_active=True,
        )
        self.inactive_bundle = BundleCatalog.objects.create(
            network=NetworkChoices.MTN,
            name="MTN Expired Bundle",
            data_size=5.0,
            package_id=999999,
            vendor_package_param="5",
            vendor_price=Decimal("20.00"),
            selling_price=Decimal("25.00"),
            is_active=False,
        )

    def test_list_all_active_bundles(self):
        """GET /api/bundles/ returns only active bundles."""
        response = self.client.get('/api/bundles/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        bundle_names = [b['name'] for b in data['bundles']]
        self.assertIn("MTN 1GB Data", bundle_names)
        self.assertIn("Telecel 2GB Data", bundle_names)
        self.assertNotIn("MTN Expired Bundle", bundle_names)

    def test_filter_bundles_by_network(self):
        """GET /api/bundles/?network=mtn returns only MTN bundles."""
        response = self.client.get('/api/bundles/?network=mtn')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['bundles'][0]['network'], 'mtn')

    def test_filter_invalid_network_returns_400(self):
        """GET /api/bundles/?network=unknown returns 400 Bad Request."""
        response = self.client.get('/api/bundles/?network=unknown')
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid network", response.json()['error'])

    def test_list_networks(self):
        """GET /api/bundles/networks/ returns network choices and counts."""
        response = self.client.get('/api/bundles/networks/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('networks', data)
        codes = [n['code'] for n in data['networks']]
        self.assertIn('mtn', codes)
        self.assertIn('telecel', codes)
        mtn_net = next(n for n in data['networks'] if n['code'] == 'mtn')
        self.assertEqual(mtn_net['bundle_count'], 1)

