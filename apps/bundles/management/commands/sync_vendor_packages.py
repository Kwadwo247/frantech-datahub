from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.bundles.services.vendor_api import MyDataGigsClient, VendorAPIException


class Command(BaseCommand):
    help = "Syncs bundle packages directly from mydatagigs.com into the BundleCatalog."

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            default='all',
            help='Network to sync: mtn, telecel, at_bigdata, at_ishare, or all (default)'
        )
        parser.add_argument(
            '--markup',
            type=float,
            default=15.0,
            help='Markup percentage above vendor cost price (default: 15.0%%)'
        )

    def handle(self, *args, **options):
        client = MyDataGigsClient()
        network = options['network'].lower()
        markup = Decimal(str(options['markup']))

        if not client.api_key or client.api_key == "your_mydatagigs_api_key_here":
            self.stderr.write(self.style.WARNING(
                "\n[WARNING] VENDOR_API_KEY is not set in .env. Please configure your key first."
            ))
            return

        networks = ['mtn', 'telecel', 'at_bigdata', 'at_ishare'] if network == 'all' else [network]
        total_synced = 0

        for net in networks:
            self.stdout.write(f"Syncing packages for {net.upper()}...")
            try:
                count = client.sync_packages_to_catalog(net, default_markup_percent=markup)
                total_synced += count
                self.stdout.write(self.style.SUCCESS(f"  -> Synced {count} packages for {net.upper()}"))
            except VendorAPIException as e:
                self.stderr.write(self.style.ERROR(f"  -> Failed to sync {net.upper()}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nCompleted! Total packages synced/updated: {total_synced}"))
