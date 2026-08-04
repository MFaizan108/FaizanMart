from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Brand, Category, Product
from apps.inventory.models import Stock, Warehouse
from apps.vendors.models import Store

User = get_user_model()

DEMO_PASSWORD = "Demo@12345"

DEMO_ACCOUNTS = [
    {"email": "admin@faizanmart.site", "role": User.Role.SUPER_ADMIN, "label": "Admin"},
    {"email": "vendor@faizanmart.site", "role": User.Role.VENDOR, "label": "Vendor"},
    {"email": "customer@faizanmart.site", "role": User.Role.CUSTOMER, "label": "Customer"},
    {"email": "delivery@faizanmart.site", "role": User.Role.DELIVERY_BOY, "label": "Delivery Boy"},
]


class Command(BaseCommand):
    """Seeds the demo accounts + a small product catalog recruiters/interviewers can log
    in and click around with. Idempotent (get_or_create everywhere) so it's safe to run
    against an existing database — re-running just fills in whatever's still missing."""

    help = "Seed demo accounts (admin/vendor/customer/delivery boy) and sample catalog data."

    def handle(self, *args, **options):
        users = {}
        for account in DEMO_ACCOUNTS:
            if account["role"] == User.Role.SUPER_ADMIN:
                user, created = self._get_or_create_superuser(account["email"])
            else:
                user, created = User.objects.get_or_create(
                    email=account["email"],
                    defaults={"role": account["role"], "is_email_verified": True},
                )
                if created:
                    user.set_password(DEMO_PASSWORD)
                    user.save(update_fields=["password"])
            users[account["role"]] = user
            self._report(account["label"], account["email"], created)

        store, created = Store.objects.get_or_create(
            owner=users[User.Role.VENDOR],
            defaults={
                "name": "Faizan Electronics",
                "status": Store.Status.APPROVED,
                "description": "Demo storefront seeded for recruiters/interviewers.",
                "approved_at": timezone.now(),
            },
        )
        self._report("Store", store.name, created)

        warehouse, created = Warehouse.objects.get_or_create(
            code="MAIN",
            defaults={"name": "Main Warehouse", "city": "Karachi", "country": "Pakistan"},
        )
        self._report("Warehouse", warehouse.name, created)

        category, _ = Category.objects.get_or_create(name="Laptops", defaults={"is_featured": True})
        brand, _ = Brand.objects.get_or_create(name="Generic")

        products = [
            {"name": "14-inch Ultrabook, 16GB RAM, 512GB SSD", "sku": "DEMO-LAPTOP-1", "price": "145000.00"},
            {"name": "15-inch Gaming Laptop, RTX 4060, 1TB SSD", "sku": "DEMO-LAPTOP-2", "price": "289000.00"},
            {"name": "13-inch Ultralight Laptop, i5, 8GB RAM", "sku": "DEMO-LAPTOP-3", "price": "98000.00"},
        ]
        for spec in products:
            product, created = Product.objects.get_or_create(
                sku=spec["sku"],
                defaults={
                    "store": store,
                    "category": category,
                    "brand": brand,
                    "name": spec["name"],
                    "price": Decimal(spec["price"]),
                    "status": Product.Status.PUBLISHED,
                },
            )
            Stock.objects.get_or_create(
                product=product, warehouse=warehouse, defaults={"quantity": 25, "low_stock_threshold": 5}
            )
            self._report("Product", product.name, created)

        self.stdout.write(self.style.SUCCESS(f"\nDemo password for all accounts: {DEMO_PASSWORD}"))

    def _get_or_create_superuser(self, email):
        user = User.objects.filter(email=email).first()
        if user:
            return user, False
        user = User.objects.create_superuser(email=email, password=DEMO_PASSWORD)
        return user, True

    def _report(self, label, name, created):
        verb = "created" if created else "already exists"
        self.stdout.write(f"{label}: {name} ({verb})")
