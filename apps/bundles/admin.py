from django.contrib import admin
from .models import BundleCatalog, VendorRequestLog


@admin.register(BundleCatalog)
class BundleCatalogAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'network',
        'data_size',
        'package_id',
        'vendor_package_param',
        'vendor_price',
        'selling_price',
        'profit_margin_display',
        'is_active',
        'display_order',
    )
    list_filter = ('network', 'is_active')
    search_fields = ('name', 'vendor_package_param', 'package_id')
    list_editable = ('selling_price', 'is_active', 'display_order')
    ordering = ('network', 'display_order', 'data_size')

    @admin.display(description='Profit (GHS)')
    def profit_margin_display(self, obj):
        return f"GHS {obj.profit_margin:.2f}"


@admin.register(VendorRequestLog)
class VendorRequestLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'endpoint',
        'http_method',
        'status_code',
        'is_success',
        'duration_ms',
        'order',
    )
    list_filter = ('is_success', 'http_method', 'endpoint')
    search_fields = ('endpoint', 'error_message', 'order__reference', 'order__customer_phone')
    readonly_fields = (
        'endpoint',
        'http_method',
        'request_payload',
        'response_payload',
        'status_code',
        'is_success',
        'error_message',
        'order',
        'duration_ms',
        'created_at',
    )

    def has_add_permission(self, request):
        return False  # Logs are read-only
