import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from apps.orders.models import Order, OrderStatus
from apps.payments.models import Transaction, TransactionStatus
from apps.payments.services.paystack import PaystackClient, PaystackException


class PaystackClientTest(TestCase):
    def setUp(self):
        self.client = PaystackClient(secret_key="test_sk_secret_key")

    @patch('requests.Session.request')
    def test_initialize_transaction(self, mock_request):
        """Verify initialize_transaction converts GHS to pesewas and returns auth URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": True,
            "message": "Authorization URL created",
            "data": {
                "authorization_url": "https://checkout.paystack.com/test",
                "access_code": "test_access_code",
                "reference": "SB-ABCD1234"
            }
        }
        mock_request.return_value = mock_response

        result = self.client.initialize_transaction(
            email="customer@example.com",
            amount_ghs=Decimal("46.00"),
            reference="SB-ABCD1234"
        )

        self.assertIn("authorization_url", result)
        self.assertEqual(result["reference"], "SB-ABCD1234")

        # Verify pesewas conversion (46.00 GHS → 4600 pesewas)
        called_json = mock_request.call_args[1]['json']
        self.assertEqual(called_json['amount'], 4600)
        self.assertEqual(called_json['currency'], 'GHS')

    @patch('requests.Session.request')
    def test_verify_transaction(self, mock_request):
        """Verify verify_transaction fetches and returns payment data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": True,
            "message": "Verification successful",
            "data": {
                "status": "success",
                "reference": "SB-ABCD1234",
                "amount": 4600,
                "channel": "mobile_money",
                "gateway_response": "Successful",
            }
        }
        mock_request.return_value = mock_response

        result = self.client.verify_transaction("SB-ABCD1234")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["channel"], "mobile_money")

    def test_webhook_signature_valid(self):
        """Verify webhook signature validation using HMAC-SHA512."""
        secret = "test_sk_secret_key"
        payload = b'{"event":"charge.success","data":{"reference":"SB-TEST"}}'
        computed_sig = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        with self.settings(PAYSTACK_WEBHOOK_SECRET=secret, PAYSTACK_SECRET_KEY=secret):
            client = PaystackClient(secret_key=secret)
            self.assertTrue(client.verify_webhook_signature(payload, computed_sig))

    def test_webhook_signature_invalid(self):
        """Verify a tampered webhook signature is rejected."""
        with self.settings(PAYSTACK_WEBHOOK_SECRET="test_sk_secret_key", PAYSTACK_SECRET_KEY="test_sk_secret_key"):
            client = PaystackClient(secret_key="test_sk_secret_key")
            self.assertFalse(client.verify_webhook_signature(b'payload', 'wrong_signature'))


class PaymentInitializeViewTest(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.order = Order.objects.create(
            customer_phone="0241234567",
            amount=Decimal("46.00"),
            network="mtn",
            status=OrderStatus.PENDING_PAYMENT
        )

    @patch('apps.payments.views.PaystackClient')
    def test_initiate_payment_success(self, MockPaystackClient):
        """Verify payment initialization returns checkout URL and creates Transaction."""
        mock_instance = MockPaystackClient.return_value
        mock_instance.initialize_transaction.return_value = {
            "authorization_url": "https://checkout.paystack.com/test",
            "access_code": "test_access",
            "reference": self.order.reference
        }

        response = self.api_client.post('/api/payments/initialize/', {
            "order_reference": self.order.reference,
            "customer_email": "test@example.com"
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIn("authorization_url", response.data)
        self.assertTrue(Transaction.objects.filter(order=self.order).exists())

    def test_initiate_payment_missing_email(self):
        """Verify 400 is returned if email is not supplied."""
        response = self.api_client.post('/api/payments/initialize/', {
            "order_reference": self.order.reference
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("customer_email", response.data.get("error", ""))

    def test_initiate_payment_order_not_found(self):
        """Verify 404 is returned for a non-existent order reference."""
        response = self.api_client.post('/api/payments/initialize/', {
            "order_reference": "SB-NONEXIST",
            "customer_email": "test@example.com"
        }, format='json')
        self.assertEqual(response.status_code, 404)


class PaystackWebhookViewTest(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.order = Order.objects.create(
            customer_phone="0241234567",
            amount=Decimal("46.00"),
            network="mtn",
            status=OrderStatus.PENDING_PAYMENT
        )
        self.transaction = Transaction.objects.create(
            order=self.order,
            paystack_reference=self.order.reference,
            amount=Decimal("46.00"),
            status=TransactionStatus.PENDING
        )

    def _make_signature(self, payload: bytes, secret: str) -> str:
        return hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

    def test_webhook_charge_success(self):
        """Verify a valid webhook with charge.success updates order and transaction."""
        secret = "test_webhook_secret"
        event_payload = json.dumps({
            "event": "charge.success",
            "data": {
                "reference": self.order.reference,
                "status": "success",
                "channel": "mobile_money",
                "gateway_response": "Successful",
                "amount": 4600
            }
        }).encode('utf-8')

        sig = self._make_signature(event_payload, secret)

        with self.settings(
            PAYSTACK_WEBHOOK_SECRET=secret,
            PAYSTACK_SECRET_KEY=secret
        ):
            with patch('apps.orders.tasks.deliver_order.delay') as mock_delay:
                response = self.api_client.post(
                    '/api/payments/webhook/',
                    data=event_payload,
                    content_type='application/json',
                    HTTP_X_PAYSTACK_SIGNATURE=sig
                )

        self.assertEqual(response.status_code, 200)
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, TransactionStatus.SUCCESS)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID)
        mock_delay.assert_called_once_with(self.order.id)

    def test_webhook_invalid_signature_rejected(self):
        """Verify a webhook with bad signature is rejected with 401."""
        with self.settings(PAYSTACK_WEBHOOK_SECRET="real_secret", PAYSTACK_SECRET_KEY="real_secret"):
            response = self.api_client.post(
                '/api/payments/webhook/',
                data=b'{}',
                content_type='application/json',
                HTTP_X_PAYSTACK_SIGNATURE='invalid_signature'
            )
        self.assertEqual(response.status_code, 401)

    @patch('apps.payments.views.PaystackClient')
    @patch('apps.orders.tasks.dispatch_delivery')
    def test_verify_view_success_triggers_delivery(self, mock_dispatch, MockPaystackClient):
        """Verify GET /api/payments/verify/<reference>/ verifies with Paystack and triggers delivery."""
        mock_instance = MockPaystackClient.return_value
        mock_instance.verify_transaction.return_value = {
            "status": "success",
            "reference": self.order.reference,
            "amount": 4600,
            "channel": "mobile_money",
            "gateway_response": "Successful"
        }

        response = self.api_client.get(f'/api/payments/verify/{self.order.reference}/')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['payment_status'], 'success')
        self.assertEqual(data['order_status'], 'paid')

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, TransactionStatus.SUCCESS)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID)
        mock_dispatch.assert_called_once_with(self.order.id)

