from django.urls import path
from .views import BundleCatalogListView, BundleNetworkListView

urlpatterns = [
    path('', BundleCatalogListView.as_view(), name='bundle-list'),
    path('networks/', BundleNetworkListView.as_view(), name='bundle-networks'),
]
