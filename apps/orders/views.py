import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404

from apps.orders.models import Order, OrderStatus, ResultCheckerType
from apps.orders.serializers import (
    OrderCreateSerializer,
    OrderStatusSerializer,
    ResultCheckerTypeSerializer,
)
from apps.payments.models import Transaction, TransactionStatus
from apps.payments.services.paystack import PaystackClient, PaystackException

logger = logging.getLogger(__name__)


class OrderCreateView(APIView):
    """
    POST /api/orders/
    Creates a new customer order for data bundles, AFA registration, or WAEC result checkers.
    Optionally initializes Paystack payment immediately if auto_initialize_payment is True and email is provided.

    Request Body (Data Bundle):
        {
            "order_type": "data_bundle",
            "customer_phone": "0241234567",
            "customer_email": "customer@example.com",
            "network": "mtn",
            "bundle_id": 1,
            "callback_url": "http://localhost:5173/order-status"
        }

    Request Body (WAEC Result Checker):
        {
            "order_type": "result_checker",
            "customer_phone": "0241234567",
            "customer_email": "customer@example.com",
            "result_checker_data": {
                "checker_type_code": "BECE",
                "quantity": 1
            }
        }

    Request Body (AFA Registration):
        {
            "order_type": "afa_registration",
            "customer_phone": "0241234567",
            "customer_email": "customer@example.com",
            "afa_data": {
                "full_name": "Kwame Mensah",
                "phone_number": "0241234567",
                "ghana_card_number": "GHA-123456789-0",
                "town": "Accra",
                "occupation": "Trader"
            }
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = serializer.save()

        # Automatic payment initialization if email provided and flag not False
        auto_pay = request.data.get('auto_initialize_payment', True)
        callback_url = request.data.get('callback_url', '').strip()
        if not callback_url:
            callback_url = f"{request.scheme}://{request.get_host()}/"
        payment_info = None

        if auto_pay and order.customer_email:
            try:
                client = PaystackClient()
                metadata = {
                    "order_reference": order.reference,
                    "customer_phone": order.customer_phone,
                    "order_type": order.order_type,
                    "network": order.network or "",
                }
                paystack_data = client.initialize_transaction(
                    email=order.customer_email,
                    amount_ghs=order.amount,
                    reference=order.reference,
                    callback_url=callback_url,
                    metadata=metadata,
                )

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

                payment_info = {
                    "authorization_url": paystack_data.get('authorization_url'),
                    "access_code": paystack_data.get('access_code'),
                    "reference": paystack_data.get('reference', order.reference),
                }

            except PaystackException as exc:
                logger.warning(f"Auto payment initialization failed for order {order.reference}: {exc}")
                # We do not fail the order creation; order is saved and can be paid later
                payment_info = {
                    "error": str(exc),
                    "note": "Payment could not be auto-initialized. Call /api/payments/initialize/ to retry."
                }

        order_data = OrderStatusSerializer(order).data
        return Response({
            "order": order_data,
            "payment": payment_info
        }, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    """
    GET /api/orders/<str:reference>/
    Retrieves live order status, delivery state, and digital vouchers (if completed WAEC checker order).
    """
    permission_classes = [AllowAny]

    def get(self, request, reference):
        clean_ref = reference.strip().upper()
        try:
            order = Order.objects.select_related('bundle').prefetch_related('vouchers__checker_type').get(
                reference=clean_ref
            )
        except Order.DoesNotExist:
            return Response(
                {"error": f"Order with reference '{reference}' was not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrderStatusSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResultCheckerTypeListView(APIView):
    """
    GET /api/orders/result-checkers/
    Returns all active WAEC Result Checker types with current stock availability and pricing.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        checkers = ResultCheckerType.objects.filter(is_active=True).order_by('code')
        serializer = ResultCheckerTypeSerializer(checkers, many=True)
        return Response({
            "result_checkers": serializer.data
        }, status=status.HTTP_200_OK)
