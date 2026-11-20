import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def dispatch_delivery(order_id: int):
    """
    Dispatches delivery for an order.
    Attempts to queue via Celery worker. If Celery broker is offline, or if task raises
    ConnectionError or OperationalError, gracefully executes delivery synchronously via fallback.
    """
    try:
        deliver_order.delay(order_id)
        logger.info(f"[Delivery] Queued delivery task via Celery for Order ID={order_id}")
    except Exception as exc:
        logger.warning(
            f"[Delivery] Celery queue dispatch failed for Order ID={order_id} ({exc}). "
            "Executing delivery synchronously via offline fallback..."
        )
        execute_order_delivery(order_id)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,   # Wait 60 seconds before first retry
    autoretry_for=(Exception,),
    retry_backoff=True,       # Exponential backoff: 60s, 120s, 240s
    retry_backoff_max=600,    # Cap at 10 minutes
    acks_late=True            # Only ack task after completion (safer for retries)
)
def deliver_order(self, order_id: int):
    """Celery shared task wrapper for order delivery."""
    execute_order_delivery(order_id, task_instance=self)


def execute_order_delivery(order_id: int, task_instance=None):
    """
    Core delivery execution. Routes to the right fulfillment method based on order_type:
        - data_bundle       -> Calls vendor API (mydatagigs.com) to send data
        - result_checker    -> Dispenses N PIN/Serial vouchers from local inventory
        - afa_registration  -> Marks as submitted for manual/agent processing
    """
    from apps.orders.models import Order, OrderStatus, OrderType

    logger.info(f"[Delivery] Starting delivery execution for Order ID={order_id}")

    try:
        order = Order.objects.select_related('bundle', 'checker_type').get(pk=order_id)
    except Order.DoesNotExist:
        logger.error(f"[Delivery] Order ID={order_id} does not exist. Skipping.")
        return

    # Guard: Only process paid orders that aren't already completed/failed
    if order.status not in [OrderStatus.PAID, OrderStatus.PROCESSING]:
        logger.info(f"[Delivery] Order {order.reference} has status={order.status}. Nothing to do.")
        return

    # Mark as processing
    order.status = OrderStatus.PROCESSING
    order.retry_count = (order.retry_count or 0) + 1
    order.save(update_fields=['status', 'retry_count'])

    try:
        if order.order_type == OrderType.DATA_BUNDLE:
            _deliver_data_bundle(order)
        elif order.order_type == OrderType.RESULT_CHECKER:
            _deliver_result_checker(order)
        elif order.order_type == OrderType.AFA_REGISTRATION:
            _process_afa_registration(order)
        else:
            raise ValueError(f"Unknown order_type: {order.order_type}")

        # Mark completed
        order.status = OrderStatus.COMPLETED
        order.failure_reason = ""
        order.save(update_fields=['status', 'failure_reason'])
        logger.info(f"[Delivery] Order {order.reference} completed successfully.")

        # Dispatch automated SMS notification
        try:
            from apps.orders.services.sms import send_order_sms
            send_order_sms(order.id)
        except Exception as sms_exc:
            logger.warning(f"[SMS] Automated SMS notification failed for {order.reference}: {sms_exc}")

    except Exception as exc:
        logger.error(f"[Delivery] Delivery failed for Order {order.reference}: {exc}")

        max_retries = getattr(task_instance, 'max_retries', 3) if task_instance else 0
        current_retries = getattr(getattr(task_instance, 'request', None), 'retries', 0) if task_instance else 0

        if task_instance and current_retries < max_retries:
            order.status = OrderStatus.PAID  # Reset so retry can pick it up
            order.failure_reason = str(exc)
            order.save(update_fields=['status', 'failure_reason'])
            raise task_instance.retry(exc=exc)
        else:
            # Max retries exhausted or synchronous fallback execution failed
            order.status = OrderStatus.FAILED
            order.failure_reason = str(exc)
            order.save(update_fields=['status', 'failure_reason'])
            logger.error(f"[Delivery] Order {order.reference} PERMANENTLY FAILED: {exc}")


def _deliver_data_bundle(order):
    """Call vendor API to push the data bundle to the customer's phone."""
    from apps.bundles.services.vendor_api import MyDataGigsClient, VendorAPIException

    if not order.bundle:
        raise ValueError(f"Order {order.reference} has no bundle linked.")

    client = MyDataGigsClient()

    # First check wallet balance to avoid unnecessary vendor calls
    try:
        balance = client.get_wallet_balance()
        if balance < order.bundle.vendor_price:
            raise ValueError(
                f"Insufficient vendor wallet balance (GHS {balance}) to fulfill "
                f"bundle costing GHS {order.bundle.vendor_price}. Top up required."
            )
    except VendorAPIException as exc:
        logger.warning(f"Could not check wallet balance: {exc}. Proceeding anyway.")

    # Place the order with the vendor
    result = client.place_order(
        network=order.network,
        beneficiary=order.customer_phone,
        package_param=order.bundle.vendor_package_param,
        order=order
    )

    # Save vendor order ID and status
    order.vendor_order_id = str(result.get('order_id', ''))
    order.vendor_status = result.get('status', 'submitted')
    order.save(update_fields=['vendor_order_id', 'vendor_status'])

    logger.info(
        f"[Vendor] Bundle dispatched: Order {order.reference} -> "
        f"Vendor Order ID={order.vendor_order_id}, Phone={order.customer_phone}"
    )


def _deliver_result_checker(order):
    """
    Dispense PIN/Serial voucher(s) from local inventory for the ordered checker product.
    Supports single or multiple quantity dispensing atomically.
    """
    from apps.orders.models import ResultCheckerVoucher, ResultCheckerType
    from django.db import transaction

    checker_type = order.checker_type
    if not checker_type:
        # Fallback: check if order quantity vouchers are available in any active checker type
        first_available = ResultCheckerVoucher.objects.filter(is_sold=False).select_related('checker_type').first()
        if first_available:
            checker_type = first_available.checker_type
        else:
            raise ValueError(
                f"No result checker product associated with Order {order.reference} "
                "and no vouchers available in inventory."
            )

    needed_qty = order.quantity or 1

    with transaction.atomic():
        available_vouchers = list(
            ResultCheckerVoucher.objects.select_for_update()
            .filter(checker_type=checker_type, is_sold=False)
            .order_by('id')[:needed_qty]
        )

        if len(available_vouchers) < needed_qty:
            raise ValueError(
                f"Insufficient {checker_type.code} vouchers in stock for order {order.reference}. "
                f"Needed: {needed_qty}, Available: {len(available_vouchers)}. "
                "Please restock vouchers in the admin panel."
            )

        now = timezone.now()
        for voucher in available_vouchers:
            voucher.is_sold = True
            voucher.order = order
            voucher.sold_at = now
            voucher.save(update_fields=['is_sold', 'order', 'sold_at'])

    logger.info(
        f"[Voucher] Successfully dispensed {needed_qty}x {checker_type.code} voucher(s) "
        f"to Order {order.reference}."
    )


def _process_afa_registration(order):
    """
    AFA Registration: update status to 'submitted' so admin can
    manually confirm with MTN agent or process through the agent portal.
    """
    from apps.orders.models import AfaRegistration, AfaStatus

    try:
        registration = order.afa_registration
        registration.status = AfaStatus.SUBMITTED
        registration.save(update_fields=['status'])
        logger.info(f"[AFA] Registration for {registration.phone_number} marked as SUBMITTED.")
    except AfaRegistration.DoesNotExist:
        raise ValueError(f"Order {order.reference} has no AFA registration data.")


@shared_task
def check_stuck_orders():
    """
    Celery Beat periodic task.
    Re-queues orders stuck in PROCESSING status for more than 10 minutes.
    Also polls vendor API for any orders stuck in PAID status.
    """
    from apps.orders.models import Order, OrderStatus
    from django.utils.timezone import now
    from datetime import timedelta

    cutoff = now() - timedelta(minutes=10)
    stuck_orders = Order.objects.filter(
        status=OrderStatus.PROCESSING,
        updated_at__lt=cutoff
    )

    count = stuck_orders.count()
    if count:
        logger.info(f"[Beat] Found {count} stuck orders. Re-queuing delivery tasks...")
        for order in stuck_orders:
            order.status = OrderStatus.PAID
            order.save(update_fields=['status'])
            deliver_order.delay(order.id)
        logger.info(f"[Beat] Re-queued {count} stuck orders.")
    else:
        logger.debug("[Beat] No stuck orders found.")

    return count
