import logging
import requests
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from django.conf import settings
from django.utils import timezone
from apps.orders.models import Order, OrderType, SMSLog, SMSStatus

logger = logging.getLogger(__name__)


@dataclass
class SMSResult:
    success: bool
    provider: str
    message_id: str = ""
    raw_response: Dict[str, Any] = None
    error_message: str = ""


class BaseSMSProvider:
    """Base interface for Ghana SMS providers."""
    name: str = "base"

    def send(self, recipient: str, message: str, sender_id: str) -> SMSResult:
        raise NotImplementedError


class ArkeselSMSProvider(BaseSMSProvider):
    """
    Arkesel Ghana SMS API v2 Client.
    Docs: https://arkesel.com/docs
    Endpoint: POST https://openapi.arkesel.com/api/v2/sms/send
    """
    name: str = "arkesel"
    ENDPOINT = "https://openapi.arkesel.com/api/v2/sms/send"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'ARKESEL_API_KEY', '')

    def send(self, recipient: str, message: str, sender_id: str) -> SMSResult:
        # Standardize recipient to international Ghana format 233XXXXXXXXX or local
        clean_recipient = recipient.strip().replace(' ', '').replace('-', '')
        if clean_recipient.startswith('+233'):
            clean_recipient = clean_recipient[1:]
        elif clean_recipient.startswith('0') and len(clean_recipient) == 10:
            clean_recipient = '233' + clean_recipient[1:]

        headers = {
            'api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {
            'sender': sender_id[:11],  # Max 11 characters
            'message': message,
            'recipients': [clean_recipient],
        }

        try:
            res = requests.post(self.ENDPOINT, headers=headers, json=payload, timeout=15)
            try:
                data = res.json()
            except Exception:
                data = {"raw": res.text[:500]}

            if res.status_code in [200, 201] and data.get('status') in ['success', 200, 201]:
                msg_id = str(data.get('data', {}).get('id', ''))
                return SMSResult(success=True, provider=self.name, message_id=msg_id, raw_response=data)
            else:
                err = data.get('message', f"Arkesel HTTP {res.status_code}")
                return SMSResult(success=False, provider=self.name, error_message=str(err), raw_response=data)

        except requests.RequestException as e:
            return SMSResult(success=False, provider=self.name, error_message=str(e), raw_response={})


class MNotifySMSProvider(BaseSMSProvider):
    """
    mNotify Ghana SMS Client.
    Docs: https://mnotify.com
    Endpoint: POST https://api.mnotify.com/api/sms/quick
    """
    name: str = "mnotify"
    ENDPOINT = "https://api.mnotify.com/api/sms/quick"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'MNOTIFY_API_KEY', '')

    def send(self, recipient: str, message: str, sender_id: str) -> SMSResult:
        clean_recipient = recipient.strip().replace(' ', '').replace('-', '')
        if clean_recipient.startswith('+233'):
            clean_recipient = '0' + clean_recipient[4:]

        headers = {
            'key': self.api_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'recipient': [clean_recipient],
            'sender': sender_id[:11],
            'message': message,
            'is_schedule': False,
        }

        try:
            res = requests.post(self.ENDPOINT, headers=headers, json=payload, timeout=15)
            data = res.json() if res.content else {}
            if res.status_code == 200 and data.get('status') == 'success':
                msg_id = str(data.get('summary', {}).get('_id', ''))
                return SMSResult(success=True, provider=self.name, message_id=msg_id, raw_response=data)
            else:
                return SMSResult(success=False, provider=self.name, error_message=data.get('message', f"HTTP {res.status_code}"), raw_response=data)
        except requests.RequestException as e:
            return SMSResult(success=False, provider=self.name, error_message=str(e), raw_response={})


class HubtelSMSProvider(BaseSMSProvider):
    """
    Hubtel Ghana SMS Client.
    Docs: https://developers.hubtel.com
    Endpoint: POST https://smsc.hubtel.com/v1/messages/send
    """
    name: str = "hubtel"
    ENDPOINT = "https://smsc.hubtel.com/v1/messages/send"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or getattr(settings, 'HUBTEL_CLIENT_ID', '')
        self.client_secret = client_secret or getattr(settings, 'HUBTEL_CLIENT_SECRET', '')

    def send(self, recipient: str, message: str, sender_id: str) -> SMSResult:
        clean_recipient = recipient.strip().replace(' ', '').replace('-', '')
        if clean_recipient.startswith('+233'):
            clean_recipient = clean_recipient[1:]
        elif clean_recipient.startswith('0'):
            clean_recipient = '233' + clean_recipient[1:]

        payload = {
            'From': sender_id[:11],
            'To': clean_recipient,
            'Content': message,
        }

        try:
            res = requests.post(
                self.ENDPOINT,
                auth=(self.client_id, self.client_secret),
                json=payload,
                timeout=15
            )
            data = res.json() if res.content else {}
            if res.status_code in [200, 201] and data.get('status') == 0:
                msg_id = str(data.get('messageId', ''))
                return SMSResult(success=True, provider=self.name, message_id=msg_id, raw_response=data)
            else:
                return SMSResult(success=False, provider=self.name, error_message=data.get('message', f"HTTP {res.status_code}"), raw_response=data)
        except requests.RequestException as e:
            return SMSResult(success=False, provider=self.name, error_message=str(e), raw_response={})


class SandboxSMSProvider(BaseSMSProvider):
    """
    Simulated SMS Gateway for development & test environments.
    Prints simulated SMS output cleanly to console without calling external telco APIs.
    """
    name: str = "sandbox"

    def send(self, recipient: str, message: str, sender_id: str) -> SMSResult:
        simulated_id = f"SMS-MOCK-{int(timezone.now().timestamp())}"
        logger.info(
            f"[SMS Sandbox] Provider: {self.name} | Sender: {sender_id} | "
            f"To: {recipient} | Message: \"{message}\""
        )
        return SMSResult(
            success=True,
            provider=self.name,
            message_id=simulated_id,
            raw_response={
                "status": "success",
                "message": "Simulated SMS dispatched (Sandbox Environment)",
                "recipient": recipient,
                "message_id": simulated_id,
                "sender_id": sender_id,
            }
        )


def get_sms_provider() -> BaseSMSProvider:
    """Factory to retrieve the active Ghana SMS provider based on settings."""
    provider_name = getattr(settings, 'SMS_PROVIDER', 'arkesel').lower()
    is_debug = getattr(settings, 'DEBUG', False)

    if provider_name == 'mnotify':
        api_key = getattr(settings, 'MNOTIFY_API_KEY', '')
        if is_debug and (not api_key or 'placeholder' in api_key):
            return SandboxSMSProvider()
        return MNotifySMSProvider(api_key=api_key)

    elif provider_name == 'hubtel':
        client_id = getattr(settings, 'HUBTEL_CLIENT_ID', '')
        client_secret = getattr(settings, 'HUBTEL_CLIENT_SECRET', '')
        if is_debug and (not client_id or 'placeholder' in client_id):
            return SandboxSMSProvider()
        return HubtelSMSProvider(client_id=client_id, client_secret=client_secret)

    elif provider_name == 'sandbox':
        return SandboxSMSProvider()

    else:
        # Default: Arkesel
        api_key = getattr(settings, 'ARKESEL_API_KEY', '')
        if is_debug and (not api_key or 'placeholder' in api_key or 'your_arkesel' in api_key):
            return SandboxSMSProvider()
        return ArkeselSMSProvider(api_key=api_key)


def build_order_sms_text(order: Order) -> str:
    """Generates the customer-facing SMS message content based on order type."""
    ref = order.reference

    if order.order_type == OrderType.RESULT_CHECKER:
        vouchers = list(order.vouchers.all())
        checker_name = order.checker_type.name if order.checker_type else "WAEC Checker"

        if not vouchers:
            return f"SellBundle: Your {checker_name} order {ref} has been confirmed. View status at: http://sellbundle.gh/?reference={ref}"

        if len(vouchers) == 1:
            v = vouchers[0]
            return (
                f"SellBundle: Order {ref} complete! {checker_name} -> "
                f"PIN: {v.pin} | Serial: {v.serial_number}. "
                f"Check at eresults.waecgh.org"
            )
        else:
            items = " ".join([f"#{i+1}: PIN {v.pin} (SN: {v.serial_number})" for i, v in enumerate(vouchers)])
            return f"SellBundle: Order {ref} ({len(vouchers)}x {checker_name}) -> {items}"

    elif order.order_type == OrderType.DATA_BUNDLE:
        pkg = order.bundle.name if order.bundle else "Data Bundle"
        return (
            f"SellBundle: Your {pkg} for {order.customer_phone} (Order {ref}) "
            f"has been delivered successfully! Check balance via *138# (MTN) or *124# (AT/Telecel). Thank you!"
        )

    elif order.order_type == OrderType.AFA_REGISTRATION:
        return (
            f"SellBundle: Your MTN AFA Registration for {order.customer_phone} (Order {ref}) "
            f"has been received and submitted for telco activation. Contact 024XXXXXXX for support."
        )

    return f"SellBundle: Order {ref} update: {order.get_status_display()}."


def send_order_sms(order_id: int) -> Optional[SMSLog]:
    """
    Builds and sends an SMS notification to the order's customer phone number.
    Records the attempt in SMSLog for audit and retry capability.
    """
    if not getattr(settings, 'SMS_ENABLED', True):
        logger.info(f"[SMS] SMS notifications are disabled in settings. Skipping Order ID={order_id}.")
        return None

    try:
        order = Order.objects.select_related('bundle', 'checker_type').prefetch_related('vouchers').get(pk=order_id)
    except Order.DoesNotExist:
        logger.error(f"[SMS] Order ID={order_id} does not exist. Cannot send SMS.")
        return None

    recipient = order.customer_phone
    if not recipient:
        logger.warning(f"[SMS] Order {order.reference} has no customer_phone. Skipping SMS.")
        return None

    message = build_order_sms_text(order)
    sender_id = getattr(settings, 'SMS_SENDER_ID', 'SellBundle')
    provider = get_sms_provider()

    logger.info(f"[SMS] Sending notification for Order {order.reference} via {provider.name} to {recipient}...")

    # Create initial pending log
    log = SMSLog.objects.create(
        order=order,
        recipient=recipient,
        message=message,
        provider=provider.name,
        status=SMSStatus.PENDING,
    )

    result = provider.send(recipient=recipient, message=message, sender_id=sender_id)

    if result.success:
        log.status = SMSStatus.SENT
        log.response_payload = result.raw_response or {}
        log.save(update_fields=['status', 'response_payload'])
        logger.info(f"[SMS] Successfully sent SMS to {recipient} for Order {order.reference} (ID={result.message_id}).")
    else:
        log.status = SMSStatus.FAILED
        log.error_message = result.error_message
        log.response_payload = result.raw_response or {}
        log.save(update_fields=['status', 'error_message', 'response_payload'])
        logger.warning(f"[SMS] Failed to send SMS to {recipient} for Order {order.reference}: {result.error_message}")

    return log
