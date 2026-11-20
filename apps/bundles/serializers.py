from rest_framework import serializers
from apps.bundles.models import BundleCatalog, NetworkChoices
from apps.orders.serializers import (
    GHANA_MTN_PREFIXES,
    GHANA_TELECEL_PREFIXES,
    GHANA_AT_PREFIXES,
)


class BundleCatalogSerializer(serializers.ModelSerializer):
    """Public customer-facing bundle catalog item serializer."""
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    data_label = serializers.SerializerMethodField()

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
        ]

    def get_data_label(self, obj) -> str:
        size = float(obj.data_size)
        if size < 1:
            return f"{int(size * 1024)} MB"
        if size == int(size):
            return f"{int(size)} GB"
        return f"{size} GB"


class NetworkChoiceSerializer(serializers.Serializer):
    """Network choices metadata serializer for frontend filtering and display."""
    code = serializers.CharField()
    name = serializers.CharField()
    bundle_count = serializers.IntegerField()
    prefixes = serializers.ListField(child=serializers.CharField())
    color = serializers.CharField()
