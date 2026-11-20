from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'paystack_reference',
        'order_ref',
        'amount',
        'currency',
        'channel',
        'status',
        'gateway_response',
        'paid_at',
        'created_at',
    )
    list_filter = ('status', 'channel', 'created_at')
    search_fields = (
        'paystack_reference',
        'order__reference',
        'order__customer_phone',
        'gateway_response',
    )
    readonly_fields = (
        'order',
        'paystack_reference',
        'amount',
        'currency',
        'channel',
        'status',
        'gateway_response',
        'authorization_url',
        'access_code',
        'customer_ip',
        'raw_response',
        'paid_at',
        'created_at',
        'updated_at',
    )

    @admin.display(description='Order')
    def order_ref(self, obj):
        return obj.order.reference
