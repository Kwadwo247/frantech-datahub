from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.db.models import Count

from apps.bundles.models import BundleCatalog, NetworkChoices
from apps.bundles.serializers import BundleCatalogSerializer, NetworkChoiceSerializer
from apps.orders.serializers import (
    GHANA_MTN_PREFIXES,
    GHANA_TELECEL_PREFIXES,
    GHANA_AT_PREFIXES,
)


class BundleCatalogListView(APIView):
    """
    GET /api/bundles/
    Returns active bundle catalog.
    Optional Query Parameters:
        - network: filter by network code (mtn, telecel, at_bigdata, at_ishare)
        - min_size: filter by minimum GB data size
        - max_size: filter by maximum GB data size
    """
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = BundleCatalog.objects.filter(is_active=True)

        network = request.query_params.get('network', '').strip().lower()
        if network:
            if network not in NetworkChoices.values:
                return Response(
                    {"error": f"Invalid network '{network}'. Choose from: {', '.join(NetworkChoices.values)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset = queryset.filter(network=network)

        min_size = request.query_params.get('min_size')
        if min_size:
            try:
                queryset = queryset.filter(data_size__gte=float(min_size))
            except ValueError:
                pass

        max_size = request.query_params.get('max_size')
        if max_size:
            try:
                queryset = queryset.filter(data_size__lte=float(max_size))
            except ValueError:
                pass

        queryset = queryset.order_by('network', 'display_order', 'data_size')
        serializer = BundleCatalogSerializer(queryset, many=True)
        return Response({
            "count": len(serializer.data),
            "bundles": serializer.data
        })


class BundleNetworkListView(APIView):
    """
    GET /api/bundles/networks/
    Returns all supported network operators with active bundle counts and brand styling hints.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        network_meta = {
            NetworkChoices.MTN: {
                "name": "MTN Ghana",
                "prefixes": GHANA_MTN_PREFIXES,
                "color": "#FFCC00",
            },
            NetworkChoices.TELECEL: {
                "name": "Telecel Ghana",
                "prefixes": GHANA_TELECEL_PREFIXES,
                "color": "#E60000",
            },
            NetworkChoices.AT_BIGDATA: {
                "name": "AT (Big Time Data)",
                "prefixes": GHANA_AT_PREFIXES,
                "color": "#0055A5",
            },
            NetworkChoices.AT_ISHARE: {
                "name": "AT (iShare)",
                "prefixes": GHANA_AT_PREFIXES,
                "color": "#003366",
            },
        }

        # Calculate active bundle count per network
        counts = {
            item['network']: item['total']
            for item in BundleCatalog.objects.filter(is_active=True).values('network').annotate(total=Count('id'))
        }

        data = []
        for code, choice_label in NetworkChoices.choices:
            meta = network_meta.get(code, {"name": choice_label, "prefixes": [], "color": "#666666"})
            data.append({
                "code": code,
                "name": meta["name"],
                "bundle_count": counts.get(code, 0),
                "prefixes": meta["prefixes"],
                "color": meta["color"],
            })

        serializer = NetworkChoiceSerializer(data, many=True)
        return Response({"networks": serializer.data})
