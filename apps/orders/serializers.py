import re
from decimal import Decimal
from django.utils.crypto import get_random_string
from rest_framework import serializers
from apps.bundles.models import BundleCatalog, NetworkChoices
from apps.orders.models import (
    Order, OrderStatus, OrderType,
    AfaRegistration, ResultCheckerType, ResultCheckerVoucher
)
from apps.payments.models import Transaction

# ------------------------------------------------------------------------------
# GHANA PHONE NUMBER VALIDATOR
# Official Ghana network prefixes (as of 2024):
#   MTN:       024, 025, 053, 054, 055, 059
#   Telecel:   020, 050
#   AirtelTigo:027, 057, 026, 056, 028, 058
# ------------------------------------------------------------------------------
GHANA_MTN_PREFIXES      = ['024', '025', '053', '054', '055', '059']
GHANA_TELECEL_PREFIXES  = ['020', '050']
GHANA_AT_PREFIXES       = ['027', '057', '026', '056', '028', '058']

ALL_GHANA_PREFIXES = GHANA_MTN_PREFIXES + GHANA_TELECEL_PREFIXES + GHANA_AT_PREFIXES

NETWORK_PREFIX_MAP = {
    NetworkChoices.MTN: GHANA_MTN_PREFIXES,
    NetworkChoices.TELECEL: GHANA_TELECEL_PREFIXES,
    NetworkChoices.AT_BIGDATA: GHANA_AT_PREFIXES,
    NetworkChoices.AT_ISHARE: GHANA_AT_PREFIXES,
}


def normalize_ghana_phone(phone: str) -> str:
    """Normalize a Ghana phone number to local 10-digit format (e.g. 0241234567)."""
    phone = phone.strip().replace(' ', '').replace('-', '')
    if phone.startswith('+233') and len(phone) == 13:
        return '0' + phone[4:]
    if phone.startswith('233') and len(phone) == 12:
        return '0' + phone[3:]
    return phone


def validate_ghana_phone(phone: str, network: str = None) -> str:
    """
    Validates and normalizes a Ghana phone number.
    Optionally checks that the prefix matches the selected network.
    """
    normalized = normalize_ghana_phone(phone)

    if not re.match(r'^0[2-9]\d{8}$', normalized):
        raise serializers.ValidationError(
            f"'{phone}' is not a valid Ghana phone number. "
            "Use the format 024XXXXXXX or +233XXXXXXXXX."
        )

    prefix = normalized[:3]
    if prefix not in ALL_GHANA_PREFIXES:
        raise serializers.ValidationError(
            f"Phone number prefix '{prefix}' is not a registered Ghana network prefix."
        )

    if network:
        expected_prefixes = NETWORK_PREFIX_MAP.get(network, [])
        if expected_prefixes and prefix not in expected_prefixes:
            raise serializers.ValidationError(
                f"Phone number '{normalized}' does not belong to the {network.upper()} network. "
                f"Expected prefixes: {', '.join(expected_prefixes)}."
            )

    return normalized


# ==============================================================================
# BUNDLE SERIALIZERS
# ==============================================================================

class BundleCatalogSerializer(serializers.ModelSerializer):
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    data_label = serializers.SerializerMethodField()
    profit_margin = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = BundleCatalog
        fields = [
            'id',
            'network',
            'network_display',
            'name',
            'data_size',
            'data_label',
            'selling_price',
            'is_active',
            'display_order',
            # Admin-only fields are excluded from the customer-facing API
            # 'vendor_price', 'profit_margin', 'package_id'
        ]

    def get_data_label(self, obj) -> str:
        size = float(obj.data_size)
        if size < 1:
            return f"{int(size * 1024)} MB"
        if size == int(size):
            return f"{int(size)} GB"
        return f"{size} GB"


# ==============================================================================
# ORDER SERIALIZERS
# ==============================================================================

class AfaRegistrationCreateSerializer(serializers.Serializer):
    """KYC fields required for MTN AFA Bundle Registration."""
    full_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20)
    ghana_card_number = serializers.CharField(max_length=30)
    town = serializers.CharField(max_length=100)
    occupation = serializers.CharField(max_length=100)

    def validate_phone_number(self, value):
        return validate_ghana_phone(value, network=NetworkChoices.MTN)

    def validate_ghana_card_number(self, value):
        # Format: GHA-XXXXXXXXX-X (e.g. GHA-123456789-0)
        clean = value.strip().upper()
        if not re.match(r'^GHA-\d{9}-\d$', clean):
            raise serializers.ValidationError(
                "Invalid Ghana Card number format. Expected: GHA-XXXXXXXXX-X (e.g. GHA-123456789-0)"
            )
        return clean


class ResultCheckerOrderSerializer(serializers.Serializer):
    """Fields required for WAEC Result Checker purchase."""
    checker_type_code = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1, max_value=20)

    def validate_checker_type_code(self, value):
        try:
            return ResultCheckerType.objects.get(code=value.upper(), is_active=True)
        except ResultCheckerType.DoesNotExist:
            raise serializers.ValidationError(
                f"Result checker type '{value}' is not available. Choose BECE or WASSCE."
            )


class OrderCreateSerializer(serializers.Serializer):
    """
    Create a new customer order. Supports all 3 order types:
    - data_bundle
    - afa_registration
    - result_checker
    """
    order_type = serializers.ChoiceField(choices=OrderType.choices, default=OrderType.DATA_BUNDLE)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(required=False, allow_blank=True)

    # Data Bundle fields
    network = serializers.ChoiceField(choices=NetworkChoices.choices, required=False)
    bundle_id = serializers.IntegerField(required=False)

    # AFA Registration fields (required when order_type=afa_registration)
    afa_data = AfaRegistrationCreateSerializer(required=False)

    # Result Checker fields (required when order_type=result_checker)
    result_checker_data = ResultCheckerOrderSerializer(required=False)

    def validate_customer_phone(self, value):
        return normalize_ghana_phone(value)

    def validate(self, attrs):
        order_type = attrs.get('order_type', OrderType.DATA_BUNDLE)

        if order_type == OrderType.DATA_BUNDLE:
            if not attrs.get('network'):
                raise serializers.ValidationError({"network": "Network is required for data bundle orders."})
            if not attrs.get('bundle_id'):
                raise serializers.ValidationError({"bundle_id": "bundle_id is required for data bundle orders."})

            # Validate phone matches network
            phone = attrs.get('customer_phone', '')
            network = attrs.get('network', '')
            try:
                validate_ghana_phone(phone, network=network)
            except serializers.ValidationError as e:
                raise serializers.ValidationError({"customer_phone": e.detail})

            # Fetch bundle
            try:
                bundle = BundleCatalog.objects.get(id=attrs['bundle_id'], is_active=True)
                if bundle.network != network:
                    raise serializers.ValidationError({
                        "bundle_id": f"Bundle '{bundle.name}' belongs to {bundle.network.upper()}, not {network.upper()}."
                    })
                attrs['bundle'] = bundle
            except BundleCatalog.DoesNotExist:
                raise serializers.ValidationError({"bundle_id": "Bundle not found or not active."})

        elif order_type == OrderType.AFA_REGISTRATION:
            if not attrs.get('afa_data'):
                raise serializers.ValidationError({
                    "afa_data": "AFA registration details are required."
                })

        elif order_type == OrderType.RESULT_CHECKER:
            if not attrs.get('result_checker_data'):
                raise serializers.ValidationError({
                    "result_checker_data": "Result checker details are required."
                })

        return attrs

    def create(self, validated_data):
        order_type = validated_data['order_type']
        phone = validated_data['customer_phone']
        email = validated_data.get('customer_email', '')

        if order_type == OrderType.DATA_BUNDLE:
            bundle = validated_data['bundle']
            order = Order.objects.create(
                order_type=order_type,
                customer_phone=phone,
                customer_email=email,
                network=validated_data['network'],
                bundle=bundle,
                amount=bundle.selling_price,
                status=OrderStatus.PENDING_PAYMENT,
            )

        elif order_type == OrderType.AFA_REGISTRATION:
            order = Order.objects.create(
                order_type=order_type,
                customer_phone=phone,
                customer_email=email,
                network=NetworkChoices.MTN,
                amount=Decimal('10.00'),  # Standard AFA registration fee
                status=OrderStatus.PENDING_PAYMENT,
            )
            afa = validated_data['afa_data']
            AfaRegistration.objects.create(
                order=order,
                full_name=afa['full_name'],
                phone_number=afa['phone_number'],
                ghana_card_number=afa['ghana_card_number'],
                town=afa['town'],
                occupation=afa['occupation'],
            )

        elif order_type == OrderType.RESULT_CHECKER:
            result_data = validated_data['result_checker_data']
            checker_type = result_data['checker_type_code']  # Already resolved to object in validate
            quantity = result_data['quantity']
            total = checker_type.selling_price * quantity

            # Verify stock
            available_stock = checker_type.available_stock
            if available_stock < quantity:
                raise serializers.ValidationError({
                    "result_checker_data": (
                        f"Only {available_stock} voucher(s) available for {checker_type.code}. "
                        f"Requested: {quantity}."
                    )
                })

            order = Order.objects.create(
                order_type=order_type,
                customer_phone=phone,
                customer_email=email,
                checker_type=checker_type,
                quantity=quantity,
                amount=total,
                status=OrderStatus.PENDING_PAYMENT,
            )

        return order


class OrderStatusSerializer(serializers.ModelSerializer):
    """Public-facing order status response (no sensitive fields)."""
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    bundle_name = serializers.SerializerMethodField()
    checker_type_name = serializers.CharField(source='checker_type.name', read_only=True, default='')
    checker_type_code = serializers.CharField(source='checker_type.code', read_only=True, default='')
    vouchers = serializers.SerializerMethodField()
    sms_sent = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'reference',
            'order_type',
            'order_type_display',
            'customer_phone',
            'network',
            'bundle_name',
            'checker_type_name',
            'checker_type_code',
            'quantity',
            'amount',
            'status',
            'status_display',
            'vendor_status',
            'failure_reason',
            'vouchers',
            'sms_sent',
            'created_at',
            'updated_at',
        ]

    def get_sms_sent(self, obj) -> bool:
        return obj.sms_logs.filter(status='sent').exists()

    def get_bundle_name(self, obj) -> str:
        return str(obj.bundle) if obj.bundle else ""

    def get_vouchers(self, obj):
        """Only include voucher data if order is completed."""
        if obj.status == OrderStatus.COMPLETED and obj.order_type == OrderType.RESULT_CHECKER:
            return [
                {
                    "serial_number": v.serial_number,
                    "pin": v.pin,
                    "type": v.checker_type.code
                }
                for v in obj.vouchers.all()
            ]
        return []


class ResultCheckerTypeSerializer(serializers.ModelSerializer):
    """Serializer for WAEC Result Checker products."""
    available_stock = serializers.IntegerField(read_only=True)

    class Meta:
        model = ResultCheckerType
        fields = [
            'id',
            'code',
            'name',
            'description',
            'selling_price',
            'available_stock',
            'is_active',
        ]

