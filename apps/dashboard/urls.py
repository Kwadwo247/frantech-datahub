from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),

    # Chart data JSON APIs
    path('api/chart/revenue/', views.chart_revenue_daily, name='chart-revenue'),
    path('api/chart/order-types/', views.chart_order_types, name='chart-order-types'),
    path('api/chart/networks/', views.chart_network_breakdown, name='chart-networks'),

    # AFA actions
    path('api/afa/approve-all/', views.afa_batch_approve, name='afa-approve-all'),
    path('api/afa/approve/<int:pk>/', views.afa_approve_single, name='afa-approve-single'),
]
