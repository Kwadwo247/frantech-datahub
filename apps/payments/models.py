from django.db import models


class TransactionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SUCCESS = 'success', 'Successful'
    FAILED = 'failed', 'Failed'
    ABANDONED = 'abandoned', 'Abandoned'


class Transaction(models.Model):
    """
    Paystack Payment Transaction record linked to an Order.
    Handles Ghana Mobile Money (MTN MoMo, Telecel Cash, AT Money) & Card payments.
    """
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='transaction',
        help_text="The customer order associated with this payment"
    )
    paystack_reference = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique reference code generated for Paystack payment"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount in GHS (Paystack charges in Pesewas = GHS * 100)"
    )
    currency = models.CharField(
        max_length=10,
        default='GHS'
    )
    channel = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment channel used (e.g. 'mobile_money', 'card')"
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
        db_index=True
    )
    gateway_response = models.CharField(
        max_length=255,
        blank=True,
        help_text="Message returned by Paystack (e.g. 'Successful', 'Approved')"
    )
    authorization_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Paystack checkout URL generated for redirect"
    )
    access_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Paystack checkout access code"
    )
    customer_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    raw_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Full JSON payload received from Paystack webhook / verification"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when payment was confirmed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'

    def __str__(self):
        return f"{self.paystack_reference} - GHS {self.amount} [{self.get_status_display()}]"
