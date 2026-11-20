from django.db import models


class NetworkChoices(models.TextChoices):
    MTN = 'mtn', 'MTN'
    TELECEL = 'telecel', 'Telecel'
    AT_BIGDATA = 'at_bigdata', 'AirtelTigo (Big Time Data)'
    AT_ISHARE = 'at_ishare', 'AirtelTigo (iShare)'


class BundleCatalog(models.Model):
    """
    Catalog of data bundles mapped to the vendor API (mydatagigs.com).
    """
    network = models.CharField(
        max_length=20,
        choices=NetworkChoices.choices,
        help_text="Network provider code matching vendor API (mtn, telecel, at_bigdata, at_ishare)"
    )
    name = models.CharField(
        max_length=100,
        help_text="Display name (e.g. 'MTN 10GB Data')"
    )
    data_size = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Data volume in Gigabytes (e.g. 1.00, 2.50, 10.00)"
    )
    package_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Vendor package_id returned by /packages endpoint (e.g. 638849)"
    )
    vendor_package_param = models.CharField(
        max_length=50,
        help_text="Value to send in 'pa_data-bundle-packages' payload to vendor (e.g. '10', '2', or package_id)"
    )
    vendor_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Wholesale cost price on vendor wallet in GHS (e.g. 39.50)"
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Retail selling price for customers in GHS (e.g. 45.00)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this bundle is visible and purchasable by customers"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Sorting order on frontend (lower numbers display first)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['network', 'display_order', 'data_size']
        verbose_name = 'Bundle Package'
        verbose_name_plural = 'Bundle Packages'

    def __str__(self):
        return f"[{self.get_network_display()}] {self.name} - GHS {self.selling_price}"

    @property
    def profit_margin(self):
        """Calculate gross profit per bundle in GHS."""
        return self.selling_price - self.vendor_price


class VendorRequestLog(models.Model):
    """
    Audit log of every outbound request to the vendor API (mydatagigs.com)
    and its exact response for troubleshooting and financial reconciliation.
    """
    endpoint = models.CharField(
        max_length=255,
        help_text="Vendor API endpoint URL or path (e.g. /place-order, /wallet-balance)"
    )
    http_method = models.CharField(
        max_length=10,
        default='POST'
    )
    request_payload = models.JSONField(
        null=True,
        blank=True,
        help_text="Exact JSON payload sent to vendor"
    )
    response_payload = models.JSONField(
        null=True,
        blank=True,
        help_text="Exact JSON response received from vendor"
    )
    status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code (e.g. 200, 400, 500)"
    )
    is_success = models.BooleanField(
        default=False,
        help_text="Whether vendor returned status == 'success'"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Any exception, timeout or vendor error message"
    )
    order = models.ForeignKey(
        'orders.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='vendor_logs',
        help_text="Linked customer order if this call was an order placement"
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Call latency in milliseconds"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Vendor API Log'
        verbose_name_plural = 'Vendor API Logs'

    def __str__(self):
        status_text = "SUCCESS" if self.is_success else f"HTTP {self.status_code}"
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {self.endpoint} [{status_text}]"
