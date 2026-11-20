import random
import string
from django.core.management.base import BaseCommand
from apps.orders.models import ResultCheckerType, ResultCheckerVoucher


class Command(BaseCommand):
    help = "Seeds initial inventory of WAEC Result Checker vouchers (BECE and WASSCE)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of vouchers to seed for each active checker type (default: 20)'
        )

    def handle(self, *args, **options):
        count = options['count']
        checker_types = ResultCheckerType.objects.filter(is_active=True)

        if not checker_types.exists():
            self.stdout.write(self.style.WARNING("No active ResultCheckerTypes found. Creating defaults..."))
            ResultCheckerType.objects.get_or_create(
                code="BECE",
                defaults={"name": "BECE Result Checker", "selling_price": 16.00, "vendor_price": 13.50}
            )
            ResultCheckerType.objects.get_or_create(
                code="WASSCE",
                defaults={"name": "WASSCE Result Checker", "selling_price": 16.00, "vendor_price": 13.50}
            )
            checker_types = ResultCheckerType.objects.filter(is_active=True)

        total_seeded = 0
        for checker in checker_types:
            created_for_type = 0
            for _ in range(count):
                # Generate unique serial e.g. WAE-BECE-84729103
                rand_digits = ''.join(random.choices(string.digits, k=8))
                serial = f"WAE-{checker.code}-{rand_digits}"

                # Generate 12-digit PIN e.g. 984210492817
                pin = ''.join(random.choices(string.digits, k=12))

                _, created = ResultCheckerVoucher.objects.get_or_create(
                    checker_type=checker,
                    serial_number=serial,
                    defaults={"pin": pin, "is_sold": False}
                )
                if created:
                    created_for_type += 1
                    total_seeded += 1

            self.stdout.write(
                f"Seeded {created_for_type} vouchers for {checker.code}. "
                f"Current in-stock: {checker.available_stock}"
            )

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {total_seeded} WAEC vouchers in total!"))
