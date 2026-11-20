"""
URL configuration for SellBundle project.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    return Response({
        "name": "SellBundle Ghana Data Reselling API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health/",
            "bundles": "/api/bundles/",
            "bundle_networks": "/api/bundles/networks/",
            "orders": "/api/orders/",
            "result_checkers": "/api/orders/result-checkers/",
            "payments_initialize": "/api/payments/initialize/",
            "payments_verify": "/api/payments/verify/<reference>/",
            "payments_webhook": "/api/payments/webhook/",
            "admin": "/admin/",
        }
    })

from apps.payments.views import PaystackSandboxCheckoutView

urlpatterns = [
    # Customer Storefront (Web UI)
    path('', TemplateView.as_view(template_name='index.html'), name='storefront'),

    # Paystack MoMo Sandbox Simulator (for local testing)
    path('sandbox/paystack/<str:reference>/', PaystackSandboxCheckoutView.as_view(), name='sandbox-checkout'),

    # Admin Portal
    path('admin/', admin.site.urls),

    # Financial Dashboard
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),

    # REST APIs
    path('api/', api_root, name='api-root'),
    path('api/', include('apps.accounts.urls')),
    path('api/bundles/', include('apps.bundles.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/payments/', include('apps.payments.urls')),
]
