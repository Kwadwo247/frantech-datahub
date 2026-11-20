from decimal import Decimal
from django.test import TestCase
from apps.bundles.models import BundleCatalog, NetworkChoices
from apps.orders.models import Order, OrderStatus, OrderType, AfaRegistration, ResultCheckerType, ResultCheckerVoucher


class OrderModelTest(TestCase):
    def setUp(self):
        self.bundle = BundleCatalog.objects.create(
            network=NetworkChoices.MTN,
            name="MTN 1GB Data",
            data_size=1.0,
            package_id=1307872,
            vendor_package_param="1",
            vendor_price=Decimal("4.34"),
            selling_price=Decimal("5.50"),
        )

    def test_order_creation_and_reference(self):
        """Verify order generates unique reference and calculates paid state."""
        order = Order.objects.create(
            customer_phone="0241234567",
            customer_email="customer@example.com",
            network="mtn",
            bundle=self.bundle,
            amount=self.bundle.selling_price,
            status=OrderStatus.PENDING_PAYMENT
        )
        self.assertTrue(order.reference.startswith("SB-"))
        self.assertFalse(order.is_paid)

        order.status = OrderStatus.PAID
        order.save()
        self.assertTrue(order.is_paid)

    def test_afa_registration_relationship(self):
        """Verify AFA registration links cleanly to parent order."""
        order = Order.objects.create(
            order_type=OrderType.AFA_REGISTRATION,
            customer_phone="0241234567",
            amount=Decimal("10.00"),
            status=OrderStatus.PAID
        )
        afa = AfaRegistration.objects.create(
            order=order,
            full_name="Kwame Mensah",
            phone_number="0241234567",
            ghana_card_number="GHA-123456789-0",
            town="Accra",
            occupation="Trader"
        )
        self.assertEqual(order.afa_registration.full_name, "Kwame Mensah")

    def test_result_checker_voucher_stock(self):
        """Verify voucher stock count and assignment."""
        checker = ResultCheckerType.objects.create(
            code="BECE",
            name="BECE Result Checker",
            vendor_price=Decimal("13.50"),
            selling_price=Decimal("16.00")
        )
        self.assertEqual(checker.profit_margin, Decimal("2.50"))
        v1 = ResultCheckerVoucher.objects.create(
            checker_type=checker,
            serial_number="WG1234567",
            pin="123456789012"
        )
        self.assertEqual(checker.available_stock, 1)

        # Mark as sold
        order = Order.objects.create(
            order_type=OrderType.RESULT_CHECKER,
            customer_phone="0241234567",
            amount=Decimal("16.00"),
            status=OrderStatus.PAID
        )
        v1.is_sold = True
        v1.order = order
        v1.save()

        self.assertEqual(checker.available_stock, 0)


class OrderAPITest(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.bundle = BundleCatalog.objects.create(
            network=NetworkChoices.MTN,
            name="MTN 1GB Data",
            data_size=1.0,
            package_id=1307872,
            vendor_package_param="1",
            vendor_price=Decimal("4.34"),
            selling_price=Decimal("5.50"),
            is_active=True,
        )
        self.checker = ResultCheckerType.objects.create(
            code="BECE",
            name="BECE Result Checker",
            vendor_price=Decimal("13.50"),
            selling_price=Decimal("16.00"),
            is_active=True
        )
        ResultCheckerVoucher.objects.create(
            checker_type=self.checker,
            serial_number="WG1234567",
            pin="123456789012"
        )

    def test_create_data_bundle_order_success(self):
        """POST /api/orders/ creates data bundle order."""
        payload = {
            "order_type": "data_bundle",
            "customer_phone": "0241234567",
            "customer_email": "test@example.com",
            "network": "mtn",
            "bundle_id": self.bundle.id,
            "auto_initialize_payment": False
        }
        response = self.client.post('/api/orders/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['order']['reference'].startswith('SB-'))
        self.assertEqual(data['order']['status'], 'pending_payment')
        self.assertEqual(data['order']['amount'], '5.50')

    def test_phone_network_mismatch_fails(self):
        """Entering Telecel 020 number for MTN order returns 400."""
        payload = {
            "order_type": "data_bundle",
            "customer_phone": "0201234567",
            "network": "mtn",
            "bundle_id": self.bundle.id,
            "auto_initialize_payment": False
        }
        response = self.client.post('/api/orders/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("customer_phone", response.json())

    def test_create_result_checker_order(self):
        """POST /api/orders/ for result checker reserves available voucher."""
        payload = {
            "order_type": "result_checker",
            "customer_phone": "0241234567",
            "result_checker_data": {
                "checker_type_code": "BECE",
                "quantity": 1
            },
            "auto_initialize_payment": False
        }
        response = self.client.post('/api/orders/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['order']['amount'], '16.00')

    def test_result_checker_insufficient_stock_fails(self):
        """Requesting more vouchers than available returns 400."""
        payload = {
            "order_type": "result_checker",
            "customer_phone": "0241234567",
            "result_checker_data": {
                "checker_type_code": "BECE",
                "quantity": 5
            },
            "auto_initialize_payment": False
        }
        response = self.client.post('/api/orders/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("result_checker_data", response.json())

    def test_create_afa_registration_order(self):
        """POST /api/orders/ for AFA registration creates parent order and KYC entry."""
        payload = {
            "order_type": "afa_registration",
            "customer_phone": "0241234567",
            "afa_data": {
                "full_name": "Ama Serwaa",
                "phone_number": "0241234567",
                "ghana_card_number": "GHA-123456789-1",
                "town": "Kumasi",
                "occupation": "Teacher"
            },
            "auto_initialize_payment": False
        }
        response = self.client.post('/api/orders/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['order']['amount'], '10.00')
        self.assertEqual(AfaRegistration.objects.filter(full_name="Ama Serwaa").count(), 1)

    def test_get_order_detail(self):
        """GET /api/orders/<reference>/ retrieves order status."""
        order = Order.objects.create(
            customer_phone="0241234567",
            amount=Decimal("5.50"),
            bundle=self.bundle,
            status=OrderStatus.PENDING_PAYMENT
        )
        response = self.client.get(f'/api/orders/{order.reference}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['reference'], order.reference)

    def test_get_order_detail_not_found(self):
        """GET /api/orders/SB-NONEXISTENT/ returns 404."""
        response = self.client.get('/api/orders/SB-NONEXISTENT/')
        self.assertEqual(response.status_code, 404)

    def test_list_result_checkers(self):
        """GET /api/orders/result-checkers/ returns active checkers and available stock."""
        response = self.client.get('/api/orders/result-checkers/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('result_checkers', data)
        bece = next(c for c in data['result_checkers'] if c['code'] == 'BECE')
        self.assertEqual(bece['available_stock'], 1)

    def test_create_result_checker_order_saves_checker_type(self):
        """Verify POST /api/orders/ saves checker_type ForeignKey on Order."""
        payload = {
            "order_type": "result_checker",
            "customer_phone": "0241234567",
            "result_checker_data": {
                "checker_type_code": "BECE",
                "quantity": 1
            },
            "auto_initialize_payment": False
        }
        response = self.client.post('/api/orders/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        ref = response.json()['order']['reference']
        order = Order.objects.get(reference=ref)
        self.assertEqual(order.checker_type, self.checker)
        self.assertEqual(response.json()['order']['checker_type_code'], 'BECE')
        self.assertEqual(response.json()['order']['checker_type_name'], 'BECE Result Checker')


class DeliveryTaskTest(TestCase):
    def setUp(self):
        self.bece = ResultCheckerType.objects.create(
            code="BECE",
            name="BECE Result Checker",
            vendor_price=Decimal("13.50"),
            selling_price=Decimal("16.00"),
            is_active=True
        )
        self.wassce = ResultCheckerType.objects.create(
            code="WASSCE",
            name="WASSCE Result Checker",
            vendor_price=Decimal("13.50"),
            selling_price=Decimal("16.00"),
            is_active=True
        )

        # Create 2 BECE vouchers
        self.v_bece1 = ResultCheckerVoucher.objects.create(
            checker_type=self.bece, serial_number="BECE-001", pin="111111111111"
        )
        self.v_bece2 = ResultCheckerVoucher.objects.create(
            checker_type=self.bece, serial_number="BECE-002", pin="222222222222"
        )

        # Create 2 WASSCE vouchers
        self.v_wassce1 = ResultCheckerVoucher.objects.create(
            checker_type=self.wassce, serial_number="WASS-001", pin="333333333333"
        )
        self.v_wassce2 = ResultCheckerVoucher.objects.create(
            checker_type=self.wassce, serial_number="WASS-002", pin="444444444444"
        )

    def test_deliver_result_checker_multi_quantity(self):
        """Test dispensing 2 BECE vouchers accurately without touching WASSCE vouchers."""
        from apps.orders.tasks import execute_order_delivery

        order = Order.objects.create(
            order_type=OrderType.RESULT_CHECKER,
            customer_phone="0241234567",
            checker_type=self.bece,
            quantity=2,
            amount=Decimal("32.00"),
            status=OrderStatus.PAID
        )

        execute_order_delivery(order.id)
        order.refresh_from_db()

        self.assertEqual(order.status, OrderStatus.COMPLETED)
        vouchers = order.vouchers.all()
        self.assertEqual(vouchers.count(), 2)
        # All assigned vouchers must be BECE
        for v in vouchers:
            self.assertEqual(v.checker_type, self.bece)
            self.assertTrue(v.is_sold)

        # WASSCE vouchers must remain unsold
        self.assertEqual(ResultCheckerVoucher.objects.filter(checker_type=self.wassce, is_sold=False).count(), 2)

    def test_deliver_result_checker_insufficient_stock_fails(self):
        """Attempting to dispense more vouchers than in stock sets status to FAILED."""
        from apps.orders.tasks import execute_order_delivery

        order = Order.objects.create(
            order_type=OrderType.RESULT_CHECKER,
            customer_phone="0241234567",
            checker_type=self.bece,
            quantity=5,  # only 2 exist
            amount=Decimal("80.00"),
            status=OrderStatus.PAID
        )

        execute_order_delivery(order.id)
        order.refresh_from_db()

        self.assertEqual(order.status, OrderStatus.FAILED)
        self.assertIn("Insufficient BECE vouchers", order.failure_reason)

    def test_dispatch_delivery_celery_offline_fallback(self):
        """When Celery broker is offline, dispatch_delivery executes synchronously via fallback."""
        from unittest.mock import patch
        from apps.orders.tasks import dispatch_delivery

        order = Order.objects.create(
            order_type=OrderType.RESULT_CHECKER,
            customer_phone="0241234567",
            checker_type=self.bece,
            quantity=1,
            amount=Decimal("16.00"),
            status=OrderStatus.PAID
        )

        with patch('apps.orders.tasks.deliver_order.delay', side_effect=Exception("Redis connection refused")):
            dispatch_delivery(order.id)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertEqual(order.vouchers.count(), 1)


