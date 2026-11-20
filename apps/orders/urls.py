from django.urls import path
from .views import OrderCreateView, OrderDetailView, ResultCheckerTypeListView

urlpatterns = [
    path('', OrderCreateView.as_view(), name='order-create'),
    path('result-checkers/', ResultCheckerTypeListView.as_view(), name='result-checker-list'),
    path('<str:reference>/', OrderDetailView.as_view(), name='order-detail'),
]
