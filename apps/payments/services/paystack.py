import hashlib
import hmac
import logging
import requests
from decimal import Decimal
from typing import Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class PaystackException(Exception):
    """Base exception for Paystack API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.data = data or {}


class PaystackClient:
    """
    Service client for Paystack API (Ghana: Mobile Money + Card).

    Base URL: https://api.paystack.co
    Auth: Authorization: Bearer <SECRET_KEY>
    Currency: GHS (Paystack charges in Pesewas = GHS * 100)

    Endpoints used:
        POST /transaction/initialize   - Start a payment
        GET  /transaction/verify/:ref  - Verify a payment
    """

    BASE_URL = "https://api.paystack.co"

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _request(self, method: str, path: str, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=self._get_headers(),
                json=json_data,
                timeout=30
            )
            data = response.json()

            if not data.get('status'):
                raise PaystackException(
                    data.get('message', 'Paystack request failed'),
                    status_code=response.status_code,
                    data=data
                )
            return data

        except requests.RequestException as exc:
            raise PaystackException(f"Network error calling Paystack: {exc}")

    # --------------------------------------------------------------------------
    # PUBLIC API METHODS
    # --------------------------------------------------------------------------

    def initialize_transaction(
        self,
        email: str,
        amount_ghs: Decimal,
        reference: str,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
        channels: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Initialize a Paystack payment session.

        Paystack charges in pesewas (GHS × 100), so GHS 46.00 = 4600 pesewas.
        Supported channels for Ghana: 'mobile_money', 'card'.

        Returns:
            {
                "authorization_url": "https://checkout.paystack.com/...",
                "access_code": "...",
                "reference": "SB-XXXXXXXX"
            }
        """
        # Convert GHS to pesewas (integer, no decimals)
        amount_pesewas = int(amount_ghs * 100)

        payload = {
            "email": email,
            "amount": amount_pesewas,
            "currency": "GHS",
            "reference": reference,
            "channels": channels or ["mobile_money", "card"],
            "metadata": metadata or {},
        }

        if callback_url:
            payload["callback_url"] = callback_url

        if getattr(settings, 'DEBUG', False) and (not self.secret_key or 'placeholder' in self.secret_key):
            logger.info(f"[Paystack Sandbox] Initializing mock checkout session for {reference}")
            return {
                "authorization_url": f"/sandbox/paystack/{reference}/",
                "access_code": f"sandbox_code_{reference}",
                "reference": reference,
            }

        response = self._request('POST', '/transaction/initialize', json_data=payload)
        return response.get('data', {})

    def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verify a Paystack payment by its reference.

        Returns the full Paystack data object.
        Key fields to check:
            data['status']              -> 'success' | 'failed' | 'abandoned'
            data['amount']              -> Amount in pesewas
            data['channel']             -> 'mobile_money' | 'card'
            data['gateway_response']    -> 'Successful' | 'Approved' etc.
            data['paid_at']             -> Timestamp ISO string
        """
        if getattr(settings, 'DEBUG', False) and (not self.secret_key or 'placeholder' in self.secret_key):
            logger.info(f"[Paystack Sandbox] Mock verifying transaction {reference}")
            return {
                "status": "success",
                "reference": reference,
                "amount": 0,
                "channel": "mobile_money",
                "gateway_response": "Successful (Sandbox Simulation)",
            }

        response = self._request('GET', f'/transaction/verify/{reference}')
        return response.get('data', {})

    def verify_webhook_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """
        Validates the Paystack webhook signature to prevent spoofed requests.

        Paystack sends a X-Paystack-Signature header containing the HMAC-SHA512
        hash of the raw request body, signed with your Paystack Secret Key.

        Args:
            payload_body:       Raw bytes from request.body
            signature_header:   Value of X-Paystack-Signature HTTP header

        Returns:
            True if signature is valid; False otherwise.
        """
        webhook_secret = getattr(settings, 'PAYSTACK_WEBHOOK_SECRET', '') or self.secret_key
        if not webhook_secret:
            logger.warning("Paystack webhook secret is not set — rejecting all webhooks for safety.")
            return False

        computed = hmac.new(
            webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(computed, signature_header)
