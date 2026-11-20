import uuid
from django.db import models
from django.utils.crypto import get_random_string


class OrderType(models.TextChoices):
    DATA_BUNDLE = 'data_bundle', 'Data Bundle'
    AFA_REGISTRATION = 'afa_registration', 'AFA Bundle Registration'
    RESULT_CHECKER = 'result_checker', 'WAEC Result Checker'


class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
    PAID = 'paid', 'Payment Confirmed'
    PROCESSING = 'processing', 'Processing Delivery'
    COMPLETED = 'completed', 'Completed / Delivered'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


def generate_order_reference():
    """Generates a human-friendly unique order reference like SB-A1B2C3D4."""
    return f"SB-{get_random_string(8).upper()}"


class Order(models.Model):
    """
    Central Order model managing customer purchases across Data Bundles,
    AFA Registrations, and Result Checkers.
    """
    reference = models.CharField(
        max_length=32,
        unique=True,
        default=generate_order_reference,
        editable=False,
        help_text="Unique customer-facing order reference code (e.g. SB-8X7K2M9P)"
    )
    order_type = models.CharField(
        max_length=30,
        choices=OrderType.choices,
        default=OrderType.DATA_BUNDLE
    )
    customer_phone = models.CharField(
        max_length=20,
        help_text="Recipient / customer phone number (e.g. 0241234567)"
    )
    customer_email = models.EmailField(
        blank=True,
        help_text="Optional customer email for Paystack receipt & status alerts"
    )
    network = models.CharField(
        max_length=20,
        blank=True,
        help_text="Provider network (mtn, telecel, at_bigdata, at_ishare)"
    )
    bundle = models.ForeignKey(
        'bundles.BundleCatalog',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
        help_text="Selected bundle package if order_type is data_bundle"
    )
    checker_type = models.ForeignKey(
        'orders.ResultCheckerType',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
        help_text="Selected WAEC checker product if order_type is result_checker"
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Number of units (e.g. for Result Checkers)"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total customer payment amount in GHS"
    )
    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING_PAYMENT,
        db_index=True
    )
    # Vendor Fulfillment details (mydatagigs.com)
    vendor_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Order ID returned by vendor API /place-order (e.g. 1669242)"
    )
    vendor_status = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Latest status reported by vendor (e.g. 'Delivered', 'Processing')"
    )
    failure_reason = models.TextField(
        blank=True,
        help_text="Reason for failure if order could not be fulfilled"
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of automated fulfillment retry attempts"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer Order'
        verbose_name_plural = 'Customer Orders'

    def __str__(self):
        return f"{self.reference} - {self.customer_phone} ({self.get_order_type_display()}) - {self.get_status_display()}"

    @property
    def is_paid(self):
        return self.status in [
            OrderStatus.PAID,
            OrderStatus.PROCESSING,
            OrderStatus.COMPLETED
        ]


# ------------------------------------------------------------------------------
# AFA REGISTRATION DETAILS
# ------------------------------------------------------------------------------
class AfaStatus(models.TextChoices):
    PENDING = 'pending', 'Pending Submission'
    SUBMITTED = 'submitted', 'Submitted to Agent/Telco'
    REGISTERED = 'registered', 'Successfully Registered'
    REJECTED = 'rejected', 'Rejected'


class AfaRegistration(models.Model):
    """
    Stores KYC info for customers registering onto the MTN AFA package.
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='afa_registration'
    )
    full_name = models.CharField(
        max_length=150,
        help_text="Customer's full legal name as on Ghana Card"
    )
    phone_number = models.CharField(
        max_length=20,
        help_text="MTN phone number to register on AFA"
    )
    ghana_card_number = models.CharField(
        max_length=30,
        help_text="Ghana Card PIN (e.g. GHA-123456789-0)"
    )
    town = models.CharField(
        max_length=100,
        help_text="Residential town or city"
    )
    occupation = models.CharField(
        max_length=100,
        help_text="Occupation / Profession (e.g. Farmer, Trader, Teacher)"
    )
    status = models.CharField(
        max_length=30,
        choices=AfaStatus.choices,
        default=AfaStatus.PENDING
    )
    agent_notes = models.TextField(
        blank=True,
        help_text="Internal notes or confirmation codes from MTN/agent"
    )
    registered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AFA Bundle Registration'
        verbose_name_plural = 'AFA Bundle Registrations'

    def __str__(self):
        return f"AFA: {self.full_name} ({self.phone_number}) - {self.get_status_display()}"


# ------------------------------------------------------------------------------
# WAEC RESULT CHECKER MODELS
# ------------------------------------------------------------------------------
class ResultCheckerType(models.Model):
    """
    Result Checker product definition (e.g. BECE, WASSCE, CSSPS).
    """
    code = models.CharField(
        max_length=30,
        unique=True,
        help_text="Unique product identifier (e.g. 'BECE', 'WASSCE')"
    )
    name = models.CharField(
        max_length=100,
        help_text="Display title (e.g. 'BECE Result Checker')"
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short description (e.g. 'Basic Education Certificate Examination')"
    )
    vendor_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=14.00,
        help_text="Wholesale cost price from vendor / WAEC in GHS (e.g. 14.00)"
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=16.00,
        help_text="Retail selling price for customers in GHS (e.g. 16.00)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Available for sale"
    )

    class Meta:
        verbose_name = 'Result Checker Product'
        verbose_name_plural = 'Result Checker Products'

    def __str__(self):
        return f"{self.name} - GHS {self.selling_price}"

    @property
    def price(self):
        """Backward-compatible alias for selling_price."""
        return self.selling_price

    @property
    def profit_margin(self):
        """Gross profit margin per card in GHS."""
        return self.selling_price - self.vendor_price

    @property
    def available_stock(self):
        return self.vouchers.filter(is_sold=False).count()


class ResultCheckerVoucher(models.Model):
    """
    Individual digital voucher inventory (Serial Number & PIN).
    Dispensed automatically to the customer upon payment confirmation.
    """
    checker_type = models.ForeignKey(
        ResultCheckerType,
        on_delete=models.CASCADE,
        related_name='vouchers'
    )
    serial_number = models.CharField(
        max_length=100,
        help_text="Voucher Serial Number"
    )
    pin = models.CharField(
        max_length=100,
        help_text="Voucher Secret PIN"
    )
    is_sold = models.BooleanField(
        default=False,
        db_index=True
    )
    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='vouchers',
        help_text="Customer order this voucher was dispensed to"
    )
    sold_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('checker_type', 'serial_number')
        verbose_name = 'Result Checker Voucher'
        verbose_name_plural = 'Result Checker Vouchers'

    def __str__(self):
        sold_flag = f"[SOLD to {self.order.reference}]" if self.is_sold and self.order else "[AVAILABLE]"
        return f"{self.checker_type.code} - Serial: {self.serial_number} {sold_flag}"


# ------------------------------------------------------------------------------
# SMS NOTIFICATION LOG
# ------------------------------------------------------------------------------
class SMSStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent Successfully'
    FAILED = 'failed', 'Failed'


class SMSLog(models.Model):
    """
    Audit log of all SMS messages dispatched to customers (order receipts, voucher PINs, delivery alerts).
    """
    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sms_logs',
        help_text="Related order if triggered by an order"
    )
    recipient = models.CharField(
        max_length=20,
        help_text="Recipient phone number (e.g. 0241234567)"
    )
    message = models.TextField(
        help_text="Exact SMS text sent to the recipient"
    )
    provider = models.CharField(
        max_length=30,
        default='arkesel',
        help_text="SMS gateway provider used (e.g. arkesel, mnotify, hubtel, sandbox)"
    )
    status = models.CharField(
        max_length=20,
        choices=SMSStatus.choices,
        default=SMSStatus.PENDING,
        db_index=True
    )
    response_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw response payload or message ID returned by the SMS gateway"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if SMS failed to dispatch"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SMS Notification Log'
        verbose_name_plural = 'SMS Notification Logs'

    def __str__(self):
        return f"SMS to {self.recipient} [{self.get_status_display()}] - {self.provider}"

