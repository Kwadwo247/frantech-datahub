from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from decouple import config

class FoundationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_environment_decouple_loaded(self):
        """Verify decouple loads environment variables without crashing."""
        debug_val = config('DEBUG', default=False, cast=bool)
        self.assertIsInstance(debug_val, bool)

    def test_api_root_endpoint(self):
        """Verify the /api/ root endpoint works and exposes our API routes."""
        response = self.client.get(reverse('api-root'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('endpoints', response.data)
        self.assertEqual(response.data['name'], "SellBundle Ghana Data Reselling API")

    def test_health_check_endpoint(self):
        """Verify the /api/health/ endpoint returns status healthy."""
        response = self.client.get(reverse('api-health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'healthy')

    def test_admin_changelist_template_rendering(self):
        """Verify Django admin changelist renders without Python 3.14 context copy error."""
        from django.contrib.auth.models import User
        admin_user = User.objects.create_superuser('admin_test', 'admin@example.com', 'password123')
        self.client.force_login(admin_user)

        # Test BundleCatalog changelist
        res_bundles = self.client.get('/admin/bundles/bundlecatalog/')
        self.assertEqual(res_bundles.status_code, 200)
        self.assertContains(res_bundles, "Select Bundle Package to change")

        # Test Order changelist
        res_orders = self.client.get('/admin/orders/order/')
        self.assertEqual(res_orders.status_code, 200)

        # Test Transaction changelist
        res_tx = self.client.get('/admin/payments/transaction/')
        self.assertEqual(res_tx.status_code, 200)

