import time
import logging
import requests
from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.conf import settings
from apps.bundles.models import VendorRequestLog, BundleCatalog, NetworkChoices

logger = logging.getLogger(__name__)


class VendorAPIException(Exception):
    """Base exception for all vendor API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class VendorAuthenticationError(VendorAPIException):
    """Raised when vendor returns 401 or invalid API key."""
    pass


class VendorInsufficientBalanceError(VendorAPIException):
    """Raised when vendor wallet balance is too low to place an order."""
    pass


class VendorOrderPlacementError(VendorAPIException):
    """Raised when order placement fails at vendor."""
    pass


class MyDataGigsClient:
    """
    Client for interacting with the MyDataGigs aggregator API (https://mydatagigs.com).

    Source of Truth:
    - Base URL: https://mydatagigs.com/wp-json/custom/v1
    - Headers:
        Authorization: Bearer <API_KEY>
        Content-Type: application/json
    - Endpoints:
        GET  /wallet-balance
        GET  /packages?network=<network>
        POST /place-order
        GET  /order-status?order_id=<order_id>
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 30):
        self.base_url = (base_url or getattr(settings, 'VENDOR_BASE_URL', '')).rstrip('/')
        self.api_key = api_key or getattr(settings, 'VENDOR_API_KEY', '')
        self.timeout = timeout
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'SellBundle-Ghana/1.0',
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        order=None
    ) -> Dict[str, Any]:
        """
        Executes an HTTP request to the vendor API and audits the call in VendorRequestLog.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        start_time = time.time()
        status_code = None
        response_payload = None
        is_success = False
        error_message = ""

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=self._get_headers(),
                params=params,
                json=json_data,
                timeout=self.timeout
            )
            status_code = response.status_code
            duration_ms = int((time.time() - start_time) * 1000)

            try:
                response_payload = response.json()
            except Exception:
                response_payload = {"raw_text": response.text[:2000]}

            # Check if vendor reported success
            if response.status_code == 200:
                if isinstance(response_payload, dict) and response_payload.get('status') == 'success':
                    is_success = True
                elif isinstance(response_payload, list):
                    is_success = True
                else:
                    error_message = response_payload.get('message', 'Vendor returned unexpected response format')
            elif response.status_code in (401, 403):
                error_message = f"Vendor Authentication failed (HTTP {status_code}). Check your VENDOR_API_KEY."
            else:
                error_message = f"Vendor returned HTTP {status_code}: {response.text[:300]}"

            # Log to database
            self._log_request(
                endpoint=path,
                http_method=method.upper(),
                request_payload=json_data or params,
                response_payload=response_payload,
                status_code=status_code,
                is_success=is_success,
                error_message=error_message,
                order=order,
                duration_ms=duration_ms
            )

            # Raise appropriate exceptions if not successful
            if not is_success:
                if status_code in (401, 403):
                    raise VendorAuthenticationError(error_message, status_code, response_payload)
                raise VendorAPIException(error_message or "Vendor request failed", status_code, response_payload)

            return response_payload

        except requests.RequestException as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            error_message = f"Network exception communicating with vendor: {str(exc)}"
            self._log_request(
                endpoint=path,
                http_method=method.upper(),
                request_payload=json_data or params,
                response_payload={"exception": str(exc)},
                status_code=status_code,
                is_success=False,
                error_message=error_message,
                order=order,
                duration_ms=duration_ms
            )
            logger.error(f"[VendorAPI Error] {error_message}")
            raise VendorAPIException(error_message)

    def _log_request(
        self,
        endpoint: str,
        http_method: str,
        request_payload: Any,
        response_payload: Any,
        status_code: Optional[int],
        is_success: bool,
        error_message: str,
        order,
        duration_ms: int
    ):
        """Helper to create a VendorRequestLog entry in the database."""
        try:
            VendorRequestLog.objects.create(
                endpoint=endpoint,
                http_method=http_method,
                request_payload=request_payload if isinstance(request_payload, (dict, list)) else {'payload': str(request_payload)},
                response_payload=response_payload if isinstance(response_payload, (dict, list)) else {'payload': str(response_payload)},
                status_code=status_code,
                is_success=is_success,
                error_message=error_message,
                order=order,
                duration_ms=duration_ms
            )
        except Exception as e:
            logger.error(f"Failed to save VendorRequestLog: {e}")

    # --------------------------------------------------------------------------
    # PUBLIC API METHODS
    # --------------------------------------------------------------------------

    def get_wallet_balance(self) -> Decimal:
        """
        Check your current cash balance on the vendor platform.
        Endpoint: GET /wallet-balance
        Expected Response: {"status": "success", "balance": 851.44}
        """
        if getattr(settings, 'DEBUG', False) and (not self.api_key or 'placeholder' in self.api_key or 'your_mydatagigs' in self.api_key):
            logger.info("[Vendor Sandbox] Returning simulated wallet balance GHS 2,500.00")
            return Decimal("2500.00")

        data = self._request('GET', '/wallet-balance')
        try:
            balance_val = data.get('balance', 0)
            return Decimal(str(balance_val))
        except Exception as e:
            raise VendorAPIException(f"Failed to parse wallet balance: {e}", response_data=data)

    def fetch_packages(self, network: str) -> List[Dict[str, Any]]:
        """
        Fetch available bundle packages for a specific network from the vendor.
        Endpoint: GET /packages?network=<network>
        Accepts: mtn, telecel, at_bigdata, at_ishare
        """
        network_clean = network.lower().strip()
        data = self._request('GET', '/packages', params={'network': network_clean})
        packages = data.get('packages', [])
        return packages

    def place_order(
        self,
        network: str,
        beneficiary: str,
        package_param: Any,
        order=None
    ) -> Dict[str, Any]:
        """
        Place a real data bundle order via the vendor API.
        Endpoint: POST /place-order
        Payload:
        {
            "network": "mtn",
            "beneficiary": "0241234567",
            "pa_data-bundle-packages": 2
        }
        Expected Response:
        {
            "status": "success",
            "order_id": 1669242,
            "amount": 8.3,
            "network": "MTN",
            "beneficiary": "0241234567"
        }
        """
        # Format beneficiary phone number to standard Ghana local 10 digits (e.g. 024XXXXXXX)
        phone = beneficiary.strip().replace(' ', '').replace('-', '')
        if phone.startswith('+233'):
            phone = '0' + phone[4:]
        elif phone.startswith('233') and len(phone) == 12:
            phone = '0' + phone[3:]

        payload = {
            "network": network.lower().strip(),
            "beneficiary": phone,
            "pa_data-bundle-packages": package_param
        }

        if getattr(settings, 'DEBUG', False) and (not self.api_key or 'placeholder' in self.api_key or 'your_mydatagigs' in self.api_key):
            logger.info(f"[Vendor Sandbox] Simulating order dispatch for {phone} ({package_param})")
            mock_id = f"VEND-{order.reference if order else 'MOCK1'}"
            self._log_request(
                endpoint='/place-order',
                http_method='POST',
                request_payload=payload,
                response_payload={"status": "success", "order_id": mock_id, "amount": 5.0, "is_sandbox": True},
                status_code=200,
                is_success=True,
                error_message="",
                order=order,
                duration_ms=45
            )
            return {
                "status": "success",
                "order_id": mock_id,
                "amount": float(order.bundle.vendor_price) if (order and order.bundle) else 5.0,
                "network": network.upper(),
                "beneficiary": phone,
                "is_sandbox": True
            }

        response = self._request(
            method='POST',
            path='/place-order',
            json_data=payload,
            order=order
        )
        return response

    def check_order_status(self, vendor_order_id: Any, order=None) -> Dict[str, Any]:
        """
        Query the fulfillment status of a placed order.
        Endpoint: GET /order-status?order_id=<order_id>
        Expected Response:
        {
            "status": "success",
            "order_id": 1685487,
            "order_status": "Delivered",
            "amount": 4.15
        }
        """
        if getattr(settings, 'DEBUG', False) and (not self.api_key or 'placeholder' in self.api_key or 'your_mydatagigs' in self.api_key):
            return {
                "status": "success",
                "order_id": vendor_order_id,
                "order_status": "Delivered",
                "is_sandbox": True
            }

        response = self._request(
            method='GET',
            path='/order-status',
            params={'order_id': str(vendor_order_id)},
            order=order
        )
        return response

    def sync_packages_to_catalog(self, network: str, default_markup_percent: Decimal = Decimal('15.0')) -> int:
        """
        Helper method to fetch packages from vendor and sync/upsert into local BundleCatalog.
        """
        packages = self.fetch_packages(network)
        synced_count = 0

        for pkg in packages:
            pkg_id = pkg.get('package_id')
            label = str(pkg.get('label', ''))
            vendor_price = Decimal(str(pkg.get('price', '0.00')))
            data_size = Decimal(str(pkg.get('data_size', label)))

            # Calculate recommended retail price with markup
            markup_multiplier = (Decimal('100.0') + default_markup_percent) / Decimal('100.0')
            recommended_selling = (vendor_price * markup_multiplier).quantize(Decimal('0.50'))

            bundle, created = BundleCatalog.objects.update_or_create(
                network=network,
                package_id=pkg_id,
                defaults={
                    'name': f"{network.upper()} {label} GB",
                    'data_size': data_size,
                    'vendor_package_param': label,
                    'vendor_price': vendor_price,
                    'selling_price': recommended_selling,
                    'is_active': True,
                }
            )
            synced_count += 1

        return synced_count
