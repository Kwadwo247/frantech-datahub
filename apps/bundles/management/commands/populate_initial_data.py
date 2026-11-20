from django.core.management.base import BaseCommand
from decimal import Decimal
from apps.bundles.models import BundleCatalog, NetworkChoices
from apps.orders.models import ResultCheckerType


class Command(BaseCommand):
    help = "Seeds initial bundle packages from vendor (mydatagigs.com) and WAEC result checker types."

    def handle(self, *args, **options):
        self.stdout.write("Populating bundle catalog from vendor specs...")

        # MTN Packages directly from mydatagigs vendor API documentation
        mtn_packages = [
            {"size": 1.0, "label": "1", "pkg_id": 1307872, "vendor_price": Decimal("4.34"), "sell_price": Decimal("5.50"), "order": 1},
            {"size": 2.0, "label": "2", "pkg_id": 638817, "vendor_price": Decimal("8.60"), "sell_price": Decimal("10.50"), "order": 2},
            {"size": 3.0, "label": "3", "pkg_id": 638822, "vendor_price": Decimal("12.80"), "sell_price": Decimal("15.00"), "order": 3},
            {"size": 4.0, "label": "4", "pkg_id": 638825, "vendor_price": Decimal("16.70"), "sell_price": Decimal("19.50"), "order": 4},
            {"size": 5.0, "label": "5", "pkg_id": 638826, "vendor_price": Decimal("20.80"), "sell_price": Decimal("24.50"), "order": 5},
            {"size": 6.0, "label": "6", "pkg_id": 638828, "vendor_price": Decimal("24.80"), "sell_price": Decimal("29.00"), "order": 6},
            {"size": 8.0, "label": "8", "pkg_id": 638842, "vendor_price": Decimal("33.00"), "sell_price": Decimal("38.50"), "order": 7},
            {"size": 10.0, "label": "10", "pkg_id": 638849, "vendor_price": Decimal("39.50"), "sell_price": Decimal("46.00"), "order": 8},
            {"size": 15.0, "label": "15", "pkg_id": 638853, "vendor_price": Decimal("58.00"), "sell_price": Decimal("67.50"), "order": 9},
            {"size": 20.0, "label": "20", "pkg_id": 638867, "vendor_price": Decimal("77.50"), "sell_price": Decimal("89.00"), "order": 10},
        ]

        for p in mtn_packages:
            BundleCatalog.objects.update_or_create(
                network=NetworkChoices.MTN,
                data_size=p["size"],
                defaults={
                    "name": f"MTN {p['label']} GB",
                    "package_id": p["pkg_id"],
                    "vendor_package_param": p["label"],
                    "vendor_price": p["vendor_price"],
                    "selling_price": p["sell_price"],
                    "display_order": p["order"],
                    "is_active": True,
                }
            )

        # Telecel packages
        telecel_packages = [
            {"size": 1.0, "label": "1", "vendor_price": Decimal("4.50"), "sell_price": Decimal("5.50"), "order": 1},
            {"size": 2.0, "label": "2", "vendor_price": Decimal("8.80"), "sell_price": Decimal("10.50"), "order": 2},
            {"size": 5.0, "label": "5", "vendor_price": Decimal("21.50"), "sell_price": Decimal("25.00"), "order": 3},
            {"size": 10.0, "label": "10", "vendor_price": Decimal("41.00"), "sell_price": Decimal("48.00"), "order": 4},
        ]
        for p in telecel_packages:
            BundleCatalog.objects.update_or_create(
                network=NetworkChoices.TELECEL,
                data_size=p["size"],
                defaults={
                    "name": f"Telecel {p['label']} GB",
                    "vendor_package_param": p["label"],
                    "vendor_price": p["vendor_price"],
                    "selling_price": p["sell_price"],
                    "display_order": p["order"],
                    "is_active": True,
                }
            )

        # AirtelTigo Big Time Data
        at_packages = [
            {"size": 1.0, "label": "1", "vendor_price": Decimal("4.20"), "sell_price": Decimal("5.00"), "order": 1},
            {"size": 2.0, "label": "2", "vendor_price": Decimal("8.40"), "sell_price": Decimal("10.00"), "order": 2},
            {"size": 5.0, "label": "5", "vendor_price": Decimal("20.00"), "sell_price": Decimal("24.00"), "order": 3},
            {"size": 10.0, "label": "10", "vendor_price": Decimal("38.50"), "sell_price": Decimal("45.00"), "order": 4},
        ]
        for p in at_packages:
            BundleCatalog.objects.update_or_create(
                network=NetworkChoices.AT_BIGDATA,
                data_size=p["size"],
                defaults={
                    "name": f"AT Big Time {p['label']} GB",
                    "vendor_package_param": p["label"],
                    "vendor_price": p["vendor_price"],
                    "selling_price": p["sell_price"],
                    "display_order": p["order"],
                    "is_active": True,
                }
            )

        # AirtelTigo iShare Data
        at_ishare_packages = [
            {"size": 1.0, "label": "1", "vendor_price": Decimal("4.20"), "sell_price": Decimal("5.00"), "order": 1},
            {"size": 2.0, "label": "2", "vendor_price": Decimal("8.40"), "sell_price": Decimal("10.00"), "order": 2},
            {"size": 3.0, "label": "3", "vendor_price": Decimal("12.50"), "sell_price": Decimal("15.00"), "order": 3},
            {"size": 5.0, "label": "5", "vendor_price": Decimal("20.00"), "sell_price": Decimal("24.00"), "order": 4},
            {"size": 10.0, "label": "10", "vendor_price": Decimal("38.50"), "sell_price": Decimal("45.00"), "order": 5},
        ]
        for p in at_ishare_packages:
            BundleCatalog.objects.update_or_create(
                network=NetworkChoices.AT_ISHARE,
                data_size=p["size"],
                defaults={
                    "name": f"AT iShare {p['label']} GB",
                    "vendor_package_param": p["label"],
                    "vendor_price": p["vendor_price"],
                    "selling_price": p["sell_price"],
                    "display_order": p["order"],
                    "is_active": True,
                }
            )

        # WAEC Result Checkers
        ResultCheckerType.objects.update_or_create(
            code="BECE",
            defaults={
                "name": "BECE Result Checker",
                "description": "Basic Education Certificate Examination Checker PIN",
                "vendor_price": Decimal("13.50"),
                "selling_price": Decimal("16.00"),
                "is_active": True,
            }
        )
        ResultCheckerType.objects.update_or_create(
            code="WASSCE",
            defaults={
                "name": "WASSCE Result Checker",
                "description": "West African Senior School Certificate Examination Checker PIN",
                "vendor_price": Decimal("13.50"),
                "selling_price": Decimal("16.00"),
                "is_active": True,
            }
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded bundle packages and result checkers!"))
