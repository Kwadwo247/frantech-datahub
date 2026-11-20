from django.urls import path
from .views import (
    OrderPaymentInitiateView,
    PaystackWebhookView,
    PaystackVerifyView,
    PaystackSandboxCheckoutView,
)

urlpatterns = [
    path('initialize/', OrderPaymentInitiateView.as_view(), name='payment-initialize'),
    path('webhook/', PaystackWebhookView.as_view(), name='paystack-webhook'),
    path('verify/<str:reference>/', PaystackVerifyView.as_view(), name='payment-verify'),
    path('sandbox/<str:reference>/', PaystackSandboxCheckoutView.as_view(), name='payment-sandbox'),
]
