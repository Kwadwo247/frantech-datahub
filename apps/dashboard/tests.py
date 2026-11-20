from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.bundles.models import BundleCatalog, NetworkChoices
from apps.orders.models import (
    Order, OrderStatus, OrderType, AfaRegistration, AfaStatus,
    ResultCheckerType, ResultCheckerVoucher
)


class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.staff_user = User.objects.create_user(
            username="staff_admin",
            password="testpassword123",
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular_user",
            password="testpassword123",
            is_staff=False
        )

        # Products
        self.bundle = BundleCatalog.objects.create(
            network=NetworkChoices.MTN,
            name="MTN 10GB Data",
            data_size=10.0,
            package_id=638849,
            vendor_package_param="10",
            vendor_price=Decimal("39.50"),
            selling_price=Decimal("46.00"),
            is_active=True,
        )
        self.checker_type = ResultCheckerType.objects.create(
            code="BECE",
            name="BECE Result Checker",
            vendor_price=Decimal("13.50"),
            selling_price=Decimal("16.00"),
            is_active=True,
        )
        ResultCheckerVoucher.objects.create(
            checker_type=self.checker_type,
            serial_number="BECE-12345",
            pin="999888777666",
            is_sold=False
        )

        # Orders
        self.paid_bundle_order = Order.objects.create(
            order_type=OrderType.DATA_BUNDLE,
            customer_phone="0241234567",
            network="mtn",
            bundle=self.bundle,
            amount=Decimal("46.00"),
            status=OrderStatus.COMPLETED
        )
        self.paid_checker_order = Order.objects.create(
            order_type=OrderType.RESULT_CHECKER,
            customer_phone="0247654321",
            checker_type=self.checker_type,
            quantity=1,
            amount=Decimal("16.00"),
            status=OrderStatus.COMPLETED
        )
        self.afa_order = Order.objects.create(
            order_type=OrderType.AFA_REGISTRATION,
            customer_phone="0240001122",
            amount=Decimal("10.00"),
            status=OrderStatus.PAID
        )
        self.afa_reg = AfaRegistration.objects.create(
            order=self.afa_order,
            full_name="Kofi Mensah",
            phone_number="0240001122",
            ghana_card_number="GHA-123456789-0",
            town="Kumasi",
            occupation="Farmer",
            status=AfaStatus.PENDING
        )

    def test_anonymous_access_redirects_to_login(self):
        """Unauthenticated access should redirect to the admin login page."""
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_non_staff_access_redirects_to_login(self):
        """Non-staff authenticated user should be denied access and redirected."""
        self.client.login(username="regular_user", password="testpassword123")
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)

    def test_staff_access_loads_dashboard_successfully(self):
        """Staff member can load the dashboard with correct metrics in context."""
        self.client.login(username="staff_admin", password="testpassword123")
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/dashboard/index.html')

        # Verify key context values
        ctx = response.context
        self.assertGreaterEqual(ctx['total_revenue'], Decimal("72.00"))
        self.assertGreaterEqual(ctx['gross_profit'], Decimal("19.00"))
        self.assertEqual(ctx['afa_pending_count'], 1)
        self.assertEqual(len(ctx['checker_stock']), 1)
        self.assertIn(self.paid_bundle_order, ctx['recent_orders'])

    def test_chart_revenue_daily_api(self):
        """Verify the daily revenue chart JSON API returns valid timeseries data."""
        self.client.login(username="staff_admin", password="testpassword123")
        response = self.client.get(reverse('dashboard:chart-revenue'), {'days': 7})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('revenue', data)
        self.assertIn('orders', data)
        self.assertEqual(len(data['labels']), 7)
        self.assertGreater(sum(data['revenue']), 0)

    def test_chart_order_types_api(self):
        """Verify the order types breakdown chart JSON API."""
        self.client.login(username="staff_admin", password="testpassword123")
        response = self.client.get(reverse('dashboard:chart-order-types'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('revenue', data)
        self.assertIn('counts', data)
        self.assertIn('Data Bundles', data['labels'])

    def test_chart_network_breakdown_api(self):
        """Verify the network breakdown chart JSON API for data bundles."""
        self.client.login(username="staff_admin", password="testpassword123")
        response = self.client.get(reverse('dashboard:chart-networks'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('revenue', data)
        self.assertIn('MTN', data['labels'])

    def test_afa_single_approve_success(self):
        """POST to single AFA approval marks the registration as submitted."""
        self.client.login(username="staff_admin", password="testpassword123")
        url = reverse('dashboard:afa-approve-single', kwargs={'pk': self.afa_reg.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'submitted')

        self.afa_reg.refresh_from_db()
        self.assertEqual(self.afa_reg.status, AfaStatus.SUBMITTED)

    def test_afa_single_approve_get_not_allowed(self):
        """GET request to single AFA approve endpoint should be rejected with 405."""
        self.client.login(username="staff_admin", password="testpassword123")
        url = reverse('dashboard:afa-approve-single', kwargs={'pk': self.afa_reg.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_afa_single_approve_not_found(self):
        """Approving non-existent or already processed registration returns 404."""
        self.client.login(username="staff_admin", password="testpassword123")
        url = reverse('dashboard:afa-approve-single', kwargs={'pk': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_afa_batch_approve_success(self):
        """POST to batch AFA approval marks all pending registrations as submitted."""
        self.client.login(username="staff_admin", password="testpassword123")
        url = reverse('dashboard:afa-approve-all')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['updated'], 1)

        self.afa_reg.refresh_from_db()
        self.assertEqual(self.afa_reg.status, AfaStatus.SUBMITTED)

    def test_afa_batch_approve_get_not_allowed(self):
        """GET request to batch AFA approve should return 405."""
        self.client.login(username="staff_admin", password="testpassword123")
        url = reverse('dashboard:afa-approve-all')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
