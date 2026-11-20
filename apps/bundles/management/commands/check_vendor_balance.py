from django.core.management.base import BaseCommand
from apps.bundles.services.vendor_api import MyDataGigsClient, VendorAPIException


class Command(BaseCommand):
    help = "Tests the vendor API integration and fetches the live wallet balance from mydatagigs.com."

    def handle(self, *args, **options):
        self.stdout.write("Connecting to vendor API at mydatagigs.com...")
        client = MyDataGigsClient()

        if not client.api_key or client.api_key == "your_mydatagigs_api_key_here":
            self.stderr.write(self.style.WARNING(
                "\n[WARNING] VENDOR_API_KEY is not set or still contains placeholder text in your .env file."
                "\nPlease open .env and set your real API key from https://mydatagigs.com/my-account/api-access/."
            ))
            return

        try:
            balance = client.get_wallet_balance()
            self.stdout.write(self.style.SUCCESS(
                f"\n[SUCCESS] Connected to mydatagigs.com successfully!"
                f"\nCurrent Wallet Balance: GHS {balance:,.2f}"
            ))
        except VendorAPIException as e:
            self.stderr.write(self.style.ERROR(
                f"\n[ERROR] Vendor API Error: {str(e)}"
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"\n[ERROR] Unexpected error: {str(e)}"
            ))
