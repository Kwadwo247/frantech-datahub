import json
import logging
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle

from apps.orders.models import Order, OrderStatus
from apps.payments.models import Transaction, TransactionStatus
from apps.payments.services.paystack import PaystackClient, PaystackException

logger = logging.getLogger(__name__)


class OrderPaymentInitiateView(APIView):
    """
    POST /api/payments/initialize/
    Starts a Paystack payment session for a given order.

    Request Body:
        {
            "order_reference": "SB-ABCD1234",
            "customer_email": "customer@example.com",
            "callback_url": "https://yoursite.com/order-status"
        }

    Response (200):
        {
            "authorization_url": "https://checkout.paystack.com/...",
            "access_code": "...",
            "reference": "SB-ABCD1234"
        }
    """
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        order_reference = request.data.get('order_reference', '').strip()
        customer_email = request.data.get('customer_email', '').strip()
        callback_url = request.data.get('callback_url', '').strip()
        if not callback_url:
            callback_url = f"{request.scheme}://{request.get_host()}/"

        # Validate required fields
        if not order_reference:
            return Response(
                {"error": "order_reference is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not customer_email:
            return Response(
                {"error": "customer_email is required for Paystack."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch the order
        try:
            order = Order.objects.get(reference=order_reference)
        except Order.DoesNotExist:
            return Response(
                {"error": f"Order '{order_reference}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Guard: Do not charge twice for an already-paid order
        if order.is_paid:
            return Response(
                {"error": f"Order '{order_reference}' is already paid or in delivery."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update email if provided and order doesn't have one
        if customer_email and not order.customer_email:
            order.customer_email = customer_email
            order.save(update_fields=['customer_email'])

        # Build metadata to track product details inside Paystack dashboard
        metadata = {
            "order_reference": order.reference,
            "customer_phone": order.customer_phone,
            "order_type": order.order_type,
            "network": order.network or "",
            "bundle": str(order.bundle) if order.bundle else "",
        }

        try:
            client = PaystackClient()
            paystack_data = client.initialize_transaction(
                email=customer_email,
                amount_ghs=order.amount,
                reference=order.reference,
                callback_url=callback_url,
                metadata=metadata,
            )
        except PaystackException as exc:
            logger.error(f"Paystack initialization failed for order {order_reference}: {exc}")
            return Response(
                {"error": "Payment gateway error. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Create or update the Transaction record
        Transaction.objects.update_or_create(
            order=order,
            defaults={
                'paystack_reference': paystack_data.get('reference', order.reference),
                'amount': order.amount,
                'currency': 'GHS',
                'authorization_url': paystack_data.get('authorization_url', ''),
                'access_code': paystack_data.get('access_code', ''),
                'status': TransactionStatus.PENDING,
                'customer_ip': request.META.get('REMOTE_ADDR'),
            }
        )

        return Response({
            "authorization_url": paystack_data.get('authorization_url'),
            "access_code": paystack_data.get('access_code'),
            "reference": paystack_data.get('reference', order.reference),
        }, status=status.HTTP_200_OK)


class PaystackWebhookView(APIView):
    """
    POST /api/payments/webhook/
    Receives Paystack payment confirmation events.

    Security:
        - Verifies X-Paystack-Signature header (HMAC-SHA512) to authenticate the request.
        - Only processes 'charge.success' events.
        - After payment verified, triggers Celery task to deliver the bundle.
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # No session/token auth for webhooks

    def post(self, request):
        # 1. Verify webhook signature
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        if not signature:
            logger.warning("Paystack webhook received without signature header.")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        client = PaystackClient()
        if not client.verify_webhook_signature(request.body, signature):
            logger.warning("Paystack webhook signature verification FAILED — possible spoofed request.")
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        # 2. Parse event payload
        try:
            event_data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event = event_data.get('event', '')
        data = event_data.get('data', {})

        logger.info(f"Paystack webhook received: event={event}, ref={data.get('reference')}")

        # 3. Only process confirmed payment events
        if event != 'charge.success':
            return Response({"message": "Event noted but not processed."}, status=status.HTTP_200_OK)

        # 4. Find and update the Transaction + Order
        reference = data.get('reference', '')
        payment_status = data.get('status', '')

        try:
            transaction = Transaction.objects.get(paystack_reference=reference)
        except Transaction.DoesNotExist:
            # Try finding by order reference
            try:
                order = Order.objects.get(reference=reference)
                transaction = Transaction.objects.get(order=order)
            except (Order.DoesNotExist, Transaction.DoesNotExist):
                logger.warning(f"Paystack webhook: No transaction found for reference {reference}")
                return Response({"message": "Order not found."}, status=status.HTTP_200_OK)

        # Guard: already processed
        if transaction.status == TransactionStatus.SUCCESS:
            return Response({"message": "Already processed."}, status=status.HTTP_200_OK)

        # 5. Update Transaction record with full Paystack response
        transaction.status = TransactionStatus.SUCCESS if payment_status == 'success' else TransactionStatus.FAILED
        transaction.channel = data.get('channel', '')
        transaction.gateway_response = data.get('gateway_response', '')
        transaction.paid_at = timezone.now()
        transaction.raw_response = data
        transaction.save()

        # 6. Update Order status
        order = transaction.order
        if payment_status == 'success':
            order.status = OrderStatus.PAID
            order.save(update_fields=['status'])

            # 7. Trigger bundle/voucher delivery (via Celery with offline fallback)
            from apps.orders.tasks import dispatch_delivery
            dispatch_delivery(order.id)

            logger.info(f"Order {order.reference} payment confirmed. Delivery dispatched.")

        return Response({"message": "Webhook processed."}, status=status.HTTP_200_OK)


class PaystackVerifyView(APIView):
    """
    GET /api/payments/verify/<reference>/
    Allows the frontend to manually verify payment status after redirect.
    """
    permission_classes = [AllowAny]

    def get(self, request, reference):
        try:
            transaction = Transaction.objects.select_related('order').get(
                paystack_reference=reference
            )
        except Transaction.DoesNotExist:
            return Response(
                {"error": "Transaction not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # If still pending, call Paystack API to check
        if transaction.status == TransactionStatus.PENDING:
            try:
                client = PaystackClient()
                data = client.verify_transaction(reference)
                payment_status = data.get('status', '')

                if payment_status == 'success':
                    transaction.status = TransactionStatus.SUCCESS
                    transaction.channel = data.get('channel', '')
                    transaction.gateway_response = data.get('gateway_response', '')
                    transaction.paid_at = timezone.now()
                    transaction.raw_response = data
                    transaction.save()

                    order = transaction.order
                    if not order.is_paid:
                        order.status = OrderStatus.PAID
                        order.save(update_fields=['status'])
                        from apps.orders.tasks import dispatch_delivery
                        dispatch_delivery(order.id)

            except PaystackException as exc:
                logger.error(f"Paystack verification error for {reference}: {exc}")

        order = transaction.order
        return Response({
            "reference": reference,
            "payment_status": transaction.status,
            "order_reference": order.reference,
            "order_status": order.status,
            "amount": str(transaction.amount),
            "channel": transaction.channel,
        })


from django.views.generic import View
from django.shortcuts import render, redirect

class PaystackSandboxCheckoutView(View):
    """
    Development Sandbox Checkout View.
    Renders an interactive simulated Paystack Mobile Money authorization modal
    when running locally without live Paystack credentials.
    """
    def get(self, request, reference):
        clean_ref = reference.strip().upper()
        try:
            order = Order.objects.get(reference=clean_ref)
        except Order.DoesNotExist:
            return render(request, 'sandbox_checkout.html', {'error': f"Order '{reference}' was not found."})

        transaction, _ = Transaction.objects.get_or_create(
            order=order,
            defaults={
                'paystack_reference': order.reference,
                'amount': order.amount,
                'currency': 'GHS',
                'status': TransactionStatus.PENDING,
            }
        )

        return render(request, 'sandbox_checkout.html', {
            'order': order,
            'transaction': transaction,
        })

    def post(self, request, reference):
        clean_ref = reference.strip().upper()
        try:
            order = Order.objects.get(reference=clean_ref)
        except Order.DoesNotExist:
            return redirect(f"/?reference={clean_ref}")

        action = request.POST.get('action', 'approve')

        if action == 'approve':
            transaction, _ = Transaction.objects.get_or_create(
                order=order,
                defaults={
                    'paystack_reference': order.reference,
                    'amount': order.amount,
                    'currency': 'GHS',
                }
            )
            transaction.status = TransactionStatus.SUCCESS
            transaction.channel = request.POST.get('channel', 'mobile_money')
            transaction.gateway_response = 'Approved via Sandbox MoMo Simulator'
            transaction.paid_at = timezone.now()
            transaction.save()

            order.status = OrderStatus.PAID
            order.save(update_fields=['status'])

            from apps.orders.tasks import dispatch_delivery
            dispatch_delivery(order.id)

            return redirect(f"/?reference={clean_ref}")
        else:
            return redirect(f"/?reference={clean_ref}&cancelled=true")

