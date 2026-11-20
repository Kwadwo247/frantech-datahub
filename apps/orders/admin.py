from django.contrib import admin
from django.utils.html import format_html
from .models import Order, AfaRegistration, ResultCheckerType, ResultCheckerVoucher, SMSLog, SMSStatus


class AfaRegistrationInline(admin.StackedInline):
    model = AfaRegistration
    extra = 0
    can_delete = False


class VoucherInline(admin.TabularInline):
    model = ResultCheckerVoucher
    extra = 0
    readonly_fields = ('checker_type', 'serial_number', 'pin', 'sold_at')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'order_type',
        'customer_phone',
        'network',
        'bundle_info',
        'amount',
        'status',
        'vendor_order_id',
        'vendor_status',
        'created_at',
    )
    list_filter = ('status', 'order_type', 'network', 'created_at')
    search_fields = (
        'reference',
        'customer_phone',
        'customer_email',
        'vendor_order_id',
    )
    readonly_fields = (
        'reference',
        'created_at',
        'updated_at',
        'retry_count',
    )
    inlines = [AfaRegistrationInline, VoucherInline]
    date_hierarchy = 'created_at'

    @admin.display(description='Bundle / Items')
    def bundle_info(self, obj):
        if obj.bundle:
            return f"{obj.bundle.name}"
        if obj.order_type == 'result_checker':
            checker_name = obj.checker_type.name if obj.checker_type else "Result Checker"
            return f"{obj.quantity}x {checker_name}"
        if obj.order_type == 'afa_registration':
            return "AFA Registration"
        return "-"


@admin.register(AfaRegistration)
class AfaRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'phone_number',
        'ghana_card_number',
        'town',
        'occupation',
        'status',
        'order_ref',
        'created_at',
    )
    list_filter = ('status', 'town')
    search_fields = ('full_name', 'phone_number', 'ghana_card_number', 'town', 'occupation')
    list_editable = ('status',)

    @admin.display(description='Order')
    def order_ref(self, obj):
        return obj.order.reference


class ResultCheckerVoucherInline(admin.TabularInline):
    model = ResultCheckerVoucher
    extra = 1
    fields = ('serial_number', 'pin', 'is_sold', 'order')


@admin.register(ResultCheckerType)
class ResultCheckerTypeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'vendor_price',
        'selling_price',
        'profit_margin_display',
        'is_active',
        'stock_count',
    )
    list_editable = ('selling_price', 'is_active')
    inlines = [ResultCheckerVoucherInline]

    @admin.display(description='Profit (GHS)')
    def profit_margin_display(self, obj):
        return f"GHS {obj.profit_margin:.2f}"

    @admin.display(description='Available Stock')
    def stock_count(self, obj):
        return obj.available_stock


@admin.register(ResultCheckerVoucher)
class ResultCheckerVoucherAdmin(admin.ModelAdmin):
    list_display = ('checker_type', 'serial_number', 'pin', 'is_sold', 'order', 'sold_at')
    list_filter = ('checker_type', 'is_sold')
    search_fields = ('serial_number', 'pin', 'order__reference')


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'recipient',
        'provider',
        'status_badge',
        'order_ref',
        'message_preview',
    )
    list_filter = ('status', 'provider', 'created_at')
    search_fields = ('recipient', 'order__reference', 'message')
    readonly_fields = (
        'order', 'recipient', 'message', 'provider',
        'status', 'response_payload', 'error_message', 'created_at'
    )
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            SMSStatus.SENT: '#10b981',
            SMSStatus.FAILED: '#ef4444',
            SMSStatus.PENDING: '#f59e0b',
        }
        color = colors.get(obj.status, '#94a3b8')
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )

    @admin.display(description='Order')
    def order_ref(self, obj):
        return obj.order.reference if obj.order else '—'

    @admin.display(description='Message')
    def message_preview(self, obj):
        return obj.message[:60] + '…' if len(obj.message) > 60 else obj.message

